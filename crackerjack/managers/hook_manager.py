import typing as t
from contextlib import suppress
from pathlib import Path

from rich.console import Console

from crackerjack.config import CrackerjackSettings
from crackerjack.config.hooks import HookConfigLoader
from crackerjack.executors.hook_executor import HookExecutor
from crackerjack.executors.lsp_aware_hook_executor import LSPAwareHookExecutor
from crackerjack.executors.progress_hook_executor import ProgressHookExecutor
from crackerjack.models.task import HookResult

try:
    from crackerjack.services.git import GitService  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    GitService = None  # type: ignore

try:
    from crackerjack.orchestration.config import OrchestrationConfig  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    OrchestrationConfig = None  # type: ignore
    orchestration_available = False
else:
    orchestration_available = OrchestrationConfig is not None

try:
    from crackerjack.orchestration.hook_orchestrator import (  # type: ignore
        HookOrchestratorSettings,
    )
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    HookOrchestratorSettings = None  # type: ignore
    orchestration_available = False
else:
    orchestration_available = HookOrchestratorSettings is not None

if t.TYPE_CHECKING:
    from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter


class HookManagerImpl:
    executor: HookExecutor | LSPAwareHookExecutor | ProgressHookExecutor
    _settings: CrackerjackSettings | None

    def _setup_git_service(self, use_incremental: bool, pkg_path: Path):
        git_service = None
        if use_incremental and GitService is not None:
            git_service = GitService(self.console, pkg_path)
        return git_service

    def _setup_executor(
        self,
        pkg_path: Path,
        verbose: bool,
        quiet: bool,
        debug: bool,
        enable_lsp_optimization: bool,
        enable_tool_proxy: bool,
        use_incremental: bool,
        git_service: t.Any,
    ):
        if enable_lsp_optimization:
            self.executor = LSPAwareHookExecutor(
                self.console,
                pkg_path,
                verbose,
                quiet,
                debug,
                use_tool_proxy=enable_tool_proxy,
                use_incremental=use_incremental,
                git_service=git_service,
            )
        else:
            if not debug and not use_incremental and git_service is None:
                self.executor = HookExecutor(  # type: ignore[assignment]
                    self.console,
                    pkg_path,
                    verbose,
                    quiet,
                )
            else:
                self.executor = HookExecutor(  # type: ignore[assignment]
                    self.console,
                    pkg_path,
                    verbose,
                    quiet,
                    debug=debug,
                    use_incremental=use_incremental,
                    git_service=git_service,
                )

    def _load_from_project_config(
        self,
        config_path: Path,
        enable_orchestration: bool | None,
        orchestration_mode: str | None,
    ) -> None:
        if OrchestrationConfig is None:
            self._create_default_orchestration_config(
                enable_orchestration,
                orchestration_mode,
                enable_caching=False,
                cache_backend="memory",
            )
            return

        loaded_config = OrchestrationConfig.load(config_path)
        self._orchestration_config: t.Any = loaded_config

        self.orchestration_enabled = (
            enable_orchestration
            if enable_orchestration is not None
            else loaded_config.enable_orchestration
        ) and orchestration_available
        self.orchestration_mode = (
            orchestration_mode
            if orchestration_mode is not None
            else loaded_config.orchestration_mode
        )

    def _create_default_orchestration_config(
        self,
        enable_orchestration: bool | None,
        orchestration_mode: str | None,
        enable_caching: bool,
        cache_backend: str,
    ) -> None:
        try:
            from crackerjack.orchestration.hook_orchestrator import (
                HookOrchestratorSettings,
            )

            orchestration_available = True
        except ModuleNotFoundError:
            orchestration_available = False
            HookOrchestratorSettings = None

        if orchestration_available:
            self._orchestration_config = HookOrchestratorSettings(
                enable_caching=enable_caching,
                cache_backend=cache_backend,
            )
        else:

            class _FallbackOrchestrationConfig:
                def __init__(
                    self,
                    enable_caching: bool,
                    cache_backend: str,
                ) -> None:
                    self.enable_caching = enable_caching
                    self.cache_backend = cache_backend
                    self.max_parallel_hooks = 4
                    self.enable_adaptive_execution = True
                    self.orchestration_mode = "oneiric"

            self._orchestration_config = _FallbackOrchestrationConfig(
                enable_caching=enable_caching,
                cache_backend=cache_backend,
            )

        self.orchestration_enabled = (
            bool(enable_orchestration)
            if enable_orchestration is not None
            else getattr(self._settings, "enable_orchestration", False)
        ) and orchestration_available
        self.orchestration_mode = (
            orchestration_mode
            if orchestration_mode is not None
            else (getattr(self._settings, "orchestration_mode", None) or "oneiric")
        )

    def _load_orchestration_config(
        self,
        pkg_path: Path,
        orchestration_config: t.Any,
        enable_orchestration: bool | None,
        orchestration_mode: str | None,
        enable_caching: bool,
        cache_backend: str,
    ):
        if self._settings is None:
            self._settings = CrackerjackSettings()

        if orchestration_config:
            self._orchestration_config = orchestration_config
            self.orchestration_enabled = getattr(
                orchestration_config, "enable_orchestration", False
            )
            self.orchestration_mode = getattr(
                orchestration_config, "orchestration_mode", "oneiric"
            )
        else:
            config_path = pkg_path / ".crackerjack.yaml"
            if config_path.exists():
                self._load_from_project_config(
                    config_path, enable_orchestration, orchestration_mode
                )
            else:
                self._create_default_orchestration_config(
                    enable_orchestration,
                    orchestration_mode,
                    enable_caching,
                    cache_backend,
                )

    def __init__(
        self,
        pkg_path: Path,
        verbose: bool = False,
        quiet: bool = False,
        debug: bool = False,
        enable_lsp_optimization: bool = False,
        enable_tool_proxy: bool = True,
        use_incremental: bool = False,
        orchestration_config: t.Any = None,
        enable_orchestration: bool | None = None,
        orchestration_mode: str | None = None,
        enable_caching: bool = True,
        cache_backend: str = "memory",
        console: t.Any = None,
        settings: CrackerjackSettings | None = None,
    ) -> None:
        self.pkg_path = pkg_path
        self.debug = debug
        self._settings = settings

        self.console = console or Console()

        git_service = self._setup_git_service(use_incremental, pkg_path)

        self._setup_executor(
            pkg_path,
            verbose,
            quiet,
            debug,
            enable_lsp_optimization,
            enable_tool_proxy,
            use_incremental,
            git_service,
        )

        self.config_loader = HookConfigLoader()
        self._config_path: Path | None = None
        self.lsp_optimization_enabled = enable_lsp_optimization
        self.tool_proxy_enabled = enable_tool_proxy

        self._load_orchestration_config(
            pkg_path,
            orchestration_config,
            enable_orchestration,
            orchestration_mode,
            enable_caching,
            cache_backend,
        )

        self._orchestrator: HookOrchestratorAdapter | None = None

        self._progress_callback: t.Callable[[int, int], None] | None = None
        self._progress_start_callback: t.Callable[[int, int], None] | None = None

    def set_config_path(self, config_path: Path) -> None:
        self._config_path = config_path

    async def _init_orchestrator(self) -> None:
        if self._orchestrator is not None:
            return

        if not self.orchestration_enabled:
            return

        try:
            from crackerjack.orchestration.hook_orchestrator import (
                HookOrchestratorSettings,
            )
        except ModuleNotFoundError:
            self.orchestration_enabled = False
            return

        execution_mode = getattr(
            self._orchestration_config,
            "execution_mode",
            getattr(self._orchestration_config, "orchestration_mode", "oneiric"),
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
            hook_executor=self.executor,
        )

        await self._orchestrator.init()

    async def _run_fast_hooks_orchestrated(self) -> list[HookResult]:
        await self._init_orchestrator()
        assert self._orchestrator is not None

        strategy = self.config_loader.load_strategy("fast")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path

        getattr(self, "_progress_callback", None)

        return await self._orchestrator.execute_strategy(
            strategy,
            progress_callback=getattr(self, "_progress_callback", None),
            progress_start_callback=getattr(self, "_progress_start_callback", None),
        )

    async def _run_comprehensive_hooks_orchestrated(self) -> list[HookResult]:
        await self._init_orchestrator()
        assert self._orchestrator is not None

        strategy = self.config_loader.load_strategy("comprehensive")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path

        getattr(self, "_progress_callback", None)

        return await self._orchestrator.execute_strategy(
            strategy,
            progress_callback=getattr(self, "_progress_callback", None),
            progress_start_callback=getattr(self, "_progress_start_callback", None),
        )

    def run_fast_hooks(self) -> list[HookResult]:
        if self.orchestration_enabled:
            import asyncio

            try:
                asyncio.get_running_loop()

                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._run_fast_hooks_orchestrated()
                    )
                    return future.result()
            except RuntimeError:
                return asyncio.run(self._run_fast_hooks_orchestrated())

        strategy = self.config_loader.load_strategy("fast")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path

        with suppress(Exception):
            self.executor.set_progress_callbacks(
                started_cb=getattr(self, "_progress_start_callback", None),
                completed_cb=getattr(self, "_progress_callback", None),
                total=len(strategy.hooks),
            )
        execution_result = self.executor.execute_strategy(strategy)
        return execution_result.results

    def run_comprehensive_hooks(self) -> list[HookResult]:
        if self.orchestration_enabled:
            import asyncio

            try:
                asyncio.get_running_loop()

                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._run_comprehensive_hooks_orchestrated()
                    )
                    return future.result()
            except RuntimeError:
                return asyncio.run(self._run_comprehensive_hooks_orchestrated())

        strategy = self.config_loader.load_strategy("comprehensive")

        if self._config_path:
            for hook in strategy.hooks:
                hook.config_path = self._config_path

        with suppress(Exception):
            self.executor.set_progress_callbacks(
                started_cb=getattr(self, "_progress_start_callback", None),
                completed_cb=getattr(self, "_progress_callback", None),
                total=len(strategy.hooks),
            )
        execution_result = self.executor.execute_strategy(strategy)
        return execution_result.results

    async def _run_hooks_parallel(self) -> list[HookResult]:
        import asyncio

        fast_task = self._run_fast_hooks_orchestrated()
        comp_task = self._run_comprehensive_hooks_orchestrated()

        fast_results, comp_results = await asyncio.gather(fast_task, comp_task)
        return fast_results + comp_results

    def run_hooks(self) -> list[HookResult]:
        enable_parallelism = getattr(
            self._orchestration_config, "enable_strategy_parallelism", True
        )
        if self.orchestration_enabled and enable_parallelism:
            import asyncio

            try:
                asyncio.get_running_loop()

                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._run_hooks_parallel())
                    return future.result()
            except RuntimeError:
                return asyncio.run(self._run_hooks_parallel())

        fast_results = self.run_fast_hooks()
        comprehensive_results = self.run_comprehensive_hooks()
        return fast_results + comprehensive_results

    def configure_lsp_optimization(self, enable: bool) -> None:
        if enable == self.lsp_optimization_enabled:
            return

        if enable:
            self.executor = LSPAwareHookExecutor(  # type: ignore[assignment]
                self.console,
                self.pkg_path,
                verbose=getattr(self.executor, "verbose", False),
                quiet=getattr(self.executor, "quiet", True),
                use_tool_proxy=self.tool_proxy_enabled,
            )
        else:
            self.executor = HookExecutor(  # type: ignore[assignment]
                self.console,
                self.pkg_path,
                verbose=getattr(self.executor, "verbose", False),
                quiet=getattr(self.executor, "quiet", True),
            )

        self.lsp_optimization_enabled = enable

        if self._config_path:
            pass

    def configure_tool_proxy(self, enable: bool) -> None:
        if enable == self.tool_proxy_enabled:
            return

        self.tool_proxy_enabled = enable

        try:
            is_lsp_executor = isinstance(self.executor, LSPAwareHookExecutor)
        except TypeError:
            is_lsp_executor = False

        if is_lsp_executor:
            self.executor = LSPAwareHookExecutor(
                self.console,
                self.pkg_path,
                verbose=getattr(self.executor, "verbose", False),
                quiet=getattr(self.executor, "quiet", True),
                use_tool_proxy=enable,
            )

            if self._config_path:
                pass

    async def get_orchestration_stats(self) -> dict[str, t.Any] | None:
        if not self.orchestration_enabled or self._orchestrator is None:
            return None

        return await self._orchestrator.get_cache_stats()

    def get_execution_info(self) -> dict[str, t.Any]:
        info = {
            "lsp_optimization_enabled": self.lsp_optimization_enabled,
            "tool_proxy_enabled": self.tool_proxy_enabled,
            "executor_type": type(self.executor).__name__,
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

        if hasattr(self.executor, "get_execution_mode_summary"):
            info.update(self.executor.get_execution_mode_summary())

        return info

    def get_hook_ids(self) -> list[str]:
        fast_strategy = self.config_loader.load_strategy("fast")
        comprehensive_strategy = self.config_loader.load_strategy("comprehensive")

        all_hooks = fast_strategy.hooks + comprehensive_strategy.hooks
        return [hook.name for hook in all_hooks]

    def get_hook_count(self, suite_name: str) -> int:
        strategy = self.config_loader.load_strategy(suite_name)
        return len(strategy.hooks)

    def install_hooks(self) -> bool:
        self.console.print(
            "[yellow]ℹ️[/yellow] Hook installation not required with direct invocation"
        )
        return True

    def update_hooks(self) -> bool:
        self.console.print(
            "[yellow]ℹ️[/yellow] Hook updates managed via UV dependency resolution"
        )
        return True

    @staticmethod
    def get_hook_summary(
        results: list[HookResult], elapsed_time: float | None = None
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

    @staticmethod
    def validate_hooks_config() -> bool:
        return True
