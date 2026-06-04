"""Thin MCP client wrapping the Dhara server's kv_timeseries tool group.

The Dhara MCP server (separate repo, `dhara`) exposes five tools under
`TOOL_GROUP_KV_TIME_SERIES`: `put`, `get`, `record_time_series`,
`query_time_series`, and `aggregate_patterns`. This module provides
typed Python wrappers around those tools, plus a connection lifecycle
that's safe to drive from sync code (crackerjack's adapter-learning
call sites are sync and use `asyncio.run` to bridge).

`connect()` returns `bool` and never raises. The factory
(`crackerjack/integration/dhara_integration.py::create_adapter_learner`)
catches all exceptions from learner construction, so the client must
not raise from `connect()` either. Tool methods catch internally and
return `None` or `[]` so a single failed tool call doesn't break the
learner.
"""

from __future__ import annotations

import logging
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# ASCII control characters (0x00-0x1F and 0x7F) are illegal in URLs and
# frequently appear in SSRF / header-smuggling payloads. A bare
# `any(c < 0x20 or c == 0x7F for c in url)` is plenty; we don't need a
# heavyweight regex.
_CONTROL_CHARS: t.Final[frozenset[str]] = frozenset(chr(c) for c in range(0x20)) | {
    "\x7f"
}


@dataclass
class DharaMCPConfig:
    """Configuration for the Dhara MCP client.

    `url` is the BASE URL of the Dhara server. The streamablehttp
    transport appends `/mcp` automatically. `token`, when set, is sent
    as a `Bearer` header on every tool call (the Dhara server gates
    `put` and `record_time_series` with `auth=auth("write")`).

    Security:
    - `url` must use `http` or `https`, have a non-empty host, and
      contain no ASCII control characters. Other schemes (e.g.
      `file://`, `gopher://`) and malformed inputs are rejected with
      `ValueError` to prevent SSRF and accidental misuse.
    - If `token` is set, the URL must be `https://` so the bearer
      token is never sent in cleartext. The local-dev default
      `http://localhost:8683` remains valid *without* a token; the
      check only fires when a token is configured.
    """

    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None

    def __post_init__(self) -> None:
        """Validate the URL and reject insecure token transport.

        Raises:
            ValueError: if the URL fails SSRF-style validation
                (bad scheme, empty host, control characters) or if a
                `token` is configured over a plain-`http://` URL.
        """
        if not isinstance(self.url, str) or not self.url:
            raise ValueError("DharaMCPConfig.url must be a non-empty string")

        if any(c in _CONTROL_CHARS for c in self.url):
            raise ValueError(
                f"DharaMCPConfig.url contains control characters: {self.url!r}"
            )

        try:
            parts = urlsplit(self.url)
        except ValueError as exc:
            raise ValueError(
                f"DharaMCPConfig.url is not a parseable URL: {self.url!r}"
            ) from exc

        if parts.scheme not in {"http", "https"}:
            raise ValueError(
                f"DharaMCPConfig.url must use http or https scheme, "
                f"got {parts.scheme!r}"
            )

        if not parts.hostname:
            raise ValueError(
                f"DharaMCPConfig.url must include a non-empty host: {self.url!r}"
            )

        if self.token and self.url.startswith("http://"):
            raise ValueError(
                "DharaMCPConfig.token is set but url uses http://; "
                "use https:// so the bearer token is not sent in cleartext"
            )


