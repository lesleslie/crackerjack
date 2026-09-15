"""Test suite for SessionBuddyMCP git metrics methods.

Post-migration (2026-09-14): the wrapper delegates transport to
:meth:`mcp_common.clients.CommonMCPClient.call_tool`. These tests mock
the SDK call directly via a stand-in ``client._client`` whose
``.call_tool`` returns a ``MagicMock`` shaped like the real SDK result
(``.data`` populated, ``.content`` empty).

Tests the MCP client integration for recording git metrics and
retrieving workflow recommendations from session-buddy.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest

from crackerjack.integration.session_buddy_mcp import (
    MCPClientConfig,
    SessionBuddyMCPClient,
    create_mcp_client,
)
from crackerjack.models.session_metrics import SessionMetrics


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_session_metrics():
    """Fixture providing SessionMetrics with git data for MCP testing."""
    return SessionMetrics(
        session_id="mcp-test-session-123",
        project_path=Path("/tmp/mcp_test_project"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        end_time=datetime(2025, 2, 11, 11, 30, 0),
        git_commit_velocity=3.8,
        git_branch_count=6,
        git_merge_success_rate=0.87,
        conventional_commit_compliance=0.91,
        git_workflow_efficiency_score=82.5,
        tests_run=120,
        tests_passed=115,
        test_pass_rate=0.958,
    )


@pytest.fixture
def mcp_client_config():
    """Fixture providing MCP client configuration."""
    return MCPClientConfig(
        server_url="http://localhost:8678",
        timeout_seconds=5,
        max_retries=3,
        retry_delay_seconds=1.0,
        health_check_interval=30,
        enable_fallback=True,
    )


@pytest.fixture
def mock_common_result():
    """Build a MagicMock that mimics CommonMCPClient.call_tool's return value.

    ``.data`` is the FastMCP structured-output attribute the wrapper's
    ``_extract_payload`` prefers.
    """
    result = MagicMock(spec=["data", "content"])
    result.content = []
    return result


@pytest.fixture
def client_with_common():
    """A SessionBuddyMCPClient with a fake SDK client pre-attached.

    Replaces the pre-migration ``client._call_tool = AsyncMock(...)`` pattern.
    Tests that use this fixture should set ``mock_common.call_tool.return_value``
    directly on the returned client._client.call_tool.
    """
    client = SessionBuddyMCPClient(session_id="test-session")
    client._client = AsyncMock()
    client._client.call_tool = AsyncMock()
    client._is_connected = True
    return client


# ============================================================================
# Initialization Tests
# ============================================================================


def test_mcp_client_initialization_default_config():
    """Test SessionBuddyMCPClient initialization with default config."""
    client = SessionBuddyMCPClient()

    assert client.session_id == "default"
    assert isinstance(client.config, MCPClientConfig)
    assert client._is_connected is False
    assert client._client is None


def test_mcp_client_initialization_custom_config(mcp_client_config):
    """Test SessionBuddyMCPClient initialization with custom config."""
    client = SessionBuddyMCPClient(
        session_id="custom-session",
        config=mcp_client_config,
    )

    assert client.session_id == "custom-session"
    assert client.config.server_url == "http://localhost:8678"
    assert client.config.timeout_seconds == 5
    assert client.config.enable_fallback is True


def test_create_mcp_client_factory():
    """Test create_mcp_client factory function."""
    client = create_mcp_client(session_id="factory-session")

    assert isinstance(client, SessionBuddyMCPClient)
    assert client.session_id == "factory-session"


def test_create_mcp_client_with_custom_config(mcp_client_config):
    """Test create_mcp_client with custom configuration."""
    client = create_mcp_client(
        session_id="factory-custom",
        config=mcp_client_config,
    )

    assert client.session_id == "factory-custom"
    assert client.config == mcp_client_config


# ============================================================================
# Git Metrics Recording Tests
# ============================================================================


@pytest.mark.asyncio
async def test_record_git_metrics_success(sample_session_metrics, client_with_common):
    """Test successful git metrics recording via MCP."""
    client_with_common._client.call_tool.return_value = MagicMock(
        spec=["data", "content"], data={"status": "success"}, content=[]
    )

    # Should not raise exception
    await client_with_common.record_git_metrics(sample_session_metrics)

    # Verify call_tool was invoked with correct parameters
    client_with_common._client.call_tool.assert_awaited_once()
    call_args = client_with_common._client.call_tool.await_args
    assert call_args.args[0] == "record_git_metrics"
    assert "metrics" in call_args.kwargs["arguments"]


@pytest.mark.asyncio
async def test_record_git_metrics_fields(sample_session_metrics, client_with_common):
    """Test that all git metric fields are passed correctly."""
    client_with_common._client.call_tool.return_value = MagicMock(
        spec=["data", "content"], data={"status": "success"}, content=[]
    )

    await client_with_common.record_git_metrics(sample_session_metrics)

    call_args = client_with_common._client.call_tool.await_args
    metrics_arg = call_args.kwargs["arguments"]["metrics"]

    assert metrics_arg["commit_velocity"] == 3.8
    assert metrics_arg["branch_count"] == 6
    assert metrics_arg["merge_success_rate"] == 0.87
    assert metrics_arg["conventional_compliance"] == 0.91
    assert metrics_arg["workflow_efficiency"] == 82.5


@pytest.mark.asyncio
async def test_record_git_metrics_fallback(sample_session_metrics):
    """Test fallback to direct tracker when MCP connect fails."""
    client = SessionBuddyMCPClient(
        session_id="test-fallback",
        config=MCPClientConfig(enable_fallback=True),
    )
    # Force connect() to fail so the fallback path runs.
    client.connect = AsyncMock(return_value=False)

    mock_tracker = MagicMock()
    mock_tracker.record_git_metrics = AsyncMock()
    client._fallback_tracker = mock_tracker

    await client.record_git_metrics(sample_session_metrics)

    mock_tracker.record_git_metrics.assert_called_once_with(sample_session_metrics)


@pytest.mark.asyncio
async def test_record_git_metrics_no_fallback_when_disabled(sample_session_metrics):
    """Test that no fallback occurs when enable_fallback is False."""
    client = SessionBuddyMCPClient(
        session_id="test-no-fallback",
        config=MCPClientConfig(enable_fallback=False),
    )
    client.connect = AsyncMock(return_value=False)

    # Should not raise exception, just log warning
    await client.record_git_metrics(sample_session_metrics)

    assert client._fallback_tracker is None


@pytest.mark.asyncio
async def test_record_git_metrics_with_none_values(client_with_common):
    """Test recording metrics with None values."""
    metrics = SessionMetrics(
        session_id="none-metrics",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
        git_commit_velocity=None,
        git_branch_count=None,
        git_merge_success_rate=None,
        conventional_commit_compliance=None,
        git_workflow_efficiency_score=None,
    )

    client_with_common._client.call_tool.return_value = MagicMock(
        spec=["data", "content"], data=None, content=[]
    )

    # Should handle None values gracefully
    await client_with_common.record_git_metrics(metrics)

    call_args = client_with_common._client.call_tool.await_args
    metrics_arg = call_args.kwargs["arguments"]["metrics"]

    assert metrics_arg["commit_velocity"] is None
    assert metrics_arg["branch_count"] is None
    assert metrics_arg["merge_success_rate"] is None
    assert metrics_arg["conventional_compliance"] is None
    assert metrics_arg["workflow_efficiency"] is None


# ============================================================================
# Workflow Recommendations Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_workflow_recommendations_success(client_with_common):
    """Test successful workflow recommendations retrieval."""
    client_with_common._client.call_tool.return_value = MagicMock(
        spec=["data", "content"],
        data={
            "status": "success",
            "recommendations": [
                {
                    "priority": "high",
                    "action": "Improve branch hygiene",
                    "title": "Reduce branch count",
                    "description": "Too many active branches",
                    "expected_impact": "Faster integration",
                    "effort": "medium",
                }
            ],
        },
        content=[],
    )

    recommendations = await client_with_common.get_workflow_recommendations(
        session_id="test-session-123"
    )

    assert len(recommendations) == 1
    assert recommendations[0]["priority"] == "high"


@pytest.mark.asyncio
async def test_get_workflow_recommendations_empty_on_error(client_with_common):
    """Test that empty list is returned on MCP transport failure."""
    client_with_common._client.call_tool.side_effect = RuntimeError(
        "MCP connection failed"
    )

    recommendations = await client_with_common.get_workflow_recommendations(
        session_id="test-session-456"
    )

    assert recommendations == []


@pytest.mark.asyncio
async def test_get_workflow_recommendations_session_id(client_with_common):
    """Test that session_id is passed correctly."""
    client_with_common._client.call_tool.return_value = MagicMock(
        spec=["data", "content"],
        data={"status": "success", "recommendations": []},
        content=[],
    )

    await client_with_common.get_workflow_recommendations(session_id="target-session-789")

    call_args = client_with_common._client.call_tool.await_args
    assert call_args.args[0] == "get_workflow_recommendations"
    assert call_args.kwargs["arguments"]["session_id"] == "target-session-789"


@pytest.mark.asyncio
async def test_get_workflow_recommendations_no_fallback():
    """Test that workflow recommendations has no fallback (unlike git metrics)."""
    client = SessionBuddyMCPClient(
        session_id="test-recs-no-fallback",
        config=MCPClientConfig(enable_fallback=True),
    )
    client.connect = AsyncMock(return_value=False)

    recommendations = await client.get_workflow_recommendations(
        session_id="test-session-no-fallback"
    )

    assert recommendations == []


# ============================================================================
# Connection and Disconnect Tests (post-migration)
# ============================================================================


@pytest.mark.asyncio
async def test_connect_returns_false_when_sdk_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``connect()`` returns False when ``CommonMCPClient.__aenter__`` raises."""
    from mcp_common.clients import common_mcp_client as cmc

    class _BoomClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> None:
            raise ConnectionError("refused")

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(cmc, "CommonMCPClient", _BoomClient)

    client = SessionBuddyMCPClient(session_id="test-connect-fail")
    result = await client.connect()

    assert result is False
    assert client._is_connected is False
    assert client._client is None


