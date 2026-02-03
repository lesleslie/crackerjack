"""Rich console utilities for crackerjack CLI.

This module provides centralized imports and helper functions for Rich console
operations, reducing import duplication across the codebase.

Common usage:
    from crackerjack.cli._rich_utils import console, print_panel, print_table
"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

# Default console instance for CLI operations
console = Console()

# Commonly used Rich components
__all__ = [
    "console",
    "Console",
    "Panel",
    "Table",
    "Progress",
    "SpinnerColumn",
    "TextColumn",
    "BarColumn",
    "TimeRemainingColumn",
]


def get_console() -> Console:
    """Get the default Rich console instance.

    Returns:
        The default Console object for CLI output.
    """
    return console


def print_panel(
    content: str,
    title: str | None = None,
    style: str | None = None,
    subtitle: str | None = None,
) -> None:
    """Print content in a Rich panel.

    Args:
        content: The content to display in the panel.
        title: Optional title for the panel.
        style: Optional style string for the panel.
        subtitle: Optional subtitle for the panel.
    """
    panel = Panel(content, title=title, subtitle=subtitle)
    if style:
        console.print(panel, style=style)
    else:
        console.print(panel)


def create_table(
    title: str | None = None,
    caption: str | None = None,
    show_header: bool = True,
    show_edge: bool = True,
) -> Table:
    """Create a Rich table with common defaults.

    Args:
        title: Optional table title.
        caption: Optional table caption.
        show_header: Whether to show the header row.
        show_edge: Whether to show the table edge.

    Returns:
        A configured Rich Table object.
    """
    return Table(
        title=title,
        caption=caption,
        show_header=show_header,
        show_edge=show_edge,
    )


def create_progress_spinner(
    description: str = "Processing...",
) -> Progress:
    """Create a Rich progress spinner with common columns.

    Args:
        description: Description text for the spinner.

    Returns:
        A configured Rich Progress object.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
        console=console,
    )
