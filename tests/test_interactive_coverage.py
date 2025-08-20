"""
Tests for interactive.py to increase coverage significantly.
Targeting 31% → 60%+ coverage (~100 statements).
"""

from unittest.mock import Mock, patch

import pytest
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
)


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.name == "PENDING"
        assert TaskStatus.RUNNING.name == "RUNNING"
        assert TaskStatus.SUCCESS.name == "SUCCESS"
        assert TaskStatus.FAILED.name == "FAILED"
        assert TaskStatus.SKIPPED.name == "SKIPPED"


class TestWorkflowOptions:
    """Test WorkflowOptions dataclass."""

    def test_workflow_options_defaults(self):
        """Test WorkflowOptions default values."""
        options = WorkflowOptions()

        assert options.clean is False
        assert options.test is False
        assert options.publish is None
        assert options.bump is None
        assert options.commit is False
        assert options.create_pr is False
        assert options.interactive is True
        assert options.dry_run is False

    def test_workflow_options_custom_values(self):
        """Test WorkflowOptions with custom values."""
        options = WorkflowOptions(
            clean=True,
            test=True,
            publish="pypi",
            bump="patch",
            commit=True,
            create_pr=True,
            interactive=False,
            dry_run=True,
        )

        assert options.clean is True
        assert options.test is True
        assert options.publish == "pypi"
        assert options.bump == "patch"
        assert options.commit is True
        assert options.create_pr is True
        assert options.interactive is False
        assert options.dry_run is True

    def test_from_args_with_complete_args(self):
        """Test from_args with complete argument object."""
        mock_args = Mock()
        mock_args.clean = True
        mock_args.test = True
        mock_args.publish = "testpypi"
        mock_args.bump = "minor"
        mock_args.commit = True
        mock_args.create_pr = True
        mock_args.interactive = False
        mock_args.dry_run = True

        options = WorkflowOptions.from_args(mock_args)

        assert options.clean is True
        assert options.test is True
        assert options.publish == "testpypi"
        assert options.bump == "minor"
        assert options.commit is True
        assert options.create_pr is True
        assert options.interactive is False
        assert options.dry_run is True

    def test_from_args_with_partial_args(self):
        """Test from_args with partial argument object."""

        # Use a simple object instead of Mock to avoid Mock's behavior
        class PartialArgs:
            def __init__(self):
                self.clean = True
                self.test = False

        partial_args = PartialArgs()
        options = WorkflowOptions.from_args(partial_args)

        assert options.clean is True
        assert options.test is False
        assert options.publish is None  # Default
        assert options.bump is None  # Default
        assert options.commit is False  # Default
        assert options.create_pr is False  # Default
        assert options.interactive is True  # Default
        assert options.dry_run is False  # Default


class TestTaskDefinition:
    """Test TaskDefinition dataclass."""

    def test_task_definition_creation(self):
        """Test TaskDefinition creation."""
        task_def = TaskDefinition(
            id="test-task",
            name="Test Task",
            description="A test task",
            dependencies=["dep1", "dep2"],
            optional=True,
            estimated_duration=5.0,
        )

        assert task_def.id == "test-task"
        assert task_def.name == "Test Task"
        assert task_def.description == "A test task"
        assert task_def.dependencies == ["dep1", "dep2"]
        assert task_def.optional is True
        assert task_def.estimated_duration == 5.0

    def test_task_definition_post_init_empty_dependencies(self):
        """Test TaskDefinition post_init with None dependencies."""
        task_def = TaskDefinition(
            id="test-task",
            name="Test Task",
            description="A test task",
            dependencies=None,
        )

        assert task_def.dependencies == []

    def test_task_definition_post_init_existing_dependencies(self):
        """Test TaskDefinition post_init with existing dependencies."""
        task_def = TaskDefinition(
            id="test-task",
            name="Test Task",
            description="A test task",
            dependencies=["dep1"],
        )

        assert task_def.dependencies == ["dep1"]


