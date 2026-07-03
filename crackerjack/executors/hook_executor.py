from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import typing as t
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from crackerjack.config import get_console_width
from crackerjack.config.hooks import HookDefinition, HookStrategy, RetryPolicy
from crackerjack.models.protocols import ConsoleInterface
from crackerjack.models.task import HookResult
from crackerjack.services.security_logger import get_security_logger
from crackerjack.utils.issue_detection import (
    extract_issue_lines,
)

logger = logging.getLogger(__name__)


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
    # Single source of truth for tools whose stdout/stderr needs a
    # dedicated parser rather than the loose ``extract_issue_lines``
    # fallback. Referenced from ``_determine_initial_status``,
    # ``_update_status_for_reporting_tools``, and
    # ``_extract_issues_from_process_output``. Adding ``ty`` here is
    # the fix for the parsing-leak bug where ``ty`` fell through to
    # ``_extract_issues_for_regular_tools`` and the user-visible
    # ``issues=N`` column counted the ratchet's structured summary
    # lines and the test-tail slice (24 in the oneiric repro) instead
    # of routing to ``_parse_ty_ratchet_issues``.
    _REPORTING_TOOLS: frozenset[str] = frozenset({
        "complexipy",
        "refurb",
        "pyscn",
        "gitleaks",
        "creosote",
        "pip-audit",
        "lychee",
        "ty",
    })

    def __init__(
        self,
        console: ConsoleInterface,
        pkg_path: Path,
        verbose: bool = False,
        quiet: bool = False,
        debug: bool = False,
        use_incremental: bool = False,
        git_service: t.Any | None = None,
        file_filter: t.Any | None = None,
        enable_hooks: list[str] | None = None,
        skip_offline_pip_audit: bool = True,
        adapter_learner_integration: t.Any | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.verbose = verbose
        self.quiet = quiet
        self.debug = debug
        self.use_incremental = use_incremental
        self.git_service = git_service
        self.file_filter = file_filter
        self.enable_hooks = set(enable_hooks) if enable_hooks else set()
        self.skip_offline_pip_audit = skip_offline_pip_audit
        self._adapter_learner_integration = adapter_learner_integration

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
        self,
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> list[HookResult]:
        if strategy.retry_policy != RetryPolicy.NONE:
            return self._handle_retries(strategy, results)
        return results

    def _create_execution_result(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
        start_time: float,
    ) -> HookExecutionResult:
        total_duration = time.time() - start_time
        success = all(r.status in ("passed", "skipped") for r in results)

        performance_gain = self._calculate_performance_gain(
            strategy,
            results,
            total_duration,
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
        self,
        strategy: HookStrategy,
        results: list[HookResult],
        total_duration: float,
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

        enabled_hooks = []
        skipped_hooks = []
        for h in strategy.hooks:
            if h.disabled and h.name not in self.enable_hooks:
                skipped_hooks.append(h)
            else:
                enabled_hooks.append(h)
                if h.disabled and h.name in self.enable_hooks:
                    if self.verbose:
                        self.console.print(
                            f"🔓 {h.name} force-enabled (was disabled: {h.run_schedule or 'manual'})"
                        )

        for hook in skipped_hooks:
            if self.verbose:
                schedule_info = (
                    f" (scheduled: {hook.run_schedule})" if hook.run_schedule else ""
                )
                self.console.print(
                    f"⏭️ {hook.name}.................................................. skipped{schedule_info}"
                )

        total_hooks = len(enabled_hooks)

        for hook in enabled_hooks:
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
        enabled_hooks, skipped_hooks = self._categorize_hooks(strategy)
        self._display_skipped_hooks(skipped_hooks)
        return self._run_hooks_by_type(enabled_hooks, strategy)

    def _categorize_hooks(
        self, strategy: HookStrategy
    ) -> tuple[list[HookDefinition], list[HookDefinition]]:
        enabled_hooks: list[HookDefinition] = []
        skipped_hooks: list[HookDefinition] = []
        for h in strategy.hooks:
            if h.disabled and h.name not in self.enable_hooks:
                skipped_hooks.append(h)
            else:
                enabled_hooks.append(h)
                self._log_force_enabled_hooks(h)
        return enabled_hooks, skipped_hooks

    def _log_force_enabled_hooks(self, hook: HookDefinition) -> None:
        if hook.disabled and hook.name in self.enable_hooks and self.verbose:
            self.console.print(
                f"🔓 {hook.name} force-enabled (was disabled: {hook.run_schedule or 'manual'})"
            )

    def _display_skipped_hooks(self, skipped_hooks: list[HookDefinition]) -> None:
        for hook in skipped_hooks:
            if self.verbose:
                schedule_info = (
                    f" (scheduled: {hook.run_schedule})" if hook.run_schedule else ""
                )
                self.console.print(
                    f"⏭️ {hook.name}.................................................. skipped{schedule_info}"
                )

    def _run_hooks_by_type(
        self, enabled_hooks: list[HookDefinition], strategy: HookStrategy
    ) -> list[HookResult]:
        results: list[HookResult] = []
        formatting_hooks = [h for h in enabled_hooks if h.is_formatting]
        other_hooks = [h for h in enabled_hooks if not h.is_formatting]

        for hook in formatting_hooks:
            self._execute_single_hook_with_progress(hook, results)

        if other_hooks:
            self._execute_parallel_hooks(other_hooks, strategy, results)

        return results

    def _execute_single_hook_with_progress(
        self,
        hook: HookDefinition,
        results: list[HookResult],
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
        self,
        results: list[HookResult],
        other_hooks: list[HookDefinition],
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
        self,
        future,
        future_to_hook: dict,
        results: list[HookResult],
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

        except subprocess.TimeoutExpired as e:
            partial_output = (e.stdout or b"").decode("utf-8", errors="ignore")
            partial_stderr = (e.stderr or b"").decode("utf-8", errors="ignore")
            return self._create_timeout_result(
                hook, start_time, partial_output, partial_stderr
            )

        except Exception as e:
            return self._create_error_result(hook, start_time, e)

    def _get_changed_files_for_hook(self, hook: HookDefinition) -> list[Path] | None:
        if not self.use_incremental or not hook.accepts_file_paths:
            return None

        if self.file_filter:
            with suppress(Exception):
                from crackerjack.services.file_filter import SmartFileFilter

                if isinstance(self.file_filter, SmartFileFilter):
                    all_changed_files = self.file_filter.get_files_for_qa_scan(
                        package_dir=self.pkg_path,
                        force_incremental=True,
                    )

                    filtered_files = self._filter_files_by_hook_type(
                        all_changed_files, hook.name
                    )

                    if filtered_files:
                        return filtered_files

        if not self.git_service:
            return None

        extension_map: dict[str, list[str]] = {
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

    def _filter_files_by_hook_type(
        self, files: list[Path], hook_name: str
    ) -> list[Path]:
        extension_map: dict[str, list[str]] = {
            "ruff-check": [".py"],
            "ruff-format": [".py"],
            "mdformat": [".md"],
            "check-yaml": [".yaml", ".yml"],
            "check-toml": [".toml"],
            "check-json": [".json"],
            "check-ast": [".py"],
            "format-json": [".json"],
            "codespell": [".py", ".md", ".txt", ".rst"],
            "trailing-whitespace": [],
            "end-of-file-fixer": [],
        }

        extensions = extension_map.get(hook_name, [])

        if not extensions:
            return files

        return [f for f in files if f.suffix in extensions]

    def _run_hook_subprocess(
        self,
        hook: HookDefinition,
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
                args=hook.get_command(),
                returncode=1,
                stdout="",
                stderr=str(e),
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
                f"(CPU < 0.1% for 3+ min, elapsed: {metrics.elapsed_seconds:.1f}s)[/yellow]",
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
        self,
        result: subprocess.CompletedProcess[str],
        hook_name: str = "",
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
        if self._should_skip_offline_pip_audit(hook, result):
            return self._create_skipped_hook_result(
                hook=hook,
                duration=duration,
                message="pip-audit skipped: network resolution unavailable",
                output=result.stdout,
                error=result.stderr,
            )

        status = self._determine_initial_status(hook, result)

        issues_found = self._extract_issues_from_process_output(hook, result, status)

        status = self._update_status_for_reporting_tools(
            hook,
            status,
            issues_found,
            result,
        )

        parsed_output = self._parse_hook_output(result, hook.name)

        exit_code, error_message = self._determine_exit_code_and_error(status, result)

        issues_found = self._handle_no_issues_for_failed_hook(
            status,
            issues_found,
            result,
        )

        issues_count = self._calculate_issues_count(status, issues_found)

        qa_result = self._try_get_qa_result_for_hook(hook, result, duration)

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
            output=result.stdout,
            error=result.stderr,
            advisory_issues=parsed_output.get("advisory_issues", []),
            qa_result=qa_result,
        )

    def _create_skipped_hook_result(
        self,
        *,
        hook: HookDefinition,
        duration: float,
        message: str,
        output: str,
        error: str,
    ) -> HookResult:
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="skipped",
            duration=duration,
            files_processed=0,
            issues_found=[],
            issues_count=0,
            stage=hook.stage.value,
            exit_code=None,
            error_message=message,
            is_timeout=False,
            output=output,
            error=error,
        )

    def _should_skip_offline_pip_audit(
        self,
        hook: HookDefinition,
        result: subprocess.CompletedProcess[str],
    ) -> bool:
        if (
            not self.skip_offline_pip_audit
            or hook.name != "pip-audit"
            or result.returncode == 0
        ):
            return False

        output = f"{result.stdout}\n{result.stderr}".lower()
        offline_markers = (
            "getaddrinfo",
            "temporary failure in name resolution",
            "name or service not known",
            "could not resolve host",
            "nodename nor servname provided",
            "network is unreachable",
            "connection refused",
            "connection aborted",
            "connection reset",
            "max retries exceeded",
            "failed to establish a new connection",
        )
        return any(marker in output for marker in offline_markers)

    def _determine_initial_status(
        self,
        hook: HookDefinition,
        result: subprocess.CompletedProcess[str],
    ) -> str:
        if self.debug and hook.name in self._REPORTING_TOOLS:
            self.console.print(
                f"[yellow]DEBUG _create_hook_result_from_process: hook={hook.name}, "
                f"returncode={result.returncode}[/yellow]",
            )

        if hook.name == "ruff-check" and result.returncode != 0:
            return "failed"

        if hook.is_formatting and result.returncode == 1:
            output_text = result.stdout + result.stderr
            if "files were modified by this hook" in output_text:
                return "passed"
            return "failed"
        return "passed" if result.returncode == 0 else "failed"

    def _update_status_for_reporting_tools(
        self,
        hook: HookDefinition,
        status: str,
        issues_found: list[str],
        result: subprocess.CompletedProcess[str] | None = None,
    ) -> str:
        # ty is excluded from the status-flip set because the ratchet's
        # prod gate already drives the exit code (see
        # crackerjack.tools.ty_ratchet: overall_exit is prod_gate). When
        # only the test gate fails, the ratchet returns 0 and the hook
        # is "passed" — the test-tail diagnostics are surfaced as
        # advisory only via the negative ``files_processed`` sentinel
        # and the warning banner in phase_coordinator. Flipping status
        # here would regress that documented contract.
        status_flipping_tools = self._REPORTING_TOOLS - {"ty"}

        if hook.name in status_flipping_tools and issues_found:
            status = "failed"

        if hook.name in self._REPORTING_TOOLS and self.debug and result:
            self.console.print(
                f"[yellow]DEBUG {hook.name}: returncode={result.returncode}, "
                f"issues={len(issues_found)}, status={status}[/yellow]",
            )

        return status

    def _determine_exit_code_and_error(
        self,
        status: str,
        result: subprocess.CompletedProcess[str],
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
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()

            for text in (stderr, stdout):
                if "Traceback (most recent call last):" in text:
                    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
                    exception_line = next(
                        (ln for ln in reversed(lines) if not ln.startswith("File ")),
                        "unknown error",
                    )
                    return [f"Tool crashed (infrastructure error): {exception_line}"]

            if stderr:
                error_lines = [
                    line.strip() for line in stderr.split("\n") if line.strip()
                ][:10]
                issues_found = error_lines
            elif stdout and not stdout.startswith(("{", "[")):
                error_lines = [
                    line.strip() for line in stdout.split("\n") if line.strip()
                ][:10]
                issues_found = error_lines
            else:
                issues_found = [
                    f"Hook exited with code {result.returncode} but reported no parseable issues"
                ]
        return issues_found

    def _calculate_issues_count(self, status: str, issues_found: list[str]) -> int:
        return len(issues_found)

    def _extract_issues_from_process_output(
        self,
        hook: HookDefinition,
        result: subprocess.CompletedProcess[str],
        status: str,
    ) -> list[str]:
        error_output = (result.stdout + result.stderr).strip()

        if self.debug and hook.name in self._REPORTING_TOOLS:
            self.console.print(
                f"[yellow]DEBUG _extract_issues: hook={hook.name}, status={status}, "
                f"output_len={len(error_output)}[/yellow]",
            )

        if hook.name == "semgrep":
            return self._parse_semgrep_issues(error_output)

        if hook.name in self._REPORTING_TOOLS:
            return self._extract_issues_for_reporting_tools(hook, error_output)

        return self._extract_issues_for_regular_tools(
            hook,
            error_output,
            status,
            result,
        )

    def _extract_issues_for_reporting_tools(
        self,
        hook: HookDefinition,
        error_output: str,
    ) -> list[str]:
        # Tools with a registered JSONParser (preferred path):
        # pyscn writes `.pyscn/reports/analyze_*.json`; the parser reads
        # that file rather than scraping Rich-glyph stdout. complexipy
        # is registered too so future re-enable is a 1-line flip in
        # COMPREHENSIVE_HOOKS (disabled=True → False).
        # betterleaks (gitleaks-compatible JSON output) and check-jsonschema
        # (crackerjack's internal JSON-schema validator) round out the
        # JSON-first comp tools as of 2026-06-29.
        if hook.name in {
            "pyscn",
            "complexipy",
            "betterleaks",
            "check-jsonschema",
        }:
            return self._extract_issues_via_json_parser(hook.name, error_output)
        if hook.name == "refurb":
            return self._parse_refurb_issues(error_output)
        if hook.name == "gitleaks":
            return self._parse_gitleaks_issues(error_output)
        if hook.name == "creosote":
            return self._parse_creosote_issues(error_output)
        if hook.name == "pip-audit":
            return self._parse_pip_audit_issues(error_output)
        if hook.name == "lychee":
            return self._parse_lychee_issues(error_output)
        if hook.name == "ty":
            return self._parse_ty_ratchet_issues(error_output)
        return []

    def _extract_issues_via_json_parser(self, tool_name: str, output: str) -> list[str]:
        """Route a hook through the JSON parser factory.

        Falls back to the existing text parsers if the JSONParser raises
        (file not found, parse error, etc.) so we never regress to a
        silent-empty result.
        """
        try:
            from crackerjack.parsers.factory import ParserFactory

            factory = ParserFactory()
            issues = factory.parse_with_validation(tool_name, output)
            return [
                f"{issue.file_path}:{issue.line_number}: {issue.message}"
                if issue.file_path and issue.line_number
                else issue.message
                for issue in issues
            ]
        except Exception as exc:
            logger.warning(
                f"JSON parser path failed for {tool_name} ({exc}); "
                f"falling back to text parser"
            )
            if tool_name == "pyscn":
                return self._parse_pyscn_issues(output)
            if tool_name == "complexipy":
                return self._parse_complexipy_issues(output)
            # betterleaks and check-jsonschema are JSON-only — there is no
            # legacy text parser to fall back to. Return [] rather than
            # regress to silent-empty via a now-removed text path.
            return []

    def _parse_lychee_issues(self, json_output: str) -> list[str]:
        import json

        try:
            obj, _ = json.JSONDecoder().raw_decode(json_output.strip())
            if not isinstance(obj, dict):
                return []
            data = obj
        except (json.JSONDecodeError, ValueError):
            return []

        failure_maps = (
            ("error_map", "errors"),
            ("timeout_map", "timeouts"),
        )
        issues: list[str] = []
        for map_key, counter_key in failure_maps:
            entries: dict[str, list[dict[str, object]]] = data.get(map_key) or {}
            counter = int(data.get(counter_key, 0) or 0)
            if not entries and counter > 0:
                issues.append(
                    f"lychee reported {counter} {counter_key} (see full output)"
                )
                continue
            for file_path, entry_list in entries.items():
                for entry in entry_list:
                    issues.append(self._format_lychee_entry(file_path, entry))

        return issues

    @staticmethod
    def _format_lychee_entry(file_path: str, entry: object) -> str:
        if not isinstance(entry, dict):
            return f"{file_path}: {entry}"

        url = entry.get("url", "<unknown>")
        status = entry.get("status", {})
        if isinstance(status, dict):
            error_text = status.get("text", "Unknown error")
        else:
            error_text = str(status) if status else "Unknown error"
        span = entry.get("span", {})
        line = span.get("line", "?")  # ty: ignore[unresolved-attribute]
        return f"{file_path}:{line}: {url} ({error_text})"

    def _extract_issues_for_regular_tools(
        self,
        hook: HookDefinition,
        error_output: str,
        status: str,
        result: subprocess.CompletedProcess[str],
    ) -> list[str]:
        if status == "passed":
            return []

        if (
            hook.is_formatting
            and hook.name != "ruff-check"
            and "files were modified by this hook" in error_output
        ):
            return []

        if hook.name == "ruff-check":
            error_output = "\n".join(
                line
                for line in error_output.splitlines()
                if "files were modified by this hook" not in line.lower()
            )

        if error_output and error_output.strip().startswith(("{", "[")):
            return []

        if error_output:
            return extract_issue_lines(error_output, tool_name=hook.name)

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
        issues: list[str] = []
        failed_section = self._extract_failed_functions_section(output)

        if not failed_section:
            return issues

        current_file = None
        for line in failed_section.split("\n"):
            line_stripped = line.strip()

            if line_stripped.startswith("- "):
                current_file = self._parse_file_line(line_stripped, issues)
            elif line_stripped and current_file:
                self._parse_continuation_line(line_stripped, current_file, issues)

        return issues

    def _parse_file_line(self, line: str, issues: list[str]) -> str | None:
        remainder = line[2:].strip()

        if ":" not in remainder:
            return self._extract_filename(remainder)

        parts = remainder.split(":", 1)
        filename = self._extract_filename(parts[0].strip())

        if len(parts) >= 2:
            func_text = parts[1].strip()
            if func_text:
                self._add_function_entries(filename, func_text, issues)

        return filename

    def _extract_filename(self, filepath: str) -> str:
        if "/" in filepath:
            return filepath.split("/")[-1]
        return filepath

    def _add_function_entries(
        self, filename: str, func_text: str, issues: list[str]
    ) -> None:
        functions = [f.strip() for f in func_text.split(", ")]
        for func in functions:
            if func:
                issues.append(f"{filename}: {func}")

    def _parse_continuation_line(
        self, line: str, filename: str, issues: list[str]
    ) -> None:
        self._add_function_entries(filename, line, issues)

    def _extract_failed_functions_section(self, output: str) -> str | None:
        if "Failed functions:" not in output:
            return None

        lines = output.split("\n")
        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            if "Failed functions:" in line:
                start_idx = i + 1
            elif start_idx is not None and line.startswith(("─", "=")):
                end_idx = i
                break

        if start_idx is not None and end_idx is not None:
            return "\n".join(lines[start_idx:end_idx])
        elif start_idx is not None:
            return "\n".join(lines[start_idx:])

        return None

    def _parse_refurb_issues(self, output: str) -> list[str]:
        import re

        issues = []
        for line in output.split("\n"):
            if "[FURB" not in line or ":" not in line:
                continue

            match = re.search(
                r"(.+?):\s*(\d+):\s*\d+\s+\[(\w+)\]:\s*(.+)",
                line.strip(),
            )

            if match:
                file_path, line_num, error_code, message = match.groups()

                short_path = self._shorten_path(file_path)

                formatted = f"{short_path}:{line_num} [{error_code}] {message.strip()}"
                issues.append(formatted)
            else:
                issues.append(line.strip())

        return issues

    def _parse_pyscn_issues(self, output: str) -> list[str]:
        import re

        # Inline finding: file.py:line:col: issue_name (severity)
        inline_pattern = re.compile(
            r"^(?P<file>.+?\.py):(?P<line>\d+):\d+:\s+(?P<issue>\S+)\s+\((?P<severity>\w+)\)\s*$"
        )
        # Multi-line finding: header line (file:line:col: func), then message
        finding_markers = (
            "is too complex",
            "is a clone of",
            "Found circular dependency",
            "circular dependency between",
        )

        issues: list[str] = []
        prev_line = ""
        for raw_line in output.split("\n"):
            line = raw_line.rstrip()
            stripped = line.strip()

            # Inline single-line format (deadcode, unreachable, etc.)
            inline_match = inline_pattern.match(stripped)
            if inline_match:
                file_path = self._shorten_path(inline_match.group("file"))
                line_num = inline_match.group("line")
                issue = inline_match.group("issue")
                severity = inline_match.group("severity")
                issues.append(f"{file_path}:{line_num}: {issue} ({severity})")
                prev_line = ""
                continue

            # Multi-line format (complexity findings)
            is_finding = any(marker in line for marker in finding_markers)
            if not is_finding:
                if stripped:
                    prev_line = line
                continue

            message = stripped
            header_match = re.match(
                r"^(?P<file>.+?\.py):(?P<line>\d+):\d+:\s*(?P<func>.+?)\s*$",
                prev_line.strip(),
            )
            if header_match:
                file_path = self._shorten_path(header_match.group("file"))
                line_num = header_match.group("line")
                func = header_match.group("func").strip()
                formatted = f"{file_path}:{line_num}: {func} — {message}"
            else:
                formatted = message

            issues.append(formatted)
            prev_line = ""

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

            clean_path = file_path.lstrip("./")  # type: ignore
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
                    f"{error_type}: {error_msg}[/yellow]",
                )
            else:
                issues.append(f"{error_type}: {error_msg}")
        return issues

    def _parse_pip_audit_issues(self, output: str) -> list[str]:

        from crackerjack.config.pip_audit_ignores import IGNORED_VULNERABILITY_IDS

        if "Traceback (most recent call last):" in output:
            lines = [ln.strip() for ln in output.split("\n") if ln.strip()]
            exception_line = next(
                (ln for ln in reversed(lines) if not ln.startswith("File ")),
                "unknown error",
            )
            return [f"pip-audit crashed (pip installation error): {exception_line}"]

        ignore_vulns = set(IGNORED_VULNERABILITY_IDS)

        json_str = self._extract_json_from_pip_output(output)
        if not json_str:
            return self._parse_pip_text_issues(output)

        data = self._parse_pip_json(json_str)
        if not data:
            return self._parse_pip_text_issues(output)

        return self._extract_vulnerability_issues(data, ignore_vulns)

    def _extract_json_from_pip_output(self, output: str) -> str | None:
        lines = output.strip().split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                return "\n".join(lines[i:])
        return None

    def _parse_pip_text_issues(self, output: str) -> list[str]:
        if "No known vulnerabilities" in output or "0 vulnerabilities" in output:
            return []
        return [
            line.strip()
            for line in output.split("\n")
            if line.strip()
            and ("CVE-" in line or "PYSEC-" in line or "vulnerability" in line.lower())
        ][:10]

    def _parse_pip_json(self, json_str: str) -> dict[str, object] | None:
        import json

        try:
            obj, _ = json.JSONDecoder().raw_decode(json_str.strip())
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None

    def _extract_vulnerability_issues(
        self, data: dict[str, object], ignore_vulns: set[str]
    ) -> list[str]:
        issues = []
        deps = data.get("dependencies")
        if isinstance(deps, list):
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                # pip-audit's JSON schema guarantees `name` and `version` are
                # strings; default fallbacks are also strings. Cast to narrow
                # `dict.get`'s `object` return type to match the helper signature.
                package_name = t.cast(str, dep.get("name", "unknown"))
                package_version = t.cast(str, dep.get("version", "unknown"))
                dep_dict = t.cast(dict[str, object], dep)

                dep_issues = self._extract_dep_vulnerabilities(
                    dep_dict, package_name, package_version, ignore_vulns
                )
                issues.extend(dep_issues)

        return issues

    def _extract_dep_vulnerabilities(
        self,
        dep: dict[str, object],
        package_name: str,
        package_version: str,
        ignore_vulns: set[str],
    ) -> list[str]:
        issues = []
        vulns = dep.get("vulns")
        if isinstance(vulns, list):
            for vuln in vulns:
                if not isinstance(vuln, dict):
                    continue
                # pip-audit JSON schema: `id`, `description` are strings;
                # `aliases`, `fix_versions` are lists. Default fallbacks keep
                # the types correct on missing keys.
                vuln_id = t.cast(str, vuln.get("id", "unknown"))
                aliases = t.cast(list[object], vuln.get("aliases", []))
                description = t.cast(str, vuln.get("description", ""))
                fix_versions = t.cast(list[object], vuln.get("fix_versions", []))

                all_ids = {vuln_id, *aliases}
                if all_ids & ignore_vulns:
                    continue

                issue_msg = self._format_vulnerability_message(
                    package_name,
                    package_version,
                    vuln_id,
                    aliases,
                    description,
                    fix_versions,
                )
                issues.append(issue_msg)

        return issues

    @staticmethod
    def _format_vulnerability_message(
        package_name: str,
        package_version: str,
        vuln_id: str,
        aliases: list[object],
        description: str,
        fix_versions: list[object],
    ) -> str:
        msg_parts = [f"{package_name}=={package_version}", vuln_id]

        cve_aliases = [
            a for a in aliases if isinstance(a, str) and a.startswith("CVE-")
        ]
        if cve_aliases:
            msg_parts.append(f"({', '.join(cve_aliases)})")

        if description:
            desc_preview = (
                description[:80] + "..." if len(description) > 80 else description
            )
            msg_parts.append(f"- {desc_preview}")

        if fix_versions:
            fix_versions_str = [str(v) for v in fix_versions[:3]]
            msg_parts.append(f"Fix: {', '.join(fix_versions_str)}")

        return " ".join(msg_parts)

    def _create_timeout_result(
        self,
        hook: HookDefinition,
        start_time: float,
        partial_output: str = "",
        partial_stderr: str = "",
    ) -> HookResult:
        duration = time.time() - start_time

        subprocess.CompletedProcess(
            args=[],
            returncode=124,
            stdout=partial_output.encode("utf-8") if partial_output else b"",
            stderr=partial_stderr.encode("utf-8") if partial_stderr else b"",
        )

        issues_found = self._extract_issues_from_process_output(
            hook,
            subprocess.CompletedProcess(
                args=[],
                returncode=124,
                stdout=partial_output,
                stderr=partial_stderr,
            ),
            "timeout",
        )

        timeout_msg = (
            f"Hook timed out after {duration:.1f}s (found {len(issues_found)} issues "
            f"before timeout)"
        )
        issues_found.append(timeout_msg)

        return HookResult(
            id=hook.name,
            name=hook.name,
            status="timeout",
            duration=duration,
            issues_found=issues_found,
            issues_count=len(issues_found),
            stage=hook.stage.value,
            exit_code=124,
            error_message=f"Execution exceeded timeout of {hook.timeout}s "
            f"(completed in {duration:.1f}s)",
            is_timeout=True,
            output=partial_output,
            error=partial_stderr,
        )

    def _create_error_result(
        self,
        hook: HookDefinition,
        start_time: float,
        error: Exception,
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
            advisory_issues: list[str] = []
        elif hook_name == "ty":
            # The ty ratchet (crackerjack.tools.ty_ratchet) prints two
            # structured lines in --split mode:
            #   ty ratchet [split] prod: PASS|FAIL (N/M)
            #   ty ratchet [split] test: PASS|FAIL (N/M)
            # The exit code is driven by the PROD gate only; the test
            # gate is advisory (see ty_ratchet.py). We extract the test
            # gate's advisory diagnostics via _parse_ty_ratchet and pass
            # them through HookResult.advisory_issues so the
            # _display_hook_result banner can surface them without
            # re-parsing.
            files_processed, advisory_issues = self._parse_ty_ratchet(output)
        else:
            files_processed = self._parse_generic_hook_output(output)
            advisory_issues = []

        parse_result = self._create_parse_result(
            files_processed, result.returncode, output
        )
        parse_result["advisory_issues"] = advisory_issues
        return parse_result

    def _parse_ty_ratchet(self, output: str) -> tuple[int, list[str]]:
        """Extract the test-ratchet advisories from a ``--split`` run.

        Returns ``(files_processed, advisory_issues)``. ``files_processed``
        is always 0 (the prior negative-encoding sentinel has been
        removed — see ``HookResult.advisory_issues``).

        ``advisory_issues`` carries concise-format diagnostic lines from
        the test-gate run when that gate fails. It is the post-stage
        warning signal: the prod gate drives the exit code, and the
        test-gate diagnostics are surfaced via
        ``_display_hook_result``'s ``⚠️`` banner.
        """
        import re

        test_re = re.compile(
            r"ty ratchet \[split\] test:\s+(?P<status>PASS|FAIL)\s+"
            r"\((?P<count>\d+)/(?P<max>\d+)\)"
        )
        concise_diag_re = re.compile(
            r"^[\w./-]+:\d+:\d+:\s+(?:error|warning)\["
        )

        test_failed = False
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            m = test_re.search(line)
            if m and m.group("status") == "FAIL":
                test_failed = True
                break

        if not test_failed:
            return 0, []

        advisories = [
            raw.strip()
            for raw in output.splitlines()
            if concise_diag_re.match(raw.strip())
        ]
        return 0, advisories

    def _parse_ty_ratchet_issues(self, error_output: str) -> list[str]:
        """Extract operator-actionable issues from a ty ratchet run.

        The ratchet (``crackerjack.tools.ty_ratchet --split``) emits, in
        order, on stdout + stderr:

        1. A prod summary line: ``ty ratchet [split] prod: FAIL (24/50)``
        2. A test summary line: ``ty ratchet [split] test: FAIL (679/30)``
        3. If the test gate fails, a stderr advisory banner:
           ``⚠️  ty: test ratchet FAIL (679/30) — advisory only; prod
           gate FAIL (24/50) controls the exit code.``
        4. The last 20 lines of the test ty run (concise-format
           diagnostics) on stderr.
        5. If the prod gate fails, the last 20 lines of the prod ty run
           on stderr.

        This parser does NOT call ``extract_issue_lines`` — that helper
        is the bug we're fixing. We construct the issue list by hand
        from ty's concise diagnostic prefix, with an explicit
        allow-list of which lines are issues. The two structured
        summary lines, the ``⚠️`` advisory, and ``Found N diagnostics``
        are filtered out — they are the ratchet's own reporting, not
        findings.

        Note: the prod gate drives the exit code; the test tail is
        advisory only (see ``_parse_ty_ratchet`` and
        ``phase_coordinator``'s warning banner). This parser returns
        both because the operator needs to see the type debt even when
        the gate passes. The status-flip in
        ``_update_status_for_reporting_tools`` excludes ``ty`` so
        the test-tail alone does not flip the hook to ``failed``.
        """
        import re

        summary_re = re.compile(
            r"^ty ratchet \[split\] (?:prod|test):\s+(?P<status>PASS|FAIL)"
            r"\s+\((?P<count>\d+)/(?P<max>\d+)\)\s*$"
        )
        advisory_re = re.compile(r"^⚠️\s*ty:")
        concise_diag_re = re.compile(
            r"^[\w./-]+:\d+:\d+:\s+(?:error|warning)\["
        )
        found_summary_re = re.compile(r"^Found\s+\d+\s+diagnostics?\s*$")

        issues: list[str] = []
        for raw in error_output.splitlines():
            line = raw.strip()
            if not line:
                continue
            if summary_re.match(line):
                continue
            if advisory_re.match(line):
                continue
            if found_summary_re.match(line):
                continue
            if concise_diag_re.match(line):
                issues.append(line)
        return issues

    def _is_semgrep_output(self, output: str, args_str: str) -> bool:
        return "semgrep" in output.lower() or "semgrep" in args_str.lower()

    def _create_parse_result(
        self,
        files_processed: int,
        exit_code: int,
        output: str,
    ) -> dict[str, t.Any]:
        return {
            "hook_id": None,
            "exit_code": exit_code,
            "files_processed": files_processed,
            "advisory_issues": [],
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
                if len(match) == 1 and "no issues" not in output.lower():
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

        # Surface ty's test-ratchet advisory as a visible warning after
        # the status line. The prod gate controls pass/fail; the test
        # gate's status is informational so the operator sees the debt
        # without having to scroll through the dim per-line output.
        # The negative ``files_processed`` is a sentinel from
        # ``_parse_ty_ratchet`` — see the comment there for the why.
        if (
            result.name == "ty"
            and result.status == "passed"
            and result.files_processed < 0
        ):
            test_count = -result.files_processed
            self.console.print(
                f"⚠️  ty test ratchet FAIL: {test_count} diagnostic(s) in tests/ "
                f"(advisory only; prod gate controls stage)"
            )

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
        self,
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> set[str]:
        formatting_hooks_failed: set[str] = set()

        for i, result in enumerate(results):
            hook = strategy.hooks[i]
            if hook.is_formatting and result.status == "failed":
                formatting_hooks_failed.add(hook.name)

        return formatting_hooks_failed

    def _retry_all_formatting_hooks(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
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
        self,
        strategy: HookStrategy,
        results: list[HookResult],
        failed_hooks: list[int],
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
                    ("PYTHON", "PIP_", "CONDA_", "VIRTUAL_", "__PYVENV"),
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
        clean_env = {
            "HOME": os.environ.get("HOME", ""),
            "USER": os.environ.get("USER", ""),
            "SHELL": os.environ.get("SHELL", "/bin/bash"),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "TERM": os.environ.get("TERM", "xterm-256color"),
        }

        uv_env = self._get_uv_environment_paths()
        clean_env.update(uv_env)
        return clean_env

    def _get_uv_environment_paths(self) -> dict[str, str]:
        import tempfile

        root_dir = self.pkg_path / ".crackerjack" / "uv"
        try:
            if root_dir.exists():
                shutil.rmtree(root_dir)
            cache_dir = root_dir / "cache"
            data_dir = root_dir / "data"
            tool_dir = root_dir / "tools"
            cache_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            tool_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            root_dir = Path(tempfile.gettempdir()) / "crackerjack" / "uv"
            cache_dir = root_dir / "cache"
            data_dir = root_dir / "data"
            tool_dir = root_dir / "tools"
            cache_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            tool_dir.mkdir(parents=True, exist_ok=True)

        ruff_cache_dir = cache_dir / "ruff"
        pip_cache_dir = cache_dir / "pip"
        ruff_cache_dir.mkdir(parents=True, exist_ok=True)
        pip_cache_dir.mkdir(parents=True, exist_ok=True)

        return {
            "UV_CACHE_DIR": str(cache_dir),
            "UV_TOOL_DIR": str(tool_dir),
            "XDG_CACHE_HOME": str(cache_dir),
            "XDG_DATA_HOME": str(data_dir),
            "RUFF_CACHE_DIR": str(ruff_cache_dir),
            "PIP_CACHE_DIR": str(pip_cache_dir),
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

    def _try_get_qa_result_for_hook(
        self,
        hook: HookDefinition,
        result: subprocess.CompletedProcess[str],
        duration: float,
    ) -> t.Any | None:

        if not self._tool_has_qa_adapter(hook.name):
            return None

        if result.returncode == 0 and hook.name not in {
            "complexipy",
            "refurb",
            "gitleaks",
            "creosote",
        }:
            return None

        try:
            import asyncio

            from crackerjack.adapters.factory import DefaultAdapterFactory
            from crackerjack.models.qa_config import QACheckConfig
            from crackerjack.models.qa_results import QACheckType

            adapter_factory = DefaultAdapterFactory()
            adapter = adapter_factory.create_adapter(hook.name)

            if adapter is None:
                return None

            asyncio.run(adapter.init())

            config = QACheckConfig(
                check_id=adapter.module_id,  # type: ignore
                check_name=hook.name,
                check_type=QACheckType.LINT,
                enabled=True,
                file_patterns=["**/*.py"],
                timeout_seconds=hook.timeout,
            )

            check_start = time.monotonic()
            qa_result = asyncio.run(adapter.check(config=config))
            execution_time_ms = int((time.monotonic() - check_start) * 1000)

            if self._adapter_learner_integration is not None:
                with suppress(Exception):
                    self._adapter_learner_integration.track_adapter_execution(
                        adapter_name=hook.name,
                        file_path=str(self.pkg_path),
                        file_size=0,
                        project_context={},
                        success=qa_result.is_success if qa_result else True,
                        execution_time_ms=execution_time_ms,
                        error_type=qa_result.details
                        if qa_result and not qa_result.is_success
                        else None,
                    )

            if qa_result and qa_result.parsed_issues:
                if self.verbose:
                    self.console.print(
                        f"[dim]✅ Cached QAResult for '{hook.name}' "
                        f"({len(qa_result.parsed_issues)} issues)[/dim]"
                    )
                return qa_result

            return None

        except Exception as e:
            if self.debug:
                self.console.print(
                    f"[yellow]QA adapter failed for '{hook.name}': {e}[/yellow]"
                )
            return None

    def _tool_has_qa_adapter(self, tool_name: str) -> bool:

        tools_with_adapters = {
            "complexipy",
            "skylos",
            "ruff",
            "ruff-format",
            "mypy",
            "zuban",
            "pyright",
            "pylint",
            "bandit",
            "semgrep",
            "codespell",
            "refurb",
            "creosote",
            "pyscn",
            "pytest",
            "mdformat",
            "check-yaml",
            "check-toml",
            "check-json",
            "check-jsonschema",
            "check-ast",
            "trailing-whitespace",
            "end-of-file-fixer",
            "format-json",
            "linkcheckmd",
            "local-link-checker",
            "validate-regex-patterns",
            "gitleaks",
        }

        return tool_name in tools_with_adapters

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
