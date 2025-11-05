import time
import typing as t
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial
from typing import Protocol

from acb.console import Console
from acb.depends import depends
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .errors import CrackerjackError, ErrorCode


class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class InteractiveWorkflowOptions:
    clean: bool = False
    test: bool = False
    publish: str | None = None
    bump: str | None = None
    commit: bool = False
    create_pr: bool = False
    interactive: bool = True
    dry_run: bool = False

    def __init__(
        self,
        clean: bool = False,
        test: bool = False,
        publish: str | None = None,
        bump: str | None = None,
        commit: bool = False,
        create_pr: bool = False,
        interactive: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.clean = clean
        self.test = test
        self.publish = publish
        self.bump = bump
        self.commit = commit
        self.create_pr = create_pr
        self.interactive = interactive
        self.dry_run = dry_run

    @classmethod
    def from_args(cls, args: t.Any) -> "InteractiveWorkflowOptions":
        return cls(
            clean=getattr(args, "clean", False),
            test=getattr(args, "test", False),
            publish=getattr(args, "publish", None),
            bump=getattr(args, "bump", None),
            commit=getattr(args, "commit", False),
            create_pr=getattr(args, "create_pr", False),
            interactive=getattr(args, "interactive", True),
            dry_run=getattr(args, "dry_run", False),
        )


class TaskExecutor(Protocol):
    def __call__(self) -> bool: ...


@dataclass
class TaskDefinition:
    id: str
    name: str
    description: str
    dependencies: list[str]
    optional: bool = False
    estimated_duration: float = 0.0

    def __post_init__(self) -> None:
        if not self.dependencies:
            self.dependencies = []


class Task:
    def __init__(
        self,
        definition: TaskDefinition,
        executor: TaskExecutor | None = None,
        workflow_tasks: dict[str, "Task"] | None = None,
    ) -> None:
        self.definition = definition
        self.executor = executor
        self.status = TaskStatus.PENDING
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.error: CrackerjackError | None = None
        self._workflow_tasks = workflow_tasks
        import logging

        self.logger = logging.getLogger(f"crackerjack.task.{definition.id}")

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def dependencies(self) -> list["Task"] | list[str]:
        if self._workflow_tasks:
            return [
                self._workflow_tasks[dep_name]
                for dep_name in self.definition.dependencies
                if dep_name in self._workflow_tasks
            ]
        return self.definition.dependencies

    def get_resolved_dependencies(
        self,
        workflow_tasks: dict[str, "Task"],
    ) -> list["Task"]:
        return [
            workflow_tasks[dep_name]
            for dep_name in self.definition.dependencies
            if dep_name in workflow_tasks
        ]

    @property
    def duration(self) -> float | None:
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    def start(self) -> None:
        self.status = TaskStatus.RUNNING
        self.start_time = time.time()
        self.logger.info("Task started", extra={"task_id": self.definition.id})

    def complete(self, success: bool = True) -> None:
        self.end_time = time.time()
        self.status = TaskStatus.SUCCESS if success else TaskStatus.FAILED

        self.logger.info(
            "Task completed",
            extra={
                "task_id": self.definition.id,
                "success": success,
                "duration": self.duration,
            },
        )

    def skip(self) -> None:
        self.status = TaskStatus.SKIPPED
        self.end_time = time.time()
        self.logger.info("Task skipped", extra={"task_id": self.definition.id})

    def fail(self, error: CrackerjackError) -> None:
        self.status = TaskStatus.FAILED
        self.end_time = time.time()
        self.error = error

        self.logger.error(
            "Task failed",
            extra={
                "task_id": self.definition.id,
                "error": str(error),
                "duration": self.duration,
            },
        )

    def can_run(self, completed_tasks: set[str]) -> bool:
        if self._workflow_tasks:
            resolved_deps = self.get_resolved_dependencies(self._workflow_tasks)
            return all(
                dep.status in (TaskStatus.SUCCESS, TaskStatus.SKIPPED)
                for dep in resolved_deps
            )

        return all(dep in completed_tasks for dep in self.definition.dependencies)


class WorkflowBuilder:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.tasks: dict[str, TaskDefinition] = {}
        import logging

        self.logger = logging.getLogger("crackerjack.workflow.builder")

    def add_task(
        self,
        task_id: str,
        name: str,
        description: str,
        dependencies: list[str] | None = None,
        optional: bool = False,
        estimated_duration: float = 0.0,
    ) -> "WorkflowBuilder":
        task_def = TaskDefinition(
            id=task_id,
            name=name,
            description=description,
            dependencies=dependencies or [],
            optional=optional,
            estimated_duration=estimated_duration,
        )

        self.tasks[task_id] = task_def
        self.logger.debug("Task added to workflow", extra={"task_id": task_id})
        return self

    def add_conditional_task(
        self,
        condition: bool,
        task_id: str,
        name: str,
        description: str,
        dependencies: list[str] | None = None,
        estimated_duration: float = 0.0,
    ) -> str:
        if condition:
            self.add_task(
                task_id=task_id,
                name=name,
                description=description,
                dependencies=dependencies,
                estimated_duration=estimated_duration,
            )
            return task_id

        return dependencies[-1] if dependencies else ""

    def build(self) -> dict[str, TaskDefinition]:
        self._validate_workflow()
        return self.tasks.copy()

    def _validate_workflow(self) -> None:
        self._validate_dependencies()
        self._check_circular_dependencies()

    def _validate_dependencies(self) -> None:
        for task_id, task_def in self.tasks.items():
            for dep in task_def.dependencies:
                if dep not in self.tasks:
                    msg = f"Task {task_id} depends on unknown task {dep}"
                    raise ValueError(msg)

    def _check_circular_dependencies(self) -> None:
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            for dep in self.tasks[task_id].dependencies:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited and has_cycle(task_id):
                msg = f"Circular dependency detected involving task {task_id}"
                raise ValueError(
                    msg,
                )


class WorkflowManager:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.tasks: dict[str, Task] = {}
        self.task_definitions: dict[str, TaskDefinition] = {}
        import logging

        self.logger = logging.getLogger("crackerjack.workflow.manager")

    def load_workflow(self, task_definitions: dict[str, TaskDefinition]) -> None:
        self.task_definitions = task_definitions
        self.tasks = {
            task_id: Task(definition)
            for task_id, definition in task_definitions.items()
        }

        for task in self.tasks.values():
            task._workflow_tasks = self.tasks

        self.logger.info("Workflow loaded", extra={"task_count": len(self.tasks)})

    def set_task_executor(self, task_id: str, executor: TaskExecutor) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].executor = executor

    def get_next_task(self) -> Task | None:
        completed_tasks = {
            task_id
            for task_id, task in self.tasks.items()
            if task.status == TaskStatus.SUCCESS
        }

        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING and task.can_run(completed_tasks):
                return task

        return None

    def all_tasks_completed(self) -> bool:
        return all(
            task.status in (TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.SKIPPED)
            for task in self.tasks.values()
        )

    def run_task(self, task: Task) -> bool:
        if not task.executor:
            return self._handle_task_without_executor(task)

        return self._execute_task_with_executor(task)

    def _handle_task_without_executor(self, task: Task) -> bool:
        task.skip()
        self.console.print(f"[yellow]⏭️ Skipped {task.name} (no executor)[/ yellow]")
        return True

    def _execute_task_with_executor(self, task: Task) -> bool:
        task.start()
        self.console.print(f"[blue]🔄 Running {task.name}...[/ blue]")

        try:
            return self._try_execute_task(task)
        except Exception as e:
            return self._handle_task_exception(task, e)

    def _try_execute_task(self, task: Task) -> bool:
        self.logger.info(f"Executing task: {task.definition.id}")
        success = task.executor() if task.executor else False
        task.complete(success)

        self._display_task_result(task, success)
        return success

    def _display_task_result(self, task: Task, success: bool) -> None:
        if success:
            duration_str = f" ({task.duration: .1f}s)" if task.duration else ""
            self.console.print(f"[green]✅ {task.name}{duration_str}[/ green]")
        else:
            self.console.print(f"[red]❌ {task.name} failed[/ red]")

    def _handle_task_exception(self, task: Task, e: Exception) -> bool:
        error = CrackerjackError(
            message=f"Task {task.name} failed: {e}",
            error_code=ErrorCode.COMMAND_EXECUTION_ERROR,
        )
        task.fail(error)
        self.console.print(f"[red]💥 {task.name} crashed: {e}[/ red]")
        return False

    def display_task_tree(self) -> None:
        tree = Tree("🚀 Workflow Tasks")
        status_groups = self._get_status_groups()

        for status, (label, color) in status_groups.items():
            self._add_status_branch(tree, status, label, color)

        self.console.print(tree)

    def _get_status_groups(self) -> dict[TaskStatus, tuple[str, str]]:
        return {
            TaskStatus.SUCCESS: ("✅ Completed", "green"),
            TaskStatus.RUNNING: ("🔄 Running", "blue"),
            TaskStatus.FAILED: ("❌ Failed", "red"),
            TaskStatus.SKIPPED: ("⏭️ Skipped", "yellow"),
            TaskStatus.PENDING: ("⏳ Pending", "white"),
        }

    def _add_status_branch(
        self,
        tree: Tree,
        status: TaskStatus,
        label: str,
        color: str,
    ) -> None:
        status_tasks = [task for task in self.tasks.values() if task.status == status]

        if not status_tasks:
            return

        status_branch = tree.add(f"[{color}]{label}[/{color}]")
        for task in status_tasks:
            duration_str = f" ({task.duration: .1f}s)" if task.duration else ""
            status_branch.add(f"{task.name}{duration_str}")

    def get_workflow_summary(self) -> dict[str, int]:
        summary = {status.name.lower(): 0 for status in TaskStatus}

        for task in self.tasks.values():
            summary[task.status.name.lower()] += 1

        return summary


