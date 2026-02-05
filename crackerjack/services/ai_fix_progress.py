import logging
from contextlib import suppress
from pathlib import Path
from typing import Any

from alive_progress import alive_bar, config_handler
from rich.console import Console
from rich.panel import Panel

config_handler.set_global(
    theme="smooth",
    bar="smooth",
    spinner="waves",
    stats="false",
    force_tty=True,
    enrich_print=False,
)

logger = logging.getLogger(__name__)


AGENT_ICONS = {
    "RefactoringAgent": "🔧",
    "SecurityAgent": "🔒",
    "PerformanceAgent": "⚡",
    "FormattingAgent": "✨",
    "TestCreationAgent": "🧪",
    "TestSpecialistAgent": "🔬",
    "DocumentationAgent": "📝",
    "DRYAgent": "🔄",
    "ImportOptimizationAgent": "📦",
    "SemanticAgent": "🧠",
    "ArchitectAgent": "🏗️",
    "EnhancedProactiveAgent": "🔮",
}


class AIFixProgressManager:
    def __init__(
        self,
        console: Console | None = None,
        enabled: bool = True,
        enable_agent_bars: bool = False,
        max_agent_bars: int = 5,
    ) -> None:
        self.console = console or Console()
        self.enabled = enabled
        self.enable_agent_bars = enable_agent_bars
        self.max_agent_bars = max_agent_bars

        self.iteration_bar: Any = None
        self.agent_bars: dict[str, Any] = {}
        self.issue_history: list[int] = []
        self.current_iteration = 0
        self.stage = "fast"
        self.current_operation: str = ""

    def start_fix_session(
        self,
        stage: str = "fast",
        initial_issue_count: int = 0,
    ) -> None:
        if not self.enabled:
            return

        self.stage = stage
        self.current_iteration = 0
        self.issue_history = [initial_issue_count] if initial_issue_count > 0 else []

        self._print_stage_header(stage, initial_issue_count)

    def start_iteration(
        self,
        iteration: int,
        issue_count: int,
    ) -> None:
        if not self.enabled:
            return

        self.current_iteration = iteration

        if issue_count > 0:
            self.issue_history.append(issue_count)

        title = f"🤖 AI-FIX STAGE: {self.stage.upper()}"
        self.iteration_bar = alive_bar(
            total=100,
            title=title,
            title_length=50,
            manual=True,
            enrich_print=False,
            force_tty=True,
            stats=False,
        )

        self.iteration_bar = self.iteration_bar.__enter__()

        with suppress(Exception):
            self.iteration_bar(0)

        self._update_iteration_display(iteration, issue_count, 0)

    def update_iteration_progress(
        self,
        iteration: int,
        issues_remaining: int,
        no_progress_count: int = 0,
    ) -> None:
        if not self.enabled or not self.iteration_bar:
            return

        if issues_remaining > 0:
            if not self.issue_history or self.issue_history[-1] != issues_remaining:
                self.issue_history.append(issues_remaining)

        if self.issue_history:
            initial_issues = self.issue_history[0]
            issues_fixed = initial_issues - issues_remaining
            reduction_pct = (
                int((issues_fixed / initial_issues) * 100) if initial_issues > 0 else 0
            )
        else:
            reduction_pct = 0

        if self.iteration_bar:
            with suppress(Exception):
                self.iteration_bar(reduction_pct)

        self._update_iteration_display(iteration, issues_remaining, no_progress_count)

    def end_iteration(self) -> None:
        if not self.enabled or not self.iteration_bar:
            return

        with suppress(Exception):
            self.iteration_bar(100)

        self.iteration_bar = None

        if self.enable_agent_bars:
            self.end_agent_bars()

    def start_agent_bars(self, agent_names: list[str]) -> None:
        if not self.enabled or not self.enable_agent_bars:
            return

        limited_agents = agent_names[: self.max_agent_bars]

        for agent_name in limited_agents:
            if agent_name not in self.agent_bars:
                icon = AGENT_ICONS.get(agent_name, "🤖")
                bar = alive_bar(
                    total=100,
                    title=f"{icon} {agent_name}",
                    title_length=40,
                    manual=True,
                    enrich_print=False,
                )
                self.agent_bars[agent_name] = bar.__enter__()

    def update_agent_progress(
        self,
        agent_name: str,
        completed: int,
        total: int,
        current_file: str | None = None,
        current_issue_type: str | None = None,
    ) -> None:
        if not self.enabled or not self.enable_agent_bars:
            return

        if agent_name not in self.agent_bars:
            self.start_agent_bars([agent_name])

        if total > 0:
            pct = (completed / total) * 100
        else:
            pct = 100

        if agent_name in self.agent_bars:
            with suppress(Exception):
                self.agent_bars[agent_name](pct)

        if current_file or current_issue_type:
            self._print_current_operation(agent_name, current_file, current_issue_type)

    def end_agent_bars(self) -> None:
        if not self.enabled:
            return

        for bar in self.agent_bars.values():
            with suppress(Exception):
                bar(100)

        self.agent_bars.clear()
        self.current_operation = ""

    def _print_current_operation(
        self,
        agent_name: str,
        current_file: str | None,
        current_issue_type: str | None,
    ) -> None:
        if not current_file and not current_issue_type:
            return

        icon = AGENT_ICONS.get(agent_name, "🤖")

        short_file = ""
        if current_file:
            short_file = current_file

            with suppress(Exception):
                cwd = str(Path.cwd())
                if current_file.startswith(cwd):
                    short_file = "." + current_file[len(cwd) :]

            if len(short_file) > 50:
                short_file = "..." + short_file[-47:]

        if current_file and current_issue_type:
            operation = f"{icon} Processing: {current_issue_type} → {agent_name}\n    File: {short_file}"
        elif current_file:
            operation = f"{icon} Processing: {agent_name}\n    File: {short_file}"
        elif current_issue_type:
            operation = f"{icon} Processing: {current_issue_type} → {agent_name}"
        else:
            return

        self.console.print(f"  {operation}")

    def finish_session(self, success: bool = True, message: str = "") -> None:
        if not self.enabled:
            return

        self.end_iteration()

        if success:
            reduction_pct = self._calculate_reduction()
            self.console.print(
                f"[green]✓ All issues resolved![/green] "
                f"({reduction_pct:.0f}% reduction in {len(self.issue_history)} iterations)"
            )
        else:
            self.console.print(
                f"[yellow]⚠ Convergence limit reached[/yellow] {message}"
            )

        if self.issue_history:
            self._print_final_summary()

    def _print_stage_header(self, stage: str, initial_count: int) -> None:
        stage_upper = stage.upper()

        header_text = (
            f"[bold cyan]🤖 AI-FIX STAGE: {stage_upper}[/bold cyan]\n"
            f"[dim]Initializing AI agents...[/dim]"
        )

        if initial_count > 0:
            header_text += f"\n[dim]Detected {initial_count} issues[/dim]"

        panel = Panel(
            header_text,
            border_style="cyan",
            padding=(0, 2),
        )

        self.console.print(panel)

    def _update_iteration_display(
        self,
        iteration: int,
        issues_remaining: int,
        no_progress_count: int,
    ) -> None:

        if self.issue_history:
            history_str = " → ".join(str(count) for count in self.issue_history)
            reduction_pct = self._calculate_reduction()
            issues_line = f"Issues: {history_str}  ({reduction_pct:.0f}% reduction)"
        else:
            issues_line = "No issues detected"

        if no_progress_count == 0:
            convergence_str = "✓ Converging"
        elif no_progress_count < 3:
            convergence_str = f"⚠ {no_progress_count}/3 no progress"
        else:
            convergence_str = "⚠ Convergence limit reached"

        self.console.print(f"  {issues_line}")
        self.console.print(f"  Iteration {iteration} | {convergence_str}")

    def _calculate_reduction(self) -> float:
        if len(self.issue_history) < 2:
            return 0.0

        start = self.issue_history[0]
        current = self.issue_history[-1]

        if start == 0:
            return 0.0

        return ((start - current) / start) * 100

    def _print_final_summary(self) -> None:
        start = self.issue_history[0]
        end = self.issue_history[-1]
        iterations = len(self.issue_history)

        self.console.print()
        self.console.print(f"[dim]  Started with: {start} issues[/dim]")
        self.console.print(f"[dim]  Finished with: {end} issues[/dim]")
        self.console.print(f"[dim]  Iterations: {iterations}[/dim]")
        self.console.print()

    def is_enabled(self) -> bool:
        return self.enabled

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

        if self.iteration_bar:
            self.iteration_bar()
            self.iteration_bar = None
