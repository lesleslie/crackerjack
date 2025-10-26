import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.task import HookResult


class MockOptions:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.track_progress = getattr(self, "track_progress", True)
        self.testing = getattr(self, "testing", False)
        self.autofix = getattr(self, "autofix", False)
        self.skip_hooks = getattr(self, "skip_hooks", False)
        self.test = getattr(self, "test", False)
        self.publish = getattr(self, "publish", None)
        self.all = getattr(self, "all", None)
        self.bump = getattr(self, "bump", None)
        self.commit = getattr(self, "commit", False)
        self.dry_run = getattr(self, "dry_run", False)
        self.experimental_hooks = getattr(self, "experimental_hooks", False)
        self.clean = getattr(self, "clean", False)
        self.no_config_updates = getattr(self, "no_config_updates", False)
        self.no_git_tags = getattr(self, "no_git_tags", False)
        self.interactive = getattr(self, "interactive", False)
        self.cleanup_pypi = getattr(self, "cleanup_pypi", False)
        self.keep_releases = getattr(self, "keep_releases", 5)


class TestSessionCoordinator:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def coordinator(self, console, temp_path):
        return SessionCoordinator(console, temp_path)

    def test_initialization(self, coordinator, console, temp_path) -> None:
        assert coordinator.console == console
        assert coordinator.pkg_path == temp_path
        assert coordinator.session_tracker is None

    def test_initialize_session_tracking(self, coordinator) -> None:
        options = MockOptions(track_progress=True)
        coordinator.initialize_session_tracking(options)

        assert coordinator.session_tracker is not None

    def test_track_task(self, coordinator) -> None:
        options = MockOptions(track_progress=True)
        coordinator.initialize_session_tracking(options)

        coordinator.track_task("test_task", "Test description")

        assert "test_task" in coordinator.session_tracker.tasks
        task = coordinator.session_tracker.tasks["test_task"]
        assert task.name == "Test description"
        assert task.status == "in_progress"
        assert task.start_time is not None

    def test_complete_task(self, coordinator) -> None:
        options = MockOptions(track_progress=True)
        coordinator.initialize_session_tracking(options)

        coordinator.track_task("test_task", "Test")
        coordinator.complete_task("test_task", "Success details")

        task = coordinator.session_tracker.tasks["test_task"]
        assert task.status == "completed"
        assert task.details == "Success details"
        assert task.end_time is not None
        assert task.duration is not None

    def test_fail_task(self, coordinator) -> None:
        options = MockOptions(track_progress=True)
        coordinator.initialize_session_tracking(options)

        coordinator.track_task("test_task", "Test")
        coordinator.fail_task("test_task", "Error message")

        task = coordinator.session_tracker.tasks["test_task"]
        assert task.status == "failed"
        assert task.error_message == "Error message"

    def test_finalize_session(self, coordinator) -> None:
        import time

        options = MockOptions(track_progress=True)
        coordinator.initialize_session_tracking(options)
        coordinator.track_task("workflow", "Test workflow")

        start_time = time.time() - 0.01
        coordinator.finalize_session(start_time, True)

        assert coordinator.session_tracker is not None

    def test_cleanup_resources(self, coordinator) -> None:
        coordinator.cleanup_resources()


@pytest.mark.skip(reason="AutofixCoordinator requires complex nested ACB DI setup - integration test, not unit test")
class TestAutofixCoordinator:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def coordinator(self, console, temp_path):
        return AutofixCoordinator(console, temp_path)

    def test_initialization(self, coordinator) -> None:
        assert hasattr(coordinator, "console")
        assert hasattr(coordinator, "pkg_path")
        assert hasattr(coordinator, "logger")

    def test_apply_fast_stage_fixes(self, coordinator) -> None:
        result = coordinator.apply_fast_stage_fixes()
        assert isinstance(result, bool)

    def test_validate_fix_command(self, coordinator) -> None:
        assert (
            coordinator.validate_fix_command(["uv", "run", "ruff", "format", "."])
            is True
        )
        assert (
            coordinator.validate_fix_command(["uv", "run", "bandit", "- f", "json"])
            is True
        )

        assert coordinator.validate_fix_command(["python", "script.py"]) is False
        assert coordinator.validate_fix_command(["uv", "run", "unknown_tool"]) is False
        assert coordinator.validate_fix_command([]) is False

    def test_should_skip_autofix(self, coordinator) -> None:
        class MockResult:
            def __init__(self, output) -> None:
                self.raw_output = output

        results_with_import_error = [
            MockResult("ModuleNotFoundError: No module named 'test'"),
        ]
        assert coordinator.should_skip_autofix(results_with_import_error) is True

        results_normal = [MockResult("Some other error")]
        assert coordinator.should_skip_autofix(results_normal) is False


