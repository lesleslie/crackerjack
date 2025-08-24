"""Strategic test coverage for cli/interactive.py - Interactive CLI components."""

import time
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.cli.interactive import (
    InteractiveCLI,
    InteractiveTask,
    TaskStatus,
    launch_interactive_cli,
)
from crackerjack.errors import CrackerjackError, ErrorCode


class MockOptions:
    """Mock options for testing."""

    def __init__(self, **kwargs) -> None:
        self.clean = kwargs.get("clean", False)
        self.test = kwargs.get("test", False)
        self.commit = kwargs.get("commit", False)
        self.publish = kwargs.get("publish", False)
        self.all = kwargs.get("all", False)
        self.bump = kwargs.get("bump", False)
        self.verbose = kwargs.get("verbose", False)
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_task_status_enum_values(self) -> None:
        """Test that TaskStatus enum has expected values."""
        assert TaskStatus.PENDING
        assert TaskStatus.RUNNING
        assert TaskStatus.SUCCESS
        assert TaskStatus.FAILED
        assert TaskStatus.SKIPPED

    def test_task_status_enum_types(self) -> None:
        """Test that TaskStatus values are auto-generated integers."""
        assert isinstance(TaskStatus.PENDING.value, int)
        assert isinstance(TaskStatus.RUNNING.value, int)
        assert isinstance(TaskStatus.SUCCESS.value, int)
        assert isinstance(TaskStatus.FAILED.value, int)
        assert isinstance(TaskStatus.SKIPPED.value, int)

    def test_task_status_enum_uniqueness(self) -> None:
        """Test that all TaskStatus values are unique."""
        values = [status.value for status in TaskStatus]
        assert len(values) == len(set(values))


class TestInteractiveTask:
    """Test InteractiveTask class."""

    def test_task_initialization_basic(self) -> None:
        """Test basic task initialization."""
        task = InteractiveTask(
            name="test_task",
            description="Test task description",
            phase_method="test_method",
        )

        assert task.name == "test_task"
        assert task.description == "Test task description"
        assert task.phase_method == "test_method"
        assert task.dependencies == []
        assert task.status == TaskStatus.PENDING
        assert task.start_time is None
        assert task.end_time is None
        assert task.error is None

    def test_task_initialization_with_dependencies(self) -> None:
        """Test task initialization with dependencies."""
        dep1 = InteractiveTask("dep1", "Dependency 1", "dep1_method")
        dep2 = InteractiveTask("dep2", "Dependency 2", "dep2_method")

        task = InteractiveTask(
            name="main_task",
            description="Main task",
            phase_method="main_method",
            dependencies=[dep1, dep2],
        )

        assert len(task.dependencies) == 2
        assert dep1 in task.dependencies
        assert dep2 in task.dependencies

    def test_task_duration_no_start_time(self) -> None:
        """Test duration calculation when no start time is set."""
        task = InteractiveTask("test", "Test task", "test_method")

        assert task.duration is None

    def test_task_duration_with_start_time_no_end_time(self) -> None:
        """Test duration calculation with start time but no end time."""
        task = InteractiveTask("test", "Test task", "test_method")

        start_time = time.time()
        task.start_time = start_time

        # Should use current time as end time
        duration = task.duration
        assert duration is not None
        assert duration >= 0
        assert duration < 1  # Should be very small since we just set it

    def test_task_duration_with_both_times(self) -> None:
        """Test duration calculation with both start and end times."""
        task = InteractiveTask("test", "Test task", "test_method")

        task.start_time = 100.0
        task.end_time = 105.0

        assert task.duration == 5.0

    def test_task_status_updates(self) -> None:
        """Test that task status can be updated."""
        task = InteractiveTask("test", "Test task", "test_method")

        assert task.status == TaskStatus.PENDING

        task.status = TaskStatus.RUNNING
        assert task.status == TaskStatus.RUNNING

        task.status = TaskStatus.SUCCESS
        assert task.status == TaskStatus.SUCCESS

    def test_task_error_assignment(self) -> None:
        """Test that task errors can be assigned."""
        task = InteractiveTask("test", "Test task", "test_method")

        error = CrackerjackError("Test error", ErrorCode.HOOK_FAILED)
        task.error = error

        assert task.error is error

    def test_task_time_assignment(self) -> None:
        """Test that task start and end times can be assigned."""
        task = InteractiveTask("test", "Test task", "test_method")

        start_time = time.time()
        end_time = start_time + 10

        task.start_time = start_time
        task.end_time = end_time

        assert task.start_time == start_time
        assert task.end_time == end_time