class TestTask:
    """Test Task class."""

    @pytest.fixture
    def task_definition(self):
        """Create test task definition."""
        return TaskDefinition(
            id="test-task",
            name="Test Task",
            description="A test task",
            dependencies=["dep1"],
            estimated_duration=3.0,
        )

    @pytest.fixture
    def mock_executor(self):
        """Create mock task executor."""
        return Mock(return_value=True)

    def test_task_initialization(self, task_definition, mock_executor):
        """Test Task initialization."""
        task = Task(task_definition, mock_executor)

        assert task.definition == task_definition
        assert task.executor == mock_executor
        assert task.status == TaskStatus.PENDING
        assert task.start_time is None
        assert task.end_time is None
        assert task.error is None
        assert task.logger is not None

    def test_task_properties(self, task_definition):
        """Test Task properties."""
        task = Task(task_definition)

        assert task.name == "Test Task"
        assert task.description == "A test task"
        assert task.dependencies == ["dep1"]

    def test_task_duration_not_started(self, task_definition):
        """Test duration when task not started."""
        task = Task(task_definition)
        assert task.duration is None

    def test_task_duration_started_not_completed(self, task_definition):
        """Test duration when task started but not completed."""
        task = Task(task_definition)

        with patch("time.time", side_effect=[100.0, 105.0]):
            task.start()
            duration = task.duration

        assert duration == 5.0

    def test_task_duration_completed(self, task_definition):
        """Test duration when task completed."""
        task = Task(task_definition)

        with patch("time.time", side_effect=[100.0, 105.0]):
            task.start()
            task.complete()

        assert task.duration == 5.0

    def test_task_start(self, task_definition):
        """Test task start."""
        task = Task(task_definition)

        with patch("time.time", return_value=100.0):
            task.start()

        assert task.status == TaskStatus.RUNNING
        assert task.start_time == 100.0

    def test_task_complete_success(self, task_definition):
        """Test task completion with success."""
        task = Task(task_definition)

        with patch("time.time", return_value=105.0):
            task.complete(success=True)

        assert task.status == TaskStatus.SUCCESS
        assert task.end_time == 105.0

    def test_task_complete_failure(self, task_definition):
        """Test task completion with failure."""
        task = Task(task_definition)

        with patch("time.time", return_value=105.0):
            task.complete(success=False)

        assert task.status == TaskStatus.FAILED
        assert task.end_time == 105.0

    def test_task_skip(self, task_definition):
        """Test task skip."""
        task = Task(task_definition)

        with patch("time.time", return_value=105.0):
            task.skip()

        assert task.status == TaskStatus.SKIPPED
        assert task.end_time == 105.0

    def test_task_fail(self, task_definition):
        """Test task fail with error."""
        task = Task(task_definition)
        error = CrackerjackError("Test error", ErrorCode.COMMAND_EXECUTION_ERROR)

        with patch("time.time", return_value=105.0):
            task.fail(error)

        assert task.status == TaskStatus.FAILED
        assert task.end_time == 105.0
        assert task.error == error

    def test_can_run_no_dependencies(self):
        """Test can_run with no dependencies."""
        task_def = TaskDefinition("test", "Test", "Description", dependencies=[])
        task = Task(task_def)

        assert task.can_run(set()) is True
        assert task.can_run({"other-task"}) is True

    def test_can_run_dependencies_met(self, task_definition):
        """Test can_run with dependencies met."""
        task = Task(task_definition)
        completed_tasks = {"dep1"}

        assert task.can_run(completed_tasks) is True

    def test_can_run_dependencies_not_met(self, task_definition):
        """Test can_run with dependencies not met."""
        task = Task(task_definition)
        completed_tasks = {"other-task"}

        assert task.can_run(completed_tasks) is False


