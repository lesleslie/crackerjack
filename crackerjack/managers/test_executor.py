import re
import subprocess
import threading
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from rich.console import Console
from rich.live import Live

from .test_progress import TestProgress


class TestExecutor:
    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path

    def execute_with_progress(
        self,
        cmd: list[str],
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[str]:
        # Pre-collect tests to set the total count upfront if possible
        total_tests = self._pre_collect_tests(cmd)
        progress = self._initialize_progress()
        if total_tests > 0:
            # Set the total tests but keep is_collecting as True initially to ensure
            # the collection header appears in pytest output
            progress.update(total_tests=total_tests)
            # Set the collection status to indicate we pre-collected
            progress.collection_status = (
                f"Pre-collected {total_tests} tests, starting execution..."
            )

        return self._execute_with_live_progress(cmd, timeout, progress=progress)

    def execute_with_ai_progress(
        self,
        cmd: list[str],
        progress_callback: t.Callable[[dict[str, t.Any]], None],
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[str]:
        # Pre-collect tests to set the total count upfront if possible
        total_tests = self._pre_collect_tests(cmd)
        progress = self._initialize_progress()
        if total_tests > 0:
            # Set the total tests but keep is_collecting as True initially to ensure
            # the collection header appears in pytest output
            progress.update(total_tests=total_tests)
            # Set the collection status to indicate we pre-collected
            progress.collection_status = (
                f"Pre-collected {total_tests} tests, starting execution..."
            )

        return self._run_test_command_with_ai_progress(
            cmd, progress_callback, timeout, progress=progress
        )

    def _pre_collect_tests(self, original_cmd: list[str]) -> int:
        """
        Run a preliminary collection-only pass to determine the total number of tests.
        This allows us to show the real test count from the start.
        """
        # Create collection command by replacing the original command with the collect-only version
        # Preserve the test paths and other options, but replace the main pytest command
        collect_cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            "--collect-only",
            "-qq",
        ]  # Use -qq to minimize output but still get collection info

        # Extract test paths and relevant options from original command
        test_path_found = False
        for i, arg in enumerate(original_cmd):
            if not arg.startswith("-") and (
                arg.startswith("tests") or arg == "." or arg.endswith(".py")
            ):
                # Add test paths to collection command
                collect_cmd.extend(original_cmd[i:])
                test_path_found = True
                break

        # If no test path found, use the default
        if not test_path_found:
            collect_cmd.append("tests" if (self.pkg_path / "tests").exists() else ".")

        with suppress(Exception):
            result = subprocess.run(
                collect_cmd,
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                timeout=30,  # Collection should be fast
                env=self._setup_test_environment(),
            )

            # Parse output to extract number of collected tests
            if result.stdout:
                # Look for the "collected X items" pattern (with more flexible matching)
                # Match both "collected X items" and "collected X tests"
                match = re.search(r"collected\s+(\d+)\s+(?:item|test)s?", result.stdout)
                if match:
                    return int(match.group(1))

        return 0  # Return 0 if collection fails

    def _execute_with_live_progress(
        self, cmd: list[str], timeout: int, progress: TestProgress | None = None
    ) -> subprocess.CompletedProcess[str]:
        if progress is None:
            progress = self._initialize_progress()

        with Live(
            progress.format_progress(), console=self.console, transient=True
        ) as live:
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

            stdout_thread, stderr_thread, monitor_thread = self._start_reader_threads(
                process, progress, live
            )

            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._handle_progress_error(
                    process, progress, "Test execution timed out"
                )

            self._cleanup_threads([stdout_thread, stderr_thread, monitor_thread])

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
        progress: TestProgress | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if progress is None:
            progress = self._initialize_progress()
        env = self._setup_coverage_env()

        result = self._execute_test_process_with_progress(
            cmd, env, progress, progress_callback, timeout
        )

        return result

    def _initialize_progress(self) -> TestProgress:
        progress = TestProgress()
        progress.start_time = time.time()
        return progress

    def _setup_test_environment(self) -> dict[str, str]:
        import os

        cache_dir = Path.home() / ".cache" / "crackerjack" / "coverage"
        cache_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(cache_dir / ".coverage")
        env["PYTEST_CURRENT_TEST"] = ""
        return env

    def _setup_coverage_env(self) -> dict[str, str]:
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
        def read_stderr() -> None:
            if process.stderr:
                for line in iter(process.stderr.readline, ""):
                    if line.strip() and "warning" not in line.lower():
                        progress.update(current_test=f"⚠️ {line.strip()}")
                        self._update_display_if_needed(progress, live)

        return threading.Thread(target=read_stderr, daemon=True)

    def _create_monitor_thread(self, progress: TestProgress) -> threading.Thread:
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
        self._parse_test_line(line, progress)

    def _parse_test_line(self, line: str, progress: TestProgress) -> None:
        if self._handle_collection_completion(line, progress):
            return

        if self._handle_session_events(line, progress):
            return

        if self._handle_collection_progress(line, progress):
            return

        if self._handle_test_execution(line, progress):
            return

    def _handle_collection_completion(self, line: str, progress: TestProgress) -> bool:
        if "collected" in line and ("item" in line or "test" in line):
            # Fixed regex: \d+ (one or more digits) and (?:item|test) (alternation without spaces)
            match = re.search(r"(\d+)\s+(?:item|test)", line)
            if match:
                progress.update(
                    total_tests=int(match.group(1)),
                    is_collecting=False,
                    collection_status="Collection complete",
                )
                return True
        return False

    def _handle_session_events(self, line: str, progress: TestProgress) -> bool:
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
        if progress.is_collecting:
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
        elif ":: " in line and any(x in line for x in ("RUNNING", "test_")):
            self._handle_running_test(line, progress)
            return True

        return False

    def _handle_running_test(self, line: str, progress: TestProgress) -> None:
        if ":: " in line:
            test_parts = line.split(":: ")
            if len(test_parts) >= 2:
                test_name = ":: ".join(test_parts[-2:])
                progress.update(current_test=test_name)

    def _extract_current_test(self, line: str, progress: TestProgress) -> None:
        if ":: " in line:
            parts = line.split(" ")
            for part in parts:
                if ":: " in part:
                    progress.update(current_test=part)
                    break

    def _update_display_if_needed(self, progress: TestProgress, live: Live) -> None:
        if self._should_refresh_display(progress):
            live.update(progress.format_progress())

    def _should_refresh_display(self, progress: TestProgress) -> bool:
        return (
            progress.is_complete
            or progress.total_tests > 0
            or len(progress.current_test) > 0
        )

    def _mark_test_as_stuck(self, progress: TestProgress, test_name: str) -> None:
        if test_name:
            progress.update(current_test=f"🐌 {test_name} (slow)")

    def _cleanup_threads(self, threads: list[threading.Thread]) -> None:
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=1.0)

    def _handle_progress_error(
        self, process: subprocess.Popen[str], progress: TestProgress, error_msg: str
    ) -> None:
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
            progress_callback(progress_data)
