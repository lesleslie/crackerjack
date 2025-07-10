import time
import typing as t
from enum import Enum, auto
from pathlib import Path

from rich.box import ROUNDED
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .errors import CrackerjackError, ErrorCode, handle_error


class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


class Task:
    def __init__(
        self, name: str, description: str, dependencies: list["Task"] | None = None
    ) -> None:
        self.name = name
        self.description = description
        self.dependencies = dependencies or []
        self.status = TaskStatus.PENDING
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.error: CrackerjackError | None = None

    @property
    def duration(self) -> float | None:
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    def start(self) -> None:
        self.status = TaskStatus.RUNNING
        self.start_time = time.time()

    def complete(self, success: bool = True) -> None:
        self.end_time = time.time()
        self.status = TaskStatus.SUCCESS if success else TaskStatus.FAILED

    def skip(self) -> None:
        self.status = TaskStatus.SKIPPED

    def fail(self, error: CrackerjackError) -> None:
        self.end_time = time.time()
        self.status = TaskStatus.FAILED
        self.error = error

    def can_run(self) -> bool:
        return all(
            dep.status in (TaskStatus.SUCCESS, TaskStatus.SKIPPED)
            for dep in self.dependencies
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.status.name})"


class WorkflowManager:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.tasks: dict[str, Task] = {}
        self.current_task: Task | None = None

    def add_task(
        self, name: str, description: str, dependencies: list[str] | None = None
    ) -> Task:
        dep_tasks = []
        if dependencies:
            for dep_name in dependencies:
                if dep_name not in self.tasks:
                    raise ValueError(f"Dependency task '{dep_name}' not found")
                dep_tasks.append(self.tasks[dep_name])
        task = Task(name, description, dep_tasks)
        self.tasks[name] = task
        return task

    def get_next_task(self) -> Task | None:
        for task in self.tasks.values():
            if (
                task.status == TaskStatus.PENDING
                and task.can_run()
                and (task != self.current_task)
            ):
                return task
        return None

    def all_tasks_completed(self) -> bool:
        return all(
            task.status in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.SKIPPED)
            for task in self.tasks.values()
        )

    def run_task(self, task: Task, func: t.Callable[[], t.Any]) -> bool:
        self.current_task = task
        task.start()
        try:
            func()
            task.complete()
            return True
        except CrackerjackError as e:
            task.fail(e)
            return False
        except Exception as e:
            from .errors import ExecutionError

            error = ExecutionError(
                message=f"Unexpected error in task '{task.name}'",
                error_code=ErrorCode.UNEXPECTED_ERROR,
                details=str(e),
                recovery=f"This is an unexpected error in task '{task.name}'. Please report this issue.",
            )
            task.fail(error)
            return False
        finally:
            self.current_task = None

    def display_task_tree(self) -> None:
        tree = Tree("Workflow")
        for task in self.tasks.values():
            if not task.dependencies:
                self._add_task_to_tree(task, tree)
        self.console.print(tree)

    def _add_task_to_tree(self, task: Task, parent: Tree) -> None:
        if task.status == TaskStatus.SUCCESS:
            status = "[green]✅[/green]"
        elif task.status == TaskStatus.FAILED:
            status = "[red]❌[/red]"
        elif task.status == TaskStatus.RUNNING:
            status = "[yellow]⏳[/yellow]"
        elif task.status == TaskStatus.SKIPPED:
            status = "[blue]⏩[/blue]"
        else:
            status = "[grey]⏸️[/grey]"
        branch = parent.add(f"{status} {task.name} - {task.description}")
        for dependent in self.tasks.values():
            if task in dependent.dependencies:
                self._add_task_to_tree(dependent, branch)