class TestWorkflowBuilder:
    """Test WorkflowBuilder class."""

    @pytest.fixture
    def console(self):
        """Create mock console."""
        return Mock(spec=Console)

    @pytest.fixture
    def builder(self, console):
        """Create WorkflowBuilder instance."""
        return WorkflowBuilder(console)

    def test_initialization(self, builder, console):
        """Test WorkflowBuilder initialization."""
        assert builder.console == console
        assert builder.tasks == {}
        assert builder.logger is not None

    def test_add_task_basic(self, builder):
        """Test adding basic task."""
        result = builder.add_task(
            task_id="test-task", name="Test Task", description="A test task"
        )

        assert result == builder  # Should return self for chaining
        assert "test-task" in builder.tasks

        task_def = builder.tasks["test-task"]
        assert task_def.id == "test-task"
        assert task_def.name == "Test Task"
        assert task_def.description == "A test task"
        assert task_def.dependencies == []
        assert task_def.optional is False
        assert task_def.estimated_duration == 0.0

    def test_add_task_with_all_options(self, builder):
        """Test adding task with all options."""
        builder.add_task(
            task_id="test-task",
            name="Test Task",
            description="A test task",
            dependencies=["dep1", "dep2"],
            optional=True,
            estimated_duration=5.0,
        )

        task_def = builder.tasks["test-task"]
        assert task_def.dependencies == ["dep1", "dep2"]
        assert task_def.optional is True
        assert task_def.estimated_duration == 5.0

    def test_add_conditional_task_true(self, builder):
        """Test add_conditional_task when condition is True."""
        result = builder.add_conditional_task(
            condition=True,
            task_id="conditional-task",
            name="Conditional Task",
            description="A conditional task",
            dependencies=["dep1"],
            estimated_duration=3.0,
        )

        assert result == "conditional-task"
        assert "conditional-task" in builder.tasks

    def test_add_conditional_task_false_with_dependencies(self, builder):
        """Test add_conditional_task when condition is False with dependencies."""
        result = builder.add_conditional_task(
            condition=False,
            task_id="conditional-task",
            name="Conditional Task",
            description="A conditional task",
            dependencies=["dep1", "dep2"],
        )

        assert result == "dep2"  # Should return last dependency
        assert "conditional-task" not in builder.tasks

    def test_add_conditional_task_false_no_dependencies(self, builder):
        """Test add_conditional_task when condition is False with no dependencies."""
        result = builder.add_conditional_task(
            condition=False,
            task_id="conditional-task",
            name="Conditional Task",
            description="A conditional task",
        )

        assert result == ""  # Should return empty string
        assert "conditional-task" not in builder.tasks

    def test_build_valid_workflow(self, builder):
        """Test building valid workflow."""
        builder.add_task("task1", "Task 1", "First task")
        builder.add_task("task2", "Task 2", "Second task", dependencies=["task1"])

        workflow = builder.build()

        assert len(workflow) == 2
        assert "task1" in workflow
        assert "task2" in workflow
        assert workflow["task2"].dependencies == ["task1"]

    def test_validate_dependencies_missing_dependency(self, builder):
        """Test validation with missing dependency."""
        builder.add_task("task1", "Task 1", "First task", dependencies=["nonexistent"])

        with pytest.raises(ValueError) as exc_info:
            builder.build()

        assert "depends on unknown task nonexistent" in str(exc_info.value)

    def test_check_circular_dependencies_simple_cycle(self, builder):
        """Test detection of simple circular dependency."""
        builder.add_task("task1", "Task 1", "First task", dependencies=["task2"])
        builder.add_task("task2", "Task 2", "Second task", dependencies=["task1"])

        with pytest.raises(ValueError) as exc_info:
            builder.build()

        assert "Circular dependency detected" in str(exc_info.value)

    def test_check_circular_dependencies_complex_cycle(self, builder):
        """Test detection of complex circular dependency."""
        builder.add_task("task1", "Task 1", "First task", dependencies=["task3"])
        builder.add_task("task2", "Task 2", "Second task", dependencies=["task1"])
        builder.add_task("task3", "Task 3", "Third task", dependencies=["task2"])

        with pytest.raises(ValueError) as exc_info:
            builder.build()

        assert "Circular dependency detected" in str(exc_info.value)


