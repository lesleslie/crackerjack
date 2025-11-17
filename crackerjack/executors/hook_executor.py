import json
import os
import subprocess
import time
import typing as t
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from acb.console import Console

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
        # Optional progress callbacks used when orchestration is disabled
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
        """Set optional progress callbacks for legacy execution.

        Args:
            started_cb: Called when a hook starts with (started, total)
            completed_cb: Called when a hook completes with (completed, total)
            total: Total number of hooks (defaults to len(strategy.hooks))
        """
        self._progress_start_callback = started_cb
        self._progress_callback = completed_cb
        self._total_hooks = int(total or 0)
        self._started_hooks = 0
        self._completed_hooks = 0

    def execute_strategy(self, strategy: HookStrategy) -> HookExecutionResult:
        start_time = time.time()

        # Header is displayed by PhaseCoordinator; suppress here to avoid duplicates

        results = self._execute_hooks(strategy)

        results = self._apply_retries_if_needed(strategy, results)

        return self._create_execution_result(strategy, results, start_time)

    def _execute_hooks(self, strategy: HookStrategy) -> list[HookResult]:
        """Execute hooks based on strategy configuration."""
        if strategy.parallel and len(strategy.hooks) > 1:
            return self._execute_parallel(strategy)
        return self._execute_sequential(strategy)

    def _apply_retries_if_needed(
        self, strategy: HookStrategy, results: list[HookResult]
    ) -> list[HookResult]:
        """Apply retries if the strategy requires it."""
        if strategy.retry_policy != RetryPolicy.NONE:
            return self._handle_retries(strategy, results)
        return results

    def _create_execution_result(
        self, strategy: HookStrategy, results: list[HookResult], start_time: float
    ) -> HookExecutionResult:
        """Create the final execution result with performance metrics."""
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
        """Calculate the performance gain from parallel execution."""
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
        # Intentionally no-op: PhaseCoordinator controls stage headers
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
        """Handle progress start callback."""
        if self._progress_start_callback:
            with suppress(Exception):
                self._started_hooks += 1
                total = self._total_hooks or total_hooks
                self._progress_start_callback(self._started_hooks, total)

    def _handle_progress_completion(self, total_hooks: int) -> None:
        """Handle progress completion callback."""
        if self._progress_callback:
            with suppress(Exception):
                self._completed_hooks += 1
                total = self._total_hooks or total_hooks
                self._progress_callback(self._completed_hooks, total)

    def _execute_parallel(self, strategy: HookStrategy) -> list[HookResult]:
        results: list[HookResult] = []

        formatting_hooks = [h for h in strategy.hooks if h.is_formatting]
        other_hooks = [h for h in strategy.hooks if not h.is_formatting]

        # Execute formatting hooks sequentially first
        for hook in formatting_hooks:
            self._execute_single_hook_with_progress(hook, results)

        # Execute other hooks in parallel
        if other_hooks:
            self._execute_parallel_hooks(other_hooks, strategy, results)

        return results

    def _execute_single_hook_with_progress(
        self, hook: HookDefinition, results: list[HookResult]
    ) -> None:
        """Execute a single hook and update progress callbacks."""
        if self._progress_start_callback:
            with suppress(Exception):
                self._started_hooks += 1
                total = self._total_hooks or len(results) + 1  # Approximate total
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
        """Execute non-formatting hooks in parallel."""

        # Use helper function to run hooks with progress tracking
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
        """Create a function that runs a hook with progress tracking."""

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
        """Handle the result of a completed future from thread pool execution."""
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
                issues_count=1,  # Error counts as 1 issue
                stage=hook.stage.value,
                exit_code=1,
                error_message=str(e),
                is_timeout=False,
            )
            results.append(error_result)
            self._display_hook_result(error_result)
            self._update_progress_on_completion()

    def _update_progress_on_completion(self) -> None:
        """Update progress callback when a hook completes."""
        if self._progress_callback:
            with suppress(Exception):
                self._completed_hooks += 1
                total = self._total_hooks or self._completed_hooks  # Approximate total
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
        """Get changed files for incremental execution if supported.

        Returns:
            List of changed files if incremental mode enabled and hook supports it,
            None if full scan should be used (no changes or hook doesn't support files)
        """
        if not self.use_incremental or not hook.accepts_file_paths:
            return None

        if not self.git_service:
            return None

        # Map hook names to file extensions
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
            "trailing-whitespace": [""],  # All files
            "end-of-file-fixer": [""],  # All files
        }

        extensions = extension_map.get(hook.name)
        if not extensions:
            return None

        changed_files = self.git_service.get_changed_files_by_extension(extensions)

        # If no files changed, return None to skip the hook entirely
        # (or run full scan depending on configuration)
        return changed_files or None

    def _run_hook_subprocess(
        self, hook: HookDefinition
    ) -> subprocess.CompletedProcess[str]:
        clean_env = self._get_clean_environment()

        try:
            repo_root = self.pkg_path

            # Get changed files for incremental execution
            changed_files = self._get_changed_files_for_hook(hook)

            # Use build_command with files if incremental, otherwise get_command
            command = (
                hook.build_command(changed_files)
                if changed_files
                else hook.get_command()
            )

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

    def _display_hook_output_if_needed(
        self, result: subprocess.CompletedProcess[str], hook_name: str = ""
    ) -> None:
        # For complexipy, only show output when --debug flag is set
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
        # Determine initial status
        status = self._determine_initial_status(hook, result)

        # Extract issues
        issues_found = self._extract_issues_from_process_output(hook, result, status)

        # Update status for reporting tools
        status = self._update_status_for_reporting_tools(
            hook, status, issues_found, result
        )

        # Parse hook output to extract file count
        parsed_output = self._parse_hook_output(result, hook.name)

        # Determine exit code and error message
        exit_code, error_message = self._determine_exit_code_and_error(status, result)

        # Handle case where hook failed but has no parsed issues
        issues_found = self._handle_no_issues_for_failed_hook(
            status, issues_found, result
        )

        # Calculate issue count
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
            is_timeout=False,  # Set by timeout handler if applicable
        )

    def _determine_initial_status(
        self, hook: HookDefinition, result: subprocess.CompletedProcess[str]
    ) -> str:
        """Determine the initial status of the hook."""
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
            # Initial status based on exit code
            return "passed" if result.returncode == 0 else "failed"

    def _update_status_for_reporting_tools(
        self,
        hook: HookDefinition,
        status: str,
        issues_found: list[str],
        result: subprocess.CompletedProcess[str] | None = None,
    ) -> str:
        """Update status for reporting tools if there are issues."""
        reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}

        if hook.name in reporting_tools and issues_found:
            status = "failed"

        # Debug: Log status for reporting tools
        if hook.name in reporting_tools and self.debug and result:
            self.console.print(
                f"[yellow]DEBUG {hook.name}: returncode={result.returncode}, "
                f"issues={len(issues_found)}, status={status}[/yellow]"
            )

        return status

    def _determine_exit_code_and_error(
        self, status: str, result: subprocess.CompletedProcess[str]
    ) -> tuple[int | None, str | None]:
        """Determine exit code and error message."""
        exit_code = result.returncode if status == "failed" else None
        error_message = None
        if status == "failed" and result.stderr.strip():
            # Capture stderr for failed hooks (truncate if very long)
            error_message = result.stderr.strip()[:500]
        return exit_code, error_message

    def _handle_no_issues_for_failed_hook(
        self,
        status: str,
        issues_found: list[str],
        result: subprocess.CompletedProcess[str],
    ) -> list[str]:
        """Handle the case where a hook failed but has no parsed issues."""
        if status == "failed" and not issues_found:
            output_text = (result.stdout + result.stderr).strip()
            if output_text:
                # Split output into lines and take first 10 non-empty lines as issues
                error_lines = [
                    line.strip() for line in output_text.split("\n") if line.strip()
                ][:10]
                issues_found = error_lines or ["Hook failed with non-zero exit code"]
        return issues_found

    def _calculate_issues_count(self, status: str, issues_found: list[str]) -> int:
        """Calculate the number of issues."""
        return max(len(issues_found), 1 if status == "failed" else 0)

    def _extract_issues_from_process_output(
        self,
        hook: HookDefinition,
        result: subprocess.CompletedProcess[str],
        status: str,
    ) -> list[str]:
        error_output = (result.stdout + result.stderr).strip()

        # These tools are reporting/analysis tools that return exit code 0 even when finding issues
        # They need special parsing regardless of exit code status
        reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}

        if self.debug and hook.name in reporting_tools:
            self.console.print(
                f"[yellow]DEBUG _extract_issues: hook={hook.name}, status={status}, "
                f"output_len={len(error_output)}[/yellow]"
            )

        # Handle special parsing tools first
        if hook.name == "semgrep":
            return self._parse_semgrep_issues(error_output)

        # Handle reporting tools that always need parsing
        if hook.name in reporting_tools:
            return self._extract_issues_for_reporting_tools(hook, error_output)

        # For non-reporting tools, only parse output if they failed
        return self._extract_issues_for_regular_tools(
            hook, error_output, status, result
        )

    def _extract_issues_for_reporting_tools(
        self, hook: HookDefinition, error_output: str
    ) -> list[str]:
        """Extract issues from reporting tools."""
        # Always parse output for reporting tools (they exit 0 even with findings)
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
        """Extract issues from regular tools."""
        # For non-reporting tools, only parse output if they failed
        if status == "passed":
            return []

        if hook.is_formatting and "files were modified by this hook" in error_output:
            return []

        if error_output:
            return [line.strip() for line in error_output.split("\n") if line.strip()]

        return [f"Hook failed with code {result.returncode}"]

    def _is_header_or_separator_line(self, line: str) -> bool:
        """Check if the line is a header or separator line."""
        return any(x in line for x in ("Path", "─────", "┌", "└", "├", "┼", "┤", "┃"))

    def _extract_complexity_from_parts(self, parts: list[str]) -> int | None:
        """Extract complexity value from line parts."""
        if len(parts) >= 4:
            with suppress(ValueError, IndexError):
                return int(parts[-1])
        return None

    def _detect_package_from_output(self, output: str) -> str:
        """Auto-detect package name from tool output.

        Looks for common patterns like:
        - Table rows with paths: │ ./package_name/...
        - File paths: package_name/file.py

        Returns:
            Detected package name, or falls back to pkg_path detection
        """
        import re
        from collections import Counter

        # Try to extract from file paths in output (format: ./package_name/file.py)
        path_pattern = r"\./([a-z_][a-z0-9_]*)/[a-z_]"
        matches = re.findall(path_pattern, output, re.IGNORECASE)

        if matches:
            # Return most common package name found
            return Counter(matches).most_common(1)[0][0]

        # Fallback to detecting from pyproject.toml (existing logic)
        from crackerjack.config.tool_commands import _detect_package_name_cached

        return _detect_package_name_cached(str(self.pkg_path))

    def _should_include_line(self, line: str, package_name: str) -> bool:
        """Check if the line should be included in the output.

        Args:
            line: Line from complexipy output
            package_name: Name of the package being scanned

        Returns:
            True if line contains the package name and is a table row
        """
        return "│" in line and package_name in line

    def _parse_complexipy_issues(self, output: str) -> list[str]:
        """Parse complexipy table output to count actual violations (complexity > 15)."""
        # Auto-detect package name from output
        package_name = self._detect_package_from_output(output)

        issues = []
        for line in output.split("\n"):
            # Match table rows: │ path │ file │ function │ complexity │
            if self._should_include_line(line, package_name):
                # Skip header/separator rows
                if not self._is_header_or_separator_line(line):
                    # Extract complexity value (last column)
                    parts = [p.strip() for p in line.split("│") if p.strip()]
                    complexity = self._extract_complexity_from_parts(parts)
                    # Only count functions exceeding limit (15)
                    if complexity is not None and complexity > 15:
                        issues.append(line.strip())
        return issues

    def _parse_refurb_issues(self, output: str) -> list[str]:
        """Parse refurb output to count actual violations with shortened paths.

        Refurb output format: "path/to/file.py: line: col [FURB###]: message"
        Returns format: "relative/path.py:line [FURB###] message"
        """
        import re

        issues = []
        for line in output.split("\n"):
            if "[FURB" not in line or ":" not in line:
                continue

            # Match refurb format: path: line: col [FURB###]: message
            # Example: ./crackerjack/core/phase.py: 42: 10 [FURB123]: Use dict.get() instead
            # Note: Allow spaces after colons (": 42: 10" not ":42:10")
            match = re.search(
                r"(.+?):\s*(\d+):\s*\d+\s+\[(\w+)\]:\s*(.+)", line.strip()
            )

            if match:
                file_path, line_num, error_code, message = match.groups()

                # Shorten path to be relative to project root
                short_path = self._shorten_path(file_path)

                # Format: path:line [CODE] message
                formatted = f"{short_path}:{line_num} [{error_code}] {message.strip()}"
                issues.append(formatted)
            else:
                # Fallback: keep original line if parsing fails
                issues.append(line.strip())

        return issues

    def _shorten_path(self, path: str) -> str:
        """Shorten file path to be relative to project root.

        Args:
            path: Absolute or relative file path

        Returns:
            Shortened path relative to pkg_path, or basename if outside project
        """
        try:
            # Convert to Path object
            file_path = Path(path)

            # Try to make it relative to pkg_path if it's absolute
            if file_path.is_absolute():
                try:
                    relative = file_path.relative_to(self.pkg_path)
                    return str(relative).replace("\\", "/")
                except ValueError:
                    # Path is outside project, just use basename
                    return file_path.name

            # Already relative - clean up by removing leading "./"
            clean_path = str(file_path).lstrip("./")
            return clean_path.replace("\\", "/")

        except Exception:
            # Fallback: return original path
            return path

    def _parse_gitleaks_issues(self, output: str) -> list[str]:
        """Parse gitleaks output - ignore warnings, only count leaks."""
        # Gitleaks outputs "no leaks found" when clean
        if "no leaks found" in output.lower():
            return []
        return [
            line.strip()
            for line in output.split("\n")
            if not (
                "WRN" in line and "Invalid .gitleaksignore" in line
            )  # Skip warnings about .gitleaksignore format
            and any(
                x in line.lower() for x in ("leak", "secret", "credential", "api")
            )  # Look for actual leak findings
            and "found" not in line.lower()  # Skip summary lines
        ]

    def _parse_creosote_issues(self, output: str) -> list[str]:
        """Parse creosote output - only count unused dependencies."""
        if "No unused dependencies found" in output:
            return []
        issues = []
        parsing_unused = False
        for line in output.split("\n"):
            if "unused" in line.lower() and "dependenc" in line.lower():
                parsing_unused = True
                continue
            if parsing_unused and line.strip() and not line.strip().startswith("["):
                # Dependency names (not ANSI color codes)
                dep_name = line.strip().lstrip("- ")
                if dep_name:
                    issues.append(f"Unused dependency: {dep_name}")
            if not line.strip():
                parsing_unused = False
        return issues

    def _parse_semgrep_issues(self, output: str) -> list[str]:
        """Parse semgrep JSON output to extract both findings and errors.

        Semgrep returns JSON with two arrays:
        - "results": Security/code quality findings
        - "errors": Configuration, download, or execution errors

        Error categorization:
        - CODE_ERROR_TYPES: Actual code issues that should fail the build
        - INFRA_ERROR_TYPES: Infrastructure issues (network, timeouts) that should warn only

        This method extracts issues from both arrays to provide comprehensive error reporting.
        """
        import json

        try:
            # Try to parse as JSON
            json_data = json.loads(output.strip())
            issues = []

            # Extract findings from results array
            issues.extend(self._extract_semgrep_results(json_data))

            # Extract errors from errors array with categorization
            issues.extend(self._extract_semgrep_errors(json_data))

            return issues

        except json.JSONDecodeError:
            # If JSON parsing fails, return raw output (shouldn't happen with --json flag)
            if output.strip():
                return [line.strip() for line in output.split("\n") if line.strip()][
                    :10
                ]

        return []

    def _extract_semgrep_results(self, json_data: dict) -> list[str]:
        """Extract findings from semgrep results."""
        issues = []
        for result in json_data.get("results", []):
            # Format: "file.py:line - rule_id: message"
            path = result.get("path", "unknown")
            line_num = result.get("start", {}).get("line", "?")
            rule_id = result.get("check_id", "unknown-rule")
            message = result.get("extra", {}).get("message", "Security issue detected")
            issues.append(f"{path}:{line_num} - {rule_id}: {message}")
        return issues

    def _extract_semgrep_errors(self, json_data: dict) -> list[str]:
        """Extract errors from semgrep errors with categorization."""
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

            # Infrastructure errors: warn but don't fail the build
            if error_type in INFRA_ERROR_TYPES:
                self.console.print(
                    f"[yellow]Warning: Semgrep infrastructure error: "
                    f"{error_type}: {error_msg}[/yellow]"
                )
            else:
                # Code/config errors: add to issues (will fail the build)
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
            issues_count=1,  # Timeout counts as 1 issue
            stage=hook.stage.value,
            exit_code=124,  # Standard timeout exit code
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
            issues_count=1,  # Error counts as 1 issue
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

        # Special handling for semgrep to count files with issues, not total files scanned
        if hook_name == "semgrep":
            files_processed = self._parse_semgrep_output(result)
        else:
            files_processed = self._parse_generic_hook_output(output)

        return self._create_parse_result(files_processed, result.returncode, output)

    def _is_semgrep_output(self, output: str, args_str: str) -> bool:
        """Check if the output is from semgrep."""
        return "semgrep" in output.lower() or "semgrep" in args_str.lower()

    def _create_parse_result(
        self, files_processed: int, exit_code: int, output: str
    ) -> dict[str, t.Any]:
        """Create the parse result dictionary."""
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
        """Parse Semgrep output to count files with issues, not total files scanned."""

        # Try to extract JSON output from semgrep (if available)
        # Semgrep JSON output contains results with file paths
        json_files = self._parse_semgrep_json_output(result)
        if json_files is not None and json_files >= 0:
            # Successfully parsed JSON - return result (including 0 for no issues)
            return json_files

        # If we couldn't extract from JSON, try to parse from text output
        return self._parse_semgrep_text_output(result.stdout + result.stderr)

    def _parse_semgrep_json_output(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> int | None:
        """Parse Semgrep JSON output to count unique files with issues.

        Returns:
            int: Number of files with issues if JSON parsed successfully (including 0)
            None: If JSON parsing failed
        """
        # Look for JSON output between potentially mixed text output
        output = result.stdout + result.stderr
        return self._process_output_for_json(output)

    def _process_output_for_json(self, output: str) -> int | None:
        """Process output looking for JSON content.

        Returns:
            int: Number of files if JSON found (including 0 for no issues)
            None: If no valid JSON found
        """
        lines = output.splitlines()
        for line in lines:
            result = self._try_parse_line_json(line)
            if result is not None:
                return result
        return None

    def _try_parse_line_json(self, line: str) -> int | None:
        """Try to parse a line as JSON, checking both pure JSON and JSON with text.

        Returns:
            int: Number of files if JSON parsed successfully (including 0)
            None: If JSON parsing failed
        """
        line = line.strip()
        # Check if it's a pure JSON object
        if self._is_pure_json(line):
            result = self._parse_json_line(line)
            if result is not None:
                return result
        # Check if it contains JSON results
        if self._contains_json_results(line):
            result = self._parse_json_line(line)
            if result is not None:
                return result
        return None

    def _is_pure_json(self, line: str) -> bool:
        """Check if a line is a pure JSON object."""
        return line.startswith("{") and line.endswith("}")

    def _contains_json_results(self, line: str) -> bool:
        """Check if a line contains JSON results."""
        return '"results":' in line

    def _parse_json_line(self, line: str) -> int | None:
        """Parse a single JSON line to extract file count.

        Returns:
            int: Number of unique files with issues if JSON is valid (including 0)
            None: If JSON parsing failed
        """
        try:
            json_data = json.loads(line)
            if "results" in json_data:
                # Count unique file paths in results
                file_paths = {
                    result.get("path") for result in json_data.get("results", [])
                }
                return len([p for p in file_paths if p])  # Filter out None values
        except json.JSONDecodeError:
            pass
        return None

    def _parse_semgrep_text_output(self, output: str) -> int:
        """Parse Semgrep text output to extract file count."""
        import re

        # Look for patterns in Semgrep output that indicate findings
        # Example: "found 3 issues in 2 files" or "found no issues"
        semgrep_patterns = [
            r"found\s+(\d+)\s+issues?\s+in\s+(\d+)\s+files?",
            r"found\s+no\s+issues",
            r"scanning\s+(\d+)\s+files?",
        ]

        for pattern in semgrep_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                result = self._process_matches(matches, output)
                if result != -1:  # -1 means "continue to next pattern"
                    return result

        return 0

    def _process_matches(self, matches: list, output: str) -> int:
        """Process regex matches to extract file count."""
        for match in matches:
            if isinstance(match, tuple):
                if len(match) == 2:  # "found X issues in Y files" pattern
                    return self._handle_issues_in_files_match(match)
                elif len(match) == 1 and "no issues" not in output.lower():
                    # This would be from "scanning X files" - we don't want this for the files_processed
                    continue  # Return -1 to indicate continue
            elif "no issues" in output.lower():
                return 0
        return -1  # Indicates to continue to next pattern

    def _handle_issues_in_files_match(self, match: tuple) -> int:
        """Handle the 'found X issues in Y files' match."""
        issue_count, file_count = int(match[0]), int(match[1])
        # Use the number of files with issues, not total files scanned
        return file_count if issue_count > 0 else 0

    def _parse_generic_hook_output(self, output: str) -> int:
        """Parse output from other hooks (non-semgrep) to extract file count."""
        files_processed = 0

        # Check for common patterns in hook output (for other tools)
        if "files" in output.lower():
            files_processed = self._extract_file_count_from_patterns(output)

        # Special handling for ruff and other common tools
        if not files_processed and "ruff" in output.lower():
            # Look for patterns like "All checks passed!" with files processed elsewhere
            files_processed = self._extract_file_count_for_ruff_like_tools(output)

        return files_processed

    def _extract_file_count_from_patterns(self, output: str) -> int:
        """Extract file counts from common patterns in hook output."""
        import re

        # Pattern for "N file(s)" in output - return the highest found number
        all_matches = []
        file_count_patterns = [
            r"(\d+)\s+files?\s+would\s+be",  # "X files would be reformatted"
            r"(\d+)\s+files?\s+already\s+formatted",  # "X files already formatted"
            r"(\d+)\s+files?\s+processed",  # "X files processed"
            r"(\d+)\s+files?\s+checked",  # "X files checked"
            r"(\d+)\s+files?\s+analyzed",  # "X files analyzed"
            r"Checking\s+(\d+)\s+files?",  # "Checking 5 files"
            r"Found\s+(\d+)\s+files?",  # "Found 5 files"
            r"(\d+)\s+files?",  # "5 files" or "1 file" (general pattern)
        ]
        for pattern in file_count_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                # Convert all matches to integers and add to list
                all_matches.extend([int(m) for m in matches if m.isdigit()])

        # Use the highest value found
        if all_matches:
            return max(all_matches)

        return 0

    def _extract_file_count_for_ruff_like_tools(self, output: str) -> int:
        """Extract file counts for ruff-like tools that don't report files when all pass."""
        import re

        # Look for patterns like "All checks passed!" with files processed elsewhere
        all_passed_match = re.search(r"All\s+checks?\s+passed!", output, re.IGNORECASE)
        if all_passed_match:
            # For all-checks-passed scenarios, try to find other mentions of file counts
            other_matches = re.findall(r"(\d+)\s+files?", output, re.IGNORECASE)
            if other_matches:
                all_matches = [int(m) for m in other_matches if m.isdigit()]
                if all_matches:
                    return max(all_matches)  # Use highest value found

        return 0

    def _display_hook_result(self, result: HookResult) -> None:
        if self.quiet:
            return
        status_icon = "✅" if result.status == "passed" else "❌"

        max_width = get_console_width()
        content_width = max_width - 4  # Adjusted for icon and padding

        if len(result.name) > content_width:
            line = result.name[: content_width - 3] + "..."
        else:
            dots_needed = max(0, content_width - len(result.name))
            line = result.name + ("." * dots_needed)

        # Real-time inline hook status (dotted-line format)
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
        """Find the names of formatting hooks that failed."""
        formatting_hooks_failed: set[str] = set()

        for i, result in enumerate(results):
            hook = strategy.hooks[i]
            if hook.is_formatting and result.status == "failed":
                formatting_hooks_failed.add(hook.name)

        return formatting_hooks_failed

    def _retry_all_formatting_hooks(
        self, strategy: HookStrategy, results: list[HookResult]
    ) -> list[HookResult]:
        """Retry all formatting hooks."""
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
        """Find the indices of hooks that failed."""
        return [i for i, r in enumerate(results) if r.status == "failed"]

    def _retry_failed_hooks(
        self, strategy: HookStrategy, results: list[HookResult], failed_hooks: list[int]
    ) -> list[HookResult]:
        """Retry the failed hooks."""
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
        """Retry a single hook."""
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
        """Get the base environment variables."""
        return {
            "HOME": os.environ.get("HOME", ""),
            "USER": os.environ.get("USER", ""),
            "SHELL": os.environ.get("SHELL", "/bin/bash"),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "TERM": os.environ.get("TERM", "xterm-256color"),
        }

    def _update_path(self, clean_env: dict[str, str]) -> None:
        """Update the PATH environment variable."""
        system_path = os.environ.get("PATH", "")
        if system_path:
            venv_bin = str(Path(self.pkg_path) / ".venv" / "bin")
            path_parts = [p for p in system_path.split(os.pathsep) if p != venv_bin]
            clean_env["PATH"] = os.pathsep.join(path_parts)

    def _get_python_vars_to_exclude(self) -> set[str]:
        """Get the set of Python variables to exclude."""
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
