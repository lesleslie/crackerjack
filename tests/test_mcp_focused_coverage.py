"""Focused MCP test coverage for maximum impact.

This test file targets the highest-impact MCP modules with streamlined tests
that cover critical paths quickly and effectively boost coverage toward 42%.

Key targets:
- server_core.py: MCP server entry points and configuration
- context.py: Server context lifecycle and management
- cache.py: Error pattern caching and analysis
- state.py: Session state management and tracking
- tools/core_tools.py: Core MCP tool functionality
- tools/monitoring_tools.py: Status monitoring and health checks

Optimized for speed and coverage impact.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from crackerjack.mcp.cache import ErrorCache, ErrorPattern, FixResult
from crackerjack.mcp.context import BatchedStateSaver, MCPServerConfig, MCPServerContext

# Import key MCP components
from crackerjack.mcp.server_core import MCPOptions, _validate_job_id
from crackerjack.mcp.state import Issue, Priority, StageStatus, StateManager
from crackerjack.mcp.tools.core_tools import (
    _configure_stage_options,
    _detect_errors_and_suggestions,
    _get_error_patterns,
    _parse_stage_args,
)
from crackerjack.mcp.tools.monitoring_tools import (
    _build_server_stats,
    _create_error_response,
    _determine_next_action,
    _get_stage_status_dict,
)


class TestMCPServerCore:
    """Fast tests for MCP server core functionality."""

    def test_mcp_options_initialization(self) -> None:
        """Test MCPOptions with various configurations."""
        # Default options
        options = MCPOptions()
        assert options.autofix is True
        assert options.ai_agent is False
        assert options.test is False

        # Custom options
        options = MCPOptions(test=True, ai_agent=True, verbose=True)
        assert options.test is True
        assert options.ai_agent is True
        assert options.verbose is True

        # Invalid attributes ignored
        options = MCPOptions(invalid_attr="ignored")
        assert not hasattr(options, "invalid_attr")

    def test_job_id_validation(self) -> None:
        """Test job ID validation patterns."""
        # Valid patterns
        valid_ids = ["abc123", "job-123", "test_job", "a1b2c3"]
        for job_id in valid_ids:
            assert _validate_job_id(job_id), f"Should be valid: {job_id}"

        # Invalid patterns
        invalid_ids = ["", "a" * 51, "../path", "job with spaces", "/absolute"]
        for job_id in invalid_ids:
            assert not _validate_job_id(job_id), f"Should be invalid: {job_id}"


class TestMCPContext:
    """Fast tests for MCP context management."""

    @pytest.fixture
    def temp_path(self) -> Path:
        """Create temporary directory."""
        return Path(tempfile.mkdtemp())

    @pytest.fixture
    def mcp_config(self, temp_path: Path) -> MCPServerConfig:
        """Create MCP configuration."""
        return MCPServerConfig(project_path=temp_path, stdio_mode=True)

    @pytest.fixture
    def mcp_context(self, mcp_config: MCPServerConfig) -> MCPServerContext:
        """Create MCP context."""
        return MCPServerContext(mcp_config)

    def test_context_initialization(self, mcp_context: MCPServerContext) -> None:
        """Test context initialization."""
        assert mcp_context._initialized is False
        assert mcp_context.console is None
        assert isinstance(mcp_context.batched_saver, BatchedStateSaver)

    @pytest.mark.asyncio
    async def test_context_lifecycle(self, mcp_context: MCPServerContext) -> None:
        """Test context lifecycle."""
        await mcp_context.initialize()
        assert mcp_context._initialized is True
        assert mcp_context.console is not None
        assert mcp_context.cli_runner is not None

        await mcp_context.shutdown()
        assert mcp_context._initialized is False

    def test_job_id_validation_methods(self, mcp_context: MCPServerContext) -> None:
        """Test job ID validation methods."""
        assert mcp_context.validate_job_id("valid-123") is True
        assert mcp_context.validate_job_id("../invalid") is False

        # Test progress file path creation
        progress_file = mcp_context.create_progress_file_path("test-job")
        assert progress_file.name == "job-test-job.json"

        with pytest.raises(ValueError):
            mcp_context.create_progress_file_path("../invalid")

    def test_context_stats(self, mcp_context: MCPServerContext) -> None:
        """Test context statistics."""
        stats = mcp_context.get_context_stats()

        required_keys = [
            "initialized",
            "stdio_mode",
            "project_path",
            "progress_dir",
            "components",
            "websocket_server",
            "progress_queue",
            "batched_saving",
        ]

        for key in required_keys:
            assert key in stats

        assert stats["initialized"] is False
        assert stats["stdio_mode"] is True


class TestMCPCache:
    """Fast tests for MCP error caching."""

    @pytest.fixture
    def cache_dir(self) -> Path:
        """Create temporary cache directory."""
        return Path(tempfile.mkdtemp())

    @pytest.fixture
    def error_cache(self, cache_dir: Path) -> ErrorCache:
        """Create error cache."""
        return ErrorCache(cache_dir=cache_dir)

    def test_cache_initialization(self, error_cache: ErrorCache) -> None:
        """Test cache initialization."""
        assert error_cache.cache_dir.exists()
        assert isinstance(error_cache.patterns, dict)
        assert isinstance(error_cache.fix_results, list)

    @pytest.mark.asyncio
    async def test_pattern_management(self, error_cache: ErrorCache) -> None:
        """Test error pattern management."""
        pattern = ErrorPattern(
            pattern_id="test_1",
            error_type="ruff",
            error_code="E501",
            message_pattern="line too long",
            auto_fixable=True,
        )

        # Add pattern
        await error_cache.add_pattern(pattern)
        retrieved = error_cache.get_pattern("test_1")
        assert retrieved is not None
        assert retrieved.error_type == "ruff"

        # Test pattern queries
        ruff_patterns = error_cache.find_patterns_by_type("ruff")
        assert len(ruff_patterns) == 1

        e501_patterns = error_cache.find_patterns_by_code("E501")
        assert len(e501_patterns) == 1

        auto_fixable = error_cache.get_auto_fixable_patterns()
        assert len(auto_fixable) == 1

    @pytest.mark.asyncio
    async def test_fix_results(self, error_cache: ErrorCache) -> None:
        """Test fix result tracking."""
        pattern = ErrorPattern("test_1", "ruff", "E501", "error", auto_fixable=False)
        await error_cache.add_pattern(pattern)

        fix_result = FixResult(
            fix_id="fix_1",
            pattern_id="test_1",
            success=True,
            files_affected=["test.py"],
            time_taken=1.0,
        )

        await error_cache.add_fix_result(fix_result)

        # Pattern should now be auto_fixable
        updated_pattern = error_cache.get_pattern("test_1")
        assert updated_pattern.auto_fixable is True

        # Check success rate
        success_rate = error_cache.get_fix_success_rate("test_1")
        assert success_rate == 1.0

    def test_cache_stats(self, error_cache: ErrorCache) -> None:
        """Test cache statistics."""
        stats = error_cache.get_cache_stats()

        required_keys = [
            "total_patterns",
            "auto_fixable_patterns",
            "auto_fixable_rate",
            "total_fix_attempts",
            "successful_fixes",
            "fix_success_rate",
            "average_pattern_frequency",
            "error_types",
        ]

        for key in required_keys:
            assert key in stats


class TestMCPState:
    """Fast tests for MCP state management."""

    @pytest.fixture
    def state_dir(self) -> Path:
        """Create temporary state directory."""
        return Path(tempfile.mkdtemp())

    @pytest.fixture
    def state_manager(self, state_dir: Path) -> StateManager:
        """Create state manager."""
        return StateManager(state_dir=state_dir)

    def test_state_initialization(self, state_manager: StateManager) -> None:
        """Test state manager initialization."""
        assert len(state_manager.session_state.session_id) == 8
        assert state_manager.session_state.start_time > 0
        assert state_manager.session_state.stages == {}
        assert state_manager.session_state.global_issues == []

    @pytest.mark.asyncio
    async def test_stage_lifecycle(self, state_manager: StateManager) -> None:
        """Test stage lifecycle management."""
        stage_name = "test_stage"

        # Start stage
        await state_manager.start_stage(stage_name)
        assert state_manager.session_state.current_stage == stage_name
        assert stage_name in state_manager.session_state.stages

        stage_result = state_manager.session_state.stages[stage_name]
        assert stage_result.status == StageStatus.RUNNING

        # Complete stage
        await state_manager.complete_stage(stage_name)
        stage_result = state_manager.session_state.stages[stage_name]
        assert stage_result.status == StageStatus.COMPLETED
        assert state_manager.session_state.current_stage is None

    @pytest.mark.asyncio
    async def test_issue_management(self, state_manager: StateManager) -> None:
        """Test issue management."""
        issue = Issue(
            id="issue_1",
            type="test_error",
            message="Test issue",
            file_path="test.py",
            priority=Priority.HIGH,
            auto_fixable=True,
        )

        # Add issue
        await state_manager.add_issue(issue)
        assert len(state_manager.session_state.global_issues) == 1

        # Query by priority
        high_priority = state_manager.get_issues_by_priority(Priority.HIGH)
        assert len(high_priority) == 1

        # Query by type
        test_errors = state_manager.get_issues_by_type("test_error")
        assert len(test_errors) == 1

        # Query auto-fixable
        auto_fixable = state_manager.get_auto_fixable_issues()
        assert len(auto_fixable) == 1

        # Remove issue
        removed = state_manager.remove_issue("issue_1")
        assert removed is True
        assert len(state_manager.session_state.global_issues) == 0

    def test_session_summary(self, state_manager: StateManager) -> None:
        """Test session summary generation."""
        summary = state_manager.get_session_summary()

        required_keys = [
            "session_id",
            "duration",
            "current_stage",
            "stages",
            "total_issues",
            "issues_by_priority",
            "issues_by_type",
            "total_fixes",
            "auto_fixable_issues",
        ]

        for key in required_keys:
            assert key in summary


class TestMCPCoreTools:
    """Fast tests for MCP core tools."""

    def test_stage_args_parsing(self) -> None:
        """Test stage argument parsing."""
        # Valid args
        result = _parse_stage_args("fast", "{}")
        assert isinstance(result, tuple)
        stage, kwargs = result
        assert stage == "fast"
        assert kwargs == {}

        # Valid args with JSON
        result = _parse_stage_args("tests", '{"dry_run": true}')
        assert isinstance(result, tuple)
        stage, kwargs = result
        assert stage == "tests"
        assert kwargs == {"dry_run": True}

        # Invalid stage
        result = _parse_stage_args("invalid", "{}")
        assert isinstance(result, str)
        assert "error" in result

        # Invalid JSON
        result = _parse_stage_args("fast", "invalid json")
        assert isinstance(result, str)
        assert "Invalid JSON" in result

    def test_stage_options_configuration(self) -> None:
        """Test stage options configuration."""
        from crackerjack.models.config import WorkflowOptions

        # Test each stage type
        for stage in ["fast", "comprehensive", "tests", "cleaning"]:
            options = _configure_stage_options(stage)
            assert isinstance(options, WorkflowOptions)

    def test_error_pattern_detection(self) -> None:
        """Test error pattern detection."""
        patterns = _get_error_patterns()
        assert len(patterns) > 0

        # Test error detection
        error_text = "TypeError: object has no attribute 'test'\nFAILED test.py"

        detected_errors, suggestions = _detect_errors_and_suggestions(error_text, True)
        assert "type_error" in detected_errors
        assert "test_failure" in detected_errors
        assert len(suggestions) > 0

        # Test without suggestions
        detected_errors_no_sugg, suggestions_no_sugg = _detect_errors_and_suggestions(
            error_text,
            False,
        )
        assert detected_errors_no_sugg == detected_errors
        assert suggestions_no_sugg == []


class TestMCPMonitoringTools:
    """Fast tests for MCP monitoring tools."""

    def test_error_response_creation(self) -> None:
        """Test error response creation."""
        response = _create_error_response("Test error")
        response_data = json.loads(response)
        assert response_data["error"] == "Test error"
        assert response_data["success"] is False

        response_custom = _create_error_response("Test error", success=True)
        response_data_custom = json.loads(response_custom)
        assert response_data_custom["success"] is True

    def test_stage_status_queries(self) -> None:
        """Test stage status querying."""
        mock_state_manager = Mock()
        mock_state_manager.get_stage_status = Mock(return_value="completed")

        result = _get_stage_status_dict(mock_state_manager)

        expected_stages = ["fast", "comprehensive", "tests", "cleaning"]
        assert len(result) == len(expected_stages)

        for stage in expected_stages:
            assert stage in result
            assert result[stage] == "completed"

    def test_next_action_determination(self) -> None:
        """Test next action determination."""
        mock_state_manager = Mock()

        # Test when fast stage incomplete
        mock_state_manager.get_stage_status = Mock(
            side_effect=lambda stage: "pending" if stage == "fast" else "completed",
        )

        result = _determine_next_action(mock_state_manager)
        assert result["recommended_action"] == "run_stage"
        assert result["parameters"]["stage"] == "fast"

        # Test when all stages complete
        mock_state_manager.get_stage_status = Mock(return_value="completed")

        result = _determine_next_action(mock_state_manager)
        assert result["recommended_action"] == "complete"

    def test_server_stats_building(self) -> None:
        """Test server statistics building."""
        mock_context = Mock()
        mock_context.config.project_path = Path("/test")
        mock_context.websocket_server_port = 8675
        mock_context.websocket_server_process = None
        mock_context.rate_limiter = None
        mock_context.progress_dir.exists.return_value = False

        result = _build_server_stats(mock_context)

        required_keys = ["server_info", "rate_limiting", "resource_usage", "timestamp"]
        for key in required_keys:
            assert key in result

        assert result["server_info"]["project_path"] == "/test"
        assert result["server_info"]["websocket_port"] == 8675
        assert result["server_info"]["websocket_active"] is False


class TestMCPBatchedSaver:
    """Fast tests for batched state saver."""

    @pytest.fixture
    def batched_saver(self) -> BatchedStateSaver:
        """Create batched saver."""
        return BatchedStateSaver(debounce_delay=0.05, max_batch_size=2)

    @pytest.mark.asyncio
    async def test_batched_saver_lifecycle(
        self,
        batched_saver: BatchedStateSaver,
    ) -> None:
        """Test batched saver lifecycle."""
        assert not batched_saver._running

        await batched_saver.start()
        assert batched_saver._running

        await batched_saver.stop()
        assert not batched_saver._running

    @pytest.mark.asyncio
    async def test_batched_saving(self, batched_saver: BatchedStateSaver) -> None:
        """Test batched saving functionality."""
        await batched_saver.start()

        save_calls = []

        def save_func() -> None:
            save_calls.append("saved")

        # Schedule saves up to batch size
        await batched_saver.schedule_save("save_1", save_func)
        await batched_saver.schedule_save("save_2", save_func)

        # Wait longer and check that saves were executed
        # Use timeout to prevent hanging
        try:
            for _ in range(20):  # Wait up to 2 seconds
                await asyncio.sleep(0.1)
                if len(save_calls) >= 2:
                    break

            # Should have executed both saves
            assert len(save_calls) >= 2
        finally:
            await batched_saver.stop()

    def test_batched_saver_stats(self, batched_saver: BatchedStateSaver) -> None:
        """Test batched saver statistics."""
        stats = batched_saver.get_stats()

        assert "running" in stats
        assert "pending_saves" in stats
        assert "debounce_delay" in stats
        assert "max_batch_size" in stats
        assert stats["running"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