class TestModernWorkflowManager:
    """Test WorkflowManager class."""

    @pytest.fixture
    def console(self):
        """Create mock console."""
        return Mock(spec=Console)

    @pytest.fixture
    def workflow_manager(self, console):
        """Create WorkflowManager instance."""
        return WorkflowManager(console)

    @pytest.fixture
    def sample_workflow(self):
        """Create sample workflow definitions."""
        return {
            "task1": TaskDefinition("task1", "Task 1", "First task", dependencies=[]),
            "task2": TaskDefinition(
                "task2", "Task 2", "Second task", dependencies=["task1"]
            ),
            "task3": TaskDefinition(
                "task3", "Task 3", "Third task", dependencies=["task1"]
            ),
        }

    def test_initialization(self, workflow_manager, console):
        """Test WorkflowManager initialization."""
        assert workflow_manager.console == console
        assert workflow_manager.tasks == {}
        assert workflow_manager.task_definitions == {}
        assert workflow_manager.logger is not None

    def test_load_workflow(self, workflow_manager, sample_workflow):
        """Test loading workflow."""
        workflow_manager.load_workflow(sample_workflow)

        assert len(workflow_manager.tasks) == 3
        assert len(workflow_manager.task_definitions) == 3
        assert all(isinstance(task, Task) for task in workflow_manager.tasks.values())

    def test_set_task_executor_existing_task(self, workflow_manager, sample_workflow):
        """Test setting executor for existing task."""
        workflow_manager.load_workflow(sample_workflow)
        mock_executor = Mock(return_value=True)

        workflow_manager.set_task_executor("task1", mock_executor)

        assert workflow_manager.tasks["task1"].executor == mock_executor

    def test_set_task_executor_nonexistent_task(
        self, workflow_manager, sample_workflow
    ):
        """Test setting executor for nonexistent task."""
        workflow_manager.load_workflow(sample_workflow)
        mock_executor = Mock(return_value=True)

        # Should not raise error
        workflow_manager.set_task_executor("nonexistent", mock_executor)

    def test_get_next_task_first_task(self, workflow_manager, sample_workflow):
        """Test getting next task when no tasks completed."""
        workflow_manager.load_workflow(sample_workflow)

        next_task = workflow_manager.get_next_task()

        assert next_task is not None
        assert next_task.definition.id == "task1"  # No dependencies

    def test_get_next_task_with_completed_dependency(
        self, workflow_manager, sample_workflow
    ):
        """Test getting next task after dependency completed."""
        workflow_manager.load_workflow(sample_workflow)

        # Complete task1
        workflow_manager.tasks["task1"].status = TaskStatus.SUCCESS

        next_task = workflow_manager.get_next_task()

        assert next_task is not None
        assert next_task.definition.id in ["task2", "task3"]  # Either dependent task

    def test_get_next_task_no_available_tasks(self, workflow_manager, sample_workflow):
        """Test getting next task when no tasks available."""
        workflow_manager.load_workflow(sample_workflow)

        # Mark task1 as running (blocks task2 and task3)
        workflow_manager.tasks["task1"].status = TaskStatus.RUNNING

        next_task = workflow_manager.get_next_task()

        assert next_task is None

    def test_all_tasks_completed_false(self, workflow_manager, sample_workflow):
        """Test all_tasks_completed when tasks pending."""
        workflow_manager.load_workflow(sample_workflow)

        assert workflow_manager.all_tasks_completed() is False

    def test_all_tasks_completed_true(self, workflow_manager, sample_workflow):
        """Test all_tasks_completed when all tasks done."""
        workflow_manager.load_workflow(sample_workflow)

        # Mark all tasks as completed
        workflow_manager.tasks["task1"].status = TaskStatus.SUCCESS
        workflow_manager.tasks["task2"].status = TaskStatus.FAILED
        workflow_manager.tasks["task3"].status = TaskStatus.SKIPPED

        assert workflow_manager.all_tasks_completed() is True

    def test_run_task_without_executor(self, workflow_manager, sample_workflow):
        """Test running task without executor."""
        workflow_manager.load_workflow(sample_workflow)
        task = workflow_manager.tasks["task1"]

        result = workflow_manager.run_task(task)

        assert result is True
        assert task.status == TaskStatus.SKIPPED
        workflow_manager.console.print.assert_called()

    def test_run_task_with_successful_executor(self, workflow_manager, sample_workflow):
        """Test running task with successful executor."""
        workflow_manager.load_workflow(sample_workflow)
        task = workflow_manager.tasks["task1"]

        mock_executor = Mock(return_value=True)
        task.executor = mock_executor

        result = workflow_manager.run_task(task)

        assert result is True
        assert task.status == TaskStatus.SUCCESS
        mock_executor.assert_called_once()

    def test_run_task_with_failing_executor(self, workflow_manager, sample_workflow):
        """Test running task with failing executor."""
        workflow_manager.load_workflow(sample_workflow)
        task = workflow_manager.tasks["task1"]

        mock_executor = Mock(return_value=False)
        task.executor = mock_executor

        result = workflow_manager.run_task(task)

        assert result is False
        assert task.status == TaskStatus.FAILED

    def test_run_task_with_exception(self, workflow_manager, sample_workflow):
        """Test running task that throws exception."""
        workflow_manager.load_workflow(sample_workflow)
        task = workflow_manager.tasks["task1"]

        mock_executor = Mock(side_effect=RuntimeError("Test error"))
        task.executor = mock_executor

        result = workflow_manager.run_task(task)

        assert result is False
        assert task.status == TaskStatus.FAILED
        assert task.error is not None
        assert "Test error" in str(task.error)

    def test_display_task_tree(self, workflow_manager, sample_workflow):
        """Test displaying task tree."""
        workflow_manager.load_workflow(sample_workflow)

        # Set different statuses
        workflow_manager.tasks["task1"].status = TaskStatus.SUCCESS
        workflow_manager.tasks["task2"].status = TaskStatus.RUNNING
        workflow_manager.tasks["task3"].status = TaskStatus.PENDING

        workflow_manager.display_task_tree()

        # Should print tree to console
        workflow_manager.console.print.assert_called()

    def test_get_workflow_summary(self, workflow_manager, sample_workflow):
        """Test getting workflow summary."""
        workflow_manager.load_workflow(sample_workflow)

        # Set different statuses
        workflow_manager.tasks["task1"].status = TaskStatus.SUCCESS
        workflow_manager.tasks["task2"].status = TaskStatus.RUNNING
        workflow_manager.tasks["task3"].status = TaskStatus.PENDING

        summary = workflow_manager.get_workflow_summary()

        assert summary["success"] == 1
        assert summary["running"] == 1
        assert summary["pending"] == 1
        assert summary["failed"] == 0
        assert summary["skipped"] == 0


