import asyncio
import typing as t
from pathlib import Path

from acb.console import Console

from crackerjack.config.hooks import HookConfigLoader
from crackerjack.executors.async_hook_executor import AsyncHookExecutor
from crackerjack.models.task import HookResult


class AsyncHookManager:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        max_concurrent: int = 3,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.async_executor = AsyncHookExecutor(
            console,
            pkg_path,
            max_concurrent=max_concurrent,
            quiet=True,
        )
        self.config_loader = HookConfigLoader()
        self._config_path: Path | None = None

    def set_config_path(self, config_path: Path) -> None:
        self._config_path = config_path

    async def run_fast_hooks_async(self) -> list[HookResult]:
        strategy = self.config_loader.load_strategy("fast")

        strategy.parallel = False

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path

        execution_result = await self.async_executor.execute_strategy(strategy)
        return execution_result.results

    async def run_comprehensive_hooks_async(self) -> list[HookResult]:
        strategy = self.config_loader.load_strategy("comprehensive")

        strategy.parallel = True
        strategy.max_workers = 3

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path

        execution_result = await self.async_executor.execute_strategy(strategy)
        return execution_result.results

    def run_fast_hooks(self) -> list[HookResult]:
        return asyncio.run(self.run_fast_hooks_async())

    def run_comprehensive_hooks(self) -> list[HookResult]:
        return asyncio.run(self.run_comprehensive_hooks_async())

    async def install_hooks_async(self) -> bool:
        """Install git hooks (async version).

        Phase 8.5: This method is deprecated. Direct tool invocation doesn't require
        pre-commit hook installation. Returns True with informational message.
        """
        self.console.print(
            "[yellow]ℹ️[/yellow] Hook installation not required with direct invocation"
        )
        return True

    def install_hooks(self) -> bool:
        return asyncio.run(self.install_hooks_async())

    async def update_hooks_async(self) -> bool:
        """Update hooks to latest versions (async version).

        Phase 8.5: This method is deprecated. Direct tool invocation uses UV for
        dependency management. Returns True with informational message.
        """
        self.console.print(
            "[yellow]ℹ️[/yellow] Hook updates managed via UV dependency resolution"
        )
        return True

    def update_hooks(self) -> bool:
        return asyncio.run(self.update_hooks_async())

    @staticmethod
    def get_hook_summary(
        results: list[HookResult], elapsed_time: float | None = None
    ) -> dict[str, t.Any]:
        """Calculate summary statistics for hook execution results.

        Args:
            results: List of hook execution results
            elapsed_time: Optional wall-clock elapsed time in seconds.
                         If provided, used as total_duration (critical for parallel execution).
                         If None, falls back to sum of individual durations (sequential mode).

        Returns:
            Dictionary with execution statistics
        """
        if not results:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "total_duration": 0,
                "success_rate": 0,
            }

        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        errors = sum(1 for r in results if r.status in ("timeout", "error"))

        # Use wall-clock time if provided (parallel execution), else sum durations (sequential)
        total_duration = (
            elapsed_time
            if elapsed_time is not None
            else sum(r.duration for r in results)
        )

        return {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total_duration": total_duration,
            "success_rate": (passed / len(results)) * 100 if results else 0,
        }
