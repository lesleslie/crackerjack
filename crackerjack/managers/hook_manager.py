import typing as t
from pathlib import Path

from acb.depends import depends
from rich.console import Console

from crackerjack.config import CrackerjackSettings
from crackerjack.config.hooks import HookConfigLoader
from crackerjack.executors.hook_executor import HookExecutor
from crackerjack.executors.lsp_aware_hook_executor import LSPAwareHookExecutor
from crackerjack.models.task import HookResult

if t.TYPE_CHECKING:
    from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter


class HookManagerImpl:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        verbose: bool = False,
        quiet: bool = False,
        enable_lsp_optimization: bool = False,
        enable_tool_proxy: bool = True,
        # Legacy parameters kept for backward compatibility (deprecated)
        orchestration_config: t.Any = None,
        enable_orchestration: bool | None = None,
        orchestration_mode: str | None = None,
        enable_caching: bool = True,
        cache_backend: str = "memory",
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

        # Get settings from ACB dependency injection
        self._settings = depends.get(CrackerjackSettings)

        # Load orchestration config with priority:
        # 1. Explicit orchestration_config param (highest - for testing)
        # 2. Project .crackerjack.yaml file (middle - for project-specific settings)
        # 3. Create from constructor params + DI settings (lowest - for defaults)
        if orchestration_config:
            # Explicit config object provided - use its values directly
            # Legacy parameters (enable_orchestration, orchestration_mode) are ignored
            # when an explicit config object is provided
            self._orchestration_config = orchestration_config
            self.orchestration_enabled = orchestration_config.enable_orchestration
            self.orchestration_mode = orchestration_config.orchestration_mode
        else:
            # Try to load from project config file
            from crackerjack.orchestration.config import OrchestrationConfig

            config_path = pkg_path / ".crackerjack.yaml"
            if config_path.exists():
                # Load from file
                loaded_config = OrchestrationConfig.load(config_path)
                self._orchestration_config = loaded_config
                # Extract orchestration settings with param override
                self.orchestration_enabled = (
                    enable_orchestration
                    if enable_orchestration is not None
                    else loaded_config.enable_orchestration
                )
                self.orchestration_mode = (
                    orchestration_mode
                    if orchestration_mode is not None
                    else loaded_config.orchestration_mode
                )
            else:
                # Create default config from constructor params
                from crackerjack.orchestration.hook_orchestrator import (
                    HookOrchestratorSettings,
                )

                self._orchestration_config = HookOrchestratorSettings(
                    enable_caching=enable_caching,
                    cache_backend=cache_backend,
                )
                # Use constructor params or fall back to DI settings, then to hardcoded defaults
                self.orchestration_enabled = (
                    enable_orchestration
                    if enable_orchestration is not None
                    else self._settings.enable_orchestration
                )
                self.orchestration_mode = (
                    orchestration_mode
                    if orchestration_mode is not None
                    else (self._settings.orchestration_mode or "acb")
                )

        self._orchestrator: HookOrchestratorAdapter | None = None

    def set_config_path(self, config_path: Path) -> None:
        self._config_path = config_path

    async def _init_orchestrator(self) -> None:
        """Initialize orchestrator if not already initialized."""
        if self._orchestrator is not None:
            return  # Already initialized

        from crackerjack.orchestration.hook_orchestrator import (
            HookOrchestratorAdapter,
            HookOrchestratorSettings,
        )

        # Create orchestrator settings from orchestration config
        # Handle both OrchestrationConfig (uses orchestration_mode) and
        # HookOrchestratorSettings (uses execution_mode)
        execution_mode = getattr(
            self._orchestration_config,
            "execution_mode",
            getattr(self._orchestration_config, "orchestration_mode", "acb"),
        )

        orchestrator_settings = HookOrchestratorSettings(
            execution_mode=execution_mode,
            enable_caching=self._orchestration_config.enable_caching,
            cache_backend=self._orchestration_config.cache_backend,
            max_parallel_hooks=self._orchestration_config.max_parallel_hooks,
            enable_adaptive_execution=getattr(
                self._orchestration_config, "enable_adaptive_execution", True
            ),
        )

        self._orchestrator = HookOrchestratorAdapter(
            settings=orchestrator_settings,
            hook_executor=self.executor,  # Provide executor for legacy mode fallback
        )

        await self._orchestrator.init()

    async def _run_fast_hooks_orchestrated(self) -> list[HookResult]:
        """Run fast hooks using orchestrator (async path)."""
        await self._init_orchestrator()
        assert self._orchestrator is not None

        strategy = self.config_loader.load_strategy("fast")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path

        return await self._orchestrator.execute_strategy(strategy)

    async def _run_comprehensive_hooks_orchestrated(self) -> list[HookResult]:
        """Run comprehensive hooks using orchestrator (async path)."""
        await self._init_orchestrator()
        assert self._orchestrator is not None

        strategy = self.config_loader.load_strategy("comprehensive")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path

        return await self._orchestrator.execute_strategy(strategy)

    def run_fast_hooks(self) -> list[HookResult]:
        # Use orchestrator if enabled (Phase 3+)
        if self.orchestration_enabled:
            import asyncio

            # Check if we're already in an event loop (e.g., during testing)
            try:
                asyncio.get_running_loop()
                # We're in an event loop, run in thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._run_fast_hooks_orchestrated()
                    )
                    return future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                return asyncio.run(self._run_fast_hooks_orchestrated())

        # Legacy executor path (Phase 1-2)
        strategy = self.config_loader.load_strategy("fast")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path
        execution_result = self.executor.execute_strategy(strategy)
        return execution_result.results

    def run_comprehensive_hooks(self) -> list[HookResult]:
        # Use orchestrator if enabled (Phase 3+)
        if self.orchestration_enabled:
            import asyncio

            # Check if we're already in an event loop (e.g., during testing)
            try:
                asyncio.get_running_loop()
                # We're in an event loop, run in thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._run_comprehensive_hooks_orchestrated()
                    )
                    return future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                return asyncio.run(self._run_comprehensive_hooks_orchestrated())

        # Legacy executor path (Phase 1-2)
        strategy = self.config_loader.load_strategy("comprehensive")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path
        execution_result = self.executor.execute_strategy(strategy)
        return execution_result.results

    async def _run_hooks_parallel(self) -> list[HookResult]:
        """Run fast and comprehensive strategies in parallel (async helper)."""
        import asyncio

        fast_task = self._run_fast_hooks_orchestrated()
        comp_task = self._run_comprehensive_hooks_orchestrated()

        fast_results, comp_results = await asyncio.gather(fast_task, comp_task)
        return fast_results + comp_results

    def run_hooks(self) -> list[HookResult]:
        # Phase 5-7: Enable strategy-level parallelism when orchestration is enabled
        # Use config's enable_strategy_parallelism setting (defaults to True if not set)
        enable_parallelism = getattr(
            self._orchestration_config, "enable_strategy_parallelism", True
        )
        if self.orchestration_enabled and enable_parallelism:
            import asyncio

            # Check if we're already in an event loop (e.g., during testing)
            try:
                asyncio.get_running_loop()
                # We're in an event loop, use nest_asyncio or run in thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._run_hooks_parallel())
                    return future.result()
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                return asyncio.run(self._run_hooks_parallel())

        # Legacy path: Sequential execution (backward compatibility)
        fast_results = self.run_fast_hooks()
        comprehensive_results = self.run_comprehensive_hooks()
        return fast_results + comprehensive_results

    async def get_orchestration_stats(self) -> dict[str, t.Any] | None:
        """Get orchestration statistics if orchestrator is initialized.

        Returns:
            Dictionary with orchestration stats, or None if orchestration disabled
        """
        if not self.orchestration_enabled or self._orchestrator is None:
            return None

        return await self._orchestrator.get_cache_stats()

    def get_execution_info(self) -> dict[str, t.Any]:
        """Get information about current execution mode and capabilities."""
        info = {
            "lsp_optimization_enabled": self.lsp_optimization_enabled,
            "tool_proxy_enabled": self.tool_proxy_enabled,
            "executor_type": type(self.executor).__name__,
            # Use instance properties which may override settings via constructor params
            "orchestration_enabled": self.orchestration_enabled,
            "orchestration_mode": (
                self.orchestration_mode if self.orchestration_enabled else None
            ),
            "caching_enabled": (
                self._orchestration_config.enable_caching
                if self.orchestration_enabled
                else False
            ),
            "cache_backend": (
                self._orchestration_config.cache_backend
                if self.orchestration_enabled
                else None
            ),
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
        """Validate hooks configuration.

        Phase 8.5: This method is deprecated. Direct tool invocation doesn't require
        pre-commit config validation. Always returns True for backward compatibility.
        """
        return True

    def get_hook_ids(self) -> list[str]:
        fast_strategy = self.config_loader.load_strategy("fast")
        comprehensive_strategy = self.config_loader.load_strategy("comprehensive")

        all_hooks = fast_strategy.hooks + comprehensive_strategy.hooks
        return [hook.name for hook in all_hooks]

    def install_hooks(self) -> bool:
        """Install git hooks.

        Phase 8.5: This method is deprecated. Direct tool invocation doesn't require
        pre-commit hook installation. Returns True with informational message.
        """
        self.console.print(
            "[yellow]ℹ️[/yellow] Hook installation not required with direct invocation"
        )
        return True

    def update_hooks(self) -> bool:
        """Update hooks to latest versions.

        Phase 8.5: This method is deprecated. Direct tool invocation uses UV for
        dependency management. Returns True with informational message.
        """
        self.console.print(
            "[yellow]ℹ️[/yellow] Hook updates managed via UV dependency resolution"
        )
        return True

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
