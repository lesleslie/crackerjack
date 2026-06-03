from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import Any

import rich.box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from crackerjack.config import get_console_width

logger = logging.getLogger(__name__)


AGENT_ICONS = {
    "RefactoringAgent": "🔧",
    "SecurityAgent": "🔒",
    "PerformanceAgent": "⚡",
    "FormattingAgent": "✨",
    "FixerCoordinator": "🛠️",
    "TestCreationAgent": "🧪",
    "TestSpecialistAgent": "🔬",
    "DocumentationAgent": "📝",
    "DocAgent": "📝",
    "DRYAgent": "🔄",
    "ImportOptimizationAgent": "📦",
    "SemanticAgent": "🧠",
    "ArchitectAgent": "🏗️",
    "EnhancedProactiveAgent": "🔮",
    "TypeErrorSpecialist": "🔎",
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
        self._fix_session_started: bool = False

        self.issue_history: list[int] = []
        self.current_iteration = 0
        self.stage = "fast"
        self.current_operation: str = ""

        self.hook_progress: dict[str, dict[str, str | int | float]] = {}
        self.hook_start_times: dict[str, float] = {}
        self.total_hooks: int = 0
        self.completed_hooks: int = 0

    def _render_header_panel(self, stage: str, initial_issues: int) -> None:
        table = Table(box=rich.box.SIMPLE, show_header=False, padding=0)
        table.add_column("left", width=1)
        table.add_column("right", width=38)

        table.add_row("║", "[bold white]🤖 CRACKERJACK AI-ENGINE v2.0[/]")
        table.add_row("║", "")
        table.add_row("║", f"[dim]Stage:[/dim] [bold cyan]{stage.upper()}[/]")
        if initial_issues > 0:
            table.add_row("║", f"[dim]Issues:[/dim] [bold yellow]{initial_issues}[/]")

        panel = Panel(
            table,
            border_style="cyan",
            padding=0,
            width=min(42, get_console_width()),
        )
        self.console.print(panel)

    def _render_footer_panel(self, success: bool) -> None:
        color = "green" if success else "yellow"

        initial = self.issue_history[0] if self.issue_history else 0
        current = (
            0 if success else (self.issue_history[-1] if self.issue_history else 0)
        )
        reduction = ((initial - current) / initial * 100) if initial > 0 else 0

        title = "Session Completed" if success else "Convergence Limit"

        iteration_count = getattr(self, "_last_iteration_count", len(self.issue_history))

        table = Table(box=rich.box.SIMPLE, show_header=False, padding=0)
        table.add_column("left", width=1)
        table.add_column("right", width=38)

        table.add_row("║", f"[dim]Issues:[/dim] [bold]{initial} → {current}[/]")
        table.add_row("║", f"[dim]Reduction:[/dim] [bold]{reduction:.0f}%[/]")
        table.add_row("║", f"[dim]Iterations:[/dim] [bold]{iteration_count}[/]")

        panel = Panel(
            table,
            title=f"[bold {color}]{title}[/]",
            border_style=color,
            padding=0,
            width=min(42, get_console_width()),
        )
        self.console.print(panel)

    def _neon_print(
        self,
        status: str,
        agent: str,
        action: str,
        file: str | object,
        issue_type: str = "",
    ) -> None:
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

        file_text = str(file)
        file_short = file_text.split("/")[-1] if "/" in file_text else file_text
        if len(file_short) > 30:
            file_short = "..." + file_short[-27:]

        # Suppress type_label when it would duplicate the agent name suffix
        # e.g. "Documentation [documentation]" → "Documentation"
        type_label = ""
        if issue_type:
            type_lower = issue_type.lower()
            agent_lower = agent_short.lower()
            if not (
                agent_lower.endswith(type_lower) or type_lower.endswith(agent_lower)
            ):
                type_label = f" [{issue_type}]"

        self.console.print(
            f"{color}{status_icon} {icon} {agent_short}{type_label}: {action} in {file_short}{Neon.RESET}"
        )

    def log_warning(self, message: str) -> None:
        if not self.enabled:
            return
        self.console.print(f"{Neon.YELLOW}⚠ {message}{Neon.RESET}")

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
            box=rich.box.SIMPLE,
            padding=(0, 1),
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
            f" {status_icon} {hook_name} [{elapsed_str}] {issues_str} "
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

    def compute_hook_total(self, hook_results: Sequence[object]) -> int:
        """Sum issues_count across non-config-error hook results.

        Matches the Comprehensive Hooks table: config errors (e.g. semgrep
        "error" status with is_config_error=True) are excluded so the panel
        and the table never disagree.
        """
        total = 0
        for result in hook_results:
            if getattr(result, "is_config_error", False):
                continue
            if hasattr(result, "issues_count"):
                total += getattr(result, "issues_count", 0) or 0
        return total

    def start_fix_session(
        self,
        stage: str = "fast",
        initial_issue_count: int = 0,
    ) -> None:
        if not self.enabled:
            return

        # Guard against re-entry: only the first call prints the header panel.
        # Subsequent calls (e.g. from retry paths) are silently ignored.
        if self._fix_session_started:
            return

        self._fix_session_started = True
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
        file: str | object,
        severity: str = "info",
        issue_type: str = "",
    ) -> None:
        if not self.enabled:
            return

        self._neon_print(severity, agent, action, file, issue_type=issue_type)

    async def async_log_event(
        self,
        agent: str,
        action: str,
        file: str | object,
        severity: str = "info",
        issue_type: str = "",
    ) -> None:
        if not self.enabled:
            return

        await asyncio.sleep(0)
        self._neon_print(severity, agent, action, file, issue_type=issue_type)

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

    def finish_session(
        self,
        success: bool = True,
        message: str = "",
        iteration_count: int | None = None,
    ) -> None:
        if not self.enabled:
            return

        self.end_iteration()

        self._last_iteration_count = (
            iteration_count
            if iteration_count is not None
            else len(self.issue_history)
        )

        self.console.print()
        self._render_footer_panel(success)
        self.console.print()

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

        yield None

    def update_bar_text(self, text: str | object) -> None:
        if self._bar is not None:
            text_str = str(text) if not isinstance(text, str) else text
            if len(text_str) > 45:
                text_str = "..." + text_str[-42:]
            self._bar.text(f"📄 {text_str}")


ActivityEvent = tuple
