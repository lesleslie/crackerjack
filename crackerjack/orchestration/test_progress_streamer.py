import asyncio
import subprocess
import time
import typing as t
from dataclasses import dataclass
from pathlib import Path

from acb.console import Console

from crackerjack.models.protocols import OptionsProtocol
from crackerjack.services.regex_patterns import SAFE_PATTERNS, CompiledPatternCache


@dataclass
class TestProgress:
    test_id: str
    test_file: str
    test_class: str | None = None
    test_method: str | None = None
    status: str = "pending"
    start_time: float | None = None
    end_time: float | None = None
    duration: float | None = None
    output_lines: list[str] | None = None
    error_message: str | None = None
    failure_traceback: str | None = None
    assertions_count: int = 0
    errors_found: int = 0
    warnings_found: int = 0
    error_details: list[dict[str, t.Any]] | None = None

    def __post_init__(self) -> None:
        if self.output_lines is None:
            self.output_lines = []
        if self.error_details is None:
            self.error_details = []
        if self.end_time and self.start_time:
            self.duration = self.end_time - self.start_time

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "test_id": self.test_id,
            "test_file": self.test_file,
            "test_class": self.test_class,
            "test_method": self.test_method,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "output_lines": self.output_lines[-5:] if self.output_lines else [],
            "error_message": self.error_message,
            "failure_traceback": self.failure_traceback[:500]
            if self.failure_traceback
            else None,
            "assertions_count": self.assertions_count,
            "errors_found": self.errors_found,
            "warnings_found": self.warnings_found,
            "error_details": self.error_details,
        }


@dataclass
class TestSuiteProgress:
    total_tests: int = 0
    completed_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    start_time: float | None = None
    end_time: float | None = None
    duration: float | None = None
    coverage_percentage: float | None = None
    current_test: str | None = None

    @property
    def progress_percentage(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.completed_tests / self.total_tests) * 100

    @property
    def success_rate(self) -> float:
        if self.completed_tests == 0:
            return 0.0
        return (self.passed_tests / self.completed_tests) * 100

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "total_tests": self.total_tests,
            "completed_tests": self.completed_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "error_tests": self.error_tests,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "coverage_percentage": self.coverage_percentage,
            "current_test": self.current_test,
            "progress_percentage": self.progress_percentage,
            "success_rate": self.success_rate,
        }


