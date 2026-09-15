"""Unit tests for `DharaMCPClient`.

After the 2026-09-14 transport migration, this wrapper delegates the
streamable-HTTP lifecycle to :class:`mcp_common.clients.CommonMCPClient`.
These tests monkey-patch the SDK's ``call_tool`` directly so they run
without a live Dhara MCP server.

Wraps ``mcp.client.streamable_http`` and translates each Dhara MCP
tool into a typed Python method.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.integration.dhara_mcp_client import (
    DharaMCPClient,
    DharaMCPConfig,
)


@pytest.fixture
def mock_common() -> AsyncMock:
    """A mock CommonMCPClient whose ``call_tool`` returns a MagicMock-shaped
    payload with ``.data`` populated — matches the FastMCP structured-output
    shape the wrapper's ``_extract_payload`` prefers.
    """
    client = AsyncMock()
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def client_with_common(mock_common: AsyncMock) -> DharaMCPClient:
    """A `DharaMCPClient` with a mock SDK client already attached.

    Skips the ``connect()`` handshake so tests can drive tool methods
    directly. Replaces the pre-migration ``client._session = mock_session``
    fixture.
    """
    client = DharaMCPClient(DharaMCPConfig(url="http://test/mcp"))
    client._client = mock_common
    client._is_connected = True
    return client


@pytest.mark.asyncio
async def test_record_time_series_calls_correct_tool(
    client_with_common: DharaMCPClient, mock_common: AsyncMock
) -> None:
    """`record_time_series` must invoke the underlying MCP `record_time_series`
    tool with the metric_type, entity_id, record, and timestamp arguments."""
    expected_response = MagicMock()
    expected_response.data = {"ok": True, "metric_type": "adapter_attempt"}
    mock_common.call_tool.return_value = expected_response

    result = await client_with_common.record_time_series(
        metric_type="adapter_attempt",
        entity_id="prefect",
        record={"success": True, "execution_time_ms": 42},
        timestamp="2026-06-03T12:00:00+00:00",
    )

    assert result == {"ok": True, "metric_type": "adapter_attempt"}
    mock_common.call_tool.assert_awaited_once()
    call_args = mock_common.call_tool.await_args
    assert call_args.args[0] == "record_time_series"
    arguments = call_args.kwargs["arguments"]
    assert arguments["metric_type"] == "adapter_attempt"
    assert arguments["entity_id"] == "prefect"
    assert arguments["record"] == {"success": True, "execution_time_ms": 42}
    assert arguments["timestamp"] == "2026-06-03T12:00:00+00:00"


@pytest.mark.asyncio
async def test_put_calls_correct_tool(
    client_with_common: DharaMCPClient, mock_common: AsyncMock
) -> None:
    """`put` must invoke the underlying `put` tool with key, value, and TTL."""
    expected_response = MagicMock()
    expected_response.data = {"ok": True, "key": "test"}
    mock_common.call_tool.return_value = expected_response

    result = await client_with_common.put(key="test", value={"a": 1}, ttl=60)

    assert result == {"ok": True, "key": "test"}
    call_args = mock_common.call_tool.await_args
    assert call_args.args[0] == "put"
    assert call_args.kwargs["arguments"]["key"] == "test"
    assert call_args.kwargs["arguments"]["ttl"] == 60


@pytest.mark.asyncio
async def test_get_calls_correct_tool(
    client_with_common: DharaMCPClient, mock_common: AsyncMock
) -> None:
    """`get` must invoke the underlying `get` tool with the key."""
    expected_response = MagicMock()
    expected_response.data = {"key": "test", "value": 42}
    mock_common.call_tool.return_value = expected_response

    result = await client_with_common.get(key="test")

    assert result == {"key": "test", "value": 42}
    call_args = mock_common.call_tool.await_args
    assert call_args.args[0] == "get"


@pytest.mark.asyncio
async def test_query_time_series_returns_empty_list_on_tool_error(
    client_with_common: DharaMCPClient, mock_common: AsyncMock
) -> None:
    """When the underlying tool raises, the wrapper returns `[]` (not None)."""
    mock_common.call_tool.side_effect = RuntimeError("simulated")

    result = await client_with_common.query_time_series(
        metric_type="adapter_attempt", entity_id="prefect"
    )

    assert result == []


@pytest.mark.asyncio
async def test_aggregate_patterns_passes_through_args(
    client_with_common: DharaMCPClient, mock_common: AsyncMock
) -> None:
    """`aggregate_patterns` must pass start_date and min_occurrences through."""
    expected_response = MagicMock()
    expected_response.data = [{"pattern": "success:prefect", "count": 5}]
    mock_common.call_tool.return_value = expected_response

    result = await client_with_common.aggregate_patterns(
        start_date="2026-06-01", min_occurrences=3
    )

    assert result == [{"pattern": "success:prefect", "count": 5}]
    call_args = mock_common.call_tool.await_args
    assert call_args.args[0] == "aggregate_patterns"
    assert call_args.kwargs["arguments"]["min_occurrences"] == 3


@pytest.mark.asyncio
async def test_connect_returns_false_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``connect()`` returns False when ``CommonMCPClient.__aenter__`` raises.

    Patches ``mcp_common.clients.common_mcp_client.CommonMCPClient`` to a
    stub whose ``__aenter__`` raises ``ConnectionError``. This exercises
    the ``connect()`` try/except path without requiring a live Dhara server.
    """
    from mcp_common.clients import common_mcp_client as cmc

    class _BoomClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> None:
            raise ConnectionError("refused")

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(cmc, "CommonMCPClient", _BoomClient)

    client = DharaMCPClient(DharaMCPConfig(url="http://unreachable:9999"))
    result = await client.connect()

    assert result is False
    assert client._is_connected is False
    assert client._client is None


