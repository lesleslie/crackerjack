"""Tests for monitoring_tools.py MCP tools.

Tests status, stats, and monitoring tools.
"""

import json
import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock

from crackerjack.mcp.tools.monitoring_tools import (
    _suggest_agent_for_context,
    _create_error_response,
    _get_stage_status_dict,
    _get_session_info,
    _determine_next_action,
    _build_server_stats,
    _add_state_manager_stats,
    _get_active_jobs,
    _validate_status_components,
    _get_services_status,
    _get_resources_status,
    _format_status_error,
    register_monitoring_tools,
)


class TestSuggestAgentForContext:
    """Tests for _suggest_agent_for_context function."""

    def test_suggests_test_specialist_on_test_failure(self) -> None:
        """Test suggests test-specialist when tests are failing."""
        state_manager = MagicMock()
        state_manager.recent_errors = ["Test failure in test_example.py"]
        state_manager.get_stage_status = MagicMock(
            side_effect=lambda s: "failed" if s == "tests" else "completed"
        )

        result = _suggest_agent_for_context(state_manager)

        assert result["recommended_agent"] == "test-specialist"
        assert result["priority"] == "HIGH"

    def test_suggests_security_auditor_on_security_issues(self) -> None:
        """Test suggests security-auditor when security issues detected."""
        state_manager = MagicMock()
        state_manager.recent_errors = ["bandit detected security issue"]
        state_manager.get_stage_status = MagicMock(return_value="completed")

        result = _suggest_agent_for_context(state_manager)

        assert result["recommended_agent"] == "security-auditor"
        assert result["priority"] == "HIGH"

    def test_suggests_architect_on_complexity_issues(self) -> None:
        """Test suggests architect for complexity issues."""
        state_manager = MagicMock()
        state_manager.recent_errors = ["complex function detected"]
        state_manager.get_stage_status = MagicMock(return_value="completed")

        result = _suggest_agent_for_context(state_manager)

        assert result["recommended_agent"] == "crackerjack-architect"
        assert result["priority"] == "HIGH"

    def test_suggests_default_agent_when_no_issues(self) -> None:
        """Test suggests default agent when no issues detected."""
        state_manager = MagicMock()
        state_manager.recent_errors = []
        state_manager.get_stage_status = MagicMock(return_value="completed")

        result = _suggest_agent_for_context(state_manager)

        assert result["recommended_agent"] == "crackerjack-architect"
        assert result["priority"] == "MEDIUM"

    def test_handles_exception_gracefully(self) -> None:
        """Test handles exceptions gracefully."""
        state_manager = MagicMock()
        state_manager.recent_errors = "not a list"

        result = _suggest_agent_for_context(state_manager)

        assert result["recommended_agent"] is None
        assert result["priority"] == "MEDIUM"


class TestCreateErrorResponse:
    """Tests for _create_error_response function."""

    def test_creates_error_response(self) -> None:
        """Test creates error response JSON."""
        result = _create_error_response("Test error")

        parsed = json.loads(result)
        assert parsed["error"] == "Test error"
        assert parsed["success"] is False

    def test_creates_error_with_success_true(self) -> None:
        """Test creates error response with success=True."""
        result = _create_error_response("Warning message", success=True)

        parsed = json.loads(result)
        assert parsed["error"] == "Warning message"
        assert parsed["success"] is True


class TestGetStageStatusDict:
    """Tests for _get_stage_status_dict function."""

    def test_returns_status_for_all_stages(self) -> None:
        """Test returns status dictionary for all stages."""
        state_manager = MagicMock()
        state_manager.get_stage_status = MagicMock(
            side_effect=lambda s: {"fast": "completed", "comprehensive": "running",
                                  "tests": "failed", "cleaning": "pending"}.get(s, "unknown")
        )

        result = _get_stage_status_dict(state_manager)

        assert "fast" in result
        assert "comprehensive" in result
        assert "tests" in result
        assert "cleaning" in result
        assert result["tests"] == "failed"


class TestGetSessionInfo:
    """Tests for _get_session_info function."""

    def test_returns_session_info(self) -> None:
        """Test returns session information."""
        state_manager = MagicMock()
        state_manager.iteration_count = 5
        state_manager.current_iteration = 3
        state_manager.session_active = True

        result = _get_session_info(state_manager)

        assert result["total_iterations"] == 5
        assert result["current_iteration"] == 3
        assert result["session_active"] is True

    def test_handles_missing_attributes(self) -> None:
        """Test handles missing state_manager attributes."""
        state_manager = MagicMock(spec=[])

        result = _get_session_info(state_manager)

        assert result["total_iterations"] == 0
        assert result["current_iteration"] == 0
        assert result["session_active"] is False


