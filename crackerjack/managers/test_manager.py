import subprocess
import time
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.models.protocols import CoverageRatchetProtocol, OptionsProtocol

from .test_command_builder import TestCommandBuilder
from .test_executor import TestExecutor


class TestManager:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        coverage_ratchet: CoverageRatchetProtocol | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path

        self.executor = TestExecutor(console, pkg_path)
        self.command_builder = TestCommandBuilder(pkg_path)

        if coverage_ratchet is None:
            # Import here to avoid circular imports
            from crackerjack.services.coverage_ratchet import CoverageRatchetService

            coverage_ratchet = CoverageRatchetService(pkg_path, console)

        self.coverage_ratchet = coverage_ratchet

        self._last_test_failures: list[str] = []
        self._progress_callback: t.Callable[[dict[str, t.Any]], None] | None = None
        self.coverage_ratchet_enabled = True

    def set_progress_callback(
        self,
        callback: t.Callable[[dict[str, t.Any]], None] | None,
    ) -> None:
        self._progress_callback = callback

    def set_coverage_ratchet_enabled(self, enabled: bool) -> None:
        self.coverage_ratchet_enabled = enabled
        if enabled:
            self.console.print(
                "[cyan]📊[/ cyan] Coverage ratchet enabled-targeting 100 % coverage"
            )
        else:
            self.console.print("[yellow]⚠️[/ yellow] Coverage ratchet disabled")

    def run_tests(self, options: OptionsProtocol) -> bool:
        start_time = time.time()

        try:
            result = self._execute_test_workflow(options)
            duration = time.time() - start_time

            if result:
                return self._handle_test_success(result.stdout, duration)
            else:
                return self._handle_test_failure(
                    result.stderr if result else "", duration
                )

        except Exception as e:
            return self._handle_test_error(start_time, e)

    def run_specific_tests(self, test_pattern: str) -> bool:
        self.console.print(f"[cyan]🧪[/ cyan] Running tests matching: {test_pattern}")

        cmd = self.command_builder.build_specific_test_command(test_pattern)
        result = self.executor.execute_with_progress(cmd)

        success = result.returncode == 0
        if success:
            self.console.print("[green]✅[/ green] Specific tests passed")
        else:
            self.console.print("[red]❌[/ red] Some specific tests failed")

        return success

    def validate_test_environment(self) -> bool:
        if not self.has_tests():
            self.console.print("[yellow]⚠️[/ yellow] No tests found")
            return False

        cmd = self.command_builder.build_validation_command()
        result = subprocess.run(cmd, cwd=self.pkg_path, capture_output=True, text=True)

        if result.returncode != 0:
            self.console.print("[red]❌[/ red] Test environment validation failed")
            self.console.print(result.stderr)
            return False

        self.console.print("[green]✅[/ green] Test environment validated")
        return True

    def get_coverage_ratchet_status(self) -> dict[str, t.Any]:
        return self.coverage_ratchet.get_status_report()

    def get_test_stats(self) -> dict[str, t.Any]:
        return {
            "has_tests": self.has_tests(),
            "coverage_ratchet_enabled": self.coverage_ratchet_enabled,
            "last_failures_count": len(self._last_test_failures),
        }

    def get_test_failures(self) -> list[str]:
        return self._last_test_failures.copy()

    def get_test_command(self, options: OptionsProtocol) -> list[str]:
        return self.command_builder.build_command(options)

    def get_coverage_report(self) -> str | None:
        try:
            return self.coverage_ratchet.get_coverage_report()
        except Exception:
            return None

    def get_coverage(self) -> dict[str, t.Any]:
        try:
            status = self.coverage_ratchet.get_status_report()

            if status.get("status") == "not_initialized":
                return {
                    "status": "not_initialized",
                    "coverage_percent": 0.0,
                    "message": "Coverage ratchet not initialized",
                }

            return {
                "status": "active",
                "coverage_percent": status.get("current_coverage", 0.0),
                "target_coverage": status.get("target_coverage", 100.0),
                "next_milestone": status.get("next_milestone"),
                "progress_percent": status.get("progress_percent", 0.0),
                "last_updated": status.get("last_updated"),
                "milestones_achieved": status.get("milestones_achieved", []),
            }
        except Exception as e:
            return {
                "status": "error",
                "coverage_percent": 0.0,
                "error": str(e),
                "message": "Failed to get coverage information",
            }

    def has_tests(self) -> bool:
        test_directories = ["tests", "test"]
        test_files = ["test_*.py", "*_test.py"]

        for test_dir in test_directories:
            test_path = self.pkg_path / test_dir
            if test_path.exists() and test_path.is_dir():
                for test_file_pattern in test_files:
                    if list(test_path.glob(f"**/{test_file_pattern}")):
                        return True

        for test_file_pattern in test_files:
            if list(self.pkg_path.glob(test_file_pattern)):
                return True

        return False

    def _execute_test_workflow(
        self, options: OptionsProtocol
    ) -> subprocess.CompletedProcess[str]:
        self._print_test_start_message(options)

        cmd = self.command_builder.build_command(options)

        if self._progress_callback:
            return self.executor.execute_with_ai_progress(
                cmd, self._progress_callback, self._get_timeout(options)
            )
        return self.executor.execute_with_progress(cmd, self._get_timeout(options))

    def _print_test_start_message(self, options: OptionsProtocol) -> None:
        workers = self.command_builder.get_optimal_workers(options)
        timeout = self.command_builder.get_test_timeout(options)

        self.console.print(
            f"[cyan]🧪[/ cyan] Running tests (workers: {workers}, timeout: {timeout}s)"
        )

    def _handle_test_success(self, output: str, duration: float) -> bool:
        self.console.print(f"[green]✅[/ green] Tests passed in {duration: .1f}s")

        if self.coverage_ratchet_enabled:
            return self._process_coverage_ratchet()

        return True

    def _handle_test_failure(self, output: str, duration: float) -> bool:
        self.console.print(f"[red]❌[/ red] Tests failed in {duration: .1f}s")

        self._last_test_failures = self._extract_failure_lines(output)
        return False

    def _handle_test_error(self, start_time: float, error: Exception) -> bool:
        duration = time.time() - start_time
        self.console.print(
            f"[red]💥[/ red] Test execution error after {duration: .1f}s: {error}"
        )
        return False

    def _process_coverage_ratchet(self) -> bool:
        if not self.coverage_ratchet_enabled:
            return True

        ratchet_result = self.coverage_ratchet.check_and_update_coverage()
        return self._handle_ratchet_result(ratchet_result)

    def _handle_ratchet_result(self, ratchet_result: dict[str, t.Any]) -> bool:
        if ratchet_result.get("success", False):
            if ratchet_result.get("improved", False):
                self._handle_coverage_improvement(ratchet_result)
            return True
        else:
            if "message" in ratchet_result:
                self.console.print(f"[red]📉[/ red] {ratchet_result['message']}")
            else:
                current = ratchet_result.get("current_coverage", 0)
                previous = ratchet_result.get("previous_coverage", 0)
                self.console.print(
                    f"[red]📉[/ red] Coverage regression: "
                    f"{current:.2f}% < {previous:.2f}%"
                )
            return False

    def _handle_coverage_improvement(self, ratchet_result: dict[str, t.Any]) -> None:
        improvement = ratchet_result.get("improvement", 0)
        current = ratchet_result.get("current_coverage", 0)

        self.console.print(
            f"[green]📈[/ green] Coverage improved by {improvement: .2f}% "
            f"to {current: .2f}%"
        )

    def _extract_failure_lines(self, output: str) -> list[str]:
        failures = []
        lines = output.split("\n")

        for line in lines:
            if any(
                keyword in line for keyword in ("FAILED", "ERROR", "AssertionError")
            ):
                failures.append(line.strip())

        return failures[:10]

    def _get_timeout(self, options: OptionsProtocol) -> int:
        return self.command_builder.get_test_timeout(options)


TestManagementImpl = TestManager
