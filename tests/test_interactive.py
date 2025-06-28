import io
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from rich.panel import Panel
from crackerjack.errors import ErrorCode, ExecutionError
from crackerjack.interactive import (
    InteractiveCLI,
    Task,
    TaskStatus,
    WorkflowManager,
    launch_interactive_cli,
)


class TestTask:
    def test_task_initialization(self) -> None:
        task = Task("test_task", "Test Description")
        assert task.name == "test_task"
        assert task.description == "Test Description"
        assert not task.dependencies
        assert task.status == TaskStatus.PENDING
        assert task.start_time is None
        assert task.end_time is None
        assert task.error is None

    def test_task_with_dependencies(self) -> None:
        dep1 = Task("dep1", "Dependency 1")
        dep2 = Task("dep2", "Dependency 2")
        task = Task("test_task", "Test Description", dependencies=[dep1, dep2])
        assert task.dependencies == [dep1, dep2]

    def test_task_duration(self) -> None:
        task = Task("test", "Test")
        assert task.duration is None
        task.start()
        time.sleep(0.01)
        duration1 = task.duration
        assert duration1 is not None
        assert duration1 > 0
        time.sleep(0.01)
        task.complete()
        duration2 = task.duration
        assert duration2 is not None
        assert duration2 > duration1
        time.sleep(0.01)
        assert task.duration == duration2

    def test_task_state_transitions(self) -> None:
        task = Task("test", "Test")
        assert task.status == TaskStatus.PENDING
        task.start()
        assert task.status == TaskStatus.RUNNING
        assert task.start_time is not None
        task.complete()
        assert task.status == TaskStatus.SUCCESS
        assert task.end_time is not None
        task = Task("test", "Test")
        task.start()
        error = ExecutionError(
            message="Test error",
            error_code=ErrorCode.UNEXPECTED_ERROR,
            details="Test details",
        )
        task.fail(error)
        assert task.status == TaskStatus.FAILED
        assert task.end_time is not None
        assert task.error == error
        task = Task("test", "Test")
        task.skip()
        assert task.status == TaskStatus.SKIPPED

    def test_task_can_run(self) -> None:
        dep1 = Task("dep1", "Dependency 1")
        dep2 = Task("dep2", "Dependency 2")
        task = Task("test", "Test", dependencies=[dep1, dep2])
        assert not task.can_run()
        dep1.start()
        dep1.complete()
        dep2.start()
        dep2.fail(ExecutionError(message="Test", error_code=ErrorCode.UNEXPECTED_ERROR))
        assert not task.can_run()
        dep2 = Task("dep2", "Dependency 2")
        task = Task("test", "Test", dependencies=[dep1, dep2])
        dep2.skip()
        assert task.can_run()
        dep1 = Task("dep1", "Dependency 1")
        dep2 = Task("dep2", "Dependency 2")
        task = Task("test", "Test", dependencies=[dep1, dep2])
        dep1.start()
        dep1.complete()
        dep2.start()
        dep2.complete()
        assert task.can_run()

    def test_task_str_representation(self) -> None:
        task = Task("test", "Test")
        assert str(task) == "test (PENDING)"
        task.start()
        assert str(task) == "test (RUNNING)"
        task.complete()
        assert str(task) == "test (SUCCESS)"


