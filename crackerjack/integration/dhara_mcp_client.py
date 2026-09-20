"""Async MCP client for Dhara's MCP server.

.. deprecated::
    The Dhara MCP server is being absorbed into Mahavishnu / Oneiric /
    AkoSHA / Crackerjack per the Dhara decomposition plan. Phase 8 of
    that plan retires the Dhara MCP server entirely; this wrapper is
    deleted wholesale in the same commit.

    See:
    ``mahavishnu/docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md``

    Migration targets when the time comes:

    - ``mcp__mahavishnu__upsert_service`` (was ``dhara_upsert_service``)
    - ``mcp__mahavishnu__record_event`` (was ``dhara_record_event``)

    No shim is shipped here; that is a downstream call-site change.

Transport migration:
    This module's bespoke ``streamable_http_client`` lifecycle was
    replaced with :class:`mcp_common.clients.CommonMCPClient` on
    2026-09-14 (see
    ``mahavishnu/docs/plans/2026-09-14-common-mcp-client-transport-unification.md``
    — the plan listed only the crackerjack smoke test under
    crackerjack's obligations, but two bespoke transports lived in
    ``crackerjack/integration/`` and were migrated in tandem).

    The public surface (``DharaMCPConfig`` + ``DharaMCPClient``) is
    preserved 1-for-1 so production callers
    (:mod:`crackerjack.services.failure_metrics_repository`,
    :mod:`crackerjack.integration.dhara_integration`) and the
    existing test fixtures continue to work unchanged.
"""

from __future__ import annotations

import json
import logging
import typing as t
from dataclasses import dataclass, field
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


_CONTROL_CHARS: t.Final[frozenset[str]] = frozenset(chr(c) for c in range(0x20)) | {
    "\x7f"
}


@dataclass
class DharaMCPConfig:
    url: str = "http://localhost: 8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None

    def __post_init__(self) -> None:
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


def _extract_payload(
    result: t.Any,
) -> dict[str, t.Any] | list[dict[str, t.Any]] | None:
    """Unwrap an MCP tool-call result to its dict/list payload.

    Handles the two wire shapes the upstream MCP SDK may return:

    1. Structured output: ``result.data`` is set to a dict/list.
    2. Plain text: ``result.content`` is a list of ``TextContent``
       items whose ``.text`` holds the JSON string.
    """
    data = getattr(result, "data", None)
    if isinstance(data, (dict, list)):
        return data

    content = getattr(result, "content", None)
    if content:
        for item in content:
            text = getattr(item, "text", None)
            if text:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return {"value": text}
                if isinstance(parsed, (dict, list)):
                    return parsed
                return {"value": parsed}

    if data is not None:
        return {"value": data}
    return None


@dataclass
class DharaMCPClient:
    config: DharaMCPConfig
    _client: t.Any = field(init=False, default=None)
    _is_connected: bool = field(init=False, default=False)

    def _mcp_url(self) -> str:
        """Build the MCP endpoint URL (``<base>/mcp`` if not already present)."""
        base = self.config.url.rstrip("/")
        return base if base.endswith("/mcp") else f"{base}/mcp"

    async def connect(self) -> bool:
        """Open the MCP session via :class:`CommonMCPClient`.

        Returns ``True`` on success, ``False`` on any error or when
        ``config.enabled`` is ``False``. Subsequent tool methods
        (``put``, ``get``, ``record_time_series``, ...) reuse this
        session and return ``None``/``[]`` when not connected.
        """
        if not self.config.enabled:
            logger.debug("DharaMCPClient.connect: disabled by config")
            return False
        if self._is_connected and self._client is not None:
            return True

        await self._safe_close()

        from mcp_common.clients.common_mcp_client import CommonMCPClient

        try:
            client = CommonMCPClient(
                base_url=self._mcp_url(),
                timeout=float(self.config.timeout_seconds),
                token=self.config.token,
            )
            await client.__aenter__()
        except Exception as exc:
            logger.debug(
                f"DharaMCPClient.connect failed: {type(exc).__name__}: {exc!r}"
            )
            await self._safe_close()
            return False

        self._client = client
        self._is_connected = True
        return True

    async def _safe_close(self) -> None:
        """Close the SDK client, swallowing cross-task and other teardown errors."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except RuntimeError as exc:
                # CommonMCPClient already tolerates cross-task aclose
                # with a DEBUG log; surface any other RuntimeError.
                if "different task" not in str(exc):
                    logger.debug(f"DharaMCPClient: aclose runtime error: {exc!r}")
            except Exception as exc:
                logger.debug(f"DharaMCPClient: aclose failed: {exc!r}")
            finally:
                self._client = None
        self._is_connected = False

    async def disconnect(self) -> None:
        await self._safe_close()

    async def _call_tool(
        self, name: str, arguments: dict[str, t.Any]
    ) -> dict[str, t.Any] | list[dict[str, t.Any]] | None:
        """Invoke an MCP tool. Returns None on any failure (best-effort)."""
        if not self._is_connected or self._client is None:
            logger.debug(f"DharaMCPClient._call_tool({name}): not connected")
            return None
        try:
            response = await self._client.call_tool(name, arguments=arguments)
        except Exception as exc:
            logger.debug(
                f"DharaMCPClient._call_tool({name}) failed: "
                f"{type(exc).__name__}: {exc!r}"
            )
            return None
        return _extract_payload(response)

    async def put(
        self,
        key: str,
        value: t.Any,
        ttl: int | None = None,
    ) -> dict[str, t.Any] | None:
        result = await self._call_tool("put", {"key": key, "value": value, "ttl": ttl})
        if isinstance(result, dict):
            return result
        return None

    async def get(self, key: str) -> dict[str, t.Any] | None:
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
        result = await self._call_tool(
            "aggregate_patterns",
            {"start_date": start_date, "min_occurrences": min_occurrences},
        )
        if isinstance(result, list):
            return result
        return []

    async def is_alive(self) -> bool:
        if not self._is_connected:
            return False
        result = await self._call_tool("get", {"key": "__health__"})
        return result is not None
