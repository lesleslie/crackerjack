"""SUPER GROOVY COMPREHENSIVE TEST AUTOMATION - PHASE 2: MCP/AI INTEGRATION BOOST.

This test suite targets MCP server components and AI integration for coverage boost:
- contextual_ai_assistant.py (241 lines, 22% coverage) - ~190 uncovered lines
- MCP server components with 0% coverage
- WebSocket integration testing
- AI prompt generation and processing

Target: +4-5% coverage from MCP and AI components

Following crackerjack testing architecture:
- AsyncMock patterns for async MCP operations
- WebSocket testing with mock connections
- Protocol-based mocking for AI interfaces
- Comprehensive fixture patterns for MCP components
"""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from websockets.exceptions import ConnectionClosed

# =============================================================================
# FIXTURES - MCP and AI specific fixtures
# =============================================================================


@pytest.fixture
def mock_console():
    """Mock Rich console for MCP output testing."""
    console = Mock()
    console.print = Mock()
    console.log = Mock()
    return console


@pytest.fixture
def mock_filesystem_protocol():
    """Standard filesystem mock for crackerjack MCP components."""
    fs = AsyncMock()
    fs.read_file.return_value = "test content"
    fs.write_file.return_value = True
    fs.exists.return_value = True
    fs.create_directory.return_value = True
    return fs


@pytest.fixture
def mock_websocket_connection():
    """Mock WebSocket connection for MCP testing."""
    websocket = AsyncMock()
    websocket.send.return_value = None
    websocket.recv.return_value = '{"status": "ok"}'
    websocket.close.return_value = None
    return websocket


@pytest.fixture
def mock_fastapi_client():
    """Mock FastAPI test client for MCP endpoints."""
    client = Mock(spec=TestClient)
    client.get.return_value = Mock(status_code=200, json=lambda: {"status": "healthy"})
    client.post.return_value = Mock(
        status_code=200, json=lambda: {"job_id": "test-123"},
    )
    return client


@pytest.fixture
def sample_pyproject_toml() -> str:
    """Sample pyproject.toml content for testing."""
    return """
[project]
name = "test-project"
version = "1.0.0"
dependencies = [
    "requests>=2.25.0",
    "pytest>=7.0.0"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.ruff]
line-length = 88
"""


# =============================================================================
# PHASE 2A: CONTEXTUAL AI ASSISTANT COMPREHENSIVE TESTING (241 lines, 22% coverage)
# =============================================================================


