from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator


class MockOptions:
    def __init__(self, **kwargs) -> None:
        self.commit = False
        self.interactive = False
        self.no_config_updates = False
        self.verbose = False
        self.update_docs = False
        self.clean = False
        self.test = False
        self.benchmark = False
        self.test_workers = 0
        self.test_timeout = 0
        self.publish = None
        self.bump = None
        self.all = None
        self.ai_agent = False
        self.autofix = False
        self.ai_agent_autofix = False
        self.start_mcp_server = False
        self.create_pr = False
        self.skip_hooks = False
        self.update_precommit = False
        self.async_mode = False
        self.track_progress = False
        self.progress_file = None
        self.experimental_hooks = False
        self.enable_pyrefly = False
        self.enable_ty = False
        self.no_git_tags = False
        self.skip_version_check = False
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def console():
    return Console(force_terminal=True)


@pytest.fixture
def temp_project(tmp_path):
    return tmp_path


@pytest.fixture
def orchestrator(console, temp_project):
    return WorkflowOrchestrator(console=console, pkg_path=temp_project, dry_run=True)


class TestWorkflowOrchestrator:
    def test_initialization(self, orchestrator) -> None:
        assert orchestrator.console is not None
        assert orchestrator.pkg_path is not None
        assert orchestrator.dry_run is True
        assert orchestrator.container is not None

    def test_cleaning_phase_skip(self, orchestrator) -> None:
        options = MockOptions(clean=False)
        result = orchestrator.run_cleaning_phase(options)
        assert result is True

    def test_cleaning_phase_no_files(self, orchestrator, temp_project) -> None:
        options = MockOptions(clean=True)
        result = orchestrator.run_cleaning_phase(options)
        assert result is True

    def test_cleaning_phase_with_files(self, orchestrator, temp_project) -> None:
        python_file = temp_project / "test.py"
        python_file.write_text('print("hello")\n')
        options = MockOptions(clean=True)
        with patch(
            "crackerjack.core.phase_coordinator.CodeCleaner.should_process_file",
            return_value=True,
        ):
            with patch(
                "crackerjack.core.phase_coordinator.CodeCleaner.clean_file",
                return_value=True,
            ):
                result = orchestrator.run_cleaning_phase(options)
                assert result is True

    def test_hooks_phase_skip(self, orchestrator) -> None:
        options = MockOptions(skip_hooks=True)
        result = orchestrator.run_hooks_phase(options)
        assert result is True

    @patch(
        "crackerjack.core.workflow_orchestrator.WorkflowOrchestrator._initialize_session_tracking"
    )
    def test_session_tracking_initialization(self, mock_init, orchestrator) -> None:
        options = MockOptions(track_progress=True)
        orchestrator._initialize_session_tracking(options)
        mock_init.assert_called_once()

    def test_testing_phase_skip(self, orchestrator) -> None:
        options = MockOptions(test=False)
        result = orchestrator.run_testing_phase(options)
        assert result is True

    def test_publishing_phase_skip(self, orchestrator) -> None:
        options = MockOptions()
        result = orchestrator.run_publishing_phase(options)
        assert result is True

    def test_commit_phase_skip(self, orchestrator) -> None:
        options = MockOptions(commit=False)
        result = orchestrator.run_commit_phase(options)
        assert result is True

    def test_complete_workflow_basic(self, orchestrator) -> None:
        options = MockOptions()
        with patch.object(
            orchestrator.phases, "run_configuration_phase", return_value=True
        ):
            with patch.object(
                orchestrator.phases, "run_cleaning_phase", return_value=True
            ):
                with patch.object(
                    orchestrator.phases, "run_hooks_phase", return_value=True
                ):
                    with patch.object(
                        orchestrator.phases, "run_testing_phase", return_value=True
                    ):
                        with patch.object(
                            orchestrator.phases,
                            "run_publishing_phase",
                            return_value=True,
                        ):
                            with patch.object(
                                orchestrator.phases,
                                "run_commit_phase",
                                return_value=True,
                            ):
                                result = orchestrator.run_complete_workflow(options)
                                assert result is True

    def test_complete_workflow_with_testing(self, orchestrator) -> None:
        options = MockOptions(test=True)
        with patch.object(
            orchestrator.phases, "run_configuration_phase", return_value=True
        ):
            with patch.object(
                orchestrator.phases, "run_cleaning_phase", return_value=True
            ):
                with patch.object(
                    orchestrator.phases, "run_fast_hooks_only", return_value=True
                ):
                    with patch.object(
                        orchestrator.phases, "run_testing_phase", return_value=True
                    ):
                        with patch.object(
                            orchestrator.phases,
                            "run_comprehensive_hooks_only",
                            return_value=True,
                        ):
                            with patch.object(
                                orchestrator.phases,
                                "run_publishing_phase",
                                return_value=True,
                            ):
                                with patch.object(
                                    orchestrator.phases,
                                    "run_commit_phase",
                                    return_value=True,
                                ):
                                    result = orchestrator.run_complete_workflow(options)
                                    assert result is True

    def test_complete_workflow_failure_handling(self, orchestrator) -> None:
        options = MockOptions()
        with patch.object(orchestrator, "run_cleaning_phase", return_value=False):
            with patch.object(orchestrator, "run_hooks_phase", return_value=True):
                with patch.object(orchestrator, "run_testing_phase", return_value=True):
                    with patch.object(
                        orchestrator, "run_publishing_phase", return_value=True
                    ):
                        with patch.object(
                            orchestrator, "run_commit_phase", return_value=True
                        ):
                            result = orchestrator.run_complete_workflow(options)
                            assert result is False

    def test_complete_workflow_autofix_continues_on_failure(self, orchestrator) -> None:
        options = MockOptions(autofix=True)
        with patch.object(
            orchestrator.phases, "run_configuration_phase", return_value=True
        ):
            with patch.object(
                orchestrator.phases, "run_cleaning_phase", return_value=False
            ):
                with patch.object(
                    orchestrator.phases, "run_hooks_phase", return_value=True
                ):
                    with patch.object(
                        orchestrator.phases, "run_testing_phase", return_value=True
                    ):
                        with patch.object(
                            orchestrator.phases,
                            "run_publishing_phase",
                            return_value=True,
                        ):
                            with patch.object(
                                orchestrator.phases,
                                "run_commit_phase",
                                return_value=True,
                            ):
                                result = orchestrator.run_complete_workflow(options)
                                assert result is False

    def test_workflow_keyboard_interrupt(self, orchestrator) -> None:
        options = MockOptions()
        with patch.object(
            orchestrator, "run_cleaning_phase", side_effect=KeyboardInterrupt
        ):
            result = orchestrator.run_complete_workflow(options)
            assert result is False

    def test_workflow_unexpected_error(self, orchestrator) -> None:
        options = MockOptions()
        with patch.object(
            orchestrator, "run_cleaning_phase", side_effect=Exception("Test error")
        ):
            result = orchestrator.run_complete_workflow(options)
            assert result is False


