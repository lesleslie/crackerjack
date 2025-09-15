import subprocess
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.config.hooks import HookConfigLoader
from crackerjack.executors.hook_executor import HookExecutor
from crackerjack.executors.lsp_aware_hook_executor import LSPAwareHookExecutor
from crackerjack.models.task import HookResult


class HookManagerImpl:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        verbose: bool = False,
        quiet: bool = False,
        enable_lsp_optimization: bool = False,
        enable_tool_proxy: bool = True,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.executor: HookExecutor

        # Use LSP-aware executor if optimization is enabled
        if enable_lsp_optimization:
            self.executor = LSPAwareHookExecutor(
                console, pkg_path, verbose, quiet, use_tool_proxy=enable_tool_proxy
            )
        else:
            self.executor = HookExecutor(console, pkg_path, verbose, quiet)

        self.config_loader = HookConfigLoader()
        self._config_path: Path | None = None
        self.lsp_optimization_enabled = enable_lsp_optimization
        self.tool_proxy_enabled = enable_tool_proxy

    def set_config_path(self, config_path: Path) -> None:
        self._config_path = config_path

    def run_fast_hooks(self) -> list[HookResult]:
        strategy = self.config_loader.load_strategy("fast")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path
        execution_result = self.executor.execute_strategy(strategy)
        return execution_result.results

    def run_comprehensive_hooks(self) -> list[HookResult]:
        strategy = self.config_loader.load_strategy("comprehensive")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path
        execution_result = self.executor.execute_strategy(strategy)
        return execution_result.results

    def run_hooks(self) -> list[HookResult]:
        fast_results = self.run_fast_hooks()
        comprehensive_results = self.run_comprehensive_hooks()
        return fast_results + comprehensive_results

    def get_execution_info(self) -> dict[str, t.Any]:
        """Get information about current execution mode and capabilities."""
        info = {
            "lsp_optimization_enabled": self.lsp_optimization_enabled,
            "tool_proxy_enabled": self.tool_proxy_enabled,
            "executor_type": type(self.executor).__name__,
        }

        # Get LSP-specific info if available
        if hasattr(self.executor, "get_execution_mode_summary"):
            info.update(self.executor.get_execution_mode_summary())

        return info

    def configure_lsp_optimization(self, enable: bool) -> None:
        """Enable or disable LSP optimization by switching executors."""
        if enable == self.lsp_optimization_enabled:
            return  # Already in the correct state

        # Switch executor based on the enable flag
        if enable:
            self.executor = LSPAwareHookExecutor(
                self.console,
                self.pkg_path,
                verbose=getattr(self.executor, "verbose", False),
                quiet=getattr(self.executor, "quiet", True),
                use_tool_proxy=self.tool_proxy_enabled,
            )
        else:
            self.executor = HookExecutor(
                self.console,
                self.pkg_path,
                verbose=getattr(self.executor, "verbose", False),
                quiet=getattr(self.executor, "quiet", True),
            )

        self.lsp_optimization_enabled = enable

        # Restore config path if it was set[t.Any]
        if self._config_path:
            # Config path is set[t.Any] at the manager level, not executor level
            pass

    def configure_tool_proxy(self, enable: bool) -> None:
        """Enable or disable tool proxy resilience."""
        if enable == self.tool_proxy_enabled:
            return  # Already in the correct state

        self.tool_proxy_enabled = enable

        # If using LSP-aware executor, recreate it with new tool proxy setting
        if isinstance(self.executor, LSPAwareHookExecutor):
            self.executor = LSPAwareHookExecutor(
                self.console,
                self.pkg_path,
                verbose=getattr(self.executor, "verbose", False),
                quiet=getattr(self.executor, "quiet", True),
                use_tool_proxy=enable,
            )

            # Restore config path if it was set[t.Any]
            if self._config_path:
                pass  # Config path handled at manager level

    def validate_hooks_config(self) -> bool:
        try:
            result = subprocess.run(
                ["uv", "run", "pre-commit", "validate-config"],
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_hook_ids(self) -> list[str]:
        fast_strategy = self.config_loader.load_strategy("fast")
        comprehensive_strategy = self.config_loader.load_strategy("comprehensive")

        all_hooks = fast_strategy.hooks + comprehensive_strategy.hooks
        return [hook.name for hook in all_hooks]

    def install_hooks(self) -> bool:
        try:
            result = subprocess.run(
                ["uv", "run", "pre-commit", "install"],
                check=False,
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self.console.print("[green]✅[/ green] Pre-commit hooks installed")
                return True
            self.console.print(
                f"[red]❌[/ red] Failed to install hooks: {result.stderr}",
            )
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error installing hooks: {e}")
            return False

    def update_hooks(self) -> bool:
        try:
            result = subprocess.run(
                ["uv", "run", "pre-commit", "autoupdate"],
                check=False,
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self.console.print("[green]✅[/ green] Pre-commit hooks updated")
                return True
            self.console.print(
                f"[red]❌[/ red] Failed to update hooks: {result.stderr}",
            )
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error updating hooks: {e}")
            return False

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
