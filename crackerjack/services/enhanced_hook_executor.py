"""Enhanced hook executor integrating Phase 10.3 optimization infrastructure.

Phase 10.4.3: Integrates ToolProfiler, IncrementalExecutor, and ToolFilter
for optimized hook execution with performance tracking and caching.

Phase 10.4.5: Adds execution optimization with fast-first ordering and
parallel execution for independent tools.
"""

import concurrent.futures
from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.config.hooks import HookDefinition
from crackerjack.services.incremental_executor import (
    IncrementalExecutor,
)
from crackerjack.services.profiler import ToolProfiler
from crackerjack.services.tool_filter import FilterConfig, ToolFilter


@dataclass
class HookResult:
    """Result of executing a single hook."""

    hook_name: str
    success: bool
    output: str
    error: str | None = None
    execution_time: float = 0.0
    files_processed: int = 0
    files_cached: int = 0
    cache_hit_rate: float = 0.0


@dataclass
class ExecutionSummary:
    """Summary of hook execution session."""

    total_hooks: int
    hooks_run: int
    hooks_skipped: int
    hooks_succeeded: int
    hooks_failed: int
    total_execution_time: float
    filter_effectiveness: float = 0.0
    cache_effectiveness: float = 0.0
    results: list[HookResult] = field(default_factory=list)