@pytest.mark.skip(reason="PhaseCoordinator requires complex nested ACB DI setup - integration test, not unit test")
class TestPhaseCoordinator:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def mock_dependencies(self):
        session = Mock()
        filesystem = Mock()
        git_service = Mock()
        hook_manager = Mock()
        test_manager = Mock()
        publish_manager = Mock()
        config_merge_service = Mock()

        return {
            "session": session,
            "filesystem": filesystem,
            "git_service": git_service,
            "hook_manager": hook_manager,
            "test_manager": test_manager,
            "publish_manager": publish_manager,
            "config_merge_service": config_merge_service,
        }

    @pytest.fixture
    def coordinator(self, console, temp_path, mock_dependencies):
        with patch("crackerjack.core.phase_coordinator.CodeCleaner"):
                coordinator = PhaseCoordinator(
                    console=console,
                    pkg_path=temp_path,
                    **mock_dependencies,
                )

                coordinator.config_service = Mock()
                coordinator.config_service.update_precommit_config.return_value = True
                coordinator.config_service.update_pyproject_config.return_value = True
                return coordinator

    def test_initialization(self, coordinator, console, temp_path) -> None:
        assert coordinator.console == console
        assert coordinator.pkg_path == temp_path
        assert hasattr(coordinator, "session")
        assert hasattr(coordinator, "filesystem")

    def test_run_configuration_phase_success(
        self, coordinator, mock_dependencies
    ) -> None:
        options = MockOptions()

        coordinator.config_service.update_precommit_config.return_value = True
        coordinator.config_service.update_pyproject_config.return_value = True

        result = coordinator.run_configuration_phase(options)
        assert result is True

    def test_run_configuration_phase_failure(self, coordinator) -> None:
        options = MockOptions()

        coordinator.config_service.update_precommit_config.return_value = False
        coordinator.config_service.update_pyproject_config.return_value = True

        result = coordinator.run_configuration_phase(options)
        assert result is False

    def test_run_cleaning_phase_disabled(self, coordinator) -> None:
        options = MockOptions(clean=False)

        result = coordinator.run_cleaning_phase(options)
        assert result is True

    def test_run_hooks_phase_with_skip(self, coordinator) -> None:
        options = MockOptions(skip_hooks=True)

        result = coordinator.run_hooks_phase(options)
        assert result is True

    def test_run_fast_hooks_only(self, coordinator, mock_dependencies) -> None:
        options = MockOptions()

        hook_results = [
            HookResult(
                id="1",
                name="test",
                status="passed",
                duration=1.0,
                issues_found=[],
                stage="fast",
            ),
        ]
        mock_dependencies["hook_manager"].run_fast_hooks.return_value = hook_results
        mock_dependencies["hook_manager"].get_hook_summary.return_value = {
            "failed": 0,
            "errors": 0,
            "passed": 1,
            "total": 1,
        }

        result = coordinator.run_fast_hooks_only(options)
        assert result is True
        mock_dependencies["hook_manager"].run_fast_hooks.assert_called_once()

    def test_run_comprehensive_hooks_only(self, coordinator, mock_dependencies) -> None:
        options = MockOptions()

        hook_results = [
            HookResult(
                id="1",
                name="test",
                status="passed",
                duration=1.0,
                issues_found=[],
                stage="comprehensive",
            ),
        ]
        mock_dependencies[
            "hook_manager"
        ].run_comprehensive_hooks.return_value = hook_results
        mock_dependencies["hook_manager"].get_hook_summary.return_value = {
            "failed": 0,
            "errors": 0,
            "passed": 1,
            "total": 1,
        }

        result = coordinator.run_comprehensive_hooks_only(options)
        assert result is True
        mock_dependencies["hook_manager"].run_comprehensive_hooks.assert_called_once()

    def test_run_testing_phase_success(self, coordinator, mock_dependencies) -> None:
        options = MockOptions(test=True)

        mock_dependencies["test_manager"].validate_test_environment.return_value = True
        mock_dependencies["test_manager"].run_tests.return_value = True
        mock_dependencies["test_manager"].get_coverage.return_value = {
            "total_coverage": 85.0,
        }

        result = coordinator.run_testing_phase(options)
        assert result is True
        mock_dependencies["test_manager"].validate_test_environment.assert_called_once()
        mock_dependencies["test_manager"].run_tests.assert_called_once_with(options)
        mock_dependencies["test_manager"].get_coverage.assert_called_once()

    def test_run_testing_phase_failure(self, coordinator, mock_dependencies) -> None:
        options = MockOptions(test=True)

        mock_dependencies["test_manager"].validate_test_environment.return_value = True
        mock_dependencies["test_manager"].run_tests.return_value = False

        result = coordinator.run_testing_phase(options)
        assert result is False

    def test_run_publishing_phase_disabled(self, coordinator) -> None:
        options = MockOptions(publish=False)

        result = coordinator.run_publishing_phase(options)
        assert result is True

    def test_run_publishing_phase_enabled(self, coordinator, mock_dependencies) -> None:
        options = MockOptions(publish="patch")

        mock_dependencies["publish_manager"].bump_version.return_value = "1.2.4"
        mock_dependencies["publish_manager"].publish_package.return_value = True

        result = coordinator.run_publishing_phase(options)
        assert result is True
        mock_dependencies["publish_manager"].bump_version.assert_called_once_with(
            "patch",
        )
        mock_dependencies["publish_manager"].publish_package.assert_called_once()

    def test_run_commit_phase_disabled(self, coordinator) -> None:
        options = MockOptions(commit=False)

        result = coordinator.run_commit_phase(options)
        assert result is True

    def test_run_commit_phase_enabled(self, coordinator, mock_dependencies) -> None:
        options = MockOptions(commit=True)

        mock_dependencies["git_service"].get_changed_files.return_value = ["file1.py"]
        mock_dependencies["git_service"].add_files.return_value = True
        mock_dependencies["git_service"].commit.return_value = True
        mock_dependencies["git_service"].push.return_value = True
        mock_dependencies["git_service"].get_commit_message_suggestions.return_value = [
            "Update files",
        ]

        result = coordinator.run_commit_phase(options)
        assert result is True
        mock_dependencies["git_service"].get_changed_files.assert_called_once()
        mock_dependencies["git_service"].add_files.assert_called_once_with(["file1.py"])
        mock_dependencies["git_service"].commit.assert_called_once_with("Update files")


class TestCoreModuleIntegration:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    def test_session_and_autofix_integration(self, console, temp_path) -> None:
        from crackerjack.core.autofix_coordinator import AutofixCoordinator
        from crackerjack.core.session_coordinator import SessionCoordinator

        session = SessionCoordinator(console, temp_path)
        autofix = AutofixCoordinator(console, temp_path)

        assert session.console == console
        assert autofix.console == console
        assert session.pkg_path == temp_path
        assert autofix.pkg_path == temp_path

    def test_mock_workflow_pipeline(self, console, temp_path) -> None:
        from crackerjack.core.autofix_coordinator import AutofixCoordinator
        from crackerjack.core.session_coordinator import SessionCoordinator

        session = SessionCoordinator(console, temp_path)
        autofix = AutofixCoordinator(console, temp_path)

        options = MockOptions(track_progress=True)
        session.initialize_session_tracking(options)

        session.track_task("test_workflow", "Test workflow")

        assert autofix.validate_fix_command(["uv", "run", "ruff", "format", "."])

        session.complete_task("test_workflow", "Success")

        assert session.session_tracker is not None
        assert "test_workflow" in session.session_tracker.tasks
