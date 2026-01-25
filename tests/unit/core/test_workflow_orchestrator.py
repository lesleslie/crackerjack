"""Unit tests for workflow orchestrator components."""

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from crackerjack.config import CrackerjackSettings
from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import (
    WorkflowPipeline,
    WorkflowResult,
    _adapt_options,
    _workflow_result_success,
)


class TestWorkflowResult:
    """Test WorkflowResult dataclass."""

    def test_workflow_result_creation(self) -> None:
        """Test creating a WorkflowResult instance."""
        result = WorkflowResult(success=True, details={"key": "value"})

        assert result.success is True
        assert result.details == {"key": "value"}


class TestWorkflowResultSuccess:
    """Test _workflow_result_success function."""

    def test_workflow_result_success_empty_dict(self) -> None:
        """Test _workflow_result_success with empty dict."""
        result = {}
        assert _workflow_result_success(result) is True

    def test_workflow_result_success_none(self) -> None:
        """Test _workflow_result_success with None."""
        result = None
        assert _workflow_result_success(result) is True

    def test_workflow_result_success_all_true(self) -> None:
        """Test _workflow_result_success with all true values."""
        result = {"results": {"op1": True, "op2": True}}
        assert _workflow_result_success(result) is True

    def test_workflow_result_success_mixed_values(self) -> None:
        """Test _workflow_result_success with mixed values."""
        result = {"results": {"op1": True, "op2": "success", "op3": 1}}
        assert _workflow_result_success(result) is True

    def test_workflow_result_success_with_false(self) -> None:
        """Test _workflow_result_success with false value."""
        result = {"results": {"op1": True, "op2": False}}
        assert _workflow_result_success(result) is False

    def test_workflow_result_success_with_zero(self) -> None:
        """Test _workflow_result_success with zero value."""
        result = {"results": {"op1": True, "op2": 0}}
        assert _workflow_result_success(result) is False

    def test_workflow_result_success_not_dict(self) -> None:
        """Test _workflow_result_success with non-dict input."""
        result = "not_a_dict"
        assert _workflow_result_success(result) is True


class TestAdaptOptions:
    """Test _adapt_options function."""

    def test_adapt_options_passthrough(self) -> None:
        """Test _adapt_options passes through options unchanged."""
        options = {"key": "value"}
        result = _adapt_options(options)
        assert result is options