class TestInteractiveCLI:
    """Test InteractiveCLI class."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock(spec=Console)

    @pytest.fixture
    def cli(self, mock_console):
        """Create InteractiveCLI instance with mocked console."""
        with patch("crackerjack.cli.interactive.Console", return_value=mock_console):
            return InteractiveCLI("1.0.0")

    def test_cli_initialization(self, cli) -> None:
        """Test CLI initialization."""
        assert cli.pkg_version == "1.0.0"
        assert cli.console is not None
        assert hasattr(cli, "orchestrator")

    def test_cli_has_required_methods(self, cli) -> None:
        """Test that CLI has required methods."""
        assert hasattr(cli, "run")
        assert callable(cli.run)
        assert hasattr(cli, "_show_welcome")
        assert callable(cli._show_welcome)
        assert hasattr(cli, "_get_user_preferences")
        assert callable(cli._get_user_preferences)

    def test_cli_run_method_exists(self, cli) -> None:
        """Test that run method exists and can be called."""
        options = MockOptions()

        # Mock the workflow orchestrator to avoid actual execution
        with patch.object(cli, "orchestrator") as mock_orchestrator:
            mock_orchestrator.run_complete_workflow.return_value = True

            # Mock the UI methods to avoid rich UI interactions
            with (
                patch.object(cli, "_show_welcome"),
                patch.object(cli, "_get_user_preferences", return_value=options),
                patch("rich.prompt.Confirm.ask", return_value=True),
            ):
                result = cli.run(options)

                # Should complete without error
                assert result is not None

    def test_show_welcome_method(self, cli) -> None:
        """Test the welcome display method."""
        # Should not raise an error when called
        cli._show_welcome()

        # Verify console.print was called
        cli.console.print.assert_called()

    def test_get_user_preferences_basic(self, cli) -> None:
        """Test basic user preferences gathering."""
        options = MockOptions(clean=True, test=False)

        with (
            patch("rich.prompt.Confirm.ask", return_value=False),
            patch("rich.prompt.Prompt.ask", return_value="patch"),
        ):
            result = cli._get_user_preferences(options)

            # Should return an options object
            assert hasattr(result, "clean")
            assert hasattr(result, "test")
            assert hasattr(result, "commit")

    def test_get_user_preferences_with_publish(self, cli) -> None:
        """Test user preferences with publish options."""
        options = MockOptions(publish="patch")

        with patch("rich.prompt.Confirm.ask", return_value=False):
            result = cli._get_user_preferences(options)

            # Should handle publish option correctly
            assert hasattr(result, "publish")

    def test_get_user_preferences_with_advanced_options(self, cli) -> None:
        """Test user preferences with advanced options."""
        options = MockOptions(verbose=False)

        # Mock user selecting advanced options
        confirm_responses = [
            False,
            False,
            False,
            True,
            True,
        ]  # clean, test, commit, advanced, verbose

        with patch("rich.prompt.Confirm.ask", side_effect=confirm_responses):
            result = cli._get_user_preferences(options)

            # Should handle advanced options
            assert hasattr(result, "verbose")


class TestLaunchInteractiveCLI:
    """Test the launch_interactive_cli function."""

    def test_launch_function_exists(self) -> None:
        """Test that the launch function exists."""
        assert callable(launch_interactive_cli)

    def test_launch_function_basic_call(self) -> None:
        """Test basic launch function call."""
        options = MockOptions()

        with patch("crackerjack.cli.interactive.InteractiveCLI") as mock_cli_class:
            mock_cli = Mock()
            mock_cli_class.return_value = mock_cli

            launch_interactive_cli("1.0.0", options)

            # Should create CLI instance with version
            mock_cli_class.assert_called_once_with("1.0.0")
            # Should call run method with options
            mock_cli.run.assert_called_once_with(options)

    def test_launch_function_with_different_version(self) -> None:
        """Test launch function with different version."""
        options = MockOptions()

        with patch("crackerjack.cli.interactive.InteractiveCLI") as mock_cli_class:
            mock_cli = Mock()
            mock_cli_class.return_value = mock_cli

            launch_interactive_cli("2.1.3", options)

            mock_cli_class.assert_called_once_with("2.1.3")


class TestInteractiveCLIIntegration:
    """Integration tests for InteractiveCLI."""

    def test_cli_components_work_together(self) -> None:
        """Test that CLI components work together without crashing."""
        MockOptions()

        with (
            patch("crackerjack.cli.interactive.Console"),
            patch("crackerjack.cli.interactive.WorkflowOrchestrator"),
            patch("rich.prompt.Confirm.ask", return_value=False),
            patch("rich.prompt.Prompt.ask", return_value="patch"),
        ):
            cli = InteractiveCLI("1.0.0")

            # Should be able to create instance
            assert cli is not None
            assert cli.pkg_version == "1.0.0"

    def test_task_dependency_structure(self) -> None:
        """Test that task dependency structure works correctly."""
        task1 = InteractiveTask("task1", "First task", "method1")
        task2 = InteractiveTask("task2", "Second task", "method2", dependencies=[task1])
        task3 = InteractiveTask(
            "task3", "Third task", "method3", dependencies=[task1, task2],
        )

        # Check dependency relationships
        assert len(task2.dependencies) == 1
        assert task1 in task2.dependencies

        assert len(task3.dependencies) == 2
        assert task1 in task3.dependencies
        assert task2 in task3.dependencies

    def test_task_status_lifecycle(self) -> None:
        """Test typical task status lifecycle."""
        task = InteractiveTask("test", "Test task", "test_method")

        # Initial state
        assert task.status == TaskStatus.PENDING
        assert task.duration is None

        # Start task
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        assert task.status == TaskStatus.RUNNING
        assert task.duration is not None

        # Complete task
        task.status = TaskStatus.SUCCESS
        task.end_time = time.time()
        assert task.status == TaskStatus.SUCCESS
        assert task.duration is not None