class TestDetermineNextAction:
    """Tests for _determine_next_action function."""

    @pytest.mark.asyncio
    async def test_recommends_fast_when_not_completed(self) -> None:
        """Test recommends running fast stage when not completed."""
        state_manager = MagicMock()
        state_manager.get_stage_status = MagicMock(
            side_effect=lambda s: "completed" if s != "fast" else "running"
        )

        result = await _determine_next_action(state_manager)

        assert result["recommended_action"] == "run_stage"
        assert result["parameters"]["stage"] == "fast"

    @pytest.mark.asyncio
    async def test_recommends_tests_when_fast_completed(self) -> None:
        """Test recommends running tests when fast is completed."""
        state_manager = MagicMock()
        state_manager.get_stage_status = MagicMock(
            side_effect=lambda s: "completed" if s == "fast" else "running"
        )

        result = await _determine_next_action(state_manager)

        assert result["recommended_action"] == "run_stage"
        assert result["parameters"]["stage"] == "tests"

    @pytest.mark.asyncio
    async def test_recommends_complete_when_all_done(self) -> None:
        """Test recommends complete when all stages done."""
        state_manager = MagicMock()
        state_manager.get_stage_status = MagicMock(return_value="completed")

        result = await _determine_next_action(state_manager)

        assert result["recommended_action"] == "complete"


class TestBuildServerStats:
    """Tests for _build_server_stats function."""

    @pytest.mark.asyncio
    async def test_returns_server_stats(self) -> None:
        """Test returns server statistics."""
        context = MagicMock()
        context.config.project_path = MagicMock()
        context.rate_limiter = None
        context.progress_dir = MagicMock()
        context.progress_dir.exists.return_value = False

        result = await _build_server_stats(context)

        assert "server_info" in result
        assert "rate_limiting" in result
        assert "resource_usage" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_includes_rate_limiter_config(self) -> None:
        """Test includes rate limiter config when present."""
        context = MagicMock()
        context.config.project_path = MagicMock()
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.config = MagicMock()
        mock_rate_limiter.config.__dict__ = {"max_requests": 100}
        context.rate_limiter = mock_rate_limiter
        context.progress_dir = MagicMock()
        context.progress_dir.exists.return_value = False

        result = await _build_server_stats(context)

        assert result["rate_limiting"]["enabled"] is True
        assert result["rate_limiting"]["config"] is not None


class TestAddStateManagerStats:
    """Tests for _add_state_manager_stats function."""

    def test_adds_stats_when_state_manager_provided(self) -> None:
        """Test adds state manager stats to dictionary."""
        stats = {}
        state_manager = MagicMock()
        state_manager.iteration_count = 10
        state_manager.session_active = True
        state_manager.issues = ["issue1", "issue2"]

        _add_state_manager_stats(stats, state_manager)

        assert "state_manager" in stats
        assert stats["state_manager"]["iteration_count"] == 10
        assert stats["state_manager"]["session_active"] is True
        assert stats["state_manager"]["issues_count"] == 2

    def test_does_nothing_when_state_manager_is_none(self) -> None:
        """Test does nothing when state_manager is None."""
        stats = {"existing": "value"}

        _add_state_manager_stats(stats, None)

        assert "state_manager" not in stats


class TestGetActiveJobs:
    """Tests for _get_active_jobs function."""

    def test_returns_empty_when_progress_dir_not_exists(self) -> None:
        """Test returns empty list when progress dir doesn't exist."""
        context = MagicMock()
        context.progress_dir.exists.return_value = False

        result = _get_active_jobs(context)

        assert result == []

    def test_returns_empty_when_no_job_files(self, tmp_path) -> None:
        """Test returns empty list when no job files exist."""
        context = MagicMock()
        context.progress_dir = tmp_path
        tmp_path.mkdir(exist_ok=True)

        result = _get_active_jobs(context)

        assert result == []

    def test_parses_job_files_correctly(self, tmp_path) -> None:
        """Test parses job files correctly."""
        context = MagicMock()
        context.progress_dir = tmp_path
        tmp_path.mkdir(exist_ok=True)

        job_file = tmp_path / "job-123.json"
        job_file.write_text(json.dumps({
            "job_id": "123",
            "status": "running",
            "iteration": 2,
            "max_iterations": 5,
            "current_stage": "tests",
            "overall_progress": 50,
            "stage_progress": 75,
            "message": "Running tests",
            "timestamp": "2024-01-01T00:00:00",
            "error_counts": {"type_error": 1},
        }))

        result = _get_active_jobs(context)

        assert len(result) == 1
        assert result[0]["job_id"] == "123"
        assert result[0]["status"] == "running"
        assert result[0]["iteration"] == 2

    def test_skips_invalid_json_files(self, tmp_path) -> None:
        """Test skips files with invalid JSON."""
        context = MagicMock()
        context.progress_dir = tmp_path
        tmp_path.mkdir(exist_ok=True)

        invalid_file = tmp_path / "job-invalid.json"
        invalid_file.write_text("not json")

        result = _get_active_jobs(context)

        assert result == []


