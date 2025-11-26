"""Enhanced hook executor with rich progress indicators.

Extends base HookExecutor with real-time progress feedback using rich library.
Part of Phase 10.2.2: Development Velocity Improvements.
"""

import time
import typing as t
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from acb.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from crackerjack.config.hooks import HookStrategy, RetryPolicy
from crackerjack.executors.hook_executor import HookExecutionResult, HookExecutor
from crackerjack.models.task import HookResult


class ProgressHookExecutor(HookExecutor):
    """Hook executor with enhanced progress indicators.

    Provides real-time feedback during hook execution using rich progress bars,
    improving developer experience during long-running quality checks.
    """

    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        verbose: bool = False,
        quiet: bool = False,
        show_progress: bool = True,
        debug: bool = False,
        use_incremental: bool = False,
        git_service: t.Any | None = None,
    ) -> None:
        """Initialize progress-enhanced hook executor.

        Args:
            console: Rich console for output
            pkg_path: Project root path
            verbose: Show detailed output
            quiet: Suppress output
            show_progress: Enable progress bars (disable for CI/testing)
            debug: Enable debug output
            use_incremental: Run hooks only on changed files
            git_service: GitService instance for incremental execution
        """
        super().__init__(
            console, pkg_path, verbose, quiet, debug, use_incremental, git_service
        )
        self.show_progress = show_progress and not quiet
        self.debug = debug

    def execute_strategy(self, strategy: HookStrategy) -> HookExecutionResult:
        """Execute hook strategy with progress indicators.

        Args:
            strategy: Hook strategy to execute

        Returns:
            Execution result with timing and status information
        """
        start_time = time.time()

        self._print_strategy_header(strategy)

        if not self.show_progress:
            # Fall back to base implementation without progress bars
            return super().execute_strategy(strategy)

        # Create progress bar context
        with self._create_progress_bar() as progress:
            # Add main task for overall progress
            main_task = progress.add_task(
                f"[cyan]Running {len(strategy.hooks)} hooks...",
                total=len(strategy.hooks),
            )

            if strategy.parallel and len(strategy.hooks) > 1:
                results = self._execute_parallel_with_progress(
                    strategy, progress, main_task
                )
            else:
                results = self._execute_sequential_with_progress(
                    strategy, progress, main_task
                )

        # Handle retries (without progress bar to avoid confusion)
        if strategy.retry_policy != RetryPolicy.NONE:
            if not self.quiet:
                self.console.print("\n[yellow]Retrying failed hooks...[/yellow]")
            results = self._handle_retries(strategy, results)

        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in results)

        # Calculate performance gain for the summary
        performance_gain = 0.0  # Default value for progress executor
        if not self.quiet:
            self._print_summary(strategy, results, success, performance_gain)

        return HookExecutionResult(
            strategy_name=strategy.name,
            results=results,
            total_duration=total_duration,
            success=success,
        )

    def _create_progress_bar(self) -> Progress:
        """Create configured progress bar with appropriate columns.

        Progress bar width is constrained to respect console width by limiting
        description text and using compact time format.

        Logger output is suppressed at the source (logging level) to prevent
        interference with progress bar updates.

        Returns:
            Configured Progress instance
        """
        return Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[progress.description]{task.description}", justify="left"),
            BarColumn(bar_width=20),  # Fixed narrow bar to prevent overflow
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True,  # Clear progress bar after completion (consistent with test progress)
            refresh_per_second=10,  # Smooth single-line updates
        )

    def _execute_sequential_with_progress(
        self,
        strategy: HookStrategy,
        progress: Progress,
        main_task: t.Any,
    ) -> list[HookResult]:
        """Execute hooks sequentially with progress updates.

        Args:
            strategy: Hook strategy to execute
            progress: Progress bar context
            main_task: Main progress task ID

        Returns:
            List of hook execution results
        """
        results: list[HookResult] = []

        for hook in strategy.hooks:
            # Update description to show current hook
            progress.update(
                main_task,
                description=f"[cyan]Running {hook.name}...",
            )

            result = self.execute_single_hook(hook)
            results.append(result)

            # Update progress with completion
            status_icon = "✅" if result.status == "passed" else "❌"
            progress.update(
                main_task,
                advance=1,
                description=f"[cyan]Completed {hook.name} {status_icon}",
            )

        return results

    def _execute_parallel_with_progress(
        self,
        strategy: HookStrategy,
        progress: Progress,
        main_task: t.Any,
    ) -> list[HookResult]:
        """Execute hooks in parallel with progress updates.

        Formatting hooks run sequentially first, then analysis hooks run in parallel.

        Args:
            strategy: Hook strategy to execute
            progress: Progress bar context
            main_task: Main progress task ID

        Returns:
            List of hook execution results
        """
        results: list[HookResult] = []

        # Separate formatting hooks (must run sequentially)
        formatting_hooks = [h for h in strategy.hooks if h.is_formatting]
        other_hooks = [h for h in strategy.hooks if not h.is_formatting]

        # Execute formatting hooks sequentially
        for hook in formatting_hooks:
            progress.update(
                main_task,
                description=f"[cyan]Running {hook.name}...",
            )

            result = self.execute_single_hook(hook)
            results.append(result)

            status_icon = "✅" if result.status == "passed" else "❌"
            progress.update(
                main_task,
                advance=1,
                description=f"[cyan]Completed {hook.name} {status_icon}",
            )

        # Execute analysis hooks in parallel
        if other_hooks:
            progress.update(
                main_task,
                description=f"[cyan]Running {len(other_hooks)} hooks in parallel...",
            )

            with ThreadPoolExecutor(max_workers=strategy.max_workers) as executor:
                future_to_hook = {
                    executor.submit(self.execute_single_hook, hook): hook
                    for hook in other_hooks
                }

                for future in as_completed(future_to_hook):
                    try:
                        result = future.result()
                        results.append(result)

                        status_icon = "✅" if result.status == "passed" else "❌"
                        progress.update(
                            main_task,
                            advance=1,
                            description=f"[cyan]Completed {result.name} {status_icon}",
                        )

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
                        )
                        results.append(error_result)

                        progress.update(
                            main_task,
                            advance=1,
                            description=f"[cyan]Failed {hook.name} ❌",
                        )

        return results

    def _display_hook_result(self, result: HookResult) -> None:
        """Display hook result with emoji status.

        When progress bars are disabled, always show inline hook status.
        When progress bars are enabled, suppress inline output (progress bar shows it).

        Args:
            result: Hook execution result
        """
        # Always show inline status when progress bars are disabled
        # Skip inline output when progress bars are enabled (they show the status)
        if not self.show_progress:
            super()._display_hook_result(result)
