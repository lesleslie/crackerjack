"""
Futuristic progress tracking for AI-fix iterations using alive-progress.

Provides two modes:
- **Phase 1 (Default)**: Single-bar progress with iteration tracking
- **Phase 2 (Optional)**: Multi-bar progress with per-agent tracking

Phase 1 example:
    ╔══════════════════════════════════════════════════════════════════╗
    ║  🤖 AI-FIX STAGE: COMPREHENSIVE                                 ║
    ║  ████████████░░░░░░░░░░░░░  Iteration 5  (67% convergence)      ║
    ║  Issues: 127 → 84 → 52 → 31 → 18 → 12  (91% reduction)         ║
    ╚══════════════════════════════════════════════════════════════════╝

Phase 2 example:
    ╔══════════════════════════════════════════════════════════════════╗
    ║  🤖 AI-FIX STAGE: COMPREHENSIVE                                 ║
    ║  ████████████░░░░░░░░░░░░░  Iteration 3  (33% convergence)      ║
    ║  Issues: 127 → 84 → 52  (59% reduction)                        ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║ 🔧 RefactoringAgent  ████████████████░░  12/15 issues          ║
    ║ 🔒 SecurityAgent     ██████████░░░░░░░░   6/10 issues          ║
    ║ ⚡ PerformanceAgent   ████████████████████  3/3 issues          ║
    ╙──────────────────────────────────────────────────────────────────╙
"""

import logging
from typing import Any

from alive_progress import alive_bar, config_handler
from rich.console import Console
from rich.panel import Panel

# Configure alive-progress for futuristic appearance
config_handler.set_global(
    theme="smooth",  # Smooth animations
    bar="smooth",  # █░ blocks
    spinner="waves",  # Wave animation
    stats="false",  # Hide default time stats (we show custom)
    force_tty=True,  # Force colors
    enrich_print=False,  # We handle custom printing
)

logger = logging.getLogger(__name__)