class PytestOutputParser:
    def __init__(self) -> None:
        self.current_test: str | None = None
        self.test_traceback_buffer: list[str] = []
        self.in_traceback = False

        self._test_start_pattern = CompiledPatternCache.get_compiled_pattern(
            SAFE_PATTERNS["pytest_test_start"].pattern
        )
        self._test_result_pattern = CompiledPatternCache.get_compiled_pattern(
            SAFE_PATTERNS["pytest_test_result"].pattern
        )
        self._test_collection_pattern = CompiledPatternCache.get_compiled_pattern(
            SAFE_PATTERNS["pytest_collection_count"].pattern
        )
        self._session_start_pattern = CompiledPatternCache.get_compiled_pattern(
            SAFE_PATTERNS["pytest_session_start"].pattern
        )
        self._coverage_pattern = CompiledPatternCache.get_compiled_pattern(
            SAFE_PATTERNS["pytest_coverage_total"].pattern
        )
        self._detailed_test_pattern = CompiledPatternCache.get_compiled_pattern(
            SAFE_PATTERNS["pytest_detailed_test"].pattern
        )

    def parse_pytest_output(self, output_lines: list[str]) -> dict[str, t.Any]:
        tests: dict[str, TestProgress] = {}
        suite_info = TestSuiteProgress()

        for line in output_lines:
            line = line.strip()
            if not line:
                continue

            self._process_test_collection_line(line, suite_info)
            self._process_test_result_line(line, tests, suite_info)
            self._process_coverage_line(line, suite_info)
            self._process_current_test_line(line, suite_info)

        return {
            "tests": list[t.Any](tests.values()),
            "suite_progress": suite_info,
            "test_count": len(tests),
        }

    def _process_test_collection_line(
        self,
        line: str,
        suite_info: TestSuiteProgress,
    ) -> None:
        if match := self._test_collection_pattern.search(line):
            assert match is not None  # Type checker: match cannot be None here
            suite_info.total_tests = int(match.group(1))

    def _process_test_result_line(
        self,
        line: str,
        tests: dict[str, TestProgress],
        suite_info: TestSuiteProgress,
    ) -> None:
        if match := self._detailed_test_pattern.match(line):
            assert match is not None  # Type checker: match cannot be None here
            file_path, test_name, status = match.groups()
            test_id = f"{file_path}:: {test_name}"

            if test_id not in tests:
                tests[test_id] = self._create_test_progress(
                    file_path,
                    test_name,
                    test_id,
                )

            self._update_test_progress(tests[test_id], status)
            self._update_suite_counts(suite_info, status)

    def _create_test_progress(
        self,
        file_path: str,
        test_name: str,
        test_id: str,
    ) -> TestProgress:
        test_file = Path(file_path).name
        test_parts = test_name.split(":: ")
        test_class = test_parts[0] if len(test_parts) > 1 else None
        test_method = test_parts[-1]

        return TestProgress(
            test_id=test_id,
            test_file=test_file,
            test_class=test_class,
            test_method=test_method,
        )

    def _update_test_progress(self, test_progress: TestProgress, status: str) -> None:
        test_progress.status = status.lower()
        test_progress.end_time = time.time()

    def _update_suite_counts(self, suite_info: TestSuiteProgress, status: str) -> None:
        suite_info.completed_tests += 1
        if status == "PASSED":
            suite_info.passed_tests += 1
        elif status == "FAILED":
            suite_info.failed_tests += 1
        elif status == "SKIPPED":
            suite_info.skipped_tests += 1
        elif status == "ERROR":
            suite_info.error_tests += 1

    def _process_coverage_line(self, line: str, suite_info: TestSuiteProgress) -> None:
        if match := self._coverage_pattern.search(line):
            assert match is not None  # Type checker: match cannot be None here
            suite_info.coverage_percentage = float(match.group(1))

    def _process_current_test_line(
        self,
        line: str,
        suite_info: TestSuiteProgress,
    ) -> None:
        if ":: " in line and any(
            status in line for status in ("PASSED", "FAILED", "SKIPPED", "ERROR")
        ):
            suite_info.current_test = line.split()[0] if line.split() else None

    def parse_test_failure_details(self, output_lines: list[str]) -> dict[str, str]:
        failures: dict[str, str] = {}
        current_test: str | None = None
        current_traceback: list[str] = []
        in_failure_section = False

        for line in output_lines:
            if self._is_failure_section_start(line):
                in_failure_section = True
                continue

            if not in_failure_section:
                continue

            if self._is_test_header(line):
                self._save_current_failure(failures, current_test, current_traceback)
                current_test = line.strip("_")
                current_traceback = []
                continue

            if self._should_add_to_traceback(current_test, line):
                current_traceback.append(line)

        self._save_current_failure(failures, current_test, current_traceback)
        return failures

    def _is_failure_section_start(self, line: str) -> bool:
        return "FAILURES" in line or "ERRORS" in line

    def _is_test_header(self, line: str) -> bool:
        return line.startswith("_") and ":: " in line

    def _should_add_to_traceback(self, current_test: str | None, line: str) -> bool:
        return current_test is not None and bool(line.strip())

    def _save_current_failure(
        self,
        failures: dict[str, str],
        current_test: str | None,
        current_traceback: list[str],
    ) -> None:
        if current_test and current_traceback:
            failures[current_test] = "\n".join(current_traceback)


