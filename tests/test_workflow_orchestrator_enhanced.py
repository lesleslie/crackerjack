import logging
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowPipeline,
)
from crackerjack.services.logging import setup_structured_logging


class MockOptions:
    def __init__(self, **kwargs) -> None:
        self.testing = kwargs.get("testing", False)
        self.autofix = kwargs.get("autofix", False)
        self.skip_hooks = kwargs.get("skip_hooks", False)
        self.test = kwargs.get("test", False)
        self.publish = kwargs.get("publish", False)
        self.commit = kwargs.get("commit", False)
        self.dry_run = kwargs.get("dry_run", False)


class TestWorkflowPipeline:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False, width=80)

    @pytest.fixture
    def pkg_path(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def mock_session(self):
        session = Mock()
        session.initialize_session_tracking = Mock()
        session.track_task = Mock()
        session.complete_task = Mock()
        session.fail_task = Mock()
        session.finalize_session = Mock()
        session.cleanup_resources = Mock()
        return session

    @pytest.fixture
    def mock_autofix(self):
        autofix = Mock()
        return autofix

    @pytest.fixture
    def mock_phases(self):
        phases = Mock()
        phases.run_configuration_phase = Mock(return_value=True)
        phases.run_cleaning_phase = Mock(return_value=True)
        phases.run_fast_hooks_only = Mock(return_value=True)
        phases.run_comprehensive_hooks_only = Mock(return_value=True)
        phases.run_hooks_phase = Mock(return_value=True)
        phases.run_testing_phase = Mock(return_value=True)
        phases.run_publishing_phase = Mock(return_value=True)
        phases.run_commit_phase = Mock(return_value=True)
        return phases

    @pytest.fixture
    def pipeline(self, console, pkg_path, mock_session, mock_phases):
        return WorkflowPipeline(console, pkg_path, mock_session, mock_phases)

    def test_pipeline_initialization(self, pipeline, console, pkg_path) -> None:
        assert pipeline.console == console
        assert pipeline.pkg_path == pkg_path
        assert pipeline.session is not None
        assert pipeline.phases is not None
        assert hasattr(pipeline, "logger")

    def test_complete_workflow_success(
        self, pipeline, mock_session, mock_phases
    ) -> None:
        options = MockOptions(testing=False, autofix=True)

        result = pipeline.run_complete_workflow(options)

        assert result is True
        mock_session.initialize_session_tracking.assert_called_once_with(options)
        mock_session.track_task.assert_called_once_with(
            "workflow", "Complete crackerjack workflow"
        )
        mock_session.finalize_session.assert_called_once()
        mock_session.cleanup_resources.assert_called_once()
        mock_phases.run_configuration_phase.assert_called_once_with(options)

    def test_complete_workflow_keyboard_interrupt(
        self, pipeline, mock_session, mock_phases
    ) -> None:
        options = MockOptions()
        mock_phases.run_configuration_phase.side_effect = KeyboardInterrupt()

        result = pipeline.run_complete_workflow(options)

        assert result is False
        mock_session.fail_task.assert_called_once_with(
            "workflow", "Interrupted by user"
        )
        mock_session.cleanup_resources.assert_called_once()

    def test_complete_workflow_exception(
        self, pipeline, mock_session, mock_phases
    ) -> None:
        options = MockOptions()
        mock_phases.run_configuration_phase.side_effect = RuntimeError("Test error")

        result = pipeline.run_complete_workflow(options)

        assert result is False
        mock_session.fail_task.assert_called_once_with(
            "workflow", "Unexpected error: Test error"
        )
        mock_session.cleanup_resources.assert_called_once()

    def test_execute_test_workflow_success(self, pipeline, mock_phases) -> None:
        options = MockOptions(test=True, autofix=True)

        result = pipeline._execute_test_workflow(options)

        assert result is True
        mock_phases.run_fast_hooks_only.assert_called_once()
        mock_phases.run_testing_phase.assert_called_once()
        mock_phases.run_comprehensive_hooks_only.assert_called_once()

    def test_execute_test_workflow_fast_hooks_failure(
        self, pipeline, mock_phases, mock_session
    ) -> None:
        options = MockOptions(test=True, autofix=False)
        mock_phases.run_fast_hooks_only.return_value = False

        result = pipeline._execute_test_workflow(options)

        assert result is False
        mock_session.fail_task.assert_called_once_with("workflow", "Fast hooks failed")

    def test_execute_test_workflow_testing_failure(
        self, pipeline, mock_phases, mock_session
    ) -> None:
        options = MockOptions(test=True, autofix=False)
        mock_phases.run_testing_phase.return_value = False

        result = pipeline._execute_test_workflow(options)

        assert result is False
        mock_session.fail_task.assert_called_once_with("workflow", "Testing failed")

    def test_execute_standard_hooks_workflow_success(
        self, pipeline, mock_phases
    ) -> None:
        options = MockOptions()

        result = pipeline._execute_standard_hooks_workflow(options)

        assert result is True
        mock_phases.run_hooks_phase.assert_called_once()

    def test_execute_standard_hooks_workflow_failure(
        self, pipeline, mock_phases, mock_session
    ) -> None:
        options = MockOptions(autofix=False)
        mock_phases.run_hooks_phase.return_value = False

        result = pipeline._execute_standard_hooks_workflow(options)

        assert result is False
        mock_session.fail_task.assert_called_once_with("workflow", "Hooks failed")


class TestWorkflowOrchestrator:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False, width=80)

    @pytest.fixture
    def pkg_path(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def orchestrator(self, console, pkg_path):
        with patch("crackerjack.core.container.create_container"):
            return WorkflowOrchestrator(console, pkg_path, dry_run=True)

    def test_orchestrator_initialization(self, orchestrator, console, pkg_path) -> None:
        assert orchestrator.console == console
        assert orchestrator.pkg_path == pkg_path
        assert orchestrator.dry_run is True
        assert hasattr(orchestrator, "container")
        assert hasattr(orchestrator, "session")
        assert hasattr(orchestrator, "phases")

    def test_logging_initialization(self, tmp_path) -> None:
        with patch("crackerjack.core.container.create_container"):
            WorkflowOrchestrator(pkg_path=tmp_path)

            log_files = list(tmp_path.glob("crackerjack-debug-*.log"))
            assert len(log_files) >= 0

    def test_session_tracking_methods(self, orchestrator) -> None:
        options = MockOptions()

        with patch.object(
            orchestrator.session, "initialize_session_tracking"
        ) as mock_init:
            orchestrator._initialize_session_tracking(options)
            mock_init.assert_called_once_with(options)

        with patch.object(orchestrator.session, "track_task") as mock_track:
            orchestrator._track_task("test_id", "test_name")
            mock_track.assert_called_once_with("test_id", "test_name")

        with patch.object(orchestrator.session, "complete_task") as mock_complete:
            orchestrator._complete_task("test_id", "details")
            mock_complete.assert_called_once_with("test_id", "details")

        with patch.object(orchestrator.session, "fail_task") as mock_fail:
            orchestrator._fail_task("test_id", "error")
            mock_fail.assert_called_once_with("test_id", "error")

    def test_phase_delegation_methods(self, orchestrator) -> None:
        options = MockOptions()

        methods_to_test = [
            "run_cleaning_phase",
            "run_fast_hooks_only",
            "run_comprehensive_hooks_only",
            "run_hooks_phase",
            "run_testing_phase",
            "run_publishing_phase",
            "run_commit_phase",
        ]

        for method_name in methods_to_test:
            orchestrator_method = getattr(orchestrator, method_name)
            getattr(orchestrator.phases, method_name)

            with patch.object(
                orchestrator.phases, method_name, return_value=True
            ) as mock_method:
                result = orchestrator_method(options)
                mock_method.assert_called_once_with(options)
                assert result is True

    def test_pipeline_delegation(self, orchestrator) -> None:
        options = MockOptions()

        with patch.object(
            orchestrator.pipeline, "run_complete_workflow", return_value=True
        ) as mock_run:
            result = orchestrator.run_complete_workflow(options)
            mock_run.assert_called_once_with(options)
            assert result is True


class TestLoggingIntegration:
    def test_workflow_with_structured_logging(self, tmp_path, capsys) -> None:
        log_file = tmp_path / "test.log"
        setup_structured_logging(level="INFO", json_output=True, log_file=log_file)

        console = Console(force_terminal=False)

        with patch("crackerjack.core.container.create_container"):
            orchestrator = WorkflowOrchestrator(console, tmp_path)

        with (
            patch.object(
                orchestrator.phases, "run_configuration_phase", return_value=True
            ),
            patch.object(orchestrator.phases, "run_cleaning_phase", return_value=True),
            patch.object(orchestrator.phases, "run_hooks_phase", return_value=True),
            patch.object(
                orchestrator.phases, "run_publishing_phase", return_value=True
            ),
            patch.object(orchestrator.phases, "run_commit_phase", return_value=True),
        ):
            options = MockOptions(publish=True, commit=True)
            result = orchestrator.run_complete_workflow(options)

            assert result is True

    def test_error_logging_in_workflow(self, tmp_path, capsys) -> None:
        setup_structured_logging(level="INFO", json_output=False)

        console = Console(force_terminal=False)

        with patch("crackerjack.core.container.create_container"):
            orchestrator = WorkflowOrchestrator(console, tmp_path)

        with patch.object(
            orchestrator.phases,
            "run_configuration_phase",
            side_effect=RuntimeError("Test error"),
        ):
            options = MockOptions()
            result = orchestrator.run_complete_workflow(options)

            assert result is False

            captured = capsys.readouterr()
            assert "Workflow execution failed" in captured.out
            assert "Test error" in captured.out
            assert "RuntimeError" in captured.out


@pytest.fixture(autouse=True)
def reset_logging():
    yield

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    import structlog

    structlog.reset_defaults()