class TestWorkflowManager:
    @pytest.fixture
    def workflow(self) -> WorkflowManager:
        return WorkflowManager(Console())

    def test_workflow_initialization(self, workflow: WorkflowManager) -> None:
        assert not workflow.tasks
        assert workflow.current_task is None

    def test_add_task(self, workflow: WorkflowManager) -> None:
        task = workflow.add_task("test", "Test task")
        assert task.name == "test"
        assert task.description == "Test task"
        assert task in workflow.tasks.values()
        assert workflow.tasks["test"] == task

    def test_add_task_with_dependencies(self, workflow: WorkflowManager) -> None:
        workflow.add_task("dep1", "Dependency 1")
        workflow.add_task("dep2", "Dependency 2")
        task = workflow.add_task("test", "Test task", dependencies=["dep1", "dep2"])
        assert len(task.dependencies) == 2
        assert workflow.tasks["dep1"] in task.dependencies
        assert workflow.tasks["dep2"] in task.dependencies

    def test_add_task_with_invalid_dependency(self, workflow: WorkflowManager) -> None:
        with pytest.raises(ValueError, match="Dependency task 'invalid' not found"):
            workflow.add_task("test", "Test task", dependencies=["invalid"])

    def test_get_next_task(self, workflow: WorkflowManager) -> None:
        workflow.add_task("task1", "Task 1")
        dep1 = workflow.tasks["task1"]
        workflow.add_task("task2", "Task 2", dependencies=["task1"])
        task2 = workflow.tasks["task2"]
        next_task = workflow.get_next_task()
        assert next_task == dep1
        dep1.start()
        dep1.complete()
        next_task = workflow.get_next_task()
        assert next_task == task2
        workflow.current_task = task2
        next_task = workflow.get_next_task()
        assert next_task is None
        task2.start()
        task2.complete()
        workflow.current_task = None
        next_task = workflow.get_next_task()
        assert next_task is None

    def test_all_tasks_completed(self, workflow: WorkflowManager) -> None:
        workflow.add_task("task1", "Task 1")
        workflow.add_task("task2", "Task 2")
        assert not workflow.all_tasks_completed()
        workflow.tasks["task1"].start()
        workflow.tasks["task1"].complete()
        assert not workflow.all_tasks_completed()
        workflow.tasks["task2"].skip()
        assert workflow.all_tasks_completed()
        workflow.add_task("task3", "Task 3")
        assert not workflow.all_tasks_completed()
        workflow.tasks["task3"].start()
        workflow.tasks["task3"].fail(
            ExecutionError(message="Test", error_code=ErrorCode.UNEXPECTED_ERROR)
        )
        assert workflow.all_tasks_completed()

    def test_run_task_success(self, workflow: WorkflowManager) -> None:
        task = workflow.add_task("test", "Test task")
        func = MagicMock()
        result = workflow.run_task(task, func)
        assert result
        assert task.status == TaskStatus.SUCCESS
        func.assert_called_once()
        assert workflow.current_task is None

    def test_run_task_crackerjack_error(self, workflow: WorkflowManager) -> None:
        task = workflow.add_task("test", "Test task")
        error = ExecutionError(
            message="Test error", error_code=ErrorCode.COMMAND_EXECUTION_ERROR
        )
        func = MagicMock(side_effect=error)
        result = workflow.run_task(task, func)
        assert not result
        assert task.status == TaskStatus.FAILED
        assert task.error == error
        func.assert_called_once()
        assert workflow.current_task is None

    def test_run_task_generic_exception(self, workflow: WorkflowManager) -> None:
        task = workflow.add_task("test", "Test task")
        func = MagicMock(side_effect=ValueError("Test exception"))
        result = workflow.run_task(task, func)
        assert not result
        assert task.status == TaskStatus.FAILED
        assert task.error is not None
        assert task.error.error_code == ErrorCode.UNEXPECTED_ERROR
        assert "Test exception" in str(task.error.details)
        func.assert_called_once()
        assert workflow.current_task is None

    def test_display_task_tree(self, workflow: WorkflowManager) -> None:
        workflow.add_task("task1", "Task 1")
        workflow.add_task("task2", "Task 2", dependencies=["task1"])
        workflow.add_task("task3", "Task 3", dependencies=["task1"])
        with patch.object(workflow.console, "print") as mock_print:
            workflow.display_task_tree()
            mock_print.assert_called_once()
            assert mock_print.call_args is not None
            assert mock_print.call_args.args is not None
            assert len(mock_print.call_args.args) > 0
            from rich.tree import Tree

            assert isinstance(mock_print.call_args.args[0], Tree)


