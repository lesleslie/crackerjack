"""Test execution engine with progress tracking and output parsing.

This module handles the actual test execution, subprocess management, and real-time
output parsing. Split from test_manager.py for better separation of concerns.
"""

import re
import subprocess
import threading
import time
import typing as t
from pathlib import Path

from rich.console import Console
from rich.live import Live

from .test_progress import TestProgress


class TestExecutor:
    """Handles test execution with real-time progress tracking."""

    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path

    def execute_with_progress(
        self,
        cmd: list[str],
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[str]:
        """Execute test command with live progress display."""
        return self._execute_with_live_progress(cmd, timeout)

    def execute_with_ai_progress(
        self,
        cmd: list[str],
        progress_callback: t.Callable[[dict[str, t.Any]], None],
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[str]:
        """Execute test command with AI-compatible progress callbacks."""
        return self._run_test_command_with_ai_progress(cmd, progress_callback, timeout)

    def _execute_with_live_progress(
        self, cmd: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        """Execute tests with Rich live progress display."""
        progress = self._initialize_progress()

        with Live(progress.format_progress(), console=self.console) as live:
            env = self._setup_test_environment()

            process = subprocess.Popen(
                cmd,
                cwd=self.pkg_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
            )

            # Start reader threads
            stdout_thread, stderr_thread, monitor_thread = self._start_reader_threads(
                process, progress, live
            )

            # Wait for completion
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._handle_progress_error(
                    process, progress, "Test execution timed out"
                )

            # Cleanup
            self._cleanup_threads([stdout_thread, stderr_thread, monitor_thread])

            # Return completed process with string output
            stdout_str = process.stdout.read() if process.stdout else ""
            stderr_str = process.stderr.read() if process.stderr else ""
            return subprocess.CompletedProcess(
                cmd, process.returncode, stdout_str, stderr_str
            )

    def _run_test_command_with_ai_progress(
        self,
        cmd: list[str],
        progress_callback: t.Callable[[dict[str, t.Any]], None],
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[str]:
        """Execute test command with AI progress callbacks."""
        progress = self._initialize_progress()
        env = self._setup_coverage_env()

        result = self._execute_test_process_with_progress(
            cmd, env, progress, progress_callback, timeout
        )

        return result

    def _initialize_progress(self) -> TestProgress:
        """Initialize progress tracker."""
        progress = TestProgress()
        progress.start_time = time.time()
        return progress

    def _setup_test_environment(self) -> dict[str, str]:
        """Set up environment variables for test execution."""
        import os

        cache_dir = Path.home() / ".cache" / "crackerjack" / "coverage"
        cache_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(cache_dir / ".coverage")
        env["PYTEST_CURRENT_TEST"] = ""
        return env

    def _setup_coverage_env(self) -> dict[str, str]:
        """Set up coverage environment for AI mode."""
        import os
        from pathlib import Path

        cache_dir = Path.home() / ".cache" / "crackerjack" / "coverage"
        cache_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(cache_dir / ".coverage")
        return env

    def _start_reader_threads(
        self, process: subprocess.Popen[str], progress: TestProgress, live: Live
    ) -> tuple[threading.Thread, threading.Thread, threading.Thread]:
        """Start threads for reading stdout, stderr, and monitoring."""
        stdout_thread = self._create_stdout_reader(process, progress, live)
        stderr_thread = self._create_stderr_reader(process, progress, live)
        monitor_thread = self._create_monitor_thread(progress)

        stdout_thread.start()
        stderr_thread.start()
        monitor_thread.start()

        return stdout_thread, stderr_thread, monitor_thread

    def _create_stdout_reader(
        self, process: subprocess.Popen[str], progress: TestProgress, live: Live
    ) -> threading.Thread:
        """Create thread for reading stdout."""

        def read_output() -> None:
            if process.stdout:
                for line in iter(process.stdout.readline, ""):
                    if line.strip():
                        self._process_test_output_line(line.strip(), progress)
                        self._update_display_if_needed(progress, live)
                    if progress.is_complete:
                        break

        return threading.Thread(target=read_output, daemon=True)

    def _create_stderr_reader(
        self, process: subprocess.Popen[str], progress: TestProgress, live: Live
    ) -> threading.Thread:
        """Create thread for reading stderr."""

        def read_stderr() -> None:
            if process.stderr:
                for line in iter(process.stderr.readline, ""):
                    if line.strip() and "warning" not in line.lower():
                        progress.update(current_test=f"⚠️ {line.strip()}")
                        self._update_display_if_needed(progress, live)

        return threading.Thread(target=read_stderr, daemon=True)

    def _create_monitor_thread(self, progress: TestProgress) -> threading.Thread:
        """Create thread for monitoring stuck tests."""

        def monitor_stuck_tests() -> None:
            last_update = time.time()
            last_test = ""

            while not progress.is_complete:
                time.sleep(5)
                current_time = time.time()

                if (
                    progress.current_test == last_test
                    and current_time - last_update > 30
                ):
                    self._mark_test_as_stuck(progress, progress.current_test)
                    last_update = current_time
                elif progress.current_test != last_test:
                    last_test = progress.current_test
                    last_update = current_time

        return threading.Thread(target=monitor_stuck_tests, daemon=True)

    def _process_test_output_line(self, line: str, progress: TestProgress) -> None:
        """Process a single line of test output."""
        self._parse_test_line(line, progress)

    def _parse_test_line(self, line: str, progress: TestProgress) -> None:
        """Parse test output line and update progress."""
        # Handle collection completion
        if self._handle_collection_completion(line, progress):
            return

        # Handle session events
        if self._handle_session_events(line, progress):
            return

        # Handle collection progress
        if self._handle_collection_progress(line, progress):
            return

        # Handle test execution
        if self._handle_test_execution(line, progress):
            return

    def _handle_collection_completion(self, line: str, progress: TestProgress) -> bool:
        """Handle test collection completion."""
        if "collected" in line and ("item" in line or "test" in line):
            match = re.search(r"(\d+) (?:item|test)", line)
            if match:
                progress.update(
                    total_tests=int(match.group(1)),
                    is_collecting=False,
                    collection_status="Collection complete",
                )
                return True
        return False

    def _handle_session_events(self, line: str, progress: TestProgress) -> bool:
        """Handle pytest session events."""
        if "session starts" in line and progress.collection_status != "Session started":
            progress.update(collection_status="Session started")
            return True
        elif (
            "test session starts" in line
            and progress.collection_status != "Test collection started"
        ):
            progress.update(collection_status="Test collection started")
            return True
        return False

    def _handle_collection_progress(self, line: str, progress: TestProgress) -> bool:
        """Handle collection progress updates."""
        if progress.is_collecting:
            # Look for file discovery patterns
            if line.endswith(".py") and ("test_" in line or "_test.py" in line):
                with progress._lock:
                    if line not in progress._seen_files:
                        progress._seen_files.add(line)
                        progress.files_discovered += 1
                        progress.collection_status = (
                            f"Found {progress.files_discovered} test files..."
                        )
                return True
        return False

    def _handle_test_execution(self, line: str, progress: TestProgress) -> bool:
        """Handle test execution progress."""
        # Test result patterns
        if " PASSED " in line:
            progress.update(passed=progress.passed + 1)
            self._extract_current_test(line, progress)
            return True
        elif " FAILED " in line:
            progress.update(failed=progress.failed + 1)
            self._extract_current_test(line, progress)
            return True
        elif " SKIPPED " in line:
            progress.update(skipped=progress.skipped + 1)
            self._extract_current_test(line, progress)
            return True
        elif " ERROR " in line:
            progress.update(errors=progress.errors + 1)
            self._extract_current_test(line, progress)
            return True
        elif "::" in line and any(x in line for x in ("RUNNING", "test_")):
            self._handle_running_test(line, progress)
            return True

        return False

    def _handle_running_test(self, line: str, progress: TestProgress) -> None:
        """Handle currently running test indicator."""
        if "::" in line:
            # Extract test name from line
            test_parts = line.split("::")
            if len(test_parts) >= 2:
                test_name = "::".join(test_parts[-2:])
                progress.update(current_test=test_name)

    def _extract_current_test(self, line: str, progress: TestProgress) -> None:
        """Extract current test name from output line."""
        if "::" in line:
            # Extract test identifier
            parts = line.split(" ")
            for part in parts:
                if "::" in part:
                    progress.update(current_test=part)
                    break

    def _update_display_if_needed(self, progress: TestProgress, live: Live) -> None:
        """Update display if enough time has passed or significant change occurred."""
        if self._should_refresh_display(progress):
            live.update(progress.format_progress())

    def _should_refresh_display(self, progress: TestProgress) -> bool:
        """Determine if display should be refreshed."""
        # Only refresh on significant changes to reduce spam
        return (
            progress.is_complete
            or progress.total_tests > 0
            or len(progress.current_test) > 0
        )

    def _mark_test_as_stuck(self, progress: TestProgress, test_name: str) -> None:
        """Mark a test as potentially stuck."""
        if test_name:
            progress.update(current_test=f"🐌 {test_name} (slow)")

    def _cleanup_threads(self, threads: list[threading.Thread]) -> None:
        """Clean up reader threads."""
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=1.0)

    def _handle_progress_error(
        self, process: subprocess.Popen[str], progress: TestProgress, error_msg: str
    ) -> None:
        """Handle progress tracking errors."""
        process.terminate()
        progress.update(is_complete=True, current_test=f"❌ {error_msg}")

    def _execute_test_process_with_progress(
        self,
        cmd: list[str],
        env: dict[str, str],
        progress: TestProgress,
        progress_callback: t.Callable[[dict[str, t.Any]], None],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        """Execute test process with AI progress tracking."""
        process = subprocess.Popen(
            cmd,
            cwd=self.pkg_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        stdout_lines = self._read_stdout_with_progress(
            process, progress, progress_callback
        )
        stderr_lines = self._read_stderr_lines(process)

        return_code = self._wait_for_process_completion(process, timeout)

        return subprocess.CompletedProcess(
            cmd, return_code, "\n".join(stdout_lines), "\n".join(stderr_lines)
        )

    def _read_stdout_with_progress(
        self,
        process: subprocess.Popen[str],
        progress: TestProgress,
        progress_callback: t.Callable[[dict[str, t.Any]], None],
    ) -> list[str]:
        """Read stdout with progress updates."""
        stdout_lines = []

        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                if not line:
                    break

                line = line.strip()
                if line:
                    stdout_lines.append(line)
                    self._process_test_output_line(line, progress)
                    self._emit_ai_progress(progress, progress_callback)

        return stdout_lines

    def _read_stderr_lines(self, process: subprocess.Popen[str]) -> list[str]:
        """Read stderr lines."""
        stderr_lines = []

        if process.stderr:
            for line in iter(process.stderr.readline, ""):
                if not line:
                    break
                line = line.strip()
                if line:
                    stderr_lines.append(line)

        return stderr_lines

    def _wait_for_process_completion(
        self, process: subprocess.Popen[str], timeout: int
    ) -> int:
        """Wait for process completion with timeout."""
        try:
            process.wait(timeout=timeout)
            return process.returncode
        except subprocess.TimeoutExpired:
            process.terminate()
            return -1

    def _emit_ai_progress(
        self,
        progress: TestProgress,
        progress_callback: t.Callable[[dict[str, t.Any]], None],
    ) -> None:
        """Emit progress update for AI consumption."""
        progress_data = {
            "type": "test_progress",
            "total_tests": progress.total_tests,
            "completed": progress.completed,
            "passed": progress.passed,
            "failed": progress.failed,
            "skipped": progress.skipped,
            "errors": progress.errors,
            "current_test": progress.current_test,
            "elapsed_time": progress.elapsed_time,
            "is_collecting": progress.is_collecting,
            "is_complete": progress.is_complete,
            "collection_status": progress.collection_status,
        }

        if progress.eta_seconds:
            progress_data["eta_seconds"] = progress.eta_seconds

        from contextlib import suppress

        with suppress(Exception):
            # Don't let progress callback errors affect test execution
            progress_callback(progress_data)
