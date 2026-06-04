"""Unit tests for `DharaMCPClient`.

The client wraps `mcp.client.streamablehttp` and translates each Dhara
MCP tool into a typed Python method. These tests use `unittest.mock`
to mock the `ClientSession` and verify the right tool name and
arguments are passed.
"""

from __future__ import annotations

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

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