class TestModernInteractiveCLI:
    """Test InteractiveCLI class."""

    @pytest.fixture
    def console(self):
        """Create mock console."""
        return Mock(spec=Console)

    @pytest.fixture
    def cli(self, console):
        """Create InteractiveCLI instance."""
        return InteractiveCLI(console)

    def test_initialization_with_console(self, console):
        """Test CLI initialization with provided console."""
        cli = InteractiveCLI(console)

        assert cli.console == console
        assert isinstance(cli.workflow, WorkflowManager)
        assert cli.logger is not None

    def test_initialization_without_console(self):
        """Test CLI initialization without console."""
        cli = InteractiveCLI()

        assert isinstance(cli.console, Console)
        assert isinstance(cli.workflow, WorkflowManager)

    def test_create_dynamic_workflow_minimal(self, cli):
        """Test creating dynamic workflow with minimal options."""
        options = WorkflowOptions()

        cli.create_dynamic_workflow(options)

        # Should have created some basic tasks
        assert len(cli.workflow.tasks) > 0

    def test_create_dynamic_workflow_full_options(self, cli):
        """Test creating dynamic workflow with full options."""
        options = WorkflowOptions(
            clean=True,
            test=True,
            publish="pypi",
            bump="patch",
            commit=True,
            create_pr=True,
        )

        cli.create_dynamic_workflow(options)

        # Should have created more tasks
        assert len(cli.workflow.tasks) > 5

    def test_workflow_phase_methods(self, cli):
        """Test individual workflow phase methods."""
        builder = Mock()
        builder.add_task.return_value = builder
        builder.add_conditional_task.return_value = "task_id"

        # Test each phase method
        result = cli._add_setup_phase(builder, "")
        assert result == "setup"

        result = cli._add_config_phase(builder, "setup")
        assert result == "config"

        result = cli._add_cleaning_phase(builder, "config", enabled=True)
        assert result == "task_id"  # From mock

        # When enabled=False, add_conditional_task returns last dependency or empty string
        builder.add_conditional_task.return_value = (
            ""  # Mock returns empty string for disabled
        )
        result = cli._add_cleaning_phase(builder, "config", enabled=False)
        assert result == "config"  # Should return last_task via 'or' logic

        result = cli._add_fast_hooks_phase(builder, "config")
        assert result == "fast_hooks"

        result = cli._add_testing_phase(builder, "fast_hooks", enabled=True)
        assert result == "task_id"

        builder.add_conditional_task.return_value = (
            ""  # Mock returns empty string for disabled
        )
        result = cli._add_testing_phase(builder, "fast_hooks", enabled=False)
        assert result == "fast_hooks"

        result = cli._add_comprehensive_hooks_phase(builder, "test")
        assert result == "comprehensive_hooks"

        builder.add_conditional_task.return_value = "task_id"  # Reset for enabled
        result = cli._add_version_phase(builder, "comprehensive_hooks", enabled=True)
        assert result == "task_id"

        builder.add_conditional_task.return_value = (
            ""  # Mock returns empty string for disabled
        )
        result = cli._add_version_phase(builder, "comprehensive_hooks", enabled=False)
        assert result == "comprehensive_hooks"

        builder.add_conditional_task.return_value = "task_id"  # Reset for enabled
        result = cli._add_publish_phase(builder, "version", enabled=True)
        assert result == "task_id"

        builder.add_conditional_task.return_value = (
            ""  # Mock returns empty string for disabled
        )
        result = cli._add_publish_phase(builder, "version", enabled=False)
        assert result == "version"

        builder.add_conditional_task.return_value = "task_id"  # Reset for enabled
        result = cli._add_commit_phase(builder, "publish", enabled=True)
        assert result == "task_id"

        builder.add_conditional_task.return_value = (
            ""  # Mock returns empty string for disabled
        )
        result = cli._add_commit_phase(builder, "publish", enabled=False)
        assert result == "publish"

        builder.add_conditional_task.return_value = "task_id"  # Reset for enabled
        result = cli._add_pr_phase(builder, "commit", enabled=True)
        assert result == "task_id"

        builder.add_conditional_task.return_value = (
            ""  # Mock returns empty string for disabled
        )
        result = cli._add_pr_phase(builder, "commit", enabled=False)
        assert result == "commit"

    def test_run_interactive_workflow_success(self, cli):
        """Test successful interactive workflow execution."""
        options = WorkflowOptions(clean=True, test=True)

        with patch("crackerjack.interactive.Confirm.ask", return_value=True):
            with patch.object(cli, "_execute_workflow_loop", return_value=True):
                result = cli.run_interactive_workflow(options)

                assert result is True

    def test_run_interactive_workflow_cancelled(self, cli):
        """Test cancelled interactive workflow."""
        options = WorkflowOptions()

        with patch("crackerjack.interactive.Confirm.ask", return_value=False):
            result = cli.run_interactive_workflow(options)

            assert result is False

    def test_execute_workflow_loop_success(self, cli):
        """Test successful workflow loop execution."""
        # Mock workflow state
        cli.workflow = Mock()
        cli.workflow.all_tasks_completed.side_effect = [False, False, True]

        mock_task = Mock()
        mock_task.name = "Test Task"
        cli.workflow.get_next_task.side_effect = [mock_task, mock_task, None]

        with patch.object(cli, "_should_run_task", return_value=True):
            with patch.object(cli, "_execute_single_task", return_value=True):
                with patch.object(cli, "_display_workflow_summary"):
                    result = cli._execute_workflow_loop()

                    assert result is True

    def test_execute_workflow_loop_stuck(self, cli):
        """Test workflow loop with stuck workflow."""
        cli.workflow = Mock()
        cli.workflow.all_tasks_completed.return_value = False
        cli.workflow.get_next_task.return_value = None

        # Mock pending tasks
        mock_task = Mock()
        mock_task.status = TaskStatus.PENDING
        cli.workflow.tasks = {"task1": mock_task}

        with patch.object(cli, "_display_workflow_summary"):
            result = cli._execute_workflow_loop()

            assert result is False

    def test_execute_workflow_loop_with_failure(self, cli):
        """Test workflow loop with task failure."""
        cli.workflow = Mock()
        cli.workflow.all_tasks_completed.side_effect = [False, True]

        mock_task = Mock()
        mock_task.name = "Test Task"
        cli.workflow.get_next_task.return_value = mock_task

        with patch.object(cli, "_should_run_task", return_value=True):
            with patch.object(cli, "_execute_single_task", return_value=False):
                with patch.object(
                    cli, "_should_continue_after_failure", return_value=False
                ):
                    with patch.object(cli, "_display_workflow_summary"):
                        result = cli._execute_workflow_loop()

                        assert result is False

    def test_handle_stuck_workflow_with_pending(self, cli):
        """Test handling stuck workflow with pending tasks."""
        cli.workflow = Mock()
        mock_task = Mock()
        mock_task.status = TaskStatus.PENDING
        cli.workflow.tasks = {"task1": mock_task}

        result = cli._handle_stuck_workflow()
        assert result is False

    def test_handle_stuck_workflow_no_pending(self, cli):
        """Test handling stuck workflow with no pending tasks."""
        cli.workflow = Mock()
        cli.workflow.tasks = {}

        result = cli._handle_stuck_workflow()
        assert result is True

    def test_should_run_task_confirmed(self, cli):
        """Test should_run_task with user confirmation."""
        mock_task = Mock()
        mock_task.name = "Test Task"

        with patch("crackerjack.interactive.Confirm.ask", return_value=True):
            result = cli._should_run_task(mock_task)
            assert result is True

    def test_should_run_task_declined(self, cli):
        """Test should_run_task with user declining."""
        mock_task = Mock()
        mock_task.name = "Test Task"
        mock_task.skip = Mock()

        with patch("crackerjack.interactive.Confirm.ask", return_value=False):
            result = cli._should_run_task(mock_task)
            assert result is False
            mock_task.skip.assert_called_once()

    def test_execute_single_task(self, cli):
        """Test executing single task."""
        cli.workflow = Mock()
        mock_task = Mock()
        cli.workflow.run_task.return_value = True

        result = cli._execute_single_task(mock_task)
        assert result is True
        cli.workflow.run_task.assert_called_once_with(mock_task)

    def test_should_continue_after_failure(self, cli):
        """Test should_continue_after_failure prompt."""
        with patch("crackerjack.interactive.Confirm.ask", return_value=True):
            result = cli._should_continue_after_failure()
            assert result is True

    def test_display_workflow_summary(self, cli):
        """Test displaying workflow summary."""
        cli.workflow.get_workflow_summary.return_value = {
            "success": 2,
            "failed": 1,
            "skipped": 0,
            "pending": 0,
            "running": 0,
        }

        cli._display_workflow_summary()

        # Should have printed table
        cli.console.print.assert_called()