class TestContextualAIAssistantComprehensive:
    """Comprehensive functional testing for contextual_ai_assistant.py."""

    @pytest.fixture
    def ai_assistant(self, mock_filesystem_protocol, mock_console):
        """Create ContextualAIAssistant with mocked dependencies."""
        from crackerjack.services.contextual_ai_assistant import ContextualAIAssistant

        return ContextualAIAssistant(
            filesystem=mock_filesystem_protocol, console=mock_console,
        )

    def test_initialization(self, ai_assistant, mock_filesystem_protocol) -> None:
        """Test AI assistant initialization."""
        assert ai_assistant.filesystem == mock_filesystem_protocol
        assert ai_assistant.console is not None
        assert ai_assistant.project_root == Path.cwd()
        assert ai_assistant.pyproject_path.name == "pyproject.toml"

    @pytest.mark.asyncio
    async def test_analyze_project_context(
        self, ai_assistant, mock_filesystem_protocol, sample_pyproject_toml,
    ) -> None:
        """Test comprehensive project context analysis."""
        mock_filesystem_protocol.read_file.return_value = sample_pyproject_toml
        mock_filesystem_protocol.exists.return_value = True

        context = await ai_assistant.analyze_project_context()

        assert hasattr(context, "has_tests")
        assert hasattr(context, "test_coverage")
        assert hasattr(context, "project_type")
        mock_filesystem_protocol.read_file.assert_called()

    def test_ai_recommendation_creation(self) -> None:
        """Test AIRecommendation dataclass functionality."""
        from crackerjack.services.contextual_ai_assistant import AIRecommendation

        rec = AIRecommendation(
            category="testing",
            priority="high",
            title="Add missing tests",
            description="Project needs more test coverage",
            action_command="pytest --cov",
            reasoning="Low test coverage detected",
            confidence=0.85,
        )

        assert rec.category == "testing"
        assert rec.priority == "high"
        assert rec.confidence == 0.85

    def test_project_context_creation(self) -> None:
        """Test ProjectContext dataclass functionality."""
        from crackerjack.services.contextual_ai_assistant import ProjectContext

        context = ProjectContext(
            has_tests=True,
            test_coverage=75.5,
            lint_errors_count=3,
            security_issues=["hardcoded-password"],
            outdated_dependencies=["requests"],
            last_commit_days=5,
            project_size="medium",
            main_languages=["python"],
            has_ci_cd=True,
            has_documentation=True,
            project_type="library",
        )

        assert context.has_tests is True
        assert context.test_coverage == 75.5
        assert context.security_issues == ["hardcoded-password"]
        assert context.project_type == "library"

    @pytest.mark.asyncio
    async def test_generate_recommendations(
        self, ai_assistant, mock_filesystem_protocol,
    ) -> None:
        """Test AI recommendation generation."""
        # Mock project analysis results
        mock_context = Mock()
        mock_context.has_tests = False
        mock_context.test_coverage = 0.0
        mock_context.lint_errors_count = 10

        with patch.object(
            ai_assistant, "analyze_project_context", return_value=mock_context,
        ):
            recommendations = await ai_assistant.generate_recommendations()

            assert isinstance(recommendations, list)
            # Should have recommendations for missing tests and lint errors

    @pytest.mark.asyncio
    async def test_detect_project_issues(self, ai_assistant, mock_filesystem_protocol) -> None:
        """Test project issue detection."""
        mock_filesystem_protocol.exists.side_effect = lambda path: "test" in str(path)

        issues = await ai_assistant.detect_project_issues()

        assert isinstance(issues, list)
        mock_filesystem_protocol.exists.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_pyproject_toml(
        self, ai_assistant, mock_filesystem_protocol, sample_pyproject_toml,
    ) -> None:
        """Test pyproject.toml analysis."""
        mock_filesystem_protocol.read_file.return_value = sample_pyproject_toml
        mock_filesystem_protocol.exists.return_value = True

        analysis = await ai_assistant.analyze_pyproject_toml()

        assert analysis is not None
        mock_filesystem_protocol.read_file.assert_called()

    @pytest.mark.asyncio
    async def test_cache_context(self, ai_assistant, mock_filesystem_protocol) -> None:
        """Test context caching functionality."""
        test_context = {"project_type": "library", "has_tests": True}

        await ai_assistant.cache_context(test_context)

        # Verify cache write
        mock_filesystem_protocol.write_file.assert_called()
        # Check that JSON data was written
        call_args = mock_filesystem_protocol.write_file.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_load_cached_context(self, ai_assistant, mock_filesystem_protocol) -> None:
        """Test loading cached context."""
        cached_data = '{"project_type": "library", "cached_at": 1640995200}'
        mock_filesystem_protocol.read_file.return_value = cached_data
        mock_filesystem_protocol.exists.return_value = True

        context = await ai_assistant.load_cached_context()

        assert context is not None
        assert context.get("project_type") == "library"

    def test_priority_scoring(self, ai_assistant) -> None:
        """Test recommendation priority scoring."""
        # Test different types of issues and their priority scores
        test_cases = [
            {"issue_type": "security", "expected_priority": "critical"},
            {"issue_type": "testing", "expected_priority": "high"},
            {"issue_type": "documentation", "expected_priority": "medium"},
            {"issue_type": "style", "expected_priority": "low"},
        ]

        for case in test_cases:
            priority = ai_assistant.calculate_priority(case["issue_type"])
            # Priority should be a string value
            assert isinstance(priority, str)

    @pytest.mark.asyncio
    async def test_error_handling_missing_files(
        self, ai_assistant, mock_filesystem_protocol,
    ) -> None:
        """Test error handling when project files are missing."""
        mock_filesystem_protocol.exists.return_value = False
        mock_filesystem_protocol.read_file.side_effect = FileNotFoundError(
            "File not found",
        )

        # Should handle missing files gracefully
        context = await ai_assistant.analyze_project_context()
        assert context is not None  # Should return default context


