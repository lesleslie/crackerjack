"""Test result rendering for console output.

This module provides Rich-based rendering for test results, failures,
and related information to the console.

The TestResultRenderer class handles all UI rendering for test results,
providing a clean separation between test execution logic and display
logic. This follows the Single Responsibility Principle by isolating
all presentation concerns from the TestManager orchestration logic.

Typical usage:
    >>> from rich.console import Console
    >>> from crackerjack.services.testing.test_result_renderer import TestResultRenderer
    >>> console = Console()
    >>> renderer = TestResultRenderer(console)
    >>> stats = {"total": 10, "passed": 8, "failed": 2, "duration": 1.5}
    >>> renderer.render_test_results_panel(stats, workers=4, success=False)

The renderer uses Rich console formatting with emoji indicators and
color-coded output for improved readability.
"""

from rich import box
from rich.panel import Panel
from rich.table import Table

from crackerjack.config import get_console_width
from crackerjack.models.protocols import ConsoleInterface
import typing as t


class TestResultRenderer:
    """Render test results to console using Rich.

    This class handles all UI rendering for test results, providing a clean
    separation between test execution logic and presentation logic. Following
    the Single Responsibility Principle, it focuses exclusively on formatting
    and displaying test information.

    Responsibilities:
        - Test statistics panel (Rich table with metrics)
        - Banners and headers (section dividers)
        - Error messages (parsing failures, etc.)
        - Conditional rendering logic (what to display when)

    The renderer is protocol-based, accepting any ConsoleInterface implementation,
    which makes it easy to test with mock consoles.

    Attributes:
        console: Console interface for all output operations

    Example:
        >>> from rich.console import Console
        >>> from crackerjack.services.testing.test_result_renderer import TestResultRenderer
        >>> console = Console()
        >>> renderer = TestResultRenderer(console)
        >>> stats = {"total": 100, "passed": 95, "failed": 5, "duration": 12.3}
        >>> renderer.render_test_results_panel(stats, workers=4, success=False)
    """

    def __init__(self, console: ConsoleInterface) -> None:
        """Initialize the renderer with a console instance.

        Args:
            console: Console interface for output (typically Rich console)

        The renderer stores the console reference for all subsequent
        rendering operations. This allows for dependency injection
        and easier testing with mock consoles.
        """
        self.console = console

    def render_test_results_panel(
        self,
        stats: dict[str, t.Any],
        workers: int | str,
        success: bool,
    ) -> None:
        """Render test results as a Rich panel with table.

        Creates a formatted Rich panel containing test statistics in a table
        format with color-coded metrics, percentages, and summary information.
        The panel styling (border color, title, icons) reflects whether
        tests passed or failed overall.

        Args:
            stats: Test statistics dictionary with keys:
                - total (int): Total number of tests
                - passed (int): Number of passed tests
                - failed (int): Number of failed tests
                - skipped (int): Number of skipped tests (optional)
                - errors (int): Number of error tests (optional)
                - xfailed (int): Number of expected failures (optional)
                - xpassed (int): Number of unexpected passes (optional)
                - duration (float): Test execution time in seconds
                - coverage (float | None): Coverage percentage (optional)
            workers: Number of workers used for test execution (int or 'auto')
            success: Whether all tests passed (controls panel styling)

        The panel includes:
            - Core metrics (passed, failed, skipped, errors) with percentages
            - Optional metrics (xfailed, xpassed) when present
            - Summary section (total tests, duration, worker count)
            - Coverage percentage when available

        Example:
            >>> stats = {
            ...     "total": 10,
            ...     "passed": 8,
            ...     "failed": 2,
            ...     "duration": 1.5,
            ...     "coverage": 85.5
            ... }
            >>> renderer.render_test_results_panel(stats, workers=4, success=False)
        """
        table = Table(box=box.SIMPLE, header_style="bold bright_white")
        table.add_column("Metric", style="cyan", overflow="fold")
        table.add_column("Count", justify="right", style="bright_white")
        table.add_column("Percentage", justify="right", style="magenta")

        total = stats["total"]

        # Core metrics
        metrics = [
            ("✅ Passed", stats["passed"], "green"),
            ("❌ Failed", stats["failed"], "red"),
            ("⏭ Skipped", stats["skipped"], "yellow"),
            ("💥 Errors", stats["errors"], "red"),
        ]

        # Optional metrics
        if stats.get("xfailed", 0) > 0:
            metrics.append(("📌 XFailed", stats["xfailed"], "yellow"))
        if stats.get("xpassed", 0) > 0:
            metrics.append(("⭐ XPassed", stats["xpassed"], "green"))

        # Add metric rows
        for label, count, _ in metrics:
            percentage = f"{(count / total * 100):.1f}%" if total > 0 else "0.0%"
            table.add_row(label, str(count), percentage)

        # Summary rows
        table.add_row("─" * 20, "─" * 10, "─" * 15, style="dim")
        table.add_row("📊 Total Tests", str(total), "100.0%", style="bold")
        table.add_row(
            "⏱ Duration",
            f"{stats['duration']:.2f}s",
            "",
            style="bold magenta",
        )
        table.add_row(
            "👥 Workers",
            str(workers),
            "",
            style="bold cyan",
        )

        # Coverage row (if available)
        if stats.get("coverage") is not None:
            table.add_row(
                "📈 Coverage",
                f"{stats['coverage']:.1f}%",
                "",
                style="bold green",
            )

        # Panel styling based on success/failure
        border_style = "green" if success else "red"
        title_icon = "✅" if success else "❌"
        title_text = "Test Results" if success else "Test Results (Failed)"

        panel = Panel(
            table,
            title=f"[bold]{title_icon} {title_text}[/bold]",
            border_style=border_style,
            padding=(0, 1),
            width=get_console_width(),
        )

        self.console.print(panel)

    def render_banner(
        self,
        title: str,
        *,
        line_style: str = "red",
        title_style: str | None = None,
        char: str = "━",
        padding: bool = True,
    ) -> None:
        """Render a banner with title.

        Args:
            title: Banner title text
            line_style: Rich style for the line
            title_style: Rich style for the title (defaults to bold + line_style)
            char: Character to use for the line
            padding: Whether to add padding before/after the banner
        """
        from rich.text import Text

        width = max(20, get_console_width())
        line_text = Text(char * width, style=line_style)
        resolved_title_style = title_style or ("bold " + line_style).strip()
        title_text = Text(title, style=resolved_title_style)

        if padding:
            self.console.print()

        self.console.print(line_text)
        self.console.print(title_text)
        self.console.print(line_text)

        if padding:
            self.console.print()

    def should_render_test_panel(self, stats: dict[str, t.Any]) -> bool:
        """Determine if test results panel should be rendered.

        Args:
            stats: Test statistics dictionary

        Returns:
            True if panel should be rendered, False otherwise
        """
        return any(
            [
                stats.get("total", 0) > 0,
                stats.get("passed", 0) > 0,
                stats.get("failed", 0) > 0,
                stats.get("errors", 0) > 0,
                stats.get("skipped", 0) > 0,
                stats.get("xfailed", 0) > 0,
                stats.get("xpassed", 0) > 0,
                stats.get("duration", 0.0) > 0.0,
                stats.get("coverage") is not None,
            ],
        )

    def render_parsing_error_message(self, error: Exception) -> None:
        """Render error message for parsing failures.

        Args:
            error: The exception that occurred
        """
        self.console.print(
            f"[dim yellow]⚠️ Structured parsing failed: {error}[/dim yellow]",
        )
        self.console.print(
            "[dim yellow]Falling back to standard formatting...[/dim yellow]\n",
        )