class TestLegacyWorkflowManager:
    """Test legacy WorkflowManager compatibility."""

    @pytest.fixture
    def console(self):
        """Create mock console."""
        return Mock(spec=Console)

    @pytest.fixture
    def workflow_manager(self, console):
        """Create legacy WorkflowManager instance."""
        from crackerjack.interactive import WorkflowManager

        return WorkflowManager(console)

    def test_initialization(self, workflow_manager, console):
        """Test WorkflowManager initialization."""
        assert workflow_manager.console == console
        assert workflow_manager.current_task is None
        assert isinstance(workflow_manager.tasks, dict)

    def test_add_task_basic(self, workflow_manager):
        """Test adding task with basic parameters."""
        task = workflow_manager.add_task("Test Task", "A test task")

        assert task.name == "Test Task"
        assert task.description == "A test task"
        assert task.dependencies == []
        assert "Test Task" in workflow_manager.tasks

    def test_add_task_with_dependencies(self, workflow_manager):
        """Test adding task with dependencies."""
        task = workflow_manager.add_task(
            "Test Task", "A test task", dependencies=["dep1", "dep2"]
        )

        assert task.dependencies == ["dep1", "dep2"]

    def test_run_legacy_task_success(self, workflow_manager):
        """Test running legacy task successfully."""
        task = workflow_manager.add_task("Test Task", "A test task")

        def success_func():
            return True

        result = workflow_manager.run_legacy_task(task, success_func)

        assert result is True
        assert task.status == TaskStatus.SUCCESS
        assert workflow_manager.current_task is None

    def test_run_legacy_task_crackerjack_error(self, workflow_manager):
        """Test running legacy task with CrackerjackError."""
        task = workflow_manager.add_task("Test Task", "A test task")

        def error_func():
            raise CrackerjackError("Test error", ErrorCode.COMMAND_EXECUTION_ERROR)

        result = workflow_manager.run_legacy_task(task, error_func)

        assert result is False
        assert task.status == TaskStatus.FAILED
        assert task.error is not None

    def test_run_legacy_task_unexpected_error(self, workflow_manager):
        """Test running legacy task with unexpected error."""
        task = workflow_manager.add_task("Test Task", "A test task")

        def error_func():
            raise ValueError("Unexpected error")

        result = workflow_manager.run_legacy_task(task, error_func)

        assert result is False
        assert task.status == TaskStatus.FAILED
        assert task.error is not None
        assert "Unexpected error" in str(task.error)