class TestValidateStatusComponents:
    """Tests for _validate_status_components function."""

    def test_accepts_valid_components(self) -> None:
        """Test accepts valid component names."""
        requested, error = _validate_status_components("services, jobs")

        assert error is None
        assert "services" in requested
        assert "jobs" in requested

    def test_accepts_all(self) -> None:
        """Test accepts 'all' as valid component."""
        requested, error = _validate_status_components("all")

        assert error is None
        assert "all" in requested

    def test_returns_error_for_invalid_components(self) -> None:
        """Test returns error for invalid components."""
        requested, error = _validate_status_components("invalid, components")

        assert error is not None
        assert "Invalid" in error

    def test_normalizes_component_names(self) -> None:
        """Test normalizes component names to lowercase."""
        requested, error = _validate_status_components("SERVICES, Jobs")

        assert error is None
        assert "services" in requested
        assert "jobs" in requested


class TestGetServicesStatus:
    """Tests for _get_services_status function."""

    def test_returns_mcp_server_status(self) -> None:
        """Test returns MCP server status."""
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.find_mcp_server_processes"
        ) as mock_find:
            mock_find.return_value = ["process1", "process2"]

            result = _get_services_status()

            assert "mcp_server" in result
            assert result["mcp_server"]["running"] == ["process1", "process2"]


class TestGetResourcesStatus:
    """Tests for _get_resources_status function."""

    def test_returns_resource_info(self) -> None:
        """Test returns resource information."""
        context = MagicMock()
        mock_progress_dir = MagicMock()
        mock_progress_dir.exists.return_value = True
        mock_progress_dir.glob.return_value = [MagicMock(), MagicMock()]
        context.progress_dir = mock_progress_dir

        result = _get_resources_status(context)

        assert "temp_files_count" in result
        assert "progress_dir" in result


class TestFormatStatusError:
    """Tests for _format_status_error function."""

    def test_returns_formatted_error(self) -> None:
        """Test returns formatted error JSON."""
        with patch(
            "crackerjack.mcp.tools.monitoring_tools.get_secure_status_formatter"
        ) as mock_formatter:
            mock_instance = MagicMock()
            mock_instance.format_error_response.return_value = {
                "error": "Test error",
                "success": False,
            }
            mock_formatter.return_value = mock_instance

            result = _format_status_error("Test error")

            parsed = json.loads(result)
            assert parsed["error"] == "Test error"


class TestRegisterMonitoringTools:
    """Tests for register_monitoring_tools function."""

    def test_registers_six_tools(self) -> None:
        """Test registers six monitoring MCP tools."""
        mcp_app = MagicMock()

        register_monitoring_tools(mcp_app)

        assert mcp_app.tool.call_count == 6

    def test_registers_stage_status_tool(self) -> None:
        """Test registers get_stage_status tool."""
        mcp_app = MagicMock()

        register_monitoring_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_next_action_tool(self) -> None:
        """Test registers get_next_action tool."""
        mcp_app = MagicMock()

        register_monitoring_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_server_stats_tool(self) -> None:
        """Test registers get_server_stats tool."""
        mcp_app = MagicMock()

        register_monitoring_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_comprehensive_status_tool(self) -> None:
        """Test registers get_comprehensive_status tool."""
        mcp_app = MagicMock()

        register_monitoring_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_list_slash_commands_tool(self) -> None:
        """Test registers list_slash_commands tool."""
        mcp_app = MagicMock()

        register_monitoring_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_filtered_status_tool(self) -> None:
        """Test registers get_filtered_status tool."""
        mcp_app = MagicMock()

        register_monitoring_tools(mcp_app)

        assert mcp_app.tool.called