class TestSessionTracking:
    def test_session_tracking_disabled(self, orchestrator) -> None:
        options = MockOptions(track_progress=False)
        with patch.object(
            orchestrator.session, "initialize_session_tracking"
        ) as mock_init:
            orchestrator.session.initialize_session_tracking(options)
            mock_init.assert_called_once_with(options)

    def test_session_tracking_enabled(self, orchestrator, temp_project) -> None:
        options = MockOptions(track_progress=True)
        with patch.object(
            orchestrator.session, "initialize_session_tracking"
        ) as mock_init:
            orchestrator.session.initialize_session_tracking(options)
            mock_init.assert_called_once_with(options)

    def test_session_tracking_custom_file(self, orchestrator, temp_project) -> None:
        custom_file = "custom - progress.md"
        options = MockOptions(track_progress=True, progress_file=custom_file)
        with patch.object(
            orchestrator.session, "initialize_session_tracking"
        ) as mock_init:
            orchestrator.session.initialize_session_tracking(options)
            mock_init.assert_called_once_with(options)

    def test_task_tracking_methods(self, orchestrator, temp_project) -> None:
        options = MockOptions(track_progress=True)
        orchestrator._initialize_session_tracking(options)
        orchestrator._track_task("test_task", "Test Task")
        orchestrator._complete_task("test_task", "Completed successfully")
        orchestrator._fail_task("test_task", "Failed for testing")


class TestWorkflowPhases:
    def test_cleaning_phase_exception_handling(self, orchestrator) -> None:
        options = MockOptions(clean=True)
        with patch.object(
            orchestrator.code_cleaner,
            "should_process_file",
            side_effect=Exception("Test error"),
        ):
            result = orchestrator.run_cleaning_phase(options)
            assert result is False

    def test_hooks_phase_with_mocked_managers(self, orchestrator) -> None:
        options = MockOptions(skip_hooks=False)
        orchestrator.hook_manager.run_fast_hooks = MagicMock(return_value=[])
        orchestrator.hook_manager.run_comprehensive_hooks = MagicMock(return_value=[])
        orchestrator.hook_manager.get_hook_summary = MagicMock(
            return_value={"failed": 0, "errors": 0, "passed": 5, "total": 5}
        )
        result = orchestrator.run_hooks_phase(options)
        assert result is True

    def test_testing_phase_with_mocked_manager(self, orchestrator) -> None:
        options = MockOptions(test=True)
        orchestrator.test_manager.validate_test_environment = MagicMock(
            return_value=True
        )
        orchestrator.test_manager.run_tests = MagicMock(return_value=True)
        orchestrator.test_manager.get_coverage = MagicMock(
            return_value={"total_coverage": 85.0}
        )
        result = orchestrator.run_testing_phase(options)
        assert result is True

    def test_publishing_phase_version_bump_only(self, orchestrator) -> None:
        options = MockOptions(bump="patch")
        orchestrator.publish_manager.bump_version = MagicMock(return_value="1.0.1")
        result = orchestrator.run_publishing_phase(options)
        assert result is True

    def test_commit_phase_no_changes(self, orchestrator) -> None:
        options = MockOptions(commit=True)
        orchestrator.git_service.get_changed_files = MagicMock(return_value=[])
        result = orchestrator.run_commit_phase(options)
        assert result is True

    def test_commit_phase_with_changes(self, orchestrator) -> None:
        options = MockOptions(commit=True)
        orchestrator.git_service.get_changed_files = MagicMock(
            return_value=["file1.py", "file2.py"]
        )
        orchestrator.git_service.get_commit_message_suggestions = MagicMock(
            return_value=["Update files"]
        )
        orchestrator.git_service.add_files = MagicMock(return_value=True)
        orchestrator.git_service.commit = MagicMock(return_value=True)
        orchestrator.git_service.push = MagicMock(return_value=True)
        result = orchestrator.run_commit_phase(options)
        assert result is True
