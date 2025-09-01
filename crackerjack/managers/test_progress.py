"""Test progress tracking and display functionality.

This module handles real-time test execution progress tracking, including collection
and execution phases. Split from test_manager.py for better separation of concerns.
"""

import threading
import time
import typing as t

from rich.align import Align
from rich.table import Table


class TestProgress:
    """Tracks test execution progress with thread-safe updates."""

    def __init__(self) -> None:
        self.total_tests: int = 0
        self.passed: int = 0
        self.failed: int = 0
        self.skipped: int = 0
        self.errors: int = 0
        self.current_test: str = ""
        self.start_time: float = 0
        self.is_complete: bool = False
        self.is_collecting: bool = True
        self.files_discovered: int = 0
        self.collection_status: str = "Starting collection..."
        self._lock = threading.Lock()
        self._seen_files: set[str] = set()  # Track seen files to prevent duplicates

    @property
    def completed(self) -> int:
        """Total completed tests (passed + failed + skipped + errors)."""
        return self.passed + self.failed + self.skipped + self.errors

    @property
    def elapsed_time(self) -> float:
        """Elapsed time since test start."""
        return time.time() - self.start_time if self.start_time else 0

    @property
    def eta_seconds(self) -> float | None:
        """Estimated time to completion based on current progress rate."""
        if self.completed <= 0 or self.total_tests <= 0:
            return None
        progress_rate = (
            self.completed / self.elapsed_time if self.elapsed_time > 0 else 0
        )
        remaining = self.total_tests - self.completed
        return remaining / progress_rate if progress_rate > 0 else None

    def update(self, **kwargs: t.Any) -> None:
        """Thread-safe update of progress attributes."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def format_progress(self) -> Align:
        """Format progress display for Rich output."""
        if self.is_collecting:
            return Align.center(self._format_collection_progress())
        return Align.center(self._format_execution_progress())

    def _format_collection_progress(self) -> Table:
        """Format test collection progress display."""
        table = Table.grid(padding=(0, 2))
        table.add_column()
        table.add_column(justify="center")

        # Collection status
        table.add_row(
            "[yellow]📋[/yellow] Test Collection",
            f"[dim]{self.collection_status}[/dim]",
        )

        # Files discovered
        if self.files_discovered > 0:
            table.add_row(
                "[cyan]📁[/cyan] Files Found",
                f"[green]{self.files_discovered}[/green] test files",
            )

        # Elapsed time
        elapsed = self.elapsed_time
        if elapsed > 1:
            table.add_row("[blue]⏱️[/blue] Elapsed", f"[dim]{elapsed:.1f}s[/dim]")

        return table

    def _format_execution_progress(self) -> Table:
        """Format test execution progress display."""
        table = Table.grid(padding=(0, 2))
        table.add_column()
        table.add_column(justify="center")

        # Progress bar representation
        if self.total_tests > 0:
            progress_pct = (self.completed / self.total_tests) * 100
            completed_blocks = int((self.completed / self.total_tests) * 20)
            remaining_blocks = 20 - completed_blocks
            progress_bar = "█" * completed_blocks + "░" * remaining_blocks

            table.add_row(
                "[yellow]⚡[/yellow] Progress",
                f"[green]{progress_bar}[/green] {progress_pct:.1f}%",
            )

        # Test counts
        table.add_row("[green]✅[/green] Passed", f"[green]{self.passed}[/green]")

        if self.failed > 0:
            table.add_row("[red]❌[/red] Failed", f"[red]{self.failed}[/red]")

        if self.skipped > 0:
            table.add_row(
                "[yellow]⏭️[/yellow] Skipped", f"[yellow]{self.skipped}[/yellow]"
            )

        if self.errors > 0:
            table.add_row("[red]💥[/red] Errors", f"[red]{self.errors}[/red]")

        # Current test
        if self.current_test and not self.is_complete:
            table.add_row(
                "[blue]🔄[/blue] Running",
                f"[dim]{self.current_test[:50]}...[/dim]"
                if len(self.current_test) > 50
                else f"[dim]{self.current_test}[/dim]",
            )

        # Timing information
        elapsed = self.elapsed_time
        if elapsed > 1:
            table.add_row("[blue]⏱️[/blue] Elapsed", f"[dim]{elapsed:.1f}s[/dim]")

        # ETA
        eta = self.eta_seconds
        if eta and eta > 1 and not self.is_complete:
            table.add_row("[blue]📅[/blue] ETA", f"[dim]{eta:.1f}s[/dim]")

        return table