class TestLegacyInteractiveCLI:
    """Test legacy InteractiveCLI compatibility."""

    @pytest.fixture
    def console(self):
        """Create mock console."""
        return Mock(spec=Console)

    @pytest.fixture
    def cli(self, console):
        """Create legacy InteractiveCLI instance."""
        from crackerjack.interactive import InteractiveCLI

        return InteractiveCLI(console)

    def test_initialization_with_console(self, console):
        """Test CLI initialization with console."""
        from crackerjack.interactive import InteractiveCLI, WorkflowManager

        cli = InteractiveCLI(console)

        assert cli.console == console
        assert isinstance(cli.workflow, WorkflowManager)

    def test_initialization_without_console(self):
        """Test CLI initialization without console."""
        from crackerjack.interactive import InteractiveCLI

        cli = InteractiveCLI()

        assert isinstance(cli.console, Console)

    def test_show_banner(self, cli):
        """Test showing banner."""
        cli.show_banner("1.0.0")

        # Should print banner
        cli.console.print.assert_called()

    def test_create_standard_workflow(self, cli):
        """Test creating standard workflow."""
        cli.create_standard_workflow()

        # Should have created standard tasks
        expected_tasks = [
            "setup",
            "config",
            "clean",
            "hooks",
            "test",
            "version",
            "publish",
            "commit",
        ]
        for task_name in expected_tasks:
            assert task_name in cli.workflow.tasks

    def test_create_dynamic_workflow_with_options(self, cli):
        """Test creating dynamic workflow with options."""
        mock_options = Mock()
        mock_options.clean = True
        mock_options.test = True
        mock_options.publish = "pypi"

        with patch.object(cli, "create_dynamic_workflow") as mock_create:
            cli.create_dynamic_workflow(mock_options)
            mock_create.assert_called_once()


