import asyncio
import logging
import time
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from crackerjack.config import get_console_width
from crackerjack.config.hooks import (
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
)
from crackerjack.models.protocols import HookLockManagerProtocol
from crackerjack.models.task import HookResult
from crackerjack.services.logging import LoggingContext

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


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
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        max_concurrent: int = 4,
        timeout: int = 300,
        quiet: bool = False,
        logger: t.Any | None = None,
        hook_lock_manager: HookLockManagerProtocol | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.quiet = quiet
        self.logger = logger or logging.getLogger(__name__)

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running_processes: set = set()  # Track running subprocesses
        self._last_stdout: bytes | None = None
        self._last_stderr: bytes | None = None

        if hook_lock_manager is None:
            from crackerjack.executors.hook_lock_manager import (
                hook_lock_manager as default_manager,
            )

            self.hook_lock_manager: HookLockManagerProtocol = t.cast(
                HookLockManagerProtocol, default_manager
            )
        else:
            self.hook_lock_manager = hook_lock_manager

    def _format_log(self, message: str, fields: dict[str, t.Any]) -> str:
        if not fields:
            return message
        details = ", ".join(f"{key}={value}" for key, value in fields.items())
        return f"{message} ({details})"

    def _log_info(self, message: str, **fields: t.Any) -> None:
        self.logger.info(self._format_log(message, fields))

    def _log_warning(self, message: str, **fields: t.Any) -> None:
        self.logger.warning(self._format_log(message, fields))

    def _log_debug(self, message: str, **fields: t.Any) -> None:
        self.logger.debug(self._format_log(message, fields))

    def _log_exception(self, message: str, **fields: t.Any) -> None:
        self.logger.exception(self._format_log(message, fields))

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
            self._log_info(
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

            self._log_info(
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
        await self._cleanup_running_processes()
        self._running_processes.clear()
        await self._cleanup_pending_tasks()

    async def _cleanup_running_processes(self) -> None:
        """Terminate all running subprocesses."""
        for proc in list(self._running_processes):
            await self._terminate_single_process(proc)

    async def _terminate_single_process(self, proc: asyncio.subprocess.Process) -> None:
        """Terminate a single subprocess safely."""
        try:
            if proc.returncode is None:
                proc.kill()
                await self._wait_for_process_termination(proc)
        except ProcessLookupError:
            pass
        except Exception:
            pass

    async def _wait_for_process_termination(
        self, proc: asyncio.subprocess.Process
    ) -> None:
        """Wait briefly for process to terminate."""
        with suppress(TimeoutError, RuntimeError):
            await asyncio.wait_for(proc.wait(), timeout=0.1)

    async def _cleanup_pending_tasks(self) -> None:
        """Cancel any pending hook-related tasks."""
        with suppress(RuntimeError):
            loop = asyncio.get_running_loop()
            pending_tasks = self._get_pending_hook_tasks(loop)
            await self._cancel_tasks(pending_tasks)

    def _get_pending_hook_tasks(self, loop: asyncio.AbstractEventLoop) -> list:
        """Get list of pending hook-related tasks."""
        return [
            task
            for task in asyncio.all_tasks(loop)
            if not task.done() and "hook" in str(task).lower()
        ]

    async def _cancel_tasks(self, tasks: list) -> None:
        """Cancel a list of tasks safely."""
        for task in tasks:
            if not task.done():
                await self._cancel_single_task(task)

    async def _cancel_single_task(self, task: asyncio.Task) -> None:
        """Cancel a single task safely."""
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

    async def _execute_single_hook(
        self,
        hook: HookDefinition,
        command_override: list[str] | None = None,
    ) -> HookResult:
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
                    return await self._run_hook_subprocess(
                        hook, command_override=command_override
                    )
            else:
                return await self._run_hook_subprocess(
                    hook, command_override=command_override
                )

    async def _run_hook_subprocess(
        self,
        hook: HookDefinition,
        command_override: list[str] | None = None,
    ) -> HookResult:
        start_time = time.time()

        try:
            cmd = (
                command_override
                if command_override is not None
                else hook.get_command()
                if hasattr(hook, "get_command")
                else [str(hook)]
            )
            timeout_val = getattr(hook, "timeout", self.timeout)

            self.logger.debug(
                "Starting hook execution",
                hook=hook.name,
                command=" ".join(cmd),
                timeout=timeout_val,
            )

            repo_root = self._get_repo_root()
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=repo_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Track this process for cleanup
            self._running_processes.add(process)

            result = await self._execute_process_with_timeout(
                process, hook, timeout_val, start_time
            )
            if result is not None:
                return result

            # Process completed successfully
            duration = time.time() - start_time
            return await self._build_success_result(process, hook, duration)

        except RuntimeError as e:
            return self._handle_runtime_error(e, hook, start_time)
        except Exception as e:
            return self._handle_general_error(e, hook, start_time)

    def _execute_hook_sync(
        self,
        hook: HookDefinition,
        files: list[Path] | None = None,
        stage: HookStage | None = None,
        command_override: list[str] | None = None,
    ) -> HookResult:
        """Synchronous wrapper for single-hook execution (tests/utilities)."""
        if stage is not None:
            hook.stage = stage

        if command_override is None:
            command_override = (
                hook.build_command(files) if files else hook.get_command()
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self._execute_single_hook(hook, command_override=command_override)
            )

        raise RuntimeError(
            "Use await _execute_single_hook within an active event loop."
        )

    def _get_repo_root(self) -> Path:
        """Determine the repository root directory.

        Returns pkg_path directly to ensure hooks run in the correct project directory
        regardless of the project name.
        """
        return self.pkg_path

    async def _execute_process_with_timeout(
        self,
        process: asyncio.subprocess.Process,
        hook: HookDefinition,
        timeout_val: int,
        start_time: float,
    ) -> HookResult | None:
        """Execute process with timeout handling. Returns HookResult on timeout, None on success."""
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_val,
            )
            # Process completed normally - remove from tracking
            self._running_processes.discard(process)
            # Store output for later use
            self._last_stdout = stdout
            self._last_stderr = stderr
            return None
        except TimeoutError:
            return await self._handle_process_timeout(
                process, hook, timeout_val, start_time
            )

    async def _handle_process_timeout(
        self,
        process: asyncio.subprocess.Process,
        hook: HookDefinition,
        timeout_val: int,
        start_time: float,
    ) -> HookResult:
        """Handle process timeout by killing process and returning timeout result."""
        await self._terminate_process_safely(process, hook)
        duration = time.time() - start_time

        self._log_warning(
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
            issues_count=1,  # Timeout counts as 1 issue
            stage=hook.stage.value,
            exit_code=124,  # Standard timeout exit code
            error_message=f"Hook execution exceeded timeout of {timeout_val}s",
            is_timeout=True,
        )

    async def _terminate_process_safely(
        self,
        process: asyncio.subprocess.Process,
        hook: HookDefinition,
    ) -> None:
        """Safely terminate a process and handle termination errors."""
        try:
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=0.1)
            self._running_processes.discard(process)
        except (TimeoutError, RuntimeError) as e_wait:
            self._log_termination_error(e_wait, hook)
            self._running_processes.discard(process)

    def _log_termination_error(
        self,
        error: Exception,
        hook: HookDefinition,
    ) -> None:
        """Log process termination errors appropriately."""
        error_str = str(error)
        if "Event loop is closed" in error_str:
            self._log_debug(
                "Event loop closed while waiting for process termination",
                hook=hook.name,
            )
        elif "handle" in error_str.lower() or "pid" in error_str.lower():
            self._log_debug(
                "Subprocess handle issue during termination",
                hook=hook.name,
            )

    async def _build_success_result(
        self,
        process: asyncio.subprocess.Process,
        hook: HookDefinition,
        duration: float,
    ) -> HookResult:
        """Build HookResult from successful process execution."""
        output_text = self._decode_process_output(self._last_stdout, self._last_stderr)
        return_code = process.returncode if process.returncode is not None else -1
        parsed_output = self._parse_hook_output(return_code, output_text, hook.name)

        status = "passed" if return_code == 0 else "failed"

        self._log_info(
            "Hook execution completed",
            hook=hook.name,
            status=status,
            duration_seconds=round(duration, 2),
            return_code=process.returncode,
            files_processed=parsed_output.get("files_processed", 0),
            issues_count=len(parsed_output.get("issues", [])),
        )

        issues = parsed_output.get("issues", [])
        # If hook failed but has no parsed issues, use raw output as error details
        if status == "failed" and not issues and output_text:
            # Split output into lines and take first 10 non-empty lines as issues
            error_lines = [
                line.strip() for line in output_text.split("\n") if line.strip()
            ][:10]
            issues = error_lines or ["Hook failed with non-zero exit code"]

        # Ensure failed hooks always have at least 1 issue count
        issues_count = max(len(issues), 1 if status == "failed" else 0)

        return HookResult(
            id=parsed_output.get("hook_id", hook.name),
            name=hook.name,
            status=status,
            duration=duration,
            files_processed=parsed_output.get("files_processed", 0),
            issues_found=issues,
            issues_count=issues_count,
            stage=hook.stage.value,
            exit_code=return_code,  # Include exit code for debugging
            error_message=output_text[:500]
            if status == "failed" and output_text
            else None,  # First 500 chars of error
            is_timeout=False,
        )

    def _decode_process_output(self, stdout: bytes | None, stderr: bytes | None) -> str:
        """Decode process stdout and stderr into a single string."""
        stdout_text = stdout.decode() if stdout else ""
        stderr_text = stderr.decode() if stderr else ""
        return stdout_text + stderr_text

    def _handle_runtime_error(
        self,
        error: RuntimeError,
        hook: HookDefinition,
        start_time: float,
    ) -> HookResult:
        """Handle RuntimeError during hook execution."""
        if "Event loop is closed" in str(error):
            duration = time.time() - start_time
            self._log_warning(
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
                issues_count=1,  # Error counts as 1 issue
                stage=hook.stage.value,
                exit_code=1,
                error_message="Event loop closed during hook execution",
                is_timeout=False,
            )
        else:
            raise

    def _handle_general_error(
        self,
        error: Exception,
        hook: HookDefinition,
        start_time: float,
    ) -> HookResult:
        """Handle general exceptions during hook execution."""
        duration = time.time() - start_time
        self._log_exception(
            "Hook execution failed with exception",
            hook=hook.name,
            error=str(error),
            error_type=type(error).__name__,
            duration_seconds=round(duration, 2),
        )
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="error",
            duration=duration,
            issues_found=[str(error)],
            issues_count=1,  # Error counts as 1 issue
            stage=hook.stage.value,
            exit_code=1,
            error_message=f"{type(error).__name__}: {error}",
            is_timeout=False,
        )

    def _parse_semgrep_output_async(self, output: str) -> int:
        """Parse Semgrep output to count files with issues, not total files scanned."""

        # Try JSON parsing first
        json_result = self._try_parse_semgrep_json(output)
        if json_result is not None:
            return json_result

        # Fall back to text pattern matching
        return self._parse_semgrep_text_patterns(output)

    def _try_parse_semgrep_json(self, output: str) -> int | None:
        """Try to parse Semgrep JSON output."""

        try:
            stripped_output = output.strip()

            # Try parsing entire output as JSON
            if stripped_output.startswith("{"):
                count = self._extract_file_count_from_json(stripped_output)
                if count is not None:
                    return count

            # Try line-by-line JSON parsing
            return self._parse_semgrep_json_lines(output)
        except Exception:
            return None

    def _extract_file_count_from_json(self, json_str: str) -> int | None:
        """Extract file count from JSON string."""
        import json

        try:
            json_data = json.loads(json_str)
            if "results" in json_data:
                file_paths = {
                    result.get("path") for result in json_data.get("results", [])
                }
                return len([p for p in file_paths if p])
        except json.JSONDecodeError:
            pass
        return None

    def _parse_semgrep_json_lines(self, output: str) -> int | None:
        """Parse JSON from individual lines in output."""

        lines = output.splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                count = self._extract_file_count_from_json(line)
                if count is not None:
                    return count
        return None

    def _parse_semgrep_text_patterns(self, output: str) -> int:
        """Parse Semgrep text output using regex patterns."""
        import re

        semgrep_patterns = [
            r"found\s+(\d+)\s+issues?\s+in\s+(\d+)\s+files?",
            r"found\s+no\s+issues",
            r"scanning\s+(\d+)\s+files?",
        ]

        for pattern in semgrep_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                result = self._process_semgrep_matches(matches, output)
                if result is not None:
                    return result

        return 0

    def _process_semgrep_matches(self, matches: list, output: str) -> int | None:
        """Process regex matches from Semgrep output."""
        for match in matches:
            if isinstance(match, tuple):
                if len(match) == 2:
                    issue_count, file_count = int(match[0]), int(match[1])
                    return file_count if issue_count > 0 else 0
                elif len(match) == 1 and "no issues" not in output.lower():
                    continue
            elif "no issues" in output.lower():
                return 0
        return None

    def _parse_semgrep_issues_async(self, output: str) -> list[str]:
        """Parse semgrep JSON output to extract both findings and errors.

        Semgrep returns JSON with two arrays:
        - "results": Security/code quality findings
        - "errors": Configuration, download, or execution errors

        This method extracts issues from both arrays to provide comprehensive error reporting.
        """
        import json

        issues = []

        try:
            # Try to parse as JSON
            json_data = json.loads(output.strip())

            # Extract findings from results array
            if "results" in json_data:
                for result in json_data.get("results", []):
                    # Format: "file.py:line - rule_id: message"
                    path = result.get("path", "unknown")
                    line_num = result.get("start", {}).get("line", "?")
                    rule_id = result.get("check_id", "unknown-rule")
                    message = result.get("extra", {}).get(
                        "message", "Security issue detected"
                    )
                    issues.append(f"{path}:{line_num} - {rule_id}: {message}")

            # Extract errors from errors array (config errors, download failures, etc.)
            if "errors" in json_data:
                for error in json_data.get("errors", []):
                    error_type = error.get("type", "SemgrepError")
                    error_msg = error.get("message", str(error))
                    issues.append(f"{error_type}: {error_msg}")

        except json.JSONDecodeError:
            # If JSON parsing fails, return raw output (shouldn't happen with --json flag)
            if output.strip():
                issues = [line.strip() for line in output.split("\n") if line.strip()][
                    :10
                ]

        return issues

    def _parse_hook_output(
        self, returncode: int, output: str, hook_name: str = ""
    ) -> dict[str, t.Any]:
        """Parse hook output to extract file counts and other metrics.

        Args:
            returncode: Exit code from the subprocess
            output: Raw output from the hook execution
            hook_name: Name of the hook being executed to allow special handling

        Returns:
            Dictionary with parsed results including files_processed
        """
        result = self._initialize_parse_result(returncode, output)

        # Special handling for semgrep
        if hook_name == "semgrep":
            result["files_processed"] = self._parse_semgrep_output_async(output)
            result["issues"] = self._parse_semgrep_issues_async(output)
            return result

        # Special handling for check-added-large-files
        if hook_name == "check-added-large-files":
            result["files_processed"] = self._parse_large_files_output(
                output, returncode
            )
            return result

        # General hook parsing
        result["files_processed"] = self._extract_file_count_from_output(output)
        return result

    def _initialize_parse_result(
        self, returncode: int, output: str
    ) -> dict[str, t.Any]:
        """Initialize result dictionary with default values."""
        return {
            "hook_id": None,
            "exit_code": returncode,
            "files_processed": 0,
            "issues": [],
            "raw_output": output,
        }

    def _parse_large_files_output(self, output: str, returncode: int) -> int:
        """Parse check-added-large-files output to count files exceeding size limit."""

        clean_output = output.replace("\\n", "\n").replace("\\t", "\t")

        # Try to find explicit failure patterns
        failure_count = self._find_large_file_failures(clean_output)
        if failure_count is not None:
            return failure_count

        # Check for "all files under limit" success case
        if self._is_all_files_under_limit(clean_output, returncode):
            return 0

        # If hook failed but no pattern matched, assume at least 1 file failed
        if returncode != 0:
            return 1

        # Default: no large files found
        return 0

    def _find_large_file_failures(self, clean_output: str) -> int | None:
        """Find count of files that exceeded size limit."""
        import re

        failure_patterns = [
            r"large file(?:s)? found:?\s*(\d+)",
            r"found\s+(\d+)\s+large file",
            r"(\d+)\s+file(?:s)?\s+exceed(?:ed)?\s+size\s+limit",
            r"(\d+)\s+large file(?:s)?\s+found",
            r"(\d+)\s+file(?:s)?\s+(?:failed|violated|exceeded)",
        ]

        for pattern in failure_patterns:
            matches = re.findall(pattern, clean_output, re.IGNORECASE)
            if matches:
                return int(max([int(m) for m in matches if m.isdigit()]))

        return None

    def _is_all_files_under_limit(self, clean_output: str, returncode: int) -> bool:
        """Check if output indicates all files are under size limit."""
        import re

        pattern = r"All files are under size limit"
        return bool(re.search(pattern, clean_output, re.IGNORECASE) and returncode == 0)

    def _extract_file_count_from_output(self, output: str) -> int:
        """Extract file count from general hook output."""
        import re

        clean_output = output.replace("\\n", "\n").replace("\\t", "\t")
        patterns = self._get_file_count_patterns()

        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, clean_output, re.IGNORECASE)
            if matches:
                all_matches.extend([int(m) for m in matches if m.isdigit()])

        return max(all_matches) if all_matches else 0

    def _get_file_count_patterns(self) -> list[str]:
        """Get regex patterns for extracting file counts from hook output."""
        return [
            r"(\d+)\s+files?\s+(?:processed|checked|examined|scanned|formatted|found|affected)",
            r"found\s+(\d+)\s+files?",
            r"(\d+)\s+files?\s+with\s+issues?",
            r"(\d+)\s+files?\s+(?:would\s+be|were)\s+(?:formatted|modified|fixed)",
            r"(\d+)\s+files?\s+would\s+be\s+?(?:formatted|fixed|updated)",
            r"(\d+)\s+files?\s+?(?:formatted|fixed|updated)",
            r"(\d+)\s+files?\s+formatted",
            r"analyzed\s+(\d+)\s+deps",
            r"(\d+)\s+findings?",
            r"(\d+)\s+issues?\s+found",
            r"(\d+)\s+tests ran",
            r"(\d+)\s+files\s+scanned",
            r"Checked\s+(\d+)\s+files?",
            r"for\s+(\d+)\s+files?",
            r"(\d+)\s+files?",
        ]

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
