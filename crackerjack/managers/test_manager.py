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
            from crackerjack.services.coverage_ratchet import CoverageRatchetService

            coverage_ratchet_obj = CoverageRatchetService(pkg_path, console)
            self.coverage_ratchet: CoverageRatchetProtocol | None = t.cast(
                CoverageRatchetProtocol, coverage_ratchet_obj
            )
        else:
            self.coverage_ratchet = coverage_ratchet

        self._last_test_failures: list[str] = []
        self._progress_callback: t.Callable[[dict[str, t.Any]], None] | None = None
        self.coverage_ratchet_enabled = True
        self.use_lsp_diagnostics = True

        # Initialize coverage badge service
        from crackerjack.services.coverage_badge_service import CoverageBadgeService

        self._coverage_badge_service = CoverageBadgeService(console, pkg_path)

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

    def _get_coverage_from_file(self) -> float | None:
        """Extract coverage from coverage.json file."""
        import json

        coverage_json_path = self.pkg_path / "coverage.json"
        if not coverage_json_path.exists():
            return None

        try:
            with coverage_json_path.open() as f:
                coverage_data = json.load(f)

            # Extract coverage percentage from totals
            totals = coverage_data.get("totals", {})
            percent_covered = totals.get("percent_covered", None)

            if percent_covered is not None:
                return float(percent_covered)

            # Alternative extraction methods for different coverage formats
            if "percent_covered" in coverage_data:
                return float(coverage_data["percent_covered"])

            # Check for coverage in files section
            files = coverage_data.get("files", {})
            if files:
                total_lines = 0
                covered_lines = 0
                for file_data in files.values():
                    summary = file_data.get("summary", {})
                    total_lines += summary.get("num_statements", 0)
                    covered_lines += summary.get("covered_lines", 0)

                if total_lines > 0:
                    return (covered_lines / total_lines) * 100

            return None

        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            return None

    def _handle_no_ratchet_status(
        self, direct_coverage: float | None
    ) -> dict[str, t.Any]:
        """Handle case when ratchet is not initialized."""
        if direct_coverage is not None:
            return {
                "status": "coverage_available",
                "coverage_percent": direct_coverage,
                "message": "Coverage data available from coverage.json",
                "source": "coverage.json",
            }

        return {
            "status": "not_initialized",
            "coverage_percent": 0.0,
            "message": "Coverage ratchet not initialized",
        }

    def _get_final_coverage(
        self, ratchet_coverage: float, direct_coverage: float | None
    ) -> float:
        """Determine final coverage value."""
        return direct_coverage if direct_coverage is not None else ratchet_coverage

    def get_coverage(self) -> dict[str, t.Any]:
        try:
            status = self.coverage_ratchet.get_status_report()

            # Check if we have actual coverage data from coverage.json even if ratchet is not initialized
            direct_coverage = self._get_coverage_from_file()

            # If ratchet is not initialized but we have direct coverage data, use it
            if (
                not status or status.get("status") == "not_initialized"
            ) and direct_coverage is not None:
                return self._handle_no_ratchet_status(direct_coverage)

            # If ratchet is not initialized and no direct coverage, return not initialized
            if not status or status.get("status") == "not_initialized":
                return self._handle_no_ratchet_status(None)

            # Use ratchet data, but prefer direct coverage if available and different
            ratchet_coverage = status.get("current_coverage", 0.0)
            final_coverage = self._get_final_coverage(ratchet_coverage, direct_coverage)

            return {
                "status": "active",
                "coverage_percent": final_coverage,
                "target_coverage": status.get("target_coverage", 100.0),
                "next_milestone": status.get("next_milestone"),
                "progress_percent": status.get("progress_percent", 0.0),
                "last_updated": status.get("last_updated"),
                "milestones_achieved": status.get("milestones_achieved", []),
                "source": "coverage.json" if direct_coverage is not None else "ratchet",
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
                    if list[t.Any](test_path.glob(f"**/{test_file_pattern}")):
                        return True

        for test_file_pattern in test_files:
            if list[t.Any](self.pkg_path.glob(test_file_pattern)):
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

        # Update coverage badge if coverage information is available
        self._update_coverage_badge(ratchet_result)

        return self._handle_ratchet_result(ratchet_result)

    def _attempt_coverage_extraction(self) -> float | None:
        """Attempt to extract coverage from various sources."""
        # Primary: Try to extract from coverage.json
        current_coverage = self._get_coverage_from_file()
        if current_coverage is not None:
            return current_coverage

        return None

    def _handle_coverage_extraction_result(
        self, current_coverage: float | None
    ) -> float | None:
        """Handle the result of coverage extraction attempts."""
        if current_coverage is not None:
            self.console.print(
                f"[dim]📊 Coverage extracted from coverage.json: {current_coverage:.2f}%[/dim]"
            )
        return current_coverage

    def _get_fallback_coverage(
        self, ratchet_result: dict[str, t.Any], current_coverage: float | None
    ) -> float | None:
        """Get coverage from fallback sources."""
        # Secondary: Try ratchet result if coverage.json failed
        if current_coverage is None:
            current_coverage = self._get_coverage_from_ratchet(ratchet_result)
            if current_coverage is not None:
                self.console.print(
                    f"[dim]📊 Coverage from ratchet result: {current_coverage:.2f}%[/dim]"
                )

        # Tertiary: Try coverage service, but only accept non-zero values
        if current_coverage is None:
            current_coverage = self._get_coverage_from_service()
            if current_coverage is not None:
                self.console.print(
                    f"[dim]📊 Coverage from service fallback: {current_coverage:.2f}%[/dim]"
                )
            else:
                coverage_json_path = self.pkg_path / "coverage.json"
                if coverage_json_path.exists():
                    self.console.print(
                        "[yellow]⚠️[/yellow] Skipping 0.0% fallback when coverage.json exists"
                    )

        return current_coverage

    def _update_coverage_badge(self, ratchet_result: dict[str, t.Any]) -> None:
        """Update coverage badge in README.md if coverage changed."""
        try:
            # Get current coverage directly from coverage.json to ensure freshest data
            current_coverage = self._attempt_coverage_extraction()
            current_coverage = self._handle_coverage_extraction_result(current_coverage)

            # Get fallback coverage if needed
            current_coverage = self._get_fallback_coverage(
                ratchet_result, current_coverage
            )

            # Only update badge if we have valid coverage data
            if current_coverage is not None and current_coverage >= 0:
                if self._coverage_badge_service.should_update_badge(current_coverage):
                    self._coverage_badge_service.update_readme_coverage_badge(
                        current_coverage
                    )
                    self.console.print(
                        f"[green]✅[/green] Badge updated to {current_coverage:.2f}%"
                    )
                else:
                    self.console.print(
                        f"[dim]📊 Badge unchanged (current: {current_coverage:.2f}%)[/dim]"
                    )
            else:
                self.console.print(
                    "[yellow]⚠️[/yellow] No valid coverage data found for badge update"
                )

        except Exception as e:
            # Don't fail the test process if badge update fails
            self.console.print(f"[yellow]⚠️[/yellow] Badge update failed: {e}")

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
                    f"{current: .2f}% < {previous: .2f}%"
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

    async def run_pre_test_lsp_diagnostics(self) -> bool:
        """Run LSP diagnostics before tests to catch type errors early."""
        if not self.use_lsp_diagnostics:
            return True

        try:
            from crackerjack.services.lsp_client import LSPClient

            lsp_client = LSPClient(self.console)

            # Check if LSP server is available
            if not lsp_client.is_server_running():
                return True  # No LSP server, skip diagnostics

            # Run type diagnostics on the project
            diagnostics, summary = lsp_client.check_project_with_feedback(
                self.pkg_path,
                show_progress=False,  # Keep quiet for test integration
            )

            # Check if there are type errors
            has_errors = any(diags for diags in diagnostics.values())

            if has_errors:
                self.console.print(
                    "[yellow]⚠️ LSP detected type errors before running tests[/yellow]"
                )
                # Format and show a summary
                error_count = sum(len(diags) for diags in diagnostics.values())
                self.console.print(f"[yellow]Found {error_count} type issues[/yellow]")

            return not has_errors  # Return False if there are type errors

        except Exception as e:
            # If LSP diagnostics fail, don't block tests
            self.console.print(f"[dim]LSP diagnostics failed: {e}[/dim]")
            return True

    def configure_lsp_diagnostics(self, enable: bool) -> None:
        """Enable or disable LSP diagnostics integration."""
        self.use_lsp_diagnostics = enable

        if enable:
            self.console.print(
                "[cyan]🔍 LSP diagnostics enabled for faster test feedback[/cyan]"
            )


TestManagementImpl = TestManager