@pytest.mark.asyncio
async def test_disconnect_with_attached_sdk_client() -> None:
    """``disconnect()`` clears the SDK client and flips the connected flag."""
    client = SessionBuddyMCPClient(session_id="test-disconnect")
    sdk = AsyncMock()
    sdk.aclose = AsyncMock()
    client._client = sdk
    client._is_connected = True

    await client.disconnect()

    sdk.aclose.assert_awaited_once()
    assert client._is_connected is False
    assert client._client is None


# ============================================================================
# Introspection Tests
# ============================================================================


def test_is_connected():
    """Test is_connected property."""
    client = SessionBuddyMCPClient(session_id="test-is-connected")

    assert client.is_connected() is False

    client._is_connected = True
    assert client.is_connected() is True


def test_is_enabled():
    """Test is_enabled property."""
    # With fallback disabled
    client = SessionBuddyMCPClient(
        session_id="test-is-enabled",
        config=MCPClientConfig(enable_fallback=False),
    )
    # Not enabled when no connection and no fallback
    assert client.is_enabled() is False

    # Enabled when connected
    client._is_connected = True
    assert client.is_enabled() is True

    # With fallback enabled (creates tracker automatically)
    client2 = SessionBuddyMCPClient(
        session_id="test-is-enabled-2",
        config=MCPClientConfig(enable_fallback=True),
    )
    # Should be enabled because fallback tracker is created
    assert client2.is_enabled() is True