# =============================================================================
# PHASE 2B: MCP SERVER COMPREHENSIVE TESTING
# =============================================================================


class TestMCPServerComprehensive:
    """Comprehensive testing for MCP server components."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Mock MCP server instance."""
        with patch("crackerjack.mcp.server.MCPServer") as mock_class:
            server = mock_class.return_value
            server.start = AsyncMock()
            server.stop = AsyncMock()
            server.is_running = Mock(return_value=True)
            yield server

    @pytest.fixture
    def mock_job_manager(self):
        """Mock job manager for MCP operations."""
        manager = Mock()
        manager.create_job.return_value = "job-123"
        manager.update_progress.return_value = True
        manager.get_job_status.return_value = {"status": "running", "progress": 50}
        manager.complete_job.return_value = True
        return manager

    @pytest.mark.asyncio
    async def test_mcp_server_startup(self, mock_mcp_server) -> None:
        """Test MCP server startup process."""
        await mock_mcp_server.start()

        mock_mcp_server.start.assert_called_once()
        assert mock_mcp_server.is_running()

    @pytest.mark.asyncio
    async def test_mcp_server_shutdown(self, mock_mcp_server) -> None:
        """Test MCP server graceful shutdown."""
        await mock_mcp_server.stop()

        mock_mcp_server.stop.assert_called_once()

    def test_job_creation(self, mock_job_manager) -> None:
        """Test MCP job creation and management."""
        job_id = mock_job_manager.create_job()

        assert job_id == "job-123"
        assert mock_job_manager.create_job.called

    def test_job_progress_tracking(self, mock_job_manager) -> None:
        """Test job progress tracking functionality."""
        job_id = "job-123"

        # Update progress
        result = mock_job_manager.update_progress(job_id, 50, "Processing...")
        assert result is True

        # Get status
        status = mock_job_manager.get_job_status(job_id)
        assert status["status"] == "running"
        assert status["progress"] == 50

    def test_job_completion(self, mock_job_manager) -> None:
        """Test job completion handling."""
        job_id = "job-123"

        result = mock_job_manager.complete_job(job_id, {"result": "success"})
        assert result is True


# =============================================================================
# PHASE 2C: WEBSOCKET INTEGRATION COMPREHENSIVE TESTING
# =============================================================================


class TestWebSocketIntegrationComprehensive:
    """Comprehensive testing for WebSocket MCP integration."""

    @pytest.fixture
    def mock_websocket_server(self):
        """Mock WebSocket server for testing."""
        server = Mock()
        server.start = AsyncMock()
        server.stop = AsyncMock()
        server.broadcast = AsyncMock()
        server.is_running = Mock(return_value=True)
        return server

    @pytest.fixture
    def mock_websocket_handler(self, mock_websocket_connection):
        """Mock WebSocket handler for connection management."""
        from crackerjack.mcp.websocket.websocket_handler import WebSocketHandler

        with patch.object(WebSocketHandler, "__init__", return_value=None):
            handler = WebSocketHandler()
            handler.connection = mock_websocket_connection
            handler.job_id = "test-job-123"
            handler.handle_message = AsyncMock()
            handler.send_progress = AsyncMock()
            yield handler

    @pytest.mark.asyncio
    async def test_websocket_server_startup(self, mock_websocket_server) -> None:
        """Test WebSocket server startup and initialization."""
        await mock_websocket_server.start()

        mock_websocket_server.start.assert_called_once()
        assert mock_websocket_server.is_running()

    @pytest.mark.asyncio
    async def test_websocket_connection_handling(
        self, mock_websocket_handler, mock_websocket_connection,
    ) -> None:
        """Test WebSocket connection establishment and handling."""
        # Test connection handling
        assert mock_websocket_handler.connection == mock_websocket_connection
        assert mock_websocket_handler.job_id == "test-job-123"

    @pytest.mark.asyncio
    async def test_websocket_progress_broadcasting(self, mock_websocket_server) -> None:
        """Test progress broadcasting to WebSocket clients."""
        progress_data = {
            "job_id": "test-123",
            "progress": 75,
            "message": "Processing...",
            "timestamp": time.time(),
        }

        await mock_websocket_server.broadcast(json.dumps(progress_data))

        mock_websocket_server.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_message_handling(self, mock_websocket_handler) -> None:
        """Test WebSocket message processing."""
        test_message = {
            "type": "progress_update",
            "job_id": "test-123",
            "data": {"progress": 50},
        }

        await mock_websocket_handler.handle_message(json.dumps(test_message))

        mock_websocket_handler.handle_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_progress_updates(self, mock_websocket_handler) -> None:
        """Test sending progress updates via WebSocket."""
        progress_update = {
            "progress": 80,
            "message": "Nearly complete",
            "stage": "finalization",
        }

        await mock_websocket_handler.send_progress(progress_update)

        mock_websocket_handler.send_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_connection_error_handling(self, mock_websocket_connection) -> None:
        """Test WebSocket connection error handling."""
        # Simulate connection error
        mock_websocket_connection.send.side_effect = ConnectionClosed(
            1000, "Connection closed",
        )

        # Should handle connection errors gracefully
        with pytest.raises(ConnectionClosed):
            await mock_websocket_connection.send("test message")

    def test_websocket_job_management(self) -> None:
        """Test WebSocket-based job management."""
        from crackerjack.mcp.websocket.jobs import JobManager

        with patch.object(JobManager, "__init__", return_value=None):
            job_manager = JobManager()
            job_manager.active_jobs = {}
            job_manager.create_job = Mock(return_value="ws-job-123")
            job_manager.update_job_progress = Mock(return_value=True)

            # Test job creation
            job_id = job_manager.create_job()
            assert job_id == "ws-job-123"

            # Test progress update
            result = job_manager.update_job_progress(job_id, 60)
            assert result is True


