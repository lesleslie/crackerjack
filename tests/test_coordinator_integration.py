from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowPipeline,
)


class MockOptions:
    def __init__(self, **kwargs) -> None:
        self.clean = kwargs.get("clean", True)
        self.test = kwargs.get("test", False)
        self.autofix = kwargs.get("autofix", False)
        self.skip_hooks = kwargs.get("skip_hooks", False)
        self.track_progress = kwargs.get("track_progress", False)
        self.progress_file = kwargs.get("progress_file", None)
        self.no_config_updates = kwargs.get("no_config_updates", False)
        self.update_precommit = kwargs.get("update_precommit", False)
        self.interactive = kwargs.get("interactive", False)
        self.publish = kwargs.get("publish", None)
        self.all = kwargs.get("all", None)
        self.bump = kwargs.get("bump", None)
        self.commit = kwargs.get("commit", False)
        self.no_git_tags = kwargs.get("no_git_tags", False)


class TestSessionCoordinator:
    def test_initialization(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        coordinator = SessionCoordinator(console, pkg_path)
        assert coordinator.console == console
        assert coordinator.pkg_path == pkg_path
        assert coordinator.session_tracker is None
        assert hasattr(coordinator, "_cleanup_handlers")
        assert coordinator._thread_pool is None
        assert coordinator._lock_files == set()

    def test_session_tracking_disabled(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        coordinator = SessionCoordinator(console, pkg_path)
        options = MockOptions(track_progress=False)
        coordinator.initialize_session_tracking(options)
        assert coordinator.session_tracker is None

    def test_session_tracking_enabled(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        coordinator = SessionCoordinator(console, pkg_path)
        options = MockOptions(track_progress=True)
        coordinator.initialize_session_tracking(options)
        assert coordinator.session_tracker is not None
        assert coordinator.session_tracker.session_id is not None
        assert coordinator.session_tracker.start_time > 0

    def test_task_tracking_without_session(self) -> None:
        console = Console()
        coordinator = SessionCoordinator(console, Path.cwd())
        coordinator.track_task("test", "Test task")
        coordinator.complete_task("test", "Completed")
        coordinator.fail_task("test", "Failed")
        summary = coordinator.get_session_summary()
        assert summary is None

    def test_cleanup_registration(self) -> None:
        console = Console()
        coordinator = SessionCoordinator(console, Path.cwd())
        cleanup_mock = MagicMock()
        coordinator.register_cleanup(cleanup_mock)
        assert len(coordinator._cleanup_handlers) == 1
        coordinator.cleanup_resources()
        cleanup_mock.assert_called_once()

    def test_lock_file_tracking(self) -> None:
        import tempfile

        console = Console()
        coordinator = SessionCoordinator(console, Path.cwd())
        with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
            lock_path = Path(f.name)
        coordinator.track_lock_file(lock_path)
        assert lock_path in coordinator._lock_files


class TestPhaseCoordinator:
    def test_initialization(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        session = SessionCoordinator(console, pkg_path)
        filesystem = MagicMock()
        git_service = MagicMock()
        hook_manager = MagicMock()
        test_manager = MagicMock()
        publish_manager = MagicMock()
        coordinator = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
            filesystem=filesystem,
            git_service=git_service,
            hook_manager=hook_manager,
            test_manager=test_manager,
            publish_manager=publish_manager,
        )
        assert coordinator.console == console
        assert coordinator.pkg_path == pkg_path
        assert coordinator.session == session
        assert coordinator.filesystem == filesystem
        assert coordinator.git_service == git_service
        assert coordinator.hook_manager == hook_manager
        assert coordinator.test_manager == test_manager
        assert coordinator.publish_manager == publish_manager

    def test_cleaning_phase_disabled(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        session = SessionCoordinator(console, pkg_path)
        coordinator = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
            filesystem=MagicMock(),
            git_service=MagicMock(),
            hook_manager=MagicMock(),
            test_manager=MagicMock(),
            publish_manager=MagicMock(),
        )
        options = MockOptions(clean=False)
        result = coordinator.run_cleaning_phase(options)
        assert result is True

    def test_testing_phase_disabled(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        session = SessionCoordinator(console, pkg_path)
        coordinator = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
            filesystem=MagicMock(),
            git_service=MagicMock(),
            hook_manager=MagicMock(),
            test_manager=MagicMock(),
            publish_manager=MagicMock(),
        )
        options = MockOptions(test=False)
        result = coordinator.run_testing_phase(options)
        assert result is True


class TestWorkflowPipeline:
    def test_initialization(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        session = SessionCoordinator(console, pkg_path)
        phases = MagicMock()
        pipeline = WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            session=session,
            phases=phases,
        )
        assert pipeline.console == console
        assert pipeline.pkg_path == pkg_path
        assert pipeline.session == session
        assert pipeline.phases == phases

    @patch("crackerjack.core.workflow_orchestrator.time.time")
    async def test_workflow_execution_success(self, mock_time) -> None:
        mock_time.return_value = 1000.0
        console = Console()
        pkg_path = Path.cwd()
        session = MagicMock()
        phases = MagicMock()
        phases.run_configuration_phase.return_value = True
        phases.run_cleaning_phase.return_value = True
        phases.run_hooks_phase.return_value = True
        phases.run_publishing_phase.return_value = True
        phases.run_commit_phase.return_value = True
        pipeline = WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            session=session,
            phases=phases,
        )
        options = MockOptions()
        result = await pipeline.run_complete_workflow(options)
        assert result is True
        session.initialize_session_tracking.assert_called_once_with(options)
        session.track_task.assert_called_once_with(
            "workflow", "Complete crackerjack workflow"
        )
        session.finalize_session.assert_called_once()

    async def test_workflow_execution_keyboard_interrupt(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        session = MagicMock()
        phases = MagicMock()
        phases.run_configuration_phase.side_effect = KeyboardInterrupt()
        pipeline = WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            session=session,
            phases=phases,
        )
        options = MockOptions()
        result = await pipeline.run_complete_workflow(options)
        assert result is False
        session.fail_task.assert_called_once_with("workflow", "Interrupted by user")


class TestWorkflowOrchestrator:
    @patch("crackerjack.core.container.create_container")
    def test_initialization(self, mock_create) -> None:
        console = Console()
        pkg_path = Path.cwd()
        mock_container = MagicMock()
        mock_create.return_value = mock_container
        orchestrator = WorkflowOrchestrator(
            console=console,
            pkg_path=pkg_path,
            dry_run=False,
        )
        assert orchestrator.console == console
        assert orchestrator.pkg_path == pkg_path
        assert orchestrator.session is not None
        assert orchestrator.phases is not None
        assert orchestrator.pipeline is not None

    @patch("crackerjack.core.container.create_container")
    async def test_delegation_methods(self, mock_create) -> None:
        console = Console()
        pkg_path = Path.cwd()
        mock_container = MagicMock()
        mock_create.return_value = mock_container
        orchestrator = WorkflowOrchestrator(
            console=console,
            pkg_path=pkg_path,
            dry_run=False,
        )
        orchestrator.session = MagicMock()
        orchestrator.phases = MagicMock()
        orchestrator.autofix = MagicMock()
        orchestrator.pipeline = MagicMock()

        # Make the pipeline method return a coroutine
        async def mock_run_workflow(options):
            return True

        orchestrator.pipeline.run_complete_workflow = MagicMock(
            side_effect=mock_run_workflow
        )

        options = MockOptions()
        orchestrator._track_task("test", "Test task")
        orchestrator.session.track_task.assert_called_once_with("test", "Test task")
        orchestrator.run_cleaning_phase(options)
        orchestrator.phases.run_cleaning_phase.assert_called_once_with(options)
        await orchestrator.run_complete_workflow(options)
        orchestrator.pipeline.run_complete_workflow.assert_called_once_with(options)


class TestCoordinatorIntegration:
    def test_session_and_phase_integration(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        session = SessionCoordinator(console, pkg_path)
        filesystem = MagicMock()
        git_service = MagicMock()
        hook_manager = MagicMock()
        test_manager = MagicMock()
        publish_manager = MagicMock()
        phases = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
            filesystem=filesystem,
            git_service=git_service,
            hook_manager=hook_manager,
            test_manager=test_manager,
            publish_manager=publish_manager,
        )
        options = MockOptions(clean=False)
        result = phases.run_cleaning_phase(options)
        assert result is True

    def test_autofix_and_phase_integration(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        session = SessionCoordinator(console, pkg_path)
        filesystem = MagicMock()
        git_service = MagicMock()
        hook_manager = MagicMock()
        test_manager = MagicMock()
        publish_manager = MagicMock()
        phases = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
            filesystem=filesystem,
            git_service=git_service,
            hook_manager=hook_manager,
            test_manager=test_manager,
            publish_manager=publish_manager,
        )

        assert phases.console == console
        assert phases.pkg_path == pkg_path

    async def test_full_pipeline_integration(self) -> None:
        console = Console()
        pkg_path = Path.cwd()
        session = SessionCoordinator(console, pkg_path)
        filesystem = MagicMock()
        git_service = MagicMock()
        hook_manager = MagicMock()
        test_manager = MagicMock()
        publish_manager = MagicMock()
        phases = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
            filesystem=filesystem,
            git_service=git_service,
            hook_manager=hook_manager,
            test_manager=test_manager,
            publish_manager=publish_manager,
        )
        pipeline = WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            session=session,
            phases=phases,
        )
        phases.run_configuration_phase = MagicMock(return_value=True)
        phases.run_cleaning_phase = MagicMock(return_value=True)
        phases.run_hooks_phase = MagicMock(return_value=True)
        phases.run_publishing_phase = MagicMock(return_value=True)
        phases.run_commit_phase = MagicMock(return_value=True)
        options = MockOptions()
        with patch("time.time", return_value=1000.0):
            result = await pipeline.run_complete_workflow(options)
        assert result is True
        phases.run_configuration_phase.assert_called_once_with(options)
        phases.run_cleaning_phase.assert_called_once_with(options)
        phases.run_hooks_phase.assert_called_once_with(options)
        phases.run_publishing_phase.assert_called_once_with(options)
        phases.run_commit_phase.assert_called_once_with(options)


if __name__ == "__main__":
    pytest.main([__file__, " - v"])