def test_get_backend():
    """Test get_backend method."""
    # Fallback disabled so no fallback tracker is auto-created
    client = SessionBuddyMCPClient(
        session_id="test-get-backend",
        config=MCPClientConfig(enable_fallback=False),
    )

    # No backend
    assert client.get_backend() == "none"

    # MCP backend
    client._is_connected = True
    assert client.get_backend() == "mcp"

    # Direct fallback backend
    client._is_connected = False
    mock_tracker = MagicMock()
    mock_tracker.get_backend = MagicMock(return_value="direct")
    client._fallback_tracker = mock_tracker
    assert "direct-fallback" in client.get_backend()


# ============================================================================
# Type Safety Tests
# ============================================================================


def test_git_metrics_type_safety_import():
    """Test that TYPE_CHECKING import prevents circular dependency."""
    # This test verifies that the module can be imported without circular deps
    from crackerjack.integration import session_buddy_mcp

    # SessionMetrics should be available in TYPE_CHECKING block
    assert hasattr(session_buddy_mcp, "SessionBuddyMCPClient")
    assert hasattr(session_buddy_mcp, "MCPClientConfig")


# ============================================================================
# Configuration Tests
# ============================================================================


def test_mcp_config_defaults():
    """Test MCPClientConfig default values."""
    config = MCPClientConfig()

    assert config.server_url == "http://localhost:8678"
    assert config.timeout_seconds == 5
    assert config.max_retries == 3
    assert config.retry_delay_seconds == 1.0
    assert config.health_check_interval == 30
    assert config.enable_fallback is True


def test_mcp_config_custom_values():
    """Test MCPClientConfig with custom values."""
    config = MCPClientConfig(
        server_url="http://custom-server:9000",
        timeout_seconds=10,
        max_retries=5,
        retry_delay_seconds=2.0,
        health_check_interval=60,
        enable_fallback=False,
    )

    assert config.server_url == "http://custom-server:9000"
    assert config.timeout_seconds == 10
    assert config.max_retries == 5
    assert config.retry_delay_seconds == 2.0
    assert config.health_check_interval == 60
    assert config.enable_fallback is False


# ============================================================================
# Extract-payload helpers
# ============================================================================


@pytest.mark.asyncio
async def test_extract_payload_handles_structured_data() -> None:
    """``result.data`` dict is returned verbatim."""
    from crackerjack.integration.session_buddy_mcp import _extract_payload

    result = MagicMock(spec=["data", "content"])
    result.data = {"ok": True, "value": 42}
    result.content = []
    assert _extract_payload(result) == {"ok": True, "value": 42}


@pytest.mark.asyncio
async def test_extract_payload_handles_content_only_json() -> None:
    """``result.content[0].text`` JSON is parsed into a dict."""
    import json as _json

    from crackerjack.integration.session_buddy_mcp import _extract_payload

    result = MagicMock(spec=["content"])
    result.content = [MagicMock(spec=["text"], text=_json.dumps({"k": "v"}))]
    assert _extract_payload(result) == {"k": "v"}


@pytest.mark.asyncio
async def test_extract_payload_returns_none_when_empty() -> None:
    """Empty content + no data → None."""
    from crackerjack.integration.session_buddy_mcp import _extract_payload

    result = MagicMock(spec=["data", "content"])
    result.data = None
    result.content = []
    assert _extract_payload(result) is None
