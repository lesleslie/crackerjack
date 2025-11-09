import asyncio
import time
import typing as t
from dataclasses import dataclass
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends
from acb.logger import Logger

from crackerjack.config import get_console_width
from crackerjack.config.hooks import HookDefinition, HookStrategy, RetryPolicy
from crackerjack.models.protocols import HookLockManagerProtocol
from crackerjack.models.task import HookResult
from crackerjack.services.logging import LoggingContext


@dataclass
class AsyncHookExecutionResult:
    strategy_name: str
    results: list[HookResult]
    total_duration: float
    success: bool
    concurrent_execution: bool = True
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
            "performance_gain_percent": round(self.performance_gain, 1),
        }


class AsyncHookExecutor:
    @depends.inject
    def __init__(
        self,
        logger: Inject[Logger],
        console: Console,
        pkg_path: Path,
        max_concurrent: int = 4,
        timeout: int = 300,
        quiet: bool = False,
        hook_lock_manager: HookLockManagerProtocol | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.quiet = quiet
        self.logger = logger

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running_processes: set = set()  # Track running subprocesses

        if hook_lock_manager is None:
            from crackerjack.executors.hook_lock_manager import (
                hook_lock_manager as default_manager,
            )

            self.hook_lock_manager: HookLockManagerProtocol = t.cast(
                HookLockManagerProtocol, default_manager
            )
        else:
            self.hook_lock_manager = hook_lock_manager

    async def execute_strategy(
        self,
        strategy: HookStrategy,
    ) -> AsyncHookExecutionResult:
        with LoggingContext(
            "async_hook_strategy",
            strategy_name=strategy.name,
            hook_count=len(strategy.hooks),
        ):
            start_time = time.time()
            self.logger.info(
                "Starting async hook strategy execution",
                strategy=strategy.name,
                hooks=len(strategy.hooks),
                parallel=strategy.parallel,
                max_workers=getattr(strategy, "max_workers", self.max_concurrent),
            )

            # Header is displayed by PhaseCoordinator; suppress here to avoid duplicates

            estimated_sequential = sum(
                getattr(hook, "timeout", 30) for hook in strategy.hooks
            )

            if strategy.parallel and len(strategy.hooks) > 1:
                results = await self._execute_parallel(strategy)
            else:
                results = await self._execute_sequential(strategy)

            if strategy.retry_policy != RetryPolicy.NONE:
                results = await self._handle_retries(strategy, results)

            total_duration = time.time() - start_time
            success = all(r.status == "passed" for r in results)
            performance_gain = max(
                0,
                ((estimated_sequential - total_duration) / estimated_sequential) * 100,
            )

            self.logger.info(
                "Async hook strategy completed",
                strategy=strategy.name,
                success=success,
                duration_seconds=round(total_duration, 2),
                performance_gain_percent=round(performance_gain, 1),
                passed=sum(1 for r in results if r.status == "passed"),
                failed=sum(1 for r in results if r.status == "failed"),
                errors=sum(1 for r in results if r.status in ("timeout", "error")),
            )

            if not self.quiet:
                self._print_summary(strategy, results, success, performance_gain)

            return AsyncHookExecutionResult(
                strategy_name=strategy.name,
                results=results,
                total_duration=total_duration,
                success=success,
                performance_gain=performance_gain,
            )

    def get_lock_statistics(self) -> dict[str, t.Any]:
        return self.hook_lock_manager.get_lock_stats()

    def get_comprehensive_status(self) -> dict[str, t.Any]:
        return {
            "executor_config": {
                "max_concurrent": self.max_concurrent,
                "timeout": self.timeout,
                "quiet": self.quiet,
            },
            "lock_manager_status": self.hook_lock_manager.get_lock_stats(),
        }

    def _print_strategy_header(self, strategy: HookStrategy) -> None:
        # Intentionally no-op: PhaseCoordinator controls stage headers
        return None

    async def _execute_sequential(self, strategy: HookStrategy) -> list[HookResult]:
        results: list[HookResult] = []
        for hook in strategy.hooks:
            result = await self._execute_single_hook(hook)
            results.append(result)
            self._display_hook_result(result)
        return results

    async def _execute_parallel(self, strategy: HookStrategy) -> list[HookResult]:
        results: list[HookResult] = []

        formatting_hooks = [
            h for h in strategy.hooks if getattr(h, "is_formatting", False)
        ]
        other_hooks = [
            h for h in strategy.hooks if not getattr(h, "is_formatting", False)
        ]

        for hook in formatting_hooks:
            result = await self._execute_single_hook(hook)
            results.append(result)
            self._display_hook_result(result)

        if other_hooks:
            tasks = [self._execute_single_hook(hook) for hook in other_hooks]
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, task_result in enumerate(parallel_results):
                if isinstance(task_result, Exception):
                    hook = other_hooks[i]
                    error_result = HookResult(
                        id=getattr(hook, "name", f"hook_{i}"),
                        name=getattr(hook, "name", f"hook_{i}"),
                        status="error",
                        duration=0.0,
                        issues_found=[str(task_result)],
                        stage=hook.stage.value,
                    )
                    results.append(error_result)
                    self._display_hook_result(error_result)
                else:
                    hook_result = t.cast(HookResult, task_result)
                    results.append(hook_result)
                    self._display_hook_result(hook_result)

        return results

    async def cleanup(self) -> None:
        """Clean up any remaining resources before event loop closes."""
        # First terminate any running subprocesses
        for proc in list(self._running_processes):
            try:
                if proc.returncode is None:  # Process is still running
                    proc.kill()
                    try:
                        # Wait briefly for process to terminate
                        await asyncio.wait_for(proc.wait(), timeout=0.1)
                    except (TimeoutError, RuntimeError):
                        pass  # Process may have already terminated
            except ProcessLookupError:
                # Process already terminated
                pass
            except Exception:
                # Other error during process termination, continue
                pass

        # Clear the running processes set
        self._running_processes.clear()

        # Cancel any pending tasks related to hook execution
        try:
            loop = asyncio.get_running_loop()
            pending_tasks = [task for task in asyncio.all_tasks(loop)
                           if not task.done() and 'hook' in str(task).lower()]

            for task in pending_tasks:
                if not task.done():
                    try:
                        task.cancel()
                        await asyncio.wait_for(task, timeout=0.1)
                    except (TimeoutError, asyncio.CancelledError):
                        pass
                    except RuntimeError as e:
                        if "Event loop is closed" in str(e):
                            return
                        else:
                            raise
        except RuntimeError:
            # No running event loop
            pass

    async def _execute_single_hook(self, hook: HookDefinition) -> HookResult:
        async with self._semaphore:
            if self.hook_lock_manager.requires_lock(hook.name):
                self.logger.debug(
                    f"Hook {hook.name} requires sequential execution lock"
                )
                if not self.quiet:
                    self.console.print(
                        f"[dim]🔒 {hook.name} (sequential execution)[/dim]"
                    )

            if self.hook_lock_manager.requires_lock(hook.name):
                self.logger.debug(
                    f"Hook {hook.name} requires sequential execution lock"
                )
                if not self.quiet:
                    self.console.print(
                        f"[dim]🔒 {hook.name} (sequential execution)[/dim]"
                    )

                async with self.hook_lock_manager.acquire_hook_lock(hook.name):
                    return await self._run_hook_subprocess(hook)
            else:
                return await self._run_hook_subprocess(hook)

    async def _run_hook_subprocess(self, hook: HookDefinition) -> HookResult:
        start_time = time.time()

        try:
            cmd = hook.get_command() if hasattr(hook, "get_command") else [str(hook)]
            timeout_val = getattr(hook, "timeout", self.timeout)

            self.logger.debug(
                "Starting hook execution",
                hook=hook.name,
                command=" ".join(cmd),
                timeout=timeout_val,
            )

            repo_root = (
                self.pkg_path.parent
                if self.pkg_path.name == "crackerjack"
                else self.pkg_path
            )
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=repo_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Track this process for cleanup
            self._running_processes.add(process)

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_val,
                )
                # Process completed normally - remove from tracking
                self._running_processes.discard(process)
            except TimeoutError:
                try:
                    process.kill()
                    # Use a very short timeout to avoid waiting too long if event loop is closed
                    await asyncio.wait_for(process.wait(), timeout=0.1)
                    # Process terminated due to timeout - remove from tracking
                    self._running_processes.discard(process)
                except (TimeoutError, RuntimeError) as e_wait:
                    # Process didn't terminate quickly or event loop is closed, continue
                    if "Event loop is closed" in str(e_wait):
                        # Log but don't raise - this prevents the error message from appearing
                        self.logger.debug(
                            "Event loop closed while waiting for process termination",
                            hook=hook.name,
                        )
                    elif "handle" in str(e_wait).lower() or "pid" in str(e_wait).lower():
                        # Catch the specific error related to subprocess handles and PIDs
                        self.logger.debug(
                            "Subprocess handle issue during termination",
                            hook=hook.name,
                        )
                    # Remove from tracking anyway since we're giving up
                    self._running_processes.discard(process)
                    pass
                duration = time.time() - start_time

                self.logger.warning(
                    "Hook execution timed out",
                    hook=hook.name,
                    timeout=timeout_val,
                    duration_seconds=round(duration, 2),
                )

                return HookResult(
                    id=hook.name,
                    name=hook.name,
                    status="timeout",
                    duration=duration,
                    issues_found=[f"Hook timed out after {duration: .1f}s"],
                    stage=hook.stage.value,
                )

            duration = time.time() - start_time
            output_text = (stdout.decode() if stdout else "") + (
                stderr.decode() if stderr else ""
            )
            return_code = process.returncode if process.returncode is not None else -1
            parsed_output = self._parse_hook_output(return_code, output_text, hook.name)

            status = "passed" if return_code == 0 else "failed"

            self.logger.info(
                "Hook execution completed",
                hook=hook.name,
                status=status,
                duration_seconds=round(duration, 2),
                return_code=process.returncode,
                files_processed=parsed_output.get("files_processed", 0),
                issues_count=len(parsed_output.get("issues", [])),
            )

            return HookResult(
                id=parsed_output.get("hook_id", hook.name),
                name=hook.name,
                status=status,
                duration=duration,
                files_processed=parsed_output.get("files_processed", 0),
                issues_found=parsed_output.get("issues", []),
                stage=hook.stage.value,
            )

        except RuntimeError as e:
            # Handle cases where event loop is closed during subprocess execution
            if "Event loop is closed" in str(e):
                duration = time.time() - start_time
                self.logger.warning(
                    "Event loop closed during hook execution, returning error",
                    hook=hook.name,
                    duration_seconds=round(duration, 2),
                )
                return HookResult(
                    id=hook.name,
                    name=hook.name,
                    status="error",
                    duration=duration,
                    issues_found=["Event loop closed during execution"],
                    stage=hook.stage.value,
                )
            else:
                # Re-raise any other runtime errors
                raise
        except Exception as e:
            duration = time.time() - start_time
            self.logger.exception(
                "Hook execution failed with exception",
                hook=hook.name,
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=round(duration, 2),
            )
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="error",
                duration=duration,
                issues_found=[str(e)],
                stage=hook.stage.value,
            )

    def _parse_hook_output(self, returncode: int, output: str, hook_name: str = "") -> dict[str, t.Any]:
        """Parse hook output to extract file counts and other metrics.

        Args:
            returncode: Exit code from the subprocess
            output: Raw output from the hook execution
            hook_name: Name of the hook being executed to allow special handling

        Returns:
            Dictionary with parsed results including files_processed
        """
        import re

        # Initialize with default values
        result = {
            "hook_id": None,
            "exit_code": returncode,
            "files_processed": 0,
            "issues": [],
            "raw_output": output,
        }

        # For some hooks, we want to track different metrics than others
        # For example, check-added-large-files should report files that failed (exceeded size limit)
        # rather than total files checked

        # Check if this is the check-added-large-files hook specifically
        is_check_large_files = hook_name == "check-added-large-files"

        if is_check_large_files:
            # For check-added-large-files, we want to count the files that failed (exceeded size limit)
            # rather than total files checked
            failure_patterns = [
                # Pattern for large files that were found/exceeded limits
                r"large file(?:s)? found:?\s*(\d+)",
                r"found\s+(\d+)\s+large file",
                r"(\d+)\s+file(?:s)?\s+exceed(?:ed)?\s+size\s+limit",
                r"(\d+)\s+large file(?:s)?\s+found",
                r"(\d+)\s+file(?:s)?\s+(?:failed|violated|exceeded)",
            ]

            clean_output = output.replace('\\n', '\n').replace('\\t', '\t')
            for pattern in failure_patterns:
                matches = re.findall(pattern, clean_output, re.IGNORECASE)
                if matches:
                    # Return the number of large files found as files_processed
                    result["files_processed"] = int(max([int(m) for m in matches if m.isdigit()]))
                    return result

            # SPECIAL CASE: Check for "All X files are under size limit" pattern which means 0 failed
            # This specifically should result in 0 files processed since no files exceeded size limits
            all_under_limit_pattern = r"All files are under size limit"
            if re.search(all_under_limit_pattern, clean_output, re.IGNORECASE) and returncode == 0:
                # All files are under size limit (hook passed), so 0 files failed the size check
                result["files_processed"] = 0
                return result

            # If the hook has a non-zero exit code, it means large files were found but we missed the pattern
            if returncode != 0:
                # In case we missed the pattern but hook failed, assume at least 1 file failed
                result["files_processed"] = 1
                return result

            # DEFAULT CASE: If no failure patterns matched and exit code is 0
            # it means no large files were found, so 0 files processed
            result["files_processed"] = 0
            return result

        # Remove any potential escape characters that might interfere with parsing
        clean_output = output.replace('\\n', '\n').replace('\\t', '\t')

        # Count files based on patterns that appear in various tool outputs
        # Examples of patterns to look for:
        # - "X files checked/processed/formatted"
        # - "Found issues in X files"
        # - Specific patterns for common tools

        # Common patterns for counting files for other hooks
        patterns = [
            # Standard patterns like "X files were processed"
            r"(\d+)\s+files?\s+(?:processed|checked|examined|scanned|formatted|found|affected)",
            r"found\s+(\d+)\s+files?",
            r"(\d+)\s+files?\s+with\s+issues?",
            r"(\d+)\s+files?\s+(?:would\s+be|were)\s+(?:formatted|modified|fixed)",
            # Ruff patterns
            r"(\d+)\s+files?\s+would\s+be\s+?(?:formatted|fixed|updated)",
            r"(\d+)\s+files?\s+?(?:formatted|fixed|updated)",
            # mdformat patterns
            r"(\d+)\s+files?\s+formatted",
            # creosote patterns
            r"analyzed\s+(\d+)\s+deps",
            # refurb patterns
            r"(\d+)\s+findings?",
            # skylos patterns
            r"(\d+)\s+issues?\s+found",
            # bandit patterns
            r"(\d+)\s+tests ran",
            # gitleaks patterns (if needed)
            r"(\d+)\s+files\s+scanned",
            # Ruff-specific patterns (like "Checked X files")
            r"Checked\s+(\d+)\s+files?",
            # Pyright/Zuban patterns
            r"for\s+(\d+)\s+files?",
            # General file count pattern
            r"(\d+)\s+files?",
        ]

        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, clean_output, re.IGNORECASE)
            if matches:
                # Convert matches to integers and add to list
                all_matches.extend([int(m) for m in matches if m.isdigit()])

        # Use the highest value found or default to 0
        if all_matches:
            result["files_processed"] = max(all_matches)
        else:
            # If no specific file counts found in output, default to 0
            # This is appropriate when tools don't explicitly state file counts
            result["files_processed"] = 0

        return result

    def _display_hook_result(self, result: HookResult) -> None:
        if self.quiet:
            return
        width = get_console_width()
        dots = "." * max(0, (width - len(result.name)))
        status_text = "Passed" if result.status == "passed" else "Failed"
        status_color = "green" if result.status == "passed" else "red"

        self.console.print(
            f"{result.name}{dots}[{status_color}]{status_text}[/{status_color}]"
        )

        if result.status != "passed" and result.issues_found:
            for issue in result.issues_found:
                if issue and "raw_output" not in issue:
                    self.console.print(issue)

    async def _handle_retries(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> list[HookResult]:
        if strategy.retry_policy == RetryPolicy.FORMATTING_ONLY:
            return await self._retry_formatting_hooks(strategy, results)
        if strategy.retry_policy == RetryPolicy.ALL_HOOKS:
            return await self._retry_all_hooks(strategy, results)
        return results

    async def _retry_formatting_hooks(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> list[HookResult]:
        formatting_hooks_failed: set[str] = set()

        for i, result in enumerate(results):
            hook = strategy.hooks[i]
            if getattr(hook, "is_formatting", False) and result.status == "failed":
                formatting_hooks_failed.add(hook.name)

        if not formatting_hooks_failed:
            return results

        retry_tasks = [self._execute_single_hook(hook) for hook in strategy.hooks]
        retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

        updated_results: list[HookResult] = []
        for i, (prev_result, new_result) in enumerate(
            zip(results, retry_results, strict=False)
        ):
            if isinstance(new_result, Exception):
                hook = strategy.hooks[i]
                error_result = HookResult(
                    id=hook.name,
                    name=hook.name,
                    status="error",
                    duration=prev_result.duration,
                    issues_found=[str(new_result)],
                    stage=hook.stage.value,
                )
                updated_results.append(error_result)
            else:
                hook_result = t.cast("HookResult", new_result)
                hook_result.duration += prev_result.duration
                updated_results.append(hook_result)

            self._display_hook_result(updated_results[-1])

        return updated_results

    async def _retry_all_hooks(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
    ) -> list[HookResult]:
        failed_indices = [i for i, r in enumerate(results) if r.status == "failed"]

        if not failed_indices:
            return results

        updated_results = results.copy()
        retry_tasks: list[t.Awaitable[HookResult]] = []
        retry_indices: list[int] = []

        for i in failed_indices:
            hook = strategy.hooks[i]
            retry_tasks.append(self._execute_single_hook(hook))
            retry_indices.append(i)

        retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

        for result_idx, new_result in zip(retry_indices, retry_results, strict=False):
            prev_result = results[result_idx]

            if isinstance(new_result, Exception):
                hook = strategy.hooks[result_idx]
                error_result = HookResult(
                    id=hook.name,
                    name=hook.name,
                    status="error",
                    duration=prev_result.duration,
                    issues_found=[str(new_result)],
                    stage=hook.stage.value,
                )
                updated_results[result_idx] = error_result
            else:
                hook_result = t.cast("HookResult", new_result)
                hook_result.duration += prev_result.duration
                updated_results[result_idx] = hook_result

            self._display_hook_result(updated_results[result_idx])

        return updated_results

    def _print_summary(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
        success: bool,
        performance_gain: float,
    ) -> None:
        if success:
            self.console.print(
                f"[green]✅[/ green] {strategy.name.title()} hooks passed: {len(results)} / {len(results)} "
                f"(async, {performance_gain: .1f} % faster)",
            )
