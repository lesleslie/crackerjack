"""Hook Orchestrator for ACB integration.

ACB-powered orchestration layer managing hook lifecycle, dependency resolution,
and execution strategies. Supports dual execution modes for gradual migration.

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Structured logging with context fields
- Protocol-based interfaces
"""

from __future__ import annotations

import asyncio
import logging
import typing as t
from collections import Counter
from contextlib import suppress
from typing import cast
from uuid import UUID

from acb.depends import depends
from pydantic import BaseModel, Field

from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.events import WorkflowEvent, WorkflowEventBus
from crackerjack.models.qa_results import QAResultStatus
from crackerjack.models.task import HookResult

if t.TYPE_CHECKING:
    from crackerjack.executors.hook_executor import HookExecutor
    from crackerjack.orchestration.cache.memory_cache import MemoryCacheAdapter
    from crackerjack.orchestration.cache.tool_proxy_cache import ToolProxyCacheAdapter
    from crackerjack.orchestration.execution_strategies import ExecutionContext

# ACB Module Registration (REQUIRED)
MODULE_ID = UUID(
    "01937d86-ace0-7000-8000-000000000003"
)  # Static UUID7 for reproducible module identity
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


class HookOrchestratorSettings(BaseModel):
    """Settings for hook orchestration."""

    max_parallel_hooks: int = Field(default=3, ge=1, le=10)
    default_timeout: int = Field(default=300, ge=30, le=1800)
    enable_caching: bool = True
    enable_dependency_resolution: bool = True
    retry_on_failure: bool = False
    cache_backend: str = Field(
        default="tool_proxy", pattern="^(tool_proxy|redis|memory)$"
    )
    execution_mode: str = Field(default="acb", pattern="^(legacy|acb)$")
    # Phase 5-7: Triple parallelism settings
    enable_adaptive_execution: bool = True  # Use adaptive strategy (dependency-aware)


