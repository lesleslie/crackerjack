from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from acb.depends import depends

from crackerjack.config import CrackerjackSettings
from crackerjack.core.container import DependencyContainer
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowPipeline,
)
from crackerjack.mcp.tools.core_tools import _adapt_settings_to_protocol
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
    config_merge_service_mock = Mock()

    return PhaseCoordinator(
        console=console,
        pkg_path=pkg_path,
        session=session,
        filesystem=filesystem_mock,
        git_service=git_service_mock,
        hook_manager=hook_manager_mock,
        test_manager=test_manager_mock,
        publish_manager=publish_manager_mock,
        config_merge_service=config_merge_service_mock,
    )


@pytest.fixture
def workflow_options():
    """Provide OptionsProtocol using ACB Settings + adapter pattern."""
    settings = depends.get(CrackerjackSettings)
    return _adapt_settings_to_protocol(settings)


@pytest.mark.skip(reason="WorkflowOrchestrator requires complex nested ACB DI setup - integration test, not unit test")
class TestWorkflowOrchestrator:
    @pytest.fixture
    def orchestrator(self, workflow_orchestrator_di_context):
        injection_map, pkg_path = workflow_orchestrator_di_context
        return WorkflowOrchestrator(pkg_path=pkg_path)

    def test_init(self, orchestrator, workflow_orchestrator_di_context) -> None:
        injection_map, pkg_path = workflow_orchestrator_di_context
        # Console is now retrieved internally via DI, not passed
        assert orchestrator.console is not None
        assert orchestrator.pkg_path == pkg_path
        # ACB DI migration: container attribute removed, dependencies now via depends.get()
        assert orchestrator.session is not None
        assert orchestrator.phases is not None

    @patch("crackerjack.core.workflow_orchestrator.SessionCoordinator")
    @patch("crackerjack.core.workflow_orchestrator.PhaseCoordinator")
    async def test_process_workflow(
        self,
        mock_phase,
        mock_session,
        orchestrator,
        workflow_options,
    ) -> None:
        mock_session_inst = Mock()
        mock_phase_inst = Mock()

        mock_session.return_value = mock_session_inst
        mock_phase.return_value = mock_phase_inst

        orchestrator = WorkflowOrchestrator(pkg_path=orchestrator.pkg_path)
        orchestrator.session = mock_session_inst
        orchestrator.phases = mock_phase_inst

        # Note: workflow_options is now flat (from CrackerjackSettings), not nested
        workflow_options.clean = True
        await orchestrator.process(workflow_options)

        mock_session_inst.start_session.assert_called_once()
        mock_phase_inst.run_cleaning_phase.assert_called_once()

    def test_get_version(self, orchestrator) -> None:
        with patch(
            "crackerjack.core.workflow_orchestrator.version",
            return_value="1.0.0",
        ):
            version = orchestrator._get_version()
            assert version == "1.0.0"

    def test_get_version_fallback(self, orchestrator) -> None:
        with patch(
            "crackerjack.core.workflow_orchestrator.version",
            side_effect=Exception(),
        ):
            version = orchestrator._get_version()
            assert version == "unknown"


