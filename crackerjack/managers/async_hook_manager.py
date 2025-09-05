import asyncio
import typing as t
from pathlib import Path

from rich.console import Console

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
        """Set the path to the pre-commit configuration file."""
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
        try:
            process = await asyncio.create_subprocess_exec(
                "uv",
                "run",
                "pre-commit",
                "install",
                cwd=self.pkg_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                self.console.print("[green]✅[/ green] Pre-commit hooks installed")
                return True
            error_msg = stderr.decode() if stderr else "Unknown error"
            self.console.print(
                f"[red]❌[/ red] Failed to install hooks: {error_msg}",
            )
            return False

        except TimeoutError:
            self.console.print("[red]❌[/ red] Hook installation timed out")
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error installing hooks: {e}")
            return False

    def install_hooks(self) -> bool:
        return asyncio.run(self.install_hooks_async())

    async def update_hooks_async(self) -> bool:
        try:
            process = await asyncio.create_subprocess_exec(
                "uv",
                "run",
                "pre-commit",
                "autoupdate",
                cwd=self.pkg_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

            if process.returncode == 0:
                self.console.print("[green]✅[/ green] Pre-commit hooks updated")
                return True
            error_msg = stderr.decode() if stderr else "Unknown error"
            self.console.print(f"[red]❌[/ red] Failed to update hooks: {error_msg}")
            return False

        except TimeoutError:
            self.console.print("[red]❌[/ red] Hook update timed out")
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error updating hooks: {e}")
            return False

    def update_hooks(self) -> bool:
        return asyncio.run(self.update_hooks_async())

    def get_hook_summary(self, results: list[HookResult]) -> dict[str, t.Any]:
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
        total_duration = sum(r.duration for r in results)

        return {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total_duration": total_duration,
            "success_rate": (passed / len(results)) * 100 if results else 0,
        }
