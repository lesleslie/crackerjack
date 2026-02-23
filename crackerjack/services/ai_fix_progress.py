import asyncio
import logging
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from alive_progress import alive_bar
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

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


def _supports_color() -> bool:

    if os.environ.get("NO_COLOR", ""):
        return False

    if not hasattr(sys.stdout, "isatty"):
        return False

    return sys.stdout.isatty()


_COLOR_ENABLED = _supports_color()


class Neon:
    CYAN = "\033[96m" if _COLOR_ENABLED else ""
    MAGENTA = "\033[95m" if _COLOR_ENABLED else ""
    GREEN = "\033[92m" if _COLOR_ENABLED else ""
    YELLOW = "\033[93m" if _COLOR_ENABLED else ""
    RED = "\033[91m" if _COLOR_ENABLED else ""
    BLUE = "\033[94m" if _COLOR_ENABLED else ""
    WHITE = "\033[97m" if _COLOR_ENABLED else ""
    BOLD = "\033[1m" if _COLOR_ENABLED else ""
    DIM = "\033[2m" if _COLOR_ENABLED else ""
    RESET = "\033[0m" if _COLOR_ENABLED else ""


class AIFixProgressManager:
    def __init__(
        self,
        console: Console | None = None,
        enabled: bool = True,
        enable_agent_bars: bool = True,
        max_agent_bars: int = 5,
        activity_feed_size: int = 5,
        refresh_per_second: int = 1,
    ) -> None:
        self.console = console or Console()
        self.enabled = enabled
        self.enable_agent_bars = enable_agent_bars
        self.max_agent_bars = max_agent_bars
        self.activity_feed_size = activity_feed_size
        self.refresh_per_second = refresh_per_second

        self._bar_context: Any = None
        self._bar: Any = None
        self._in_progress: bool = False

        self.issue_history: list[int] = []
        self.current_iteration = 0
        self.stage = "fast"
        self.current_operation: str = ""

        self.hook_progress: dict[str, dict[str, str | int | float]] = {}
        self.hook_start_times: dict[str, float] = {}
        self.total_hooks: int = 0
        self.completed_hooks: int = 0

    def _render_header_panel(self, stage: str, initial_issues: int) -> None:
        header = Text()
        header.append("╔═══════════════════════════════════════╗\n", style="bold cyan")
        header.append("║  ", style="cyan")
        header.append("🤖 CRACKERJACK AI-ENGINE v2.0", style="bold white")
        header.append("  ║\n", style="cyan")
        header.append("╠═══════════════════════════════════════╣\n", style="cyan")
        header.append("║ ", style="cyan")
        header.append("Stage: ", style="dim")
        header.append(f"{stage.upper()}", style="bold cyan")
        header.append(" " * max(0, 25 - len(stage)), style="dim")
        header.append(" ║\n", style="cyan")
        if initial_issues > 0:
            header.append("║ ", style="cyan")
            header.append("Issues: ", style="dim")
            header.append(f"{initial_issues}", style="bold yellow")
            header.append(" " * max(0, 26 - len(str(initial_issues))), style="dim")
            header.append("║\n", style="cyan")
        header.append("╚═══════════════════════════════════════╝", style="cyan")
        self.console.print(header)

    def _render_footer_panel(self, success: bool) -> None:
        color = "green" if success else "yellow"

        initial = self.issue_history[0] if self.issue_history else 0
        current = self.issue_history[-1] if self.issue_history else 0
        reduction = ((initial - current) / initial * 100) if initial > 0 else 0

        footer = Text()
        footer.append(
            "╔═══════════════════════════════════════╗\n", style=f"bold {color}"
        )
        footer.append("║ ", style=color)
        if success:
            footer.append("✓ SESSION COMPLETE", style=f"bold {color}")
            footer.append("                    ║\n", style=color)
        else:
            footer.append("⚠ CONVERGENCE LIMIT", style=f"bold {color}")
            footer.append("              ║\n", style=color)
        footer.append("╠═══════════════════════════════════════╣\n", style=color)
        footer.append("║ ", style=color)
        footer.append("Issues: ", style="dim")
        footer.append(f"{initial} → {current}", style="bold")
        footer.append(
            "                   ║\n" if current < 10 else "                  ║\n",
            style=color,
        )
        footer.append("║ ", style=color)
        footer.append("Reduction: ", style="dim")
        footer.append(f"{reduction:.0f}%", style="bold")
        footer.append("                        ║\n", style=color)
        footer.append("║ ", style=color)
        footer.append("Iterations: ", style="dim")
        footer.append(f"{len(self.issue_history)}", style="bold")
        footer.append("                      ║\n", style=color)
        footer.append("╚═══════════════════════════════════════╝", style=color)
        self.console.print(footer)

    def _neon_print(self, status: str, agent: str, action: str, file: str) -> None:
        icon = AGENT_ICONS.get(agent, "🤖")
        agent_short = agent.replace("Agent", "")

        if status == "success":
            color = Neon.GREEN
            status_icon = "✓"
        elif status == "warning":
            color = Neon.YELLOW
            status_icon = "⚠"
        elif status == "error":
            color = Neon.RED
            status_icon = "✗"
        else:
            color = Neon.CYAN
            status_icon = "→"

        file_short = file.split("/")[-1] if "/" in file else file
        if len(file_short) > 30:
            file_short = "..." + file_short[-27:]

        print(
            f"{color}{status_icon} {icon} {agent_short}: {action} in {file_short}{Neon.RESET}"
        )

    def start_comprehensive_hooks_session(
        self,
        hook_names: list[str],
    ) -> None:
        if not self.enabled:
            return

        self.stage = "comprehensive"
        self.total_hooks = len(hook_names)
        self.completed_hooks = 0
        self.hook_progress = {}
        self.hook_start_times = {}

        header = Panel(
            f"[bold cyan]🔍 COMPREHENSIVE HOOKS[/bold cyan]\n"
            f"[dim]Running {self.total_hooks} quality checks...[/dim]",
            border_style="cyan",
            padding=(0, 2),
        )
        self.console.print(header)

    def update_hook_progress(
        self,
        hook_name: str,
        status: str,
        elapsed: float,
        issues_found: int = 0,
    ) -> None:
        if not self.enabled:
            return

        self.hook_progress[hook_name] = {
            "status": status,
            "elapsed": elapsed,
            "issues": issues_found,
        }

        if status in ("completed", "failed", "timeout"):
            self.completed_hooks += 1

        status_icon = {
            "completed": "✅",
            "failed": "❌",
            "timeout": "⏱️",
            "running": "🔄",
        }.get(status, "⏳")

        elapsed_str = f"{elapsed:.1f}s"
        issues_str = f"| {issues_found} issues" if issues_found > 0 else ""
        progress_pct = (
            int((self.completed_hooks / self.total_hooks) * 100)
            if self.total_hooks > 0
            else 0
        )

        self.console.print(
            f"  {status_icon} {hook_name} [{elapsed_str}] {issues_str} "
            f"[{self.completed_hooks}/{self.total_hooks} hooks, {progress_pct}% complete]"
        )

    def get_hook_summary(self) -> dict[str, Any]:
        return {
            "total": self.total_hooks,
            "completed": self.completed_hooks,
            "progress": int((self.completed_hooks / self.total_hooks) * 100)
            if self.total_hooks > 0
            else 0,
            "hooks": self.hook_progress.copy(),
        }

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

        self._render_header_panel(stage, initial_issue_count)

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

        self._in_progress = True

    def update_iteration_progress(
        self,
        iteration: int,
        issues_remaining: int,
        no_progress_count: int = 0,
    ) -> None:
        if not self.enabled:
            return

        if issues_remaining > 0:
            if not self.issue_history or self.issue_history[-1] != issues_remaining:
                self.issue_history.append(issues_remaining)

    def end_iteration(self) -> None:
        if not self.enabled:
            return

        self._in_progress = False

    def log_event(
        self,
        agent: str,
        action: str,
        file: str,
        severity: str = "info",
    ) -> None:
        if not self.enabled:
            return

        # Skip verbose output when progress bar is active
        # The progress bar itself shows the status
        if self._in_progress:
            return

        self._neon_print(severity, agent, action, file)

    async def async_log_event(
        self,
        agent: str,
        action: str,
        file: str,
        severity: str = "info",
    ) -> None:
        if not self.enabled:
            return

        # Skip verbose output when progress bar is active
        if self._in_progress:
            return

        await asyncio.sleep(0)
        self._neon_print(severity, agent, action, file)

    def start_agent_bars(self, agent_names: list[str]) -> None:
        pass

    def update_agent_progress(
        self,
        agent_name: str,
        completed: int,
        total: int,
        current_file: str | None = None,
        current_issue_type: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        if current_file and current_issue_type:
            severity = "success" if "fixed" in current_issue_type.lower() else "info"
            self.log_event(agent_name, current_issue_type, current_file, severity)

    def end_agent_bars(self) -> None:
        pass

    def finish_session(self, success: bool = True, message: str = "") -> None:
        if not self.enabled:
            return

        self.end_iteration()

        self._render_footer_panel(success)

        if self.issue_history:
            history_str = " → ".join(str(n) for n in self.issue_history)
            self.console.print(f"[dim]History: {history_str}[/dim]")

    def is_enabled(self) -> bool:
        return self.enabled

    def is_in_progress(self) -> bool:
        return self._in_progress

    def should_skip_console_print(self) -> bool:
        return self._in_progress

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    @contextmanager
    def progress_context(
        self,
        total: int,
        title: str = "AI-FIX",
    ) -> Generator[Any]:
        if not self.enabled:
            yield None
            return

        # Print neon separator before progress bar
        print(f"{Neon.CYAN}{'━' * 50}{Neon.RESET}")

        with alive_bar(
            total,
            title=f"⚡ {title}",
            enrich_print=False,  # Don't intercept prints - we control output
            force_tty=True,
            bar="smooth",  # Smooth filled bar
            length=40,
            receipt_text=True,
            receipt=False,  # Don't show final receipt line
        ) as bar:
            self._bar = bar
            self._in_progress = True
            try:
                yield bar
            finally:
                self._bar = None
                self._in_progress = False

        # Print completion with neon style
        print(f"{Neon.GREEN}{'━' * 50}{Neon.RESET}")

    def update_bar_text(self, text: str) -> None:
        """Update the progress bar text to show current operation."""
        if self._bar is not None:
            # Truncate long file paths
            if len(text) > 45:
                text = "..." + text[-42:]
            # Clean text for alive_progress (no ANSI codes)
            self._bar.text(f"📄 {text}")


ActivityEvent = tuple
