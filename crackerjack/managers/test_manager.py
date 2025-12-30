import re
import subprocess
import time
import typing as t
from pathlib import Path
from rich.console import Console
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from crackerjack.config import get_console_width
from crackerjack.models.protocols import (
    CoverageBadgeServiceProtocol,
    CoverageRatchetProtocol,
    OptionsProtocol,
)
from crackerjack.models.test_models import TestFailure
from crackerjack.services.lsp_client import LSPClient

from .test_command_builder import TestCommandBuilder
from .test_executor import TestExecutor

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
root_path = Path.cwd()

class TestManager:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        coverage_ratchet: CoverageRatchetProtocol | None = None,
        coverage_badge: CoverageBadgeServiceProtocol | None = None,
        command_builder: TestCommandBuilder | None = None,
        lsp_client: LSPClient | None = None,
    ) -> None:
        if console is None:
            try:
                console = Console()
            except Exception:
                console = Console()

        if coverage_ratchet is None:
            coverage_ratchet = None

        if coverage_badge is None:
            coverage_badge = None

        if command_builder is None:
            command_builder = TestCommandBuilder()

        self.console = console
        # Ensure a concrete pathlib.Path instance to avoid async Path behaviors
        # and to guarantee sync filesystem operations in this manager.
        resolved_path = pkg_path or root_path
        try:
            self.pkg_path = Path(str(resolved_path))
        except Exception:
            # Fallback in the unlikely event Path.cwd() lacks __str__
            self.pkg_path = Path(resolved_path)

        # Ensure downstream components receive a concrete pathlib.Path
        self.executor = TestExecutor(console, self.pkg_path)
        self.command_builder = command_builder

        # Services injected via ACB DI
        self.coverage_ratchet = coverage_ratchet
        self._coverage_badge_service = coverage_badge
        self._lsp_client = lsp_client

        self._last_test_failures: list[str] = []
        self._progress_callback: t.Callable[[dict[str, t.Any]], None] | None = None
        self.coverage_ratchet_enabled = coverage_ratchet is not None
        self.use_lsp_diagnostics = True
        self._service_initialized = False
        self._request_count = 0
        self._error_count = 0
        self._custom_metrics: dict[str, t.Any] = {}
        self._resources: list[t.Any] = []

    def set_progress_callback(
        self,
        callback: t.Callable[[dict[str, t.Any]], None] | None,
    ) -> None:
        self._progress_callback = callback

    def initialize(self) -> None:
        self._service_initialized = True

    def cleanup(self) -> None:
        for resource in self._resources.copy():
            self.cleanup_resource(resource)
        self._resources.clear()
        self._service_initialized = False

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        self.cleanup()

    def metrics(self) -> dict[str, t.Any]:
        return {
            "initialized": self._service_initialized,
            "requests": self._request_count,
            "errors": self._error_count,
            "custom_metrics": self._custom_metrics.copy(),
        }

    def is_healthy(self) -> bool:
        return self.health_check()

    def register_resource(self, resource: t.Any) -> None:
        self._resources.append(resource)

    def cleanup_resource(self, resource: t.Any) -> None:
        cleanup = getattr(resource, "cleanup", None)
        close = getattr(resource, "close", None)
        if callable(cleanup):
            cleanup()
        elif callable(close):
            close()

    def record_error(self, error: Exception) -> None:
        self._error_count += 1

    def increment_requests(self) -> None:
        self._request_count += 1

    def get_custom_metric(self, name: str) -> t.Any:
        return self._custom_metrics.get(name)

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        self._custom_metrics[name] = value

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
        try:
            with Live(spinner, console=self.console, transient=True):
                result = subprocess.run(
                    cmd, cwd=self.pkg_path, capture_output=True, text=True
                )
        except Exception:
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
        if self.coverage_ratchet is None:
            return {"status": "disabled", "message": "Coverage ratchet unavailable"}
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
            if self.coverage_ratchet is None:
                return None
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
            if self.coverage_ratchet is None:
                direct_coverage = self._get_coverage_from_file()
                return self._handle_no_ratchet_status(direct_coverage)

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
        if self._should_render_test_panel(stats):
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
        self.console.print(f"[red]❌[/red] Tests failed in {duration:.1f}s")

        # Parse and display test statistics panel (use stdout for stats)
        combined_output = stdout + "\n" + stderr
        clean_output = self._strip_ansi_codes(combined_output)
        stats = self._parse_test_statistics(clean_output, already_clean=True)
        if self._should_render_test_panel(stats):
            self._render_test_results_panel(stats, workers, success=False)

        # Always show key failure information, not just in verbose mode
        if clean_output.strip():
            # Extract and show essential failure details even in non-verbose mode
            failure_lines = self._extract_failure_lines(clean_output)
            if failure_lines:
                self._last_test_failures = failure_lines
                self._render_banner("Key Test Failures", line_style="red")

                for failure in failure_lines:
                    self.console.print(f"[red]• {failure}[/red]")
            else:
                self._last_test_failures = []

            # Enhanced error reporting in verbose mode
            if options.verbose or getattr(options, "ai_debug", False):
                self._render_banner(
                    "Full Test Output (Enhanced)",
                    line_style="red",
                )
                # Use Rich-formatted output instead of raw dump
                self._render_formatted_output(clean_output, options, already_clean=True)
        else:
            # Show some information even when there's no output
            border_line = "-" * getattr(options, "column_width", 70)
            self.console.print("\n🧪 TESTS Failed test execution")
            self.console.print(border_line)

            self.console.print(
                "    [yellow]This may indicate a timeout or critical error[/yellow]"
            )
            self.console.print(
                f"    [yellow]Duration: {duration:.1f}s, Workers: {workers}[/yellow]"
            )
            if duration > 290:  # Approaching 300s timeout
                self.console.print(
                    "    [yellow]⚠️  Execution time was very close to timeout, may have timed out[/yellow]"
                )
            self.console.print(
                "    [red]Workflow failed: Test workflow execution failed[/red]"
            )
            self.console.print(border_line)
            self._last_test_failures = []

        return False

    def _handle_test_error(self, start_time: float, error: Exception) -> bool:
        duration = time.time() - start_time
        self.console.print(
            f"[red]💥[/red] Test execution error after {duration: .1f}s: {error}"
        )
        return False

    def _parse_test_statistics(
        self, output: str, *, already_clean: bool = False
    ) -> dict[str, t.Any]:
        """Parse test statistics from pytest output.

        Extracts metrics like passed, failed, skipped, errors, and duration
        from pytest's summary line.

        Args:
            output: Raw pytest output text

        Returns:
            Dictionary containing test statistics
        """
        clean_output = output if already_clean else self._strip_ansi_codes(output)
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
            summary_match = self._extract_pytest_summary(clean_output)
            if summary_match:
                summary_text, duration = self._parse_summary_match(
                    summary_match, clean_output
                )
                stats["duration"] = duration

                # Extract metrics from summary
                self._extract_test_metrics(summary_text, stats)

            # Calculate totals and fallback if summary missing
            self._calculate_total_tests(stats, clean_output)

            # Extract coverage if present
            stats["coverage"] = self._extract_coverage_from_output(clean_output)

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
        status_tokens = [
            ("passed", "PASSED"),
            ("failed", "FAILED"),
            ("skipped", "SKIPPED"),
            ("errors", "ERROR"),
            ("xfailed", "XFAIL"),
            ("xpassed", "XPASS"),
        ]

        for raw_line in output.splitlines():
            line = raw_line.strip()
            if "::" not in line:
                continue

            line_upper = line.upper()
            if line_upper.startswith(
                ("FAILED", "ERROR", "XPASS", "XFAIL", "SKIPPED", "PASSED")
            ):
                continue

            for key, token in status_tokens:
                if token in line_upper:
                    stats[key] += 1
                    break

        stats["total"] = sum(
            [
                stats["passed"],
                stats["failed"],
                stats["skipped"],
                stats["errors"],
                stats.get("xfailed", 0),
                stats.get("xpassed", 0),
            ]
        )

        if stats["total"] == 0:
            legacy_patterns = {
                "passed": r"(?:\.|✓)\s*(?:PASSED|pass)",
                "failed": r"(?:F|X|❌)\s*(?:FAILED|fail)",
                "skipped": r"(?:s|S|.SKIPPED|skip)",
                "errors": r"ERROR|E\s+",
            }
            for key, pattern in legacy_patterns.items():
                stats[key] = len(re.findall(pattern, output, re.IGNORECASE))

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

    def _should_render_test_panel(self, stats: dict[str, t.Any]) -> bool:
        """Determine if the test results panel should be rendered."""
        return any(
            [
                stats.get("total", 0) > 0,
                stats.get("passed", 0) > 0,
                stats.get("failed", 0) > 0,
                stats.get("errors", 0) > 0,
                stats.get("skipped", 0) > 0,
                stats.get("xfailed", 0) > 0,
                stats.get("xpassed", 0) > 0,
                stats.get("duration", 0.0) > 0.0,
                stats.get("coverage") is not None,
            ]
        )

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

    def _render_banner(
        self,
        title: str,
        *,
        line_style: str = "red",
        title_style: str | None = None,
        char: str = "━",
        padding: bool = True,
    ) -> None:
        """Render a horizontal banner that respects configured console width."""
        width = max(20, get_console_width())
        line_text = Text(char * width, style=line_style)
        resolved_title_style = title_style or ("bold " + line_style).strip()
        title_text = Text(title, style=resolved_title_style)

        if padding:
            self.console.print()

        self.console.print(line_text)
        self.console.print(title_text)
        self.console.print(line_text)

        if padding:
            self.console.print()

    def _process_coverage_ratchet(self) -> bool:
        if not self.coverage_ratchet_enabled or self.coverage_ratchet is None:
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
            current_coverage = self.coverage_ratchet.get_baseline_coverage()
            if current_coverage is not None and current_coverage > 0:
                self.console.print(
                    f"[dim]📊 Coverage from service fallback: {current_coverage:.2f}%[/dim]"
                )
                return current_coverage
            return None
        except (AttributeError, Exception):
            # Service method doesn't exist or failed, skip
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

    @staticmethod
    def _strip_ansi_codes(text: str) -> str:
        """Remove ANSI escape sequences from a string."""
        return ANSI_ESCAPE_RE.sub("", text)

    def _split_output_sections(self, output: str) -> list[tuple[str, str]]:
        """Split pytest output into logical sections for rendering.

        Sections:
        - header: Session start, test collection
        - failure: Individual test failures with tracebacks
        - summary: Short test summary info
        - footer: Coverage, timing, final stats

        Returns:
            List of (section_type, section_content) tuples
        """
        sections = []
        lines = output.split("\n")

        current_section: list[str] = []
        current_type = "header"

        for line in lines:
            # Detect section boundaries
            if "short test summary" in line.lower():
                # Save previous section
                if current_section:
                    sections.append((current_type, "\n".join(current_section)))
                current_section = [line]
                current_type = "summary"

            elif " FAILED " in line or " ERROR " in line:
                # Save previous section
                if current_section and current_type != "failure":
                    sections.append((current_type, "\n".join(current_section)))
                    current_section = []
                current_type = "failure"
                current_section.append(line)

            elif line.startswith("=") and ("passed" in line or "failed" in line):
                # Footer section
                if current_section:
                    sections.append((current_type, "\n".join(current_section)))
                current_section = [line]
                current_type = "footer"

            else:
                current_section.append(line)

        # Add final section
        if current_section:
            sections.append((current_type, "\n".join(current_section)))

        return sections

    def _render_formatted_output(
        self,
        output: str,
        options: OptionsProtocol,
        *,
        already_clean: bool = False,
    ) -> None:
        """Render test output with Rich formatting and sections.

        Phase 2: Uses structured failure parser when available.

        Args:
            output: Raw pytest output text
            options: Test options (for verbosity level)
        """
        from rich.panel import Panel

        clean_output = output if already_clean else self._strip_ansi_codes(output)

        # Try structured parsing first (Phase 2)
        try:
            failures = self._extract_structured_failures(clean_output)
            if failures:
                self._render_banner(
                    "Detailed Failure Analysis",
                    line_style="red",
                    char="═",
                )

                self._render_structured_failure_panels(failures)

                # Still show summary section
                sections = self._split_output_sections(clean_output)
                for section_type, section_content in sections:
                    if section_type == "summary":
                        panel = Panel(
                            section_content.strip(),
                            title="[bold yellow]📋 Test Summary[/bold yellow]",
                            border_style="yellow",
                            width=get_console_width(),
                        )
                        self.console.print(panel)
                    elif section_type == "footer":
                        self.console.print(
                            f"\n[cyan]{section_content.strip()}[/cyan]\n"
                        )

                return

        except Exception as e:
            # Fallback to Phase 1 rendering if parsing fails
            self.console.print(
                f"[dim yellow]⚠️  Structured parsing failed: {e}[/dim yellow]"
            )
            self.console.print(
                "[dim yellow]Falling back to standard formatting...[/dim yellow]\n"
            )

        # Fallback: Phase 1 section-based rendering
        sections = self._split_output_sections(clean_output)

        for section_type, section_content in sections:
            if not section_content.strip():
                continue

            if section_type == "failure":
                self._render_failure_section(section_content)
            elif section_type == "summary":
                panel = Panel(
                    section_content.strip(),
                    title="[bold yellow]📋 Test Summary[/bold yellow]",
                    border_style="yellow",
                    width=get_console_width(),
                )
                self.console.print(panel)
            elif section_type == "footer":
                self.console.print(f"\n[cyan]{section_content.strip()}[/cyan]\n")
            else:
                # Header and other sections (dimmed)
                if options.verbose or getattr(options, "ai_debug", False):
                    self.console.print(f"[dim]{section_content}[/dim]")

    def _render_failure_section(self, section_content: str) -> None:
        """Render a failure section with syntax highlighting.

        Args:
            section_content: Failure output text
        """
        from rich.panel import Panel
        from rich.syntax import Syntax

        # Apply Python syntax highlighting to tracebacks
        syntax = Syntax(
            section_content,
            "python",
            theme="monokai",
            line_numbers=False,
            word_wrap=True,
            background_color="default",
        )

        panel = Panel(
            syntax,
            title="[bold red]❌ Test Failure[/bold red]",
            border_style="red",
            width=get_console_width(),
        )
        self.console.print(panel)

    def _parse_failure_header(
        self, line: str, current_failure: "TestFailure | None"
    ) -> tuple["TestFailure | None", bool]:
        """Parse failure header line."""
        import re

        from crackerjack.models.test_models import TestFailure

        failure_match = re.match(r"^(.+?)\s+(FAILED|ERROR)\s*(?:\[(.+?)\])?", line)
        if failure_match:
            test_path, status, params = failure_match.groups()
            new_failure = TestFailure(
                test_name=test_path + (f"[{params}]" if params else ""),
                status=status,
                location=test_path,
            )
            return new_failure, True
        return current_failure, False

    def _parse_location_and_assertion(
        self, line: str, current_failure: "TestFailure", in_traceback: bool
    ) -> bool:
        """Parse location and assertion lines."""
        import re

        # Detect location: "tests/test_foo.py:42: AssertionError"
        location_match = re.match(r"^(.+?\.py):(\d+):\s*(.*)$", line)
        if location_match and in_traceback:
            file_path, line_num, error_type = location_match.groups()
            current_failure.location = f"{file_path}:{line_num}"
            if error_type:
                current_failure.short_summary = error_type
            return True

        # Detect assertion errors
        if "AssertionError:" in line or line.strip().startswith("E       assert "):
            assertion_text = line.strip().lstrip("E").strip()
            if current_failure.assertion:
                current_failure.assertion += "\n" + assertion_text
            else:
                current_failure.assertion = assertion_text
            return True

        return False

    def _parse_captured_section_header(self, line: str) -> tuple[bool, str | None]:
        """Parse captured output section headers."""
        if "captured stdout" in line.lower():
            return True, "stdout"
        elif "captured stderr" in line.lower():
            return True, "stderr"
        return False, None

    def _parse_traceback_line(
        self, line: str, lines: list[str], i: int, current_failure: "TestFailure"
    ) -> bool:
        """Parse traceback lines."""
        if line.startswith(("    ", "\t", "E   ")):
            current_failure.traceback.append(line)
            return True
        elif line.strip().startswith(("=", "FAILED")) or (
            i < len(lines) - 1 and "FAILED" in lines[i + 1]
        ):
            return False
        return True

    def _parse_captured_output(
        self, line: str, capture_type: str | None, current_failure: "TestFailure"
    ) -> bool:
        """Parse captured output lines."""
        if line.strip().startswith(("=", "_")):
            return False

        if capture_type == "stdout":
            if current_failure.captured_stdout:
                current_failure.captured_stdout += "\n" + line
            else:
                current_failure.captured_stdout = line
        elif capture_type == "stderr":
            if current_failure.captured_stderr:
                current_failure.captured_stderr += "\n" + line
            else:
                current_failure.captured_stderr = line
        return True

    def _extract_structured_failures(self, output: str) -> list["TestFailure"]:
        """Extract structured failure information from pytest output.

        This parser handles pytest's standard output format and extracts:
        - Test names and locations
        - Full tracebacks
        - Assertion errors
        - Captured output (stdout/stderr)
        - Duration (if available)

        Args:
            output: Raw pytest output text

        Returns:
            List of TestFailure objects
        """
        failures = []
        lines = output.split("\n")

        current_failure = None
        in_traceback = False
        in_captured = False
        capture_type = None

        for i, line in enumerate(lines):
            # Parse failure header
            new_failure, header_found = self._parse_failure_header(
                line, current_failure
            )
            if header_found:
                if current_failure:
                    failures.append(current_failure)
                current_failure = new_failure
                in_traceback = True
                in_captured = False
                continue

            if not current_failure:
                continue

            # Parse location and assertion
            if self._parse_location_and_assertion(line, current_failure, in_traceback):
                continue

            # Parse captured section headers
            is_captured, new_capture_type = self._parse_captured_section_header(line)
            if is_captured:
                in_captured = True
                capture_type = new_capture_type
                in_traceback = False
                continue

            # Parse traceback lines
            if in_traceback:
                in_traceback = self._parse_traceback_line(
                    line, lines, i, current_failure
                )

            # Parse captured output
            if in_captured and capture_type:
                in_captured = self._parse_captured_output(
                    line, capture_type, current_failure
                )
                if not in_captured:
                    capture_type = None

        # Save final failure
        if current_failure:
            failures.append(current_failure)

        return failures

    def _render_structured_failure_panels(self, failures: list["TestFailure"]) -> None:
        """Render failures as Rich panels with tables and syntax highlighting.

        Each failure is rendered in a panel containing:
        - Summary table (test name, location, status)
        - Assertion details (if present)
        - Syntax-highlighted traceback
        - Captured output (if any)

        Args:
            failures: List of TestFailure objects
        """
        from rich import box
        from rich.console import Group
        from rich.panel import Panel
        from rich.syntax import Syntax
        from rich.table import Table

        if not failures:
            return

        # Group failures by file for better organization
        failures_by_file: dict[str, list[TestFailure]] = {}
        for failure in failures:
            file_path = failure.get_file_path()
            if file_path not in failures_by_file:
                failures_by_file[file_path] = []
            failures_by_file[file_path].append(failure)

        # Render each file group
        for file_path, file_failures in failures_by_file.items():
            self.console.print(
                f"\n[bold red]📁 {file_path}[/bold red] ({len(file_failures)} failure(s))\n"
            )

            for i, failure in enumerate(file_failures, 1):
                # Create details table
                table = Table(
                    show_header=False,
                    box=box.SIMPLE,
                    padding=(0, 1),
                    border_style="red",
                )
                table.add_column("Key", style="cyan bold", width=12)
                table.add_column("Value", overflow="fold")

                # Add rows
                table.add_row("Test", f"[yellow]{failure.test_name}[/yellow]")
                table.add_row(
                    "Location", f"[blue underline]{failure.location}[/blue underline]"
                )
                table.add_row("Status", f"[red bold]{failure.status}[/red bold]")

                if failure.duration:
                    table.add_row("Duration", f"{failure.duration:.3f}s")

                # Add summary timing insight if available
                duration_note = self._get_duration_note(failure)
                if duration_note:
                    table.add_row("Timing", duration_note)

                # Components for panel (mixed list of renderables for Rich Group)
                components: list[t.Any] = [table]

                # Add assertion details
                if failure.assertion:
                    components.extend(("", "[bold red]Assertion Error:[/bold red]"))

                    # Syntax highlight the assertion
                    assertion_syntax = Syntax(
                        failure.assertion,
                        "python",
                        theme="monokai",
                        line_numbers=False,
                        background_color="default",
                    )
                    components.append(assertion_syntax)

                # Add relevant traceback (last 15 lines)
                relevant_traceback = failure.get_relevant_traceback(max_lines=15)
                if relevant_traceback:
                    components.extend(("", "[bold red]Traceback:[/bold red]"))

                    traceback_text = "\n".join(relevant_traceback)
                    traceback_syntax = Syntax(
                        traceback_text,
                        "python",
                        theme="monokai",
                        line_numbers=False,
                        word_wrap=True,
                        background_color="default",
                    )
                    components.append(traceback_syntax)

                # Add captured output if present
                if failure.captured_stdout:
                    components.extend(("", "[bold yellow]Captured stdout:[/bold yellow]"))
                    components.append(f"[dim]{failure.captured_stdout}[/dim]")

                if failure.captured_stderr:
                    components.extend(("", "[bold yellow]Captured stderr:[/bold yellow]"))
                    components.append(f"[dim]{failure.captured_stderr}[/dim]")

                # Create grouped content
                group = Group(*components)

                # Render panel
                panel = Panel(
                    group,
                    title=f"[bold red]❌ Failure {i}/{len(file_failures)}[/bold red]",
                    border_style="red",
                    width=get_console_width(),
                    padding=(1, 2),
                )

            self.console.print(panel)

    def _get_duration_note(self, failure: "TestFailure") -> str | None:
        """Return a duration note highlighting long-running failures."""
        if not failure.duration:
            return None

        if failure.duration > 5:
            return (
                f"[bold red]{failure.duration:.2f}s – investigate slow test[/bold red]"
            )
        if failure.duration > 2:
            return f"[yellow]{failure.duration:.2f}s – moderately slow[/yellow]"
        return None

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