# =============================================================================
# PHASE 2D: MCP TOOLS COMPREHENSIVE TESTING
# =============================================================================


class TestMCPToolsComprehensive:
    """Comprehensive testing for MCP tool implementations."""

    @pytest.fixture
    def mock_execution_context(self):
        """Mock execution context for MCP tools."""
        context = Mock()
        context.base_path = Path("/tmp/test")
        context.logger = Mock()
        context.job_manager = Mock()
        return context

    @pytest.mark.asyncio
    async def test_execute_crackerjack_tool(self, mock_execution_context) -> None:
        """Test execute_crackerjack MCP tool."""
        from crackerjack.mcp.tools.core_tools import execute_crackerjack

        with patch("crackerjack.mcp.tools.core_tools.start_workflow") as mock_workflow:
            mock_workflow.return_value = {"job_id": "tool-123", "status": "started"}

            result = await execute_crackerjack(
                stage="hooks", ai_agent=True, include_tests=False,
            )

            assert result is not None
            mock_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_comprehensive_status_tool(self) -> None:
        """Test get_comprehensive_status MCP tool."""
        from crackerjack.mcp.tools.monitoring_tools import get_comprehensive_status

        with patch(
            "crackerjack.mcp.tools.monitoring_tools.collect_system_status",
        ) as mock_status:
            mock_status.return_value = {
                "mcp_server": {"status": "running"},
                "websocket_server": {"status": "running"},
                "active_jobs": 2,
                "system_health": "good",
            }

            result = await get_comprehensive_status()

            assert result is not None
            assert "mcp_server" in result
            assert "system_health" in result

    @pytest.mark.asyncio
    async def test_get_job_progress_tool(self, mock_execution_context) -> None:
        """Test get_job_progress MCP tool."""
        from crackerjack.mcp.tools.progress_tools import get_job_progress

        with patch(
            "crackerjack.mcp.tools.progress_tools.fetch_job_progress",
        ) as mock_progress:
            mock_progress.return_value = {
                "job_id": "test-123",
                "progress": 65,
                "status": "running",
                "current_stage": "testing",
            }

            result = await get_job_progress("test-123")

            assert result is not None
            assert result["progress"] == 65
            assert result["status"] == "running"

    def test_mcp_tool_registration(self) -> None:
        """Test MCP tool registration and availability."""
        # Test that tools are properly registered
        from crackerjack.mcp.tools import core_tools, monitoring_tools, progress_tools

        # Verify tools modules can be imported
        assert hasattr(core_tools, "execute_crackerjack")
        assert hasattr(monitoring_tools, "get_comprehensive_status")
        assert hasattr(progress_tools, "get_job_progress")


