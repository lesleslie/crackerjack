import asyncio
import logging
from collections import deque
from contextlib import suppress
from io import StringIO
from pathlib import Path
from typing import Any, NamedTuple

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
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


class ActivityEvent(NamedTuple):
    """Type-safe activity event for progress tracking.

    Attributes:
        agent: Agent name (e.g., "RefactoringAgent")
        action: Action being performed (e.g., "fixing", "analyzing")
        file: File path being processed
        severity: Event severity ("info", "warning", "error", "success")
    """

    agent: str
    action: str
    file: str
    severity: str = "info"


class AIFixProgressManager:
    """Progress manager for AI-fix with Live display and activity feed.

    Features:
        - Live display with activity ticker (thread-safe via Rich)
        - Progress bars for iterations and agents
        - Async-safe event logging
        - Configurable refresh rate

    Thread Safety:
        Rich's Live.update() uses internal lock, so log_event() is thread-safe
        even when called from multiple concurrent agents.

    Async Safety:
        Use async_log_event() from async contexts to avoid blocking event loop.
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
        self.console = console or Console()
        self.enabled = enabled
        self.enable_agent_bars = enable_agent_bars
        self.max_agent_bars = max_agent_bars
        self.activity_feed_size = activity_feed_size
        self.refresh_per_second = refresh_per_second

        # Progress bars (existing)
        self.iteration_bar: Progress | None = None
        self.iteration_task_id: Any | None = None
        self.agent_bars: dict[str, Any] = {}
        self.agent_progress: Progress | None = None
        self.agent_task_ids: dict[str, Any] = {}

        # Live display with activity feed (new)
        self._live_display: Live | None = None
        self._activity_events: deque[ActivityEvent] = deque(maxlen=activity_feed_size)

        # Session state
        self.issue_history: list[int] = []
        self.current_iteration = 0
        self.stage = "fast"
        self.current_operation: str = ""

    def start_fix_session(
        self,
        stage: str = "fast",
        initial_issue_count: int = 0,
    ) -> None:
        """Start a new AI-fix session."""
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
        """Start a new iteration with Live display and progress bar."""
        if not self.enabled:
            return

        self.current_iteration = iteration

        if issue_count > 0:
            self.issue_history.append(issue_count)

        # Create Live display for activity feed
        # Note: Pass lambda to call the method, not the method itself
        self._live_display = Live(
            lambda: self._render_dashboard(),
            console=self.console,
            refresh_per_second=self.refresh_per_second,
        )
        self._live_display.start()

        # Create iteration progress bar for tracking state only
        # Note: We use a separate console to avoid Live display conflicts.
        # The actual rendering is done by _get_progress_text() in the Live dashboard.
        from io import StringIO

        tracking_console = Console(file=StringIO(), force_terminal=True)
        self.iteration_bar = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=tracking_console,
            expand=False,
        )

        self.iteration_bar = self.iteration_bar.__enter__()

        title = f"🤖 AI-FIX STAGE: {self.stage.upper()}"
        self.iteration_task_id = self.iteration_bar.add_task(
            title,
            total=100,
        )

        self._update_iteration_display(iteration, issue_count, 0)

    def update_iteration_progress(
        self,
        iteration: int,
        issues_remaining: int,
        no_progress_count: int = 0,
    ) -> None:
        """Update iteration progress and Live display."""
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

        if self.iteration_bar and hasattr(self, "iteration_task_id"):
            self.iteration_bar.update(
                self.iteration_task_id,
                completed=reduction_pct,
            )

        self._update_iteration_display(iteration, issues_remaining, no_progress_count)

        # Update Live display
        if self._live_display:
            self._live_display.update(self._render_dashboard(), refresh=True)

    def end_iteration(self) -> None:
        """Complete current iteration and cleanup Live display."""
        if not self.enabled:
            return

        # Finalize iteration progress
        if self.iteration_bar and hasattr(self, "iteration_task_id"):
            self.iteration_bar.update(self.iteration_task_id, completed=100)

        # Stop Live display
        if self._live_display:
            self._live_display.stop()
            self._live_display = None

        # Stop iteration progress bar
        if self.iteration_bar:
            if hasattr(self.iteration_bar, "__exit__"):
                self.iteration_bar.__exit__(None, None, None)
            self.iteration_bar = None
            self.iteration_task_id = None

        # End agent bars
        if self.enable_agent_bars:
            self.end_agent_bars()

    def log_event(
        self,
        agent: str,
        action: str,
        file: str,
        severity: str = "info",
    ) -> None:
        """Log activity event to feed (thread-safe).

        Can be called from multiple threads concurrently.
        Rich's Live.update() uses internal lock for thread safety.

        Args:
            agent: Agent name (e.g., "RefactoringAgent")
            action: Action being performed (e.g., "fixing", "analyzing")
            file: File path being processed
            severity: Event severity ("info", "warning", "error", "success")
        """
        if not self.enabled or not self._live_display:
            return

        event = ActivityEvent(agent, action, file, severity)

        # Add to activity feed (thread-safe via deque)
        self._activity_events.append(event)

        # Update Live display (thread-safe via Rich's internal lock)
        self._live_display.update(self._render_dashboard(), refresh=True)

    async def async_log_event(
        self,
        agent: str,
        action: str,
        file: str,
        severity: str = "info",
    ) -> None:
        """Async-safe event logging.

        Runs log_event() in thread pool to avoid blocking event loop.

        Args:
            agent: Agent name (e.g., "RefactoringAgent")
            action: Action being performed (e.g., "fixing", "analyzing")
            file: File path being processed
            severity: Event severity ("info", "warning", "error", "success")
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self.log_event,
            agent,
            action,
            file,
            severity,
        )

    def start_agent_bars(self, agent_names: list[str]) -> None:
        """Start progress bars for individual agents."""
        if not self.enabled or not self.enable_agent_bars:
            return

        limited_agents = agent_names[: self.max_agent_bars]

        if not hasattr(self, "agent_progress") or self.agent_progress is None:
            # Create agent progress bar for tracking state only
            # Note: Use a separate console to avoid Live display conflicts.
            # The actual rendering is done manually in the Live dashboard.
            tracking_console = Console(file=StringIO(), force_terminal=True)
            self.agent_progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=tracking_console,
                expand=False,
            )
            self.agent_progress = self.agent_progress.__enter__()
            self.agent_task_ids = {}

        for agent_name in limited_agents:
            if agent_name not in self.agent_task_ids:
                icon = AGENT_ICONS.get(agent_name, "🤖")
                task_id = self.agent_progress.add_task(
                    f"{icon} {agent_name}",
                    total=100,
                )
                self.agent_task_ids[agent_name] = task_id

    def update_agent_progress(
        self,
        agent_name: str,
        completed: int,
        total: int,
        current_file: str | None = None,
        current_issue_type: str | None = None,
    ) -> None:
        """Update agent progress bar and log activity event."""
        if not self.enabled or not self.enable_agent_bars:
            return

        if agent_name not in getattr(self, "agent_task_ids", {}):
            self.start_agent_bars([agent_name])

        if total > 0:
            pct = (completed / total) * 100
        else:
            pct = 100

        if hasattr(self, "agent_progress") and agent_name in self.agent_task_ids:
            self.agent_progress.update(
                self.agent_task_ids[agent_name],
                completed=pct,
            )

        # Log activity event to feed
        if current_file:
            # Determine severity based on issue type
            severity = "info"
            if current_issue_type:
                issue_lower = current_issue_type.lower()
                if any(
                    term in issue_lower for term in ("error", "critical", "security")
                ):
                    severity = "error"
                elif any(term in issue_lower for term in ("warning", "deprecated")):
                    severity = "warning"
                elif any(
                    term in issue_lower for term in ("fixed", "resolved", "success")
                ):
                    severity = "success"

            action = current_issue_type or "processing"

            # Shorten agent name for display
            agent_short = agent_name.replace("Agent", "")

            self.log_event(
                agent=agent_short,
                action=action,
                file=current_file,
                severity=severity,
            )

        # Legacy: also print current operation
        if current_file or current_issue_type:
            self._print_current_operation(agent_name, current_file, current_issue_type)

    def end_agent_bars(self) -> None:
        """Complete agent progress bars."""
        if not self.enabled:
            return

        if hasattr(self, "agent_progress") and self.agent_progress:
            if hasattr(self, "agent_task_ids"):
                for task_id in self.agent_task_ids.values():
                    self.agent_progress.update(task_id, completed=100)

            if hasattr(self.agent_progress, "__exit__"):
                self.agent_progress.__exit__(None, None, None)

        self.agent_progress = None
        self.agent_task_ids = {}
        self.current_operation = ""

    def _render_dashboard(self) -> Panel:
        """Render the Live dashboard.

        Returns a Panel with:
            - Stage header
            - Progress bar (if applicable)
            - Activity feed
        """
        # Stage header
        stage_text = self._get_stage_text()

        # Progress bar
        progress_text = self._get_progress_text()

        # Activity feed
        activity_text = self._render_activity_feed()

        # Combine
        content = f"{stage_text}\n"
        if progress_text:
            content += f"{progress_text}\n"
        content += activity_text

        return Panel(
            content,
            border_style="cyan",
            padding=(0, 1),
            title="[bold]Crackerjack[/bold]",
        )

    def _get_stage_text(self) -> str:
        """Get stage header text."""
        stage_info = {
            "fast": ("Fast Hooks", "~5s"),
            "comprehensive": ("Comprehensive Hooks", "~30s"),
            "tests": ("Running Tests", ""),
            "ai_fix": ("AI Auto-Fix", ""),
        }.get(self.stage, (self.stage.title(), ""))

        stage_name, est_time = stage_info

        header = f"[bold cyan]🚀 {stage_name.upper()}[/bold cyan]"
        if est_time:
            header += f" [dim]({est_time})[/dim]"
        if self.stage == "ai_fix" and self.current_iteration > 0:
            header += f" [dim](iteration {self.current_iteration}/10)[/dim]"

        return header

    def _get_progress_text(self) -> str:
        """Get progress bar text if applicable."""
        if not self.issue_history:
            return ""

        initial_issues = self.issue_history[0]
        current_issues = self.issue_history[-1]
        reduction_pct = self._calculate_reduction()

        if initial_issues > 0:
            filled = int(reduction_pct / 5)  # 20 segments
            bar = "█" * filled + "░" * (20 - filled)
            color = "green" if current_issues == 0 else "yellow"

            return f"[{color}][{bar}] {reduction_pct:.0f}% reduction ({current_issues}/{initial_issues} issues)[/{color}]"

        return ""

    def _render_activity_feed(self) -> str:
        """Render compact activity feed."""
        if not self._activity_events:
            return "[dim]Recent Activity:[/dim] [dim]No activity yet[/dim]"

        lines = ["[dim]Recent Activity:[/dim]"]

        # Severity color mapping
        color_map = {
            "error": "red",
            "warning": "yellow",
            "success": "green",
            "info": "cyan",
        }

        for event in reversed(self._activity_events):
            # Agent icon and short name
            icon = AGENT_ICONS.get(event.agent, "🤖")
            agent_short = event.agent.replace("Agent", "")

            # Severity color
            color = color_map.get(event.severity, "white")

            # File name only (shorter)
            file_part = ""
            if event.file:
                file_path = Path(event.file)
                file_part = file_path.name

            # Format: 🔧 Refactoring: syntax error test_executor.py
            line = f"  [{color}]{icon} {agent_short}: {event.action}[/][{color}] {file_part}[/]"
            lines.append(line)

        return "\n".join(lines)

    def _print_current_operation(
        self,
        agent_name: str,
        current_file: str | None,
        current_issue_type: str | None,
    ) -> None:
        """Print current operation (legacy method, kept for compatibility)."""
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
        """Complete the AI-fix session."""
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
        """Print session start header."""
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
        """Update iteration progress display (legacy, kept for compatibility)."""
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
        self.console.print(f"  Iteration {iteration + 1} | {convergence_str}")

    def _calculate_reduction(self) -> float:
        """Calculate issue reduction percentage."""
        if len(self.issue_history) < 2:
            return 0.0

        start = self.issue_history[0]
        current = self.issue_history[-1]

        if start == 0:
            return 0.0

        return ((start - current) / start) * 100

    def _print_final_summary(self) -> None:
        """Print final session summary."""
        start = self.issue_history[0]
        end = self.issue_history[-1]
        iterations = len(self.issue_history)

        self.console.print()
        self.console.print(f"[dim]  Started with: {start} issues[/dim]")
        self.console.print(f"[dim]  Finished with: {end} issues[/dim]")
        self.console.print(f"[dim]  Iterations: {iterations}[/dim]")
        self.console.print()

    def is_enabled(self) -> bool:
        """Check if progress tracking is enabled."""
        return self.enabled

    def enable(self) -> None:
        """Enable progress tracking."""
        self.enabled = True

    def disable(self) -> None:
        """Disable progress tracking and cleanup displays."""
        self.enabled = False

        # Stop Live display
        if self._live_display:
            self._live_display.stop()
            self._live_display = None

        # Stop iteration progress bar
        if self.iteration_bar:
            if hasattr(self.iteration_bar, "__exit__"):
                self.iteration_bar.__exit__(None, None, None)
            self.iteration_bar = None
            self.iteration_task_id = None

        # Stop agent progress
        if self.agent_progress:
            if hasattr(self.agent_progress, "__exit__"):
                self.agent_progress.__exit__(None, None, None)
            self.agent_progress = None
            self.agent_task_ids = {}
