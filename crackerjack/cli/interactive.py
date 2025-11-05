import time
import typing as t
from enum import Enum, auto

from acb.console import Console
from acb.depends import depends
from rich.box import ROUNDED
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.errors import CrackerjackError, ErrorCode, handle_error
from crackerjack.models.protocols import OptionsProtocol


class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


class InteractiveTask:
    def __init__(
        self,
        name: str,
        description: str,
        phase_method: str,
        dependencies: list["InteractiveTask"] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.phase_method = phase_method
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


class InteractiveWorkflowManager:
    def __init__(self, console: Console, orchestrator: WorkflowOrchestrator) -> None:
        self.console = console
        self.orchestrator = orchestrator
        self.tasks: dict[str, InteractiveTask] = {}
        self.current_task: InteractiveTask | None = None
        self.layout = Layout()
        self._setup_layout()

    def _setup_layout(self) -> None:
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )
        self.layout["main"].split_row(
            Layout(name="tasks", minimum_size=40),
            Layout(name="details", ratio=2),
        )

    def setup_workflow(self, options: OptionsProtocol) -> None:
        self.tasks.clear()
        self._setup_cleaning_task(options)
        self._setup_hooks_task(options)
        self._setup_testing_task(options)
        self._setup_publishing_task(options)
        self._setup_commit_task(options)

    def _setup_cleaning_task(self, options: OptionsProtocol) -> None:
        if options.clean:
            self.add_task(
                "cleaning",
                "Clean code (remove docstrings, comments)",
                "run_cleaning_phase",
            )

    def _setup_hooks_task(self, options: OptionsProtocol) -> None:
        if not options.skip_hooks:
            deps = ["cleaning"] if options.clean else []
            self.add_task(
                "hooks",
                "Run quality hooks (fast + comprehensive)",
                "run_hooks_phase",
                dependencies=deps,
            )

    def _setup_testing_task(self, options: OptionsProtocol) -> None:
        if options.test:
            deps = (
                ["hooks"]
                if not options.skip_hooks
                else (["cleaning"] if options.clean else [])
            )
            self.add_task(
                "testing",
                "Run tests with coverage",
                "run_testing_phase",
                dependencies=deps,
            )

    def _setup_publishing_task(self, options: OptionsProtocol) -> None:
        if options.publish or options.all or options.bump:
            all_deps = self._get_publishing_dependencies()
            self.add_task(
                "publishing",
                "Version bump and publish to PyPI",
                "run_publishing_phase",
                dependencies=all_deps,
            )

    def _setup_commit_task(self, options: OptionsProtocol) -> None:
        if options.commit:
            all_deps = list[t.Any](self.tasks.keys())
            self.add_task(
                "commit",
                "Commit changes and push to Git",
                "run_commit_phase",
                dependencies=all_deps[:-1] if all_deps else [],
            )

    def _get_publishing_dependencies(self) -> list[str]:
        if "testing" in self.tasks:
            return ["testing"]
        elif "hooks" in self.tasks:
            return ["hooks"]
        elif "cleaning" in self.tasks:
            return ["cleaning"]
        return []

    def add_task(
        self,
        name: str,
        description: str,
        phase_method: str,
        dependencies: list[str] | None = None,
    ) -> InteractiveTask:
        dep_tasks: list[InteractiveTask] = []
        if dependencies:
            for dep_name in dependencies:
                if dep_name not in self.tasks:
                    msg = f"Dependency task '{dep_name}' not found"
                    raise ValueError(msg)
                dep_tasks.append(self.tasks[dep_name])

        task = InteractiveTask(name, description, phase_method, dep_tasks)
        self.tasks[name] = task
        return task

    def get_next_task(self) -> InteractiveTask | None:
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING and task.can_run():
                return task
        return None

    def execute_task(self, task: InteractiveTask, options: OptionsProtocol) -> bool:
        self.current_task = task
        task.start()
        try:
            phase_method = getattr(self.orchestrator, task.phase_method)
            success_result = phase_method(options)
            success_bool = bool(success_result)
            task.complete(success_bool)
            return success_bool
        except Exception as e:
            error = CrackerjackError(
                message=str(e),
                error_code=ErrorCode.COMMAND_EXECUTION_ERROR,
            )
            task.fail(error)
            return False
        finally:
            self.current_task = None

    def create_task_tree(self) -> Tree:
        tree = Tree("🔧 Workflow Tasks")
        for task in self.tasks.values():
            status_emoji = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.RUNNING: "🔄",
                TaskStatus.SUCCESS: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.SKIPPED: "⏭️",
            }
            emoji = status_emoji.get(task.status, "❓")
            label = f"{emoji} {task.name}"
            if task.duration is not None:
                label += f" ({task.duration: .1f}s)"
            task_node = tree.add(label)
            task_node.add(f"📝 {task.description}")
            if task.error:
                task_node.add(f"❌ {task.error.message}")

        return tree

    def create_details_panel(self) -> Panel:
        if self.current_task is None:
            content = Text("No task currently running", style="dim")
        else:
            task = self.current_task
            content = Text()
            content.append(f"🔄 Running: {task.name}\n", style="bold cyan")
            content.append(f"📝 {task.description}\n")
            if task.duration is not None:
                content.append(f"⏱️ Duration: {task.duration: .1f}s\n")
            if task.dependencies:
                content.append("\n📋 Dependencies: \n", style="bold")
                for dep in task.dependencies:
                    status_emoji = "✅" if dep.status == TaskStatus.SUCCESS else "❌"
                    content.append(f" {status_emoji} {dep.name}\n")

        return Panel(content, title="Current Task", border_style="cyan")

    def create_header(self, pkg_version: str) -> Panel:
        header_text = Text()
        header_text.append("🚀 Crackerjack Interactive Mode ", style="bold cyan")
        header_text.append(f"v{pkg_version}", style="dim")

        return Panel(header_text, style="cyan")

    def create_footer(self) -> Panel:
        footer_text = Text()
        footer_text.append("Press ", style="dim")
        footer_text.append("Ctrl + C", style="bold red")
        footer_text.append(" to cancel • ", style="dim")
        footer_text.append("Enter", style="bold green")
        footer_text.append(" to continue", style="dim")

        return Panel(footer_text, style="green")

    def update_layout(self, pkg_version: str) -> None:
        self.layout["header"].update(self.create_header(pkg_version))
        self.layout["tasks"].update(
            Panel(self.create_task_tree(), title="Tasks", border_style="blue"),
        )
        self.layout["details"].update(self.create_details_panel())
        self.layout["footer"].update(self.create_footer())

    def run_workflow(self, options: OptionsProtocol, pkg_version: str) -> bool:
        if not self._initialize_workflow(options, pkg_version):
            return False

        with Live(self.layout) as live:
            if not self._execute_workflow_tasks(live, options, pkg_version):
                return False

        return self._finalize_workflow()

    def _initialize_workflow(self, options: OptionsProtocol, pkg_version: str) -> bool:
        self.setup_workflow(options)
        if not self.tasks:
            self.console.print(
                "[yellow]⚠️ No tasks to execute based on options[/ yellow]",
            )
            return True

        self.update_layout(pkg_version)
        self.console.print(self.layout)

        if not Confirm.ask("\n🚀 Start workflow?", default=True):
            self.console.print("[yellow]⏹️ Workflow cancelled[/ yellow]")
            return False

        return True

    def _execute_workflow_tasks(
        self,
        live: Live,
        options: OptionsProtocol,
        pkg_version: str,
    ) -> bool:
        while True:
            next_task = self.get_next_task()
            if next_task is None:
                break

            self.update_layout(pkg_version)
            live.update(self.layout)

            success = self.execute_task(next_task, options)
            self.update_layout(pkg_version)
            live.update(self.layout)

            if not success and not self._handle_task_failure(live, next_task):
                return False

        return True

    def _handle_task_failure(self, live: Live, failed_task: InteractiveTask) -> bool:
        live.stop()
        retry = Confirm.ask(
            f"\n❌ Task '{failed_task.name}' failed. Continue anyway?",
            default=False,
        )

        if not retry:
            self.console.print("[red]⏹️ Workflow stopped due to task failure[/ red]")
            return False

        failed_task.skip()
        live.start()
        return True

    def _finalize_workflow(self) -> bool:
        self.show_final_results()

        success_count = sum(
            1 for task in self.tasks.values() if task.status == TaskStatus.SUCCESS
        )
        total_tasks = len(self.tasks)

        return success_count == total_tasks or all(
            task.status in (TaskStatus.SUCCESS, TaskStatus.SKIPPED)
            for task in self.tasks.values()
        )

    def show_final_results(self) -> None:
        success_count = sum(
            1 for task in self.tasks.values() if task.status == TaskStatus.SUCCESS
        )
        failed_count = sum(
            1 for task in self.tasks.values() if task.status == TaskStatus.FAILED
        )
        skipped_count = sum(
            1 for task in self.tasks.values() if task.status == TaskStatus.SKIPPED
        )
        table = Table(title="📊 Workflow Results", box=ROUNDED)
        table.add_column("Task", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Details")
        for task in self.tasks.values():
            status_styles = {
                TaskStatus.SUCCESS: "green",
                TaskStatus.FAILED: "red",
                TaskStatus.SKIPPED: "yellow",
                TaskStatus.PENDING: "dim",
                TaskStatus.RUNNING: "cyan",
            }
            status_text = task.status.name
            style = status_styles.get(task.status, "white")
            duration_text = f"{task.duration: .1f}s" if task.duration else "-"
            details = task.error.message if task.error else task.description
            table.add_row(
                task.name,
                f"[{style}]{status_text}[/{style}]",
                duration_text,
                details,
            )
        from rich.panel import Panel

        self.console.print("\n")
        self.console.print(Panel(table, border_style="magenta"))
        if failed_count == 0:
            self.console.print(
                f"\n[bold green]🎉 Workflow completed ! {success_count} / {len(self.tasks)} tasks successful[/ bold green]",
            )
        else:
            self.console.print(
                f"\n[bold yellow]⚠️ Workflow completed with issues: {failed_count} failed, {skipped_count} skipped[/ bold yellow]",
            )


class InteractiveCLI:
    def __init__(self, pkg_version: str, console: Console | None = None) -> None:
        self.pkg_version = pkg_version
        self.console = console or depends.get_sync(Console)
        self.orchestrator = WorkflowOrchestrator()
        self.workflow_manager = InteractiveWorkflowManager(
            self.console,
            self.orchestrator,
        )

    def launch(self, options: OptionsProtocol) -> None:
        try:
            self._show_welcome()
            updated_options = self._get_user_preferences(options)
            success = self.workflow_manager.run_workflow(
                updated_options,
                self.pkg_version,
            )
            if not success:
                raise SystemExit(1)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⏹️ Interactive session cancelled[/ yellow]")
            raise SystemExit(130)
        except Exception as e:
            error = CrackerjackError(
                message=str(e),
                error_code=ErrorCode.UNEXPECTED_ERROR,
            )
            handle_error(error, self.console)
            raise SystemExit(1)

    def _show_welcome(self) -> None:
        welcome_panel = Panel(
            f"[bold cyan]Welcome to Crackerjack Interactive Mode ! [/ bold cyan]\n\n"
            f"Version: {self.pkg_version}\n"
            f"This interactive interface will guide you through the crackerjack workflow\n"
            f"with real-time feedback and customizable options.",
            title="🚀 Crackerjack Interactive",
            border_style="cyan",
        )
        self.console.print(welcome_panel)
        self.console.print()

    def _get_user_preferences(self, options: OptionsProtocol) -> OptionsProtocol:
        self.console.print("[bold]🔧 Workflow Configuration[/ bold]")
        self.console.print("Configure your crackerjack workflow: \n")
        updated_options = type(options)(**vars(options))
        updated_options.clean = Confirm.ask(
            "🧹 Clean code (remove docstrings, comments)?",
            default=options.clean,
        )
        updated_options.test = Confirm.ask("🧪 Run tests?", default=options.test)

        # Only ask about commit if not explicitly set via command line
        # Check if commit was explicitly provided by looking at original vs default
        from ..cli.options import Options

        default_options = Options()
        if options.commit != default_options.commit:
            # Command line flag was used, preserve it
            self.console.print(f"📝 Using command line flag: --commit={options.commit}")
            updated_options.commit = options.commit  # Preserve the command line value
        else:
            # No command line flag, ask user
            updated_options.commit = Confirm.ask(
                "📝 Commit changes to git?",
                default=options.commit,
            )
        if not any([options.publish, options.all, options.bump]):
            if Confirm.ask("📦 Bump version and publish?", default=False):
                version_type = Prompt.ask(
                    "Version bump type",
                    choices=["patch", "minor", "major", "interactive"],
                    default="patch",
                )
                updated_options.publish = version_type
        if Confirm.ask("\n⚙️ Configure advanced options?", default=False):
            updated_options.verbose = Confirm.ask(
                "Enable verbose output?",
                default=options.verbose,
            )
        self.console.print()
        return updated_options


def launch_interactive_cli(pkg_version: str, options: OptionsProtocol) -> None:
    cli = InteractiveCLI(pkg_version)
    cli.launch(options)
