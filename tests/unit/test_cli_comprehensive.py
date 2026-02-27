"""Comprehensive tests for CLI commands and interactive functionality."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from crackerjack.interactive import (
    InteractiveWorkflowOptions,
    Task,
    TaskDefinition,
    TaskStatus,
)

runner = CliRunner()


@pytest.fixture
def mock_console():
    """Create a mock console for testing."""
    console = MagicMock()
    console.print = MagicMock()
    return console


class TestCLICommands:
    """Test CLI command functionality."""

    def test_cli_start_command_help(self):
        """Test CLI start command help."""
        from crackerjack.cli.mcp_cli import app

        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        # Check for usage line which includes the command name
        assert "start" in result.stdout.lower()

    def test_cli_stop_command_help(self):
        """Test CLI stop command help."""
        from crackerjack.cli.mcp_cli import app

        result = runner.invoke(app, ["stop", "--help"])
        assert result.exit_code == 0
        # Check for usage line which includes the command name
        assert "stop" in result.stdout.lower()

    def test_cli_status_command_help(self):
        """Test CLI status command help."""
        from crackerjack.cli.mcp_cli import app

        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
        # Check for usage line which includes the command name
        assert "status" in result.stdout.lower()

    def test_cli_restart_command_help(self):
        """Test CLI restart command help."""
        from crackerjack.cli.mcp_cli import app

        result = runner.invoke(app, ["restart", "--help"])
        assert result.exit_code == 0
        # Check for usage line which includes the command name
        assert "restart" in result.stdout.lower()

    def test_cli_start_command_basic(self):
        """Test CLI start command basic execution."""
        from crackerjack.cli.mcp_cli import app

        # Test with --help to avoid actually starting a server
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0

    def test_cli_start_command_with_json(self):
        """Test CLI start command with JSON output flag."""
        from crackerjack.cli.mcp_cli import app

        # Test that --json option exists
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout

    def test_cli_start_command_with_force(self):
        """Test CLI start command with force flag."""
        from crackerjack.cli.mcp_cli import app

        # Test that --force option exists
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.stdout or "-f" in result.stdout


class TestInteractiveWorkflowOptions:
    """Test InteractiveWorkflowOptions functionality."""

    def test_workflow_options_default_initialization(self):
        """Test workflow options initialize with defaults."""
        options = InteractiveWorkflowOptions()
        assert options.clean is False
        assert options.test is False
        assert options.publish is None
        assert options.bump is None
        assert options.commit is False
        assert options.create_pr is False
        assert options.interactive is True
        assert options.dry_run is False

    def test_workflow_options_custom_initialization(self):
        """Test workflow options with custom values."""
        options = InteractiveWorkflowOptions(
            clean=True,
            test=True,
            publish="pypi",
            bump="minor",
            commit=True,
            create_pr=True,
            interactive=False,
            dry_run=True,
        )
        assert options.clean is True
        assert options.test is True
        assert options.publish == "pypi"
        assert options.bump == "minor"
        assert options.commit is True
        assert options.create_pr is True
        assert options.interactive is False
        assert options.dry_run is True

    def test_workflow_options_from_args(self):
        """Test creating workflow options from args object."""
        class MockArgs:
            clean = True
            test = False
            publish = "testpypi"
            bump = "patch"
            commit = True
            create_pr = False
            interactive = False
            dry_run = True

        args = MockArgs()
        options = InteractiveWorkflowOptions.from_args(args)
        assert options.clean is True
        assert options.test is False
        assert options.publish == "testpypi"
        assert options.bump == "patch"
        assert options.commit is True
        assert options.create_pr is False
        assert options.interactive is False
        assert options.dry_run is True

    def test_workflow_options_from_empty_args(self):
        """Test workflow options from args with missing attributes."""
        class EmptyArgs:
            pass

        args = EmptyArgs()
        options = InteractiveWorkflowOptions.from_args(args)
        # Should use defaults for missing attributes
        assert options.clean is False
        assert options.test is False
        assert options.publish is None
        assert options.interactive is True


class TestTaskStatus:
    """Test TaskStatus enum functionality."""

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING is not None
        assert TaskStatus.RUNNING is not None
        assert TaskStatus.SUCCESS is not None
        assert TaskStatus.FAILED is not None
        assert TaskStatus.SKIPPED is not None

    def test_task_status_comparison(self):
        """Test TaskStatus values are comparable."""
        status1 = TaskStatus.PENDING
        status2 = TaskStatus.RUNNING
        assert status1 != status2
        assert status1 == TaskStatus.PENDING


class TestTaskDefinition:
    """Test TaskDefinition functionality."""

    def test_task_definition_creation(self):
        """Test task definition creation."""
        definition = TaskDefinition(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[],
        )
        assert definition.id == "task1"
        assert definition.name == "Test Task"
        assert definition.description == "A test task"
        assert definition.dependencies == []
        assert definition.optional is False
        assert definition.estimated_duration == 0.0

    def test_task_definition_with_dependencies(self):
        """Test task definition with dependencies."""
        definition = TaskDefinition(
            id="task2",
            name="Task with deps",
            description="Task with dependencies",
            dependencies=["task1", "task0"],
        )
        assert len(definition.dependencies) == 2
        assert "task1" in definition.dependencies
        assert "task0" in definition.dependencies

    def test_task_definition_optional(self):
        """Test optional task definition."""
        definition = TaskDefinition(
            id="task3",
            name="Optional Task",
            description="An optional task",
            dependencies=[],
            optional=True,
        )
        assert definition.optional is True

    def test_task_definition_with_duration(self):
        """Test task definition with estimated duration."""
        definition = TaskDefinition(
            id="task4",
            name="Long Task",
            description="A long running task",
            dependencies=[],
            estimated_duration=120.0,
        )
        assert definition.estimated_duration == 120.0

    def test_task_definition_post_init(self):
        """Test task definition post-init processing."""
        definition = TaskDefinition(
            id="task5",
            name="Post Init Test",
            description="Test post-init",
            dependencies=None,  # Should be converted to []
        )
        assert definition.dependencies == []


class TestTask:
    """Test Task functionality."""

    def test_task_creation(self):
        """Test task creation."""
        definition = TaskDefinition(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[],
        )
        task = Task(definition=definition)
        assert task.definition == definition
        assert task.status == TaskStatus.PENDING
        assert task.executor is None
        # workflow_tasks is stored as _workflow_tasks (private attribute)
        assert task._workflow_tasks is None

    def test_task_with_executor(self):
        """Test task with executor function."""
        definition = TaskDefinition(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[],
        )
        executor = MagicMock(return_value=True)
        task = Task(definition=definition, executor=executor)
        assert task.executor == executor

    def test_task_with_workflow_tasks(self):
        """Test task with workflow tasks dict."""
        definition = TaskDefinition(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[],
        )
        workflow_tasks = {}
        task = Task(definition=definition, workflow_tasks=workflow_tasks)
        # workflow_tasks is stored as _workflow_tasks (private attribute)
        assert task._workflow_tasks == workflow_tasks

    def test_task_status_update(self):
        """Test task status can be updated."""
        definition = TaskDefinition(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[],
        )
        task = Task(definition=definition)
        assert task.status == TaskStatus.PENDING
        task.status = TaskStatus.RUNNING
        assert task.status == TaskStatus.RUNNING
        task.status = TaskStatus.SUCCESS
        assert task.status == TaskStatus.SUCCESS


class TestTaskExecution:
    """Test task execution scenarios."""

    def test_task_executor_called(self):
        """Test task executor is called when available."""
        definition = TaskDefinition(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[],
        )
        executor = MagicMock(return_value=True)
        task = Task(definition=definition, executor=executor)
        if task.executor:
            result = task.executor()
            assert result is True
            executor.assert_called_once()

    def test_task_executor_failure(self):
        """Test task executor handling failure."""
        definition = TaskDefinition(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[],
        )
        executor = MagicMock(return_value=False)
        task = Task(definition=definition, executor=executor)
        if task.executor:
            result = task.executor()
            assert result is False


class TestTaskDependencies:
    """Test task dependency handling."""

    def test_task_with_no_dependencies(self):
        """Test task with no dependencies."""
        definition = TaskDefinition(
            id="task1",
            name="Test Task",
            description="A test task",
            dependencies=[],
        )
        task = Task(definition=definition)
        assert len(task.definition.dependencies) == 0

    def test_task_with_single_dependency(self):
        """Test task with single dependency."""
        definition = TaskDefinition(
            id="task2",
            name="Test Task",
            description="A test task",
            dependencies=["task1"],
        )
        task = Task(definition=definition)
        assert len(task.definition.dependencies) == 1
        assert "task1" in task.definition.dependencies

    def test_task_with_multiple_dependencies(self):
        """Test task with multiple dependencies."""
        definition = TaskDefinition(
            id="task3",
            name="Test Task",
            description="A test task",
            dependencies=["task1", "task2", "task0"],
        )
        task = Task(definition=definition)
        assert len(task.definition.dependencies) == 3


class TestWorkflowOptionsCombinations:
    """Test various workflow option combinations."""

    def test_clean_only_workflow(self):
        """Test clean-only workflow."""
        options = InteractiveWorkflowOptions(clean=True)
        assert options.clean is True
        assert options.test is False
        assert options.publish is None

    def test_test_only_workflow(self):
        """Test test-only workflow."""
        options = InteractiveWorkflowOptions(test=True)
        assert options.test is True
        assert options.clean is False

    def test_publish_workflow(self):
        """Test publish workflow."""
        options = InteractiveWorkflowOptions(publish="pypi")
        assert options.publish == "pypi"

    def test_version_bump_workflow(self):
        """Test version bump workflow."""
        options = InteractiveWorkflowOptions(bump="major")
        assert options.bump == "major"

    def test_full_release_workflow(self):
        """Test full release workflow."""
        options = InteractiveWorkflowOptions(
            clean=True,
            test=True,
            publish="pypi",
            bump="minor",
            commit=True,
            create_pr=True,
        )
        assert options.clean is True
        assert options.test is True
        assert options.publish == "pypi"
        assert options.bump == "minor"
        assert options.commit is True
        assert options.create_pr is True

    def test_dry_run_workflow(self):
        """Test dry-run workflow."""
        options = InteractiveWorkflowOptions(
            clean=True, test=True, dry_run=True
        )
        assert options.clean is True
        assert options.test is True
        assert options.dry_run is True

    def test_non_interactive_workflow(self):
        """Test non-interactive workflow."""
        options = InteractiveWorkflowOptions(
            test=True, interactive=False
        )
        assert options.test is True
        assert options.interactive is False


class TestTaskStatusTransitions:
    """Test task status transitions."""

    def test_pending_to_running(self):
        """Test transition from PENDING to RUNNING."""
        definition = TaskDefinition(
            id="task1", name="Task", description="Test", dependencies=[]
        )
        task = Task(definition=definition)
        task.status = TaskStatus.RUNNING
        assert task.status == TaskStatus.RUNNING

    def test_running_to_success(self):
        """Test transition from RUNNING to SUCCESS."""
        definition = TaskDefinition(
            id="task1", name="Task", description="Test", dependencies=[]
        )
        task = Task(definition=definition)
        task.status = TaskStatus.RUNNING
        task.status = TaskStatus.SUCCESS
        assert task.status == TaskStatus.SUCCESS

    def test_running_to_failure(self):
        """Test transition from RUNNING to FAILED."""
        definition = TaskDefinition(
            id="task1", name="Task", description="Test", dependencies=[]
        )
        task = Task(definition=definition)
        task.status = TaskStatus.RUNNING
        task.status = TaskStatus.FAILED
        assert task.status == TaskStatus.FAILED

    def test_pending_to_skipped(self):
        """Test transition from PENDING to SKIPPED."""
        definition = TaskDefinition(
            id="task1", name="Task", description="Test", dependencies=[]
        )
        task = Task(definition=definition)
        task.status = TaskStatus.SKIPPED
        assert task.status == TaskStatus.SKIPPED


class TestCLIOutput:
    """Test CLI output handling."""

    def test_cli_output_format(self):
        """Test CLI output is formatted correctly."""
        from crackerjack.cli.mcp_cli import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert len(result.stdout) > 0

    def test_cli_error_handling(self):
        """Test CLI handles errors gracefully."""
        from crackerjack.cli.mcp_cli import app

        # Test with invalid command
        result = runner.invoke(app, ["invalid_command"])
        assert result.exit_code != 0


class TestConsoleInterface:
    """Test console interface integration."""

    def test_console_print(self, mock_console):
        """Test console print functionality."""
        mock_console.print("Test message")
        mock_console.print.assert_called_with("Test message")

    def test_console_panel_output(self, mock_console):
        """Test console panel output."""
        from rich.panel import Panel

        panel = Panel("Test Panel")
        mock_console.print(panel)
        mock_console.print.assert_called()