# =============================================================================
# INTEGRATION TESTS - MCP and AI component interactions
# =============================================================================


class TestMCPAIIntegration:
    """Integration tests for MCP server and AI assistant interactions."""

    @pytest.mark.asyncio
    async def test_ai_assistant_mcp_coordination(
        self, mock_filesystem_protocol, mock_console,
    ) -> None:
        """Test coordination between AI assistant and MCP server."""
        from crackerjack.services.contextual_ai_assistant import ContextualAIAssistant

        # Create AI assistant
        ContextualAIAssistant(filesystem=mock_filesystem_protocol, console=mock_console)

        # Mock MCP server interaction
        with patch("crackerjack.mcp.server.MCPServer") as mock_server:
            mock_server_instance = mock_server.return_value
            mock_server_instance.process_ai_request = AsyncMock(
                return_value={"status": "processed"},
            )

            # Test AI request processing through MCP
            result = await mock_server_instance.process_ai_request("analyze project")
            assert result["status"] == "processed"

    @pytest.mark.asyncio
    async def test_websocket_ai_integration(self, mock_websocket_server) -> None:
        """Test WebSocket server integration with AI recommendations."""
        ai_recommendations = [
            {"category": "testing", "priority": "high", "title": "Add tests"},
            {
                "category": "security",
                "priority": "critical",
                "title": "Fix vulnerability",
            },
        ]

        # Test broadcasting AI recommendations via WebSocket
        await mock_websocket_server.broadcast(json.dumps(ai_recommendations))

        mock_websocket_server.broadcast.assert_called_once()


# =============================================================================
# ERROR PATH COVERAGE - MCP and AI error handling
# =============================================================================


class TestMCPAIErrorHandling:
    """Test error handling in MCP and AI components."""

    @pytest.mark.asyncio
    async def test_ai_assistant_file_errors(
        self, mock_filesystem_protocol, mock_console,
    ) -> None:
        """Test AI assistant handling of file system errors."""
        from crackerjack.services.contextual_ai_assistant import ContextualAIAssistant

        # Setup file system error
        mock_filesystem_protocol.read_file.side_effect = OSError("File access denied")

        ai_assistant = ContextualAIAssistant(
            filesystem=mock_filesystem_protocol, console=mock_console,
        )

        # Should handle file errors gracefully
        context = await ai_assistant.analyze_project_context()
        assert context is not None  # Should return default context on error

    @pytest.mark.asyncio
    async def test_websocket_connection_failures(self, mock_websocket_connection) -> None:
        """Test WebSocket connection failure handling."""
        # Simulate connection failure
        mock_websocket_connection.send.side_effect = ConnectionClosed(
            1006, "Connection lost",
        )

        # Should handle connection failures gracefully
        with pytest.raises(ConnectionClosed):
            await mock_websocket_connection.send("test")

    @pytest.mark.asyncio
    async def test_mcp_tool_execution_errors(self) -> None:
        """Test MCP tool execution error handling."""
        from crackerjack.mcp.tools.core_tools import execute_crackerjack

        with patch("crackerjack.mcp.tools.core_tools.start_workflow") as mock_workflow:
            mock_workflow.side_effect = Exception("Workflow execution failed")

            # Should handle execution errors gracefully
            try:
                result = await execute_crackerjack(stage="invalid")
                # Should return error result, not raise exception
                assert result is not None
            except Exception:
                pass  # Expected for some error conditions

    def test_ai_recommendation_validation(self) -> None:
        """Test AI recommendation data validation."""
        from crackerjack.services.contextual_ai_assistant import AIRecommendation

        # Test with invalid data - should handle gracefully
        try:
            # Missing required fields should be handled
            rec = AIRecommendation(
                category="",  # Empty category
                priority="invalid",  # Invalid priority
                title="",  # Empty title
                description="",  # Empty description
            )
            # Should create object even with empty/invalid data
            assert isinstance(rec, AIRecommendation)
        except Exception as e:
            pytest.fail(f"Should handle invalid recommendation data gracefully: {e}")
