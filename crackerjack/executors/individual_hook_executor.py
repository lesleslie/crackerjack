import asyncio
import subprocess
import time
import typing as t
from dataclasses import dataclass
from pathlib import Path

from acb.console import Console

from crackerjack.cli.formatting import separator as make_separator
from crackerjack.config import get_console_width
from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.executors.hook_executor import HookExecutionResult
from crackerjack.models.protocols import HookLockManagerProtocol
from crackerjack.models.task import HookResult
from crackerjack.services.regex_patterns import SAFE_PATTERNS


@dataclass
class HookProgress:
    hook_name: str
    status: str
    start_time: float
    end_time: float | None = None
    duration: float | None = None
    errors_found: int = 0
    warnings_found: int = 0
    files_processed: int = 0
    lines_processed: int = 0
    output_lines: list[str] | None = None
    error_details: list[dict[str, t.Any]] | None = None

    def __post_init__(self) -> None:
        if self.output_lines is None:
            self.output_lines = []
        if self.error_details is None:
            self.error_details = []
        if self.end_time and self.start_time:
            self.duration = self.end_time - self.start_time

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "hook_name": self.hook_name,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "errors_found": self.errors_found,
            "warnings_found": self.warnings_found,
            "files_processed": self.files_processed,
            "lines_processed": self.lines_processed,
            "output_lines": self.output_lines[-10:] if self.output_lines else [],
            "error_details": self.error_details,
        }


@dataclass
class IndividualExecutionResult:
    strategy_name: str
    hook_results: list[HookResult]
    hook_progress: list[HookProgress]
    total_duration: float
    success: bool
    execution_order: list[str]

    @property
    def failed_hooks(self) -> list[str]:
        return [p.hook_name for p in self.hook_progress if p.status == "failed"]

    @property
    def total_errors(self) -> int:
        return sum(p.errors_found for p in self.hook_progress)

    @property
    def total_warnings(self) -> int:
        return sum(p.warnings_found for p in self.hook_progress)


