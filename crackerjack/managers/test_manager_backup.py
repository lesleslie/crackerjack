import re
import subprocess
import threading
import time
import typing as t
from pathlib import Path

from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.table import Table

from crackerjack.models.protocols import OptionsProtocol
from crackerjack.services.coverage_ratchet import CoverageRatchetService


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
        self._seen_files: set[str] = set()  # Track seen files to prevent duplicates

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

    def format_progress(self) -> Align:
        """Format test progress display with appropriate phase-specific content."""
        with self._lock:
            if self.is_collecting:
                table = self._format_collection_progress()
            else:
                table = self._format_execution_progress()
            # Left-align the table as requested
            return Align.left(table)

    def _format_collection_progress(self) -> Table:
        """Format progress display for test collection phase."""
        table = Table(
            title="🔍 Test Collection",
            header_style="bold yellow",
            show_lines=True,
            border_style="yellow",
            title_style="bold yellow",
            expand=True,  # Use full terminal width like rich.live demo
            min_width=80,  # Ensure minimum width
        )

        # Add multiple columns for better alignment (like complexipy)
        table.add_column("Type", style="cyan", ratio=1)
        table.add_column("Details", style="white", ratio=3)  # Wider middle column
        table.add_column("Count", style="green", ratio=1)

        # Add status
        table.add_row("Status", self.collection_status, "")

        # Add collection stats
        if self.files_discovered > 0:
            table.add_row("Files", "Test files discovered", str(self.files_discovered))

        if self.total_tests > 0:
            table.add_row("Tests", "Total tests found", str(self.total_tests))

        # Add progress bar
        if self.files_discovered > 0:
            progress_chars = "▓" * min(self.files_discovered, 15) + "░" * max(
                0, 15 - self.files_discovered
            )
            table.add_row(
                "Progress", f"[{progress_chars}]", f"{self.files_discovered}/15"
            )

        # Add duration
        table.add_row("Duration", f"{self.elapsed_time:.1f} seconds", "")

        return table

    def _format_execution_progress(self) -> Table:
        """Format progress display for test execution phase."""
        table = Table(
            title="🧪 Test Execution",
            header_style="bold cyan",
            show_lines=True,
            border_style="cyan",
            title_style="bold cyan",
            expand=True,  # Use full terminal width like rich.live demo
            min_width=80,  # Ensure minimum width
        )

        # Add multiple columns for better alignment (like complexipy)
        table.add_column("Metric", style="cyan", ratio=1)
        table.add_column("Details", style="white", ratio=3)  # Wider middle column
        table.add_column("Count", style="green", ratio=1)

        # Test results summary
        if self.total_tests > 0:
            table.add_row("Total", "Total tests", str(self.total_tests))
            table.add_row("Passed", "Tests passed", f"[green]{self.passed}[/green]")

            if self.failed > 0:
                table.add_row("Failed", "Tests failed", f"[red]{self.failed}[/red]")
            if self.skipped > 0:
                table.add_row(
                    "Skipped", "Tests skipped", f"[yellow]{self.skipped}[/yellow]"
                )
            if self.errors > 0:
                table.add_row("Errors", "Test errors", f"[red]{self.errors}[/red]")

        # Progress percentage and bar
        if self.total_tests > 0:
            percentage = (self.completed / self.total_tests) * 100
            filled = int((self.completed / self.total_tests) * 15)
            bar = "█" * filled + "░" * (15 - filled)
            table.add_row("Progress", f"[{bar}]", f"{percentage:.1f}%")

        # Current test
        if self.current_test:
            test_name = self.current_test
            if len(test_name) > 40:  # Reasonable truncation
                test_name = test_name[:37] + "..."
            table.add_row("Current", test_name, "")

        # Duration and ETA
        duration_text = f"{self.elapsed_time:.1f}s"
        if self.eta_seconds is not None and self.eta_seconds > 0:
            table.add_row("Duration", duration_text, f"ETA: ~{self.eta_seconds:.0f}s")
        else:
            table.add_row("Duration", duration_text, "")

        return table


