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

    def update(self, **kwargs: t.Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def format_progress(self) -> str:
        if self.is_collecting:
            return self._format_collection_progress()
        return self._format_execution_progress()

    def _format_collection_progress(self) -> str:
        status_parts = [self.collection_status]

        if self.files_discovered > 0:
            status_parts.append(f"{self.files_discovered} test files")

        elapsed = self.elapsed_time
        if elapsed > 1:
            status_parts.append(f"{elapsed: .1f}s")

        return " | ".join(status_parts)

    def _format_execution_progress(self) -> str:
        parts = []

        if self.total_tests > 0:
            progress_pct = (self.completed / self.total_tests) * 100
            parts.append(f"{self.completed}/{self.total_tests} ({progress_pct: .1f}%)")

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

        if self.current_test and not self.is_complete:
            test_name = (
                self.current_test[:30] + "..."
                if len(self.current_test) > 30
                else self.current_test
            )
            parts.append(f"Running: {test_name}")

        elapsed = self.elapsed_time
        if elapsed > 1:
            parts.append(f"{elapsed: .1f}s")

        return " | ".join(parts)
