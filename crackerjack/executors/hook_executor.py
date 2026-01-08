import json
import os
import subprocess
import time
import typing as t
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from crackerjack.config import get_console_width
from crackerjack.config.hooks import HookDefinition, HookStrategy, RetryPolicy
from crackerjack.models.task import HookResult
from crackerjack.services.security_logger import get_security_logger


@dataclass
class HookExecutionResult:
    strategy_name: str
    results: list[HookResult]
    total_duration: float
    success: bool
    concurrent_execution: bool = False
    cache_hits: int = 0
    cache_misses: int = 0
    performance_gain: float = 0.0

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
        debug: bool = False,
        use_incremental: bool = False,
        git_service: t.Any | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.verbose = verbose
        self.quiet = quiet
        self.debug = debug
        self.use_incremental = use_incremental
        self.git_service = git_service

        self._progress_callback: t.Callable[[int, int], None] | None = None
        self._progress_start_callback: t.Callable[[int, int], None] | None = None
        self._total_hooks: int = 0
        self._started_hooks: int = 0
        self._completed_hooks: int = 0

    def set_progress_callbacks(
        self,
        *,
        started_cb: t.Callable[[int, int], None] | None = None,
        completed_cb: t.Callable[[int, int], None] | None = None,
        total: int | None = None,
    ) -> None:
        self._progress_start_callback = started_cb
        self._progress_callback = completed_cb
        self._total_hooks = int(total or 0)
        self._started_hooks = 0
        self._completed_hooks = 0

    def execute_strategy(self, strategy: HookStrategy) -> HookExecutionResult:
        start_time = time.time()

        results = self._execute_hooks(strategy)

        results = self._apply_retries_if_needed(strategy, results)

        return self._create_execution_result(strategy, results, start_time)

    def _execute_hooks(self, strategy: HookStrategy) -> list[HookResult]:
        if strategy.parallel and len(strategy.hooks) > 1:
            return self._execute_parallel(strategy)
        return self._execute_sequential(strategy)

    def _apply_retries_if_needed(
        self, strategy: HookStrategy, results: list[HookResult]
    ) -> list[HookResult]:
        if strategy.retry_policy != RetryPolicy.NONE:
            return self._handle_retries(strategy, results)
        return results

    def _create_execution_result(
        self, strategy: HookStrategy, results: list[HookResult], start_time: float
    ) -> HookExecutionResult:
        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in results)

        performance_gain = self._calculate_performance_gain(
            strategy, results, total_duration
        )

        if not self.quiet:
            self._print_summary(strategy, results, success, performance_gain)

        return HookExecutionResult(
            strategy_name=strategy.name,
            results=results,
            total_duration=total_duration,
            success=success,
            performance_gain=performance_gain,
        )

    def _calculate_performance_gain(
        self, strategy: HookStrategy, results: list[HookResult], total_duration: float
    ) -> float:
        estimated_sequential = sum(
            getattr(hook, "timeout", 30) for hook in strategy.hooks
        )
        return (
            max(
                0,
                ((estimated_sequential - total_duration) / estimated_sequential) * 100,
            )
            if estimated_sequential > 0
            else 0.0
        )

    def _print_strategy_header(self, strategy: HookStrategy) -> None:
        return None

    def _execute_sequential(self, strategy: HookStrategy) -> list[HookResult]:
        results: list[HookResult] = []
        total_hooks = len(strategy.hooks)

        for hook in strategy.hooks:
            self._handle_progress_start(total_hooks)
            result = self.execute_single_hook(hook)
            results.append(result)
            self._display_hook_result(result)
            self._handle_progress_completion(total_hooks)
        return results

    def _handle_progress_start(self, total_hooks: int) -> None:
        if self._progress_start_callback:
            with suppress(Exception):
                self._started_hooks += 1
                total = self._total_hooks or total_hooks
                self._progress_start_callback(self._started_hooks, total)

    def _handle_progress_completion(self, total_hooks: int) -> None:
        if self._progress_callback:
            with suppress(Exception):
                self._completed_hooks += 1
                total = self._total_hooks or total_hooks
                self._progress_callback(self._completed_hooks, total)

    def _execute_parallel(self, strategy: HookStrategy) -> list[HookResult]:
        results: list[HookResult] = []

        formatting_hooks = [h for h in strategy.hooks if h.is_formatting]
        other_hooks = [h for h in strategy.hooks if not h.is_formatting]

        for hook in formatting_hooks:
            self._execute_single_hook_with_progress(hook, results)

        if other_hooks:
            self._execute_parallel_hooks(other_hooks, strategy, results)

        return results

    def _execute_single_hook_with_progress(
        self, hook: HookDefinition, results: list[HookResult]
    ) -> None:
        if self._progress_start_callback:
            with suppress(Exception):
                self._started_hooks += 1
                total = self._total_hooks or len(results) + 1
                self._progress_start_callback(self._started_hooks, total)

        result = self.execute_single_hook(hook)
        results.append(result)
        self._display_hook_result(result)

        if self._progress_callback:
            with suppress(Exception):
                self._completed_hooks += 1
                total = self._total_hooks or len(results)
                self._progress_callback(self._completed_hooks, total)

    def _execute_parallel_hooks(
        self,
        other_hooks: list[HookDefinition],
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> None:
        run_hook_func = self._create_run_hook_func(results, other_hooks)

        with ThreadPoolExecutor(max_workers=strategy.max_workers) as executor:
            future_to_hook = {
                executor.submit(run_hook_func, hook): hook for hook in other_hooks
            }

            for future in as_completed(future_to_hook):
                self._handle_future_result(future, future_to_hook, results)

    def _create_run_hook_func(
        self, results: list[HookResult], other_hooks: list[HookDefinition]
    ) -> t.Callable[[HookDefinition], HookResult]:
        def _run_with_start(h: HookDefinition) -> HookResult:
            if self._progress_start_callback:
                with suppress(Exception):
                    self._started_hooks += 1
                    total_local = self._total_hooks or len(results) + len(other_hooks)
                    self._progress_start_callback(self._started_hooks, total_local)
            return self.execute_single_hook(h)

        return _run_with_start

    def _handle_future_result(
        self, future, future_to_hook: dict, results: list[HookResult]
    ) -> None:
        try:
            result = future.result()
            results.append(result)
            self._display_hook_result(result)
            self._update_progress_on_completion()
        except Exception as e:
            hook = future_to_hook[future]
            error_result = HookResult(
                id=hook.name,
                name=hook.name,
                status="error",
                duration=0.0,
                issues_found=[str(e)],
                issues_count=1,
                stage=hook.stage.value,
                exit_code=1,
                error_message=str(e),
                is_timeout=False,
            )
            results.append(error_result)
            self._display_hook_result(error_result)
            self._update_progress_on_completion()

    def _update_progress_on_completion(self) -> None:
        if self._progress_callback:
            with suppress(Exception):
                self._completed_hooks += 1
                total = self._total_hooks or self._completed_hooks
                self._progress_callback(self._completed_hooks, total)

    def execute_single_hook(self, hook: HookDefinition) -> HookResult:
        start_time = time.time()

        try:
            result = self._run_hook_subprocess(hook)
            duration = time.time() - start_time

            self._display_hook_output_if_needed(result, hook.name)
            return self._create_hook_result_from_process(hook, result, duration)

        except subprocess.TimeoutExpired:
            return self._create_timeout_result(hook, start_time)

        except Exception as e:
            return self._create_error_result(hook, start_time, e)

    def _get_changed_files_for_hook(self, hook: HookDefinition) -> list[Path] | None:
        if not self.use_incremental or not hook.accepts_file_paths:
            return None

        if not self.git_service:
            return None

        extension_map = {
            "ruff-check": [".py"],
            "ruff-format": [".py"],
            "mdformat": [".md"],
            "refurb": [".py"],
            "skylos": [".py"],
            "complexipy": [".py"],
            "semgrep": [".py"],
            "check-yaml": [".yaml", ".yml"],
            "check-toml": [".toml"],
            "check-json": [".json"],
            "check-ast": [".py"],
            "format-json": [".json"],
            "codespell": [".py", ".md", ".txt", ".rst"],
            "check-jsonschema": [".json", ".yaml", ".yml"],
            "trailing-whitespace": [""],
            "end-of-file-fixer": [""],
        }

        extensions = extension_map.get(hook.name)
        if not extensions:
            return None

        changed_files = self.git_service.get_changed_files_by_extension(extensions)

        return changed_files or None

    def _run_hook_subprocess(
        self, hook: HookDefinition
    ) -> subprocess.CompletedProcess[str]:
        clean_env = self._get_clean_environment()

        try:
            repo_root = self.pkg_path

            changed_files = self._get_changed_files_for_hook(hook)

            command = (
                hook.build_command(changed_files)
                if changed_files
                else hook.get_command()
            )

            if hook.timeout > 120:
                return self._run_with_monitoring(command, hook, repo_root, clean_env)

            return subprocess.run(
                command,
                cwd=repo_root,
                env=clean_env,
                timeout=hook.timeout,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e:
            security_logger = get_security_logger()
            security_logger.log_subprocess_failure(
                command=hook.get_command(),
                exit_code=-1,
                error_output=str(e),
            )

            return subprocess.CompletedProcess(
                args=hook.get_command(), returncode=1, stdout="", stderr=str(e)
            )

    def _run_with_monitoring(
        self,
        command: list[str],
        hook: HookDefinition,
        cwd: Path,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        from crackerjack.executors.process_monitor import (
            ProcessMetrics,
            ProcessMonitor,
        )

        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        monitor = ProcessMonitor(
            check_interval=30.0,
            cpu_threshold=0.1,
            stall_timeout=180.0,
        )

        def on_stall(hook_name: str, metrics: ProcessMetrics) -> None:
            self.console.print(
                f"[yellow]⚠️ {hook_name} may be hung "
                f"(CPU < 0.1% for 3+ min, elapsed: {metrics.elapsed_seconds:.1f}s)[/yellow]"
            )

        monitor.monitor_process(process, hook.name, hook.timeout, on_stall)

        try:
            stdout, stderr = process.communicate(timeout=hook.timeout)
            returncode = process.returncode

            return subprocess.CompletedProcess(
                args=command,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise

        finally:
            monitor.stop_monitoring()

    def _display_hook_output_if_needed(
        self, result: subprocess.CompletedProcess[str], hook_name: str = ""
    ) -> None:
        if hook_name == "complexipy" and not self.debug:
            return

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
        status = self._determine_initial_status(hook, result)

        issues_found = self._extract_issues_from_process_output(hook, result, status)

        status = self._update_status_for_reporting_tools(
            hook, status, issues_found, result
        )

        parsed_output = self._parse_hook_output(result, hook.name)

        exit_code, error_message = self._determine_exit_code_and_error(status, result)

        issues_found = self._handle_no_issues_for_failed_hook(
            status, issues_found, result
        )

        issues_count = self._calculate_issues_count(status, issues_found)

        return HookResult(
            id=hook.name,
            name=hook.name,
            status=status,
            duration=duration,
            files_processed=parsed_output["files_processed"],
            issues_found=issues_found,
            issues_count=issues_count,
            stage=hook.stage.value,
            exit_code=exit_code,
            error_message=error_message,
            is_timeout=False,
        )

    def _determine_initial_status(
        self, hook: HookDefinition, result: subprocess.CompletedProcess[str]
    ) -> str:
        reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}

        if self.debug and hook.name in reporting_tools:
            self.console.print(
                f"[yellow]DEBUG _create_hook_result_from_process: hook={hook.name}, "
                f"returncode={result.returncode}[/yellow]"
            )

        if hook.is_formatting and result.returncode == 1:
            output_text = result.stdout + result.stderr
            if "files were modified by this hook" in output_text:
                return "passed"
            else:
                return "failed"
        else:
            return "passed" if result.returncode == 0 else "failed"

    def _update_status_for_reporting_tools(
        self,
        hook: HookDefinition,
        status: str,
        issues_found: list[str],
        result: subprocess.CompletedProcess[str] | None = None,
    ) -> str:
        reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}

        if hook.name in reporting_tools and issues_found:
            status = "failed"

        if hook.name in reporting_tools and self.debug and result:
            self.console.print(
                f"[yellow]DEBUG {hook.name}: returncode={result.returncode}, "
                f"issues={len(issues_found)}, status={status}[/yellow]"
            )

        return status

    def _determine_exit_code_and_error(
        self, status: str, result: subprocess.CompletedProcess[str]
    ) -> tuple[int | None, str | None]:
        exit_code = result.returncode if status == "failed" else None
        error_message = None
        if status == "failed" and result.stderr.strip():
            error_message = result.stderr.strip()[:500]
        return exit_code, error_message

    def _handle_no_issues_for_failed_hook(
        self,
        status: str,
        issues_found: list[str],
        result: subprocess.CompletedProcess[str],
    ) -> list[str]:
        if status == "failed" and not issues_found:
            output_text = (result.stdout + result.stderr).strip()
            if output_text:
                error_lines = [
                    line.strip() for line in output_text.split("\n") if line.strip()
                ][:10]
                issues_found = error_lines or ["Hook failed with non-zero exit code"]
        return issues_found

    def _calculate_issues_count(self, status: str, issues_found: list[str]) -> int:
        return max(len(issues_found), 1 if status == "failed" else 0)

    def _extract_issues_from_process_output(
        self,
        hook: HookDefinition,
        result: subprocess.CompletedProcess[str],
        status: str,
    ) -> list[str]:
        error_output = (result.stdout + result.stderr).strip()

        reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}

        if self.debug and hook.name in reporting_tools:
            self.console.print(
                f"[yellow]DEBUG _extract_issues: hook={hook.name}, status={status}, "
                f"output_len={len(error_output)}[/yellow]"
            )

        if hook.name == "semgrep":
            return self._parse_semgrep_issues(error_output)

        if hook.name in reporting_tools:
            return self._extract_issues_for_reporting_tools(hook, error_output)

        return self._extract_issues_for_regular_tools(
            hook, error_output, status, result
        )

    def _extract_issues_for_reporting_tools(
        self, hook: HookDefinition, error_output: str
    ) -> list[str]:
        if hook.name == "complexipy":
            return self._parse_complexipy_issues(error_output)
        if hook.name == "refurb":
            return self._parse_refurb_issues(error_output)
        if hook.name == "gitleaks":
            return self._parse_gitleaks_issues(error_output)
        if hook.name == "creosote":
            return self._parse_creosote_issues(error_output)
        return []

    def _extract_issues_for_regular_tools(
        self,
        hook: HookDefinition,
        error_output: str,
        status: str,
        result: subprocess.CompletedProcess[str],
    ) -> list[str]:
        if status == "passed":
            return []

        if hook.is_formatting and "files were modified by this hook" in error_output:
            return []

        if error_output:
            return [line.strip() for line in error_output.split("\n") if line.strip()]

        return [f"Hook failed with code {result.returncode}"]

    def _is_header_or_separator_line(self, line: str) -> bool:
        return any(x in line for x in ("Path", "─────", "┌", "└", "├", "┼", "┤", "┃"))

    def _extract_complexity_from_parts(self, parts: list[str]) -> int | None:
        if len(parts) >= 4:
            with suppress(ValueError, IndexError):
                return int(parts[-1])
        return None

    def _detect_package_from_output(self, output: str) -> str:
        import re
        from collections import Counter

        path_pattern = r"\./([a-z_][a-z0-9_]*)/[a-z_]"
        matches = re.findall(path_pattern, output, re.IGNORECASE)

        if matches:
            return Counter(matches).most_common(1)[0][0]

        from crackerjack.config.tool_commands import _detect_package_name_cached

        return _detect_package_name_cached(str(self.pkg_path))

    def _should_include_line(self, line: str, package_name: str) -> bool:
        return "│" in line and package_name in line

    def _parse_complexipy_issues(self, output: str) -> list[str]:
        package_name = self._detect_package_from_output(output)

        issues = []
        for line in output.split("\n"):
            if self._should_include_line(line, package_name):
                if not self._is_header_or_separator_line(line):
                    parts = [p.strip() for p in line.split("│") if p.strip()]
                    complexity = self._extract_complexity_from_parts(parts)

                    if complexity is not None and complexity > 15:
                        issues.append(line.strip())
        return issues

    def _parse_refurb_issues(self, output: str) -> list[str]:
        import re

        issues = []
        for line in output.split("\n"):
            if "[FURB" not in line or ":" not in line:
                continue

            match = re.search(
                r"(.+?):\s*(\d+):\s*\d+\s+\[(\w+)\]:\s*(.+)", line.strip()
            )

            if match:
                file_path, line_num, error_code, message = match.groups()

                short_path = self._shorten_path(file_path)

                formatted = f"{short_path}:{line_num} [{error_code}] {message.strip()}"
                issues.append(formatted)
            else:
                issues.append(line.strip())

        return issues

    def _shorten_path(self, path: str) -> str:
        try:
            file_path = Path(path)

            if file_path.is_absolute():
                try:
                    relative = file_path.relative_to(self.pkg_path)
                    return str(relative).replace("\\", "/")
                except ValueError:
                    return file_path.name

            clean_path = str(file_path).lstrip("./")
            return clean_path.replace("\\", "/")

        except Exception:
            return path

    def _parse_gitleaks_issues(self, output: str) -> list[str]:
        if "no leaks found" in output.lower():
            return []
        return [
            line.strip()
            for line in output.split("\n")
            if not ("WRN" in line and "Invalid .gitleaksignore" in line)
            and any(x in line.lower() for x in ("leak", "secret", "credential", "api"))
            and "found" not in line.lower()
        ]

    def _parse_creosote_issues(self, output: str) -> list[str]:
        if "No unused dependencies found" in output:
            return []
        issues = []
        parsing_unused = False
        for line in output.split("\n"):
            if "unused" in line.lower() and "dependenc" in line.lower():
                parsing_unused = True
                continue
            if parsing_unused and line.strip() and not line.strip().startswith("["):
                dep_name = line.strip().lstrip("- ")
                if dep_name:
                    issues.append(f"Unused dependency: {dep_name}")
            if not line.strip():
                parsing_unused = False
        return issues

    def _parse_semgrep_issues(self, output: str) -> list[str]:
        import json

        try:
            json_data = json.loads(output.strip())
            issues = []

            issues.extend(self._extract_semgrep_results(json_data))

            issues.extend(self._extract_semgrep_errors(json_data))

            return issues

        except json.JSONDecodeError:
            if output.strip():
                return [line.strip() for line in output.split("\n") if line.strip()][
                    :10
                ]

        return []

    def _extract_semgrep_results(self, json_data: dict) -> list[str]:
        issues = []
        for result in json_data.get("results", []):
            path = result.get("path", "unknown")
            line_num = result.get("start", {}).get("line", "?")
            rule_id = result.get("check_id", "unknown-rule")
            message = result.get("extra", {}).get("message", "Security issue detected")
            issues.append(f"{path}:{line_num} - {rule_id}: {message}")
        return issues

    def _extract_semgrep_errors(self, json_data: dict) -> list[str]:
        issues = []
        INFRA_ERROR_TYPES = {
            "NetworkError",
            "DownloadError",
            "TimeoutError",
            "ConnectionError",
            "HTTPError",
            "SSLError",
        }

        for error in json_data.get("errors", []):
            error_type = error.get("type", "SemgrepError")
            error_msg = error.get("message", str(error))

            if error_type in INFRA_ERROR_TYPES:
                self.console.print(
                    f"[yellow]Warning: Semgrep infrastructure error: "
                    f"{error_type}: {error_msg}[/yellow]"
                )
            else:
                issues.append(f"{error_type}: {error_msg}")
        return issues

    def _create_timeout_result(
        self, hook: HookDefinition, start_time: float
    ) -> HookResult:
        duration = time.time() - start_time
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="timeout",
            duration=duration,
            issues_found=[f"Hook timed out after {duration: .1f}s"],
            issues_count=1,
            stage=hook.stage.value,
            exit_code=124,
            error_message=f"Execution exceeded timeout of {duration:.1f}s",
            is_timeout=True,
        )

    def _create_error_result(
        self, hook: HookDefinition, start_time: float, error: Exception
    ) -> HookResult:
        duration = time.time() - start_time
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="error",
            duration=duration,
            issues_found=[str(error)],
            issues_count=1,
            stage=hook.stage.value,
            exit_code=1,
            error_message=str(error),
            is_timeout=False,
        )

    def _parse_hook_output(
        self,
        result: subprocess.CompletedProcess[str],
        hook_name: str = "",
    ) -> dict[str, t.Any]:
        output = result.stdout + result.stderr

        if hook_name == "semgrep":
            files_processed = self._parse_semgrep_output(result)
        else:
            files_processed = self._parse_generic_hook_output(output)

        return self._create_parse_result(files_processed, result.returncode, output)

    def _is_semgrep_output(self, output: str, args_str: str) -> bool:
        return "semgrep" in output.lower() or "semgrep" in args_str.lower()

    def _create_parse_result(
        self, files_processed: int, exit_code: int, output: str
    ) -> dict[str, t.Any]:
        return {
            "hook_id": None,
            "exit_code": exit_code,
            "files_processed": files_processed,
            "issues": [],
            "raw_output": output,
        }

    def _parse_semgrep_output(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> int:
        json_files = self._parse_semgrep_json_output(result)
        if json_files is not None and json_files >= 0:
            return json_files

        return self._parse_semgrep_text_output(result.stdout + result.stderr)

    def _parse_semgrep_json_output(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> int | None:
        output = result.stdout + result.stderr
        return self._process_output_for_json(output)

    def _process_output_for_json(self, output: str) -> int | None:
        lines = output.splitlines()
        for line in lines:
            result = self._try_parse_line_json(line)
            if result is not None:
                return result
        return None

    def _try_parse_line_json(self, line: str) -> int | None:
        line = line.strip()

        if self._is_pure_json(line):
            result = self._parse_json_line(line)
            if result is not None:
                return result

        if self._contains_json_results(line):
            result = self._parse_json_line(line)
            if result is not None:
                return result
        return None

    def _is_pure_json(self, line: str) -> bool:
        return line.startswith("{") and line.endswith("}")

    def _contains_json_results(self, line: str) -> bool:
        return '"results":' in line

    def _parse_json_line(self, line: str) -> int | None:
        try:
            json_data = json.loads(line)
            if "results" in json_data:
                file_paths = {
                    result.get("path") for result in json_data.get("results", [])
                }
                return len([p for p in file_paths if p])
        except json.JSONDecodeError:
            pass
        return None

    def _parse_semgrep_text_output(self, output: str) -> int:
        import re

        semgrep_patterns = [
            r"found\s+(\d+)\s+issues?\s+in\s+(\d+)\s+files?",
            r"found\s+no\s+issues",
            r"scanning\s+(\d+)\s+files?",
        ]

        for pattern in semgrep_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                result = self._process_matches(matches, output)
                if result != -1:
                    return result

        return 0

    def _process_matches(self, matches: list, output: str) -> int:
        for match in matches:
            if isinstance(match, tuple):
                if len(match) == 2:
                    return self._handle_issues_in_files_match(match)
                elif len(match) == 1 and "no issues" not in output.lower():
                    continue
            elif "no issues" in output.lower():
                return 0
        return -1

    def _handle_issues_in_files_match(self, match: tuple) -> int:
        issue_count, file_count = int(match[0]), int(match[1])

        return file_count if issue_count > 0 else 0

    def _parse_generic_hook_output(self, output: str) -> int:
        files_processed = 0

        if "files" in output.lower():
            files_processed = self._extract_file_count_from_patterns(output)

        if not files_processed and "ruff" in output.lower():
            files_processed = self._extract_file_count_for_ruff_like_tools(output)

        return files_processed

    def _extract_file_count_from_patterns(self, output: str) -> int:
        import re

        all_matches = []
        file_count_patterns = [
            r"(\d+)\s+files?\s+would\s+be",
            r"(\d+)\s+files?\s+already\s+formatted",
            r"(\d+)\s+files?\s+processed",
            r"(\d+)\s+files?\s+checked",
            r"(\d+)\s+files?\s+analyzed",
            r"Checking\s+(\d+)\s+files?",
            r"Found\s+(\d+)\s+files?",
            r"(\d+)\s+files?",
        ]
        for pattern in file_count_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                all_matches.extend([int(m) for m in matches if m.isdigit()])

        if all_matches:
            return max(all_matches)

        return 0

    def _extract_file_count_for_ruff_like_tools(self, output: str) -> int:
        import re

        all_passed_match = re.search(r"All\s+checks?\s+passed!", output, re.IGNORECASE)
        if all_passed_match:
            other_matches = re.findall(r"(\d+)\s+files?", output, re.IGNORECASE)
            if other_matches:
                all_matches = [int(m) for m in other_matches if m.isdigit()]
                if all_matches:
                    return max(all_matches)

        return 0

    def _display_hook_result(self, result: HookResult) -> None:
        if self.quiet:
            return
        status_icon = "✅" if result.status == "passed" else "❌"

        max_width = get_console_width()
        content_width = max_width - 4

        if len(result.name) > content_width:
            line = result.name[: content_width - 3] + "..."
        else:
            dots_needed = max(0, content_width - len(result.name))
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
        formatting_hooks_failed = self._find_failed_formatting_hooks(strategy, results)

        if not formatting_hooks_failed:
            return results

        return self._retry_all_formatting_hooks(strategy, results)

    def _find_failed_formatting_hooks(
        self, strategy: HookStrategy, results: list[HookResult]
    ) -> set[str]:
        formatting_hooks_failed: set[str] = set()

        for i, result in enumerate(results):
            hook = strategy.hooks[i]
            if hook.is_formatting and result.status == "failed":
                formatting_hooks_failed.add(hook.name)

        return formatting_hooks_failed

    def _retry_all_formatting_hooks(
        self, strategy: HookStrategy, results: list[HookResult]
    ) -> list[HookResult]:
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
        failed_hooks = self._find_failed_hooks(results)

        if not failed_hooks:
            return results

        return self._retry_failed_hooks(strategy, results, failed_hooks)

    def _find_failed_hooks(self, results: list[HookResult]) -> list[int]:
        return [i for i, r in enumerate(results) if r.status == "failed"]

    def _retry_failed_hooks(
        self, strategy: HookStrategy, results: list[HookResult], failed_hooks: list[int]
    ) -> list[HookResult]:
        updated_results: list[HookResult] = results.copy()
        for i in failed_hooks:
            self._retry_single_hook(strategy, results, updated_results, i)
        return updated_results

    def _retry_single_hook(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
        updated_results: list[HookResult],
        hook_idx: int,
    ) -> None:
        hook = strategy.hooks[hook_idx]
        prev_result = results[hook_idx]
        new_result = self.execute_single_hook(hook)

        new_result.duration += prev_result.duration
        updated_results[hook_idx] = new_result
        self._display_hook_result(new_result)

    def _get_clean_environment(self) -> dict[str, str]:
        clean_env = self._get_base_environment()

        self._update_path(clean_env)

        security_logger = get_security_logger()
        python_vars_to_exclude = self._get_python_vars_to_exclude()

        original_count = len(os.environ)
        filtered_count = 0

        for key, value in os.environ.items():
            if key not in python_vars_to_exclude and key not in clean_env:
                if not key.startswith(
                    ("PYTHON", "PIP_", "CONDA_", "VIRTUAL_", "__PYVENV")
                ):
                    if key not in {"LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "IFS", "PS4"}:
                        clean_env[key] = value
                    else:
                        filtered_count += 1
                        security_logger.log_environment_variable_filtered(
                            variable_name=key,
                            reason="dangerous environment variable",
                            value_preview=(value[:50] if value else "")[:50],
                        )
                else:
                    filtered_count += 1

        if filtered_count > 5:
            security_logger.log_subprocess_environment_sanitized(
                original_count=original_count,
                sanitized_count=len(clean_env),
                filtered_vars=[],
            )

        return clean_env

    def _get_base_environment(self) -> dict[str, str]:
        return {
            "HOME": os.environ.get("HOME", ""),
            "USER": os.environ.get("USER", ""),
            "SHELL": os.environ.get("SHELL", "/bin/bash"),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "TERM": os.environ.get("TERM", "xterm-256color"),
        }

    def _update_path(self, clean_env: dict[str, str]) -> None:
        system_path = os.environ.get("PATH", "")
        if system_path:
            venv_bin = str(Path(self.pkg_path) / ".venv" / "bin")
            path_parts = [p for p in system_path.split(os.pathsep) if p != venv_bin]
            clean_env["PATH"] = os.pathsep.join(path_parts)

    def _get_python_vars_to_exclude(self) -> set[str]:
        return {
            "VIRTUAL_ENV",
            "PYTHONPATH",
            "PYTHON_PATH",
            "PIP_CONFIG_FILE",
            "PYTHONHOME",
            "CONDA_DEFAULT_ENV",
            "PIPENV_ACTIVE",
            "POETRY_ACTIVE",
        }

    def _print_summary(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
        success: bool,
        performance_gain: float,
    ) -> None:
        if success:
            mode = "async" if self.is_concurrent(strategy) else "sequential"
            self.console.print(
                f"[green]✅[/green] {strategy.name.title()} hooks passed: {len(results)} / {len(results)} "
                f"({mode}, {performance_gain:.1f}% faster)",
            )

    def is_concurrent(self, strategy: HookStrategy) -> bool:
        return strategy.parallel and len(strategy.hooks) > 1
