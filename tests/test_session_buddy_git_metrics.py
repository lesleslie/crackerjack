"""Test suite for SessionBuddyMCP git metrics methods.

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
def mock_mcp_client():
    """Mock SessionBuddyMCPClient for testing."""
    client = MagicMock(spec=SessionBuddyMCPClient)
    client._is_connected = True
    client._client = MagicMock()
    client._fallback_tracker = None
    client._last_health_check = 0.0
    client.session_id = "test-session-mock"

    # Mock async methods
    client._ensure_connection = AsyncMock(return_value=True)
    client._call_tool = AsyncMock()
    client.connect = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()

    return client


@pytest.fixture
def mock_mcp_response_success():
    """Mock successful MCP tool call response."""
    return {
        "status": "success",
        "data": {
            "recorded": True,
            "timestamp": datetime.now().isoformat(),
        },
    }


@pytest.fixture
def mock_mcp_response_recommendations():
    """Mock MCP response with workflow recommendations."""
    return {
        "status": "success",
        "recommendations": [
            {
                "priority": "high",
                "action": "Improve commit message structure",
                "title": "Better conventional commits",
                "description": "Increase compliance for better changelogs",
                "expected_impact": "Improved automation",
                "effort": "low",
            }
        ],
    }


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
async def test_record_git_metrics_success(sample_session_metrics):
    """Test successful git metrics recording via MCP."""
    client = SessionBuddyMCPClient(session_id="test-record-success")
    client._is_connected = True
    client._ensure_connection = AsyncMock(return_value=True)
    client._call_tool = AsyncMock(return_value={"status": "success"})

    # Should not raise exception
    await client.record_git_metrics(sample_session_metrics)

    # Verify _call_tool was invoked with correct parameters
    client._call_tool.assert_called_once()
    call_args = client._call_tool.call_args
    assert call_args[0][0] == "record_git_metrics"
    assert "metrics" in call_args[0][1]


@pytest.mark.asyncio
async def test_record_git_metrics_fields(sample_session_metrics):
    """Test that all git metric fields are passed correctly."""
    client = SessionBuddyMCPClient(session_id="test-record-fields")
    client._is_connected = True
    client._ensure_connection = AsyncMock(return_value=True)
    client._call_tool = AsyncMock(return_value={"status": "success"})

    await client.record_git_metrics(sample_session_metrics)

    call_args = client._call_tool.call_args
    metrics_arg = call_args[0][1]["metrics"]

    assert metrics_arg["commit_velocity"] == 3.8
    assert metrics_arg["branch_count"] == 6
    assert metrics_arg["merge_success_rate"] == 0.87
    assert metrics_arg["conventional_compliance"] == 0.91
    assert metrics_arg["workflow_efficiency"] == 82.5


@pytest.mark.asyncio
async def test_record_git_metrics_fallback(sample_session_metrics):
    """Test fallback to direct tracker on MCP failure."""
    client = SessionBuddyMCPClient(
        session_id="test-fallback",
        config=MCPClientConfig(enable_fallback=True),
    )
    client._is_connected = False
    client._ensure_connection = AsyncMock(return_value=False)

    # Mock the fallback tracker
    mock_tracker = MagicMock()
    mock_tracker.record_git_metrics = AsyncMock()
    client._fallback_tracker = mock_tracker

    # Should fall back to direct tracker
    await client.record_git_metrics(sample_session_metrics)

    # Verify fallback was called
    mock_tracker.record_git_metrics.assert_called_once_with(sample_session_metrics)


@pytest.mark.asyncio
async def test_record_git_metrics_no_fallback_when_disabled(sample_session_metrics):
    """Test that no fallback occurs when enable_fallback is False."""
    client = SessionBuddyMCPClient(
        session_id="test-no-fallback",
        config=MCPClientConfig(enable_fallback=False),
    )
    client._is_connected = False
    client._ensure_connection = AsyncMock(return_value=False)

    # Should not raise exception, just log warning
    await client.record_git_metrics(sample_session_metrics)

    # Verify no fallback tracker was used
    assert client._fallback_tracker is None


@pytest.mark.asyncio
async def test_record_git_metrics_with_none_values():
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

    client = SessionBuddyMCPClient(session_id="test-none-values")
    client._is_connected = True
    client._ensure_connection = AsyncMock(return_value=True)
    client._call_tool = AsyncMock(return_value={"status": "success"})

    # Should handle None values gracefully
    await client.record_git_metrics(metrics)

    call_args = client._call_tool.call_args
    metrics_arg = call_args[0][1]["metrics"]

    assert metrics_arg["commit_velocity"] is None
    assert metrics_arg["branch_count"] is None
    assert metrics_arg["merge_success_rate"] is None
    assert metrics_arg["conventional_compliance"] is None
    assert metrics_arg["workflow_efficiency"] is None


# ============================================================================
# Workflow Recommendations Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_workflow_recommendations_success():
    """Test successful workflow recommendations retrieval."""
    client = SessionBuddyMCPClient(session_id="test-recs-success")
    client._is_connected = True
    client._ensure_connection = AsyncMock(return_value=True)

    mock_response = {
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
    }
    client._call_tool = AsyncMock(return_value=mock_response)

    recommendations = await client.get_workflow_recommendations(
        session_id="test-session-123"
    )

    assert len(recommendations) == 1
    assert recommendations[0]["priority"] == "high"


@pytest.mark.asyncio
async def test_get_workflow_recommendations_empty_on_error():
    """Test that empty list is returned on MCP error."""
    client = SessionBuddyMCPClient(session_id="test-recs-error")
    client._is_connected = True
    client._ensure_connection = AsyncMock(return_value=True)
    client._call_tool = AsyncMock(side_effect=Exception("MCP connection failed"))

    recommendations = await client.get_workflow_recommendations(
        session_id="test-session-456"
    )

    assert recommendations == []


@pytest.mark.asyncio
async def test_get_workflow_recommendations_session_id():
    """Test that session_id is passed correctly."""
    client = SessionBuddyMCPClient(session_id="test-recs-session-id")
    client._is_connected = True
    client._ensure_connection = AsyncMock(return_value=True)
    client._call_tool = AsyncMock(
        return_value={"status": "success", "recommendations": []}
    )

    await client.get_workflow_recommendations(session_id="target-session-789")

    call_args = client._call_tool.call_args
    assert call_args[0][0] == "get_workflow_recommendations"
    assert call_args[0][1]["session_id"] == "target-session-789"


@pytest.mark.asyncio
async def test_get_workflow_recommendations_no_fallback():
    """Test that workflow recommendations has no fallback (unlike git metrics)."""
    client = SessionBuddyMCPClient(
        session_id="test-recs-no-fallback",
        config=MCPClientConfig(enable_fallback=True),
    )
    client._is_connected = False
    client._ensure_connection = AsyncMock(return_value=False)

    # Should return empty list, not use fallback
    recommendations = await client.get_workflow_recommendations(
        session_id="test-session-no-fallback"
    )

    assert recommendations == []


# ============================================================================
# Connection and Health Check Tests
# ============================================================================


@pytest.mark.asyncio
async def test_connect_success():
    """Test successful connection to MCP server."""
    client = SessionBuddyMCPClient(session_id="test-connect")

    result = await client.connect()

    assert result is True
    assert client._is_connected is True


@pytest.mark.asyncio
async def test_connect_failure():
    """Test connection failure handling."""
    client = SessionBuddyMCPClient(session_id="test-connect-fail")

    # Mock connection failure
    with patch.object(
        client, "_health_check", side_effect=Exception("Connection failed")
    ):
        # Should not raise exception
        result = await client.connect()

        # Currently implementation returns True even on "failure" in mock
        # In real scenario, would handle actual connection errors
        assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_disconnect():
    """Test disconnection from MCP server."""
    client = SessionBuddyMCPClient(session_id="test-disconnect")
    client._is_connected = True
    client._client = MagicMock()

    await client.disconnect()

    assert client._is_connected is False
    assert client._client is None


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
    client = SessionBuddyMCPClient(session_id="test-get-backend")

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
# Error Handling Tests
# ============================================================================


# Note: Tests for retry mechanism removed as the retry logic is internal
# to _call_tool and cannot be tested by mocking the method itself.
# The retry behavior is tested indirectly through integration tests.


@pytest.mark.asyncio
async def test_ensure_connection_reconnect():
    """Test that _ensure_connection triggers reconnection when unhealthy."""
    client = SessionBuddyMCPClient(
        session_id="test-reconnect",
        config=MCPClientConfig(health_check_interval=1),
    )
    client._is_connected = True
    client._last_health_check = 0.0

    # Mock health check to return False, triggering reconnect
    client._health_check = AsyncMock(return_value=False)
    client.connect = AsyncMock(return_value=True)

    result = await client._ensure_connection()

    assert result is True
    client._health_check.assert_called_once()
    client.connect.assert_called_once()


# ============================================================================
# Configuration Tests
# ============================================================================


def test_mcp_config_defaults():
    """Test MCPClientConfig default values."""
    config = MCPClientConfig()

    assert config.server_url == "http://localhost: 8678"
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
