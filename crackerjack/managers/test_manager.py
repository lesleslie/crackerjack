import subprocess
import time
import typing as t
from pathlib import Path

from rich.console import Console

from ..models.protocols import OptionsProtocol


class TestManagementImpl:
    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self._last_test_failures: list[str] = []

    def _run_test_command(
        self, cmd: list[str], timeout: int = 600
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
            cwd=self.pkg_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

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
        self._last_test_failures = []
        start_time = time.time()
        try:
            cmd = self._build_test_command(options)
            timeout = self._get_test_timeout(options)
            self._print_test_start_message(cmd, timeout, options)
            result = self._run_test_command(cmd, timeout=timeout + 60)
            duration = time.time() - start_time

            return self._process_test_results(result, duration)
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.console.print(f"[red]⏰[/red] Tests timed out after {duration:.1f}s")
            return False
        except Exception as e:
            duration = time.time() - start_time
            self.console.print(f"[red]💥[/red] Test execution failed: {e}")
            return False

    def _build_test_command(self, options: OptionsProtocol) -> list[str]:
        cmd = ["python", "-m", "pytest"]
        self._add_coverage_options(cmd, options)
        self._add_worker_options(cmd, options)
        self._add_benchmark_options(cmd, options)
        self._add_timeout_options(cmd, options)
        self._add_verbosity_options(cmd, options)
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
                "[cyan]📊[/cyan] Running in benchmark mode (no parallelization)"
            )
            cmd.append("--benchmark-only")

    def _add_timeout_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        timeout = self._get_test_timeout(options)
        cmd.extend(["--timeout", str(timeout)])

    def _add_verbosity_options(self, cmd: list[str], options: OptionsProtocol) -> None:
        if options.verbose:
            cmd.append("-v")

    def _add_test_path(self, cmd: list[str]) -> None:
        test_path = self.pkg_path / "tests"
        if test_path.exists():
            cmd.append(str(test_path))

    def _print_test_start_message(
        self, cmd: list[str], timeout: int, options: OptionsProtocol
    ) -> None:
        self.console.print(
            f"[yellow]🧪[/yellow] Running tests... (timeout: {timeout}s)"
        )
        if options.verbose:
            self.console.print(f"[dim]Command: {' '.join(cmd)}[/dim]")

    def _process_test_results(
        self, result: subprocess.CompletedProcess[str], duration: float
    ) -> bool:
        output = result.stdout + result.stderr
        if result.returncode == 0:
            return self._handle_test_success(output, duration)
        return self._handle_test_failure(output, duration)

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
                ["python", "-m", "coverage", "report", "--format=json"]
            )
            if result.returncode == 0:
                import json

                coverage_data = json.loads(result.stdout)

                return {
                    "total_coverage": coverage_data.get("totals", {}).get(
                        "percent_covered", 0
                    ),
                    "files": coverage_data.get("files", {}),
                    "summary": coverage_data.get("totals", {}),
                }
            else:
                self.console.print("[yellow]⚠️[/yellow] Could not get coverage data")
                return {}
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Error getting coverage: {e}")
            return {}

    def run_specific_tests(self, test_pattern: str) -> bool:
        try:
            cmd = ["python", "-m", "pytest", "-k", test_pattern, "-v"]
            self.console.print(
                f"[yellow]🎯[/yellow] Running tests matching: {test_pattern}"
            )
            result = self._run_test_command(cmd)
            if result.returncode == 0:
                self.console.print("[green]✅[/green] Specific tests passed")
                return True
            else:
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
                return f"Total coverage: {total} % "
            return None
        except Exception:
            return None

    def has_tests(self) -> bool:
        test_files = list(self.pkg_path.glob("tests/test_*.py"))
        return len(test_files) > 0
