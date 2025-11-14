import threading
import time
import typing as t


class TestProgress:
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
        self._seen_files: set[str] = set()

    @property
    def completed(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time if self.start_time else 0

    @property
    def eta_seconds(self) -> float | None:
        if self.completed <= 0 or self.total_tests <= 0:
            return None
        progress_rate = (
            self.completed / self.elapsed_time if self.elapsed_time > 0 else 0
        )
        remaining = self.total_tests - self.completed
        return remaining / progress_rate if progress_rate > 0 else None

    @property
    def tests_per_second(self) -> float:
        """Calculate test execution rate."""
        if self.elapsed_time > 0 and self.completed > 0:
            return self.completed / self.elapsed_time
        return 0.0

    @property
    def overall_status_color(self) -> str:
        """Determine overall status color based on test results."""
        if self.failed > 0 or self.errors > 0:
            return "red"
        elif self.completed > 0 and self.completed == self.total_tests:
            return "green"
        elif self.passed > 0:
            return "yellow"  # Tests running, some passed
        return "cyan"  # Default color

    def update(self, **kwargs: t.Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def _create_progress_bar(self, width: int = 20) -> str:
        """Create a visual progress bar.

        Args:
            width: Width of the progress bar in characters

        Returns:
            Formatted progress bar string like [████████░░░░] 40%
        """
        if self.total_tests == 0:
            return ""

        progress_ratio = self.completed / self.total_tests
        filled = int(progress_ratio * width)
        empty = width - filled

        # Use different characters for passed vs failed
        if self.failed > 0 or self.errors > 0:
            fill_char = "▓"  # Denser for failures
            bar_color = "red"
        else:
            fill_char = "█"
            bar_color = "green" if self.completed == self.total_tests else "yellow"

        bar = fill_char * filled + "░" * empty
        percentage = int(progress_ratio * 100)

        return f"[{bar_color}][{bar}] {percentage}%[/{bar_color}]"

    def _format_eta(self) -> str:
        """Format ETA in human-readable form.

        Returns:
            Formatted ETA string like "ETA: 12s" or "ETA: 2m 34s"
        """
        eta = self.eta_seconds
        if eta is None or eta <= 0:
            return ""

        if eta < 60:
            return f"ETA: {int(eta)}s"
        elif eta < 3600:
            minutes = int(eta // 60)
            seconds = int(eta % 60)
            return f"ETA: {minutes}m {seconds}s"
        else:
            hours = int(eta // 3600)
            minutes = int((eta % 3600) // 60)
            return f"ETA: {hours}h {minutes}m"

    def _format_test_rate(self) -> str:
        """Format test execution rate.

        Returns:
            Formatted rate string like "12.5 tests/s"
        """
        rate = self.tests_per_second
        if rate == 0:
            return ""
        return f"{rate:.1f} tests/s"

    def format_progress(self) -> str:
        if self.is_collecting:
            return self._format_collection_progress()
        return self._format_execution_progress()

    def _format_collection_progress(self) -> str:
        status_parts = [f"⠋ [cyan]{self.collection_status}[/cyan]"]

        if self.files_discovered > 0:
            status_parts.append(f"[dim]{self.files_discovered} test files[/dim]")

        elapsed = self.elapsed_time
        if elapsed > 1:
            status_parts.append(f"[dim]{elapsed:.1f}s[/dim]")

        return " | ".join(status_parts)

    def _format_progress_counters(self) -> list[str]:
        """Format pass/fail/skip/error status counters.

        Returns:
            List of formatted status counter strings
        """
        status_parts = []
        if self.completed > 0:
            progress_pct = (self.completed / self.total_tests) * 100
            status_parts.append(
                f"[dim]{self.completed}/{self.total_tests} ({progress_pct:.0f}%)[/dim]"
            )

        if self.passed > 0:
            status_parts.append(f"[green]✅ {self.passed}[/green]")
        if self.failed > 0:
            status_parts.append(f"[red]❌ {self.failed}[/red]")
        if self.skipped > 0:
            status_parts.append(f"[yellow]⏭ {self.skipped}[/yellow]")
        if self.errors > 0:
            status_parts.append(f"[red]💥 {self.errors}[/red]")

        return status_parts

    def _format_execution_progress(self) -> str:
        parts = []

        # Simple spinner-based display for parallel test execution
        if self.total_tests > 0:
            # Main message with test count (using simple spinner character)
            parts.append(f"⠋ [cyan]Running {self.total_tests} tests[/cyan]")

            # Add status counters with emojis if any tests have completed
            status_parts = self._format_progress_counters()
            if status_parts:
                parts.append(" | ".join(status_parts))

            # Add elapsed time
            elapsed = self.elapsed_time
            if elapsed > 1:
                parts.append(f"[dim]{elapsed:.0f}s[/dim]")
        else:
            # Before collection completes
            parts.append("⠋ [cyan]Preparing tests...[/cyan]")

        return " | ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")