class HookOutputParser:
    HOOK_PATTERNS: dict[str, dict[str, str]] = {
        "ruff-check": {
            "error": "ruff_check_error",
            "summary": "ruff_check_summary",
        },
        "pyright": {
            "error": "pyright_error",
            "warning": "pyright_warning",
            "summary": "pyright_summary",
        },
        "bandit": {
            "issue": "bandit_issue",
            "location": "bandit_location",
            "confidence": "bandit_confidence",
            "severity": "bandit_severity",
        },
        "mypy": {
            "error": "mypy_error",
            "note": "mypy_note",
        },
        "vulture": {
            "unused": "vulture_unused",
        },
        "complexipy": {
            "complex": "complexipy_complex",
        },
    }

    def parse_hook_output(
        self,
        hook_name: str,
        output_lines: list[str],
    ) -> dict[str, t.Any]:
        if hook_name not in self.HOOK_PATTERNS:
            return self._parse_generic_output(output_lines)

        result: dict[str, t.Any] = {
            "errors": [],
            "warnings": [],
            "files_processed": set(),
        }
        patterns = self.HOOK_PATTERNS[hook_name]

        parser_map = {
            "ruff-check": self._parse_ruff_check,
            "pyright": self._parse_pyright,
            "bandit": self._parse_bandit,
            "vulture": self._parse_vulture,
            "complexipy": self._parse_complexipy,
        }

        parser_map.get(hook_name, self._parse_default_hook)(
            output_lines, patterns, result
        )

        result["files_processed"] = list[t.Any](result["files_processed"])
        return result

    def _parse_ruff_check(
        self,
        output_lines: list[str],
        patterns: dict[str, str],
        result: dict[str, t.Any],
    ) -> None:
        error_pattern = SAFE_PATTERNS[patterns["error"]]._get_compiled_pattern()

        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := error_pattern.match(line):
                assert match is not None  # Type checker: match cannot be None here
                file_path, line_num, col_num, code, message = match.groups()
                result["files_processed"].add(file_path)
                result["errors"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "code": code,
                        "message": message,
                        "type": "error",
                    },
                )

    def _parse_pyright(
        self,
        output_lines: list[str],
        patterns: dict[str, str],
        result: dict[str, t.Any],
    ) -> None:
        error_pattern = SAFE_PATTERNS[patterns["error"]]._get_compiled_pattern()
        warning_pattern = SAFE_PATTERNS[patterns["warning"]]._get_compiled_pattern()

        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := error_pattern.match(line):
                assert match is not None  # Type checker: match cannot be None here
                file_path, line_num, col_num, message = match.groups()
                result["files_processed"].add(file_path)
                result["errors"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "message": message,
                        "type": "error",
                    },
                )
            elif match := warning_pattern.match(line):
                assert match is not None  # Type checker: match cannot be None here
                file_path, line_num, col_num, message = match.groups()
                result["files_processed"].add(file_path)
                result["warnings"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "message": message,
                        "type": "warning",
                    },
                )

    def _parse_bandit(
        self,
        output_lines: list[str],
        patterns: dict[str, str],
        result: dict[str, t.Any],
    ) -> None:
        issue_pattern = SAFE_PATTERNS[patterns["issue"]]._get_compiled_pattern()

        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := issue_pattern.match(line):
                assert match is not None  # Type checker: match cannot be None here
                code, message = match.groups()
                result["errors"].append(
                    {"code": code, "message": message, "type": "security"},
                )

    def _parse_vulture(
        self,
        output_lines: list[str],
        patterns: dict[str, str],
        result: dict[str, t.Any],
    ) -> None:
        unused_pattern = SAFE_PATTERNS[patterns["unused"]]._get_compiled_pattern()

        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := unused_pattern.match(line):
                assert match is not None  # Type checker: match cannot be None here
                file_path, line_num, item_type, item_name = match.groups()
                result["files_processed"].add(file_path)
                result["warnings"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "message": f"unused {item_type} '{item_name}'",
                        "type": "unused_code",
                    },
                )

    def _parse_complexipy(
        self,
        output_lines: list[str],
        patterns: dict[str, str],
        result: dict[str, t.Any],
    ) -> None:
        complex_pattern = SAFE_PATTERNS[patterns["complex"]]._get_compiled_pattern()

        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := complex_pattern.match(line):
                assert match is not None  # Type checker: match cannot be None here
                file_path, line_num, col_num, function_name, complexity = match.groups()
                result["files_processed"].add(file_path)
                result["errors"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "message": f"{function_name} is too complex ({complexity})",
                        "type": "complexity",
                    },
                )

    def _parse_default_hook(
        self,
        output_lines: list[str],
        patterns: dict[str, str],
        result: dict[str, t.Any],
    ) -> None:
        for line in output_lines:
            line = line.strip()
            if not line:
                continue

            if "error" in line.lower() or "fail" in line.lower():
                result["errors"].append(
                    {
                        "message": line,
                        "type": "generic_error",
                    },
                )
            elif "warning" in line.lower():
                result["warnings"].append(
                    {
                        "message": line,
                        "type": "generic_warning",
                    },
                )

    def _parse_generic_output(self, output_lines: list[str]) -> dict[str, t.Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        error_keywords = ["error", "failed", "violation", "issue"]
        warning_keywords = ["warning", "caution", "note"]

        for line in output_lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in error_keywords):
                errors.append({"message": line.strip(), "type": "generic_error"})
            elif any(keyword in line_lower for keyword in warning_keywords):
                warnings.append({"message": line.strip(), "type": "generic_warning"})

        return {
            "errors": errors,
            "warnings": warnings,
            "files_processed": 0,
            "total_lines": len(output_lines),
        }


