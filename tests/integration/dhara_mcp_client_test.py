"""Unit tests for `DharaMCPClient`.

The client wraps `mcp.client.streamablehttp` and translates each Dhara
MCP tool into a typed Python method. These tests use `unittest.mock`
to mock the `ClientSession` and verify the right tool name and
arguments are passed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.integration.dhara_mcp_client import (
    DharaMCPClient,
    DharaMCPConfig,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    """A mock ClientSession with `call_tool` set up as AsyncMock."""
    session = AsyncMock()
    session.call_tool = AsyncMock()
    return session


@pytest.fixture
def client_with_session(mock_session: AsyncMock) -> DharaMCPClient:
    """A `DharaMCPClient` with a mock session already attached.

    Skips the `connect()` handshake so tests can drive tool methods
    directly.
    """
    client = DharaMCPClient(DharaMCPConfig(url="http://test/mcp"))
    client._session = mock_session
    client._is_connected = True
    return client


@pytest.mark.asyncio
async def test_record_time_series_calls_correct_tool(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """`record_time_series` must invoke the underlying MCP `record_time_series`
    tool with the metric_type, entity_id, record, and timestamp arguments."""
    expected_response = MagicMock()
    expected_response.data = {"ok": True, "metric_type": "adapter_attempt"}
    mock_session.call_tool.return_value = expected_response

    result = await client_with_session.record_time_series(
        metric_type="adapter_attempt",
        entity_id="prefect",
        record={"success": True, "execution_time_ms": 42},
        timestamp="2026-06-03T12:00:00+00:00",
    )

    assert result == {"ok": True, "metric_type": "adapter_attempt"}
    mock_session.call_tool.assert_awaited_once()
    call_args = mock_session.call_tool.await_args
    assert call_args.args[0] == "record_time_series"
    arguments = call_args.kwargs["arguments"]
    assert arguments["metric_type"] == "adapter_attempt"
    assert arguments["entity_id"] == "prefect"
    assert arguments["record"] == {"success": True, "execution_time_ms": 42}
    assert arguments["timestamp"] == "2026-06-03T12:00:00+00:00"


@pytest.mark.asyncio
async def test_put_calls_correct_tool(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """`put` must invoke the underlying `put` tool with key, value, and TTL."""
    expected_response = MagicMock()
    expected_response.data = {"ok": True, "key": "test"}
    mock_session.call_tool.return_value = expected_response

    result = await client_with_session.put(key="test", value={"a": 1}, ttl=60)

    assert result == {"ok": True, "key": "test"}
    call_args = mock_session.call_tool.await_args
    assert call_args.args[0] == "put"
    assert call_args.kwargs["arguments"]["key"] == "test"
    assert call_args.kwargs["arguments"]["ttl"] == 60


@pytest.mark.asyncio
async def test_get_calls_correct_tool(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """`get` must invoke the underlying `get` tool with the key."""
    expected_response = MagicMock()
    expected_response.data = {"key": "test", "value": 42}
    mock_session.call_tool.return_value = expected_response

    result = await client_with_session.get(key="test")

    assert result == {"key": "test", "value": 42}
    call_args = mock_session.call_tool.await_args
    assert call_args.args[0] == "get"


@pytest.mark.asyncio
async def test_query_time_series_returns_empty_list_on_tool_error(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """When the underlying tool raises, the wrapper returns `[]` (not None)."""
    mock_session.call_tool.side_effect = RuntimeError("simulated")

    result = await client_with_session.query_time_series(
        metric_type="adapter_attempt", entity_id="prefect"
    )

    assert result == []


@pytest.mark.asyncio
async def test_aggregate_patterns_passes_through_args(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """`aggregate_patterns` must pass start_date and min_occurrences through."""
    expected_response = MagicMock()
    expected_response.data = [{"pattern": "success:prefect", "count": 5}]
    mock_session.call_tool.return_value = expected_response

    result = await client_with_session.aggregate_patterns(
        start_date="2026-06-01", min_occurrences=3
    )

    assert result == [{"pattern": "success:prefect", "count": 5}]
    call_args = mock_session.call_tool.await_args
    assert call_args.args[0] == "aggregate_patterns"
    assert call_args.kwargs["arguments"]["min_occurrences"] == 3


@pytest.mark.asyncio
async def test_connect_returns_false_on_connection_error() -> None:
    """`connect()` must return False (not raise) on transport failure.

    Uses ``sys.modules`` to inject a fake ``mcp.client.streamablehttp``
    whose ``streamablehttp_client`` callable raises ``ConnectionError``.
    This exercises the ``connect()`` try/except path without requiring
    the optional ``streamablehttp`` submodule to actually exist in the
    test environment.
    """
    import sys
    import types

    client = DharaMCPClient(DharaMCPConfig(url="http://unreachable:9999"))
    fake_module = types.ModuleType("mcp.client.streamablehttp")

    def _raise(*args: object, **kwargs: object) -> None:
        raise ConnectionError("refused")

    fake_module.streamablehttp_client = _raise  # type: ignore[attr-defined]
    saved = sys.modules.get("mcp.client.streamablehttp")
    sys.modules["mcp.client.streamablehttp"] = fake_module
    try:
        result = await client.connect()
    finally:
        if saved is None:
            sys.modules.pop("mcp.client.streamablehttp", None)
        else:
            sys.modules["mcp.client.streamablehttp"] = saved

    assert result is False
    assert client._is_connected is False


@pytest.mark.asyncio
async def test_call_tool_returns_none_when_not_connected() -> None:
    """Tool methods on an unconnected client must return None (not raise)."""
    client = DharaMCPClient(DharaMCPConfig(url="http://test/mcp"))
    result = await client.put(key="test", value=42)
    assert result is None


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
    """A bearer token over `https://` is the supported secure path."""
    config = DharaMCPConfig(
        url="https://dhara.example.com", token="secret-token"
    )
    assert config.token == "secret-token"
    assert config.url.startswith("https://")


def test_config_allows_http_without_token() -> None:
    """Plain `http://` is fine when no token is set (local dev)."""
    config = DharaMCPConfig(url="http://localhost:8683")
    assert config.token is None
