"""Strategic test coverage for interactive.py - Interactive CLI components."""

from rich.console import Console

from crackerjack.errors import CrackerjackError, ErrorCode
from crackerjack.interactive import (
    InteractiveCLI,
    Task,
    TaskDefinition,
    TaskStatus,
    WorkflowBuilder,
    WorkflowManager,
    WorkflowOptions,
    launch_interactive_cli,
)


class TestTaskDefinition:
    """Test TaskDefinition class functionality."""

    def test_task_definition_creation(self) -> None:
        task_def = TaskDefinition("test_id", "Test Task", "Test Description", ["dep1"])
        assert task_def.id == "test_id"
        assert task_def.name == "Test Task"
        assert task_def.description == "Test Description"
        assert task_def.dependencies == ["dep1"]
        assert not task_def.optional
        assert task_def.estimated_duration == 0.0

    def test_task_definition_no_dependencies(self) -> None:
        task_def = TaskDefinition("test_id", "Test Task", "Test Description", [])
        assert task_def.dependencies == []


class TestTask:
    """Test Task class functionality."""

    def test_task_initialization(self) -> None:
        task_def = TaskDefinition("test_task", "Test Task", "Test Description", [])
        task = Task(task_def)
        assert task.name == "Test Task"
        assert task.description == "Test Description"
        assert task.dependencies == []
        assert task.status == TaskStatus.PENDING
        assert task.start_time is None
        assert task.end_time is None
        assert task.error is None

    def test_task_lifecycle(self) -> None:
        task_def = TaskDefinition("test", "Test", "Test Description", [])
        task = Task(task_def)

        # Test start
        task.start()
        assert task.status == TaskStatus.RUNNING
        assert task.start_time is not None

        # Test completion
        task.complete()
        assert task.status == TaskStatus.SUCCESS
        assert task.end_time is not None

        # Test duration
        assert task.duration is not None
        assert task.duration > 0

    def test_task_failure(self) -> None:
        task_def = TaskDefinition("test", "Test", "Test Description", [])
        task = Task(task_def)
        task.start()

        error = CrackerjackError(
            message="Test error",
            error_code=ErrorCode.UNEXPECTED_ERROR,
            details="Test details",
        )
        task.fail(error)
        assert task.status == TaskStatus.FAILED
        assert task.error == error

    def test_task_skip(self) -> None:
        task_def = TaskDefinition("test", "Test", "Test Description", [])
        task = Task(task_def)
        task.skip()
        assert task.status == TaskStatus.SKIPPED

    def test_task_dependencies(self) -> None:
        task_def = TaskDefinition("test", "Test", "Test Description", ["dep1", "dep2"])
        task = Task(task_def)
        assert task.dependencies == ["dep1", "dep2"]

        # Test can_run with dependencies
        assert not task.can_run(set())  # No completed tasks
        assert task.can_run({"dep1", "dep2"})  # All dependencies completed
        assert not task.can_run({"dep1"})  # Partial dependencies


class TestWorkflowManager:
    """Test WorkflowManager class functionality."""

    def test_workflow_initialization(self) -> None:
        workflow = WorkflowManager(Console())
        assert not workflow.tasks
        assert not workflow.task_definitions

    def test_load_workflow(self) -> None:
        workflow = WorkflowManager(Console())
        task_defs = {
            "task1": TaskDefinition("task1", "Task 1", "First task", []),
            "task2": TaskDefinition("task2", "Task 2", "Second task", ["task1"]),
        }
        workflow.load_workflow(task_defs)
        assert len(workflow.tasks) == 2
        assert "task1" in workflow.tasks
        assert "task2" in workflow.tasks

    def test_get_next_task(self) -> None:
        workflow = WorkflowManager(Console())
        task_defs = {
            "task1": TaskDefinition("task1", "Task 1", "First task", []),
            "task2": TaskDefinition("task2", "Task 2", "Second task", ["task1"]),
        }
        workflow.load_workflow(task_defs)

        # First, task1 should be next (no dependencies)
        next_task = workflow.get_next_task()
        assert next_task == workflow.tasks["task1"]

        # Complete task1, now task2 should be next
        workflow.tasks["task1"].start()
        workflow.tasks["task1"].complete()
        next_task = workflow.get_next_task()
        assert next_task == workflow.tasks["task2"]

    def test_all_tasks_completed(self) -> None:
        workflow = WorkflowManager(Console())
        task_defs = {
            "task1": TaskDefinition("task1", "Task 1", "First task", []),
            "task2": TaskDefinition("task2", "Task 2", "Second task", []),
        }
        workflow.load_workflow(task_defs)

        assert not workflow.all_tasks_completed()
        workflow.tasks["task1"].start()
        workflow.tasks["task1"].complete()
        assert not workflow.all_tasks_completed()
        workflow.tasks["task2"].skip()
        assert workflow.all_tasks_completed()

    def test_set_task_executor(self) -> None:
        workflow = WorkflowManager(Console())
        task_defs = {"task1": TaskDefinition("task1", "Task 1", "First task", [])}
        workflow.load_workflow(task_defs)

        def mock_executor() -> bool:
            return True

        workflow.set_task_executor("task1", mock_executor)
        assert workflow.tasks["task1"].executor == mock_executor

    def test_run_task_without_executor(self) -> None:
        workflow = WorkflowManager(Console())
        task_defs = {
            "test": TaskDefinition("test", "Test task", "Test Description", [])
        }
        workflow.load_workflow(task_defs)
        task = workflow.tasks["test"]

        # Task without executor should be skipped
        result = workflow.run_task(task)
        assert result
        assert task.status == TaskStatus.SKIPPED


