import re
import subprocess
import time
import typing as t
from pathlib import Path

from acb.config import root_path
from acb.console import Console
from acb.depends import Inject, depends
from rich import box
from rich.panel import Panel
from rich.table import Table

from crackerjack.config import get_console_width
from crackerjack.models.protocols import (
    CoverageBadgeServiceProtocol,
    CoverageRatchetProtocol,
    OptionsProtocol,
)
from crackerjack.services.lsp_client import LSPClient

from .test_command_builder import TestCommandBuilder
from .test_executor import TestExecutor


class TestManager:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        coverage_ratchet: Inject[CoverageRatchetProtocol],
        coverage_badge: Inject[CoverageBadgeServiceProtocol],
        command_builder: Inject[TestCommandBuilder],
        lsp_client: Inject[LSPClient] | None = None,
    ) -> None:
        self.console = console
        # Ensure a concrete pathlib.Path instance to avoid async Path behaviors
        # and to guarantee sync filesystem operations in this manager.
        try:
            self.pkg_path = Path(str(root_path))
        except Exception:
            # Fallback in the unlikely event root_path lacks __str__
            self.pkg_path = Path(root_path)

        # Ensure downstream components receive a concrete pathlib.Path
        self.executor = TestExecutor(console, self.pkg_path)
        self.command_builder = command_builder

        # Services injected via ACB DI
        self.coverage_ratchet = coverage_ratchet
        self._coverage_badge_service = coverage_badge
        self._lsp_client = lsp_client

        self._last_test_failures: list[str] = []
        self._progress_callback: t.Callable[[dict[str, t.Any]], None] | None = None
        self.coverage_ratchet_enabled = True
        self.use_lsp_diagnostics = True

    def set_progress_callback(
        self,
        callback: t.Callable[[dict[str, t.Any]], None] | None,
    ) -> None:
        self._progress_callback = callback

    def set_coverage_ratchet_enabled(self, enabled: bool) -> None:
        self.coverage_ratchet_enabled = enabled
        if enabled:
            self.console.print(
                "[cyan]📊[/cyan] Coverage ratchet enabled-targeting 100 % coverage"
            )
        else:
            self.console.print("[yellow]⚠️[/yellow] Coverage ratchet disabled")

    def run_tests(self, options: OptionsProtocol) -> bool:
        # Early return if tests are disabled
        if hasattr(options, "test") and not options.test:
            return True

        start_time = time.time()

        try:
            result = self._execute_test_workflow(options)
            duration = time.time() - start_time

            # Get worker count for statistics panel (don't print info messages)
            workers = self.command_builder.get_optimal_workers(
                options, print_info=False
            )

            if result.returncode == 0:
                return self._handle_test_success(
                    result.stdout, duration, options, workers
                )
            else:
                return self._handle_test_failure(
                    result.stderr if result else "",
                    result.stdout if result else "",
                    duration,
                    options,
                    workers,
                )

        except Exception as e:
            return self._handle_test_error(start_time, e)

    def run_specific_tests(self, test_pattern: str) -> bool:
        self.console.print(f"[cyan]🧪[/cyan] Running tests matching: {test_pattern}")

        cmd = self.command_builder.build_specific_test_command(test_pattern)
        result = self.executor.execute_with_progress(cmd)

        success = result.returncode == 0
        if success:
            self.console.print("[green]✅[/green] Specific tests passed")
        else:
            self.console.print("[red]❌[/red] Some specific tests failed")

        return success

    def validate_test_environment(self) -> bool:
        if not self.has_tests():
            self.console.print("[yellow]⚠️[/yellow] No tests found")
            return False

        from rich.live import Live
        from rich.spinner import Spinner

        cmd = self.command_builder.build_validation_command()

        spinner = Spinner("dots", text="[cyan]Validating test environment...[/cyan]")
        with Live(spinner, console=self.console, transient=True):
            result = subprocess.run(
                cmd, cwd=self.pkg_path, capture_output=True, text=True
            )

        if result.returncode != 0:
            self.console.print("[red]❌[/red] Test environment validation failed")
            self.console.print(result.stderr)
            return False

        self.console.print("[green]✅[/green] Test environment validated")
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
        workers = self.command_builder.get_optimal_workers(options, print_info=False)
        timeout = self.command_builder.get_test_timeout(options)

        self.console.print(
            f"[cyan]🧪[/cyan] Running tests (workers: {workers}, timeout: {timeout}s)"
        )

    def _handle_test_success(
        self,
        output: str,
        duration: float,
        options: OptionsProtocol,
        workers: int | str,
    ) -> bool:
        self.console.print(f"[green]✅[/green] Tests passed in {duration: .1f}s")

        # Parse and display test statistics panel
        stats = self._parse_test_statistics(output)
        if stats["total"] > 0:  # Only show panel if tests were actually run
            self._render_test_results_panel(stats, workers, success=True)

        if self.coverage_ratchet_enabled:
            return self._process_coverage_ratchet()

        return True

    def _handle_test_failure(
        self,
        stderr: str,
        stdout: str,
        duration: float,
        options: OptionsProtocol,
        workers: int | str,
    ) -> bool:
        self.console.print(f"[red]❌[/red] Tests failed in {duration: .1f}s")

        # Parse and display test statistics panel (use stdout for stats)
        combined_output = stdout + "\n" + stderr
        stats = self._parse_test_statistics(combined_output)
        if stats["total"] > 0:  # Only show panel if tests were actually run
            self._render_test_results_panel(stats, workers, success=False)

        # Extract and display failures if --verbose or --ai-debug is enabled
        if options.verbose or getattr(options, "ai_debug", False):
            self._last_test_failures = self._extract_failure_lines(combined_output)
            if combined_output.strip():
                self.console.print("\n[red]Test Output:[/red]")
                self.console.print(combined_output)
        else:
            self._last_test_failures = []

        return False

    def _handle_test_error(self, start_time: float, error: Exception) -> bool:
        duration = time.time() - start_time
        self.console.print(
            f"[red]💥[/red] Test execution error after {duration: .1f}s: {error}"
        )
        return False

    def _parse_test_statistics(self, output: str) -> dict[str, t.Any]:
        """Parse test statistics from pytest output.

        Extracts metrics like passed, failed, skipped, errors, and duration
        from pytest's summary line.

        Args:
            output: Raw pytest output text

        Returns:
            Dictionary containing test statistics
        """
        stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "xfailed": 0,
            "xpassed": 0,
            "duration": 0.0,
            "coverage": None,
        }

        try:
            # Extract summary and duration
            summary_match = self._extract_pytest_summary(output)
            if summary_match:
                summary_text, duration = self._parse_summary_match(
                    summary_match, output
                )
                stats["duration"] = duration

                # Extract metrics from summary
                self._extract_test_metrics(summary_text, stats)

                # Calculate total and fallback if needed
                self._calculate_total_tests(stats, output)

            # Extract coverage if present
            stats["coverage"] = self._extract_coverage_from_output(output)

        except (ValueError, AttributeError) as e:
            self.console.print(f"[dim]⚠️ Failed to parse test statistics: {e}[/dim]")

        return stats

    def _extract_pytest_summary(self, output: str) -> re.Match[str] | None:
        """Extract pytest summary line match from output."""
        summary_patterns = [
            r"=+\s+(.+?)\s+in\s+([\d.]+)s?\s*=+",  # "======= 5 passed in 1.23s ======="
            r"(\d+\s+\w+)+\s+in\s+([\d.]+)s?",  # "5 passed, 2 failed in 1.23s"
            r"(\d+.*)in\s+([\d.]+)s?",  # More flexible format
        ]

        for pattern in summary_patterns:
            match = re.search(pattern, output)
            if match:
                return match
        return None

    def _parse_summary_match(
        self, match: re.Match[str], output: str
    ) -> tuple[str, float]:
        """Parse summary text and duration from regex match."""
        if len(match.groups()) >= 2:
            summary_text = match.group(1)
            duration = float(match.group(2))
        else:
            # Pattern only captured duration
            duration = (
                float(match.group(1))
                if match.group(1).replace(".", "").isdigit()
                else 0.0
            )
            summary_text = output

        return summary_text, duration

    def _extract_test_metrics(self, summary_text: str, stats: dict[str, t.Any]) -> None:
        """Extract individual test metrics from summary text."""
        for metric in ("passed", "failed", "skipped", "error", "xfailed", "xpassed"):
            metric_pattern = rf"(\d+)\s+{metric}"
            metric_match = re.search(metric_pattern, summary_text, re.IGNORECASE)
            if metric_match:
                count = int(metric_match.group(1))
                key = "errors" if metric == "error" else metric
                stats[key] = count

    def _calculate_total_tests(self, stats: dict[str, t.Any], output: str) -> None:
        """Calculate total tests and apply fallback counting if needed."""
        stats["total"] = sum(
            [
                stats["passed"],
                stats["failed"],
                stats["skipped"],
                stats["errors"],
                stats["xfailed"],
                stats["xpassed"],
            ]
        )

        # Fallback: manually count from output if total is still 0
        if stats["total"] == 0:
            self._fallback_count_tests(output, stats)

    def _fallback_count_tests(self, output: str, stats: dict[str, t.Any]) -> None:
        """Manually count test results from output when parsing fails."""
        stats["passed"] = len(
            re.findall(r"(?:\.|✓)\s*(?:PASSED|pass)", output, re.IGNORECASE)
        )
        stats["failed"] = len(
            re.findall(r"(?:F|X|❌)\s*(?:FAILED|fail)", output, re.IGNORECASE)
        ) or len(re.findall(r"FAILED", output))
        stats["skipped"] = len(
            re.findall(r"(?:s|S|.SKIPPED|skip)", output, re.IGNORECASE)
        )
        stats["errors"] = len(re.findall(r"ERROR|E\s+", output, re.IGNORECASE))
        stats["total"] = (
            stats["passed"] + stats["failed"] + stats["skipped"] + stats["errors"]
        )

    def _extract_coverage_from_output(self, output: str) -> float | None:
        """Extract coverage percentage from pytest output."""
        coverage_pattern = r"TOTAL\s+\d+\s+\d+\s+(\d+)%"
        coverage_match = re.search(coverage_pattern, output)
        if coverage_match:
            return float(coverage_match.group(1))
        return None

    def _render_test_results_panel(
        self,
        stats: dict[str, t.Any],
        workers: int | str,
        success: bool,
    ) -> None:
        """Render test results panel with statistics similar to hook results.

        Args:
            stats: Dictionary of test statistics from _parse_test_statistics
            workers: Number of workers used (or "auto")
            success: Whether tests passed overall
        """
        table = Table(box=box.SIMPLE, header_style="bold bright_white")
        table.add_column("Metric", style="cyan", overflow="fold")
        table.add_column("Count", justify="right", style="bright_white")
        table.add_column("Percentage", justify="right", style="magenta")

        total = stats["total"]

        # Add rows for each metric
        metrics = [
            ("✅ Passed", stats["passed"], "green"),
            ("❌ Failed", stats["failed"], "red"),
            ("⏭ Skipped", stats["skipped"], "yellow"),
            ("💥 Errors", stats["errors"], "red"),
        ]

        # Only show xfailed/xpassed if they exist
        if stats.get("xfailed", 0) > 0:
            metrics.append(("⚠️ Expected Failures", stats["xfailed"], "yellow"))
        if stats.get("xpassed", 0) > 0:
            metrics.append(("✨ Unexpected Passes", stats["xpassed"], "green"))

        for label, count, _ in metrics:
            percentage = f"{(count / total * 100):.1f}%" if total > 0 else "0.0%"
            table.add_row(label, str(count), percentage)

        # Add separator and summary rows
        table.add_row("─" * 20, "─" * 10, "─" * 15, style="dim")
        table.add_row("📊 Total Tests", str(total), "100.0%", style="bold")
        table.add_row(
            "⏱ Duration",
            f"{stats['duration']:.2f}s",
            "",
            style="bold magenta",
        )
        table.add_row(
            "👥 Workers",
            str(workers),
            "",
            style="bold cyan",
        )

        # Add coverage if available
        if stats.get("coverage") is not None:
            table.add_row(
                "📈 Coverage",
                f"{stats['coverage']:.1f}%",
                "",
                style="bold green",
            )

        # Create panel with appropriate styling
        border_style = "green" if success else "red"
        title_icon = "✅" if success else "❌"
        title_text = "Test Results" if success else "Test Results (Failed)"

        panel = Panel(
            table,
            title=f"[bold]{title_icon} {title_text}[/bold]",
            border_style=border_style,
            padding=(0, 1),
            width=get_console_width(),
        )

        self.console.print(panel)

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

    def _try_service_coverage(self) -> float | None:
        """Try coverage service fallback.

        Returns:
            Coverage value if available, None otherwise
        """
        try:
            current_coverage = self._get_coverage_from_service()
            if current_coverage is not None:
                self.console.print(
                    f"[dim]📊 Coverage from service fallback: {current_coverage:.2f}%[/dim]"
                )
            return current_coverage
        except AttributeError:
            # Service method doesn't exist, skip
            return None

    def _handle_zero_coverage_fallback(self, current_coverage: float | None) -> None:
        """Handle 0.0% fallback case when coverage.json exists."""
        coverage_json_path = self.pkg_path / "coverage.json"
        if current_coverage is None and coverage_json_path.exists():
            self.console.print(
                "[yellow]⚠️[/yellow] Skipping 0.0% fallback when coverage.json exists"
            )

    def _get_fallback_coverage(
        self, ratchet_result: dict[str, t.Any], current_coverage: float | None
    ) -> float | None:
        """Get coverage from fallback sources."""
        # Secondary: Try ratchet result if coverage.json failed
        if current_coverage is None and ratchet_result:
            # Try to extract from ratchet result
            if "current_coverage" in ratchet_result:
                current_coverage = ratchet_result["current_coverage"]
                if current_coverage is not None and current_coverage > 0:
                    self.console.print(
                        f"[dim]📊 Coverage from ratchet result: {current_coverage:.2f}%[/dim]"
                    )

        # Tertiary: Try coverage service, but only accept non-zero values
        if current_coverage is None:
            current_coverage = self._try_service_coverage()
            if current_coverage is None:
                self._handle_zero_coverage_fallback(current_coverage)

        return current_coverage

    def _update_coverage_badge(self, ratchet_result: dict[str, t.Any]) -> None:
        """Update coverage badge in README.md if coverage changed."""
        try:
            # Check if coverage files exist and inform user
            coverage_json_path = self.pkg_path / "coverage.json"
            ratchet_path = self.pkg_path / ".coverage-ratchet.json"

            if not coverage_json_path.exists():
                self.console.print(
                    "[yellow]ℹ️[/yellow] Coverage file doesn't exist yet, will be created after test run"
                )
            if not ratchet_path.exists():
                self.console.print(
                    "[yellow]ℹ️[/yellow] Coverage ratchet file doesn't exist yet, initializing..."
                )

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
                self.console.print(f"[red]📉[/red] {ratchet_result['message']}")
            else:
                current = ratchet_result.get("current_coverage", 0)
                previous = ratchet_result.get("previous_coverage", 0)
                self.console.print(
                    f"[red]📉[/red] Coverage regression: "
                    f"{current: .2f}% < {previous: .2f}%"
                )
            return False

    def _handle_coverage_improvement(self, ratchet_result: dict[str, t.Any]) -> None:
        improvement = ratchet_result.get("improvement", 0)
        current = ratchet_result.get("current_coverage", 0)

        self.console.print(
            f"[green]📈[/green] Coverage improved by {improvement: .2f}% "
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
        if not self.use_lsp_diagnostics or self._lsp_client is None:
            return True

        try:
            # Use injected LSP client (already instantiated)
            lsp_client = self._lsp_client

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