class TestManagementImpl:
    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self._last_test_failures: list[str] = []
        self._progress_callback: t.Callable[[dict[str, t.Any]], None] | None = None
        self.coverage_ratchet = CoverageRatchetService(pkg_path, console)
        self.coverage_ratchet_enabled = True

    def set_progress_callback(
        self,
        callback: t.Callable[[dict[str, t.Any]], None] | None,
    ) -> None:
        """Set callback for AI mode structured progress updates."""
        self._progress_callback = callback

    def set_coverage_ratchet_enabled(self, enabled: bool) -> None:
        """Enable or disable the coverage ratchet system."""
        self.coverage_ratchet_enabled = enabled
        if enabled:
            self.console.print(
                "[cyan]📊[/cyan] Coverage ratchet enabled - targeting 100% coverage"
            )
        else:
            self.console.print("[yellow]⚠️[/yellow] Coverage ratchet disabled")

    def get_coverage_ratchet_status(self) -> dict[str, t.Any]:
        """Get comprehensive coverage ratchet status."""
        return self.coverage_ratchet.get_status_report()

    def _run_test_command(
        self,
        cmd: list[str],
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[str]:
        import os
        from pathlib import Path

        # Set up coverage data file in cache directory
        cache_dir = Path.home() / ".cache" / "crackerjack" / "coverage"
        cache_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(cache_dir / ".coverage")

        return subprocess.run(
            cmd,
            check=False,
            cwd=self.pkg_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    def _run_test_command_with_progress(
        self,
        cmd: list[str],
        timeout: int = 600,
        show_progress: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not show_progress:
            return self._run_test_command(cmd, timeout)

        try:
            return self._execute_with_live_progress(cmd, timeout)
        except Exception as e:
            return self._handle_progress_error(e, cmd, timeout)

    def _execute_with_live_progress(
        self,
        cmd: list[str],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        progress = self._initialize_progress()
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        # Use a mutable container to share last_activity_time between threads
        activity_tracker = {"last_time": time.time()}

        with (
            Live(
                progress.format_progress(),
                refresh_per_second=2,
                console=self.console,
                auto_refresh=False,
                transient=True,
            ) as live,
            subprocess.Popen(
                cmd,
                cwd=self.pkg_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._setup_test_environment(),
            ) as process,
        ):
            threads = self._start_reader_threads(
                process,
                progress,
                stdout_lines,
                stderr_lines,
                live,
                activity_tracker,
            )

            returncode = self._wait_for_completion(process, progress, live, timeout)
            self._cleanup_threads(threads, progress, live)

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=returncode,
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
            )

    def _initialize_progress(self) -> TestProgress:
        progress = TestProgress()
        progress.start_time = time.time()
        progress.collection_status = "Initializing test collection..."
        return progress

    def _setup_test_environment(self) -> dict[str, str]:
        import os
        from pathlib import Path

        cache_dir = Path.home() / ".cache" / "crackerjack" / "coverage"
        cache_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(cache_dir / ".coverage")
        return env

    def _start_reader_threads(
        self,
        process: subprocess.Popen[str],
        progress: TestProgress,
        stdout_lines: list[str],
        stderr_lines: list[str],
        live: Live,
        activity_tracker: dict[str, float],
    ) -> dict[str, threading.Thread]:
        read_output = self._create_stdout_reader(
            process,
            progress,
            stdout_lines,
            live,
            activity_tracker,
        )
        read_stderr = self._create_stderr_reader(process, stderr_lines)
        monitor_stuck = self._create_monitor_thread(
            process,
            progress,
            live,
            activity_tracker,
        )

        threads = {
            "stdout": threading.Thread(target=read_output, daemon=True),
            "stderr": threading.Thread(target=read_stderr, daemon=True),
            "monitor": threading.Thread(target=monitor_stuck, daemon=True),
        }

        for thread in threads.values():
            thread.start()

        return threads

    def _create_stdout_reader(
        self,
        process: subprocess.Popen[str],
        progress: TestProgress,
        stdout_lines: list[str],
        live: Live,
        activity_tracker: dict[str, float],
    ) -> t.Callable[[], None]:
        def read_output() -> None:
            refresh_state = {"last_refresh": 0, "last_content": ""}

            if process.stdout:
                for line in iter(process.stdout.readline, ""):
                    if not line:
                        break

                    processed_line = line.rstrip()
                    if processed_line.strip():
                        self._process_test_output_line(
                            processed_line, stdout_lines, progress, activity_tracker
                        )
                        self._update_display_if_needed(progress, live, refresh_state)

        return read_output

    def _process_test_output_line(
        self,
        line: str,
        stdout_lines: list[str],
        progress: TestProgress,
        activity_tracker: dict[str, float],
    ) -> None:
        """Process a single line of test output."""
        stdout_lines.append(line)
        self._parse_test_line(line, progress)
        activity_tracker["last_time"] = time.time()

    def _update_display_if_needed(
        self,
        progress: TestProgress,
        live: Live,
        refresh_state: dict[str, t.Any],
    ) -> None:
        """Update display if refresh criteria are met."""
        current_time = time.time()
        refresh_interval = self._get_refresh_interval(progress)
        current_content = self._get_current_content_signature(progress)

        if self._should_refresh_display(
            current_time, refresh_state, refresh_interval, current_content
        ):
            live.update(progress.format_progress())
            live.refresh()
            refresh_state["last_refresh"] = current_time
            refresh_state["last_content"] = current_content

    def _get_refresh_interval(self, progress: TestProgress) -> float:
        """Get appropriate refresh interval based on test phase."""
        return 1.0 if progress.is_collecting else 0.25

    def _get_current_content_signature(self, progress: TestProgress) -> str:
        """Get a signature of current progress content for change detection."""
        return f"{progress.collection_status}:{progress.files_discovered}:{progress.total_tests}"

    def _should_refresh_display(
        self,
        current_time: float,
        refresh_state: dict[str, t.Any],
        refresh_interval: float,
        current_content: str,
    ) -> bool:
        """Determine if display should be refreshed."""
        time_elapsed = current_time - refresh_state["last_refresh"] > refresh_interval
        content_changed = current_content != refresh_state["last_content"]
        return time_elapsed or content_changed

    def _create_stderr_reader(
        self,
        process: subprocess.Popen[str],
        stderr_lines: list[str],
    ) -> t.Callable[[], None]:
        def read_stderr() -> None:
            if process.stderr:
                for line in iter(process.stderr.readline, ""):
                    if not line:
                        break
                    stderr_lines.append(line.rstrip())

        return read_stderr

    def _create_monitor_thread(
        self,
        process: subprocess.Popen[str],
        progress: TestProgress,
        live: Live,
        activity_tracker: dict[str, float],
    ) -> t.Callable[[], None]:
        def monitor_stuck_tests() -> None:
            while process.poll() is None:
                time.sleep(5)
                current_time = time.time()
                if current_time - activity_tracker["last_time"] > 30:
                    self._mark_test_as_stuck(
                        progress,
                        current_time - activity_tracker["last_time"],
                        live,
                    )

        return monitor_stuck_tests

    def _mark_test_as_stuck(
        self,
        progress: TestProgress,
        stuck_time: float,
        live: Live,
    ) -> None:
        if progress.current_test and "stuck" not in progress.current_test.lower():
            progress.update(
                current_test=f"{progress.current_test} (possibly stuck - {stuck_time:.0f}s)",
            )
            live.update(progress.format_progress())
            live.refresh()

    def _wait_for_completion(
        self,
        process: subprocess.Popen[str],
        progress: TestProgress,
        live: Live,
        timeout: int,
    ) -> int:
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            progress.update(current_test="TIMEOUT - Process killed")
            live.update(progress.format_progress())
            live.refresh()
            raise

    def _cleanup_threads(
        self,
        threads: dict[str, threading.Thread],
        progress: TestProgress,
        live: Live,
    ) -> None:
        threads["stdout"].join(timeout=1)
        threads["stderr"].join(timeout=1)
        progress.is_complete = True
        live.update(progress.format_progress())
        live.refresh()

    def _handle_progress_error(
        self,
        error: Exception,
        cmd: list[str],
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        from contextlib import suppress

        with suppress(Exception):
            self.console.print(f"[red]❌ Progress display failed: {error}[/red]")
            self.console.print("[yellow]⚠️ Falling back to standard mode[/yellow]")
        return self._run_test_command(cmd, timeout)

    def _parse_test_line(self, line: str, progress: TestProgress) -> None:
        if self._handle_collection_completion(line, progress):
            return
        if self._handle_session_events(line, progress):
            return
        if self._handle_collection_progress(line, progress):
            return
        if self._handle_test_execution(line, progress):
            return
        self._handle_running_test(line, progress)

    def _handle_collection_completion(self, line: str, progress: TestProgress) -> bool:
        if match := re.search(r"collected (\d+) items?", line):
            progress.update(
                total_tests=int(match.group(1)),
                is_collecting=False,
                current_test="Starting test execution...",
            )
            return True
        return False

    def _handle_session_events(self, line: str, progress: TestProgress) -> bool:
        if "test session starts" in line.lower():
            progress.update(collection_status="Session starting...")
            return True
        if line.startswith("collecting") or "collecting" in line.lower():
            progress.update(collection_status="Collecting tests...")
            return True
        return False

    def _handle_collection_progress(self, line: str, progress: TestProgress) -> bool:
        if not progress.is_collecting:
            return False

        # Only process meaningful collection lines, not every line containing ".py"
        if line.strip().startswith("collecting") or "collecting" in line.lower():
            progress.update(collection_status="Collecting tests...")
            return True

        # Very restrictive file discovery - only count actual test discoveries
        if (
            "::" in line
            and ".py" in line
            and ("test_" in line or "tests/" in line)
            and not any(
                status in line for status in ("PASSED", "FAILED", "SKIPPED", "ERROR")
            )
        ):
            # Only update if we haven't seen this file before
            filename = line.split("/")[-1] if "/" in line else line.split("::")[0]
            if filename.endswith(".py") and filename not in progress._seen_files:
                progress._seen_files.add(filename)
                new_count = progress.files_discovered + 1
                progress.update(
                    files_discovered=new_count,
                    collection_status=f"Discovering tests... ({new_count} files)",
                )
            return True

        return False

    def _handle_test_execution(self, line: str, progress: TestProgress) -> bool:
        if not (
            "::" in line
            and any(
                status in line for status in ("PASSED", "FAILED", "SKIPPED", "ERROR")
            )
        ):
            return False

        if "PASSED" in line:
            progress.update(passed=progress.passed + 1)
        elif "FAILED" in line:
            progress.update(failed=progress.failed + 1)
        elif "SKIPPED" in line:
            progress.update(skipped=progress.skipped + 1)
        elif "ERROR" in line:
            progress.update(errors=progress.errors + 1)

        self._extract_current_test(line, progress)
        return True

    def _handle_running_test(self, line: str, progress: TestProgress) -> None:
        if "::" not in line or any(
            status in line for status in ("PASSED", "FAILED", "SKIPPED", "ERROR")
        ):
            return

        parts = line.split()
        if parts and "::" in parts[0]:
            test_path = parts[0]
            if "/" in test_path:
                test_path = test_path.split("/")[-1]
            progress.update(current_test=f"Running: {test_path}")

    def _extract_current_test(self, line: str, progress: TestProgress) -> None:
        # Extract test name from pytest output line
        parts = line.split()
        if parts and "::" in parts[0]:
            test_path = parts[0]
            # Simplify the test path for display
            if "/" in test_path:
                test_path = test_path.split("/")[-1]  # Get just the filename part
            progress.update(current_test=test_path)

    def _run_test_command_with_ai_progress(
        self,
        cmd: list[str],
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[str]:
        """Run tests with periodic structured progress updates for AI mode."""
        try:
            env = self._setup_coverage_env()
            progress = TestProgress()
            progress.start_time = time.time()

            return self._execute_test_process_with_progress(cmd, timeout, env, progress)
        except Exception:
            # Fallback to standard mode
            return self._run_test_command(cmd, timeout)

    def _setup_coverage_env(self) -> dict[str, str]:
        """Set up environment with coverage configuration."""
        import os
        from pathlib import Path

        cache_dir = Path.home() / ".cache" / "crackerjack" / "coverage"
        cache_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(cache_dir / ".coverage")
        return env

    def _execute_test_process_with_progress(
        self,
        cmd: list[str],
        timeout: int,
        env: dict[str, str],
        progress: TestProgress,
    ) -> subprocess.CompletedProcess[str]:
        """Execute test process with progress tracking."""
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        last_update_time = [time.time()]  # Use list for mutable reference

        with subprocess.Popen(
            cmd,
            cwd=self.pkg_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        ) as process:
            # Start reader threads
            stdout_thread = threading.Thread(
                target=self._read_stdout_with_progress,
                args=(process, stdout_lines, progress, last_update_time),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._read_stderr_lines,
                args=(process, stderr_lines),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process completion
            returncode = self._wait_for_process_completion(process, timeout)

            # Clean up threads
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

            # Final progress update
            progress.is_complete = True
            self._emit_ai_progress(progress)

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=returncode,
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
            )

    def _read_stdout_with_progress(
        self,
        process: subprocess.Popen[str],
        stdout_lines: list[str],
        progress: TestProgress,
        last_update_time: list[float],
    ) -> None:
        """Read stdout and update progress."""
        if not process.stdout:
            return

        for line in iter(process.stdout.readline, ""):
            if not line:
                break
            line = line.rstrip()
            stdout_lines.append(line)
            self._parse_test_line(line, progress)

            # Emit structured progress every 10 seconds
            current_time = time.time()
            if current_time - last_update_time[0] >= 10:
                self._emit_ai_progress(progress)
                last_update_time[0] = current_time

    def _read_stderr_lines(
        self,
        process: subprocess.Popen[str],
        stderr_lines: list[str],
    ) -> None:
        """Read stderr lines."""
        if not process.stderr:
            return

        for line in iter(process.stderr.readline, ""):
            if not line:
                break
            stderr_lines.append(line.rstrip())

    def _wait_for_process_completion(
        self,
        process: subprocess.Popen[str],
        timeout: int,
    ) -> int:
        """Wait for process completion with timeout handling."""
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            raise

    def _emit_ai_progress(self, progress: TestProgress) -> None:
        """Emit structured progress data for AI consumption."""
        if not self._progress_callback:
            return

        progress_data = {
            "timestamp": progress.elapsed_time,
            "status": "complete" if progress.is_complete else "running",
            "progress_percentage": (progress.completed / progress.total_tests * 100)
            if progress.total_tests > 0
            else 0,
            "completed": progress.completed,
            "total": progress.total_tests,
            "passed": progress.passed,
            "failed": progress.failed,
            "skipped": progress.skipped,
            "errors": progress.errors,
            "current_test": progress.current_test,
            "elapsed_seconds": progress.elapsed_time,
            "eta_seconds": progress.eta_seconds,
        }

        # Include console-friendly message for periodic updates
        if not progress.is_complete and progress.total_tests > 0:
            percentage = progress.completed / progress.total_tests * 100
            self.console.print(
                f"📊 Progress update ({progress.elapsed_time:.0f}s): "
                f"{progress.completed}/{progress.total_tests} tests completed ({percentage:.0f}%)",
            )

        self._progress_callback(progress_data)

    def _get_optimal_workers(self, options: OptionsProtocol) -> int:
        if options.test_workers > 0:
            return options.test_workers
        import os

        cpu_count = os.cpu_count() or 1
        test_files = list(self.pkg_path.glob("tests/test_*.py"))
        if len(test_files) < 5:
            return min(2, cpu_count)

        return min(cpu_count, 8)

    def _get_test_timeout(self, options: OptionsProtocol) -> int:
        if options.test_timeout > 0:
            return options.test_timeout
        test_files = list(self.pkg_path.glob("tests/test_*.py"))
        base_timeout = 300

        import math

        calculated_timeout = base_timeout + int(math.sqrt(len(test_files)) * 20)
        return min(calculated_timeout, 600)

    def run_tests(self, options: OptionsProtocol) -> bool:
        """Main entry point for test execution with proper error handling."""
        self._last_test_failures = []
        start_time = time.time()

        try:
            return self._execute_test_workflow(options, start_time)
        except subprocess.TimeoutExpired:
            return self._handle_test_timeout(start_time)
        except Exception as e:
            return self._handle_test_error(start_time, e)

    def _execute_test_workflow(
        self,
        options: OptionsProtocol,
        start_time: float,
    ) -> bool:
        """Execute the complete test workflow."""
        cmd = self._build_test_command(options)
        timeout = self._get_test_timeout(options)
        result = self._execute_tests_with_appropriate_mode(cmd, timeout, options)
        duration = time.time() - start_time
        return self._process_test_results(result, duration)

    def _execute_tests_with_appropriate_mode(
        self,
        cmd: list[str],
        timeout: int,
        options: OptionsProtocol,
    ) -> subprocess.CompletedProcess[str]:
        """Execute tests using the appropriate mode based on options."""
        execution_mode = self._determine_execution_mode(options)
        extended_timeout = timeout + 60

        if execution_mode == "ai_progress":
            self._print_test_start_message(cmd, timeout, options)
            return self._run_test_command_with_ai_progress(
                cmd,
                timeout=extended_timeout,
            )
        if execution_mode == "console_progress":
            return self._run_test_command_with_progress(cmd, timeout=extended_timeout)
        # standard mode
        self._print_test_start_message(cmd, timeout, options)
        return self._run_test_command(cmd, timeout=extended_timeout)

    def _determine_execution_mode(self, options: OptionsProtocol) -> str:
        """Determine which execution mode to use based on options."""
        is_ai_mode = getattr(options, "ai_agent", False)
        is_benchmark = options.benchmark

        if is_ai_mode and self._progress_callback:
            return "ai_progress"
        if not is_ai_mode and not is_benchmark:
            return "console_progress"
        return "standard"

    def _handle_test_timeout(self, start_time: float) -> bool:
        """Handle test execution timeout."""
        duration = time.time() - start_time
        self.console.print(f"[red]⏰[/red] Tests timed out after {duration:.1f}s")
        return False

    def _handle_test_error(self, start_time: float, error: Exception) -> bool:
        """Handle test execution errors."""
        self.console.print(f"[red]💥[/red] Test execution failed: {error}")
        return False

    def _build_test_command(self, options: OptionsProtocol) -> list[str]:
        cmd = ["python", "-m", "pytest"]
        self._add_coverage_options(cmd, options)
        self._add_worker_options(cmd, options)
        self._add_benchmark_options(cmd, options)
        self._add_timeout_options(cmd, options)

        # For progress modes, we need verbose output to parse test names
        is_ai_mode = getattr(options, "ai_agent", False)
        needs_verbose = (not is_ai_mode and not options.benchmark) or (
            is_ai_mode and self._progress_callback
        )
        self._add_verbosity_options(cmd, options, force_verbose=bool(needs_verbose))
        self._add_test_path(cmd)

        return cmd

    def _add_coverage_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        if not options.benchmark:
            cmd.extend(["--cov=crackerjack", "--cov-report=term-missing"])

    def _add_worker_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        if not options.benchmark:
            workers = self._get_optimal_workers(options)
            if workers > 1:
                cmd.extend(["-n", str(workers)])
                self.console.print(f"[cyan]🔧[/cyan] Using {workers} test workers")

    def _add_benchmark_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        if options.benchmark:
            self.console.print(
                "[cyan]📊[/cyan] Running in benchmark mode (no parallelization)",
            )
            cmd.append("--benchmark-only")

    def _add_timeout_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        timeout = self._get_test_timeout(options)
        cmd.extend(["--timeout", str(timeout)])

    def _add_verbosity_options(
        self,
        cmd: list[str],
        options: OptionsProtocol,
        force_verbose: bool = False,
    ) -> None:
        if options.verbose or force_verbose:
            cmd.append("-v")

    def _add_test_path(self, cmd: list[str]) -> None:
        test_path = self.pkg_path / "tests"
        if test_path.exists():
            cmd.append(str(test_path))

    def _print_test_start_message(
        self,
        cmd: list[str],
        timeout: int,
        options: OptionsProtocol,
    ) -> None:
        self.console.print(
            f"[yellow]🧪[/yellow] Running tests... (timeout: {timeout}s)",
        )
        if options.verbose:
            self.console.print(f"[dim]Command: {' '.join(cmd)}[/dim]")

    def _process_test_results(
        self,
        result: subprocess.CompletedProcess[str],
        duration: float,
    ) -> bool:
        output = result.stdout + result.stderr
        success = result.returncode == 0

        # Process coverage ratchet if enabled and tests passed
        if self.coverage_ratchet_enabled and success:
            if not self._process_coverage_ratchet():
                return False  # Coverage regression detected

        if success:
            return self._handle_test_success(output, duration)
        return self._handle_test_failure(output, duration)

    def _process_coverage_ratchet(self) -> bool:
        """Process coverage ratchet and return False if regression detected."""
        coverage_data = self.get_coverage()
        if not coverage_data:
            return True

        current_coverage = coverage_data.get("total_coverage", 0)
        ratchet_result = self.coverage_ratchet.update_coverage(current_coverage)

        return self._handle_ratchet_result(ratchet_result)

    def _handle_ratchet_result(self, ratchet_result: dict[str, t.Any]) -> bool:
        """Handle coverage ratchet result and return False if regression detected."""
        status = ratchet_result["status"]

        if status == "improved":
            self._handle_coverage_improvement(ratchet_result)
        elif status == "regression":
            self.console.print(f"[red]📉 {ratchet_result['message']}[/red]")
            return False  # Fail the test run on coverage regression
        elif status == "maintained":
            self.console.print(f"[cyan]📊 {ratchet_result['message']}[/cyan]")

        self._display_progress_visualization()
        return True

    def _handle_coverage_improvement(self, ratchet_result: dict[str, t.Any]) -> None:
        """Handle coverage improvement display and milestone celebration."""
        self.console.print(f"[green]🎉 {ratchet_result['message']}[/green]")

        if "milestones" in ratchet_result and ratchet_result["milestones"]:
            self.coverage_ratchet.display_milestone_celebration(
                ratchet_result["milestones"]
            )

        if "next_milestone" in ratchet_result and ratchet_result["next_milestone"]:
            next_milestone = ratchet_result["next_milestone"]
            points_needed = ratchet_result.get("points_to_next", 0)
            self.console.print(
                f"[cyan]🎯 Next milestone: {next_milestone:.0f}% (+{points_needed:.2f}% needed)[/cyan]"
            )

    def _display_progress_visualization(self) -> None:
        """Display coverage progress visualization."""
        progress_viz = self.coverage_ratchet.get_progress_visualization()
        for line in progress_viz.split("\n"):
            if line.strip():
                self.console.print(f"[dim]{line}[/dim]")

    def _handle_test_success(self, output: str, duration: float) -> bool:
        self.console.print(f"[green]✅[/green] Tests passed ({duration:.1f}s)")
        lines = output.split("\n")
        for line in lines:
            if "passed" in line and ("failed" in line or "error" in line):
                self.console.print(f"[cyan]📊[/cyan] {line.strip()}")
                break

        return True

    def _handle_test_failure(self, output: str, duration: float) -> bool:
        self.console.print(f"[red]❌[/red] Tests failed ({duration:.1f}s)")
        failure_lines = self._extract_failure_lines(output)
        if failure_lines:
            self.console.print("[red]💥[/red] Failure summary: ")
            for line in failure_lines[:10]:
                if line.strip():
                    self.console.print(f" [dim]{line}[/dim]")

        self._last_test_failures = failure_lines or ["Test execution failed"]

        return False

    def _extract_failure_lines(self, output: str) -> list[str]:
        lines = output.split("\n")
        in_failure_section = False
        failure_lines: list[str] = []
        for line in lines:
            if "FAILURES" in line or "ERRORS" in line:
                in_failure_section = True
            elif in_failure_section and line.startswith(" = "):
                break
            elif in_failure_section:
                failure_lines.append(line)

        return failure_lines

    def get_coverage(self) -> dict[str, t.Any]:
        try:
            result = self._run_test_command(
                ["python", "-m", "coverage", "report", "--format=json"],
            )
            if result.returncode == 0:
                import json

                coverage_data = json.loads(result.stdout)

                return {
                    "total_coverage": coverage_data.get("totals", {}).get(
                        "percent_covered",
                        0,
                    ),
                    "files": coverage_data.get("files", {}),
                    "summary": coverage_data.get("totals", {}),
                }
            self.console.print("[yellow]⚠️[/yellow] Could not get coverage data")
            return {}
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Error getting coverage: {e}")
            return {}

    def run_specific_tests(self, test_pattern: str) -> bool:
        try:
            cmd = ["python", "-m", "pytest", "-k", test_pattern, "-v"]
            self.console.print(
                f"[yellow]🎯[/yellow] Running tests matching: {test_pattern}",
            )
            result = self._run_test_command(cmd)
            if result.returncode == 0:
                self.console.print("[green]✅[/green] Specific tests passed")
                return True
            self.console.print("[red]❌[/red] Specific tests failed")
            return False
        except Exception as e:
            self.console.print(f"[red]💥[/red] Error running specific tests: {e}")
            return False

    def validate_test_environment(self) -> bool:
        issues: list[str] = []
        try:
            result = self._run_test_command(["python", "-m", "pytest", "--version"])
            if result.returncode != 0:
                issues.append("pytest not available")
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            issues.append("pytest not accessible")
        test_dir = self.pkg_path / "tests"
        if not test_dir.exists():
            issues.append("tests directory not found")
        test_files = list(test_dir.glob("test_*.py")) if test_dir.exists() else []
        if not test_files:
            issues.append("no test files found")
        if issues:
            self.console.print("[red]❌[/red] Test environment issues: ")
            for issue in issues:
                self.console.print(f" - {issue}")
            return False
        self.console.print("[green]✅[/green] Test environment validated")
        return True

    def get_test_stats(self) -> dict[str, t.Any]:
        test_dir = self.pkg_path / "tests"
        if not test_dir.exists():
            return {"test_files": 0, "total_tests": 0, "test_lines": 0}
        test_files = list(test_dir.glob("test_*.py"))
        total_lines = 0
        total_tests = 0
        for test_file in test_files:
            try:
                content = test_file.read_text()
                total_lines += len(content.split("\n"))
                total_tests += content.count("def test_")
            except (OSError, UnicodeDecodeError, PermissionError):
                continue

        return {
            "test_files": len(test_files),
            "total_tests": total_tests,
            "test_lines": total_lines,
            "avg_tests_per_file": total_tests / len(test_files) if test_files else 0,
        }

    def get_test_failures(self) -> list[str]:
        return self._last_test_failures

    def get_test_command(self, options: OptionsProtocol) -> list[str]:
        return self._build_test_command(options)

    def get_coverage_report(self) -> str | None:
        try:
            coverage_data = self.get_coverage()
            if coverage_data:
                total = coverage_data.get("total", 0)
                return f"Total coverage: {total}%"
            return None
        except Exception:
            return None

    def has_tests(self) -> bool:
        test_files = list(self.pkg_path.glob("tests/test_*.py"))
        return len(test_files) > 0
