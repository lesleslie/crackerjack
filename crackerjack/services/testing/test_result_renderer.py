"""Test result rendering for console output.

This module provides Rich-based rendering for test results, failures,
and related information to the console.
"""

from rich import box
from rich.panel import Panel
from rich.table import Table

from crackerjack.config import get_console_width
from crackerjack.models.protocols import ConsoleInterface
import typing as t


class TestResultRenderer:
    """Render test results to console using Rich.

    This class handles all UI rendering for test results, including:
    - Test statistics panel
    - Failure panels
    - Banners and headers
    - Formatted output
    """

    def __init__(self, console: ConsoleInterface) -> None:
        """Initialize the renderer with a console instance.

        Args:
            console: Console interface for output
        """
        self.console = console

    def render_test_results_panel(
        self,
        stats: dict[str, t.Any],
        workers: int | str,
        success: bool,
    ) -> None:
        """Render test results as a Rich panel with table.

        Args:
            stats: Test statistics dictionary
            workers: Number of workers used for test execution
            success: Whether all tests passed
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