class EnhancedHookExecutor:
    """Executes hooks with integrated optimization infrastructure.

    Combines:
    - ToolProfiler: Performance tracking and baseline metrics
    - IncrementalExecutor: File-level caching and changed file detection
    - ToolFilter: Selective execution based on --tool and --changed-only flags
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: int = 86400,  # 24 hours
    ):
        """Initialize enhanced hook executor.

        Args:
            cache_dir: Directory for cache storage (shared by profiler and executor)
            ttl_seconds: Time-to-live for cache entries
        """
        self.cache_dir = cache_dir or Path.cwd() / ".crackerjack" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.profiler = ToolProfiler(cache_dir=self.cache_dir)
        self.executor = IncrementalExecutor(
            cache_dir=self.cache_dir,
            ttl_seconds=ttl_seconds,
            profiler=self.profiler,
        )
        self.filter: ToolFilter | None = None

    def optimize_hook_order(self, hooks: list[HookDefinition]) -> list[HookDefinition]:
        """Sort hooks by execution time (fastest first).

        Phase 10.4.5: Enables fail-fast feedback by running fastest tools first.

        Args:
            hooks: List of hooks to optimize

        Returns:
            Hooks sorted by mean execution time (fastest first)
        """

        def get_exec_time(hook: HookDefinition) -> float:
            """Get mean execution time for a hook from profiler."""
            if hook.name in self.profiler.results:
                return self.profiler.results[hook.name].mean_time
            # Unknown tools run last (use timeout as estimate)
            return float(hook.timeout)

        return sorted(hooks, key=get_exec_time)

    def execute_hooks(
        self,
        hooks: list[HookDefinition],
        *,
        tool_filter: str | None = None,
        changed_only: bool = False,
        file_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        force_rerun: bool = False,
        optimize_order: bool = True,
        parallel: bool = False,
        max_workers: int = 3,
    ) -> ExecutionSummary:
        """Execute hooks with filtering, caching, profiling, and optimization.

        Phase 10.4.5: Adds fast-first ordering and parallel execution.

        Args:
            hooks: List of hook definitions to execute
            tool_filter: Run only specific tool (--tool flag)
            changed_only: Run only on changed files (--changed-only flag)
            file_patterns: File glob patterns to include
            exclude_patterns: File glob patterns to exclude
            force_rerun: Skip cache and rerun all hooks
            optimize_order: Sort hooks by execution time (fastest first)
            parallel: Run independent hooks in parallel
            max_workers: Maximum parallel workers (default: 3)

        Returns:
            ExecutionSummary with results and statistics
        """
        import time

        start_time = time.perf_counter()

        # 1. Create and configure filter
        filter_config = FilterConfig(
            tool_name=tool_filter,
            changed_only=changed_only,
            file_patterns=file_patterns or [],
            exclude_patterns=exclude_patterns or [],
        )
        self.filter = ToolFilter(config=filter_config, executor=self.executor)

        # 2. Filter tools
        available_tools = [h.name for h in hooks]
        tool_result = self.filter.filter_tools(available_tools)

        # Only run filtered tools
        hooks_to_run = [h for h in hooks if h.name in tool_result.filtered_tools]

        # 3. Optimize hook order (Phase 10.4.5)
        if optimize_order:
            hooks_to_run = self.optimize_hook_order(hooks_to_run)

        # 4. Execute hooks (serial or parallel)
        results: list[HookResult] = []
        hooks_succeeded = 0
        hooks_failed = 0

        if parallel:
            # Parallel execution (Phase 10.4.5)
            results = self._execute_parallel(
                hooks_to_run,
                force_rerun=force_rerun,
                max_workers=max_workers,
            )
            hooks_succeeded = sum(1 for r in results if r.success)
            hooks_failed = sum(1 for r in results if not r.success)
        else:
            # Serial execution (original behavior)
            for hook in hooks_to_run:
                # Execute with timing
                hook_start_time = time.perf_counter()
                hook_result = self._execute_single_hook(
                    hook,
                    force_rerun=force_rerun,
                )
                hook_end_time = time.perf_counter()

                # Update profiler with single execution metrics
                if hook.name not in self.profiler.results:
                    from crackerjack.services.profiler import ProfileResult

                    self.profiler.results[hook.name] = ProfileResult(
                        tool_name=hook.name,
                        runs=0,
                    )

                profile_result = self.profiler.results[hook.name]
                profile_result.runs += 1
                profile_result.execution_times.append(hook_end_time - hook_start_time)

                results.append(hook_result)

                if hook_result.success:
                    hooks_succeeded += 1
                else:
                    hooks_failed += 1

        # 5. Calculate statistics
        total_execution_time = time.perf_counter() - start_time
        total_hooks = len(hooks)
        hooks_run = len(hooks_to_run)
        hooks_skipped = total_hooks - hooks_run

        # Calculate cache effectiveness (average cache hit rate)
        cache_effectiveness = 0.0
        if results:
            cache_rates = [r.cache_hit_rate for r in results if r.cache_hit_rate > 0]
            if cache_rates:
                cache_effectiveness = sum(cache_rates) / len(cache_rates)

        return ExecutionSummary(
            total_hooks=total_hooks,
            hooks_run=hooks_run,
            hooks_skipped=hooks_skipped,
            hooks_succeeded=hooks_succeeded,
            hooks_failed=hooks_failed,
            total_execution_time=total_execution_time,
            filter_effectiveness=tool_result.filter_effectiveness,
            cache_effectiveness=cache_effectiveness,
            results=results,
        )

    def _execute_single_hook(
        self,
        hook: HookDefinition,
        force_rerun: bool = False,
    ) -> HookResult:
        """Execute a single hook with caching.

        Args:
            hook: Hook definition to execute
            force_rerun: Skip cache and rerun

        Returns:
            HookResult with execution details
        """
        import subprocess

        # Get files to process (if tool accepts file paths)
        files_to_process = self._get_files_for_hook(hook)

        # Execute with caching if files are involved
        if (
            files_to_process
            and hasattr(hook, "accepts_file_paths")
            and hook.accepts_file_paths
        ):
            # Use incremental executor for file-level caching
            def tool_func(file_path: Path) -> bool:
                command = hook.build_command(files=[file_path])
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=hook.timeout,
                    check=False,
                )
                return result.returncode == 0

            execution_result = self.executor.execute_incremental(
                tool_name=hook.name,
                files=files_to_process,
                tool_func=tool_func,
                force_rerun=force_rerun,
            )

            return HookResult(
                hook_name=hook.name,
                success=all(execution_result.results.values()),
                output="Files processed with caching",
                error=None,
                execution_time=execution_result.execution_time,
                files_processed=execution_result.files_processed,
                files_cached=execution_result.files_cached,
                cache_hit_rate=execution_result.cache_hit_rate,
            )
        else:
            # Run on entire codebase (project-level tool)
            command = hook.get_command()
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=hook.timeout,
                    check=False,
                )

                return HookResult(
                    hook_name=hook.name,
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr if result.returncode != 0 else None,
                    execution_time=0.0,  # Measured by profiler
                    files_processed=0,
                    files_cached=0,
                    cache_hit_rate=0.0,
                )
            except subprocess.TimeoutExpired:
                return HookResult(
                    hook_name=hook.name,
                    success=False,
                    output="",
                    error=f"Timeout after {hook.timeout}s",
                    execution_time=hook.timeout,
                )
            except Exception as e:
                return HookResult(
                    hook_name=hook.name,
                    success=False,
                    output="",
                    error=str(e),
                    execution_time=0.0,
                )

    def _execute_parallel(
        self,
        hooks: list[HookDefinition],
        force_rerun: bool = False,
        max_workers: int = 3,
    ) -> list[HookResult]:
        """Execute hooks in parallel using thread pool.

        Phase 10.4.5: Enables concurrent execution of independent hooks.

        Args:
            hooks: List of hooks to execute
            force_rerun: Skip cache and rerun
            max_workers: Maximum concurrent workers

        Returns:
            List of HookResult objects
        """
        import time

        results: list[HookResult] = []

        def execute_with_profiling(hook: HookDefinition) -> HookResult:
            """Execute a single hook with profiling."""
            hook_start_time = time.perf_counter()
            hook_result = self._execute_single_hook(hook, force_rerun=force_rerun)
            hook_end_time = time.perf_counter()

            # Update profiler with single execution metrics
            if hook.name not in self.profiler.results:
                from crackerjack.services.profiler import ProfileResult

                self.profiler.results[hook.name] = ProfileResult(
                    tool_name=hook.name,
                    runs=0,
                )

            profile_result = self.profiler.results[hook.name]
            profile_result.runs += 1
            profile_result.execution_times.append(hook_end_time - hook_start_time)

            return hook_result

        # Execute hooks in parallel using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all hooks
            future_to_hook = {
                executor.submit(execute_with_profiling, hook): hook for hook in hooks
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_hook):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    hook = future_to_hook[future]
                    results.append(
                        HookResult(
                            hook_name=hook.name,
                            success=False,
                            output="",
                            error=f"Parallel execution error: {e}",
                            execution_time=0.0,
                        )
                    )

        return results

    def _get_files_for_hook(self, hook: HookDefinition) -> list[Path]:
        """Get list of files to process for a hook.

        Args:
            hook: Hook definition

        Returns:
            List of file paths to process
        """
        # Only discover files for file-level tools
        if not (hasattr(hook, "accepts_file_paths") and hook.accepts_file_paths):
            return []

        # Discover files based on tool type
        file_patterns = self._get_file_patterns_for_tool(hook.name)
        all_files: list[Path] = []

        for pattern in file_patterns:
            all_files.extend(Path.cwd().rglob(pattern))

        # Apply filters if available
        if self.filter:
            filter_result = self.filter.filter_files(
                tool_name=hook.name,
                all_files=all_files,
            )
            return filter_result.filtered_files

        return all_files

    def _get_file_patterns_for_tool(self, tool_name: str) -> list[str]:
        """Get file glob patterns for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of glob patterns (e.g., ["*.py"] for Python tools)
        """
        # Map tools to file patterns
        python_tools = {
            "ruff-check",
            "ruff-format",
            "bandit",
        }
        markdown_tools = {"mdformat"}
        yaml_tools = {"check-yaml"}
        toml_tools = {"check-toml"}
        all_text_tools = {
            "trailing-whitespace",
            "end-of-file-fixer",
            "codespell",
        }

        if tool_name in python_tools:
            return ["*.py"]
        elif tool_name in markdown_tools:
            return ["*.md"]
        elif tool_name in yaml_tools:
            return ["*.yaml", "*.yml"]
        elif tool_name in toml_tools:
            return ["*.toml"]
        elif tool_name in all_text_tools:
            # All text files except common binaries
            return [
                "*.py",
                "*.md",
                "*.yaml",
                "*.yml",
                "*.toml",
                "*.txt",
                "*.json",
            ]
        else:
            # Default to Python files
            return ["*.py"]

    def generate_report(self, summary: ExecutionSummary) -> str:
        """Generate human-readable execution report.

        Args:
            summary: Execution summary

        Returns:
            Formatted report string
        """
        lines = [
            "# Hook Execution Summary",
            "",
            f"**Total Hooks:** {summary.total_hooks}",
            f"**Hooks Run:** {summary.hooks_run}",
            f"**Hooks Skipped:** {summary.hooks_skipped}",
            f"**Succeeded:** {summary.hooks_succeeded}",
            f"**Failed:** {summary.hooks_failed}",
            f"**Total Time:** {summary.total_execution_time:.2f}s",
            "",
        ]

        if summary.filter_effectiveness > 0:
            lines.extend(
                [
                    "## Filter Effectiveness",
                    "",
                    f"- **Tools Filtered Out:** {summary.filter_effectiveness:.1f}%",
                    "",
                ]
            )

        if summary.cache_effectiveness > 0:
            lines.extend(
                [
                    "## Cache Effectiveness",
                    "",
                    f"- **Average Cache Hit Rate:** {summary.cache_effectiveness:.1f}%",
                    "",
                ]
            )

        if summary.results:
            lines.extend(
                [
                    "## Results",
                    "",
                    "| Hook | Status | Time | Cache Hit Rate |",
                    "|------|--------|------|----------------|",
                ]
            )

            for result in summary.results:
                status = "✅" if result.success else "❌"
                cache_rate = (
                    f"{result.cache_hit_rate:.1f}%"
                    if result.cache_hit_rate > 0
                    else "N/A"
                )
                lines.append(
                    f"| {result.hook_name} | {status} | {result.execution_time:.2f}s | {cache_rate} |"
                )

            lines.append("")

        # Add profiler summary
        if self.profiler.results:
            profiler_summary = self.profiler.generate_report()
            lines.extend(
                [
                    "## Performance Profiling",
                    "",
                    profiler_summary,
                ]
            )

        # Add filter summary if available
        if self.filter:
            # Generate filter summary (tool filtering already done above)
            lines.extend(
                [
                    "## Filter Details",
                    "",
                    "Use `--tool TOOL_NAME` to run specific tools",
                    "Use `--changed-only` to run only on changed files",
                    "",
                ]
            )

        return "\n".join(lines)
