import asyncio
import re
import subprocess
import time
import typing as t
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ..config.hooks import HookDefinition, HookStrategy
from ..models.task import HookResult


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
    HOOK_PATTERNS = {
        "ruff-check": {
            "error": re.compile(r"^(.+?):(\d+):(\d+):([A-Z]\d+) (.+)$"),
            "summary": re.compile(r"Found (\d+) error"),
        },
        "pyright": {
            "error": re.compile(r"^(.+?):(\d+):(\d+) - error: (.+)$"),
            "warning": re.compile(r"^(.+?):(\d+):(\d+) - warning: (.+)$"),
            "summary": re.compile(r"(\d+) error[s]?, (\d+) warning[s]?"),
        },
        "bandit": {
            "issue": re.compile(r" >> Issue: \[([A-Z]\d+): \w+\] (.+)"),
            "location": re.compile(r" Location: (.+?):(\d+):(\d+)"),
            "confidence": re.compile(r" Confidence: (\w+)"),
            "severity": re.compile(r" Severity: (\w+)"),
        },
        "mypy": {
            "error": re.compile(r"^(.+?):(\d+): error: (.+)$"),
            "note": re.compile(r"^(.+?):(\d+): note: (.+)$"),
        },
        "vulture": {
            "unused": re.compile(r"^(.+?):(\d+): unused (.+) '(.+)'"),
        },
        "complexipy": {
            "complex": re.compile(
                r"^(.+?):(\d+):(\d+) - (.+) is too complex \((\d+)\)"
            ),
        },
    }

    def parse_hook_output(
        self, hook_name: str, output_lines: list[str]
    ) -> dict[str, t.Any]:
        if hook_name not in self.HOOK_PATTERNS:
            return self._parse_generic_output(output_lines)

        result = {"errors": [], "warnings": [], "files_processed": set()}
        patterns = self.HOOK_PATTERNS[hook_name]

        parser_map = {
            "ruff-check": self._parse_ruff_check,
            "pyright": self._parse_pyright,
            "bandit": self._parse_bandit,
            "vulture": self._parse_vulture,
            "complexipy": self._parse_complexipy,
        }

        parser = parser_map.get(hook_name, self._parse_default_hook)
        parser(output_lines, patterns, result)

        result["files_processed"] = list(result["files_processed"])
        return result

    def _parse_ruff_check(
        self, output_lines: list[str], patterns: dict, result: dict
    ) -> None:
        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := patterns["error"].match(line):
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
                    }
                )

    def _parse_pyright(
        self, output_lines: list[str], patterns: dict, result: dict
    ) -> None:
        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := patterns["error"].match(line):
                file_path, line_num, col_num, message = match.groups()
                result["files_processed"].add(file_path)
                result["errors"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "message": message,
                        "type": "error",
                    }
                )
            elif match := patterns["warning"].match(line):
                file_path, line_num, col_num, message = match.groups()
                result["files_processed"].add(file_path)
                result["warnings"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "message": message,
                        "type": "warning",
                    }
                )

    def _parse_bandit(
        self, output_lines: list[str], patterns: dict, result: dict
    ) -> None:
        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := patterns["issue"].match(line):
                code, message = match.groups()
                result["errors"].append(
                    {"code": code, "message": message, "type": "security"}
                )

    def _parse_vulture(
        self, output_lines: list[str], patterns: dict, result: dict
    ) -> None:
        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := patterns["unused"].match(line):
                file_path, line_num, item_type, item_name = match.groups()
                result["files_processed"].add(file_path)
                result["warnings"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "message": f"unused {item_type} '{item_name}'",
                        "type": "unused_code",
                    }
                )

    def _parse_complexipy(
        self, output_lines: list[str], patterns: dict, result: dict
    ) -> None:
        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            if match := patterns["complex"].match(line):
                file_path, line_num, col_num, function_name, complexity = match.groups()
                result["files_processed"].add(file_path)
                result["errors"].append(
                    {
                        "file": file_path,
                        "line": int(line_num),
                        "column": int(col_num),
                        "message": f"{function_name} is too complex ({complexity})",
                        "type": "complexity",
                    }
                )

    def _parse_default_hook(
        self, output_lines: list[str], patterns: dict, result: dict
    ) -> None:
        # Default parser for hooks not specifically handled
        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            # Simple heuristic - if it looks like an error, treat it as one
            if "error" in line.lower() or "fail" in line.lower():
                result["errors"].append(
                    {
                        "message": line,
                        "type": "generic_error",
                    }
                )
            elif "warning" in line.lower():
                result["warnings"].append(
                    {
                        "message": line,
                        "type": "generic_warning",
                    }
                )

    def _parse_generic_output(self, output_lines: list[str]) -> dict[str, t.Any]:
        errors = []
        warnings = []

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
    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.parser = HookOutputParser()
        self.progress_callback: t.Callable[[HookProgress], None] | None = None
        self.suppress_realtime_output = False
        self.progress_callback_interval = (
            1  # Only callback every N lines to reduce overhead
        )

    def set_progress_callback(self, callback: t.Callable[[HookProgress], None]) -> None:
        self.progress_callback = callback

    def set_mcp_mode(self, enable: bool = True) -> None:
        """Enable MCP mode which suppresses real-time output to prevent terminal lockup."""
        self.suppress_realtime_output = enable
        if enable:
            self.progress_callback_interval = (
                10  # Reduce callback frequency in MCP mode
            )

    async def execute_strategy_individual(
        self, strategy: HookStrategy
    ) -> IndividualExecutionResult:
        start_time = time.time()

        self._print_strategy_header(strategy)

        hook_results: list[HookResult] = []
        hook_progress: list[HookProgress] = []
        execution_order: list[str] = []

        for hook in strategy.hooks:
            execution_order.append(hook.name)

            progress = HookProgress(
                hook_name=hook.name,
                status="pending",
                start_time=time.time(),
            )
            hook_progress.append(progress)

            result = await self._execute_individual_hook(hook, progress)
            hook_results.append(result)

            progress.status = "completed" if result.status == "passed" else "failed"
            progress.end_time = time.time()
            progress.duration = progress.end_time - progress.start_time

            if self.progress_callback:
                self.progress_callback(progress)

        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in hook_results)

        self._print_individual_summary(strategy, hook_results, hook_progress)

        return IndividualExecutionResult(
            strategy_name=f"{strategy.name}_individual",
            hook_results=hook_results,
            hook_progress=hook_progress,
            total_duration=total_duration,
            success=success,
            execution_order=execution_order,
        )

    async def _execute_individual_hook(
        self, hook: HookDefinition, progress: HookProgress
    ) -> HookResult:
        progress.status = "running"
        if self.progress_callback:
            self.progress_callback(progress)

        self.console.print(f"\n[bold cyan]🔍 Running {hook.name}[/bold cyan]")

        cmd = hook.get_command()

        try:
            result = await self._run_command_with_streaming(cmd, hook.timeout, progress)

            parsed_output = self.parser.parse_hook_output(
                hook.name, progress.output_lines or []
            )
            progress.errors_found = len(parsed_output["errors"])
            progress.warnings_found = len(parsed_output["warnings"])
            progress.files_processed = parsed_output["files_processed"]
            progress.lines_processed = parsed_output["total_lines"]
            progress.error_details = parsed_output["errors"] + parsed_output["warnings"]

            hook_result = HookResult(
                name=hook.name,
                status="passed" if result.returncode == 0 else "failed",
                duration=progress.duration or 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )

            self._print_hook_summary(hook.name, hook_result, progress)

            return hook_result

        except TimeoutError:
            progress.status = "failed"
            error_msg = f"Hook {hook.name} timed out after {hook.timeout}s"
            self.console.print(f"[red]⏰ {error_msg}[/red]")

            return HookResult(
                name=hook.name,
                status="failed",
                duration=hook.timeout,
                output="",
                error=error_msg,
            )

    async def _run_command_with_streaming(
        self, cmd: list[str], timeout: int, progress: HookProgress
    ) -> subprocess.CompletedProcess[str]:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.pkg_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True,
        )

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        async def read_stream(
            stream: asyncio.StreamReader, output_list: list[str]
        ) -> None:
            line_count = 0
            while True:
                try:
                    line = await stream.readline()
                    if not line:
                        break

                    line_str = line.decode() if isinstance(line, bytes) else line
                    line_str = line_str.rstrip()

                    output_list.append(line_str)
                    progress.output_lines = progress.output_lines or []
                    progress.output_lines.append(line_str)
                    line_count += 1

                    # Only print to console if not suppressed (prevents MCP terminal lockup)
                    if not self.suppress_realtime_output and line_str.strip():
                        self.console.print(f"[dim] {line_str}[/dim]")

                    # Throttle progress callbacks to reduce overhead
                    if self.progress_callback and (
                        line_count % self.progress_callback_interval == 0
                    ):
                        self.progress_callback(progress)

                except Exception:
                    break

        tasks = [
            asyncio.create_task(read_stream(process.stdout, stdout_lines)),
            asyncio.create_task(read_stream(process.stderr, stderr_lines)),
        ]

        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)

            await asyncio.gather(*tasks, return_exceptions=True)

        except TimeoutError:
            process.kill()
            for task in tasks:
                task.cancel()
            raise

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode or 0,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
        )

    def _print_strategy_header(self, strategy: HookStrategy) -> None:
        self.console.print("\n" + "=" * 80)
        self.console.print(
            f"[bold bright_cyan]🔍 INDIVIDUAL HOOK EXECUTION[/bold bright_cyan] "
            f"[bold bright_white]{strategy.name.upper()} HOOKS[/bold bright_white]"
        )
        self.console.print(
            f"[dim]Running {len(strategy.hooks)} hooks individually with real-time streaming[/dim]"
        )
        self.console.print("=" * 80)

    def _print_hook_summary(
        self, hook_name: str, result: HookResult, progress: HookProgress
    ) -> None:
        status_icon = "✅" if result.status == "passed" else "❌"
        duration_str = f"{progress.duration:.1f}s" if progress.duration else "0.0s"

        summary_parts = []
        if progress.errors_found > 0:
            summary_parts.append(f"{progress.errors_found} errors")
        if progress.warnings_found > 0:
            summary_parts.append(f"{progress.warnings_found} warnings")
        if progress.files_processed > 0:
            summary_parts.append(f"{progress.files_processed} files")

        summary = ", ".join(summary_parts) if summary_parts else "clean"

        self.console.print(
            f"[bold]{status_icon} {hook_name}[/bold] - {duration_str} - {summary}"
        )

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

        self.console.print("\n" + "-" * 80)
        self.console.print(
            f"[bold]📊 INDIVIDUAL EXECUTION SUMMARY[/bold] - {strategy.name.upper()}"
        )
        self.console.print(f"✅ Passed: {passed} | ❌ Failed: {failed}")
        if total_errors > 0:
            self.console.print(f"🚨 Total Errors: {total_errors}")
        if total_warnings > 0:
            self.console.print(f"⚠️ Total Warnings: {total_warnings}")
        self.console.print(f"⏱️ Total Duration: {total_duration:.1f}s")

        if failed > 0:
            self.console.print("\n[bold red]Failed Hooks: [/bold red]")
            for progress in progress_list:
                if progress.status == "failed":
                    error_summary = (
                        f"{progress.errors_found} errors"
                        if progress.errors_found > 0
                        else "failed"
                    )
                    self.console.print(f" ❌ {progress.hook_name} - {error_summary}")

        self.console.print("-" * 80)
