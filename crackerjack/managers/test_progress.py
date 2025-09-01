"""Test progress tracking and display functionality.

This module handles real-time test execution progress tracking, including collection
and execution phases. Split from test_manager.py for better separation of concerns.
"""

import threading
import time
import typing as t


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

    def format_progress(self) -> str:
        """Format progress display for Rich output."""
        if self.is_collecting:
            return self._format_collection_progress()
        return self._format_execution_progress()

    def _format_collection_progress(self) -> str:
        """Format test collection progress display."""
        status_parts = [self.collection_status]

        if self.files_discovered > 0:
            status_parts.append(f"{self.files_discovered} test files")

        elapsed = self.elapsed_time
        if elapsed > 1:
            status_parts.append(f"{elapsed:.1f}s")

        return " | ".join(status_parts)

    def _format_execution_progress(self) -> str:
        """Format test execution progress display."""
        parts = []

        # Test progress
        if self.total_tests > 0:
            progress_pct = (self.completed / self.total_tests) * 100
            parts.append(f"{self.completed}/{self.total_tests} ({progress_pct:.1f}%)")

        # Status counts
        status_parts = []
        if self.passed > 0:
            status_parts.append(f"✅ {self.passed}")
        if self.failed > 0:
            status_parts.append(f"❌ {self.failed}")
        if self.skipped > 0:
            status_parts.append(f"⏭ {self.skipped}")
        if self.errors > 0:
            status_parts.append(f"💥 {self.errors}")

        if status_parts:
            parts.append(" ".join(status_parts))

        # Current test (truncated)
        if self.current_test and not self.is_complete:
            test_name = (
                self.current_test[:30] + "..."
                if len(self.current_test) > 30
                else self.current_test
            )
            parts.append(f"Running: {test_name}")

        # Timing
        elapsed = self.elapsed_time
        if elapsed > 1:
            parts.append(f"{elapsed:.1f}s")

        return " | ".join(parts)
