import os
import subprocess
import time
import typing as t
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from crackerjack.config.hooks import HookDefinition, HookStrategy, RetryPolicy
from crackerjack.models.task import HookResult


@dataclass
class HookExecutionResult:
    strategy_name: str
    results: list[HookResult]
    total_duration: float
    success: bool
    concurrent_execution: bool = False
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "passed")

    @property
    def cache_hit_rate(self) -> float:
        total_requests = self.cache_hits + self.cache_misses
        return (self.cache_hits / total_requests * 100) if total_requests > 0 else 0.0

    @property
    def performance_summary(self) -> dict[str, t.Any]:
        return {
            "total_hooks": len(self.results),
            "passed": self.passed_count,
            "failed": self.failed_count,
            "duration_seconds": round(self.total_duration, 2),
            "concurrent": self.concurrent_execution,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate_percent": round(self.cache_hit_rate, 1),
        }


class HookExecutor:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        verbose: bool = False,
        quiet: bool = False,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.verbose = verbose
        self.quiet = quiet

    def execute_strategy(self, strategy: HookStrategy) -> HookExecutionResult:
        start_time = time.time()

        self._print_strategy_header(strategy)

        if strategy.parallel and len(strategy.hooks) > 1:
            results = self._execute_parallel(strategy)
        else:
            results = self._execute_sequential(strategy)

        if strategy.retry_policy != RetryPolicy.NONE:
            results = self._handle_retries(strategy, results)

        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in results)

        if not self.quiet:
            self._print_summary(strategy, results, success)

        return HookExecutionResult(
            strategy_name=strategy.name,
            results=results,
            total_duration=total_duration,
            success=success,
        )

    def _print_strategy_header(self, strategy: HookStrategy) -> None:
        self.console.print("\n" + "-" * 80)
        if strategy.name == "fast":
            self.console.print(
                "[bold bright_cyan]🔍 HOOKS[/bold bright_cyan] [bold bright_white]Running code quality checks[/bold bright_white]",
            )
        elif strategy.name == "comprehensive":
            self.console.print(
                "[bold bright_cyan]🔍 HOOKS[/bold bright_cyan] [bold bright_white]Running comprehensive quality checks[/bold bright_white]",
            )
        else:
            self.console.print(
                f"[bold bright_cyan]🔍 HOOKS[/bold bright_cyan] [bold bright_white]Running {strategy.name} hooks[/bold bright_white]",
            )
        self.console.print("-" * 80 + "\n")

    def _execute_sequential(self, strategy: HookStrategy) -> list[HookResult]:
        results: list[HookResult] = []
        for hook in strategy.hooks:
            result = self.execute_single_hook(hook)
            results.append(result)
            self._display_hook_result(result)
        return results

    def _execute_parallel(self, strategy: HookStrategy) -> list[HookResult]:
        results: list[HookResult] = []

        formatting_hooks = [h for h in strategy.hooks if h.is_formatting]
        other_hooks = [h for h in strategy.hooks if not h.is_formatting]

        for hook in formatting_hooks:
            result = self.execute_single_hook(hook)
            results.append(result)
            self._display_hook_result(result)

        if other_hooks:
            with ThreadPoolExecutor(max_workers=strategy.max_workers) as executor:
                future_to_hook = {
                    executor.submit(self.execute_single_hook, hook): hook
                    for hook in other_hooks
                }

                for future in as_completed(future_to_hook):
                    try:
                        result = future.result()
                        results.append(result)
                        self._display_hook_result(result)
                    except Exception as e:
                        hook = future_to_hook[future]
                        error_result = HookResult(
                            id=hook.name,
                            name=hook.name,
                            status="error",
                            duration=0.0,
                            issues_found=[str(e)],
                            stage=hook.stage.value,
                        )
                        results.append(error_result)
                        self._display_hook_result(error_result)

        return results

    def execute_single_hook(self, hook: HookDefinition) -> HookResult:
        start_time = time.time()

        try:
            result = self._run_hook_subprocess(hook)
            duration = time.time() - start_time

            self._display_hook_output_if_needed(result)
            return self._create_hook_result_from_process(hook, result, duration)

        except subprocess.TimeoutExpired:
            return self._create_timeout_result(hook, start_time)

        except Exception as e:
            return self._create_error_result(hook, start_time, e)

    def _run_hook_subprocess(
        self, hook: HookDefinition
    ) -> subprocess.CompletedProcess[str]:
        """Execute hook subprocess with clean environment."""
        clean_env = self._get_clean_environment()
        return subprocess.run(
            hook.get_command(),
            check=False,
            cwd=self.pkg_path,
            text=True,
            timeout=hook.timeout,
            env=clean_env,
            capture_output=True,
        )

    def _display_hook_output_if_needed(
        self, result: subprocess.CompletedProcess[str]
    ) -> None:
        """Display hook output in verbose mode for failed hooks."""
        if result.returncode == 0 or not self.verbose:
            return

        if result.stdout:
            self.console.print(result.stdout)
        if result.stderr:
            self.console.print(result.stderr)

    def _create_hook_result_from_process(
        self,
        hook: HookDefinition,
        result: subprocess.CompletedProcess[str],
        duration: float,
    ) -> HookResult:
        """Create HookResult from successful subprocess execution."""
        status = "passed" if result.returncode == 0 else "failed"
        issues_found = self._extract_issues_from_process_output(result)

        return HookResult(
            id=hook.name,
            name=hook.name,
            status=status,
            duration=duration,
            files_processed=0,
            issues_found=issues_found,
            stage=hook.stage.value,
        )

    def _extract_issues_from_process_output(
        self, result: subprocess.CompletedProcess[str]
    ) -> list[str]:
        """Extract specific issues from subprocess output for failed hooks."""
        if result.returncode == 0:
            return []

        error_output = (result.stdout + result.stderr).strip()
        if error_output:
            return [line.strip() for line in error_output.split("\n") if line.strip()]

        # Fallback to generic message if no output captured
        return [f"Hook failed with code {result.returncode}"]

    def _create_timeout_result(
        self, hook: HookDefinition, start_time: float
    ) -> HookResult:
        """Create HookResult for timeout scenarios."""
        duration = time.time() - start_time
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="timeout",
            duration=duration,
            issues_found=[f"Hook timed out after {duration:.1f}s"],
            stage=hook.stage.value,
        )

    def _create_error_result(
        self, hook: HookDefinition, start_time: float, error: Exception
    ) -> HookResult:
        """Create HookResult for general exception scenarios."""
        duration = time.time() - start_time
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="error",
            duration=duration,
            issues_found=[str(error)],
            stage=hook.stage.value,
        )

    def _parse_hook_output(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> dict[str, t.Any]:
        output = result.stdout + result.stderr
        return {
            "hook_id": None,
            "exit_code": result.returncode,
            "files_processed": 0,
            "issues": [],
            "raw_output": output,
        }

    def _display_hook_result(self, result: HookResult) -> None:
        status_icon = "✅" if result.status == "passed" else "❌"

        # Create dot-filled line like classic pre-commit format
        max_width = 70  # Leave room for terminal margins

        if len(result.name) > max_width:
            # Truncate long names
            line = result.name[: max_width - 3] + "..."
        else:
            # Fill with dots to reach max width
            dots_needed = max_width - len(result.name)
            line = result.name + ("." * dots_needed)

        self.console.print(f"{line} {status_icon}")

    def _handle_retries(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> list[HookResult]:
        if strategy.retry_policy == RetryPolicy.FORMATTING_ONLY:
            return self._retry_formatting_hooks(strategy, results)
        if strategy.retry_policy == RetryPolicy.ALL_HOOKS:
            return self._retry_all_hooks(strategy, results)
        return results

    def _retry_formatting_hooks(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> list[HookResult]:
        formatting_hooks_failed: set[str] = set()

        for i, result in enumerate(results):
            hook = strategy.hooks[i]
            if hook.is_formatting and result.status == "failed":
                formatting_hooks_failed.add(hook.name)

        if not formatting_hooks_failed:
            return results

        updated_results: list[HookResult] = []
        for i, hook in enumerate(strategy.hooks):
            prev_result = results[i]
            new_result = self.execute_single_hook(hook)

            new_result.duration += prev_result.duration
            updated_results.append(new_result)
            self._display_hook_result(new_result)

        return updated_results

    def _retry_all_hooks(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> list[HookResult]:
        failed_hooks = [i for i, r in enumerate(results) if r.status == "failed"]

        if not failed_hooks:
            return results

        updated_results: list[HookResult] = results.copy()
        for i in failed_hooks:
            hook = strategy.hooks[i]
            prev_result = results[i]
            new_result = self.execute_single_hook(hook)

            new_result.duration += prev_result.duration
            updated_results[i] = new_result
            self._display_hook_result(new_result)

        return updated_results

    def _get_clean_environment(self) -> dict[str, str]:
        clean_env = {
            "HOME": os.environ.get("HOME", ""),
            "USER": os.environ.get("USER", ""),
            "SHELL": os.environ.get("SHELL", "/bin/bash"),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "TERM": os.environ.get("TERM", "xterm-256color"),
        }

        system_path = os.environ.get("PATH", "")
        if system_path:
            venv_bin = str(Path(self.pkg_path) / ".venv" / "bin")
            path_parts = [p for p in system_path.split(":") if p != venv_bin]
            clean_env["PATH"] = ":".join(path_parts)

        python_vars_to_exclude = {
            "VIRTUAL_ENV",
            "PYTHONPATH",
            "PYTHON_PATH",
            "PIP_CONFIG_FILE",
            "PYTHONHOME",
            "CONDA_DEFAULT_ENV",
        }

        for key, value in os.environ.items():
            if key not in python_vars_to_exclude and key not in clean_env:
                if not key.startswith(("PYTHON", "PIP_", "CONDA_", "VIRTUAL_")):
                    clean_env[key] = value

        return clean_env

    def _print_summary(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
        success: bool,
    ) -> None:
        if success:
            self.console.print(
                f"[green]✅[/green] {strategy.name.title()} hooks passed: {len(results)} / {len(results)}",
            )
        else:
            failed_count = sum(1 for r in results if r.status == "failed")
            error_count = sum(1 for r in results if r.status in ("timeout", "error"))
            self.console.print(
                f"[red]❌[/red] {strategy.name.title()} hooks failed: {failed_count} failed, {error_count} errors",
            )
