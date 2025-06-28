from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from crackerjack.errors import ErrorCode, ExecutionError
from crackerjack.interactive import InteractiveCLI, TaskStatus


class TestInteractiveRun:
    @pytest.fixture
    def cli(self) -> InteractiveCLI:
        return InteractiveCLI(Console(width=100, height=50))

    def test_run_interactive_with_tasks_success_and_failure(
        self, cli: InteractiveCLI
    ) -> None:
        task1 = cli.workflow.add_task("task1", "Task 1")
        task2 = cli.workflow.add_task("task2", "Task 2")
        task3 = cli.workflow.add_task("task3", "Task 3", dependencies=["task2"])
        layout_mock = {
            "header": MagicMock(),
            "main": MagicMock(),
            "footer": MagicMock(),
            "tasks": MagicMock(),
            "details": MagicMock(),
        }
        main_layout = MagicMock()
        main_layout["tasks"] = MagicMock()
        main_layout["details"] = MagicMock()
        layout_mock["main"] = main_layout
        live_mock = MagicMock()
        progress_mock = MagicMock()
        progress_task_mock = MagicMock()
        progress_mock.add_task.return_value = progress_task_mock
        tasks_to_return = [task1, task2, task3, None]
        task_index = 0

        def mock_get_next_task():
            nonlocal task_index
            result = tasks_to_return[task_index]
            task_index += 1
            return result

        with (
            patch.object(cli, "setup_layout", return_value=layout_mock),
            patch("rich.live.Live", return_value=live_mock),
            patch("rich.progress.Progress", return_value=progress_mock),
            patch.object(cli.workflow, "get_next_task", side_effect=mock_get_next_task),
            patch("time.sleep"),
            patch("random.choice", side_effect=[True, True, False]),
            patch("rich.prompt.Confirm.ask", return_value=True),
        ):
            cli.run_interactive()
            assert task1.status == TaskStatus.SUCCESS
            assert task2.status == TaskStatus.SUCCESS
            assert task3.status == TaskStatus.FAILED
            assert isinstance(task3.error, ExecutionError)
            assert task3.error.error_code == ErrorCode.COMMAND_EXECUTION_ERROR

    def test_run_interactive_with_task_skipping(self, cli: InteractiveCLI) -> None:
        task = cli.workflow.add_task("test_task", "Test Task")
        layout_mock = {
            "header": MagicMock(),
            "main": MagicMock(),
            "footer": MagicMock(),
            "tasks": MagicMock(),
            "details": MagicMock(),
        }
        main_layout = MagicMock()
        main_layout["tasks"] = MagicMock()
        main_layout["details"] = MagicMock()
        layout_mock["main"] = main_layout
        tasks_to_return = [task, None]
        task_index = 0

        def mock_get_next_task():
            nonlocal task_index
            result = tasks_to_return[task_index]
            task_index += 1
            return result

        with (
            patch.object(cli, "setup_layout", return_value=layout_mock),
            patch("rich.live.Live", return_value=MagicMock()),
            patch("rich.progress.Progress", return_value=MagicMock()),
            patch.object(cli.workflow, "get_next_task", side_effect=mock_get_next_task),
            patch("time.sleep"),
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            cli.run_interactive()
            assert task.status == TaskStatus.SKIPPED

    def test_run_interactive_with_task_summary(self, cli: InteractiveCLI) -> None:
        task1 = cli.workflow.add_task("success", "Successful Task")
        task1.start()
        task1.complete()
        task2 = cli.workflow.add_task("failed", "Failed Task")
        task2.start()
        task2.fail(
            ExecutionError(message="Failed", error_code=ErrorCode.UNEXPECTED_ERROR)
        )
        task3 = cli.workflow.add_task("skipped", "Skipped Task")
        task3.skip()
        layout_mock = {
            "header": MagicMock(),
            "main": MagicMock(),
            "footer": MagicMock(),
            "tasks": MagicMock(),
            "details": MagicMock(),
        }
        main_layout = MagicMock()
        main_layout["tasks"] = MagicMock()
        main_layout["details"] = MagicMock()
        layout_mock["main"] = main_layout
        with (
            patch.object(cli, "setup_layout", return_value=layout_mock),
            patch("rich.live.Live", return_value=MagicMock()),
            patch("rich.progress.Progress", return_value=MagicMock()),
            patch.object(cli.workflow, "get_next_task", return_value=None),
            patch("time.sleep"),
            patch("rich.prompt.Confirm.ask", return_value=True),
        ):
            cli.run_interactive()
            assert len(cli.workflow.tasks) == 3
            assert (
                sum(
                    1
                    for t in cli.workflow.tasks.values()
                    if t.status == TaskStatus.SUCCESS
                )
                == 1
            )
            assert (
                sum(
                    1
                    for t in cli.workflow.tasks.values()
                    if t.status == TaskStatus.FAILED
                )
                == 1
            )
            assert (
                sum(
                    1
                    for t in cli.workflow.tasks.values()
                    if t.status == TaskStatus.SKIPPED
                )
                == 1
            )