@pytest.mark.asyncio
async def test_connect_returns_false_when_disabled() -> None:
    """``enabled=False`` short-circuits ``connect()`` to False without trying."""
    client = DharaMCPClient(DharaMCPConfig(url="http://test/mcp", enabled=False))
    result = await client.connect()
    assert result is False
    assert client._is_connected is False
    assert client._client is None


@pytest.mark.asyncio
async def test_call_tool_returns_none_when_not_connected() -> None:
    """Tool methods on an unconnected client must return None (not raise)."""
    client = DharaMCPClient(DharaMCPConfig(url="http://test/mcp"))
    result = await client.put(key="test", value=42)
    assert result is None


@pytest.mark.asyncio
async def test_extract_payload_handles_content_only_response() -> None:
    """When result has no ``.data`` but ``.content[0].text`` is JSON, unwrap it.

    Covers the second wire shape FastMCP may emit (raw JSON in content).
    """
    import json as _json

    from crackerjack.integration.dhara_mcp_client import _extract_payload

    result = MagicMock(spec=["content"])
    result.content = [
        MagicMock(spec=["text"], text=_json.dumps({"ok": True, "k": "v"}))
    ]
    # Explicitly: no ``.data`` attribute (spec excludes it).
    payload = _extract_payload(result)
    assert payload == {"ok": True, "k": "v"}


@pytest.mark.asyncio
async def test_extract_payload_returns_none_when_empty() -> None:
    """Empty content + no data → None (caller decides the default)."""
    from crackerjack.integration.dhara_mcp_client import _extract_payload

    result = MagicMock(spec=["content"])
    result.content = []
    assert _extract_payload(result) is None


# --- DharaMCPConfig validation tests ---


def test_config_default_url_localhost_is_valid() -> None:
    """The factory default (localhost http) must remain constructable."""
    config = DharaMCPConfig()
    assert config.url == "http://localhost: 8683"


def test_config_accepts_https_url() -> None:
    """`https://` URLs with a host are accepted."""
    config = DharaMCPConfig(url="https://example.com")
    assert config.url == "https://example.com"


def test_config_accepts_http_ip_literal() -> None:
    """Operators may point at an IP literal (e.g. `127.0.0.1:9000`)."""
    config = DharaMCPConfig(url="http://127.0.0.1:9000")
    assert config.url == "http://127.0.0.1:9000"


def test_config_rejects_file_scheme() -> None:
    """`file://` URLs must be rejected (SSRF / arbitrary-file read)."""
    with pytest.raises(ValueError, match="http or https"):
        DharaMCPConfig(url="file:///etc/passwd")


def test_config_rejects_gopher_scheme() -> None:
    """Non-http schemes like `gopher://` must be rejected."""
    with pytest.raises(ValueError, match="http or https"):
        DharaMCPConfig(url="gopher://evil.example.com/")


def test_config_rejects_empty_host() -> None:
    """URLs without a host (e.g. `http:///path`) must be rejected."""
    with pytest.raises(ValueError, match="non-empty host"):
        DharaMCPConfig(url="http:///path")


def test_config_rejects_control_characters() -> None:
    """URLs containing ASCII control characters must be rejected."""
    with pytest.raises(ValueError, match="control characters"):
        DharaMCPConfig(url="http://example.com/\r\nInjected: header")


def test_config_rejects_token_over_http() -> None:
    """A bearer token over `http://` must be rejected (cleartext leak)."""
    with pytest.raises(ValueError, match="https://"):
        DharaMCPConfig(url="http://localhost:8683", token="secret-token")


def test_config_allows_token_over_https() -> None:
    """`https://` URL with bearer token is the supported secure path."""
    config = DharaMCPConfig(
        url="https://dhara.example.com", token="secret-token"
    )
    assert config.token == "secret-token"
    assert config.url.startswith("https://")


def test_config_allows_http_without_token() -> None:
    """Plain `http://` is fine when no token is set (local dev)."""
    config = DharaMCPConfig(url="http://localhost:8683")
    assert config.token is None