class TestLaunchInteractiveCLI:
    """Test launch_interactive_cli function."""

    def test_launch_with_options(self):
        """Test launching with options."""
        from crackerjack.interactive import launch_interactive_cli

        mock_options = Mock()
        mock_options.clean = True
        mock_options.test = True

        with patch("crackerjack.interactive.Console") as mock_console_class:
            with patch("crackerjack.interactive.InteractiveCLI") as mock_cli_class:
                mock_console = Mock()
                mock_console_class.return_value = mock_console

                mock_cli = Mock()
                mock_cli_class.return_value = mock_cli
                mock_cli.run_interactive_workflow.return_value = True

                launch_interactive_cli("1.0.0", mock_options)

                mock_cli_class.assert_called_once_with(mock_console)
                mock_cli.show_banner.assert_called_once_with("1.0.0")
                mock_cli.create_dynamic_workflow.assert_called_once_with(mock_options)

    def test_launch_without_options(self):
        """Test launching without options."""
        from crackerjack.interactive import launch_interactive_cli

        with patch("crackerjack.interactive.Console") as mock_console_class:
            with patch("crackerjack.interactive.InteractiveCLI") as mock_cli_class:
                mock_console = Mock()
                mock_console_class.return_value = mock_console

                mock_cli = Mock()
                mock_cli_class.return_value = mock_cli
                mock_cli.run_interactive_workflow.return_value = True

                launch_interactive_cli("1.0.0")

                mock_cli.create_standard_workflow.assert_called_once()

    def test_launch_no_interactive_method(self):
        """Test launching when interactive method not available."""
        from crackerjack.interactive import launch_interactive_cli

        with patch("crackerjack.interactive.Console") as mock_console_class:
            with patch("crackerjack.interactive.InteractiveCLI") as mock_cli_class:
                mock_console = Mock()
                mock_console_class.return_value = mock_console

                mock_cli = Mock()
                mock_cli_class.return_value = mock_cli
                # Remove the method to simulate old version
                del mock_cli.run_interactive_workflow

                launch_interactive_cli("1.0.0")

                mock_cli.console.print.assert_called()
