from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.container import DependencyContainer
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowPipeline,
)
from crackerjack.models.config import WorkflowOptions
from crackerjack.models.protocols import FileSystemInterface


@pytest.fixture
def console():
    return Console()


@pytest.fixture
def pkg_path(tmp_path):
    return tmp_path


@pytest.fixture
def session(console, pkg_path):
    return SessionCoordinator(console, pkg_path)


@pytest.fixture
def phase_coordinator(console, pkg_path, session):
    filesystem_mock = Mock()
    git_service_mock = Mock()
    hook_manager_mock = Mock()
    test_manager_mock = Mock()
    publish_manager_mock = Mock()

    return PhaseCoordinator(
        console=console,
        pkg_path=pkg_path,
        session=session,
        filesystem=filesystem_mock,
        git_service=git_service_mock,
        hook_manager=hook_manager_mock,
        test_manager=test_manager_mock,
        publish_manager=publish_manager_mock,
    )


@pytest.fixture
def workflow_options():
    return WorkflowOptions()


class TestWorkflowOrchestrator:
    @pytest.fixture
    def orchestrator(self, console, pkg_path):
        return WorkflowOrchestrator(console, pkg_path)

    def test_init(self, orchestrator, console, pkg_path) -> None:
        assert orchestrator.console == console
        assert orchestrator.pkg_path == pkg_path
        assert orchestrator.container is not None
        assert orchestrator.session is not None
        assert orchestrator.phases is not None

    @patch("crackerjack.core.workflow_orchestrator.SessionCoordinator")
    @patch("crackerjack.core.workflow_orchestrator.PhaseCoordinator")
    async def test_process_workflow(
        self, mock_phase, mock_session, orchestrator, workflow_options
    ) -> None:
        mock_session_inst = Mock()
        mock_phase_inst = Mock()

        mock_session.return_value = mock_session_inst
        mock_phase.return_value = mock_phase_inst

        orchestrator = WorkflowOrchestrator(orchestrator.console, orchestrator.pkg_path)
        orchestrator.session = mock_session_inst
        orchestrator.phases = mock_phase_inst

        workflow_options.cleaning.clean = True
        await orchestrator.process(workflow_options)

        mock_session_inst.start_session.assert_called_once()
        mock_phase_inst.run_cleaning_phase.assert_called_once()

    def test_get_version(self, orchestrator) -> None:
        with patch(
            "crackerjack.core.workflow_orchestrator.version", return_value="1.0.0"
        ):
            version = orchestrator._get_version()
            assert version == "1.0.0"

    def test_get_version_fallback(self, orchestrator) -> None:
        with patch(
            "crackerjack.core.workflow_orchestrator.version", side_effect=Exception()
        ):
            version = orchestrator._get_version()
            assert version == "unknown"


class TestWorkflowPipeline:
    @pytest.fixture
    def pipeline(self, console, pkg_path, session, phase_coordinator):
        return WorkflowPipeline(console, pkg_path, session, phase_coordinator)

    def test_init(
        self, pipeline, console, pkg_path, session, phase_coordinator
    ) -> None:
        assert pipeline.console == console
        assert pipeline.pkg_path == pkg_path
        assert pipeline.session == session
        assert pipeline.phases == phase_coordinator

    async def test_execute(self, pipeline, workflow_options) -> None:
        async def mock_workflow(options):
            return True

        with patch.object(
            pipeline, "run_complete_workflow", side_effect=mock_workflow
        ) as mock_process:
            result = await pipeline.run_complete_workflow(workflow_options)

            mock_process.assert_called_once_with(workflow_options)
            assert result is True

    async def test_execute_error(self, pipeline, workflow_options) -> None:
        with patch.object(
            pipeline.phases, "run_cleaning_phase", side_effect=Exception("Test error")
        ):
            result = await pipeline.run_complete_workflow(workflow_options)

            assert result is False


class TestSessionCoordinator:
    def test_init(self, session, console, pkg_path) -> None:
        assert session.console == console
        assert session.pkg_path == pkg_path
        assert session.session_id is not None
        assert session.start_time is not None

    def test_start_session(self, session) -> None:
        session.start_session("test_task")

        assert session.session_id is not None

    def test_end_session(self, session) -> None:
        session.start_session("test_task")
        session.end_session(success=True)

        assert hasattr(session, "end_time")

    def test_track_task(self, session) -> None:
        session.start_session("test_task")

        task_id = session.track_task("test_task", "Test Task")

        assert task_id is not None
        assert task_id in session.tasks

    def test_update_task(self, session) -> None:
        session.start_session("test_task")
        task_id = session.track_task("test_task", "Test Task")

        session.update_task(task_id, "completed", details="Task completed")

        task = session.tasks[task_id]
        assert task.status == "completed"
        assert task.details == "Task completed"

    def test_get_summary(self, session) -> None:
        session.start_session("test_task")
        session.track_task("task1", "Task 1")
        session.track_task("task2", "Test 2")
        session.end_session(success=True)

        summary = session.get_summary()

        assert "session_id" in summary
        assert "duration" in summary
        assert "tasks_count" in summary
        assert summary["tasks_count"] == 2