class TestWorkflowPipelineInitialization:
    """Test WorkflowPipeline initialization."""

    def test_initialization_defaults(self) -> None:
        """Test WorkflowPipeline initialization with defaults."""
        pipeline = WorkflowPipeline()

        assert isinstance(pipeline.console, CrackerjackConsole)
        assert pipeline.pkg_path == Path.cwd()
        assert isinstance(pipeline.settings, CrackerjackSettings)
        assert isinstance(pipeline.session, SessionCoordinator)
        assert isinstance(pipeline.phases, PhaseCoordinator)

    def test_initialization_with_parameters(self) -> None:
        """Test WorkflowPipeline initialization with parameters."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")
        settings = CrackerjackSettings()
        session = MagicMock()
        phases = MagicMock()

        pipeline = WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            settings=settings,
            session=session,
            phases=phases,
        )

        assert pipeline.console is console
        assert pipeline.pkg_path == pkg_path
        assert pipeline.settings is settings
        assert pipeline.session is session
        assert pipeline.phases is phases

    def test_initialization_with_logger(self) -> None:
        """Test WorkflowPipeline initialization with logger."""
        logger = logging.getLogger("test")
        pipeline = WorkflowPipeline(logger=logger)

        assert pipeline.logger is logger


@pytest.mark.asyncio
class TestWorkflowPipelineRunCompleteWorkflow:
    """Test run_complete_workflow method."""

    async def test_run_complete_workflow_success(self) -> None:
        """Test run_complete_workflow with successful execution."""
        pipeline = WorkflowPipeline()
        
        # Mock the methods that are called during workflow execution
        with patch.object(pipeline, '_initialize_workflow_session') as mock_init_session, \
             patch.object(pipeline, '_clear_oneiric_cache') as mock_clear_cache, \
             patch('crackerjack.core.workflow_orchestrator.build_oneiric_runtime') as mock_build_runtime, \
             patch('crackerjack.core.workflow_orchestrator.register_crackerjack_workflow') as mock_register_workflow, \
             patch.object(pipeline.session, 'finalize_session') as mock_finalize:
            
            # Create a mock runtime with execute_dag method
            mock_runtime = MagicMock()
            mock_runtime.workflow_bridge.execute_dag = AsyncMock(return_value={"results": {"step1": True}})
            mock_build_runtime.return_value = mock_runtime
            
            options = {"test": True}
            result = await pipeline.run_complete_workflow(options)
            
            assert result is True
            mock_init_session.assert_called_once_with(options)
            mock_clear_cache.assert_called_once()
            mock_build_runtime.assert_called_once()
            mock_register_workflow.assert_called_once()
            mock_finalize.assert_called_once()

    async def test_run_complete_workflow_failure(self) -> None:
        """Test run_complete_workflow with failed execution."""
        pipeline = WorkflowPipeline()
        
        with patch.object(pipeline, '_initialize_workflow_session'), \
             patch.object(pipeline, '_clear_oneiric_cache'), \
             patch('crackerjack.core.workflow_orchestrator.build_oneiric_runtime') as mock_build_runtime, \
             patch.object(pipeline.session, 'finalize_session') as mock_finalize:
            
            # Create a mock runtime that raises an exception
            mock_runtime = MagicMock()
            mock_runtime.workflow_bridge.execute_dag = AsyncMock(side_effect=Exception("Test error"))
            mock_build_runtime.return_value = mock_runtime
            
            options = {"test": True}
            result = await pipeline.run_complete_workflow(options)
            
            assert result is False
            mock_finalize.assert_called_once_with(pipeline.session.start_time, success=False)

    async def test_run_complete_workflow_with_verbose_error(self) -> None:
        """Test run_complete_workflow with verbose error logging."""
        settings = CrackerjackSettings()
        settings.execution.verbose = True
        
        pipeline = WorkflowPipeline(settings=settings)
        
        with patch.object(pipeline, '_initialize_workflow_session'), \
             patch.object(pipeline, '_clear_oneiric_cache'), \
             patch('crackerjack.core.workflow_orchestrator.build_oneiric_runtime') as mock_build_runtime, \
             patch.object(pipeline.session, 'finalize_session'), \
             patch.object(pipeline.logger, 'exception') as mock_exception_log:
            
            mock_runtime = MagicMock()
            mock_runtime.workflow_bridge.execute_dag = AsyncMock(side_effect=Exception("Test error"))
            mock_build_runtime.return_value = mock_runtime
            
            options = {"test": True}
            result = await pipeline.run_complete_workflow(options)
            
            assert result is False
            mock_exception_log.assert_called_once()


class TestWorkflowPipelineSyncMethods:
    """Test synchronous methods of WorkflowPipeline."""

    def test_run_complete_workflow_sync(self) -> None:
        """Test run_complete_workflow_sync method."""
        pipeline = WorkflowPipeline()
        
        with patch.object(pipeline, 'run_complete_workflow') as mock_async_method:
            mock_async_method.return_value = asyncio.Future()
            mock_async_method.return_value.set_result(True)
            
            options = {"test": True}
            result = pipeline.run_complete_workflow_sync(options)
            
            # Since we're mocking the async method, we can't actually run the coroutine
            # So we'll just verify the method was called
            mock_async_method.assert_called_once()

    def test_execute_workflow(self) -> None:
        """Test execute_workflow method."""
        pipeline = WorkflowPipeline()
        
        with patch.object(pipeline, 'run_complete_workflow_sync') as mock_sync_method:
            mock_sync_method.return_value = True
            
            options = {"test": True}
            result = pipeline.execute_workflow(options)
            
            assert result is True
            mock_sync_method.assert_called_once_with(options)


class TestWorkflowPipelinePrivateMethods:
    """Test private methods of WorkflowPipeline."""

    def test_initialize_workflow_session(self) -> None:
        """Test _initialize_workflow_session method."""
        pipeline = WorkflowPipeline()
        
        with patch.object(pipeline.session, 'initialize_session_tracking') as mock_track:
            options = {"test": True}
            pipeline._initialize_workflow_session(options)
            
            mock_track.assert_called_once_with(options)

    def test_clear_oneiric_cache_no_db(self) -> None:
        """Test _clear_oneiric_cache when DB doesn't exist."""
        pipeline = WorkflowPipeline()
        
        # Temporarily change the package path to a location without the cache DB
        temp_path = Path("/tmp/nonexistent")
        pipeline.pkg_path = temp_path
        
        # This should not raise an exception
        pipeline._clear_oneiric_cache()

    def test_clear_oneiric_cache_with_db_exists(self) -> None:
        """Test _clear_oneiric_cache when DB exists."""
        pipeline = WorkflowPipeline()
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("sqlite3.connect") as mock_connect, \
             patch.object(pipeline.logger, 'debug'):
            
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_connect.return_value.__exit__.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            
            pipeline._clear_oneiric_cache()
            
            # Verify the SQL statements were executed
            assert mock_cursor.execute.call_count >= 3
            mock_conn.commit.assert_called_once()

    def test_clear_oneiric_cache_with_exception(self) -> None:
        """Test _clear_oneiric_cache when DB operations fail."""
        pipeline = WorkflowPipeline()
        
        with patch("pathlib.Path.exists", return_value=True), \
             patch("sqlite3.connect", side_effect=Exception("DB Error")), \
             patch.object(pipeline.logger, 'warning') as mock_warning:
            
            pipeline._clear_oneiric_cache()
            
            mock_warning.assert_called_once()

    def test_run_fast_hooks_phase(self) -> None:
        """Test _run_fast_hooks_phase method."""
        pipeline = WorkflowPipeline()
        
        with patch.object(pipeline.phases, 'run_fast_hooks_only', return_value=True) as mock_run:
            options = {"test": True}
            result = pipeline._run_fast_hooks_phase(options)
            
            assert result is True
            mock_run.assert_called_once_with(options)

    def test_configure_session_cleanup(self) -> None:
        """Test _configure_session_cleanup method."""
        pipeline = WorkflowPipeline()
        
        # Method exists and should not raise an exception
        options = {"test": True}
        pipeline._configure_session_cleanup(options)
        # Method currently does nothing, so just verify it doesn't crash

    def test_initialize_zuban_lsp(self) -> None:
        """Test _initialize_zuban_lsp method."""
        pipeline = WorkflowPipeline()
        
        # Method exists and should not raise an exception
        options = {"test": True}
        pipeline._initialize_zuban_lsp(options)
        # Method currently does nothing, so just verify it doesn't crash

    def test_configure_hook_manager_lsp(self) -> None:
        """Test _configure_hook_manager_lsp method."""
        pipeline = WorkflowPipeline()
        
        # Method exists and should not raise an exception
        options = {"test": True}
        pipeline._configure_hook_manager_lsp(options)
        # Method currently does nothing, so just verify it doesn't crash

    def test_register_lsp_cleanup_handler(self) -> None:
        """Test _register_lsp_cleanup_handler method."""
        pipeline = WorkflowPipeline()
        
        # Method exists and should not raise an exception
        options = {"test": True}
        pipeline._register_lsp_cleanup_handler(options)
        # Method currently does nothing, so just verify it doesn't crash

    def test_log_workflow_startup_info(self) -> None:
        """Test _log_workflow_startup_info method."""
        pipeline = WorkflowPipeline()
        
        # Method exists and should not raise an exception
        options = {"test": True}
        pipeline._log_workflow_startup_info(options)
        # Method currently does nothing, so just verify it doesn't crash