class InteractiveCLI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or depends.get_sync(Console)
        self.workflow = WorkflowManager(self.console)
        import logging

        self.logger = logging.getLogger("crackerjack.interactive.cli")

    def create_dynamic_workflow(self, options: InteractiveWorkflowOptions) -> None:
        builder = WorkflowBuilder(self.console)

        workflow_steps: list[t.Callable[[WorkflowBuilder, str], str]] = [
            self._add_setup_phase,
            self._add_config_phase,
            partial(self._add_cleaning_phase, enabled=options.clean),
            self._add_fast_hooks_phase,
            partial(self._add_testing_phase, enabled=options.test),
            self._add_comprehensive_hooks_phase,
            partial(
                self._add_version_phase,
                enabled=bool(options.publish or options.bump),
            ),
            partial(self._add_publish_phase, enabled=bool(options.publish)),
            partial(self._add_commit_phase, enabled=options.commit),
            partial(self._add_pr_phase, enabled=options.create_pr),
        ]

        last_task = ""
        for step in workflow_steps:
            last_task = step(builder, last_task)

        workflow_def = builder.build()
        self.workflow.load_workflow(workflow_def)

        self.logger.info(
            "Dynamic workflow created",
            extra={"task_count": len(workflow_def)},
        )

    def _add_setup_phase(self, builder: WorkflowBuilder, last_task: str) -> str:
        builder.add_task(
            "setup",
            "Initialize",
            "Initialize project structure",
            estimated_duration=2.0,
        )
        return "setup"

    def _add_config_phase(self, builder: WorkflowBuilder, last_task: str) -> str:
        builder.add_task(
            "config",
            "Configure",
            "Update configuration files",
            dependencies=[last_task],
            estimated_duration=3.0,
        )
        return "config"

    def _add_cleaning_phase(
        self,
        builder: WorkflowBuilder,
        last_task: str,
        enabled: bool,
    ) -> str:
        return (
            builder.add_conditional_task(
                condition=enabled,
                task_id="clean",
                name="Clean Code",
                description="Clean code (remove docstrings, comments)",
                dependencies=[last_task],
                estimated_duration=10.0,
            )
            or last_task
        )

    def _add_fast_hooks_phase(self, builder: WorkflowBuilder, last_task: str) -> str:
        builder.add_task(
            "fast_hooks",
            "Format",
            "Run formatting hooks",
            dependencies=[last_task],
            estimated_duration=15.0,
        )
        return "fast_hooks"

    def _add_testing_phase(
        self,
        builder: WorkflowBuilder,
        last_task: str,
        enabled: bool,
    ) -> str:
        return (
            builder.add_conditional_task(
                condition=enabled,
                task_id="test",
                name="Test",
                description="Run tests with coverage",
                dependencies=[last_task],
                estimated_duration=30.0,
            )
            or last_task
        )

    def _add_comprehensive_hooks_phase(
        self,
        builder: WorkflowBuilder,
        last_task: str,
    ) -> str:
        builder.add_task(
            "comprehensive_hooks",
            "Quality Check",
            "Run comprehensive hooks",
            dependencies=[last_task],
            estimated_duration=45.0,
        )
        return "comprehensive_hooks"

    def _add_version_phase(
        self,
        builder: WorkflowBuilder,
        last_task: str,
        enabled: bool,
    ) -> str:
        return (
            builder.add_conditional_task(
                condition=enabled,
                task_id="version",
                name="Version",
                description="Bump version",
                dependencies=[last_task],
                estimated_duration=5.0,
            )
            or last_task
        )

    def _add_publish_phase(
        self,
        builder: WorkflowBuilder,
        last_task: str,
        enabled: bool,
    ) -> str:
        return (
            builder.add_conditional_task(
                condition=enabled,
                task_id="publish",
                name="Publish",
                description="Publish package",
                dependencies=[last_task],
                estimated_duration=20.0,
            )
            or last_task
        )

    def _add_commit_phase(
        self,
        builder: WorkflowBuilder,
        last_task: str,
        enabled: bool,
    ) -> str:
        return (
            builder.add_conditional_task(
                condition=enabled,
                task_id="commit",
                name="Commit",
                description="Commit changes",
                dependencies=[last_task],
                estimated_duration=3.0,
            )
            or last_task
        )

    def _add_pr_phase(
        self,
        builder: WorkflowBuilder,
        last_task: str,
        enabled: bool,
    ) -> str:
        return (
            builder.add_conditional_task(
                condition=enabled,
                task_id="pr",
                name="Pull Request",
                description="Create pull request",
                dependencies=[last_task],
                estimated_duration=5.0,
            )
            or last_task
        )

    def run_interactive_workflow(self, options: InteractiveWorkflowOptions) -> bool:
        self.logger.info(
            f"Starting interactive workflow with options: {options.__dict__}",
        )
        self.create_dynamic_workflow(options)

        self.console.print("[bold blue]🚀 Starting Interactive Workflow[/ bold blue]")
        self.workflow.display_task_tree()

        if not Confirm.ask("Continue with workflow?"):
            self.console.print("[yellow]Workflow cancelled by user[/ yellow]")
            return False

        return self._execute_workflow_loop()

    def _execute_workflow_loop(self) -> bool:
        overall_success = True

        while not self.workflow.all_tasks_completed():
            next_task = self.workflow.get_next_task()

            if next_task is None:
                overall_success = self._handle_stuck_workflow()
                break

            if not self._should_run_task(next_task):
                continue

            success = self._execute_single_task(next_task)
            if not success:
                overall_success = False
                if not self._should_continue_after_failure():
                    break

        self._display_workflow_summary()
        return overall_success

    def _handle_stuck_workflow(self) -> bool:
        pending_tasks = [
            task
            for task in self.workflow.tasks.values()
            if task.status == TaskStatus.PENDING
        ]

        if pending_tasks:
            self.console.print("[red]❌ Workflow stuck-unresolved dependencies[/ red]")
            return False
        return True

    def _should_run_task(self, task: Task) -> bool:
        if not Confirm.ask(f"Run {task.name}?", default=True):
            task.skip()
            return False
        return True

    def _execute_single_task(self, task: Task) -> bool:
        return self.workflow.run_task(task)

    def _should_continue_after_failure(self) -> bool:
        return Confirm.ask("Continue despite failure?", default=True)

    def _display_workflow_summary(self) -> None:
        summary = self.workflow.get_workflow_summary()

        self.console.print("\n[bold]📊 Workflow Summary[/ bold]")

        from rich.panel import Panel

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Status", style="cyan")
        table.add_column("Count", justify="right")

        status_styles = {
            "success": "green",
            "failed": "red",
            "skipped": "yellow",
            "pending": "white",
        }

        for status, count in summary.items():
            if count > 0:
                style = status_styles.get(status, "white")
                table.add_row(f"[{style}]{status.title()}[/{style}]", str(count))

        self.console.print(
            Panel(table, title="Workflow Summary", border_style="magenta")
        )


def launch_interactive_cli(version: str, options: t.Any = None) -> None:
    console = depends.get_sync(Console)
    cli = InteractiveCLI(console)

    title = Text("Crackerjack", style="bold cyan")
    version_text = Text(f"v{version}", style="dim cyan")
    subtitle = Text("Your Python project management toolkit", style="italic")
    panel = Panel(
        f"{title} {version_text}\n{subtitle}",
        border_style="cyan",
        expand=False,
    )
    console.print(panel)
    console.print()

    workflow_options = (
        InteractiveWorkflowOptions.from_args(options)
        if options
        else InteractiveWorkflowOptions()
    )
    cli.create_dynamic_workflow(workflow_options)
    cli.run_interactive_workflow(workflow_options)


if __name__ == "__main__":
    launch_interactive_cli("0.19.8")
