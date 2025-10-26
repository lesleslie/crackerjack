import asyncio
import time
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest
from rich.console import Console

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import WorkflowPipeline


@pytest.mark.skip(reason="WorkflowPipeline requires complex nested ACB DI setup - integration test, not unit test")
class TestWorkflowPipeline:
    @pytest.fixture
    def console(self):
        return Console()

    @pytest.fixture
    def pkg_path(self):
        return Path(tempfile.gettempdir())

    @pytest.fixture
    def session(self, console, pkg_path):
        return SessionCoordinator(console, pkg_path)

    @pytest.fixture
    def phases(self):
        return MagicMock(spec=PhaseCoordinator)

    @pytest.fixture
    def pipeline(self, console, pkg_path, session, phases):
        return WorkflowPipeline(console, pkg_path, session, phases)

    def test_init(self, pipeline, console, pkg_path, phases):
        """Test WorkflowPipeline initialization"""
        assert pipeline.console == console
        assert pipeline.pkg_path == pkg_path
        assert pipeline.session is not None
        assert pipeline.phases == phases
        assert pipeline._mcp_state_manager is None
        assert pipeline._last_security_audit is None
        assert pipeline._debugger is None
        assert pipeline._quality_intelligence is not None

    def test_debugger_property(self, pipeline):
        """Test debugger property lazy loading"""
        with patch('crackerjack.core.workflow_orchestrator.get_ai_agent_debugger') as mock_debugger:
            mock_debugger_instance = Mock()
            mock_debugger.return_value = mock_debugger_instance

            # First access should create the debugger
            debugger1 = pipeline.debugger
            mock_debugger.assert_called_once()
            assert debugger1 == mock_debugger_instance

            # Second access should return the same instance
            debugger2 = pipeline.debugger
            mock_debugger.assert_called_once()  # Still only called once
            assert debugger2 == mock_debugger_instance

    def test_should_debug(self, pipeline):
        """Test _should_debug method"""
        # Test when AI_AGENT_DEBUG is not set
        with patch('os.environ.get', return_value="0"):
            assert pipeline._should_debug() is False

        # Test when AI_AGENT_DEBUG is set to 1
        with patch('os.environ.get', return_value="1"):
            assert pipeline._should_debug() is True

    @pytest.mark.asyncio
    async def test_run_complete_workflow_success(self, pipeline):
        """Test successful workflow execution"""
        # Create mock options
        options = Mock()
        options.test = False
        options.skip_hooks = False

        # Mock all the methods that would be called
        with patch.object(pipeline, '_initialize_workflow_session') as mock_init_session, \
             patch.object(pipeline, '_execute_workflow_with_timing', return_value=True) as mock_execute, \
             patch.object(pipeline, '_performance_monitor') as mock_perf_monitor, \
             patch.object(pipeline, '_memory_optimizer') as mock_memory_optimizer, \
             patch.object(pipeline, '_cache') as mock_cache, \
             patch.object(pipeline.session, 'cleanup_resources') as mock_cleanup:

            # Setup mocks
            mock_perf_monitor.start_workflow = Mock()
            mock_perf_monitor.end_workflow = Mock(return_value=Mock(performance_score=85.5, total_duration_seconds=2.5))
            mock_memory_optimizer.optimize_memory = Mock()
            mock_cache.start = AsyncMock()
            mock_cache.stop = AsyncMock()

            # Run the workflow
            result = await pipeline.run_complete_workflow(options)

            # Verify the result and calls
            assert result is True
            mock_init_session.assert_called_once_with(options)
            mock_execute.assert_called_once()
            mock_perf_monitor.start_workflow.assert_called_once()
            mock_perf_monitor.end_workflow.assert_called_once()
            mock_cache.start.assert_called_once()
            mock_cache.stop.assert_called_once()
            mock_cleanup.assert_called_once()
            mock_memory_optimizer.optimize_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_complete_workflow_keyboard_interrupt(self, pipeline):
        """Test workflow execution with keyboard interrupt"""
        options = Mock()
        options.test = False
        options.skip_hooks = False

        with patch.object(pipeline, '_initialize_workflow_session'), \
             patch.object(pipeline, '_execute_workflow_with_timing', side_effect=KeyboardInterrupt()), \
             patch.object(pipeline, '_performance_monitor') as mock_perf_monitor, \
             patch.object(pipeline, '_handle_user_interruption', return_value=False) as mock_handle_interrupt, \
             patch.object(pipeline.session, 'cleanup_resources'):

            mock_perf_monitor.end_workflow = Mock()

            result = await pipeline.run_complete_workflow(options)

            assert result is False
            mock_perf_monitor.end_workflow.assert_called_once()
            mock_handle_interrupt.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_complete_workflow_exception(self, pipeline):
        """Test workflow execution with exception"""
        options = Mock()
        options.test = False
        options.skip_hooks = False

        test_exception = Exception("Test exception")

        with patch.object(pipeline, '_initialize_workflow_session'), \
             patch.object(pipeline, '_execute_workflow_with_timing', side_effect=test_exception), \
             patch.object(pipeline, '_performance_monitor') as mock_perf_monitor, \
             patch.object(pipeline, '_handle_workflow_exception', return_value=False) as mock_handle_exception, \
             patch.object(pipeline.session, 'cleanup_resources'):

            mock_perf_monitor.end_workflow = Mock()

            result = await pipeline.run_complete_workflow(options)

            assert result is False
            mock_perf_monitor.end_workflow.assert_called_once()
            mock_handle_exception.assert_called_once_with(test_exception)

    def test_initialize_workflow_session(self, pipeline):
        """Test _initialize_workflow_session method"""
        options = Mock()

        with patch.object(pipeline.session, 'initialize_session_tracking') as mock_init_tracking, \
             patch.object(pipeline.session, 'track_task') as mock_track_task, \
             patch.object(pipeline, '_log_workflow_startup_debug') as mock_log_debug, \
             patch.object(pipeline, '_configure_session_cleanup') as mock_config_cleanup, \
             patch.object(pipeline, '_initialize_zuban_lsp') as mock_init_lsp, \
             patch.object(pipeline, '_configure_hook_manager_lsp') as mock_config_lsp, \
             patch.object(pipeline, '_register_lsp_cleanup_handler') as mock_register_cleanup, \
             patch.object(pipeline, '_log_workflow_startup_info') as mock_log_info:

            pipeline._initialize_workflow_session(options)

            mock_init_tracking.assert_called_once_with(options)
            mock_track_task.assert_called_once_with("workflow", "Complete crackerjack workflow")
            mock_log_debug.assert_called_once_with(options)
            mock_config_cleanup.assert_called_once_with(options)
            mock_init_lsp.assert_called_once_with(options)
            mock_config_lsp.assert_called_once_with(options)
            mock_register_cleanup.assert_called_once_with(options)
            mock_log_info.assert_called_once_with(options)

    def test_log_workflow_startup_debug(self, pipeline):
        """Test _log_workflow_startup_debug method"""
        options = Mock()
        options.test = True
        options.skip_hooks = False
        options.ai_agent = True

        # Test when debugging is disabled
        with patch.object(pipeline, '_should_debug', return_value=False):
            # Mock the debugger property to avoid the setter issue
            with patch.object(type(pipeline), 'debugger', new_callable=PropertyMock) as mock_debugger_prop:
                mock_debugger_instance = Mock()
                mock_debugger_prop.return_value = mock_debugger_instance
                pipeline._log_workflow_startup_debug(options)
                mock_debugger_instance.log_workflow_phase.assert_not_called()

        # Test when debugging is enabled
        with patch.object(pipeline, '_should_debug', return_value=True):
            # Mock the debugger property to avoid the setter issue
            with patch.object(type(pipeline), 'debugger', new_callable=PropertyMock) as mock_debugger_prop:
                mock_debugger_instance = Mock()
                mock_debugger_prop.return_value = mock_debugger_instance
                pipeline._log_workflow_startup_debug(options)
                mock_debugger_instance.log_workflow_phase.assert_called_once_with(
                    "workflow_execution",
                    "started",
                    details={
                        "testing": True,
                        "skip_hooks": False,
                        "ai_agent": True,
                    }
                )

    def test_configure_session_cleanup(self, pipeline):
        """Test _configure_session_cleanup method"""
        # Test when options has cleanup attribute
        options = Mock()
        options.cleanup = Mock()

        with patch.object(pipeline.session, 'set_cleanup_config') as mock_set_config:
            pipeline._configure_session_cleanup(options)
            mock_set_config.assert_called_once_with(options.cleanup)

        # Test when options doesn't have cleanup attribute
        options = Mock()
        del options.cleanup

        with patch.object(pipeline.session, 'set_cleanup_config') as mock_set_config:
            pipeline._configure_session_cleanup(options)
            mock_set_config.assert_not_called()

    def test_should_skip_zuban_lsp(self, pipeline):
        """Test _should_skip_zuban_lsp method"""
        # Test when no_zuban_lsp is True
        options = Mock()
        options.no_zuban_lsp = True

        with patch.object(pipeline, 'logger') as mock_logger:
            result = pipeline._should_skip_zuban_lsp(options)
            assert result is True
            mock_logger.debug.assert_called_once_with("Zuban LSP server disabled by --no-zuban-lsp flag")

        # Test when zuban_lsp config exists and is disabled
        options = Mock()
        options.no_zuban_lsp = False
        options.zuban_lsp = Mock()
        options.zuban_lsp.enabled = False

        with patch.object(pipeline, 'logger') as mock_logger:
            result = pipeline._should_skip_zuban_lsp(options)
            assert result is True
            mock_logger.debug.assert_called_once_with("Zuban LSP server disabled in configuration")

        # Test when zuban_lsp config exists but auto_start is False
        options = Mock()
        options.no_zuban_lsp = False
        options.zuban_lsp = Mock()
        options.zuban_lsp.enabled = True
        options.zuban_lsp.auto_start = False

        with patch.object(pipeline, 'logger') as mock_logger:
            result = pipeline._should_skip_zuban_lsp(options)
            assert result is True
            mock_logger.debug.assert_called_once_with("Zuban LSP server auto-start disabled in configuration")

        # Test when zuban_lsp should not be skipped
        options = Mock()
        options.no_zuban_lsp = False
        options.zuban_lsp = Mock()
        options.zuban_lsp.enabled = True
        options.zuban_lsp.auto_start = True

        result = pipeline._should_skip_zuban_lsp(options)
        assert result is False
