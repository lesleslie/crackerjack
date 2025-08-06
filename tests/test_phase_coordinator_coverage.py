import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.errors import CrackerjackError, ErrorCode
from crackerjack.models.config import WorkflowOptions


class TestPhaseCoordinatorCore:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Console(),
            "pkg_path": Path(" / tmp"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        return PhaseCoordinator(**mock_dependencies)

    @pytest.fixture
    def workflow_options(self):
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True
        options.publishing.publish = "patch"
        options.git.commit = True
        return options

    def test_initialization(self, phase_coordinator, mock_dependencies) -> None:
        assert phase_coordinator.console == mock_dependencies["console"]
        assert phase_coordinator.pkg_path == mock_dependencies["pkg_path"]
        assert phase_coordinator.session == mock_dependencies["session"]
        assert phase_coordinator.filesystem == mock_dependencies["filesystem"]
        assert phase_coordinator.git_service == mock_dependencies["git_service"]
        assert phase_coordinator.hook_manager == mock_dependencies["hook_manager"]
        assert phase_coordinator.test_manager == mock_dependencies["test_manager"]
        assert phase_coordinator.publish_manager == mock_dependencies["publish_manager"]

    def test_run_configuration_phase_success(
        self, phase_coordinator, workflow_options
    ) -> None:
        result = phase_coordinator.run_configuration_phase(workflow_options)
        assert result is True

    def test_run_configuration_phase_with_error(
        self, phase_coordinator, workflow_options
    ) -> None:
        phase_coordinator.filesystem.ensure_directory.side_effect = Exception(
            "FS Error"
        )

        result = phase_coordinator.run_configuration_phase(workflow_options)
        assert result is False

    def test_run_cleaning_phase_enabled(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.clean = True

        with patch.object(
            phase_coordinator, "_execute_cleaning_process", return_value=True
        ):
            result = phase_coordinator.run_cleaning_phase(workflow_options)
            assert result is True
            phase_coordinator.session.track_task.assert_called_with(
                "cleaning", "Code cleaning"
            )

    def test_run_cleaning_phase_disabled(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.clean = False

        result = phase_coordinator.run_cleaning_phase(workflow_options)
        assert result is True

    def test_run_cleaning_phase_with_error(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.clean = True

        with patch.object(
            phase_coordinator,
            "_execute_cleaning_process",
            side_effect=Exception("Clean error"),
        ):
            result = phase_coordinator.run_cleaning_phase(workflow_options)
            assert result is False

    def test_run_hooks_phase_success(self, phase_coordinator, workflow_options) -> None:
        workflow_options.skip_hooks = False

        with patch.object(phase_coordinator, "run_fast_hooks_only", return_value=True):
            with patch.object(
                phase_coordinator, "run_comprehensive_hooks_only", return_value=True
            ):
                result = phase_coordinator.run_hooks_phase(workflow_options)
                assert result is True

    def test_run_hooks_phase_failure(self, phase_coordinator, workflow_options) -> None:
        workflow_options.skip_hooks = False

        with patch.object(phase_coordinator, "run_fast_hooks_only", return_value=False):
            result = phase_coordinator.run_hooks_phase(workflow_options)
            assert result is False

    def test_run_fast_hooks_only_success(
        self, phase_coordinator, workflow_options
    ) -> None:
        phase_coordinator.hook_manager.run_fast_hooks.return_value = True

        result = phase_coordinator.run_fast_hooks_only(workflow_options)
        assert result is True
        phase_coordinator.hook_manager.run_fast_hooks.assert_called_once()

    def test_run_fast_hooks_only_failure(
        self, phase_coordinator, workflow_options
    ) -> None:
        phase_coordinator.hook_manager.run_fast_hooks.return_value = False

        result = phase_coordinator.run_fast_hooks_only(workflow_options)
        assert result is False

    def test_run_comprehensive_hooks_only_success(
        self, phase_coordinator, workflow_options
    ) -> None:
        phase_coordinator.hook_manager.run_comprehensive_hooks.return_value = True

        result = phase_coordinator.run_comprehensive_hooks_only(workflow_options)
        assert result is True
        phase_coordinator.hook_manager.run_comprehensive_hooks.assert_called_once()

    def test_run_comprehensive_hooks_only_failure(
        self, phase_coordinator, workflow_options
    ) -> None:
        phase_coordinator.hook_manager.run_comprehensive_hooks.return_value = False

        result = phase_coordinator.run_comprehensive_hooks_only(workflow_options)
        assert result is False

    def test_run_testing_phase_enabled(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.testing.test = True
        phase_coordinator.test_manager.run_tests.return_value = True

        result = phase_coordinator.run_testing_phase(workflow_options)
        assert result is True
        phase_coordinator.test_manager.run_tests.assert_called_once()

    def test_run_testing_phase_disabled(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.testing.test = False

        result = phase_coordinator.run_testing_phase(workflow_options)
        assert result is True

    def test_run_testing_phase_failure(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.testing.test = True
        phase_coordinator.test_manager.run_tests.return_value = False

        result = phase_coordinator.run_testing_phase(workflow_options)
        assert result is False

    def test_run_publishing_phase_enabled(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.publishing.publish = "patch"
        phase_coordinator.publish_manager.run_publishing.return_value = True

        result = phase_coordinator.run_publishing_phase(workflow_options)
        assert result is True
        phase_coordinator.publish_manager.run_publishing.assert_called_once()

    def test_run_publishing_phase_disabled(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.publishing.publish = None

        result = phase_coordinator.run_publishing_phase(workflow_options)
        assert result is True

    def test_run_publishing_phase_failure(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.publishing.publish = "patch"
        phase_coordinator.publish_manager.run_publishing.return_value = False

        result = phase_coordinator.run_publishing_phase(workflow_options)
        assert result is False

    def test_run_commit_phase_enabled(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.git.commit = True
        phase_coordinator.git_service.commit_changes.return_value = True

        result = phase_coordinator.run_commit_phase(workflow_options)
        assert result is True
        phase_coordinator.git_service.commit_changes.assert_called_once()

    def test_run_commit_phase_disabled(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.git.commit = False

        result = phase_coordinator.run_commit_phase(workflow_options)
        assert result is True

    def test_run_commit_phase_failure(
        self, phase_coordinator, workflow_options
    ) -> None:
        workflow_options.git.commit = True
        phase_coordinator.git_service.commit_changes.return_value = False

        result = phase_coordinator.run_commit_phase(workflow_options)
        assert result is False


class TestPhaseCoordinatorErrorHandling:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Console(),
            "pkg_path": Path(" / tmp"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        return PhaseCoordinator(**mock_dependencies)

    def test_filesystem_error_handling(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True

        phase_coordinator.filesystem.clean_directories.side_effect = OSError(
            "Permission denied"
        )

        result = phase_coordinator.run_cleaning_phase(options)
        assert result is False
        phase_coordinator.session.fail_task.assert_called()

    def test_git_error_handling(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.git.commit = True

        phase_coordinator.git_service.commit_changes.side_effect = CrackerjackError(
            "Git failed", ErrorCode.GIT_ERROR
        )

        result = phase_coordinator.run_commit_phase(options)
        assert result is False

    def test_hook_manager_error_handling(self, phase_coordinator) -> None:
        options = WorkflowOptions()

        phase_coordinator.hook_manager.run_hooks.side_effect = Exception(
            "Hook execution failed"
        )

        result = phase_coordinator.run_hooks_phase(options)
        assert result is False

    def test_test_manager_error_handling(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.testing.test = True

        phase_coordinator.test_manager.run_tests.side_effect = CrackerjackError(
            "Tests failed", ErrorCode.TEST_EXECUTION_ERROR
        )

        result = phase_coordinator.run_testing_phase(options)
        assert result is False

    def test_publish_manager_error_handling(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.publishing.publish = "patch"

        phase_coordinator.publish_manager.run_publishing.side_effect = Exception(
            "Publish failed"
        )

        result = phase_coordinator.run_publishing_phase(options)
        assert result is False


class TestPhaseCoordinatorAdvancedOptions:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Console(),
            "pkg_path": Path(" / tmp"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        return PhaseCoordinator(**mock_dependencies)

    def test_skip_hooks_option(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.execution.skip_hooks = True

        result = phase_coordinator.run_hooks_phase(options)
        assert result is True

    def test_verbose_option(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.execution.verbose = True
        options.testing.test = True

        result = phase_coordinator.run_testing_phase(options)
        assert result is True

    def test_benchmark_option(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        options.testing.benchmark = True

        phase_coordinator.test_manager.run_tests.return_value = True

        result = phase_coordinator.run_testing_phase(options)
        assert result is True

    def test_test_timeout_option(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        options.testing.test_timeout = 120

        phase_coordinator.test_manager.run_tests.return_value = True

        result = phase_coordinator.run_testing_phase(options)
        assert result is True

    def test_test_workers_option(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        options.testing.test_workers = 4

        phase_coordinator.test_manager.run_tests.return_value = True

        result = phase_coordinator.run_testing_phase(options)
        assert result is True

    def test_with_tests_option(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.hooks.with_tests = True

        phase_coordinator.hook_manager.run_comprehensive_hooks.return_value = True

        result = phase_coordinator.run_comprehensive_hooks_only(options)
        assert result is True

    def test_custom_cleanup_config(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.cleanup = {
            "keep_debug_logs": 10,
            "keep_coverage_files": 20,
            "no_cleanup": False,
        }

        result = phase_coordinator.run_configuration_phase(options)
        assert result is True


class TestPhaseCoordinatorSessionIntegration:
    @pytest.fixture
    def mock_dependencies(self):
        session = Mock(spec=SessionCoordinator)
        session.track_task = Mock()
        session.complete_task = Mock()
        session.fail_task = Mock()
        session.get_performance_metrics = Mock(return_value={"total_time": 30.5})

        return {
            "console": Console(),
            "pkg_path": Path(" / tmp"),
            "session": session,
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        return PhaseCoordinator(**mock_dependencies)

    def test_task_tracking_in_cleaning_phase(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True

        phase_coordinator.run_cleaning_phase(options)

        phase_coordinator.session.track_task.assert_called_with(
            "cleaning", "Clean package directory"
        )
        phase_coordinator.session.complete_task.assert_called_with("cleaning")

    def test_task_tracking_in_hooks_phase(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        phase_coordinator.hook_manager.run_hooks.return_value = True

        phase_coordinator.run_hooks_phase(options)

        phase_coordinator.session.track_task.assert_called_with(
            "hooks", "Execute pre - commit hooks"
        )
        phase_coordinator.session.complete_task.assert_called_with("hooks")

    def test_task_tracking_in_testing_phase(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        phase_coordinator.test_manager.run_tests.return_value = True

        phase_coordinator.run_testing_phase(options)

        phase_coordinator.session.track_task.assert_called_with(
            "testing", "Test execution"
        )
        phase_coordinator.session.complete_task.assert_called_with("testing")

    def test_task_tracking_in_publishing_phase(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.publishing.publish = "patch"
        phase_coordinator.publish_manager.run_publishing.return_value = True

        phase_coordinator.run_publishing_phase(options)

        phase_coordinator.session.track_task.assert_called_with(
            "publishing", "Publish package"
        )
        phase_coordinator.session.complete_task.assert_called_with("publishing")

    def test_task_tracking_in_commit_phase(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.git.commit = True
        phase_coordinator.git_service.commit_changes.return_value = True

        phase_coordinator.run_commit_phase(options)

        phase_coordinator.session.track_task.assert_called_with(
            "commit", "Commit changes"
        )
        phase_coordinator.session.complete_task.assert_called_with("commit")

    def test_task_failure_tracking(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        phase_coordinator.test_manager.run_tests.return_value = False

        phase_coordinator.run_testing_phase(options)

        phase_coordinator.session.track_task.assert_called_with(
            "testing", "Test execution"
        )
        phase_coordinator.session.fail_task.assert_called_with(
            "testing", "Tests failed"
        )


class TestPhaseCoordinatorPerformance:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "console": Console(),
            "pkg_path": Path(" / tmp"),
            "session": Mock(spec=SessionCoordinator),
            "filesystem": Mock(),
            "git_service": Mock(),
            "hook_manager": Mock(),
            "test_manager": Mock(),
            "publish_manager": Mock(),
        }

    @pytest.fixture
    def phase_coordinator(self, mock_dependencies):
        return PhaseCoordinator(**mock_dependencies)

    def test_phase_execution_timing(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        phase_coordinator.test_manager.run_tests.return_value = True

        start_time = time.time()
        result = phase_coordinator.run_testing_phase(options)
        end_time = time.time()

        assert result is True
        execution_time = end_time - start_time
        assert execution_time < 0.1

    def test_multiple_phases_execution(self, phase_coordinator) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True
        options.git.commit = True

        phase_coordinator.test_manager.run_tests.return_value = True
        phase_coordinator.git_service.commit_changes.return_value = True

        start_time = time.time()

        results = []
        results.append(phase_coordinator.run_cleaning_phase(options))
        results.append(phase_coordinator.run_testing_phase(options))
        results.append(phase_coordinator.run_commit_phase(options))

        end_time = time.time()

        assert all(results)
        execution_time = end_time - start_time
        assert execution_time < 0.5