class IndividualHookExecutor:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        hook_lock_manager: HookLockManagerProtocol | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.parser = HookOutputParser()
        self.progress_callback: t.Callable[[HookProgress], None] | None = None
        self.suppress_realtime_output = False
        self.progress_callback_interval = 1
        self.hook_lock_manager: HookLockManagerProtocol

        if hook_lock_manager is None:
            from crackerjack.executors.hook_lock_manager import (
                hook_lock_manager as default_manager,
            )

            # Type cast: default_manager implements the protocol interface
            self.hook_lock_manager = t.cast(HookLockManagerProtocol, default_manager)
        else:
            self.hook_lock_manager = hook_lock_manager

    def set_progress_callback(self, callback: t.Callable[[HookProgress], None]) -> None:
        self.progress_callback = callback

    def set_mcp_mode(self, enable: bool = True) -> None:
        self.suppress_realtime_output = enable
        if enable:
            self.progress_callback_interval = 10

    async def execute_strategy_individual(
        self,
        strategy: HookStrategy,
    ) -> IndividualExecutionResult:
        """Execute hook strategy with individual (sequential) execution and progress tracking."""
        start_time = time.time()
        self._print_strategy_header(strategy)

        execution_state = self._initialize_execution_state()

        for hook in strategy.hooks:
            await self._execute_single_hook_in_strategy(hook, execution_state)

        return self._finalize_execution_result(strategy, execution_state, start_time)

    async def execute_strategy(
        self,
        strategy: HookStrategy,
    ) -> HookExecutionResult:  # Changed return type to match base class
        """Execute hook strategy - API-compatible method matching other executors."""
        start_time = time.time()
        self._print_strategy_header(strategy)

        execution_state = self._initialize_execution_state()

        for hook in strategy.hooks:
            await self._execute_single_hook_in_strategy(hook, execution_state)

        # Call finalize with original strategy name instead of modified one
        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in execution_state["hook_results"])

        self._print_individual_summary(
            strategy,
            execution_state["hook_results"],
            execution_state["hook_progress"],
        )

        # Return HookExecutionResult to maintain interface compatibility
        return HookExecutionResult(
            strategy_name=strategy.name,  # Use original name, not with "_individual" suffix
            results=execution_state["hook_results"],
            total_duration=total_duration,
            success=success,
        )

    def _initialize_execution_state(self) -> dict[str, t.Any]:
        return {"hook_results": [], "hook_progress": [], "execution_order": []}

    async def _execute_single_hook_in_strategy(
        self,
        hook: HookDefinition,
        execution_state: dict[str, t.Any],
    ) -> None:
        execution_state["execution_order"].append(hook.name)

        progress = HookProgress(
            hook_name=hook.name,
            status="pending",
            start_time=time.time(),
        )
        execution_state["hook_progress"].append(progress)

        result = await self._execute_individual_hook(hook, progress)
        execution_state["hook_results"].append(result)

        self._update_hook_progress_status(progress, result)

    def _update_hook_progress_status(
        self,
        progress: HookProgress,
        result: HookResult,
    ) -> None:
        progress.status = "completed" if result.status == "passed" else "failed"
        progress.end_time = time.time()
        progress.duration = progress.end_time - progress.start_time

        if self.progress_callback:
            self.progress_callback(progress)

    def _finalize_execution_result(
        self,
        strategy: HookStrategy,
        execution_state: dict[str, t.Any],
        start_time: float,
    ) -> IndividualExecutionResult:
        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in execution_state["hook_results"])

        self._print_individual_summary(
            strategy,
            execution_state["hook_results"],
            execution_state["hook_progress"],
        )

        return IndividualExecutionResult(
            strategy_name=f"{strategy.name}_individual",
            hook_results=execution_state["hook_results"],
            hook_progress=execution_state["hook_progress"],
            total_duration=total_duration,
            success=success,
            execution_order=execution_state["execution_order"],
        )

    async def _execute_individual_hook(
        self,
        hook: HookDefinition,
        progress: HookProgress,
    ) -> HookResult:
        progress.status = "running"
        if self.progress_callback:
            self.progress_callback(progress)

        # Don't print verbose "Running..." messages - the dotted-line format shows status
        cmd = hook.get_command()

        try:
            async with self.hook_lock_manager.acquire_hook_lock(hook.name):  # type: ignore[attr-defined]
                result = await self._run_command_with_streaming(
                    cmd, hook.timeout, progress
                )

                parsed_output = self.parser.parse_hook_output(
                    hook.name,
                    progress.output_lines or [],
                )
                progress.errors_found = len(parsed_output["errors"])
                progress.warnings_found = len(parsed_output["warnings"])
                progress.files_processed = parsed_output["files_processed"]
                progress.lines_processed = parsed_output["total_lines"]
                progress.error_details = (
                    parsed_output["errors"] + parsed_output["warnings"]
                )

                status = "passed" if result.returncode == 0 else "failed"
                # Ensure failed hooks always have at least 1 issue count
                issues_count = 1 if status == "failed" else 0

                hook_result = HookResult(
                    id=hook.name,
                    name=hook.name,
                    status=status,
                    duration=progress.duration or 0,
                    issues_count=issues_count,
                )

                self._print_hook_summary(hook.name, hook_result, progress)

                return hook_result

        except TimeoutError:
            progress.status = "failed"
            error_msg = f"Hook {hook.name} timed out after {hook.timeout}s"
            self.console.print(f"[red]⏰ {error_msg}[/ red]")

            return HookResult(
                id=hook.name,
                name=hook.name,
                status="failed",
                duration=hook.timeout,
                issues_count=1,  # Timeout counts as 1 issue
            )
        except Exception as e:
            progress.status = "failed"
            error_msg = f"Hook {hook.name} failed with error: {e}"
            self.console.print(f"[red]❌ {error_msg}[/ red]")

            return HookResult(
                id=hook.name,
                name=hook.name,
                status="failed",
                duration=progress.duration or 0,
                issues_count=1,  # Error counts as 1 issue
            )

    async def _run_command_with_streaming(
        self,
        cmd: list[str],
        timeout: int,
        progress: HookProgress,
    ) -> subprocess.CompletedProcess[str]:
        process = await self._create_subprocess(cmd)

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        tasks = self._create_stream_reader_tasks(
            process,
            stdout_lines,
            stderr_lines,
            progress,
        )

        try:
            await self._wait_for_process_completion(process, tasks, timeout)
        except TimeoutError:
            self._handle_process_timeout(process, tasks)
            raise

        return self._create_completed_process(cmd, process, stdout_lines, stderr_lines)

    async def _create_subprocess(self, cmd: list[str]) -> asyncio.subprocess.Process:
        # Use pkg_path directly as the working directory for hook execution
        # This ensures hooks run in the correct project directory regardless of project name
        return await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.pkg_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    def _create_stream_reader_tasks(
        self,
        process: asyncio.subprocess.Process,
        stdout_lines: list[str],
        stderr_lines: list[str],
        progress: HookProgress,
    ) -> list[asyncio.Task[None]]:
        return [
            asyncio.create_task(
                self._read_stream(process.stdout, stdout_lines, progress),
            ),
            asyncio.create_task(
                self._read_stream(process.stderr, stderr_lines, progress),
            ),
        ]

    async def _read_stream(
        self,
        stream: asyncio.StreamReader | None,
        output_list: list[str],
        progress: HookProgress,
    ) -> None:
        if not stream:
            return

        line_count = 0
        while True:
            try:
                line = await stream.readline()
                if not line:
                    break

                line_str = self._process_stream_line(line)
                self._update_progress_with_line(
                    line_str,
                    output_list,
                    progress,
                    line_count,
                )
                line_count += 1

            except Exception:
                break

    def _process_stream_line(self, line: bytes | str) -> str:
        return (line.decode() if isinstance(line, bytes) else line).rstrip()

    def _update_progress_with_line(
        self,
        line_str: str,
        output_list: list[str],
        progress: HookProgress,
        line_count: int,
    ) -> None:
        output_list.append(line_str)
        progress.output_lines = progress.output_lines or []
        progress.output_lines.append(line_str)

        self._maybe_print_line(line_str)
        self._maybe_callback_progress(progress, line_count)

    def _maybe_print_line(self, line_str: str) -> None:
        if not self.suppress_realtime_output and line_str.strip():
            self.console.print(f"[dim] {line_str}[/ dim]")

    def _maybe_callback_progress(self, progress: HookProgress, line_count: int) -> None:
        if self.progress_callback and (
            line_count % self.progress_callback_interval == 0
        ):
            self.progress_callback(progress)

    @staticmethod
    async def _wait_for_process_completion(
        process: asyncio.subprocess.Process,
        tasks: list[asyncio.Task[None]],
        timeout: int,
    ) -> None:
        await asyncio.wait_for(process.wait(), timeout=timeout)
        await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _handle_process_timeout(
        process: asyncio.subprocess.Process,
        tasks: list[asyncio.Task[None]],
    ) -> None:
        process.kill()
        for task in tasks:
            task.cancel()

    @staticmethod
    def _create_completed_process(
        cmd: list[str],
        process: asyncio.subprocess.Process,
        stdout_lines: list[str],
        stderr_lines: list[str],
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode or 0,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
        )

    def _print_strategy_header(self, strategy: HookStrategy) -> None:
        self.console.print("\n" + "=" * 80)
        self.console.print(
            f"[bold bright_cyan]🔍 INDIVIDUAL HOOK EXECUTION[/ bold bright_cyan] "
            f"[bold bright_white]{strategy.name.upper()} HOOKS[/ bold bright_white]",
        )
        self.console.print(
            f"[dim]Running {len(strategy.hooks)} hooks individually with real-time streaming[/ dim]",
        )
        self.console.print("=" * 80)

    def _print_hook_summary(
        self,
        hook_name: str,
        result: HookResult,
        progress: HookProgress,
    ) -> None:
        """Print hook result in dotted-line format matching pre-commit style.

        Format: hook-name.......................................... ✅
        """
        status_icon = "✅" if result.status == "passed" else "❌"

        # Calculate dotted line (same logic as base HookExecutor)
        max_width = get_console_width()
        content_width = max_width - 4  # Adjusted for icon and padding

        if len(hook_name) > content_width:
            line = hook_name[: content_width - 3] + "..."
        else:
            dots_needed = max(0, content_width - len(hook_name))
            line = hook_name + ("." * dots_needed)

        self.console.print(f"{line} {status_icon}")

    def _print_individual_summary(
        self,
        strategy: HookStrategy,
        results: list[HookResult],
        progress_list: list[HookProgress],
    ) -> None:
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        total_errors = sum(p.errors_found for p in progress_list)
        total_warnings = sum(p.warnings_found for p in progress_list)
        total_duration = sum(p.duration or 0 for p in progress_list)

        self.console.print("\n" + make_separator("-", get_console_width()))
        self.console.print(
            f"[bold]📊 INDIVIDUAL EXECUTION SUMMARY[/ bold]-{strategy.name.upper()}",
        )
        self.console.print(f"✅ Passed: {passed} | ❌ Failed: {failed}")
        if total_errors > 0:
            self.console.print(f"🚨 Total Errors: {total_errors}")
        if total_warnings > 0:
            self.console.print(f"⚠️ Total Warnings: {total_warnings}")
        self.console.print(f"⏱️ Total Duration: {total_duration: .1f}s")

        if failed > 0:
            self.console.print("\n[bold red]Failed Hooks: [/ bold red]")
            for progress in progress_list:
                if progress.status == "failed":
                    error_summary = (
                        f"{progress.errors_found} errors"
                        if progress.errors_found > 0
                        else "failed"
                    )
                    self.console.print(f" ❌ {progress.hook_name}-{error_summary}")

        self.console.print(make_separator("-", get_console_width()))
