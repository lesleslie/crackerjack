import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowPipeline,
)


class TestWorkflowPipeline:
    @pytest.fixture
    def console(self):
        return Mock(spec=Console)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_session(self):
        return Mock(spec=SessionCoordinator)

    @pytest.fixture
    def mock_phases(self):
        return Mock(spec=PhaseCoordinator)

    @pytest.fixture
    def pipeline(self, console, temp_dir, mock_session, mock_phases):
        return WorkflowPipeline(
            console=console, pkg_path=temp_dir, session=mock_session, phases=mock_phases
        )

    @pytest.fixture
    def mock_options(self):
        options = Mock()
        options.testing = False
        options.skip_hooks = False
        options.test = False
        return options

    def test_pipeline_initialization(
        self, pipeline, console, temp_dir, mock_session, mock_phases
    ) -> None:
        assert pipeline.console == console
        assert pipeline.pkg_path == temp_dir
        assert pipeline.session == mock_session
        assert pipeline.phases == mock_phases
        assert hasattr(pipeline, "logger")

    def test_run_complete_workflow_success(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_configuration_phase.return_value = True
        mock_phases.run_cleaning_phase.return_value = True
        mock_phases.run_hooks_phase.return_value = True
        mock_phases.run_publishing_phase.return_value = True
        mock_phases.run_commit_phase.return_value = True

        with patch("time.time", side_effect=[1000.0, 1010.0]):
            result = pipeline.run_complete_workflow(mock_options)

        assert result is True

        mock_session.initialize_session_tracking.assert_called_once_with(mock_options)
        mock_session.track_task.assert_called_once_with(
            "workflow", "Complete crackerjack workflow"
        )
        mock_session.finalize_session.assert_called_once_with(1000.0, True)
        mock_session.cleanup_resources.assert_called_once()

    def test_run_complete_workflow_with_cleanup_config(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_options.cleanup = Mock()
        mock_phases.run_configuration_phase.return_value = True
        mock_phases.run_cleaning_phase.return_value = True
        mock_phases.run_hooks_phase.return_value = True
        mock_phases.run_publishing_phase.return_value = True
        mock_phases.run_commit_phase.return_value = True

        result = pipeline.run_complete_workflow(mock_options)

        assert result is True
        mock_session.set_cleanup_config.assert_called_once_with(mock_options.cleanup)

    def test_run_complete_workflow_keyboard_interrupt(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_configuration_phase.side_effect = KeyboardInterrupt()

        result = pipeline.run_complete_workflow(mock_options)

        assert result is False
        pipeline.console.print.assert_called_with("Interrupted by user")
        mock_session.fail_task.assert_called_with("workflow", "Interrupted by user")
        mock_session.cleanup_resources.assert_called_once()

    def test_run_complete_workflow_unexpected_exception(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        test_error = RuntimeError("Test error")
        mock_phases.run_configuration_phase.side_effect = test_error

        result = pipeline.run_complete_workflow(mock_options)

        assert result is False
        pipeline.console.print.assert_called_with("Error: Test error")
        mock_session.fail_task.assert_called_with(
            "workflow", "Unexpected error: Test error"
        )
        mock_session.cleanup_resources.assert_called_once()

    def test_execute_workflow_phases_cleaning_failure(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_configuration_phase.return_value = True
        mock_phases.run_cleaning_phase.return_value = False

        result = pipeline._execute_workflow_phases(mock_options)

        assert result is False
        mock_session.fail_task.assert_called_with("workflow", "Cleaning phase failed")

    def test_execute_workflow_phases_publishing_failure(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_configuration_phase.return_value = True
        mock_phases.run_cleaning_phase.return_value = True
        mock_phases.run_hooks_phase.return_value = True
        mock_phases.run_publishing_phase.return_value = False

        result = pipeline._execute_workflow_phases(mock_options)

        assert result is False
        mock_session.fail_task.assert_called_with("workflow", "Publishing failed")

    def test_execute_workflow_phases_commit_failure(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_configuration_phase.return_value = True
        mock_phases.run_cleaning_phase.return_value = True
        mock_phases.run_hooks_phase.return_value = True
        mock_phases.run_publishing_phase.return_value = True
        mock_phases.run_commit_phase.return_value = False

        result = pipeline._execute_workflow_phases(mock_options)

        assert result is True

    def test_execute_quality_phase_with_testing(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_options.test = True
        mock_phases.run_fast_hooks_only.return_value = True
        mock_phases.run_testing_phase.return_value = True
        mock_phases.run_comprehensive_hooks_only.return_value = True

        result = pipeline._execute_quality_phase(mock_options)

        assert result is True
        mock_phases.run_fast_hooks_only.assert_called_once_with(mock_options)
        mock_phases.run_testing_phase.assert_called_once_with(mock_options)
        mock_phases.run_comprehensive_hooks_only.assert_called_once_with(mock_options)

    def test_execute_quality_phase_without_testing(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_options.test = False
        mock_phases.run_hooks_phase.return_value = True

        result = pipeline._execute_quality_phase(mock_options)

        assert result is True
        mock_phases.run_hooks_phase.assert_called_once_with(mock_options)

    def test_execute_test_workflow_fast_hooks_failure(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_fast_hooks_only.return_value = False

        result = pipeline._execute_test_workflow(mock_options)

        assert result is False
        mock_session.fail_task.assert_called_with("workflow", "Fast hooks failed")

    def test_execute_test_workflow_testing_failure(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_fast_hooks_only.return_value = True
        mock_phases.run_testing_phase.return_value = False

        result = pipeline._execute_test_workflow(mock_options)

        assert result is False
        mock_session.fail_task.assert_called_with("workflow", "Testing failed")

    def test_execute_test_workflow_comprehensive_hooks_failure(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_fast_hooks_only.return_value = True
        mock_phases.run_testing_phase.return_value = True
        mock_phases.run_comprehensive_hooks_only.return_value = False

        result = pipeline._execute_test_workflow(mock_options)

        assert result is False
        mock_session.fail_task.assert_called_with(
            "workflow", "Comprehensive hooks failed"
        )

    def test_execute_standard_hooks_workflow_success(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_hooks_phase.return_value = True

        result = pipeline._execute_standard_hooks_workflow(mock_options)

        assert result is True

    def test_execute_standard_hooks_workflow_failure(
        self, pipeline, mock_options, mock_session, mock_phases
    ) -> None:
        mock_phases.run_hooks_phase.return_value = False

        result = pipeline._execute_standard_hooks_workflow(mock_options)

        assert result is False
        mock_session.fail_task.assert_called_with("workflow", "Hooks failed")


class TestWorkflowOrchestrator:
    @pytest.fixture
    def console(self):
        return Mock(spec=Console)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_orchestrator_initialization_defaults(self) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator()

            assert orchestrator.console is not None
            assert orchestrator.pkg_path == Path.cwd()
            assert orchestrator.dry_run is False
            assert hasattr(orchestrator, "session")
            assert hasattr(orchestrator, "phases")
            assert hasattr(orchestrator, "pipeline")
            assert hasattr(orchestrator, "logger")

    def test_orchestrator_initialization_custom(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(
                console=console, pkg_path=temp_dir, dry_run=True
            )

            assert orchestrator.console == console
            assert orchestrator.pkg_path == temp_dir
            assert orchestrator.dry_run is True

    def test_initialize_logging(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch(
                "crackerjack.core.workflow_orchestrator.setup_structured_logging"
            ) as mock_setup,
            patch("time.time", return_value=1234567890),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            WorkflowOrchestrator(console=console, pkg_path=temp_dir)

            mock_setup.assert_called_once()
            call_args = mock_setup.call_args[1]
            assert "log_file" in call_args
            assert "crackerjack-debug-1234567890.log" in str(call_args["log_file"])

    def test_initialize_session_tracking(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)
            mock_options = Mock()

            orchestrator._initialize_session_tracking(mock_options)

            orchestrator.session.initialize_session_tracking.assert_called_once_with(
                mock_options
            )

    def test_track_task(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)

            orchestrator._track_task("test_task", "Test Task")

            orchestrator.session.track_task.assert_called_once_with(
                "test_task", "Test Task"
            )

    def test_complete_task(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)

            orchestrator._complete_task("test_task", "Task completed")

            orchestrator.session.complete_task.assert_called_once_with(
                "test_task", "Task completed"
            )

    def test_fail_task(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)

            orchestrator._fail_task("test_task", "Task failed")

            orchestrator.session.fail_task.assert_called_once_with(
                "test_task", "Task failed"
            )

    def test_cleanup_resources(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)

            orchestrator._cleanup_resources()

            orchestrator.session.cleanup_resources.assert_called_once()

    def test_register_cleanup(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)
            cleanup_handler = Mock()

            orchestrator._register_cleanup(cleanup_handler)

            orchestrator.session.register_cleanup.assert_called_once_with(
                cleanup_handler
            )

    def test_track_lock_file(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)
            lock_file = temp_dir / "test.lock"

            orchestrator._track_lock_file(lock_file)

            orchestrator.session.track_lock_file.assert_called_once_with(lock_file)

    def test_phase_delegation_methods(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)
            mock_options = Mock()

            orchestrator.run_cleaning_phase(mock_options)
            orchestrator.phases.run_cleaning_phase.assert_called_with(mock_options)

            orchestrator.run_fast_hooks_only(mock_options)
            orchestrator.phases.run_fast_hooks_only.assert_called_with(mock_options)

            orchestrator.run_comprehensive_hooks_only(mock_options)
            orchestrator.phases.run_comprehensive_hooks_only.assert_called_with(
                mock_options
            )

            orchestrator.run_hooks_phase(mock_options)
            orchestrator.phases.run_hooks_phase.assert_called_with(mock_options)

            orchestrator.run_testing_phase(mock_options)
            orchestrator.phases.run_testing_phase.assert_called_with(mock_options)

            orchestrator.run_publishing_phase(mock_options)
            orchestrator.phases.run_publishing_phase.assert_called_with(mock_options)

            orchestrator.run_commit_phase(mock_options)
            orchestrator.phases.run_commit_phase.assert_called_with(mock_options)

            orchestrator.run_configuration_phase(mock_options)
            orchestrator.phases.run_configuration_phase.assert_called_with(mock_options)

    def test_run_complete_workflow_delegation(self, console, temp_dir) -> None:
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.create_container"
            ) as mock_create,
            patch("crackerjack.core.workflow_orchestrator.setup_structured_logging"),
        ):
            mock_container = Mock()
            mock_create.return_value = mock_container

            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_dir)
            mock_options = Mock()

            orchestrator.run_complete_workflow(mock_options)

            orchestrator.pipeline.run_complete_workflow.assert_called_once_with(
                mock_options
            )


class TestWorkflowOrchestratorIntegration:
    def test_full_orchestrator_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pkg_path = Path(temp_dir)
            console = Console()

            with patch(
                "crackerjack.core.workflow_orchestrator.setup_structured_logging"
            ):
                orchestrator = WorkflowOrchestrator(
                    console=console, pkg_path=pkg_path, dry_run=False
                )

                assert orchestrator.console == console
                assert orchestrator.pkg_path == pkg_path
                assert orchestrator.dry_run is False
                assert hasattr(orchestrator, "container")
                assert hasattr(orchestrator, "session")
                assert hasattr(orchestrator, "phases")
                assert hasattr(orchestrator, "pipeline")
                assert hasattr(orchestrator, "logger")

                assert orchestrator.pipeline.console == console
                assert orchestrator.pipeline.pkg_path == pkg_path
                assert orchestrator.pipeline.session == orchestrator.session
                assert orchestrator.pipeline.phases == orchestrator.phases