@dataclass
class DharaMCPClient:
    """Thin MCP client wrapping the Dhara server's kv_timeseries tools.

    Lifecycle:
    - Construction does NOT open a connection (lazy).
    - First call to a tool method (or explicit `connect()`) opens the
      transport and runs the MCP initialize handshake.
    - `disconnect()` is idempotent and safe to call from anywhere,
      including from a finalizer at interpreter shutdown.

    Error handling:
    - `connect()` returns `bool`, never raises. The factory is the
      single point that decides fallback policy.
    - Tool methods catch all exceptions internally and return `None`
      or `[]` so a single failed call doesn't break the learner.
    """

    config: DharaMCPConfig
    _client: t.Any = field(init=False, default=None)
    _session: t.Any = field(init=False, default=None)
    _is_connected: bool = field(init=False, default=False)

    async def connect(self) -> bool:
        """Open the MCP session against the configured Dhara server.

        Returns True on success. Returns False (and never raises) on
        any failure: connection refused, timeout, MCP handshake error,
        the streamablehttp cancel-scope RuntimeError documented in
        `mcp-connection-stability-plan.md`, or an ImportError if the
        `mcp` package isn't installed.
        """
        try:
            from mcp import ClientSession
            from mcp.client.streamablehttp import streamablehttp_client

            server_url = self.config.url.rstrip("/")
            # Pass the bearer token as an Authorization header so
            # write-gated tools (`put`, `record_time_series`) work
            # against a Dhara server that requires `auth="write"`.
            # The `timeout` kwarg is respected by the transport
            # so a slow server cannot hang `record_adapter_attempt`.
            headers: dict[str, str] = {}
            if self.config.token:
                headers["Authorization"] = f"Bearer {self.config.token}"
            self._client = streamablehttp_client(
                url=f"{server_url}/mcp",
                headers=headers or None,
                timeout=float(self.config.timeout_seconds),
            )
            self._session = ClientSession(self._client)
            await self._session.__aenter__()
            self._is_connected = True
            return True
        except Exception as exc:
            logger.debug(
                f"DharaMCPClient.connect failed: {type(exc).__name__}: {exc!r}"
            )
            await self._safe_close()
            return False

    async def _safe_close(self) -> None:
        """Close the session and transport without raising.

        Both `__aexit__` calls are wrapped in `suppress(Exception)`
        because the streamablehttp transport can raise the
        cancel-scope RuntimeError during teardown.
        """
        if self._session is not None:
            with suppress(Exception):
                await self._session.__aexit__(None, None, None)
            self._session = None
        if self._client is not None:
            with suppress(Exception):
                await self._client.__aexit__(None, None, None)
            self._client = None
        self._is_connected = False

    async def disconnect(self) -> None:
        """Public close. Idempotent. Equivalent to `_safe_close`."""
        await self._safe_close()

    async def _call_tool(
        self, name: str, arguments: dict[str, t.Any]
    ) -> dict[str, t.Any] | list[dict[str, t.Any]] | None:
        """Invoke a tool on the connected MCP session.

        Returns the tool response data (dict or list), or None if not
        connected or if the call raised. Never propagates exceptions.
        """
        if not self._is_connected or self._session is None:
            logger.debug(f"DharaMCPClient._call_tool({name}): not connected")
            return None
        try:
            response = await self._session.call_tool(name, arguments=arguments)
            data = getattr(response, "data", None)
            if data is None:
                return None
            if isinstance(data, (dict, list)):
                return data
            return {"value": data}
        except Exception as exc:
            logger.debug(
                f"DharaMCPClient._call_tool({name}) failed: "
                f"{type(exc).__name__}: {exc!r}"
            )
            return None

    async def put(
        self,
        key: str,
        value: t.Any,
        ttl: int | None = None,
    ) -> dict[str, t.Any] | None:
        """Wrap the Dhara MCP `put` tool (key/value store with optional TTL)."""
        result = await self._call_tool("put", {"key": key, "value": value, "ttl": ttl})
        if isinstance(result, dict):
            return result
        return None

    async def get(self, key: str) -> dict[str, t.Any] | None:
        """Wrap the Dhara MCP `get` tool (read a key/value record)."""
        result = await self._call_tool("get", {"key": key})
        if isinstance(result, dict):
            return result
        return None

    async def record_time_series(
        self,
        metric_type: str,
        entity_id: str,
        record: dict[str, t.Any],
        timestamp: str | None = None,
    ) -> dict[str, t.Any] | None:
        """Wrap the Dhara MCP `record_time_series` tool (append a time-series record).

        `record` is a free-form dict; include a `pattern` key if you
        want the server's `aggregate_patterns` tool to group on it.
        """
        arguments: dict[str, t.Any] = {
            "metric_type": metric_type,
            "entity_id": entity_id,
            "record": record,
        }
        if timestamp is not None:
            arguments["timestamp"] = timestamp
        result = await self._call_tool("record_time_series", arguments)
        if isinstance(result, dict):
            return result
        return None

    async def query_time_series(
        self,
        metric_type: str,
        entity_id: str,
        start_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, t.Any]]:
        """Wrap the Dhara MCP `query_time_series` tool (read time-series records)."""
        arguments: dict[str, t.Any] = {
            "metric_type": metric_type,
            "entity_id": entity_id,
        }
        if start_date is not None:
            arguments["start_date"] = start_date
        if limit is not None:
            arguments["limit"] = limit
        result = await self._call_tool("query_time_series", arguments)
        if isinstance(result, list):
            return result
        return []

    async def aggregate_patterns(
        self,
        start_date: str,
        min_occurrences: int = 2,
    ) -> list[dict[str, t.Any]]:
        """Wrap the Dhara MCP `aggregate_patterns` tool (group by pattern)."""
        result = await self._call_tool(
            "aggregate_patterns",
            {"start_date": start_date, "min_occurrences": min_occurrences},
        )
        if isinstance(result, list):
            return result
        return []

    async def is_alive(self) -> bool:
        """Return True if the session is connected and a probe tool call succeeds."""
        if not self._is_connected:
            return False
        result = await self._call_tool("get", {"key": "__health__"})
        return result is not None
