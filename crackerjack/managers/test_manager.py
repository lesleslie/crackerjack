import re
import subprocess
import time
import typing as t
from pathlib import Path

from rich import box
from rich.console import Console
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


        resolved_path = pkg_path or root_path
        try:
            self.pkg_path = Path(str(resolved_path))
        except Exception:

            self.pkg_path = Path(resolved_path)


        self.executor = TestExecutor(console, self.pkg_path)
        self.command_builder = command_builder


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

        if hasattr(options, "test") and not options.test:
            return True

        start_time = time.time()

        try:
            result = self._execute_test_workflow(options)
            duration = time.time() - start_time


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
        import json

        coverage_json_path = self.pkg_path / "coverage.json"
        if not coverage_json_path.exists():
            return None

        try:
            with coverage_json_path.open() as f:
                coverage_data = json.load(f)


            totals = coverage_data.get("totals", {})
            percent_covered = totals.get("percent_covered", None)

            if percent_covered is not None:
                return float(percent_covered)


            if "percent_covered" in coverage_data:
                return float(coverage_data["percent_covered"])


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
        return direct_coverage if direct_coverage is not None else ratchet_coverage

    def get_coverage(self) -> dict[str, t.Any]:
        try:
            if self.coverage_ratchet is None:
                direct_coverage = self._get_coverage_from_file()
                return self._handle_no_ratchet_status(direct_coverage)

            status = self.coverage_ratchet.get_status_report()


            direct_coverage = self._get_coverage_from_file()


            if (
                not status or status.get("status") == "not_initialized"
            ) and direct_coverage is not None:
                return self._handle_no_ratchet_status(direct_coverage)


            if not status or status.get("status") == "not_initialized":
                return self._handle_no_ratchet_status(None)


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


        stats = self._parse_test_statistics(output)

        stats["duration"] = duration
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

        combined_output = stdout + "\n" + stderr
        clean_output = self._strip_ansi_codes(combined_output)
        stats = self._parse_test_statistics(clean_output, already_clean=True)

        stats["duration"] = duration
        if self._should_render_test_panel(stats):
            self._render_test_results_panel(stats, workers, success=False)


        if clean_output.strip():

            failure_lines = self._extract_failure_lines(clean_output)
            if failure_lines:
                self._last_test_failures = failure_lines
                self._render_banner("Key Test Failures", line_style="red")

                for failure in failure_lines:

                    print(f"• {failure}")
            else:
                self._last_test_failures = []
        else:

            border_line = "-" * getattr(options, "column_width", 70)
            self.console.print("\n🧪 TESTS Failed test execution")
            self.console.print(border_line)

            self.console.print(
                " [yellow]This may indicate a timeout or critical error[/yellow]"
            )
            self.console.print(
                f" [yellow]Duration: {duration:.1f}s, Workers: {workers}[/yellow]"
            )

            timeout = self.command_builder.get_test_timeout(options)
            timeout_threshold = timeout * 0.9
            if duration > timeout_threshold:
                self.console.print(
                    f" [yellow]⚠️ Execution time ({duration:.1f}s) was very close to timeout ({timeout}s), may have timed out[/yellow]"
                )
            self.console.print(
                " [red]Workflow failed: Test workflow execution failed[/red]"
            )
            self.console.print(border_line)
            self._last_test_failures = []


        if (options.verbose or getattr(options, "ai_debug", False)) and clean_output.strip():

            self._render_formatted_output(clean_output, options, already_clean=True)

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

            summary_match = self._extract_pytest_summary(clean_output)
            if summary_match:
                summary_text, duration = self._parse_summary_match(
                    summary_match, clean_output
                )
                stats["duration"] = duration


                self._extract_test_metrics(summary_text, stats)


            self._calculate_total_tests(stats, clean_output)


            stats["coverage"] = self._extract_coverage_from_output(clean_output)

        except (ValueError, AttributeError) as e:
            self.console.print(f"[dim]⚠️ Failed to parse test statistics: {e}[/dim]")

        return stats

    def _extract_pytest_summary(self, output: str) -> re.Match[str] | None:
        summary_patterns = [
            r"=+\s+(.+?)\s+in\s+([\d.]+)s?\s*=+",
            r"(\d+\s+\w+)+\s+in\s+([\d.]+)s?",
            r"(\d+.*)in\s+([\d.]+)s?",
        ]

        for pattern in summary_patterns:
            match = re.search(pattern, output)
            if match:
                return match
        return None

    def _parse_summary_match(
        self, match: re.Match[str], output: str
    ) -> tuple[str, float]:
        if len(match.groups()) >= 2:
            summary_text = match.group(1)
            duration = float(match.group(2))
        else:

            duration = (
                float(match.group(1))
                if match.group(1).replace(".", "").isdigit()
                else 0.0
            )
            summary_text = output

        return summary_text, duration

    def _extract_test_metrics(self, summary_text: str, stats: dict[str, t.Any]) -> None:
        for metric in ("passed", "failed", "skipped", "error", "xfailed", "xpassed"):
            metric_pattern = rf"(\d+)\s+{metric}"
            metric_match = re.search(metric_pattern, summary_text, re.IGNORECASE)
            if metric_match:
                count = int(metric_match.group(1))
                key = "errors" if metric == "error" else metric
                stats[key] = count

    def _calculate_total_tests(self, stats: dict[str, t.Any], output: str) -> None:
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


        if stats["total"] == 0:
            self._fallback_count_tests(output, stats)

    def _fallback_count_tests(self, output: str, stats: dict[str, t.Any]) -> None:
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
        coverage_pattern = r"TOTAL\s+\d+\s+\d+\s+(\d+)%"
        coverage_match = re.search(coverage_pattern, output)
        if coverage_match:
            return float(coverage_match.group(1))
        return None

    def _should_render_test_panel(self, stats: dict[str, t.Any]) -> bool:
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
        table = Table(box=box.SIMPLE, header_style="bold bright_white")
        table.add_column("Metric", style="cyan", overflow="fold")
        table.add_column("Count", justify="right", style="bright_white")
        table.add_column("Percentage", justify="right", style="magenta")

        total = stats["total"]


        metrics = [
            ("✅ Passed", stats["passed"], "green"),
            ("❌ Failed", stats["failed"], "red"),
            ("⏭ Skipped", stats["skipped"], "yellow"),
            ("💥 Errors", stats["errors"], "red"),
        ]


        if stats.get("xfailed", 0) > 0:
            metrics.append(("📌 XFailed", stats["xfailed"], "yellow"))
        if stats.get("xpassed", 0) > 0:
            metrics.append(("⭐ XPassed", stats["xpassed"], "green"))

        for label, count, _ in metrics:
            percentage = f"{(count / total * 100):.1f}%" if total > 0 else "0.0%"
            table.add_row(label, str(count), percentage)


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


        if stats.get("coverage") is not None:
            table.add_row(
                "📈 Coverage",
                f"{stats['coverage']:.1f}%",
                "",
                style="bold green",
            )


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


        self._update_coverage_badge(ratchet_result)

        return self._handle_ratchet_result(ratchet_result)

    def _attempt_coverage_extraction(self) -> float | None:

        current_coverage = self._get_coverage_from_file()
        if current_coverage is not None:
            return current_coverage

        return None

    def _handle_coverage_extraction_result(
        self, current_coverage: float | None
    ) -> float | None:
        if current_coverage is not None:
            self.console.print(
                f"[dim]📊 Coverage extracted from coverage.json: {current_coverage:.2f}%[/dim]"
            )
        return current_coverage

    def _try_service_coverage(self) -> float | None:
        try:
            current_coverage = self.coverage_ratchet.get_baseline_coverage()
            if current_coverage is not None and current_coverage > 0:
                self.console.print(
                    f"[dim]📊 Coverage from service fallback: {current_coverage:.2f}%[/dim]"
                )
                return current_coverage
            return None
        except (AttributeError, Exception):

            return None

    def _handle_zero_coverage_fallback(self, current_coverage: float | None) -> None:
        coverage_json_path = self.pkg_path / "coverage.json"
        if current_coverage is None and coverage_json_path.exists():
            self.console.print(
                "[yellow]⚠️[/yellow] Skipping 0.0% fallback when coverage.json exists"
            )

    def _get_fallback_coverage(
        self, ratchet_result: dict[str, t.Any], current_coverage: float | None
    ) -> float | None:

        if current_coverage is None and ratchet_result:

            if "current_coverage" in ratchet_result:
                current_coverage = ratchet_result["current_coverage"]
                if current_coverage is not None and current_coverage > 0:
                    self.console.print(
                        f"[dim]📊 Coverage from ratchet result: {current_coverage:.2f}%[/dim]"
                    )


        if current_coverage is None:
            current_coverage = self._try_service_coverage()
            if current_coverage is None:
                self._handle_zero_coverage_fallback(current_coverage)

        return current_coverage

    def _update_coverage_badge(self, ratchet_result: dict[str, t.Any]) -> None:
        try:

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


            current_coverage = self._attempt_coverage_extraction()
            current_coverage = self._handle_coverage_extraction_result(current_coverage)


            current_coverage = self._get_fallback_coverage(
                ratchet_result, current_coverage
            )


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
        """Extract failed test names from pytest output.

        Attempts to extract test names from the short test summary section,
        falling back to scanning for FAILED lines and test paths.

        Args:
            output: Full pytest output string

        Returns:
            List of failed test names (max 10)
        """
        import re

        lines = output.split("\n")

        # Try extracting from short test summary
        failures = self._extract_from_short_summary(lines)

        # Fallback: scan for test paths if no failures found
        if not failures:
            failures = self._extract_from_test_paths(lines)

        return failures[:10]

    def _extract_from_short_summary(self, lines: list[str]) -> list[str]:
        """Extract failed test names from pytest short test summary section.

        Args:
            lines: Split output lines

        Returns:
            List of test names that failed
        """
        import re

        failures = []
        in_summary = False

        for line in lines:
            if "short test summary" in line.lower():
                in_summary = True
                continue

            if in_summary and line.strip().startswith("="):
                break

            if in_summary and line.strip().startswith("FAILED"):
                test_name = self._parse_summary_failed_line(line.strip())
                if test_name:
                    failures.append(test_name)

        return failures

    def _parse_summary_failed_line(self, line: str) -> str | None:
        """Parse a single FAILED line from short summary.

        Args:
            line: Line containing FAILED marker

        Returns:
            Extracted test name or None
        """
        import re

        # Try format: "FAILED test_path - error"
        match = re.search(r"FAILED\s+(.+?)\s+-", line)
        if match:
            return match.group(1).strip()

        # Try format: "FAILED test_path"
        if "FAILED" in line:
            parts = line.split("FAILED", 1)
            if len(parts) > 1:
                test_name = parts[1].strip().split(" - ")[0].strip()
                return test_name or None

        return None

    def _extract_from_test_paths(self, lines: list[str]) -> list[str]:
        """Extract test names from lines containing :: and FAILED markers.

        Args:
            lines: Split output lines

        Returns:
            List of test names (max 10)
        """
        failures = []

        for line in lines:
            test_name = self._try_extract_test_name(line)
            if test_name and test_name not in failures:
                failures.append(test_name)
                if len(failures) >= 10:
                    break

        return failures

    def _try_extract_test_name(self, line: str) -> str | None:
        """Try to extract test name from a line containing :: and FAILED.

        Args:
            line: Output line to parse

        Returns:
            Extracted test name or None
        """
        import re

        if not ("::" in line and "FAILED" in line.upper()):
            return None

        test_match = re.search(r'([a-zA-Z_/]+::.*?)(?:\s+|$)', line)
        if test_match:
            return test_match.group(1).strip()

        return None

    @staticmethod
    def _strip_ansi_codes(text: str) -> str:
        return ANSI_ESCAPE_RE.sub("", text)

    def _split_output_sections(self, output: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []

        current_section: list[str] = []
        current_type = "header"

        lines = output.split("\n")
        for line in lines:
            current_type, current_section = self._process_line_for_section(
                line, current_type, current_section, sections
            )


        if current_section:
            sections.append((current_type, "\n".join(current_section)))

        return sections

    def _process_line_for_section(
        self,
        line: str,
        current_type: str,
        current_section: list[str],
        sections: list[tuple[str, str]],
    ) -> tuple[str, list[str]]:
        if self._is_summary_boundary(line):
            return self._handle_section_transition(
                line, current_type, current_section, sections, "summary"
            )
        elif self._is_failure_start(line):
            return self._handle_failure_section(
                line, current_type, current_section, sections
            )
        elif self._is_footer_start(line):
            return self._handle_section_transition(
                line, current_type, current_section, sections, "footer"
            )
        else:
            current_section.append(line)
            return current_type, current_section

    def _is_summary_boundary(self, line: str) -> bool:
        return "short test summary" in line.lower()

    def _is_failure_start(self, line: str) -> bool:
        return " FAILED " in line or " ERROR " in line

    def _is_footer_start(self, line: str) -> bool:
        return line.startswith("=") and ("passed" in line or "failed" in line)

    def _handle_section_transition(
        self,
        line: str,
        current_type: str,
        current_section: list[str],
        sections: list[tuple[str, str]],
        new_type: str,
    ) -> tuple[str, list[str]]:
        if current_section:
            sections.append((current_type, "\n".join(current_section)))
        return new_type, [line]

    def _handle_failure_section(
        self,
        line: str,
        current_type: str,
        current_section: list[str],
        sections: list[tuple[str, str]],
    ) -> tuple[str, list[str]]:
        if current_section and current_type != "failure":
            sections.append((current_type, "\n".join(current_section)))
            current_section = []
        current_type = "failure"
        current_section.append(line)
        return current_type, current_section

    def _render_formatted_output(
        self,
        output: str,
        options: OptionsProtocol,
        *,
        already_clean: bool = False,
    ) -> None:

        clean_output = output if already_clean else self._strip_ansi_codes(output)


        if self._try_structured_rendering(clean_output, options):
            return


        self._render_fallback_sections(clean_output, options)

    def _try_structured_rendering(self, clean_output: str, options: OptionsProtocol) -> bool:
        try:
            failures = self._extract_structured_failures(clean_output)


            if failures:
                self._render_structured_failures_with_summary(clean_output, failures, options)
                return True
            return False
        except Exception as e:
            self._render_parsing_error_message(e)
            return False

    def _render_structured_failures_with_summary(
        self, clean_output: str, failures: list["TestFailure"], options: OptionsProtocol
    ) -> None:

        failed_tests = [f for f in failures if f.status == "FAILED"]
        error_tests = [f for f in failures if f.status == "ERROR"]
        skipped_tests = [f for f in failures if f.status == "SKIPPED"]


        if failed_tests:
            self._render_structured_failure_panels(failed_tests)


        is_verbose = getattr(options, "verbose", False)
        is_debug = getattr(options, "ai_debug", False)
        if error_tests and (is_verbose or is_debug):
            self._render_structured_failure_panels(error_tests)


        if skipped_tests and is_debug:
            self._render_structured_failure_panels(skipped_tests)

    def _render_parsing_error_message(self, error: Exception) -> None:
        self.console.print(
            f"[dim yellow]⚠️ Structured parsing failed: {error}[/dim yellow]"
        )
        self.console.print(
            "[dim yellow]Falling back to standard formatting...[/dim yellow]\n"
        )

    def _render_fallback_sections(
        self, clean_output: str, options: OptionsProtocol
    ) -> None:
        from rich.panel import Panel

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

                if options.verbose or getattr(options, "ai_debug", False):
                    self.console.print(f"[dim]{section_content}[/dim]")

    def _render_failure_section(self, section_content: str) -> None:
        from rich.panel import Panel
        from rich.syntax import Syntax


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
        import re

        from crackerjack.models.test_models import TestFailure


        failure_match = re.match(r"^(.+?)\s+(FAILED|ERROR|SKIPPED|SKIP)", line)
        if failure_match:
            test_path, status = failure_match.groups()

            test_path = re.sub(r"\s*\[[\s\d]+%\]$", "", test_path).strip()


            if not (
                "::" in test_path
                or ".py::" in test_path
                or ".py:" in test_path
                or "/" in test_path
                or "\\" in test_path
            ):


                return current_failure, False


            normalized_status = "SKIPPED" if status == "SKIP" else status

            new_failure = TestFailure(
                test_name=test_path,
                status=normalized_status,
                location=test_path,
            )
            return new_failure, True
        return current_failure, False

    def _parse_location_and_assertion(
        self, line: str, current_failure: "TestFailure", in_traceback: bool
    ) -> bool:
        import re


        location_match = re.match(r"^(.+?\.py):(\d+):\s*(.*)$", line)
        if location_match and in_traceback:
            file_path, line_num, error_type = location_match.groups()
            current_failure.location = f"{file_path}:{line_num}"
            if error_type:
                current_failure.short_summary = error_type
            return True


        if "AssertionError:" in line or line.strip().startswith("E assert "):
            assertion_text = line.strip().lstrip("E").strip()
            if current_failure.assertion:
                current_failure.assertion += "\n" + assertion_text
            else:
                current_failure.assertion = assertion_text
            return True

        return False

    def _parse_captured_section_header(self, line: str) -> tuple[bool, str | None]:
        if "captured stdout" in line.lower():
            return True, "stdout"
        elif "captured stderr" in line.lower():
            return True, "stderr"
        return False, None

    def _parse_traceback_line(
        self, line: str, lines: list[str], i: int, current_failure: "TestFailure"
    ) -> bool:
        if line.startswith((" ", "\t", "E ")):
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
        from crackerjack.models.test_models import TestFailure

        failures: list["TestFailure"] = []
        lines = output.split("\n")

        current_failure = None
        in_traceback = False
        in_captured = False
        capture_type = None

        for i, line in enumerate(lines):
            result = self._parse_failure_line(
                line, lines, i, current_failure, in_traceback, in_captured, capture_type
            )


            if result.get("stop_parsing"):
                break


            if result.get("new_failure"):
                if current_failure:
                    failures.append(current_failure)
                current_failure = result["new_failure"]
                in_traceback = True
                in_captured = False
                capture_type = None
            elif result.get("skip_line"):
                continue
            else:

                in_traceback = result.get("in_traceback", in_traceback)
                in_captured = result.get("in_captured", in_captured)
                capture_type = result.get("capture_type", capture_type)


        if current_failure:
            failures.append(current_failure)


        self._enrich_failures_from_short_summary(failures, output)

        return failures

    def _enrich_failures_from_short_summary(
        self, failures: list["TestFailure"], output: str
    ) -> None:
        """Enrich test failures with data from pytest short summary section.

        Parses the pytest short test summary to extract error messages and
        determine proper failure status (ERROR vs FAILED) for each test.

        Args:
            failures: List of TestFailure objects to enrich
            output: Full pytest output string containing short summary
        """
        from crackerjack.models.test_models import TestFailure

        summary_failures = self._parse_short_summary(output)

        # Case 1: No failures parsed yet, create from summary
        if not failures and summary_failures:
            self._create_failures_from_summary(failures, summary_failures)
            return

        # Case 2: Enrich existing failures with summary data
        if summary_failures:
            self._enrich_existing_failures(failures, summary_failures)

        # Case 3: Match unnamed failures to summary entries
        self._match_unnamed_failures(failures, summary_failures)

    def _parse_short_summary(self, output: str) -> list[dict[str, str]]:
        """Parse pytest short test summary section from output.

        Args:
            output: Full pytest output string

        Returns:
            List of dicts with 'test_path' and 'error_message' keys
        """
        import re

        lines = output.split("\n")
        in_summary = False
        summary_failures: list[dict[str, str]] = []

        for line in lines:
            if "short test summary" in line.lower():
                in_summary = True
                continue

            if in_summary and line.startswith("="):
                break

            if in_summary and line.strip().startswith("FAILED"):
                failure_data = self._parse_summary_failure_line(line.strip())
                if failure_data:
                    summary_failures.append(failure_data)

        return summary_failures

    def _parse_summary_failure_line(self, line: str) -> dict[str, str] | None:
        """Parse a single failure line from short summary.

        Args:
            line: Single line from short test summary

        Returns:
            Dict with 'test_path' and 'error_message' or None
        """
        import re

        # Try format: "FAILED test_path - error message"
        match = re.match(r"^FAILED\s+(.+?)\s+-\s+(.+)$", line)
        if match:
            test_path, error_message = match.groups()
            error_message = re.sub(r'\.\.\.$', '', error_message).strip()
            return {"test_path": test_path, "error_message": error_message}

        # Try format: "FAILED test_path -"
        match2 = re.search(r"FAILED\s+(.+?)\s+-", line)
        if match2:
            test_path = match2.group(1)
            return {
                "test_path": test_path,
                "error_message": "Error: see full output above"
            }

        return None

    def _determine_failure_status(self, error_message: str) -> str:
        """Determine if error represents ERROR or FAILED status.

        Args:
            error_message: Error message from test failure

        Returns:
            "ERROR" for exceptions, "FAILED" for assertion failures
        """
        error_types = (
            "TypeError",
            "KeyError",
            "AttributeError",
            "IndexError",
            "ValueError",
            "RuntimeError",
            "NameError",
            "ImportError",
            "FileNotFoundError",
            "UnboundLocalError",
        )

        if any(
            error_message.startswith(f"{error_type}:")
            for error_type in error_types
        ):
            return "ERROR"
        return "FAILED"

    def _create_failures_from_summary(
        self,
        failures: list["TestFailure"],
        summary_failures: list[dict[str, str]],
    ) -> None:
        """Create TestFailure objects from summary when no failures exist.

        Args:
            failures: List to append new TestFailure objects to
            summary_failures: Parsed summary data
        """
        from crackerjack.models.test_models import TestFailure

        for summary_failure in summary_failures:
            error_message = summary_failure["error_message"]
            status = self._determine_failure_status(error_message)

            failures.append(
                TestFailure(
                    test_name=summary_failure["test_path"],
                    status=status,
                    location=summary_failure["test_path"],
                    assertion=error_message,
                )
            )

    def _enrich_existing_failures(
        self,
        failures: list["TestFailure"],
        summary_failures: list[dict[str, str]],
    ) -> None:
        """Enrich existing failure objects with summary data.

        Args:
            failures: List of existing TestFailure objects
            summary_failures: Parsed summary data to enrich with
        """
        for summary_failure in summary_failures:
            test_path = summary_failure["test_path"]
            error_message = summary_failure["error_message"]
            status = self._determine_failure_status(error_message)

            # Try to match by test name
            if self._try_enrich_named_failure(failures, test_path, error_message, status):
                continue

            # Try to enrich unnamed failure
            self._try_enrich_unnamed_failure(failures, test_path, error_message, status)

    def _try_enrich_named_failure(
        self,
        failures: list["TestFailure"],
        test_path: str,
        error_message: str,
        status: str,
    ) -> bool:
        """Try to enrich a named failure with summary data.

        Args:
            failures: List of TestFailure objects
            test_path: Test identifier
            error_message: Error message from summary
            status: Determined status (ERROR or FAILED)

        Returns:
            True if failure was matched and enriched
        """
        for failure in failures:
            if failure.test_name == test_path:
                if not failure.assertion:
                    failure.assertion = error_message
                failure.status = status
                return True
        return False

    def _try_enrich_unnamed_failure(
        self,
        failures: list["TestFailure"],
        test_path: str,
        error_message: str,
        status: str,
    ) -> bool:
        """Try to enrich an unnamed failure with summary data.

        Args:
            failures: List of TestFailure objects
            test_path: Test identifier to assign
            error_message: Error message from summary
            status: Determined status (ERROR or FAILED)

        Returns:
            True if failure was matched and enriched
        """
        unnamed_values = ("", "unknown", "N/A")

        for failure in failures:
            if not failure.test_name or failure.test_name in unnamed_values:
                failure.test_name = test_path
                if not failure.assertion:
                    failure.assertion = error_message
                failure.status = status
                return True
        return False

    def _match_unnamed_failures(
        self,
        failures: list["TestFailure"],
        summary_failures: list[dict[str, str]],
    ) -> None:
        """Match unnamed failures to summary entries by position.

        Args:
            failures: List of TestFailure objects
            summary_failures: Parsed summary data
        """
        unnamed_values = ("", "unknown", "N/A")
        unnamed_failures = [
            f for f in failures
            if not f.test_name or f.test_name in unnamed_values
        ]

        if not unnamed_failures or len(unnamed_failures) > len(summary_failures):
            return

        for i, failure in enumerate(unnamed_failures):
            if i < len(summary_failures):
                failure.test_name = summary_failures[i]["test_path"]
                error_message = summary_failures[i]["error_message"]

                if not failure.assertion:
                    failure.assertion = error_message

                failure.status = self._determine_failure_status(error_message)

    def _parse_failure_line(
        self,
        line: str,
        lines: list[str],
        index: int,
        current_failure: "TestFailure | None",
        in_traceback: bool,
        in_captured: bool,
        capture_type: str | None,
    ) -> dict[str, t.Any]:
        result: dict[str, t.Any] = {}


        if "short test summary" in line.lower():
            result["stop_parsing"] = True
            return result


        new_failure, header_found = self._parse_failure_header(line, current_failure)
        if header_found:
            result["new_failure"] = new_failure
            return result

        if not current_failure:
            result["skip_line"] = True
            return result


        is_captured, new_capture_type = self._parse_captured_section_header(line)
        if is_captured:
            result["in_captured"] = True
            result["capture_type"] = new_capture_type
            result["in_traceback"] = False
            return result


        if in_captured and capture_type:
            in_captured = self._parse_captured_output(line, capture_type, current_failure)
            result["in_captured"] = in_captured
            if not in_captured:
                result["capture_type"] = None
            return result

        if in_traceback:
            in_traceback = self._parse_traceback_line(line, lines, index, current_failure)
            result["in_traceback"] = in_traceback
            return result


        if self._parse_location_and_assertion(line, current_failure, in_traceback):
            result["skip_line"] = True
            return result

        return result

    def _render_structured_failure_panels(self, failures: list["TestFailure"]) -> None:

        if not failures:
            return


        first_status = failures[0].status
        if first_status == "FAILED":
            title = f"❌ Failed Tests ({len(failures)} total)"
            style = "red"
        elif first_status == "ERROR":
            title = f"💥 Errored Tests ({len(failures)} total)"
            style = "bright_red"
        elif first_status == "SKIPPED":
            title = f"⏭ Skipped Tests ({len(failures)} total)"
            style = "yellow"
        else:
            title = f"❓ Test Issues ({len(failures)} total)"
            style = "white"


        console_width = get_console_width()
        self.console.print()
        self.console.print(f"[bold {style}]{'━' * console_width}[/bold {style}]")
        self.console.print(f"[bold {style}]{title}[/bold {style}]")
        self.console.print(f"[bold {style}]{'━' * console_width}[/bold {style}]")
        self.console.print()


        for failure in failures:

            print(f"• {failure.test_name}")

            if failure.location and failure.location != failure.test_name:
                print(f" → {failure.location}")
            print(f" Status: {failure.status}")
            if failure.short_summary:
                print(f" {failure.short_summary}")
            elif failure.assertion:
                first_line = failure.assertion.split("\n")[0]
                print(f" {first_line}")
            print()

    def _build_simple_failure_list(self, failures: list["TestFailure"]) -> str:
        lines = []

        for i, failure in enumerate(failures, 1):

            lines.append(f"[bold cyan]• {failure.test_name}[/bold cyan]")
            if failure.location and failure.location != failure.test_name:
                lines.append(f"[dim] → {failure.location}[/dim]")


            lines.append(f"[red] Status: {failure.status}[/red]")


            if failure.short_summary:
                lines.append(f"[yellow] {failure.short_summary}[/yellow]")
            elif failure.assertion:

                first_line = failure.assertion.split("\n")[0]
                if len(first_line) > 100:
                    first_line = first_line[:97] + "..."
                lines.append(f"[yellow] {first_line}[/yellow]")

        return "\n".join(lines)

    def _group_failures_by_file(
        self, failures: list["TestFailure"]
    ) -> dict[str, list["TestFailure"]]:
        failures_by_file: dict[str, list[TestFailure]] = {}
        for failure in failures:
            file_path = failure.get_file_path()
            if file_path not in failures_by_file:
                failures_by_file[file_path] = []
            failures_by_file[file_path].append(failure)
        return failures_by_file

    def _render_file_failure_header(
        self, file_path: str, file_failures: list["TestFailure"]
    ) -> None:
        self.console.print(
            f"\n[bold red]📁 {file_path}[/bold red] ({len(file_failures)} failure(s))\n"
        )

    def _render_single_failure_panel(
        self, failure: "TestFailure", index: int, total: int
    ) -> None:
        from rich.console import Group
        from rich.panel import Panel


        table = self._create_failure_details_table(failure)


        components = self._build_failure_components(failure, table)


        group = Group(*components)
        panel = Panel(
            group,
            title=f"[bold red]❌ Failure {index}/{total}[/bold red]",
            border_style="red",
            width=get_console_width(),
            padding=(1, 2),
        )
        self.console.print(panel)

    def _create_failure_details_table(self, failure: "TestFailure") -> "Table":
        from rich import box
        from rich.table import Table

        table = Table(
            show_header=False,
            box=box.SIMPLE,
            padding=(0, 1),
            border_style="red",
        )
        table.add_column("Key", style="cyan bold", width=12)
        table.add_column("Value", overflow="fold")


        table.add_row("Test", f"[yellow]{failure.test_name}[/yellow]")
        table.add_row(
            "Location", f"[blue underline]{failure.location}[/blue underline]"
        )
        table.add_row("Status", f"[red bold]{failure.status}[/red bold]")

        if failure.duration:
            table.add_row("Duration", f"{failure.duration:.3f}s")


        duration_note = self._get_duration_note(failure)
        if duration_note:
            table.add_row("Timing", duration_note)

        return table

    def _build_failure_components(
        self, failure: "TestFailure", table: "Table"
    ) -> list[t.Any]:
        from rich.syntax import Syntax

        components: list[t.Any] = [table]


        if failure.assertion:
            components.extend(("", "[bold red]Assertion Error:[/bold red]"))
            assertion_syntax = Syntax(
                failure.assertion,
                "python",
                theme="monokai",
                line_numbers=False,
                background_color="default",
            )
            components.append(assertion_syntax)


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


        if failure.captured_stdout:
            components.extend(("", "[bold yellow]Captured stdout:[/bold yellow]"))
            components.append(f"[dim]{failure.captured_stdout}[/dim]")

        if failure.captured_stderr:
            components.extend(("", "[bold yellow]Captured stderr:[/bold yellow]"))
            components.append(f"[dim]{failure.captured_stderr}[/dim]")

        return components

    def _get_duration_note(self, failure: "TestFailure") -> str | None:
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
        if not self.use_lsp_diagnostics or self._lsp_client is None:
            return True

        try:

            lsp_client = self._lsp_client


            if not lsp_client.is_server_running():
                return True


            diagnostics, summary = lsp_client.check_project_with_feedback(
                self.pkg_path,
                show_progress=False,
            )


            has_errors = any(diags for diags in diagnostics.values())

            if has_errors:
                self.console.print(
                    "[yellow]⚠️ LSP detected type errors before running tests[/yellow]"
                )

                error_count = sum(len(diags) for diags in diagnostics.values())
                self.console.print(f"[yellow]Found {error_count} type issues[/yellow]")

            return not has_errors

        except Exception as e:

            self.console.print(f"[dim]LSP diagnostics failed: {e}[/dim]")
            return True

    def configure_lsp_diagnostics(self, enable: bool) -> None:
        self.use_lsp_diagnostics = enable

        if enable:
            self.console.print(
                "[cyan]🔍 LSP diagnostics enabled for faster test feedback[/cyan]"
            )

TestManagementImpl = TestManager