class TestPhaseCoordinator:
    def test_init(self, phase_coordinator, console, pkg_path, session) -> None:
        assert phase_coordinator.console == console
        assert phase_coordinator.pkg_path == pkg_path
        assert phase_coordinator.session == session

    def test_run_cleaning_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.clean = True

        with patch.object(phase_coordinator.session, "track_task"):
            with patch.object(phase_coordinator.session, "complete_task"):
                with patch.object(
                    phase_coordinator, "_execute_cleaning_process", return_value=True
                ):
                    result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True

    def test_run_config_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.no_config_updates = False

        with patch.object(
            phase_coordinator.config_service,
            "update_precommit_config",
            return_value=True,
        ):
            with patch.object(
                phase_coordinator.config_service,
                "update_pyproject_config",
                return_value=True,
            ):
                with patch.object(phase_coordinator.session, "track_task"):
                    with patch.object(phase_coordinator.session, "complete_task"):
                        result = phase_coordinator.run_configuration_phase(mock_options)

        assert result is True

    def test_run_hooks_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.skip_hooks = False

        with patch.object(phase_coordinator, "run_fast_hooks_only", return_value=True):
            with patch.object(
                phase_coordinator, "run_comprehensive_hooks_only", return_value=True
            ):
                with patch.object(
                    phase_coordinator.config_service,
                    "get_temp_config_path",
                    return_value=None,
                ):
                    result = phase_coordinator.run_hooks_phase(mock_options)

        assert result is True

    def test_run_testing_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.test = True
        mock_options.__format__ = Mock(return_value="test_options")

        with patch.object(
            phase_coordinator.test_manager,
            "validate_test_environment",
            return_value=True,
        ):
            with patch.object(
                phase_coordinator.test_manager, "run_tests", return_value=True
            ):
                with patch.object(
                    phase_coordinator.test_manager,
                    "get_coverage",
                    return_value={"total_coverage": 85.0},
                ):
                    with patch.object(phase_coordinator.session, "track_task"):
                        with patch.object(phase_coordinator.session, "complete_task"):
                            result = phase_coordinator.run_testing_phase(mock_options)

        assert result is True

    def test_run_publishing_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.publish = "patch"

        with patch.object(
            phase_coordinator.publish_manager,
            "bump_version",
            return_value=True,
        ):
            with patch.object(
                phase_coordinator.publish_manager,
                "publish",
                return_value=True,
            ):
                with patch.object(phase_coordinator.session, "track_task"):
                    with patch.object(phase_coordinator.session, "complete_task"):
                        result = phase_coordinator.run_publishing_phase(mock_options)

        assert result is True

    def test_run_commit_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.commit = True
        mock_options.interactive = False

        with patch.object(
            phase_coordinator.git_service,
            "get_changed_files",
            return_value=["file1.py"],
        ):
            with patch.object(
                phase_coordinator.git_service,
                "get_commit_message_suggestions",
                return_value=["Update project files"],
            ):
                with patch.object(
                    phase_coordinator.git_service, "add_files", return_value=True
                ):
                    with patch.object(
                        phase_coordinator.git_service, "commit", return_value=True
                    ):
                        with patch.object(
                            phase_coordinator.git_service, "push", return_value=True
                        ):
                            with patch.object(phase_coordinator.session, "track_task"):
                                with patch.object(
                                    phase_coordinator.session, "complete_task"
                                ):
                                    result = phase_coordinator.run_commit_phase(
                                        mock_options
                                    )

        assert result is True


class TestDependencyContainer:
    @pytest.fixture
    def container(self):
        return DependencyContainer()

    def test_init(self, container) -> None:
        assert container._services == {}
        assert container._singletons == {}

    def test_register_singleton(self, container) -> None:
        mock_service = Mock()
        container.register_singleton(FileSystemInterface, mock_service)

        retrieved = container.get(FileSystemInterface)
        assert retrieved is mock_service

    def test_register_transient(self, container) -> None:
        mock_factory = Mock(return_value="test_service")
        container.register_transient(FileSystemInterface, mock_factory)

        retrieved = container.get(FileSystemInterface)
        assert retrieved == "test_service"
        mock_factory.assert_called_once()

    def test_service_not_found(self, container) -> None:
        with pytest.raises(
            ValueError, match="Service FileSystemInterface not registered"
        ):
            container.get(FileSystemInterface)