class InteractiveCLI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.workflow = WorkflowManager(self.console)

    def show_banner(self, version: str) -> None:
        title = Text("Crackerjack", style="bold cyan")
        version_text = Text(f"v{version}", style="dim cyan")
        subtitle = Text("Your Python project management toolkit", style="italic")
        panel = Panel(
            f"{title} {version_text}\n{subtitle}",
            box=ROUNDED,
            border_style="cyan",
            expand=False,
        )
        self.console.print(panel)
        self.console.print()

    def create_standard_workflow(self) -> None:
        self.workflow.add_task("setup", "Initialize project structure")
        self.workflow.add_task(
            "config", "Update configuration files", dependencies=["setup"]
        )
        self.workflow.add_task(
            "clean", "Clean code (remove docstrings, comments)", dependencies=["config"]
        )
        self.workflow.add_task("hooks", "Run pre-commit hooks", dependencies=["clean"])
        self.workflow.add_task("test", "Run tests", dependencies=["hooks"])
        self.workflow.add_task("version", "Bump version", dependencies=["test"])
        self.workflow.add_task("publish", "Publish package", dependencies=["version"])
        self.workflow.add_task("commit", "Commit changes", dependencies=["publish"])

    def setup_layout(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )
        layout["main"].split_row(
            Layout(name="tasks", ratio=1), Layout(name="details", ratio=2)
        )
        return layout

    def show_task_status(self, task: Task) -> Panel:
        if task.status == TaskStatus.RUNNING:
            status = "[yellow]Running[/yellow]"
            style = "yellow"
        elif task.status == TaskStatus.SUCCESS:
            status = "[green]Success[/green]"
            style = "green"
        elif task.status == TaskStatus.FAILED:
            status = "[red]Failed[/red]"
            style = "red"
        elif task.status == TaskStatus.SKIPPED:
            status = "[blue]Skipped[/blue]"
            style = "blue"
        else:
            status = "[dim white]Pending[/dim white]"
            style = "dim"
        duration = task.duration
        duration_text = f"Duration: {duration:.2f}s" if duration else ""
        content = f"{task.name}: {task.description}\nStatus: {status}\n{duration_text}"
        if task.error:
            content += f"\n[red]Error: {task.error.message}[/red]"
            if task.error.details:
                content += f"\n[dim red]Details: {task.error.details}[/dim red]"
            if task.error.recovery:
                content += f"\n[yellow]Recovery: {task.error.recovery}[/yellow]"
        return Panel(content, title=task.name, border_style=style, expand=False)

    def show_task_table(self) -> Table:
        table = Table(
            title="Workflow Tasks",
            box=ROUNDED,
            show_header=True,
            header_style="bold white",
        )
        table.add_column("Task", style="white")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Dependencies")
        for task in self.workflow.tasks.values():
            if task.status == TaskStatus.RUNNING:
                status = "[yellow]Running[/yellow]"
            elif task.status == TaskStatus.SUCCESS:
                status = "[green]Success[/green]"
            elif task.status == TaskStatus.FAILED:
                status = "[red]Failed[/red]"
            elif task.status == TaskStatus.SKIPPED:
                status = "[blue]Skipped[/blue]"
            else:
                status = "[dim white]Pending[/dim white]"
            duration = task.duration
            duration_text = f"{duration:.2f}s" if duration else "-"
            deps = ", ".join(dep.name for dep in task.dependencies) or "-"
            table.add_row(task.name, status, duration_text, deps)
        return table

    def run_interactive(self) -> None:
        self.console.clear()
        layout = self._setup_interactive_layout()
        progress_tracker = self._create_progress_tracker()
        with Live(layout, refresh_per_second=4, screen=True) as live:
            try:
                self._execute_workflow_loop(layout, progress_tracker, live)
                self._display_final_summary(layout)
            except KeyboardInterrupt:
                self._handle_user_interruption(layout)
        self.console.print("\nWorkflow Status:")
        self.workflow.display_task_tree()

    def _setup_interactive_layout(self) -> Layout:
        layout = self.setup_layout()
        layout["header"].update(
            Panel("Crackerjack Interactive Mode", style="bold white", box=ROUNDED)
        )
        layout["footer"].update(Panel("Press Ctrl+C to exit", style="dim", box=ROUNDED))
        return layout

    def _create_progress_tracker(self) -> dict[str, t.Any]:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[white]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        )
        total_tasks = len(self.workflow.tasks)
        progress_task = progress.add_task("Running workflow", total=total_tasks)
        return {
            "progress": progress,
            "progress_task": progress_task,
            "completed_tasks": 0,
        }

    def _execute_workflow_loop(
        self, layout: Layout, progress_tracker: dict[str, t.Any], live: Live
    ) -> None:
        while not self.workflow.all_tasks_completed():
            layout["tasks"].update(self.show_task_table())
            next_task = self.workflow.get_next_task()
            if not next_task:
                break
            if self._should_execute_task(layout, next_task, live):
                self._execute_task(layout, next_task, progress_tracker)
            else:
                next_task.skip()

    def _should_execute_task(self, layout: Layout, task: Task, live: Live) -> bool:
        layout["details"].update(self.show_task_status(task))
        live.stop()
        should_run = Confirm.ask(f"Run task '{task.name}'?", default=True)
        live.start()
        return should_run

    def _execute_task(
        self, layout: Layout, task: Task, progress_tracker: dict[str, t.Any]
    ) -> None:
        task.start()
        layout["details"].update(self.show_task_status(task))
        time.sleep(1)
        success = self._simulate_task_execution()
        if success:
            task.complete()
            progress_tracker["completed_tasks"] += 1
        else:
            error = self._create_task_error(task.name)
            task.fail(error)
        progress_tracker["progress"].update(
            progress_tracker["progress_task"],
            completed=progress_tracker["completed_tasks"],
        )
        layout["details"].update(self.show_task_status(task))

    def _simulate_task_execution(self) -> bool:
        import random

        return random.choice([True, True, True, False])

    def _create_task_error(self, task_name: str) -> t.Any:
        from .errors import ExecutionError

        return ExecutionError(
            message=f"Task '{task_name}' failed",
            error_code=ErrorCode.COMMAND_EXECUTION_ERROR,
            details="This is a simulated failure for demonstration.",
            recovery=f"Retry the '{task_name}' task.",
        )

    def _display_final_summary(self, layout: Layout) -> None:
        layout["tasks"].update(self.show_task_table())
        task_counts = self._count_tasks_by_status()
        summary = Panel(
            f"Workflow completed!\n\n"
            f"[green]✅ Successful tasks: {task_counts['successful']}[/green]\n"
            f"[red]❌ Failed tasks: {task_counts['failed']}[/red]\n"
            f"[blue]⏩ Skipped tasks: {task_counts['skipped']}[/blue]",
            title="Summary",
            border_style="cyan",
        )
        layout["details"].update(summary)

    def _count_tasks_by_status(self) -> dict[str, int]:
        return {
            "successful": sum(
                1
                for task in self.workflow.tasks.values()
                if task.status == TaskStatus.SUCCESS
            ),
            "failed": sum(
                1
                for task in self.workflow.tasks.values()
                if task.status == TaskStatus.FAILED
            ),
            "skipped": sum(
                1
                for task in self.workflow.tasks.values()
                if task.status == TaskStatus.SKIPPED
            ),
        }

    def _handle_user_interruption(self, layout: Layout) -> None:
        layout["footer"].update(
            Panel("Interrupted by user", style="yellow", box=ROUNDED)
        )

    def ask_for_file(
        self, prompt: str, directory: Path, default: str | None = None
    ) -> Path:
        self.console.print(f"\n[bold]{prompt}[/bold]")
        files = list(directory.iterdir())
        files.sort()
        table = Table(title=f"Files in {directory}", box=ROUNDED)
        table.add_column("#", style="cyan")
        table.add_column("Filename", style="green")
        table.add_column("Size", style="blue")
        table.add_column("Modified", style="yellow")
        for i, file in enumerate(files, 1):
            if file.is_file():
                size = f"{file.stat().st_size / 1024:.1f} KB"
                mtime = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(file.stat().st_mtime)
                )
                table.add_row(str(i), file.name, size, mtime)
        self.console.print(table)
        selection = Prompt.ask("Enter file number or name", default=default or "")
        if selection.isdigit() and 1 <= int(selection) <= len(files):
            return files[int(selection) - 1]
        else:
            for file in files:
                if file.name == selection:
                    return file
            return directory / selection

    def confirm_dangerous_action(self, action: str, details: str) -> bool:
        panel = Panel(
            f"[bold red]WARNING: {action}[/bold red]\n\n{details}\n\nThis action cannot be undone. Please type the action name to confirm.",
            title="Confirmation Required",
            border_style="red",
        )
        self.console.print(panel)
        confirmation = Prompt.ask("Type the action name to confirm")
        return confirmation.lower() == action.lower()

    def show_error(self, error: CrackerjackError, verbose: bool = False) -> None:
        handle_error(error, self.console, verbose, exit_on_error=False)


def launch_interactive_cli(version: str) -> None:
    console = Console()
    cli = InteractiveCLI(console)
    cli.show_banner(version)
    cli.create_standard_workflow()
    cli.run_interactive()


if __name__ == "__main__":
    launch_interactive_cli("0.19.8")
