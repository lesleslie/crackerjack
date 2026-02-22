"""
AI-Fix Progress Manager with alive-progress + Rich panels hybrid.

Uses alive-progress for the progress bar (with enrich_print for simultaneous logging)
and Rich for the cyberpunk-styled header/footer panels.

This approach eliminates the hangs caused by Rich's Live display while providing
a futuristic, log-friendly experience for the AI-fix stage.
"""

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


# Agent icons for display
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
    """Check if terminal supports ANSI colors (NO_COLOR + TTY detection)."""
    # NO_COLOR environment variable (https://no-color.org/)
    if os.environ.get("NO_COLOR", ""):
        return False

    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty"):
        return False

    return sys.stdout.isatty()


# Cache color support at module level
_COLOR_ENABLED = _supports_color()


# Neon ANSI color codes for messages (respects NO_COLOR and TTY)
class Neon:
    """Neon color codes that respect NO_COLOR and TTY detection."""

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
    """
    AI-Fix progress manager using alive-progress + Rich panels.

    Key features:
    - Rich panels for cyberpunk-styled header/footer
    - alive-progress with enrich_print for simultaneous logging
    - Neon color scheme for agent messages
    - No Rich Live = no hangs, CTRL-C works reliably

    The enrich_print feature allows print() statements to appear
    above the progress bar with position tracking ("on N:").
    """

    def __init__(
        self,
        console: Console | None = None,
        enabled: bool = True,
        enable_agent_bars: bool = True,
        max_agent_bars: int = 5,
        activity_feed_size: int = 5,
        refresh_per_second: int = 1,
    ) -> None:
        # TODO: Refactor self.console = console or Console()
        self.console = console or Console()
        self.enabled = enabled
        self.enable_agent_bars = enable_agent_bars
        self.max_agent_bars = max_agent_bars
        self.activity_feed_size = activity_feed_size
        self.refresh_per_second = refresh_per_second

        # Progress state
        self._bar_context: Any = None
        self._bar: Any = None
        self._in_progress: bool = False

        # Session state
        self.issue_history: list[int] = []
        self.current_iteration = 0
        self.stage = "fast"
        self.current_operation: str = ""

        # Hook progress (for comprehensive hooks display)
        self.hook_progress: dict[str, dict[str, str | int | float]] = {}
        self.hook_start_times: dict[str, float] = {}
        self.total_hooks: int = 0
        self.completed_hooks: int = 0

    # =========================================================================
    # Rich Panel Rendering
    # =========================================================================

    def _render_header_panel(self, stage: str, initial_issues: int) -> None:
        """Render cyberpunk-styled header panel using Rich."""
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
        """Render cyberpunk-styled footer panel using Rich."""
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
# TODO: Refactor footer.append(f"{len(self.issue_history)}", style="bold")
        footer.append(f"{len(self.issue_history)}", style="bold")
        footer.append("                      ║\n", style=color)
        footer.append("╚═══════════════════════════════════════╝", style=color)
        self.console.print(footer)

    # =========================================================================
    # Neon-Colored Print for alive-progress
    # =========================================================================

    def _neon_print(self, status: str, agent: str, action: str, file: str) -> None:
        """Print a neon-colored message that appears above the progress bar."""
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

        # Truncate file path
        file_short = file.split("/")[-1] if "/" in file else file
        if len(file_short) > 30:
            file_short = "..." + file_short[-27:]

        print(
            f"{color}{status_icon} {icon} {agent_short}: {action} in {file_short}{Neon.RESET}"
        )

    # =========================================================================
    # Session Management
    # =========================================================================

    def start_comprehensive_hooks_session(
        self,
        hook_names: list[str],
    ) -> None:
        """Start a comprehensive hooks session (uses simple Rich output)."""
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
        """Update hook progress (uses simple Rich output)."""
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
        """Get summary of hook progress."""
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
        """Start an AI-fix session."""
        if not self.enabled:
            return

        self.stage = stage
        self.current_iteration = 0
        self.issue_history = [initial_issue_count] if initial_issue_count > 0 else []

        # Render cyberpunk header
        self._render_header_panel(stage, initial_issue_count)

    def start_iteration(
        self,
        iteration: int,
        issue_count: int,
    ) -> None:
        """Start a new iteration within the AI-fix session."""
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
        """Update iteration progress (no-op for alive-progress version)."""
        if not self.enabled:
            return

        if issues_remaining > 0:
            if not self.issue_history or self.issue_history[-1] != issues_remaining:
                self.issue_history.append(issues_remaining)

    def end_iteration(self) -> None:
        """End the current iteration."""
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
        """Log an event - prints above the progress bar with neon colors."""
        if not self.enabled:
            return

        self._neon_print(severity, agent, action, file)

    async def async_log_event(
        self,
        agent: str,
        action: str,
        file: str,
        severity: str = "info",
    ) -> None:
        """Async version of log_event - yields control to event loop."""
        if not self.enabled:
            return

        # Yield control to event loop before printing
        await asyncio.sleep(0)
        self._neon_print(severity, agent, action, file)

    def start_agent_bars(self, agent_names: list[str]) -> None:
        """Start agent progress bars (compatibility - no-op)."""
        pass  # alive-progress handles this differently

    def update_agent_progress(
        self,
        agent_name: str,
        completed: int,
        total: int,
        current_file: str | None = None,
        current_issue_type: str | None = None,
    ) -> None:
        """Update agent progress - logs the event."""
        if not self.enabled:
            return

        if current_file and current_issue_type:
            severity = "success" if "fixed" in current_issue_type.lower() else "info"
            self.log_event(agent_name, current_issue_type, current_file, severity)

    def end_agent_bars(self) -> None:
        """End agent bars (compatibility - no-op)."""
        pass

    def finish_session(self, success: bool = True, message: str = "") -> None:
        """Finish the AI-fix session."""
        if not self.enabled:
            return

        self.end_iteration()

        # Render cyberpunk footer
        self._render_footer_panel(success)

        # Print history if available
        if self.issue_history:
            history_str = " → ".join(str(n) for n in self.issue_history)
            self.console.print(f"[dim]History: {history_str}[/dim]")

    def is_enabled(self) -> bool:
        """Check if progress is enabled."""
        return self.enabled

    def is_in_progress(self) -> bool:
        """Check if a progress context is currently active."""
        return self._in_progress

    def should_skip_console_print(self) -> bool:
        """Check if console prints should be skipped (progress bar active)."""
        return self._in_progress

    def enable(self) -> None:
        """Enable progress display."""
        self.enabled = True

    def disable(self) -> None:
        """Disable progress display."""
        self.enabled = False

    # =========================================================================
    # Context Manager for alive-progress
    # =========================================================================

    @contextmanager
    def progress_context(
        self,
        total: int,
        title: str = "AI-FIX",
    ) -> Generator[Any]:
        """
        Context manager for alive-progress with enrich_print.

        Usage:
            with progress.progress_context(total_issues, "COMPREHENSIVE") as bar:
                for issue in issues:
                    # Do work
                    progress.log_event("Agent", "Fixed", "file.py", "success")
                    bar()  # Advance
        """
        if not self.enabled:
            yield None
            return

        title_styled = f"{Neon.CYAN}{Neon.BOLD}╠══ {title}{Neon.RESET}"

        with alive_bar(
            total,
            title=title_styled,
            enrich_print=True,  # Key feature: simultaneous logging
            spinner="classic",
            bar="classic",
            length=40,
        ) as bar:
            self._bar = bar
            self._in_progress = True
            try:
                yield bar
            finally:
                self._bar = None
                self._in_progress = False


# Backwards compatibility - export old names
ActivityEvent = tuple  # Was NamedTuple, now just a tuple for compatibility
