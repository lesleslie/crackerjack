"""Enhanced hook executor integrating Phase 10.3 optimization infrastructure.

Phase 10.4.3: Integrates ToolProfiler, IncrementalExecutor, and ToolFilter
for optimized hook execution with performance tracking and caching.
"""

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

    def execute_hooks(
        self,
        hooks: list[HookDefinition],
        *,
        tool_filter: str | None = None,
        changed_only: bool = False,
        file_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        force_rerun: bool = False,
    ) -> ExecutionSummary:
        """Execute hooks with filtering, caching, and profiling.

        Args:
            hooks: List of hook definitions to execute
            tool_filter: Run only specific tool (--tool flag)
            changed_only: Run only on changed files (--changed-only flag)
            file_patterns: File glob patterns to include
            exclude_patterns: File glob patterns to exclude
            force_rerun: Skip cache and rerun all hooks

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

        # 3. Execute each hook with single-execution profiling
        results: list[HookResult] = []
        hooks_succeeded = 0
        hooks_failed = 0

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

        # 4. Calculate statistics
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
                command = hook.get_command() + [str(file_path)]
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

    def _get_files_for_hook(self, hook: HookDefinition) -> list[Path]:
        """Get list of files to process for a hook.

        Args:
            hook: Hook definition

        Returns:
            List of file paths to process
        """
        # TODO: Phase 10.4.4: Implement file discovery and filtering
        # For now, return empty list (project-level execution)
        return []

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