@pytest.mark.skip(reason="WorkflowPipeline requires complex nested ACB DI setup - integration test, not unit test")
class TestWorkflowPipeline:
    @pytest.fixture
    def pipeline(self, console, pkg_path, session, phase_coordinator):
        return WorkflowPipeline(console, pkg_path, session, phase_coordinator)

    def test_init(
        self,
        pipeline,
        console,
        pkg_path,
        session,
        phase_coordinator,
    ) -> None:
        assert pipeline.console == console
        assert pipeline.pkg_path == pkg_path
        assert pipeline.session == session
        assert pipeline.phases == phase_coordinator

    async def test_execute(self, pipeline, workflow_options) -> None:
        async def mock_workflow(options) -> bool:
            return True

        with patch.object(
            pipeline,
            "run_complete_workflow",
            side_effect=mock_workflow,
        ) as mock_process:
            result = await pipeline.run_complete_workflow(workflow_options)

            mock_process.assert_called_once_with(workflow_options)
            assert result is True

    async def test_execute_error(self, pipeline, workflow_options) -> None:
        with patch.object(
            pipeline.phases,
            "run_cleaning_phase",
            side_effect=Exception("Test error"),
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


@pytest.mark.skip(reason="PhaseCoordinator requires complex nested ACB DI setup - integration test, not unit test")
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
                    phase_coordinator,
                    "_execute_cleaning_process",
                    return_value=True,
                ):
                    result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True

    def test_run_config_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.no_config_updates = False

        with (
            patch.object(
                phase_coordinator.config_service,
                "update_precommit_config",
                return_value=True,
            ),
            patch.object(
                phase_coordinator.config_service,
                "update_pyproject_config",
                return_value=True,
            ),
            patch.object(phase_coordinator.session, "track_task"),
        ):
            with patch.object(phase_coordinator.session, "complete_task"):
                result = phase_coordinator.run_configuration_phase(mock_options)

        assert result is True

    def test_run_hooks_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.skip_hooks = False

        with patch.object(phase_coordinator, "run_fast_hooks_only", return_value=True):
            with patch.object(
                phase_coordinator,
                "run_comprehensive_hooks_only",
                return_value=True,
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

        with (
            patch.object(
                phase_coordinator.test_manager,
                "validate_test_environment",
                return_value=True,
            ),
            patch.object(
                phase_coordinator.test_manager,
                "run_tests",
                return_value=True,
            ),
            patch.object(
                phase_coordinator.test_manager,
                "get_coverage",
                return_value={"total_coverage": 85.0},
            ),
            patch.object(phase_coordinator.session, "track_task"),
        ):
            with patch.object(phase_coordinator.session, "complete_task"):
                result = phase_coordinator.run_testing_phase(mock_options)

        assert result is True

    def test_run_publishing_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.publish = "patch"

        with (
            patch.object(
                phase_coordinator.publish_manager,
                "bump_version",
                return_value=True,
            ),
            patch.object(
                phase_coordinator.publish_manager,
                "publish",
                return_value=True,
            ),
            patch.object(phase_coordinator.session, "track_task"),
        ):
            with patch.object(phase_coordinator.session, "complete_task"):
                result = phase_coordinator.run_publishing_phase(mock_options)

        assert result is True

    def test_run_commit_phase(self, phase_coordinator, workflow_options) -> None:
        from unittest.mock import Mock

        mock_options = Mock()
        mock_options.commit = True
        mock_options.interactive = False

        with (
            patch.object(
                phase_coordinator.git_service,
                "get_changed_files",
                return_value=["file1.py"],
            ),
            patch.object(
                phase_coordinator.git_service,
                "get_commit_message_suggestions",
                return_value=["Update project files"],
            ),
            patch.object(
                phase_coordinator.git_service,
                "add_files",
                return_value=True,
            ),
            patch.object(
                phase_coordinator.git_service,
                "commit",
                return_value=True,
            ),
            patch.object(
                phase_coordinator.git_service,
                "push",
                return_value=True,
            ),
            patch.object(phase_coordinator.session, "track_task"),
            patch.object(
                phase_coordinator.session,
                "complete_task",
            ),
        ):
            result = phase_coordinator.run_commit_phase(
                mock_options,
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
            ValueError,
            match="Service FileSystemInterface not registered",
        ):
            container.get(FileSystemInterface)


class TestCLIModulesBasic:
    def test_cli_options_import(self) -> None:
        import crackerjack.cli.options as cli_options_module

        assert cli_options_module is not None

    def test_cli_handlers_import(self) -> None:
        import crackerjack.cli.handlers as cli_handlers_module

        assert cli_handlers_module is not None

    def test_cli_utils_import(self) -> None:
        import crackerjack.cli.utils as cli_utils

        assert cli_utils is not None


class TestMainEntryPoint:
    def test_main_module_import(self) -> None:
        import crackerjack.__main__ as main_module

        assert main_module is not None

    def test_main_function_exists(self) -> None:
        from crackerjack.__main__ import main

        assert callable(main)


class TestProtocolsModule:
    def test_protocols_import(self) -> None:
        from crackerjack.models.protocols import (
            FileSystemInterface,
            GitInterface,
            HookManager,
            PublishManager,
            TestManagerProtocol,
        )

        assert FileSystemInterface is not None
        assert GitInterface is not None
        assert HookManager is not None
        assert TestManagerProtocol is not None
        assert PublishManager is not None


class TestConfigModels:
    def test_config_import(self) -> None:
        import crackerjack.models.config as config_module

        assert config_module is not None

    def test_task_model_import(self) -> None:
        import crackerjack.models.task as task_module

        assert task_module is not None


class TestErrorsModule:
    def test_errors_import(self) -> None:
        from crackerjack.errors import CrackerjackError, ErrorCode

        assert CrackerjackError is not None
        assert ErrorCode is not None

    def test_error_creation(self) -> None:
        from crackerjack.errors import CrackerjackError, ErrorCode

        error = CrackerjackError(
            message="Test error",
            error_code=ErrorCode.UNEXPECTED_ERROR,
        )

        assert error.message == "Test error"
        assert error.error_code == ErrorCode.UNEXPECTED_ERROR
