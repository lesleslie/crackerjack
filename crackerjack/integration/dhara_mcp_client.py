from __future__ import annotations

import logging
import typing as t
from contextlib import suppress
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


@dataclass
class DharaMCPClient:
    config: DharaMCPConfig
    _client: t.Any = field(init=False, default=None)
    _session: t.Any = field(init=False, default=None)
    _is_connected: bool = field(init=False, default=False)

    async def connect(self) -> bool:
        try:
            from mcp import ClientSession
            from mcp.client.streamablehttp import streamablehttp_client

            server_url = self.config.url.rstrip("/")

            headers: dict[str, str] = {}
            if self.config.token:
                headers["Authorization"] = f"Bearer {self.config.token}"
            self._client = streamablehttp_client(
                url=f"{server_url}/mcp",
                headers=headers or None,
                timeout=float(self.config.timeout_seconds),
            )

            read_stream, write_stream, _ = await self._client.__aenter__()
            self._session = ClientSession(read_stream, write_stream)
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
        await self._safe_close()

    async def _call_tool(
        self, name: str, arguments: dict[str, t.Any]
    ) -> dict[str, t.Any] | list[dict[str, t.Any]] | None:
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
