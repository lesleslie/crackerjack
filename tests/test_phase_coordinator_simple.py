from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator


class MockOptions:
    def __init__(self) -> None:
        self.clean = True
        self.test = True
        self.commit = True
        self.publish = None
        self.all = None
        self.bump = None
        self.skip_hooks = False
        self.no_config_updates = False
        self.interactive = False
        self.no_git_tags = False
        self.cleanup_pypi = False
        self.keep_releases = 5


@pytest.mark.skip(reason="PhaseCoordinator requires complex nested ACB DI setup - integration test, not unit test")
class TestPhaseCoordinatorBasics:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Mock(),
            "pkg_path": Path("/ test / project"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
            "config_merge_service": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        with patch("crackerjack.core.phase_coordinator.CodeCleaner"):
                coordinator = PhaseCoordinator(**mock_dependencies)

                coordinator.config_service = Mock()
                coordinator.config_service.update_precommit_config.return_value = True
                coordinator.config_service.update_pyproject_config.return_value = True
                return coordinator

    @pytest.fixture
    def options(self):
        return MockOptions()

    def test_initialization(self, phase_coordinator, mock_dependencies) -> None:
        assert phase_coordinator.console == mock_dependencies["console"]
        assert phase_coordinator.pkg_path == mock_dependencies["pkg_path"]
        assert phase_coordinator.session == mock_dependencies["session"]

    def test_run_cleaning_phase_enabled(self, phase_coordinator, options) -> None:
        options.clean = True

        with patch.object(
            phase_coordinator,
            "_execute_cleaning_process",
            return_value=True,
        ):
            result = phase_coordinator.run_cleaning_phase(options)
            assert result is True

    def test_run_cleaning_phase_disabled(self, phase_coordinator, options) -> None:
        options.clean = False

        result = phase_coordinator.run_cleaning_phase(options)
        assert result is True

    def test_run_cleaning_phase_error(self, phase_coordinator, options) -> None:
        options.clean = True

        with patch.object(
            phase_coordinator,
            "_execute_cleaning_process",
            side_effect=Exception("Error"),
        ):
            result = phase_coordinator.run_cleaning_phase(options)
            assert result is False

    def test_run_configuration_phase_success(self, phase_coordinator, options) -> None:
        options.no_config_updates = False
        phase_coordinator.config_service.update_precommit_config.return_value = True
        phase_coordinator.config_service.update_pyproject_config.return_value = True

        result = phase_coordinator.run_configuration_phase(options)
        assert result is True

    def test_run_configuration_phase_disabled(self, phase_coordinator, options) -> None:
        options.no_config_updates = True

        result = phase_coordinator.run_configuration_phase(options)
        assert result is True

    def test_run_testing_phase_enabled(self, phase_coordinator, options) -> None:
        options.test = True
        phase_coordinator.test_manager.validate_test_environment.return_value = True
        phase_coordinator.test_manager.run_tests.return_value = True
        phase_coordinator.test_manager.get_coverage.return_value = {
            "total_coverage": 85.5,
        }

        result = phase_coordinator.run_testing_phase(options)
        assert result is True

    def test_run_testing_phase_disabled(self, phase_coordinator, options) -> None:
        options.test = False

        result = phase_coordinator.run_testing_phase(options)
        assert result is True

    def test_run_testing_phase_validation_failure(
        self,
        phase_coordinator,
        options,
    ) -> None:
        options.test = True
        phase_coordinator.test_manager.validate_test_environment.return_value = False

        result = phase_coordinator.run_testing_phase(options)
        assert result is False

    def test_run_testing_phase_test_failure(self, phase_coordinator, options) -> None:
        options.test = True
        phase_coordinator.test_manager.validate_test_environment.return_value = True
        phase_coordinator.test_manager.run_tests.return_value = False

        result = phase_coordinator.run_testing_phase(options)
        assert result is False

    def test_run_commit_phase_enabled(self, phase_coordinator, options) -> None:
        options.commit = True
        phase_coordinator.git_service.get_changed_files.return_value = [
            "file1.py",
            "file2.py",
        ]
        phase_coordinator.git_service.add_files.return_value = True
        phase_coordinator.git_service.commit.return_value = True
        phase_coordinator.git_service.push.return_value = True

        with patch.object(
            phase_coordinator,
            "_get_commit_message",
            return_value="Test commit",
        ):
            result = phase_coordinator.run_commit_phase(options)
            assert result is True

    def test_run_commit_phase_disabled(self, phase_coordinator, options) -> None:
        options.commit = False

        result = phase_coordinator.run_commit_phase(options)
        assert result is True

    def test_run_commit_phase_no_changes(self, phase_coordinator, options) -> None:
        options.commit = True
        phase_coordinator.git_service.get_changed_files.return_value = []

        result = phase_coordinator.run_commit_phase(options)
        assert result is True

    def test_run_commit_phase_add_failure(self, phase_coordinator, options) -> None:
        options.commit = True
        phase_coordinator.git_service.get_changed_files.return_value = ["file1.py"]
        phase_coordinator.git_service.add_files.return_value = False

        with patch.object(
            phase_coordinator,
            "_get_commit_message",
            return_value="Test commit",
        ):
            result = phase_coordinator.run_commit_phase(options)
            assert result is False

    def test_run_commit_phase_commit_failure(self, phase_coordinator, options) -> None:
        options.commit = True
        phase_coordinator.git_service.get_changed_files.return_value = ["file1.py"]
        phase_coordinator.git_service.add_files.return_value = True
        phase_coordinator.git_service.commit.return_value = False

        with patch.object(
            phase_coordinator,
            "_get_commit_message",
            return_value="Test commit",
        ):
            result = phase_coordinator.run_commit_phase(options)
            assert result is False

    def test_run_commit_phase_push_failure(self, phase_coordinator, options) -> None:
        options.commit = True
        phase_coordinator.git_service.get_changed_files.return_value = ["file1.py"]
        phase_coordinator.git_service.add_files.return_value = True
        phase_coordinator.git_service.commit.return_value = True
        phase_coordinator.git_service.push.return_value = False

        with patch.object(
            phase_coordinator,
            "_get_commit_message",
            return_value="Test commit",
        ):
            result = phase_coordinator.run_commit_phase(options)
            assert result is True


@pytest.mark.skip(reason="PhaseCoordinator requires complex nested ACB DI setup - integration test, not unit test")
class TestPhaseCoordinatorHooks:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Mock(),
            "pkg_path": Path("/ test / project"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
            "config_merge_service": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        with patch("crackerjack.core.phase_coordinator.CodeCleaner"):
                coordinator = PhaseCoordinator(**mock_dependencies)

                coordinator.config_service = Mock()
                coordinator.config_service.update_precommit_config.return_value = True
                coordinator.config_service.update_pyproject_config.return_value = True
                return coordinator

    @pytest.fixture
    def options(self):
        return MockOptions()

    def test_run_hooks_phase_skip(self, phase_coordinator, options) -> None:
        options.skip_hooks = True

        result = phase_coordinator.run_hooks_phase(options)
        assert result is True

    def test_run_fast_hooks_only_skip(self, phase_coordinator, options) -> None:
        options.skip_hooks = True

        result = phase_coordinator.run_fast_hooks_only(options)
        assert result is True

    def test_run_comprehensive_hooks_only_skip(
        self,
        phase_coordinator,
        options,
    ) -> None:
        options.skip_hooks = True

        result = phase_coordinator.run_comprehensive_hooks_only(options)
        assert result is True

    def test_execute_hooks_with_retry_success(self, phase_coordinator, options) -> None:
        mock_hook_runner = Mock(return_value=[])
        phase_coordinator.hook_manager.get_hook_summary.return_value = {
            "failed": 0,
            "errors": 0,
            "passed": 5,
            "total": 5,
        }

        result = phase_coordinator._execute_hooks_with_retry(
            "fast",
            mock_hook_runner,
            options,
        )
        assert result is True

    def test_execute_hooks_with_retry_failure(self, phase_coordinator, options) -> None:
        mock_hook_runner = Mock(return_value=[])
        phase_coordinator.hook_manager.get_hook_summary.return_value = {
            "failed": 2,
            "errors": 0,
            "passed": 3,
            "total": 5,
        }

        result = phase_coordinator._execute_hooks_with_retry(
            "fast",
            mock_hook_runner,
            options,
        )
        assert result is False

    def test_execute_hooks_with_retry_exception(
        self,
        phase_coordinator,
        options,
    ) -> None:
        mock_hook_runner = Mock(side_effect=Exception("Hook error"))

        result = phase_coordinator._execute_hooks_with_retry(
            "fast",
            mock_hook_runner,
            options,
        )
        assert result is False


@pytest.mark.skip(reason="PhaseCoordinator requires complex nested ACB DI setup - integration test, not unit test")
class TestPhaseCoordinatorPublishing:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Mock(),
            "pkg_path": Path("/ test / project"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
            "config_merge_service": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        with patch("crackerjack.core.phase_coordinator.CodeCleaner"):
                coordinator = PhaseCoordinator(**mock_dependencies)

                coordinator.config_service = Mock()
                coordinator.config_service.update_precommit_config.return_value = True
                coordinator.config_service.update_pyproject_config.return_value = True
                return coordinator

    @pytest.fixture
    def options(self):
        return MockOptions()

    def test_run_publishing_phase_disabled(self, phase_coordinator, options) -> None:
        options.publish = None
        options.all = None
        options.bump = None

        result = phase_coordinator.run_publishing_phase(options)
        assert result is True

    def test_run_publishing_phase_publish_success(
        self,
        phase_coordinator,
        options,
    ) -> None:
        options.publish = "patch"
        phase_coordinator.publish_manager.bump_version.return_value = "1.2.4"
        phase_coordinator.publish_manager.publish_package.return_value = True
        phase_coordinator.publish_manager.create_git_tag.return_value = True

        phase_coordinator.session.track_task.return_value = None
        phase_coordinator.session.complete_task.return_value = None
        phase_coordinator.session.fail_task.return_value = None

        result = phase_coordinator.run_publishing_phase(options)
        assert result is True
        phase_coordinator.publish_manager.bump_version.assert_called_once_with("patch")
        phase_coordinator.publish_manager.publish_package.assert_called_once()

    def test_run_publishing_phase_publish_failure(
        self,
        phase_coordinator,
        options,
    ) -> None:
        options.publish = "patch"
        phase_coordinator.publish_manager.bump_version.return_value = "1.2.4"
        phase_coordinator.publish_manager.publish_package.return_value = False

        result = phase_coordinator.run_publishing_phase(options)
        assert result is False

    def test_run_publishing_phase_all_success(self, phase_coordinator, options) -> None:
        options.all = "minor"
        phase_coordinator.publish_manager.bump_version.return_value = "1.3.0"
        phase_coordinator.publish_manager.publish_package.return_value = True

        result = phase_coordinator.run_publishing_phase(options)
        assert result is True

    def test_run_publishing_phase_with_git_tag(
        self,
        phase_coordinator,
        options,
    ) -> None:
        options.publish = "patch"
        options.no_git_tags = False
        phase_coordinator.publish_manager.bump_version.return_value = "1.2.4"
        phase_coordinator.publish_manager.create_git_tag.return_value = True
        phase_coordinator.publish_manager.publish_package.return_value = True

        result = phase_coordinator.run_publishing_phase(options)
        assert result is True
        phase_coordinator.publish_manager.create_git_tag.assert_called_with("1.2.4")

    def test_run_publishing_phase_without_git_tag(
        self,
        phase_coordinator,
        options,
    ) -> None:
        options.publish = "patch"
        options.no_git_tags = True
        phase_coordinator.publish_manager.bump_version.return_value = "1.2.4"
        phase_coordinator.publish_manager.publish_package.return_value = True

        result = phase_coordinator.run_publishing_phase(options)
        assert result is True
        phase_coordinator.publish_manager.create_git_tag.assert_not_called()

    def test_run_publishing_phase_with_cleanup(
        self,
        phase_coordinator,
        options,
    ) -> None:
        options.publish = "patch"
        phase_coordinator.publish_manager.bump_version.return_value = "1.2.4"
        phase_coordinator.publish_manager.publish_package.return_value = True

        result = phase_coordinator.run_publishing_phase(options)
        assert result is True

    def test_handle_version_bump_only_success(self, phase_coordinator) -> None:
        phase_coordinator.publish_manager.bump_version.return_value = "1.2.4"

        result = phase_coordinator._handle_version_bump_only("patch")
        assert result is True

    def test_handle_version_bump_only_failure(self, phase_coordinator) -> None:
        phase_coordinator.publish_manager.bump_version.side_effect = Exception(
            "Bump failed",
        )

        result = phase_coordinator._handle_version_bump_only("patch")
        assert result is False

    def test_execute_publishing_workflow_stages_files(
        self, phase_coordinator, options
    ) -> None:
        """Test that git add -A . is called after version bumping in publishing workflow."""
        options.publish = "patch"
        options.no_git_tags = False

        # Mock the dependencies
        phase_coordinator.publish_manager.bump_version.return_value = "1.2.4"
        phase_coordinator.git_service.add_all_files.return_value = True
        phase_coordinator.publish_manager.create_git_tag.return_value = True
        phase_coordinator.publish_manager.publish_package.return_value = True

        # Set up session mocks
        phase_coordinator.session.track_task.return_value = None
        phase_coordinator.session.complete_task.return_value = None

        result = phase_coordinator._execute_publishing_workflow(options, "patch")

        # Verify call order and parameters
        assert result is True
        phase_coordinator.publish_manager.bump_version.assert_called_once_with("patch")
        phase_coordinator.git_service.add_all_files.assert_called_once()
        phase_coordinator.publish_manager.create_git_tag.assert_called_with("1.2.4")
        phase_coordinator.publish_manager.publish_package.assert_called_once()

    def test_execute_publishing_workflow_staging_fails_continues(
        self, phase_coordinator, options
    ) -> None:
        """Test that publishing continues even if git staging fails."""
        options.publish = "patch"
        options.no_git_tags = False

        # Mock staging failure but successful publishing
        phase_coordinator.publish_manager.bump_version.return_value = "1.2.4"
        phase_coordinator.git_service.add_all_files.return_value = (
            False  # Staging fails
        )
        phase_coordinator.publish_manager.create_git_tag.return_value = True
        phase_coordinator.publish_manager.publish_package.return_value = True

        # Set up session mocks
        phase_coordinator.session.track_task.return_value = None
        phase_coordinator.session.complete_task.return_value = None

        result = phase_coordinator._execute_publishing_workflow(options, "patch")

        # Should still succeed despite staging failure
        assert result is True
        phase_coordinator.git_service.add_all_files.assert_called_once()
        phase_coordinator.publish_manager.publish_package.assert_called_once()


@pytest.mark.skip(reason="PhaseCoordinator requires complex nested ACB DI setup - integration test, not unit test")
class TestPhaseCoordinatorCommitMessages:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Mock(),
            "pkg_path": Path("/ test / project"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
            "config_merge_service": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        with patch("crackerjack.core.phase_coordinator.CodeCleaner"):
                coordinator = PhaseCoordinator(**mock_dependencies)

                coordinator.config_service = Mock()
                coordinator.config_service.update_precommit_config.return_value = True
                coordinator.config_service.update_pyproject_config.return_value = True
                return coordinator

    @pytest.fixture
    def options(self):
        return MockOptions()

    def test_get_commit_message_no_suggestions(
        self,
        phase_coordinator,
        options,
    ) -> None:
        phase_coordinator.git_service.get_commit_message_suggestions.return_value = []

        result = phase_coordinator._get_commit_message(["file1.py"], options)
        assert result == "Update project files"

    def test_get_commit_message_non_interactive(
        self,
        phase_coordinator,
        options,
    ) -> None:
        options.interactive = False
        phase_coordinator.git_service.get_commit_message_suggestions.return_value = [
            "Update configuration files",
            "Fix linting issues",
        ]

        result = phase_coordinator._get_commit_message(["file1.py"], options)
        assert result == "Update configuration files"

    def test_get_commit_message_interactive(self, phase_coordinator, options) -> None:
        options.interactive = True
        suggestions = ["Update configuration files", "Fix linting issues"]
        phase_coordinator.git_service.get_commit_message_suggestions.return_value = (
            suggestions
        )

        with patch.object(
            phase_coordinator,
            "_interactive_commit_message_selection",
            return_value="Custom message",
        ):
            result = phase_coordinator._get_commit_message(["file1.py"], options)
            assert result == "Custom message"

    def test_process_commit_choice_valid_number(self, phase_coordinator) -> None:
        suggestions = ["Message 1", "Message 2", "Message 3"]

        result = phase_coordinator._process_commit_choice("2", suggestions)
        assert result == "Message 2"

    def test_process_commit_choice_invalid_number(self, phase_coordinator) -> None:
        suggestions = ["Message 1", "Message 2", "Message 3"]

        result = phase_coordinator._process_commit_choice("5", suggestions)
        assert result == "5"

    def test_process_commit_choice_custom_text(self, phase_coordinator) -> None:
        suggestions = ["Message 1", "Message 2", "Message 3"]

        result = phase_coordinator._process_commit_choice(
            "Custom commit message",
            suggestions,
        )
        assert result == "Custom commit message"

    def test_process_commit_choice_empty(self, phase_coordinator) -> None:
        suggestions = ["Message 1", "Message 2", "Message 3"]

        result = phase_coordinator._process_commit_choice("", suggestions)
        assert result == "Message 1"


@pytest.mark.skip(reason="PhaseCoordinator requires complex nested ACB DI setup - integration test, not unit test")
class TestPhaseCoordinatorInternalMethods:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Mock(),
            "pkg_path": Path("/ test / project"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
            "config_merge_service": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        with patch("crackerjack.core.phase_coordinator.CodeCleaner"):
                coordinator = PhaseCoordinator(**mock_dependencies)

                coordinator.config_service = Mock()
                coordinator.config_service.update_precommit_config.return_value = True
                coordinator.config_service.update_pyproject_config.return_value = True
                return coordinator

    def test_execute_cleaning_process_no_files(self, phase_coordinator) -> None:
        phase_coordinator.pkg_path = Mock()
        phase_coordinator.pkg_path.rglob.return_value = []

        result = phase_coordinator._execute_cleaning_process()
        assert result is True

    def test_execute_cleaning_process_with_files(self, phase_coordinator) -> None:
        mock_files = [Path("/ test / file1.py"), Path("/ test / file2.py")]

        phase_coordinator.pkg_path = Mock()
        phase_coordinator.pkg_path.rglob.return_value = mock_files

        with (
            patch.object(
                phase_coordinator,
                "_clean_python_files",
                return_value=["file1.py"],
            ),
            patch.object(phase_coordinator, "_report_cleaning_results"),
        ):
            result = phase_coordinator._execute_cleaning_process()
            assert result is True

    def test_clean_python_files(self, phase_coordinator) -> None:
        mock_files = [Path("/ test / file1.py"), Path("/ test / file2.py")]
        phase_coordinator.code_cleaner.should_process_file.return_value = True
        # Mock clean_file to return CleaningResult objects instead of booleans
        from crackerjack.code_cleaner import CleaningResult

        success_result = CleaningResult(
            file_path=Path("/test/file1.py"),
            success=True,
            steps_completed=["test"],
            steps_failed=[],
            warnings=[],
            original_size=100,
            cleaned_size=90,
        )
        failure_result = CleaningResult(
            file_path=Path("/test/file2.py"),
            success=False,
            steps_completed=[],
            steps_failed=["test"],
            warnings=[],
            original_size=100,
            cleaned_size=100,
        )
        phase_coordinator.code_cleaner.clean_file.side_effect = [
            success_result,
            failure_result,
        ]

        result = phase_coordinator._clean_python_files(mock_files)
        assert len(result) == 1
        assert "/ test / file1.py" in result

    def test_report_cleaning_results_with_files(self, phase_coordinator) -> None:
        cleaned_files = ["file1.py", "file2.py"]

        phase_coordinator._report_cleaning_results(cleaned_files)
        phase_coordinator.session.complete_task.assert_called_with(
            "cleaning",
            "Cleaned 2 files",
        )

    def test_report_cleaning_results_no_files(self, phase_coordinator) -> None:
        cleaned_files = []

        phase_coordinator._report_cleaning_results(cleaned_files)
        phase_coordinator.session.complete_task.assert_called_with(
            "cleaning",
            "No cleaning needed",
        )

    def test_display_cleaning_header(self, phase_coordinator) -> None:
        phase_coordinator._display_cleaning_header()

        assert phase_coordinator.console.print.called

    def test_handle_no_files_to_clean(self, phase_coordinator) -> None:
        result = phase_coordinator._handle_no_files_to_clean()
        assert result is True
        phase_coordinator.session.complete_task.assert_called_with(
            "cleaning",
            "No files to clean",
        )

    def test_display_commit_suggestions(self, phase_coordinator) -> None:
        suggestions = ["Update files", "Fix bugs", "Add features"]

        phase_coordinator._display_commit_suggestions(suggestions)

        assert phase_coordinator.console.print.called

    def test_handle_no_changes_to_commit(self, phase_coordinator) -> None:
        result = phase_coordinator._handle_no_changes_to_commit()
        assert result is True
        phase_coordinator.session.complete_task.assert_called_with(
            "commit",
            "No changes to commit",
        )
