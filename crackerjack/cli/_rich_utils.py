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

console = Console()


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
    return console


def print_panel(
    content: str,
    title: str | None = None,
    style: str | None = None,
    subtitle: str | None = None,
) -> None:
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
    return Table(
        title=title,
        caption=caption,
        show_header=show_header,
        show_edge=show_edge,
    )


def create_progress_spinner(
    description: str = "Processing...",
) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
        console=console,
    )