class TestInteractiveCLI:
    @pytest.fixture
    def console(self) -> Console:
        return Console(file=io.StringIO(), width=100)

    @pytest.fixture
    def cli(self, console: Console) -> InteractiveCLI:
        return InteractiveCLI(console)

    def test_initialization(self, console: Console) -> None:
        cli = InteractiveCLI(console)
        assert cli.console == console
        assert isinstance(cli.workflow, WorkflowManager)

    def test_initialization_default_console(self) -> None:
        cli = InteractiveCLI()
        assert isinstance(cli.console, Console)
        assert isinstance(cli.workflow, WorkflowManager)

    def test_show_banner(self, cli: InteractiveCLI, console: Console) -> None:
        from io import StringIO

        console.file = StringIO()
        cli.show_banner("1.0.0")
        output = console.file.getvalue()
        assert "Crackerjack" in output
        assert "v1.0.0" in output
        assert "Python project management" in output

    def test_create_standard_workflow(self, cli: InteractiveCLI) -> None:
        cli.create_standard_workflow()
        assert "setup" in cli.workflow.tasks
        assert "config" in cli.workflow.tasks
        assert "clean" in cli.workflow.tasks
        assert "hooks" in cli.workflow.tasks
        assert "test" in cli.workflow.tasks
        assert "version" in cli.workflow.tasks
        assert "publish" in cli.workflow.tasks
        assert "commit" in cli.workflow.tasks
        assert not cli.workflow.tasks["setup"].dependencies
        assert cli.workflow.tasks["setup"] in cli.workflow.tasks["config"].dependencies
        assert cli.workflow.tasks["config"] in cli.workflow.tasks["clean"].dependencies
        assert cli.workflow.tasks["clean"] in cli.workflow.tasks["hooks"].dependencies
        assert cli.workflow.tasks["hooks"] in cli.workflow.tasks["test"].dependencies
        assert cli.workflow.tasks["test"] in cli.workflow.tasks["version"].dependencies
        assert (
            cli.workflow.tasks["version"] in cli.workflow.tasks["publish"].dependencies
        )
        assert (
            cli.workflow.tasks["publish"] in cli.workflow.tasks["commit"].dependencies
        )

    def test_setup_layout(self, cli: InteractiveCLI) -> None:
        layout = cli.setup_layout()
        assert layout is not None
        assert layout.get("header") is not None
        assert layout.get("main") is not None
        assert layout.get("footer") is not None
        assert layout["main"].get("tasks") is not None
        assert layout["main"].get("details") is not None

    def test_show_task_status(self, cli: InteractiveCLI) -> None:
        task = Task("test", "Test Description")
        panel = cli.show_task_status(task)
        assert isinstance(panel, Panel)
        assert panel.title == "test"
        task.start()
        panel = cli.show_task_status(task)
        assert panel.title == "test"
        assert panel.border_style == "yellow"
        task.complete()
        panel = cli.show_task_status(task)
        assert panel.title == "test"
        assert panel.border_style == "green"
        task = Task("test", "Test Description")
        task.start()
        error = ExecutionError(
            message="Test error",
            error_code=ErrorCode.COMMAND_EXECUTION_ERROR,
            details="Test details",
            recovery="Test recovery",
        )
        task.fail(error)
        panel = cli.show_task_status(task)
        assert panel.title == "test"
        assert panel.border_style == "red"

    def test_show_task_table(self, cli: InteractiveCLI) -> None:
        task1 = Task("task1", "Task 1")
        task1.start()
        task1.complete()
        cli.workflow.tasks["task1"] = task1
        task2 = Task("task2", "Task 2")
        task2.start()
        cli.workflow.tasks["task2"] = task2
        task3 = Task("task3", "Task 3")
        task3.skip()
        cli.workflow.tasks["task3"] = task3
        task4 = Task("task4", "Task 4", dependencies=[task1])
        cli.workflow.tasks["task4"] = task4
        table = cli.show_task_table()
        from rich.table import Table

        assert isinstance(table, Table)
        assert table.title == "Workflow Tasks"
        assert len(table.columns) == 4
        assert cli.workflow.tasks
        assert len(table.rows) == len(cli.workflow.tasks)

    @patch("crackerjack.interactive.Prompt")
    def test_confirm_dangerous_action(
        self, mock_prompt: MagicMock, cli: InteractiveCLI
    ) -> None:
        mock_prompt.ask.return_value = "delete"
        result = cli.confirm_dangerous_action("delete", "This will delete files")
        assert result
        mock_prompt.ask.return_value = "wrong"
        result = cli.confirm_dangerous_action("delete", "This will delete files")
        assert not result

    def test_show_error(self, cli: InteractiveCLI) -> None:
        error = ExecutionError(
            message="Test error",
            error_code=ErrorCode.COMMAND_EXECUTION_ERROR,
            details="Test details",
            recovery="Test recovery",
        )
        with patch("crackerjack.interactive.handle_error") as mock_handle_error:
            cli.show_error(error, verbose=True)
            mock_handle_error.assert_called_once_with(
                error, cli.console, True, exit_on_error=False
            )

    def test_run_interactive_basic(self, cli: InteractiveCLI) -> None:
        cli.create_standard_workflow()
        with patch("crackerjack.interactive.Live") as mock_live:
            mock_context = MagicMock()
            mock_live.return_value.__enter__.return_value = mock_context
            mock_context.start.side_effect = KeyboardInterrupt
            with patch.object(cli.console, "clear"):
                with patch("crackerjack.interactive.Confirm"):
                    cli.run_interactive()

    @patch("crackerjack.interactive.Prompt")
    def test_ask_for_file(
        self, mock_prompt: MagicMock, cli: InteractiveCLI, tmp_path: Path
    ) -> None:
        file1 = tmp_path / "file1.txt"
        file1.write_text("test")
        file2 = tmp_path / "file2.txt"
        file2.write_text("test")
        mock_prompt.ask.return_value = "1"
        result = cli.ask_for_file("Select a file", tmp_path)
        assert result == file1
        mock_prompt.ask.return_value = "file2.txt"
        result = cli.ask_for_file("Select a file", tmp_path)
        assert result == file2
        mock_prompt.ask.return_value = "newfile.txt"
        result = cli.ask_for_file("Select a file", tmp_path)
        assert result == tmp_path / "newfile.txt"


@patch("crackerjack.interactive.InteractiveCLI")
def test_launch_interactive_cli(mock_cli_class: MagicMock) -> None:
    mock_cli = MagicMock()
    mock_cli_class.return_value = mock_cli
    launch_interactive_cli("1.0.0")
    mock_cli_class.assert_called_once()
    mock_cli.show_banner.assert_called_once_with("1.0.0")
    mock_cli.create_standard_workflow.assert_called_once()
    mock_cli.run_interactive.assert_called_once()
