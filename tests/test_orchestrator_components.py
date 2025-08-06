import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import WorkflowPipeline
from crackerjack.errors import CrackerjackError, ErrorCode
from crackerjack.models.config import WorkflowOptions


class TestWorkflowPipeline:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / project")

    @pytest.fixture
    def mock_session(self):
        session = Mock(spec=SessionCoordinator)
        session.initialize_session_tracking = Mock()
        session.track_task = Mock()
        session.complete_task = Mock()
        session.fail_task = Mock()
        session.set_cleanup_config = Mock()
        session.cleanup_session = Mock()
        session.cleanup_resources = Mock()
        session.finalize_session = Mock()
        session.register_cleanup = Mock()
        session.track_lock_file = Mock()
        session.get_performance_metrics = Mock(return_value={})
        return session

    @pytest.fixture
    def mock_phases(self):
        phases = Mock(spec=PhaseCoordinator)
        phases.run_configuration_phase = Mock(return_value=True)
        phases.run_cleaning_phase = Mock(return_value=True)
        phases.run_hooks_phase = Mock(return_value=True)
        phases.run_fast_hooks_only = Mock(return_value=True)
        phases.run_comprehensive_hooks_only = Mock(return_value=True)
        phases.run_testing_phase = Mock(return_value=True)
        phases.run_publishing_phase = Mock(return_value=True)
        phases.run_commit_phase = Mock(return_value=True)
        return phases

    @pytest.fixture
    def workflow_pipeline(self, mock_console, mock_pkg_path, mock_session, mock_phases):
        return WorkflowPipeline(
            console=mock_console,
            pkg_path=mock_pkg_path,
            session=mock_session,
            phases=mock_phases,
        )

    def test_init(
        self, workflow_pipeline, mock_console, mock_pkg_path, mock_session, mock_phases
    ) -> None:
        assert workflow_pipeline.console == mock_console
        assert workflow_pipeline.pkg_path == mock_pkg_path
        assert workflow_pipeline.session == mock_session
        assert workflow_pipeline.phases == mock_phases

    def test_run_complete_workflow_success(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True
        options.git.commit = True

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            result = workflow_pipeline.run_complete_workflow(options)

        assert result is True
        mock_session.initialize_session_tracking.assert_called_once_with(options)
        mock_session.track_task.assert_called_once_with(
            "workflow", "Complete crackerjack workflow"
        )

    def test_run_complete_workflow_with_error(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()
        options.testing.test = True

        mock_phases.run_testing_phase.side_effect = CrackerjackError(
            "Test failed", ErrorCode.TEST_EXECUTION_ERROR
        )

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            result = workflow_pipeline.run_complete_workflow(options)

        assert result is False
        mock_session.fail_task.assert_called_with(
            "workflow", "Unexpected error: Test failed"
        )

    def test_workflow_phase_execution_order(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True
        options.publishing.publish = "patch"
        options.git.commit = True

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            workflow_pipeline.run_complete_workflow(options)

        mock_phases.run_configuration_phase.assert_called_once()
        mock_phases.run_cleaning_phase.assert_called_once()
        mock_phases.run_fast_hooks_only.assert_called_once()
        mock_phases.run_testing_phase.assert_called_once()
        mock_phases.run_comprehensive_hooks_only.assert_called_once()
        mock_phases.run_publishing_phase.assert_called_once()
        mock_phases.run_commit_phase.assert_called_once()

    def test_workflow_partial_execution(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = False
        options.testing.test = True
        options.git.commit = False

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            workflow_pipeline.run_complete_workflow(options)

        mock_phases.run_configuration_phase.assert_called_once()
        mock_phases.run_cleaning_phase.assert_called_once()
        mock_phases.run_fast_hooks_only.assert_called_once()
        mock_phases.run_testing_phase.assert_called_once()
        mock_phases.run_comprehensive_hooks_only.assert_called_once()
        mock_phases.run_commit_phase.assert_called_once()

    def test_cleanup_configuration(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()
        options.cleanup = {"keep_debug_logs": 10, "keep_coverage_files": 20}

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            workflow_pipeline.run_complete_workflow(options)

        mock_session.set_cleanup_config.assert_called_once_with(options.cleanup)

    def test_performance_metrics_collection(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()
        options.testing.test = True

        mock_session.get_performance_metrics.return_value = {
            "total_time": 45.2,
            "hook_time": 12.5,
            "test_time": 30.1,
        }

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            workflow_pipeline.run_complete_workflow(options)

        mock_session.initialize_session_tracking.assert_called_once()
        mock_session.finalize_session.assert_called_once()

    def test_session_cleanup_on_completion(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            workflow_pipeline.run_complete_workflow(options)

        mock_session.cleanup_resources.assert_called_once()

    def test_session_cleanup_on_error(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()

        mock_phases.run_hooks_phase.side_effect = CrackerjackError(
            "Hook failed", ErrorCode.PRE_COMMIT_ERROR
        )

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            result = workflow_pipeline.run_complete_workflow(options)

        assert result is False
        mock_session.cleanup_resources.assert_called_once()

    def test_logging_context_integration(
        self, workflow_pipeline, mock_session, mock_phases
    ) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        options.execution.skip_hooks = True

        with patch(
            "crackerjack.core.workflow_orchestrator.LoggingContext"
        ) as mock_logging:
            workflow_pipeline.run_complete_workflow(options)

        mock_logging.assert_called_once()


class TestSessionCoordinatorMocking:
    @pytest.fixture
    def mock_console(self):
        return Mock()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / session")

    def test_session_coordinator_creation(self, mock_console, mock_pkg_path) -> None:
        with patch("crackerjack.services.logging.get_logger"):
            session = SessionCoordinator(mock_console, mock_pkg_path)

            assert session.console == mock_console
            assert session.pkg_path == mock_pkg_path

    def test_session_tracking_methods(self, mock_console, mock_pkg_path) -> None:
        with patch("crackerjack.services.logging.get_logger"):
            session = SessionCoordinator(mock_console, mock_pkg_path)

            assert hasattr(session, "initialize_session_tracking")
            assert hasattr(session, "track_task")
            assert hasattr(session, "cleanup_resources")


class TestPhaseCoordinatorMocking:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Mock(),
            "pkg_path": Path(" / test / phases"),
            "session": Mock(),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
        }

    def test_phase_coordinator_interface(self, mock_dependencies) -> None:
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        assert hasattr(PhaseCoordinator, "run_cleaning_phase")
        assert hasattr(PhaseCoordinator, "run_hooks_phase")
        assert hasattr(PhaseCoordinator, "run_testing_phase")
        assert hasattr(PhaseCoordinator, "run_publishing_phase")
        assert hasattr(PhaseCoordinator, "run_commit_phase")

    def test_phase_methods_signature(self) -> None:
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        mock_coordinator = Mock(spec=PhaseCoordinator)

        mock_coordinator.run_cleaning_phase.return_value = True
        mock_coordinator.run_hooks_phase.return_value = True
        mock_coordinator.run_testing_phase.return_value = True

        assert mock_coordinator.run_cleaning_phase() is True
        assert mock_coordinator.run_hooks_phase() is True
        assert mock_coordinator.run_testing_phase() is True


class TestWorkflowOptionsIntegration:
    def test_workflow_options_creation(self) -> None:
        options = WorkflowOptions()

        assert hasattr(options, "clean")
        assert hasattr(options, "test")
        assert hasattr(options, "commit")
        assert hasattr(options, "publish")

    def test_workflow_options_configuration(self) -> None:
        options = WorkflowOptions()

        options.cleaning.clean = True
        options.testing.test = True
        options.testing.benchmark = True
        options.publishing.publish = "minor"
        options.git.commit = True
        options.execution.verbose = True

        assert options.clean is True
        assert options.test is True
        assert options.testing.benchmark is True
        assert options.publish == "minor"
        assert options.commit is True
        assert options.verbose is True

    def test_workflow_options_with_pipeline(self) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        options.execution.verbose = True

        mock_console = Mock()
        mock_pkg_path = Path(" / test")
        mock_session = Mock()
        mock_phases = Mock()

        mock_session.initialize_session_tracking = Mock()
        mock_session.track_task = Mock()
        mock_session.cleanup_session = Mock()
        mock_session.get_performance_metrics = Mock(return_value={})
        mock_phases.run_hooks_phase = Mock(return_value=True)
        mock_phases.run_testing_phase = Mock(return_value=True)

        pipeline = WorkflowPipeline(
            console=mock_console,
            pkg_path=mock_pkg_path,
            session=mock_session,
            phases=mock_phases,
        )

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            result = pipeline.run_complete_workflow(options)

        assert result is True


class TestErrorHandlingInWorkflow:
    def test_pipeline_error_propagation(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / errors")
        mock_session = Mock()
        mock_phases = Mock()

        mock_session.initialize_session_tracking = Mock()
        mock_session.track_task = Mock()
        mock_session.cleanup_session = Mock()

        test_error = CrackerjackError("Phase failed", ErrorCode.COMMAND_EXECUTION_ERROR)
        mock_phases.run_hooks_phase.side_effect = test_error

        pipeline = WorkflowPipeline(
            console=mock_console,
            pkg_path=mock_pkg_path,
            session=mock_session,
            phases=mock_phases,
        )

        options = WorkflowOptions()

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            result = pipeline.run_complete_workflow(options)

        assert result is False

        mock_session.cleanup_resources.assert_called_once()

    def test_multiple_error_types(self) -> None:
        error_types = [
            (ErrorCode.CONFIG_FILE_NOT_FOUND, "Config error"),
            (ErrorCode.TEST_EXECUTION_ERROR, "Test error"),
            (ErrorCode.PRE_COMMIT_ERROR, "Hook error"),
            (ErrorCode.PUBLISH_ERROR, "Publish error"),
        ]

        for error_code, message in error_types:
            mock_console = Mock()
            mock_pkg_path = Path(" / test / multi_error")
            mock_session = Mock()
            mock_phases = Mock()

            mock_session.initialize_session_tracking = Mock()
            mock_session.track_task = Mock()
            mock_session.cleanup_session = Mock()

            specific_error = CrackerjackError(message, error_code)
            mock_phases.run_hooks_phase.side_effect = specific_error

            pipeline = WorkflowPipeline(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                phases=mock_phases,
            )

            options = WorkflowOptions()

            with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
                result = pipeline.run_complete_workflow(options)

            assert result is False


class TestWorkflowPerformanceCharacteristics:
    def test_workflow_timing_tracking(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / performance")
        mock_session = Mock()
        mock_phases = Mock()

        mock_session.initialize_session_tracking = Mock()
        mock_session.track_task = Mock()
        mock_session.cleanup_session = Mock()
        mock_session.get_performance_metrics = Mock(
            return_value={
                "total_time": 42.5,
                "hook_time": 15.2,
                "test_time": 25.1,
            }
        )

        mock_phases.run_hooks_phase = Mock(return_value=True)
        mock_phases.run_testing_phase = Mock(return_value=True)

        pipeline = WorkflowPipeline(
            console=mock_console,
            pkg_path=mock_pkg_path,
            session=mock_session,
            phases=mock_phases,
        )

        options = WorkflowOptions()
        options.testing.test = True

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            start_time = time.time()
            result = pipeline.run_complete_workflow(options)
            end_time = time.time()

        assert result is True
        execution_time = end_time - start_time

        assert execution_time < 1.0

        mock_session.initialize_session_tracking.assert_called_once()

    def test_workflow_resource_cleanup(self) -> None:
        mock_console = Mock()
        mock_pkg_path = Path(" / test / cleanup")
        mock_session = Mock()
        mock_phases = Mock()

        cleanup_calls = []

        def track_cleanup() -> None:
            cleanup_calls.append("session_cleanup")

        mock_session.initialize_session_tracking = Mock()
        mock_session.track_task = Mock()
        mock_session.cleanup_resources = Mock(side_effect=track_cleanup)
        mock_phases.run_hooks_phase = Mock(return_value=True)

        pipeline = WorkflowPipeline(
            console=mock_console,
            pkg_path=mock_pkg_path,
            session=mock_session,
            phases=mock_phases,
        )

        options = WorkflowOptions()

        with patch("crackerjack.core.workflow_orchestrator.LoggingContext"):
            pipeline.run_complete_workflow(options)

        assert "session_cleanup" in cleanup_calls
        mock_session.cleanup_resources.assert_called_once()