# Agent icons for visual distinction in Phase 2
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
    """
    Manages progress bars for AI-fix iterations.

    Supports two modes:
    - **Phase 1 (Default)**: Single iteration bar with issue reduction history
    - **Phase 2 (Optional)**: Multiple parallel agent progress bars

    Phase 1 shows:
    - Stage-level progress (Fast vs Comprehensive)
    - Iteration tracking with convergence percentage
    - Issue reduction history
    - Custom stats display

    Phase 2 additionally shows:
    - Per-agent progress bars (up to 5 most active)
    - Current operation details
    - Agent-specific metrics
    """

    def __init__(
        self,
        console: Console | None = None,
        enabled: bool = True,
        enable_agent_bars: bool = False,
        max_agent_bars: int = 5,
    ) -> None:
        """Initialize progress manager.

        Args:
            console: Rich console for output (optional)
            enabled: Whether progress tracking is enabled
            enable_agent_bars: Whether to show Phase 2 agent-level progress
            max_agent_bars: Maximum number of agent bars to show simultaneously
        """
        self.console = console or Console()
        self.enabled = enabled
        self.enable_agent_bars = enable_agent_bars
        self.max_agent_bars = max_agent_bars

        # Progress tracking state
        # alive_bar returns a context manager with __call__ method, use Any for flexibility
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
        """Start an AI-fix session with initial progress display.

        Args:
            stage: "fast" or "comprehensive"
            initial_issue_count: Number of issues detected
        """
        if not self.enabled:
            return

        self.stage = stage
        self.current_iteration = 0
        self.issue_history = [initial_issue_count] if initial_issue_count > 0 else []

        # Print fancy header
        self._print_stage_header(stage, initial_issue_count)

    def start_iteration(
        self,
        iteration: int,
        issue_count: int,
    ) -> None:
        """Start a new iteration progress bar.

        Args:
            iteration: Current iteration number
            issue_count: Number of issues in this iteration
        """
        if not self.enabled:
            return

        self.current_iteration = iteration

        # Track issue history
        if issue_count > 0:
            self.issue_history.append(issue_count)

        # Create iteration bar (alive_bar returns a context manager)
        title = f"🤖 AI-FIX STAGE: {self.stage.upper()}"
        self.iteration_bar = alive_bar(
            total=100,  # Percentage based (0-100%)
            title=title,
            title_length=50,
            manual=True,  # Manual mode - we set exact percentage
            enrich_print=False,  # We handle custom printing
            force_tty=True,  # Force colors
            stats=False,  # Hide default stats
        )

        # alive_bar is a context manager, we need to __enter__ it
        self.iteration_bar = self.iteration_bar.__enter__()

        # Update initial state (0% progress)
        try:
            self.iteration_bar(0)
        except Exception:
            pass

        # Update initial state
        self._update_iteration_display(iteration, issue_count, 0)

    def update_iteration_progress(
        self,
        iteration: int,
        issues_remaining: int,
        no_progress_count: int = 0,
    ) -> None:
        """Update iteration progress with current state.

        Args:
            iteration: Current iteration number
            issues_remaining: Number of issues remaining
            no_progress_count: Count of iterations with no fixes (0-3)
        """
        if not self.enabled or not self.iteration_bar:
            return

        # Update issue history
        if issues_remaining > 0:
            # Only add if different from last entry
            if not self.issue_history or self.issue_history[-1] != issues_remaining:
                self.issue_history.append(issues_remaining)

        # Calculate progress based on issue reduction (more intuitive)
        # Start with initial issue count, show progress as issues are fixed
        if len(self.issue_history) > 0:
            initial_issues = self.issue_history[0]
            issues_fixed = initial_issues - issues_remaining
            reduction_pct = (
                int((issues_fixed / initial_issues) * 100) if initial_issues > 0 else 0
            )
        else:
            reduction_pct = 0

        if self.iteration_bar:
            # In manual mode, we set the absolute percentage (0-100)
            try:
                self.iteration_bar(reduction_pct)
            except Exception:
                pass  # Ignore errors if bar is closed

        # Refresh display
        self._update_iteration_display(iteration, issues_remaining, no_progress_count)

    def end_iteration(self) -> None:
        """Complete current iteration bar."""
        if not self.enabled or not self.iteration_bar:
            return

        # Complete the bar to 100%
        try:
            self.iteration_bar(100)
        except Exception:
            pass  # Ignore errors on completion

        # Clean up
        self.iteration_bar = None

        # Also clean up agent bars if Phase 2 is enabled
        if self.enable_agent_bars:
            self.end_agent_bars()

    def start_agent_bars(self, agent_names: list[str]) -> None:
        """Initialize agent progress bars for Phase 2.

        Args:
            agent_names: List of agent names that will be working
        """
        if not self.enabled or not self.enable_agent_bars:
            return

        # Limit to max_agent_bars most important agents
        # Priority: agents with more issues get bars
        limited_agents = agent_names[: self.max_agent_bars]

        for agent_name in limited_agents:
            if agent_name not in self.agent_bars:
                icon = AGENT_ICONS.get(agent_name, "🤖")
                bar = alive_bar(
                    total=100,  # Percentage based
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
        """Update progress for a specific agent (Phase 2).

        Args:
            agent_name: Name of the agent (e.g., "RefactoringAgent")
            completed: Number of issues completed
            total: Total number of issues
            current_file: Current file being processed (optional)
            current_issue_type: Current issue type (optional)
        """
        if not self.enabled or not self.enable_agent_bars:
            return

        # Create bar if it doesn't exist
        if agent_name not in self.agent_bars:
            self.start_agent_bars([agent_name])

        # Calculate percentage
        if total > 0:
            pct = (completed / total) * 100
        else:
            pct = 100

        # Update bar
        if agent_name in self.agent_bars:
            try:
                self.agent_bars[agent_name](pct)
            except Exception:
                pass  # Bar might already be closed

        # Update current operation display
        if current_file or current_issue_type:
            self._print_current_operation(agent_name, current_file, current_issue_type)

    def end_agent_bars(self) -> None:
        """Complete all agent progress bars."""
        if not self.enabled:
            return

        for agent_name, bar in self.agent_bars.items():
            try:
                bar(100)  # Complete to 100%
            except Exception:
                pass  # Ignore errors

        self.agent_bars.clear()
        self.current_operation = ""

    def _print_current_operation(
        self,
        agent_name: str,
        current_file: str | None,
        current_issue_type: str | None,
    ) -> None:
        """Print current operation details (Phase 2).

        Args:
            agent_name: Agent being used
            current_file: File being processed
            current_issue_type: Type of issue being fixed
        """
        if not current_file and not current_issue_type:
            return

        icon = AGENT_ICONS.get(agent_name, "🤖")

        # Prepare file path for display
        short_file = ""
        if current_file:
            # Shorten file path for display
            import os

            short_file = current_file
            # Try to make path relative to cwd for cleaner display
            try:
                cwd = os.getcwd()
                if current_file.startswith(cwd):
                    short_file = "." + current_file[len(cwd) :]
            except Exception:
                pass

            if len(short_file) > 50:
                short_file = "..." + short_file[-47:]

        # Build operation string
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
        """Complete the entire AI-fix session.

        Args:
            success: Whether session completed successfully
            message: Optional completion message
        """
        if not self.enabled:
            return

        # End any active iteration
        self.end_iteration()

        # Print completion message
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

        # Print summary
        if self.issue_history:
            self._print_final_summary()

    def _print_stage_header(self, stage: str, initial_count: int) -> None:
        """Print stage header with box drawing."""
        stage_upper = stage.upper()

        # Using Rich's panel for fancy border

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
        """Update the iteration progress display."""
        # Build issue history string
        if self.issue_history:
            history_str = " → ".join(str(count) for count in self.issue_history)
            reduction_pct = self._calculate_reduction()
            issues_line = f"Issues: {history_str}  ({reduction_pct:.0f}% reduction)"
        else:
            issues_line = "No issues detected"

        # Build convergence status
        if no_progress_count == 0:
            convergence_str = "✓ Converging"
        elif no_progress_count < 3:
            convergence_str = f"⚠ {no_progress_count}/3 no progress"
        else:
            convergence_str = "⚠ Convergence limit reached"

        # Print stats (below progress bar)
        self.console.print(f"  {issues_line}")
        self.console.print(f"  Iteration {iteration} | {convergence_str}")

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
        """Print final summary statistics."""
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
        """Disable progress tracking."""
        self.enabled = False
        # Clean up any active bar
        if self.iteration_bar:
            self.iteration_bar()
            self.iteration_bar = None