class TestWorkflowBuilder:
    """Test WorkflowBuilder class functionality."""

    def test_builder_initialization(self) -> None:
        builder = WorkflowBuilder(Console())
        assert not builder.tasks

    def test_add_task(self) -> None:
        builder = WorkflowBuilder(Console())
        builder.add_task("task1", "Task 1", "First task")
        assert "task1" in builder.tasks
        assert builder.tasks["task1"].name == "Task 1"

    def test_build_workflow(self) -> None:
        builder = WorkflowBuilder(Console())
        builder.add_task("task1", "Task 1", "First task")
        builder.add_task("task2", "Task 2", "Second task", ["task1"])

        workflow_def = builder.build()
        assert len(workflow_def) == 2
        assert "task1" in workflow_def
        assert "task2" in workflow_def


class TestWorkflowOptions:
    """Test WorkflowOptions class functionality."""

    def test_workflow_options_defaults(self) -> None:
        options = WorkflowOptions()
        assert not options.clean
        assert not options.test
        assert options.publish is None
        assert options.bump is None
        assert not options.commit
        assert not options.create_pr
        assert options.interactive
        assert not options.dry_run

    def test_workflow_options_from_args(self) -> None:
        class MockArgs:
            clean = True
            test = True
            publish = "patch"
            commit = True

        options = WorkflowOptions.from_args(MockArgs())
        assert options.clean
        assert options.test
        assert options.publish == "patch"
        assert options.commit


class TestInteractiveCLI:
    """Test InteractiveCLI class functionality."""

    def test_cli_initialization(self) -> None:
        cli = InteractiveCLI()
        assert cli.console is not None
        assert cli.workflow is not None

    def test_cli_with_console(self) -> None:
        console = Console()
        cli = InteractiveCLI(console)
        assert cli.console == console


class TestLaunchFunction:
    """Test the launch_interactive_cli function."""

    def test_launch_function_exists(self) -> None:
        assert callable(launch_interactive_cli)


class TestTaskStatus:
    """Test TaskStatus enumeration."""

    def test_task_status_values(self) -> None:
        assert TaskStatus.PENDING
        assert TaskStatus.RUNNING
        assert TaskStatus.SUCCESS
        assert TaskStatus.FAILED
        assert TaskStatus.SKIPPED


class TestIntegrationScenarios:
    """Test integration scenarios between components."""

    def test_full_workflow_scenario(self) -> None:
        # Create workflow builder
        builder = WorkflowBuilder(Console())
        builder.add_task("setup", "Setup", "Setup task")
        builder.add_task("test", "Test", "Test task", ["setup"])
        builder.add_task("deploy", "Deploy", "Deploy task", ["test"])

        # Build and load workflow
        workflow_def = builder.build()
        manager = WorkflowManager(Console())
        manager.load_workflow(workflow_def)

        # Execute workflow step by step
        next_task = manager.get_next_task()
        assert next_task.name == "Setup"
        next_task.start()
        next_task.complete()

        next_task = manager.get_next_task()
        assert next_task.name == "Test"
        next_task.start()
        next_task.complete()

        next_task = manager.get_next_task()
        assert next_task.name == "Deploy"
        next_task.start()
        next_task.complete()

        # All tasks should be completed
        assert manager.all_tasks_completed()

        # No more tasks
        assert manager.get_next_task() is None