class TestProgressStreamer:
    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.parser = PytestOutputParser()
        self.progress_callback: t.Callable[[TestSuiteProgress], None] | None = None
        self.test_callback: t.Callable[[TestProgress], None] | None = None

    def set_progress_callback(
        self,
        callback: t.Callable[[TestSuiteProgress], None],
    ) -> None:
        self.progress_callback = callback

    def set_test_callback(self, callback: t.Callable[[TestProgress], None]) -> None:
        self.test_callback = callback

    async def run_tests_with_streaming(
        self,
        options: OptionsProtocol,
        execution_mode: str = "full_suite",
    ) -> dict[str, t.Any]:
        start_time = time.time()
        suite_progress = TestSuiteProgress(start_time=start_time)

        self.console.print(
            "\n[bold bright_green]🧪 RUNNING TESTS WITH STREAMING PROGRESS[/ bold bright_green]",
        )

        cmd = self.build_pytest_command(options, execution_mode)

        try:
            return await self._execute_tests_and_process_results(cmd, suite_progress)
        except Exception as e:
            return self._handle_test_execution_error(e, suite_progress)

    async def _execute_tests_and_process_results(
        self,
        cmd: list[str],
        suite_progress: TestSuiteProgress,
    ) -> dict[str, t.Any]:
        result = await self._run_pytest_with_streaming(cmd, suite_progress)

        parsed_results = self.parser.parse_pytest_output(result.stdout.split("\n"))
        failure_details = self.parser.parse_test_failure_details(
            result.stdout.split("\n"),
        )

        self._finalize_suite_progress(suite_progress)
        self._attach_failure_details(parsed_results["tests"], failure_details)
        self._print_test_summary(suite_progress, parsed_results["tests"])

        return self._build_success_result(result, suite_progress, parsed_results)

    def _finalize_suite_progress(self, suite_progress: TestSuiteProgress) -> None:
        suite_progress.end_time = time.time()
        suite_progress.duration = suite_progress.end_time - (
            suite_progress.start_time or 0
        )

    def _attach_failure_details(
        self,
        tests: list[TestProgress],
        failure_details: dict[str, str],
    ) -> None:
        for test in tests:
            if test.test_id in failure_details:
                test.failure_traceback = failure_details[test.test_id]

    def _build_success_result(
        self,
        result: subprocess.CompletedProcess[str],
        suite_progress: TestSuiteProgress,
        parsed_results: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        return {
            "success": result.returncode == 0,
            "suite_progress": suite_progress,
            "individual_tests": parsed_results["tests"],
            "failed_tests": [
                t for t in parsed_results["tests"] if t.status == "failed"
            ],
            "total_duration": suite_progress.duration,
            "coverage_percentage": suite_progress.coverage_percentage,
        }

    def _handle_test_execution_error(
        self,
        error: Exception,
        suite_progress: TestSuiteProgress,
    ) -> dict[str, t.Any]:
        self.console.print(f"[red]❌ Test execution failed: {error}[/ red]")
        suite_progress.end_time = time.time()
        suite_progress.duration = suite_progress.end_time - (
            suite_progress.start_time or 0
        )

        return {
            "success": False,
            "suite_progress": suite_progress,
            "individual_tests": [],
            "failed_tests": [],
            "error": str(error),
        }

    def build_pytest_command(
        self,
        options: OptionsProtocol,
        execution_mode: str,
    ) -> list[str]:
        cmd = ["uv", "run", "pytest"]

        cmd.extend(["- v", "--tb=short"])

        if hasattr(options, "coverage") and options.coverage:
            cmd.extend(["--cov=crackerjack", "- - cov - report=term-missing"])

        if execution_mode == "individual_with_progress":
            cmd.extend(["- - no-header"])
        elif execution_mode == "selective":
            pass
        else:
            cmd.extend(["- q"])

        if hasattr(options, "test_timeout"):
            cmd.extend([f"--timeout ={options.test_timeout}"])

        if hasattr(options, "test_workers") and options.test_workers > 1:
            cmd.extend(["- n", str(options.test_workers)])

        return cmd

    async def _run_pytest_with_streaming(
        self,
        cmd: list[str],
        suite_progress: TestSuiteProgress,
    ) -> subprocess.CompletedProcess[str]:
        self.console.print(f"[dim]Running: {' '.join(cmd)}[/ dim]")

        process = await self._create_subprocess(cmd)
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            await self._process_streams(
                process,
                stdout_lines,
                stderr_lines,
                suite_progress,
            )
        except Exception:
            await self._cleanup_process_and_tasks(process, [])
            raise

        return self._build_completed_process(cmd, process, stdout_lines, stderr_lines)

    async def _create_subprocess(self, cmd: list[str]) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.pkg_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def _process_streams(
        self,
        process: asyncio.subprocess.Process,
        stdout_lines: list[str],
        stderr_lines: list[str],
        suite_progress: TestSuiteProgress,
    ) -> None:
        tasks = [
            asyncio.create_task(
                self._read_stream(process.stdout, stdout_lines, suite_progress),
            ),
            asyncio.create_task(
                self._read_stream(process.stderr, stderr_lines, suite_progress),
            ),
        ]

        try:
            await process.wait()
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            await self._cleanup_process_and_tasks(process, tasks)
            raise

    async def _read_stream(
        self,
        stream: asyncio.StreamReader | None,
        output_list: list[str],
        suite_progress: TestSuiteProgress,
    ) -> None:
        if not stream:
            return

        while True:
            try:
                line = await stream.readline()
                if not line:
                    break

                line_str = self._process_stream_line(line)
                output_list.append(line_str)

                self._handle_line_output(line_str, suite_progress)

            except Exception:
                break

    def _process_stream_line(self, line: bytes | str) -> str:
        return (line.decode() if isinstance(line, bytes) else line).rstrip()

    def _handle_line_output(
        self,
        line_str: str,
        suite_progress: TestSuiteProgress,
    ) -> None:
        self._parse_line_for_progress(line_str, suite_progress)

        if line_str.strip():
            self._print_test_line(line_str)

        if self.progress_callback:
            self.progress_callback(suite_progress)

    async def _cleanup_process_and_tasks(
        self,
        process: asyncio.subprocess.Process,
        tasks: list[asyncio.Task[t.Any]],
    ) -> None:
        process.kill()
        for task in tasks:
            task.cancel()

    def _build_completed_process(
        self,
        cmd: list[str],
        process: asyncio.subprocess.Process,
        stdout_lines: list[str],
        stderr_lines: list[str],
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode or 0,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
        )

    def _parse_line_for_progress(
        self,
        line: str,
        suite_progress: TestSuiteProgress,
    ) -> None:
        if ":: " in line and any(
            status in line for status in ("PASSED", "FAILED", "SKIPPED", "ERROR")
        ):
            parts = line.split()
            if parts:
                suite_progress.current_test = parts[0]

        if match := self.parser._test_collection_pattern.search(line):
            assert match is not None  # Type checker: match cannot be None here
            suite_progress.total_tests = int(match.group(1))

        if "PASSED" in line:
            suite_progress.passed_tests += 1
            suite_progress.completed_tests += 1
        elif "FAILED" in line:
            suite_progress.failed_tests += 1
            suite_progress.completed_tests += 1
        elif "SKIPPED" in line:
            suite_progress.skipped_tests += 1
            suite_progress.completed_tests += 1
        elif "ERROR" in line:
            suite_progress.error_tests += 1
            suite_progress.completed_tests += 1

    def _print_test_line(self, line: str) -> None:
        if "PASSED" in line:
            self.console.print(f"[green]{line}[/ green]")
        elif "FAILED" in line:
            self.console.print(f"[red]{line}[/ red]")
        elif "SKIPPED" in line:
            self.console.print(f"[yellow]{line}[/ yellow]")
        elif "ERROR" in line:
            self.console.print(f"[bright_red]{line}[/ bright_red]")
        elif line.startswith("="):
            self.console.print(f"[bold cyan]{line}[/ bold cyan]")
        else:
            self.console.print(f"[dim]{line}[/ dim]")

    def _print_test_summary(
        self,
        suite_progress: TestSuiteProgress,
        tests: list[TestProgress],
    ) -> None:
        self._print_summary_header()
        self._print_test_counts(suite_progress)
        self._print_timing_stats(suite_progress)
        self._print_coverage_stats(suite_progress)
        self._print_failed_test_details(tests)
        self._print_summary_footer()

    def _print_summary_header(self) -> None:
        self.console.print("\n" + "=" * 80)
        self.console.print(
            "[bold bright_green]🧪 TEST EXECUTION SUMMARY[/ bold bright_green]",
        )
        self.console.print("=" * 80)

    def _print_test_counts(self, suite_progress: TestSuiteProgress) -> None:
        self.console.print(f"[bold]Total Tests: [/ bold] {suite_progress.total_tests}")
        self.console.print(f"[green]✅ Passed: [/ green] {suite_progress.passed_tests}")

        if suite_progress.failed_tests > 0:
            self.console.print(f"[red]❌ Failed: [/ red] {suite_progress.failed_tests}")

        if suite_progress.skipped_tests > 0:
            self.console.print(
                f"[yellow]⏭️ Skipped: [/ yellow] {suite_progress.skipped_tests}",
            )

        if suite_progress.error_tests > 0:
            self.console.print(
                f"[bright_red]💥 Errors: [/ bright_red] {suite_progress.error_tests}",
            )

    def _print_timing_stats(self, suite_progress: TestSuiteProgress) -> None:
        if not suite_progress.duration:
            return

        self.console.print(
            f"[bold]⏱️ Duration: [/ bold] {suite_progress.duration: .1f}s"
        )

        if suite_progress.total_tests > 0:
            avg_time = suite_progress.duration / suite_progress.total_tests
            self.console.print(f"[dim]Average per test: {avg_time: .2f}s[/ dim]")

        self.console.print(
            f"[bold]📊 Success Rate: [/ bold] {suite_progress.success_rate: .1f}%",
        )

    def _print_coverage_stats(self, suite_progress: TestSuiteProgress) -> None:
        if suite_progress.coverage_percentage is not None:
            self.console.print(
                f"[bold]📈 Coverage: [/ bold] {suite_progress.coverage_percentage: .1f}%",
            )

    def _print_failed_test_details(self, tests: list[TestProgress]) -> None:
        failed_tests = [t for t in tests if t.status == "failed"]
        if not failed_tests:
            return

        self.console.print(
            f"\n[bold red]Failed Tests ({len(failed_tests)}): [/ bold red]",
        )
        for test in failed_tests[:5]:
            self.console.print(f" ❌ {test.test_id}")
            if test.error_message:
                error_preview = self._format_error_preview(test.error_message)
                self.console.print(f" [dim]{error_preview}[/ dim]")

        if len(failed_tests) > 5:
            self.console.print(f" [dim]... and {len(failed_tests) - 5} more[/ dim]")

    def _format_error_preview(self, error_message: str) -> str:
        return (
            error_message[:100] + "..." if len(error_message) > 100 else error_message
        )

    def _print_summary_footer(self) -> None:
        self.console.print("=" * 80)