class HookOrchestratorAdapter:
    """ACB-powered hook orchestration layer.

    Manages hook lifecycle, dependency resolution, and execution strategies.
    Supports dual execution mode: pre-commit CLI (legacy) and direct adapters (ACB).

    Features:
    - Async parallel execution with resource limits
    - Dependency resolution between hooks
    - Content-based caching integration
    - Dual execution mode for gradual migration
    - Comprehensive structured logging

    Architecture:
    - Legacy mode (Phase 3-7): Delegates to existing HookExecutor
    - ACB mode (Phase 8+): Direct adapter.check() calls via depends.get()

    Example:
        ```python
        from acb.depends import depends
        from crackerjack.orchestration import HookOrchestratorAdapter

        # Initialize orchestrator
        orchestrator = await depends.get(HookOrchestratorAdapter)
        await orchestrator.init()

        # Execute strategy (legacy mode during Phase 3-7)
        results = await orchestrator.execute_strategy(
            strategy=fast_strategy, execution_mode="legacy"
        )
        ```
    """

    def __init__(
        self,
        settings: HookOrchestratorSettings | None = None,
        hook_executor: HookExecutor | None = None,
        cache_adapter: ToolProxyCacheAdapter | MemoryCacheAdapter | None = None,
        event_bus: WorkflowEventBus | None = None,
        execution_context: ExecutionContext | None = None,
    ) -> None:
        """Initialize Hook Orchestrator.

        Args:
            settings: Optional settings override
            hook_executor: Optional HookExecutor for legacy mode delegation
            cache_adapter: Optional cache adapter (auto-selected from settings.cache_backend if not provided)
            execution_context: Optional execution context for adapters that need it
        """
        self.settings = settings or HookOrchestratorSettings()
        self._hook_executor = hook_executor
        self._cache_adapter = cache_adapter
        self._dependency_graph: dict[str, list[str]] = {}
        self.execution_context = execution_context
        self._initialized = False
        self._cache_hits = 0
        self._cache_misses = 0
        self._event_bus = event_bus or self._resolve_event_bus()

        logger.debug(
            "HookOrchestratorAdapter initialized",
            extra={
                "has_settings": settings is not None,
                "has_executor": hook_executor is not None,
                "has_cache": cache_adapter is not None,
            },
        )

    @staticmethod
    def _resolve_event_bus() -> WorkflowEventBus | None:
        """Resolve workflow event bus from dependency injection."""
        try:
            return cast(WorkflowEventBus, depends.get_sync(WorkflowEventBus))
        except Exception:
            logger.debug("Workflow event bus not available during orchestrator setup")
            return None

    async def init(self) -> None:
        """Initialize orchestrator and build dependency graph."""
        if self._initialized:
            logger.debug("HookOrchestratorAdapter already initialized")
            return

        # Build dependency graph for hook execution order
        self._build_dependency_graph()

        # Initialize cache adapter if caching enabled
        if self.settings.enable_caching and not self._cache_adapter:
            logger.debug(
                "Initializing cache adapter",
                extra={"cache_backend": self.settings.cache_backend},
            )

            # Auto-select cache backend
            if self.settings.cache_backend == "tool_proxy":
                from crackerjack.orchestration.cache.tool_proxy_cache import (
                    ToolProxyCacheAdapter,
                )

                self._cache_adapter = ToolProxyCacheAdapter()
            elif self.settings.cache_backend == "memory":
                from crackerjack.orchestration.cache.memory_cache import (
                    MemoryCacheAdapter,
                )

                self._cache_adapter = MemoryCacheAdapter()
            else:
                logger.warning(
                    f"Unknown cache backend: {self.settings.cache_backend}, disabling caching"
                )
                self.settings.enable_caching = False

        # Initialize cache if provided
        if self._cache_adapter:
            await self._cache_adapter.init()
            logger.debug("Cache adapter initialized")

        self._initialized = True
        logger.info(
            "HookOrchestratorAdapter initialization complete",
            extra={
                "max_parallel_hooks": self.settings.max_parallel_hooks,
                "enable_caching": self.settings.enable_caching,
                "enable_dependency_resolution": self.settings.enable_dependency_resolution,
                "execution_mode": self.settings.execution_mode,
                "dependency_count": len(self._dependency_graph),
                "cache_backend": self.settings.cache_backend
                if self.settings.enable_caching
                else "disabled",
            },
        )

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "Hook Orchestrator"

    def _build_dependency_graph(self) -> None:
        """Build dependency graph for hook execution order.

        Dependency rules:
        - gitleaks must run before bandit (secrets before security)
        - zuban must run before refurb (types before refactoring)
        - formatting hooks run first (ruff-format, mdformat)
        - validation hooks run early (check-yaml, check-toml)
        """
        self._dependency_graph = {
            # Gitleaks before security analysis
            "bandit": ["gitleaks"],
            "skylos": ["gitleaks"],
            # Type checking before refactoring
            "refurb": ["zuban"],
            "creosote": ["zuban"],
            # Formatting before linting
            "ruff-check": ["ruff-format"],
            "codespell": ["ruff-format", "mdformat"],
            # Complexity analysis after refactoring
            "complexipy": ["refurb"],
        }

        logger.debug(
            "Built hook dependency graph",
            extra={
                "dependency_count": len(self._dependency_graph),
                "dependent_hooks": list(self._dependency_graph.keys()),
            },
        )

    async def execute_strategy(
        self,
        strategy: HookStrategy,
        execution_mode: str | None = None,
        progress_callback: t.Callable[[int, int], None] | None = None,
        progress_start_callback: t.Callable[[int, int], None] | None = None,
        execution_context: ExecutionContext | None = None,
    ) -> list[HookResult]:
        """Execute hook strategy with specified mode.

        Args:
            strategy: Hook strategy (fast or comprehensive)
            execution_mode: "legacy" (pre-commit CLI) or "acb" (direct adapters)
                          Defaults to settings.execution_mode if not specified
            progress_callback: Optional callback(completed, total) for progress updates

        Returns:
            List of HookResult objects

        Raises:
            ValueError: If execution_mode is invalid
            RuntimeError: If orchestrator not initialized
        """
        if not self._initialized:
            raise RuntimeError("HookOrchestrator not initialized. Call init() first.")

        mode = execution_mode or self.settings.execution_mode

        logger.info(
            "Executing hook strategy",
            extra={
                "strategy_name": strategy.name,
                "hook_count": len(strategy.hooks),
                "execution_mode": mode,
                "parallel": strategy.parallel,
                "max_workers": strategy.max_workers,
            },
        )

        await self._publish_event(
            WorkflowEvent.HOOK_STRATEGY_STARTED,
            {
                "strategy": strategy.name,
                "execution_mode": mode,
                "hook_count": len(strategy.hooks),
            },
        )

        try:
            if mode == "legacy":
                results = await self._execute_legacy_mode(strategy)
            elif mode == "acb":
                results = await self._execute_acb_mode(
                    strategy,
                    progress_callback,
                    progress_start_callback,
                )
            else:
                raise ValueError(
                    f"Invalid execution mode: {mode}. Must be 'legacy' or 'acb'"
                )
        except Exception as exc:
            await self._publish_event(
                WorkflowEvent.HOOK_STRATEGY_FAILED,
                {
                    "strategy": strategy.name,
                    "execution_mode": mode,
                    "error": str(exc),
                },
            )
            raise

        await self._publish_event(
            WorkflowEvent.HOOK_STRATEGY_COMPLETED,
            {
                "strategy": strategy.name,
                "execution_mode": mode,
                "summary": self._summarize_results(results),
            },
        )

        return results

    async def _execute_legacy_mode(self, strategy: HookStrategy) -> list[HookResult]:
        """Execute hooks via pre-commit CLI (existing HookExecutor).

        This is the bridge to the existing system during Phase 3-7.
        Delegates to HookExecutor which calls pre-commit CLI via subprocess.

        Args:
            strategy: Hook strategy to execute

        Returns:
            List of HookResult objects from HookExecutor

        Raises:
            RuntimeError: If HookExecutor not provided during initialization
        """
        logger.debug(
            "Using legacy pre-commit execution mode",
            extra={
                "strategy_name": strategy.name,
                "has_executor": self._hook_executor is not None,
            },
        )

        if not self._hook_executor:
            raise RuntimeError(
                "Legacy mode requires HookExecutor. "
                "Pass hook_executor during initialization or use execution_mode='acb'"
            )

        # Delegate to existing HookExecutor
        # This maintains full backward compatibility with current system
        execution_result = self._hook_executor.execute_strategy(strategy)

        logger.info(
            "Legacy mode execution complete",
            extra={
                "strategy_name": strategy.name,
                "total_hooks": len(execution_result.results),
                "passed": execution_result.passed_count,
                "failed": execution_result.failed_count,
                "duration": execution_result.total_duration,
            },
        )

        return execution_result.results

    async def _execute_acb_mode(
        self,
        strategy: HookStrategy,
        progress_callback: t.Callable[[int, int], None] | None = None,
        progress_start_callback: t.Callable[[int, int], None] | None = None,
    ) -> list[HookResult]:
        """Execute hooks via direct adapter calls (ACB-powered).

        This is the target architecture for Phase 8+.
        Calls adapter.check() directly via depends.get() instead of subprocess.

        Args:
            strategy: Hook strategy to execute
            progress_callback: Optional callback(completed, total) for progress updates

        Returns:
            List of HookResult objects from direct adapter execution
        """
        logger.debug(
            "Using ACB direct adapter execution mode",
            extra={
                "strategy_name": strategy.name,
                "enable_adaptive_execution": self.settings.enable_adaptive_execution,
            },
        )

        # NEW Phase 5-7: Use adaptive strategy for dependency-aware parallel execution
        if self.settings.enable_adaptive_execution:
            from crackerjack.orchestration.strategies.adaptive_strategy import (
                AdaptiveExecutionStrategy,
            )

            logger.info(
                "Using adaptive execution strategy with dependency-aware batching",
                extra={
                    "strategy_name": strategy.name,
                    "max_parallel": strategy.max_workers
                    or self.settings.max_parallel_hooks,
                    "dependency_graph_size": len(self._dependency_graph),
                },
            )

            execution_strategy = AdaptiveExecutionStrategy(
                dependency_graph=self._dependency_graph,
                max_parallel=strategy.max_workers or self.settings.max_parallel_hooks,
                default_timeout=self.settings.default_timeout,
                stop_on_critical_failure=True,
            )

            results = await execution_strategy.execute(
                hooks=strategy.hooks,
                executor_callable=self._execute_single_hook,
                progress_callback=progress_callback,
                progress_start_callback=progress_start_callback,
            )
        elif strategy.parallel:
            # Fallback to simple parallel execution without dependency resolution
            results = await self._execute_parallel(strategy.hooks, strategy.max_workers)
        else:
            # Sequential execution
            results = await self._execute_sequential(strategy.hooks)

        logger.info(
            "ACB mode execution complete",
            extra={
                "strategy_name": strategy.name,
                "total_hooks": len(results),
                "passed": sum(1 for r in results if r.status == "passed"),
                "failed": sum(1 for r in results if r.status == "failed"),
                "errors": sum(1 for r in results if r.status in ("timeout", "error")),
            },
        )

        return results

    def _resolve_dependencies(
        self, hooks: list[HookDefinition]
    ) -> list[HookDefinition]:
        """Resolve hook dependencies and return execution order.

        Uses topological sort to order hooks based on dependency graph.

        Args:
            hooks: Unordered list of hooks

        Returns:
            Ordered list of hooks respecting dependencies

        Algorithm:
        1. Build in-degree map (count of dependencies per hook)
        2. Start with hooks having zero dependencies
        3. Process hooks in layers, removing satisfied dependencies
        4. Hooks without dependencies execute in original order
        """
        # Build hook name to hook object mapping with original indices
        hook_map = {hook.name: hook for hook in hooks}
        hook_indices = {hook.name: idx for idx, hook in enumerate(hooks)}

        # Build in-degree map (how many dependencies each hook has)
        # Only count dependencies that are actually present in the hooks list
        in_degree = {hook.name: 0 for hook in hooks}
        for hook_name in hook_map:
            if hook_name in self._dependency_graph:
                # Only count dependencies that are in the current hooks list
                deps_in_list = [
                    dep for dep in self._dependency_graph[hook_name] if dep in hook_map
                ]
                in_degree[hook_name] = len(deps_in_list)

        # Queue of hooks ready to execute (zero dependencies)
        # Maintain original order for hooks with same in-degree
        ready_queue = [hook for hook in hooks if in_degree[hook.name] == 0]
        ordered = []

        # Process hooks in dependency order
        while ready_queue:
            # Take next ready hook (first in original order)
            current_hook = ready_queue.pop(0)
            ordered.append(current_hook)

            # Update in-degrees for dependent hooks
            for hook_name, deps in self._dependency_graph.items():
                if current_hook.name in deps and hook_name in in_degree:
                    in_degree[hook_name] -= 1
                    if in_degree[hook_name] == 0 and hook_name in hook_map:
                        ready_queue.append(hook_map[hook_name])

            # Re-sort ready_queue by original index to maintain stable order
            ready_queue.sort(key=lambda h: hook_indices[h.name])

        logger.debug(
            "Resolved hook dependencies",
            extra={
                "input_count": len(hooks),
                "output_count": len(ordered),
                "reordered": len(hooks) != len(ordered) or hooks != ordered,
            },
        )

        return ordered

    async def _execute_parallel(
        self,
        hooks: list[HookDefinition],
        max_workers: int = 3,
    ) -> list[HookResult]:
        """Execute hooks in parallel with resource limits.

        Args:
            hooks: Hooks to execute
            max_workers: Maximum concurrent executions

        Returns:
            List of HookResult objects
        """
        max_parallel = min(max_workers, self.settings.max_parallel_hooks)
        semaphore = asyncio.Semaphore(max_parallel)

        logger.debug(
            "Starting parallel execution",
            extra={
                "hook_count": len(hooks),
                "max_parallel": max_parallel,
            },
        )

        async def execute_with_limit(hook: HookDefinition) -> HookResult:
            async with semaphore:
                return await self._execute_single_hook(hook)

        tasks = [execute_with_limit(hook) for hook in hooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error HookResults
        final_results = []
        for hook, result in zip(hooks, results):
            if isinstance(result, HookResult):
                final_results.append(result)
            else:
                logger.error(
                    "Hook execution raised exception",
                    extra={
                        "hook": hook.name,
                        "exception": str(result),
                        "exception_type": type(result).__name__,
                    },
                )
                final_results.append(self._error_result(hook, result))

        logger.debug(
            "Parallel execution complete",
            extra={
                "total_hooks": len(final_results),
                "successful": sum(
                    1 for r in final_results if isinstance(r, HookResult)
                ),
            },
        )

        return final_results

    async def _execute_sequential(
        self, hooks: list[HookDefinition]
    ) -> list[HookResult]:
        """Execute hooks sequentially.

        Args:
            hooks: Hooks to execute

        Returns:
            List of HookResult objects
        """
        logger.debug("Starting sequential execution", extra={"hook_count": len(hooks)})

        results = []
        for hook in hooks:
            result = await self._execute_single_hook(hook)
            results.append(result)

            # Early exit on critical failures
            if result.status == "failed" and hook.security_level.value == "critical":
                logger.warning(
                    f"Critical hook {hook.name} failed, stopping execution",
                    extra={
                        "hook": hook.name,
                        "security_level": "critical",
                        "remaining_hooks": len(hooks) - len(results),
                    },
                )
                break

        logger.debug(
            "Sequential execution complete",
            extra={
                "total_hooks": len(results),
                "executed": len(results),
                "skipped": len(hooks) - len(results),
            },
        )

        return results

    async def _execute_single_hook(self, hook: HookDefinition) -> HookResult:
        """Execute a single hook (adapter or subprocess) with caching and events."""
        logger.debug(
            f"Executing hook: {hook.name}",
            extra={
                "hook": hook.name,
                "timeout": hook.timeout,
                "stage": hook.stage.value,
            },
        )
        await self._publish_event(
            WorkflowEvent.HOOK_EXECUTION_STARTED,
            {
                "hook": hook.name,
                "stage": hook.stage.value,
                "security_level": hook.security_level.value,
            },
        )

        # Cache fast-path
        cached = await self._try_get_cached(hook)
        if cached is not None:
            await self._publish_event(
                WorkflowEvent.HOOK_EXECUTION_COMPLETED,
                {
                    "hook": hook.name,
                    "stage": hook.stage.value,
                    "status": cached.status,
                    "duration": cached.duration,
                    "cached": True,
                },
            )
            return cached

        try:
            import time

            start_time = time.time()

            # Execute hooks via direct adapter calls or subprocess if no adapter exists
            adapter = self._build_adapter(hook)
            if adapter is not None:
                result = await self._run_adapter(adapter, hook, start_time)
            else:
                result = self._run_subprocess(hook, start_time)

            await self._maybe_cache(hook, result)
        except Exception as exc:
            await self._publish_event(
                WorkflowEvent.HOOK_EXECUTION_FAILED,
                {"hook": hook.name, "stage": hook.stage.value, "error": str(exc)},
            )
            raise

        await self._publish_event(
            WorkflowEvent.HOOK_EXECUTION_COMPLETED,
            {
                "hook": hook.name,
                "stage": hook.stage.value,
                "status": result.status,
                "duration": result.duration,
                "cached": False,
            },
        )
        return result

    async def _try_get_cached(self, hook: HookDefinition) -> HookResult | None:
        if not (self.settings.enable_caching and self._cache_adapter):
            return None
        cache_key = self._cache_adapter.compute_key(hook, files=[])
        cached = await self._cache_adapter.get(cache_key)
        if cached:
            self._cache_hits += 1
            logger.debug(
                f"Cache hit for hook {hook.name}",
                extra={
                    "hook": hook.name,
                    "cache_key": cache_key,
                    "cache_hits": self._cache_hits,
                },
            )
            return cached
        self._cache_misses += 1
        logger.debug(
            f"Cache miss for hook {hook.name}",
            extra={
                "hook": hook.name,
                "cache_key": cache_key,
                "cache_misses": self._cache_misses,
            },
        )
        return None

    @staticmethod
    def _pass_result(hook: HookDefinition, duration: float) -> HookResult:
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="passed",
            duration=duration,
            files_processed=0,
            issues_found=[],
            stage=hook.stage.value,
            exit_code=None,  # No error for passed hooks
            error_message=None,
            is_timeout=False,
        )

    def _build_adapter(self, hook: HookDefinition) -> t.Any | None:
        """Build adapter for hook, dispatching to specific adapter factories."""
        try:
            adapter_factory = self._get_adapter_factory(hook.name)
            if adapter_factory:
                return adapter_factory(hook)
        except Exception:
            return None
        return None

    def _get_adapter_factory(
        self, hook_name: str
    ) -> t.Callable[[HookDefinition], t.Any] | None:
        """Get adapter factory function for hook name."""
        factories: dict[str, t.Callable[[HookDefinition], t.Any]] = {
            "ruff-check": self._build_ruff_adapter,
            "ruff-format": self._build_ruff_adapter,
            "bandit": self._build_bandit_adapter,
            "codespell": self._build_codespell_adapter,
            "gitleaks": self._build_gitleaks_adapter,
            "skylos": self._build_skylos_adapter,
            "zuban": self._build_zuban_adapter,
            "complexipy": self._build_complexipy_adapter,
            "creosote": self._build_creosote_adapter,
            "refurb": self._build_refurb_adapter,
            "pyrefly": self._build_refurb_adapter,
            "mdformat": self._build_mdformat_adapter,
        }
        return factories.get(hook_name)

    @staticmethod
    def _build_ruff_adapter(hook: HookDefinition) -> t.Any:
        """Build Ruff adapter for format or check mode."""
        from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings

        is_format_mode = "format" in hook.name
        is_check_mode = "check" in hook.name

        return RuffAdapter(
            settings=RuffSettings(
                mode="format" if is_format_mode else "check",
                fix_enabled=True,  # Enable fixing for both check and format modes
                unsafe_fixes=is_check_mode,  # Enable unsafe fixes for check mode only
            )
        )

    @staticmethod
    def _build_bandit_adapter(hook: HookDefinition) -> t.Any:
        """Build Bandit security adapter."""
        from crackerjack.adapters.sast.bandit import BanditAdapter

        return BanditAdapter()

    @staticmethod
    def _build_codespell_adapter(hook: HookDefinition) -> t.Any:
        """Build Codespell lint adapter."""
        from crackerjack.adapters.lint.codespell import CodespellAdapter

        return CodespellAdapter()

    @staticmethod
    def _build_gitleaks_adapter(hook: HookDefinition) -> t.Any:
        """Build Gitleaks security adapter."""
        from crackerjack.adapters.security.gitleaks import GitleaksAdapter

        return GitleaksAdapter()

    def _build_skylos_adapter(self, hook: HookDefinition) -> t.Any:
        """Build Skylos LSP adapter."""
        from crackerjack.adapters.lsp.skylos import SkylosAdapter

        if self.execution_context is None:
            msg = f"Execution context required for {hook.name} adapter"
            raise ValueError(msg)
        return SkylosAdapter(context=self.execution_context)

    @staticmethod
    def _build_zuban_adapter(hook: HookDefinition) -> t.Any:
        """Build Zuban type checking adapter."""
        from crackerjack.adapters.type.zuban import ZubanAdapter, ZubanSettings

        return ZubanAdapter(settings=ZubanSettings())

    @staticmethod
    def _build_complexipy_adapter(hook: HookDefinition) -> t.Any:
        """Build Complexipy complexity adapter."""
        from crackerjack.adapters.complexity.complexipy import ComplexipyAdapter

        return ComplexipyAdapter()

    @staticmethod
    def _build_creosote_adapter(hook: HookDefinition) -> t.Any:
        """Build Creosote refactor adapter."""
        from crackerjack.adapters.refactor.creosote import CreosoteAdapter

        return CreosoteAdapter()

    @staticmethod
    def _build_refurb_adapter(hook: HookDefinition) -> t.Any:
        """Build Refurb refactor adapter."""
        from crackerjack.adapters.refactor.refurb import RefurbAdapter

        return RefurbAdapter()

    @staticmethod
    def _build_mdformat_adapter(hook: HookDefinition) -> t.Any:
        """Build Mdformat markdown adapter."""
        from crackerjack.adapters.format.mdformat import MdformatAdapter

        return MdformatAdapter()

    @staticmethod
    def _get_reporting_tools() -> set[str]:
        """Get the set of tools that report issues."""
        return {"complexipy", "refurb", "gitleaks", "creosote"}

    @staticmethod
    def _get_formatters() -> set[str]:
        """Get the set of formatting tools."""
        return {"ruff-format"}

    def _determine_status(self, hook: HookDefinition, qa_result: t.Any) -> str:
        """Determine the status based on hook name and QA result."""
        reporting_tools = self._get_reporting_tools()
        formatters = self._get_formatters()

        # Override status for tools that found issues but returned SUCCESS/WARNING
        if (
            (hook.name in reporting_tools or hook.name in formatters)
            and qa_result.issues_found > 0
            and qa_result.status in (QAResultStatus.SUCCESS, QAResultStatus.WARNING)
        ):
            return "failed"  # Trigger auto-fix stage
        return (
            "passed"
            if qa_result.status in (QAResultStatus.SUCCESS, QAResultStatus.WARNING)
            else "failed"
        )

    @staticmethod
    def _build_issues_list(qa_result: t.Any) -> list[str]:
        """Build the issues list from the QA result.

        This method uses the adapter's pre-formatted details string directly
        instead of re-parsing it, which preserves the original formatting and
        prevents loss of detailed error information.

        Args:
            qa_result: QAResult from adapter execution

        Returns:
            List of issue strings for display. Returns empty list if no issues.
        """
        if qa_result.issues_found == 0:
            return []

        # NEW: Use adapter's pre-formatted details directly
        if qa_result.details:
            # Parse detail lines from the adapter's formatted output
            detail_lines = [
                line.strip()
                for line in qa_result.details.split("\n")
                if line.strip() and not line.strip().startswith("...")
            ]

            # If we successfully parsed details, use them
            if detail_lines:
                # Show first 20 issues, then add summary for remainder
                max_displayed = 20
                if len(detail_lines) > max_displayed:
                    issues = detail_lines[:max_displayed]
                    remaining = len(detail_lines) - max_displayed
                    issues.append(
                        f"... and {remaining} more issue{'s' if remaining != 1 else ''} "
                        f"(run with --ai-debug for full details)"
                    )
                else:
                    issues = detail_lines

                # If qa_result reports more issues than we have details for, note it
                if qa_result.issues_found > len(detail_lines):
                    extra = qa_result.issues_found - len(detail_lines)
                    issues.append(
                        f"... and {extra} additional issue{'s' if extra != 1 else ''} without details"
                    )

                return issues

        # Fallback: No details available or details parsing failed
        # This should only happen when the adapter doesn't provide detailed output
        count = qa_result.issues_found
        return [
            f"{count} issue{'s' if count != 1 else ''} found (run with --ai-debug for full details)"
        ]

    @staticmethod
    def _extract_error_details(
        hook: HookDefinition, qa_result: t.Any, status: str, issues: list[str]
    ) -> tuple[int | None, str | None, list[str]]:
        """Extract error details for failed hooks from adapter results.

        Note: This method should only add the generic fallback if _build_issues_list
        hasn't already provided a fallback message. This prevents double-fallback.

        Args:
            hook: Hook definition
            qa_result: QAResult from adapter execution
            status: Hook status (passed/failed)
            issues: Issues list from _build_issues_list

        Returns:
            Tuple of (exit_code, error_message, updated_issues)
        """
        exit_code = None
        error_message = None

        if status == "failed":
            if hasattr(qa_result, "details") and qa_result.details:
                # For adapter-based hooks, use details as error message
                error_message = qa_result.details[:500]  # Truncate if very long

                # Only extract error from details if issues list is truly empty
                # (not just a fallback message from _build_issues_list)
                if not issues:
                    error_lines = [
                        line.strip()
                        for line in qa_result.details.split("\n")
                        if line.strip()
                    ][:10]
                    issues = error_lines or ["Hook failed with no parseable output"]
            elif not issues:
                # Only add generic fallback if we have absolutely no information
                # This should be rare since _build_issues_list provides a fallback
                issues = [
                    f"Hook {hook.name} failed with no detailed output (exit code: "
                    f"{
                        qa_result.exit_code
                        if hasattr(qa_result, 'exit_code')
                        else 'unknown'
                    })"
                ]

        return exit_code, error_message, issues

    @staticmethod
    def _calculate_total_issues(
        qa_result: t.Any, status: str, issues: list[str]
    ) -> int:
        """Calculate the total count of issues from qa_result.

        This method distinguishes between:
        1. Genuine code issues (show actual count)
        2. Configuration/tool errors (show 0, not forced to 1)
        3. Parsing failures (may show 1 if no issues parseable)

        The key insight: QAResultStatus.ERROR indicates a config/tool error,
        not a code quality issue. These should show 0 issues, not 1.
        """
        # Get the actual total count of issues from qa_result
        # This may be larger than len(issues) if issues were truncated for display
        total_issues = (
            qa_result.issues_found
            if hasattr(qa_result, "issues_found")
            else len(issues)
        )

        # Only force "1 issue" for genuine parsing failures, not config errors
        if status == "failed" and total_issues == 0:
            # Check if this is a config/tool error vs code quality failure
            if (
                hasattr(qa_result, "status")
                and qa_result.status == QAResultStatus.ERROR
            ):
                # Config/tool error - show actual count (0)
                # This prevents misleading "1 issue" for things like:
                # - Missing binary
                # - Invalid configuration
                # - Tool initialization failures
                return 0
            else:
                # Parsing failure or unexpected error - show 1 to indicate problem
                # This handles cases where the tool found issues but we couldn't parse them
                return max(total_issues, 1)

        return total_issues

    def _create_success_result(
        self, hook: HookDefinition, qa_result: t.Any, start_time: float
    ) -> HookResult:
        """Create a HookResult for successful execution."""
        files_processed = (
            len(qa_result.files_checked) if hasattr(qa_result, "files_checked") else 0
        )
        status = self._determine_status(hook, qa_result)
        issues = self._build_issues_list(qa_result)

        # Extract error details for failed hooks from adapter results
        exit_code, error_message, issues = self._extract_error_details(
            hook, qa_result, status, issues
        )

        # Calculate the total issues count
        total_issues = self._calculate_total_issues(qa_result, status, issues)

        # Determine if this is a config/tool error (not code issues)
        is_config_error = (
            status == "failed"
            and hasattr(qa_result, "status")
            and qa_result.status == QAResultStatus.ERROR
        )

        return HookResult(
            id=hook.name,
            name=hook.name,
            status=status,
            duration=self._elapsed(start_time),
            files_processed=files_processed,
            issues_found=issues,
            issues_count=total_issues,  # Store the actual total count
            stage=hook.stage.value,
            exit_code=exit_code,  # Adapters don't provide exit codes directly
            error_message=error_message,
            is_timeout=False,
            is_config_error=is_config_error,  # Mark config/tool errors
        )

    def _create_timeout_result(
        self, hook: HookDefinition, start_time: float
    ) -> HookResult:
        """Create a HookResult for timeout."""
        duration = self._elapsed(start_time)
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="timeout",
            duration=duration,
            files_processed=0,
            issues_found=[f"Hook timed out after {hook.timeout}s"],
            issues_count=1,  # Timeout counts as 1 issue
            stage=hook.stage.value,
            exit_code=124,  # Standard timeout exit code
            error_message=f"Execution exceeded timeout of {hook.timeout}s",
            is_timeout=True,
        )

    def _create_error_result(
        self, hook: HookDefinition, start_time: float, error: Exception
    ) -> HookResult:
        """Create a HookResult for error."""
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="error",
            duration=self._elapsed(start_time),
            files_processed=0,
            issues_found=[f"Adapter execution error: {error}"],
            issues_count=1,  # Error counts as 1 issue
            stage=hook.stage.value,
            exit_code=1,
            error_message=str(error),
            is_timeout=False,
        )

    async def _run_adapter(
        self, adapter: t.Any, hook: HookDefinition, start_time: float
    ) -> HookResult:
        import asyncio

        try:
            await adapter.init()
            # Let the adapter determine the appropriate files to check
            # Pass None to allow the adapter to scan for appropriate files
            qa_result = await asyncio.wait_for(
                adapter.check(files=None), timeout=hook.timeout
            )
            return self._create_success_result(hook, qa_result, start_time)
        except TimeoutError:
            return self._create_timeout_result(hook, start_time)
        except Exception as e:
            return self._create_error_result(hook, start_time, e)

    def _run_subprocess(self, hook: HookDefinition, start_time: float) -> HookResult:
        import subprocess

        cmd = hook.get_command()
        proc_result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=hook.timeout
        )
        output_text = (proc_result.stdout or "") + (proc_result.stderr or "")

        files_processed = self._extract_file_count(output_text)
        status = self._determine_hook_status(hook, proc_result, output_text)
        issues = self._collect_issues(status, proc_result)

        # Semgrep-specific JSON error parsing
        if hook.name == "semgrep" and status == "failed":
            issues = self._parse_semgrep_json_errors(output_text, issues)

        # Extract error details for failed hooks
        exit_code = proc_result.returncode if status == "failed" else None
        error_message = None
        if status == "failed" and output_text.strip():
            # Capture stdout + stderr for failed hooks (truncate if very long)
            error_message = output_text.strip()[:500]

        # Ensure failed hooks always have at least 1 issue count
        issues_count = max(len(issues), 1 if status == "failed" else 0)

        return HookResult(
            id=hook.name,
            name=hook.name,
            status=status,
            duration=self._elapsed(start_time),
            files_processed=files_processed,
            issues_found=issues,
            issues_count=issues_count,
            stage=hook.stage.value,
            exit_code=exit_code,
            error_message=error_message,
            is_timeout=False,
        )

    @staticmethod
    def _extract_file_count(output_text: str) -> int:
        """Extract file count from subprocess output using regex patterns."""
        import re

        file_count_patterns = [
            r"(\d+)\s+files?\s+would\s+be",
            r"(\d+)\s+files?\s+already\s+formatted",
            r"(\d+)\s+files?\s+processed",
            r"(\d+)\s+files?\s+checked",
            r"(\d+)\s+files?\s+analyzed",
            r"Checking\s+(\d+)\s+files?",
            r"Found\s+(\d+)\s+files?",
            r"(\d+)\s+files?",
        ]

        all_matches = []
        for pattern in file_count_patterns:
            matches = re.findall(pattern, output_text, re.IGNORECASE)
            if matches:
                all_matches.extend([int(m) for m in matches if m.isdigit()])

        return max(all_matches) if all_matches else 0

    def _determine_hook_status(
        self, hook: HookDefinition, proc_result: t.Any, output_text: str
    ) -> str:
        """Determine hook status from subprocess return code and output."""
        base_status = "passed" if proc_result.returncode == 0 else "failed"

        if base_status == "passed":
            return "passed"

        # Check special cases where return code 1 indicates success
        if self._is_formatting_success(hook, proc_result, output_text):
            return "passed"

        # For tools like ruff that return 1 when they detect issues but execute successfully
        # These should still be considered "passed" execution-wise but may have issues found
        if self._is_analysis_tool_success(hook, proc_result):
            return "passed"

        if self._is_bandit_success(hook, proc_result, output_text):
            return "passed"

        return "failed"

    @staticmethod
    def _is_formatting_success(
        hook: HookDefinition, proc_result: t.Any, output_text: str
    ) -> bool:
        """Check if formatting tool return code 1 indicates successful modification."""
        if not hook.is_formatting or proc_result.returncode != 1:
            return False
        return "files were modified by this hook" in output_text.lower()

    @staticmethod
    def _is_analysis_tool_success(hook: HookDefinition, proc_result: t.Any) -> bool:
        """Check if analysis tool return code 1 indicates findings (not failure)."""
        if proc_result.returncode != 1:
            return False
        return hook.name in {
            "creosote",
            "complexipy",
            "refurb",
            "ruff-check",
            "ruff-format",
        }

    @staticmethod
    def _is_bandit_success(
        hook: HookDefinition, proc_result: t.Any, output_text: str
    ) -> bool:
        """Check if bandit return code 1 indicates findings (not failure)."""
        if hook.name != "bandit" or proc_result.returncode != 1:
            return False
        output_text_lower = output_text.lower()
        return (
            "potential issues" in output_text_lower
            or "no issues identified" not in output_text_lower
        )

    @staticmethod
    def _collect_issues(status: str, proc_result: t.Any) -> list[str]:
        """Collect issues from subprocess output if hook failed.

        For subprocess hooks (non-adapter), extracts error information from output.
        Returns list of strings since the display layer handles both string and object types.
        """
        if status == "passed":
            return []

        # Get combined output
        output_text = (proc_result.stdout or "") + (proc_result.stderr or "")
        if not output_text.strip():
            return [
                f"Hook failed with exit code {
                    getattr(proc_result, 'returncode', 'unknown')
                } and no output"
            ]

        # Try to extract meaningful error lines (first 10 non-empty lines)
        error_lines = [
            line.strip() for line in output_text.split("\n") if line.strip()
        ][:10]

        return error_lines or ["Hook failed with non-zero exit code"]

    @staticmethod
    def _parse_semgrep_json_errors(
        output_text: str, fallback_issues: list[str]
    ) -> list[str]:
        """Parse semgrep JSON output to extract errors from errors array.

        Semgrep returns JSON with:
        - "results": Security/code quality findings (usually empty when download fails)
        - "errors": Configuration errors, download failures, etc.

        Args:
            output_text: Combined stdout + stderr from semgrep
            fallback_issues: Issues collected from raw output (used if JSON parsing fails)

        Returns:
            List of formatted error strings
        """
        import json

        try:
            json_data = json.loads(output_text.strip())

            issues = []

            # Extract security findings from results array
            if "results" in json_data:
                for result in json_data.get("results", []):
                    path = result.get("path", "unknown")
                    line_num = result.get("start", {}).get("line", "?")
                    rule_id = result.get("check_id", "unknown-rule")
                    message = result.get("extra", {}).get(
                        "message", "Security issue detected"
                    )
                    issues.append(f"{path}:{line_num} - {rule_id}: {message}")

            # Extract errors (download failures, config errors, etc.)
            if "errors" in json_data:
                for error in json_data.get("errors", []):
                    error_type = error.get("type", "SemgrepError")
                    error_msg = error.get("message", str(error))
                    issues.append(f"{error_type}: {error_msg}")

            return issues or fallback_issues

        except json.JSONDecodeError:
            # JSON parsing failed, use fallback
            return fallback_issues

    async def _maybe_cache(self, hook: HookDefinition, result: HookResult) -> None:
        if not (self.settings.enable_caching and self._cache_adapter):
            return
        cache_key = self._cache_adapter.compute_key(hook, files=[])
        await self._cache_adapter.set(cache_key, result)
        logger.debug(
            f"Cached result for hook {hook.name}",
            extra={
                "hook": hook.name,
                "cache_key": cache_key,
                "status": result.status,
                "files_processed": result.files_processed,
            },
        )

    @staticmethod
    def _elapsed(start_time: float) -> float:
        import time

        return time.time() - start_time

    @staticmethod
    def _error_result(hook: HookDefinition, error: BaseException) -> HookResult:
        """Create error HookResult from exception.

        Args:
            hook: Hook that raised exception
            error: Exception that was raised

        Returns:
            HookResult with error status
        """
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="error",
            duration=0.0,
            files_processed=0,
            issues_found=[str(error)],
            issues_count=1,  # Error counts as 1 issue
            stage=hook.stage.value,
            exit_code=1,
            error_message=str(error),
            is_timeout=False,
        )

    async def get_cache_stats(self) -> dict[str, t.Any]:
        """Get cache statistics including hit/miss ratios.

        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "caching_enabled": self.settings.enable_caching,
            "cache_backend": self.settings.cache_backend
            if self.settings.enable_caching
            else "disabled",
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_requests": self._cache_hits + self._cache_misses,
            "hit_ratio": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
        }

        # Get adapter-specific stats if available
        if self._cache_adapter:
            adapter_stats = await self._cache_adapter.get_stats()
            stats["adapter_stats"] = adapter_stats

        logger.debug("Cache statistics", extra=stats)

        return stats

    async def _publish_event(
        self,
        event: WorkflowEvent,
        payload: dict[str, t.Any],
    ) -> None:
        """Publish an event to the workflow bus if available."""
        if not self._event_bus:
            return

        try:
            await self._event_bus.publish(event, payload)
        except Exception as exc:
            logger.debug(
                "Failed to publish orchestrator event",
                extra={"event": event.value, "error": str(exc)},
            )

    @staticmethod
    def _summarize_results(results: list[HookResult]) -> dict[str, t.Any]:
        """Summarize hook results for telemetry payloads."""
        counts = Counter(result.status for result in results)
        return {
            "counts": dict(counts),
            "total": len(results),
        }


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(HookOrchestratorAdapter)
