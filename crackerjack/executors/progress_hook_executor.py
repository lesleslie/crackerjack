import time
import typing as t
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from crackerjack.config.hooks import HookStrategy, RetryPolicy
from crackerjack.executors.hook_executor import HookExecutionResult, HookExecutor
from crackerjack.models.task import HookResult


class ProgressHookExecutor(HookExecutor):
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
        super().__init__(
            console,
            pkg_path,
            verbose,
            quiet,
            debug,
            use_incremental,
            git_service,
        )
        self.show_progress = show_progress and not quiet
        self.debug = debug

    def execute_strategy(self, strategy: HookStrategy) -> HookExecutionResult:
        start_time = time.time()

        self._print_strategy_header(strategy)

        if not self.show_progress:
            return super().execute_strategy(strategy)

        with self._create_progress_bar() as progress:
            main_task = progress.add_task(
                f"[cyan]Running {len(strategy.hooks)} hooks...",
                total=len(strategy.hooks),
            )

            if strategy.parallel and len(strategy.hooks) > 1:
                results = self._execute_parallel_with_progress(
                    strategy,
                    progress,
                    main_task,
                )
            else:
                results = self._execute_sequential_with_progress(
                    strategy,
                    progress,
                    main_task,
                )

        if strategy.retry_policy != RetryPolicy.NONE:
            if not self.quiet:
                self.console.print("\n[yellow]Retrying failed hooks...[/yellow]")
            results = self._handle_retries(strategy, results)

        total_duration = time.time() - start_time
        success = all(r.status == "passed" for r in results)

        performance_gain = 0.0
        if not self.quiet:
            self._print_summary(strategy, results, success, performance_gain)

        return HookExecutionResult(
            strategy_name=strategy.name,
            results=results,
            total_duration=total_duration,
            success=success,
        )

    def _create_progress_bar(self) -> Progress:

        return Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[progress.description]{task.description}", justify="left"),
            BarColumn(bar_width=20),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            console=self.console,  # type: ignore[untyped]
            transient=True,
            refresh_per_second=4,
        )

    def _execute_sequential_with_progress(
        self,
        strategy: HookStrategy,
        progress: Progress,
        main_task: t.Any,
    ) -> list[HookResult]:
        results: list[HookResult] = []

        for hook in strategy.hooks:
            progress.update(
                main_task,
                description=f"[cyan]Running {hook.name}...",
            )

            hook_start = time.time()
            result = self._execute_hook_with_progress_updates(hook, progress, main_task)
            hook_duration = time.time() - hook_start
            result.duration = hook_duration
            results.append(result)

            status_icon = "✅" if result.status == "passed" else "❌"
            duration_str = (
                f"{hook_duration:.1f}s"
                if hook_duration < 10
                else f"{hook_duration:.0f}s"
            )
            progress.update(
                main_task,
                advance=1,
                description=f"[cyan]{status_icon} {hook.name} [{duration_str}]",
            )

        return results

    def _execute_hook_with_progress_updates(
        self,
        hook: t.Any,
        progress: Progress,
        main_task: t.Any,
    ) -> t.Any:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future: Future[t.Any] = executor.submit(self.execute_single_hook, hook)

            while not future.done():
                progress.refresh()
                time.sleep(0.1)

            return future.result()

    def _execute_parallel_with_progress(
        self,
        strategy: HookStrategy,
        progress: Progress,
        main_task: t.Any,
    ) -> list[HookResult]:
        results: list[HookResult] = []

        formatting_hooks = [h for h in strategy.hooks if h.is_formatting]
        other_hooks = [h for h in strategy.hooks if not h.is_formatting]

        for hook in formatting_hooks:
            progress.update(
                main_task,
                description=f"[cyan]Running {hook.name}...",
            )

            hook_start = time.time()
            result = self._execute_hook_with_progress_updates(hook, progress, main_task)
            hook_duration = time.time() - hook_start
            result.duration = hook_duration
            results.append(result)

            status_icon = "✅" if result.status == "passed" else "❌"
            duration_str = (
                f"{hook_duration:.1f}s"
                if hook_duration < 10
                else f"{hook_duration:.0f}s"
            )
            progress.update(
                main_task,
                advance=1,
                description=f"[cyan]{status_icon} {hook.name} [{duration_str}]",
            )

        if other_hooks:
            progress.update(
                main_task,
                description=f"[cyan]Running {len(other_hooks)} hooks in parallel...",
            )

            with ThreadPoolExecutor(max_workers=strategy.max_workers) as executor:
                hook_start_times: dict[str, float] = {}
                future_to_hook = {}
                for hook in other_hooks:
                    hook_start_times[hook.name] = time.time()
                    future_to_hook[executor.submit(self.execute_single_hook, hook)] = (
                        hook
                    )

                completed_futures: list[Future[t.Any]] = []
                while len(completed_futures) < len(future_to_hook):
                    for future in list(future_to_hook.keys()):
                        if future.done() and future not in completed_futures:
                            completed_futures.append(future)
                            try:
                                result = future.result()

                                hook_duration = time.time() - hook_start_times.get(
                                    result.name, time.time()
                                )
                                result.duration = hook_duration
                                results.append(result)

                                status_icon = (
                                    "✅" if result.status == "passed" else "❌"
                                )
                                duration_str = (
                                    f"{hook_duration:.1f}s"
                                    if hook_duration < 10
                                    else f"{hook_duration:.0f}s"
                                )
                                progress.update(
                                    main_task,
                                    advance=1,
                                    description=f"[cyan]{status_icon} {result.name} [{duration_str}]",
                                )
                            except Exception as e:
                                hook = future_to_hook[future]
                                hook_duration = time.time() - hook_start_times.get(
                                    hook.name, time.time()
                                )
                                error_result = HookResult(
                                    id=hook.name,
                                    name=hook.name,
                                    status="error",
                                    duration=hook_duration,
                                    issues_found=[str(e)],
                                    issues_count=1,
                                    stage=hook.stage.value,
                                )
                                results.append(error_result)

                                duration_str = (
                                    f"{hook_duration:.1f}s"
                                    if hook_duration < 10
                                    else f"{hook_duration:.0f}s"
                                )
                                progress.update(
                                    main_task,
                                    advance=1,
                                    description=f"[cyan]❌ {hook.name} [{duration_str}]",
                                )

                    progress.refresh()
                    time.sleep(0.1)

        return results

    def _display_hook_result(self, result: HookResult) -> None:
        if not self.show_progress:
            super()._display_hook_result(result)
