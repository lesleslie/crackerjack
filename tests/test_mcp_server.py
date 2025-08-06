"""Tests for MCP server functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from crackerjack.mcp.server import AutoFixResult, CrackerjackMCPServer, MCPOptions


@pytest.fixture
def temp_project(tmp_path):
    return tmp_path


@pytest.fixture
def mock_mcp_available():
    with patch("crackerjack.mcp.server.MCP_AVAILABLE", True):
        with patch("crackerjack.mcp.server.CommandMCPServer") as mock_server:
            yield mock_server


class TestMCPOptions:
    def test_default_options(self):
        options = MCPOptions()
        assert options.ai_agent is True
        assert options.autofix is False
        assert options.test is False
        assert options.clean is False
        assert options.verbose is False

    def test_custom_options(self):
        options = MCPOptions(test=True, verbose=True, clean=True)
        assert options.test is True
        assert options.verbose is True
        assert options.clean is True
        assert options.ai_agent is True

    def test_invalid_option_ignored(self):
        options = MCPOptions(invalid_option=True)
        assert not hasattr(options, "invalid_option")


class TestAutoFixResult:
    def test_autofix_result_creation(self):
        result = AutoFixResult(
            success=True,
            stage="formatting",
            fixes_applied=["ruff format"],
            errors_remaining=[],
            time_taken=1.5,
            retry_needed=False,
        )
        assert result.success is True
        assert result.stage == "formatting"
        assert result.fixes_applied == ["ruff format"]
        assert result.errors_remaining == []
        assert result.time_taken == 1.5
        assert result.retry_needed is False


class TestCrackerjackMCPServer:
    def test_initialization_without_mcp(self, temp_project):
        with patch("crackerjack.mcp.server.MCP_AVAILABLE", False):
            with pytest.raises(ImportError, match="MCP dependencies not available"):
                CrackerjackMCPServer(temp_project)

    def test_initialization_with_mcp(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        assert server.project_path == temp_project
        assert server.console is not None
        assert server.orchestrator is not None
        assert server.state_manager is not None
        assert server.error_cache is not None

    @pytest.mark.asyncio
    async def test_run_stage_cleaning(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.orchestrator.run_cleaning_phase = MagicMock(return_value=True)
        result = await server._run_stage("cleaning")
        assert result["success"] is True
        assert result["stage"] == "cleaning"
        assert "duration" in result
        assert "message" in result

    @pytest.mark.asyncio
    async def test_run_stage_tests(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.orchestrator.run_testing_phase = MagicMock(return_value=True)
        result = await server._run_stage("tests")
        assert result["success"] is True
        assert result["stage"] == "tests"
        server.orchestrator.run_testing_phase.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_stage_hooks(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.orchestrator.run_hooks_phase = MagicMock(return_value=True)
        result = await server._run_stage("fast")
        assert result["success"] is True
        assert result["stage"] == "fast"
        result = await server._run_stage("comprehensive")
        assert result["success"] is True
        assert result["stage"] == "comprehensive"

    @pytest.mark.asyncio
    async def test_run_stage_error_handling(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.orchestrator.run_cleaning_phase = MagicMock(
            side_effect=Exception("Test error")
        )
        result = await server._run_stage("cleaning")
        assert result["success"] is False
        assert "error" in result
        assert result["error"] == "Test error"

    @pytest.mark.asyncio
    async def test_apply_autofix_formatting(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await server._apply_autofix("formatting")
            assert result["success"] is True
            assert "ruff formatting" in result["fixes_applied"]

    @pytest.mark.asyncio
    async def test_apply_autofix_imports(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await server._apply_autofix("imports")
            assert result["success"] is True
            assert "import fixes" in result["fixes_applied"]

    @pytest.mark.asyncio
    async def test_apply_autofix_all(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await server._apply_autofix("all")
            assert result["success"] is True
            assert len(result["fixes_applied"]) >= 2

    @pytest.mark.asyncio
    async def test_apply_autofix_error(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        with patch("subprocess.run", side_effect=Exception("Command failed")):
            result = await server._apply_autofix("formatting")
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_analyze_errors(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        mock_output = "file.py:1:1: E501 line too long\nfile.py:2:1: F401 unused import"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stderr = mock_output
            mock_run.return_value.stdout = ""
            result = await server._analyze_errors()
            assert "total_errors" in result
            assert "categories" in result
            assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_get_stage_status(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.state_manager.get_session_summary = MagicMock(
            return_value={
                "session_id": "test123",
                "total_issues": 5,
                "stages": {"fast": "completed"},
            }
        )
        result = await server._get_stage_status()
        assert "session_id" in result
        assert result["session_id"] == "test123"

    @pytest.mark.asyncio
    async def test_execute_slash_command_crackerjack(
        self, temp_project, mock_mcp_available
    ):
        server = CrackerjackMCPServer(temp_project)
        server.orchestrator.run_complete_workflow = MagicMock(return_value=True)
        result = await server._execute_slash_command("/crackerjack")
        assert result["success"] is True
        assert "completed" in result["message"]
        server.orchestrator.run_complete_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_slash_command_init(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        result = await server._execute_slash_command("/init")
        assert result["success"] is True
        assert "initialized" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_slash_command_init_with_force(
        self, temp_project, mock_mcp_available
    ):
        server = CrackerjackMCPServer(temp_project)
        result = await server._execute_slash_command("/init", ["--force"])
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_slash_command_unknown(
        self, temp_project, mock_mcp_available
    ):
        server = CrackerjackMCPServer(temp_project)
        result = await server._execute_slash_command("/unknown")
        assert result["success"] is False
        assert "Unknown command" in result["error"]

    @pytest.mark.asyncio
    async def test_smart_error_analysis_with_cache(
        self, temp_project, mock_mcp_available
    ):
        server = CrackerjackMCPServer(temp_project)
        server.error_cache.get_common_patterns = MagicMock(
            return_value=[
                MagicMock(pattern_id="test1", error_type="ruff"),
                MagicMock(pattern_id="test2", error_type="pyright"),
            ]
        )
        result = await server._smart_error_analysis(use_cache=True)
        assert "cached_patterns" in result
        assert result["cached_patterns"] == 2

    @pytest.mark.asyncio
    async def test_smart_error_analysis_fresh(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        with patch.object(server, "_analyze_errors", return_value={"total_errors": 3}):
            result = await server._smart_error_analysis(use_cache=False)
            assert "total_errors" in result

    @pytest.mark.asyncio
    async def test_get_next_action(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.state_manager.get_session_summary = MagicMock(
            return_value={"fast_hooks": "pending", "comprehensive_hooks": "pending"}
        )
        result = await server._get_next_action()
        assert "action" in result
        assert result["action"] == "run_crackerjack_stage"
        assert result["parameters"]["stage"] == "fast"

    @pytest.mark.asyncio
    async def test_get_next_action_comprehensive(
        self, temp_project, mock_mcp_available
    ):
        server = CrackerjackMCPServer(temp_project)
        server.state_manager.get_session_summary = MagicMock(
            return_value={"fast_hooks": "completed", "comprehensive_hooks": "pending"}
        )
        result = await server._get_next_action()
        assert result["action"] == "run_crackerjack_stage"
        assert result["parameters"]["stage"] == "comprehensive"

    @pytest.mark.asyncio
    async def test_get_next_action_complete(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.state_manager.get_session_summary = MagicMock(
            return_value={"fast_hooks": "completed", "comprehensive_hooks": "completed"}
        )
        result = await server._get_next_action()
        assert result["action"] == "complete"

    @pytest.mark.asyncio
    async def test_session_management_save(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.state_manager.save_checkpoint = MagicMock()
        result = await server._session_management("save", "test_checkpoint")
        assert result["success"] is True
        assert "saved" in result["message"]
        server.state_manager.save_checkpoint.assert_called_once_with("test_checkpoint")

    @pytest.mark.asyncio
    async def test_session_management_load(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.state_manager.load_checkpoint = MagicMock(return_value=True)
        result = await server._session_management("load", "test_checkpoint")
        assert result["success"] is True
        assert "loaded" in result["message"]

    @pytest.mark.asyncio
    async def test_session_management_status(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.state_manager.get_session_summary = MagicMock(
            return_value={"session_id": "test123"}
        )
        result = await server._session_management("status")
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_session_management_reset(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.state_manager.reset_session = MagicMock()
        result = await server._session_management("reset")
        assert result["success"] is True
        assert "reset" in result["message"]

    @pytest.mark.asyncio
    async def test_session_management_invalid_action(
        self, temp_project, mock_mcp_available
    ):
        server = CrackerjackMCPServer(temp_project)
        result = await server._session_management("invalid")
        assert result["success"] is False
        assert "Unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_run_server(self, temp_project, mock_mcp_available):
        server = CrackerjackMCPServer(temp_project)
        server.server.run = AsyncMock()
        await server.run(host="localhost", port=8000)
        server.server.run.assert_called_once_with(host="localhost", port=8000)
