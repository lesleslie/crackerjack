"""Tests for workflow_executor.py MCP tools.

Tests execute_crackerjack_workflow and related async workflow execution functions.
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from crackerjack.mcp.tools.workflow_executor import (
    execute_crackerjack_workflow,
    _execute_crackerjack_background,
    _execute_crackerjack_sync,
    _initialize_execution,
    _setup_orchestrator,
    _create_standard_orchestrator,
    _create_workflow_options,
    _detect_orchestrator_method,
    _invoke_orchestrator_method,
    _validate_awaitable_result,
    _create_success_result,
    _create_failure_result,
    _handle_iteration_retry,
)


class TestExecuteCrackerjackWorkflow:
    """Tests for execute_crackerjack_workflow function."""

    @pytest.mark.asyncio
    async def test_returns_job_id_and_running_status(self) -> None:
        """Test workflow execution returns job_id and running status."""
        with patch("crackerjack.mcp.tools.workflow_executor.get_context") as mock_ctx, \
             patch("crackerjack.mcp.tools.workflow_executor._update_progress"), \
             patch("asyncio.create_task") as mock_task:

            mock_context = MagicMock()
            mock_ctx.return_value = mock_context
            mock_task.return_value = MagicMock()

            result = await execute_crackerjack_workflow(
                args="test",
                kwargs={"working_directory": "."},
            )

            assert "job_id" in result
            assert result["status"] == "running"
            assert "timestamp" in result
            assert "message" in result

    @pytest.mark.asyncio
    async def test_job_id_is_short_uuid(self) -> None:
        """Test job_id is a short UUID format."""
        with patch("crackerjack.mcp.tools.workflow_executor.get_context") as mock_ctx, \
             patch("crackerjack.mcp.tools.workflow_executor._update_progress"), \
             patch("asyncio.create_task") as mock_task:

            mock_context = MagicMock()
            mock_ctx.return_value = mock_context
            mock_task.return_value = MagicMock()

            result = await execute_crackerjack_workflow(
                args="test",
                kwargs={},
            )

            assert len(result["job_id"]) == 8

    @pytest.mark.asyncio
    async def test_creates_background_task(self) -> None:
        """Test background task is created for async execution."""
        with patch("crackerjack.mcp.tools.workflow_executor.get_context") as mock_ctx, \
             patch("crackerjack.mcp.tools.workflow_executor._update_progress") as mock_update, \
             patch("asyncio.create_task") as mock_task:

            mock_context = MagicMock()
            mock_ctx.return_value = mock_context
            mock_task.return_value = MagicMock()

            await execute_crackerjack_workflow(args="test", kwargs={})

            mock_task.assert_called_once()


class TestInitializeExecution:
    """Tests for _initialize_execution function."""

    @pytest.mark.asyncio
    async def test_returns_failed_for_nonexistent_directory(self) -> None:
        """Test initialization fails for non-existent working directory."""
        context = MagicMock()

        result = await _initialize_execution(
            job_id="test123",
            args="test",
            kwargs={"working_directory": "/nonexistent/path/xyz"},
            context=context,
        )

        assert result["status"] == "failed"
        assert "error" in result
        assert "does not exist" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_success_for_valid_directory(self, tmp_path) -> None:
        """Test initialization succeeds for valid directory."""
        context = MagicMock()

        result = await _initialize_execution(
            job_id="test123",
            args="test",
            kwargs={"working_directory": str(tmp_path)},
            context=context,
        )

        assert result["status"] == "initialized"
        assert "working_dir" in result
        assert result["job_id"] == "test123"


class TestCreateWorkflowOptions:
    """Tests for _create_workflow_options function."""

    def test_default_options(self) -> None:
        """Test default workflow options from empty kwargs."""
        options = _create_workflow_options({})

        assert options.commit is False
        assert options.interactive is False
        assert options.no_config_updates is False
        assert options.verbose is True
        assert options.strip_code is False
        assert options.run_tests is True
        assert options.benchmark is False
        assert options.skip_hooks is False
        assert options.ai_agent is True
        assert options.async_mode is True

    def test_commit_option(self) -> None:
        """Test commit option is correctly set."""
        options = _create_workflow_options({"commit": True})
        assert options.commit is True

    def test_interactive_option(self) -> None:
        """Test interactive option is correctly set."""
        options = _create_workflow_options({"interactive": True})
        assert options.interactive is True

    def test_verbose_option(self) -> None:
        """Test verbose option defaults to True."""
        options = _create_workflow_options({})
        assert options.verbose is True

    def test_clean_option_sets_strip_code(self) -> None:
        """Test clean option sets strip_code."""
        options = _create_workflow_options({"clean": True})
        assert options.strip_code is True

    def test_test_mode_option(self) -> None:
        """Test test_mode option sets run_tests."""
        options = _create_workflow_options({"test_mode": False})
        assert options.run_tests is False

    def test_publish_option(self) -> None:
        """Test publish option is correctly passed."""
        options = _create_workflow_options({"publish": "major"})
        assert options.publish == "major"

    def test_bump_option(self) -> None:
        """Test bump option is correctly passed."""
        options = _create_workflow_options({"bump": "minor"})
        assert options.bump == "minor"

    def test_create_pr_option(self) -> None:
        """Test create_pr option defaults to False."""
        options = _create_workflow_options({})
        assert options.create_pr is False

    def test_skip_hooks_option(self) -> None:
        """Test skip_hooks option is correctly passed."""
        options = _create_workflow_options({"skip_hooks": True})
        assert options.skip_hooks is True

    def test_start_mcp_server_option(self) -> None:
        """Test start_mcp_server option is correctly passed."""
        options = _create_workflow_options({"start_mcp_server": True})
        assert options.start_mcp_server is True

    def test_fast_option(self) -> None:
        """Test fast option is correctly passed."""
        options = _create_workflow_options({"fast": True})
        assert options.fast is True

    def test_test_workers_option(self) -> None:
        """Test test_workers option is correctly passed."""
        options = _create_workflow_options({"test_workers": 8})
        assert options.test_workers == 8

    def test_test_timeout_option(self) -> None:
        """Test test_timeout option is correctly passed."""
        options = _create_workflow_options({"test_timeout": 300})
        assert options.test_timeout == 300


class TestDetectOrchestratorMethod:
    """Tests for _detect_orchestrator_method function."""

    def test_prefers_run_complete_workflow_async(self) -> None:
        """Test method prefers run_complete_workflow_async."""
        orchestrator = MagicMock()
        orchestrator.run_complete_workflow_async = MagicMock()
        del orchestrator.run_complete_workflow
        del orchestrator.execute_workflow
        del orchestrator.run

        result = _detect_orchestrator_method(orchestrator)
        assert result == "run_complete_workflow_async"

    def test_falls_back_to_run_complete_workflow(self) -> None:
        """Test method falls back to run_complete_workflow."""
        orchestrator = MagicMock()
        orchestrator.run_complete_workflow = MagicMock()
        del orchestrator.run_complete_workflow_async
        del orchestrator.execute_workflow
        del orchestrator.run

        result = _detect_orchestrator_method(orchestrator)
        assert result == "run_complete_workflow"

    def test_falls_back_to_execute_workflow(self) -> None:
        """Test method falls back to execute_workflow."""
        orchestrator = MagicMock()
        orchestrator.execute_workflow = MagicMock()
        del orchestrator.run_complete_workflow_async
        del orchestrator.run_complete_workflow
        del orchestrator.run

        result = _detect_orchestrator_method(orchestrator)
        assert result == "execute_workflow"

    def test_falls_back_to_run(self) -> None:
        """Test method falls back to run."""
        orchestrator = MagicMock()
        orchestrator.run = MagicMock()
        del orchestrator.run_complete_workflow_async
        del orchestrator.run_complete_workflow
        del orchestrator.execute_workflow

        result = _detect_orchestrator_method(orchestrator)
        assert result == "run"

    def test_raises_error_for_no_valid_method(self) -> None:
        """Test raises ValueError when no valid method is found."""
        orchestrator = MagicMock()
        del orchestrator.run_complete_workflow_async
        del orchestrator.run_complete_workflow
        del orchestrator.execute_workflow
        del orchestrator.run

        with pytest.raises(ValueError) as exc_info:
            _detect_orchestrator_method(orchestrator)

        assert "no recognized workflow execution method" in str(exc_info.value).lower()


class TestInvokeOrchestratorMethod:
    """Tests for _invoke_orchestrator_method function."""

    def test_invokes_method_with_options(self) -> None:
        """Test method invokes orchestrator method with options."""
        orchestrator = MagicMock()
        mock_method = MagicMock(return_value="result")
        orchestrator.run = mock_method
        options = MagicMock()

        result = _invoke_orchestrator_method(orchestrator, "run", options)

        mock_method.assert_called_once_with(options)
        assert result == "result"

    def test_raises_error_for_none_result(self) -> None:
        """Test raises ValueError when method returns None."""
        orchestrator = MagicMock()
        orchestrator.run = MagicMock(return_value=None)
        options = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            _invoke_orchestrator_method(orchestrator, "run", options)

        assert "returned None" in str(exc_info.value)


class TestValidateAwaitableResult:
    """Tests for _validate_awaitable_result function."""

    def test_accepts_awaitable_result(self) -> None:
        """Test accepts awaitable objects."""
        result = MagicMock()
        result.__await__ = MagicMock(return_value=MagicMock())

        _validate_awaitable_result(result, "run", orchestrator=MagicMock())

    def test_rejects_non_awaitable_result(self) -> None:
        """Test raises ValueError for non-awaitable result."""
        result = "not awaitable"
        orchestrator = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            _validate_awaitable_result(result, "run", orchestrator)

        assert "non-awaitable" in str(exc_info.value).lower()


class TestCreateSuccessResult:
    """Tests for _create_success_result function."""

    def test_creates_success_result(self) -> None:
        """Test creates successful result dictionary."""
        context = MagicMock()

        result = _create_success_result("job123", 3, context)

        assert result["job_id"] == "job123"
        assert result["status"] == "completed"
        assert result["iterations"] == 3
        assert result["success"] is True
        assert "timestamp" in result

    def test_includes_coverage_improvement(self) -> None:
        """Test includes coverage improvement when provided."""
        context = MagicMock()
        coverage = {"tests_added": 5, "coverage_delta": 2.5}

        result = _create_success_result("job123", 3, context, coverage)

        assert "coverage_improvement" in result
        assert result["coverage_improvement"]["tests_added"] == 5


class TestCreateFailureResult:
    """Tests for _create_failure_result function."""

    def test_creates_failure_result(self) -> None:
        """Test creates failure result dictionary."""
        context = MagicMock()

        result = _create_failure_result("job123", 5, context)

        assert result["job_id"] == "job123"
        assert result["status"] == "failed"
        assert "Maximum iterations" in result["error"]
        assert result["success"] is False
        assert "timestamp" in result

    def test_includes_max_iterations_in_error(self) -> None:
        """Test error message includes max iterations."""
        context = MagicMock()

        result = _create_failure_result("job123", 10, context)

        assert "10" in result["error"]


class TestHandleIterationRetry:
    """Tests for _handle_iteration_retry function."""

    @pytest.mark.asyncio
    async def test_sleeps_before_retry(self) -> None:
        """Test retry handler sleeps before retrying."""
        context = MagicMock()

        with patch("crackerjack.mcp.tools.workflow_executor._update_progress") as mock_update:
            await _handle_iteration_retry("job123", 2, context)

            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == "job123"
            progress_data = call_args[0][1]
            assert progress_data["type"] == "iteration"
            assert progress_data["status"] == "retrying"


class TestExecuteCrackerjackBackground:
    """Tests for _execute_crackerjack_background function."""

    @pytest.mark.asyncio
    async def test_updates_progress_on_success(self) -> None:
        """Test updates progress with final result on success."""
        with patch("crackerjack.mcp.tools.workflow_executor._execute_crackerjack_sync") as mock_sync, \
             patch("crackerjack.mcp.tools.workflow_executor._update_progress") as mock_update:

            mock_sync.return_value = {
                "status": "completed",
                "result": "success",
            }

            context = MagicMock()
            await _execute_crackerjack_background("job123", "test", {}, context)

            mock_update.assert_called()
            call_args = mock_update.call_args
            progress_data = call_args[0][1]
            assert progress_data.get("final") is True

    @pytest.mark.asyncio
    async def test_updates_progress_on_failure(self) -> None:
        """Test updates progress with error on failure."""
        with patch("crackerjack.mcp.tools.workflow_executor._execute_crackerjack_sync") as mock_sync, \
             patch("crackerjack.mcp.tools.workflow_executor._update_progress") as mock_update, \
             patch("traceback.format_exc") as mock_traceback:

            mock_sync.side_effect = RuntimeError("Test error")
            mock_traceback.return_value = "traceback string"

            context = MagicMock()
            await _execute_crackerjack_background("job123", "test", {}, context)

            mock_update.assert_called()
            call_args = mock_update.call_args
            progress_data = call_args[0][1]
            assert progress_data.get("status") == "failed"
            assert "Test error" in progress_data.get("error", "")
