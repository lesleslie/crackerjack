import asyncio
import typing as t
from pathlib import Path

from crackerjack.models.protocols import (
    AsyncHookExecutorProtocol,
    ConsoleInterface,
    HookConfigLoaderProtocol,
)
from crackerjack.models.task import HookResult


class AsyncHookManager:
    def __init__(
        self,
        console: ConsoleInterface,
        pkg_path: Path,
        async_executor: AsyncHookExecutorProtocol | None = None,
        config_loader: HookConfigLoaderProtocol | None = None,
        max_concurrent: int = 3,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path

        if async_executor is None:
            from crackerjack.executors.async_hook_executor import AsyncHookExecutor

            async_executor = AsyncHookExecutor(
                console,
                pkg_path,
                max_concurrent=max_concurrent,
                quiet=True,
            )

        if config_loader is None:
            from crackerjack.config.hooks import HookConfigLoader

            config_loader = HookConfigLoader()

        self.async_executor = async_executor
        self.config_loader = config_loader
        self._config_path: Path | None = None

    def set_config_path(self, config_path: Path) -> None:
        self._config_path = config_path

    def get_hook_count(self, suite_name: str) -> int:
        strategy = self.config_loader.load_strategy(suite_name)
        return len(strategy.hooks)

    async def run_fast_hooks_async(self) -> list[HookResult]:
        strategy = self.config_loader.load_strategy("fast")

        strategy.parallel = True
        strategy.max_workers = 3

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
        self.console.print(
            "[yellow]ℹ️[/yellow] Hook installation not required with direct invocation",
        )
        return True

    def install_hooks(self) -> bool:
        return asyncio.run(self.install_hooks_async())

    async def update_hooks_async(self) -> bool:
        self.console.print(
            "[yellow]ℹ️[/yellow] Hook updates managed via UV dependency resolution",
        )
        return True

    def update_hooks(self) -> bool:
        return asyncio.run(self.update_hooks_async())

    @staticmethod
    def get_hook_summary(
        results: list[HookResult],
        elapsed_time: float | None = None,
    ) -> dict[str, t.Any]:
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
