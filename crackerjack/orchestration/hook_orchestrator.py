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
from crackerjack.models.task import HookResult

if t.TYPE_CHECKING:
    from crackerjack.executors.hook_executor import HookExecutor
    from crackerjack.orchestration.cache.memory_cache import MemoryCacheAdapter
    from crackerjack.orchestration.cache.tool_proxy_cache import ToolProxyCacheAdapter

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
    execution_mode: str = Field(default="legacy", pattern="^(legacy|acb)$")
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
    ) -> None:
        """Initialize Hook Orchestrator.

        Args:
            settings: Optional settings override
            hook_executor: Optional HookExecutor for legacy mode delegation
            cache_adapter: Optional cache adapter (auto-selected from settings.cache_backend if not provided)
        """
        self.settings = settings or HookOrchestratorSettings()
        self._hook_executor = hook_executor
        self._cache_adapter = cache_adapter
        self._dependency_graph: dict[str, list[str]] = {}
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

    def _resolve_event_bus(self) -> WorkflowEventBus | None:
        """Resolve workflow event bus from dependency injection."""
        try:
            return cast(WorkflowEventBus, depends.get(WorkflowEventBus))
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
    ) -> list[HookResult]:
        """Execute hook strategy with specified mode.

        Args:
            strategy: Hook strategy (fast or comprehensive)
            execution_mode: "legacy" (pre-commit CLI) or "acb" (direct adapters)
                          Defaults to settings.execution_mode if not specified

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
                results = await self._execute_acb_mode(strategy)
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

    async def _execute_acb_mode(self, strategy: HookStrategy) -> list[HookResult]:
        """Execute hooks via direct adapter calls (ACB-powered).

        This is the target architecture for Phase 8+.
        Calls adapter.check() directly via depends.get() instead of subprocess.

        Args:
            strategy: Hook strategy to execute

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
        """Execute a single hook (ACB adapter call) with caching.

        This is a placeholder for Phase 8+ implementation.
        Will call adapter.check() directly via depends.get().

        Args:
            hook: Hook definition to execute

        Returns:
            HookResult from adapter execution or cache
        """
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

        # Check cache if enabled
        if self.settings.enable_caching and self._cache_adapter:
            # Compute cache key (using empty file list for now - Phase 8 will provide real files)
            cache_key = self._cache_adapter.compute_key(hook, files=[])

            # Try to get cached result
            cached_result = await self._cache_adapter.get(cache_key)
            if cached_result:
                self._cache_hits += 1
                logger.debug(
                    f"Cache hit for hook {hook.name}",
                    extra={
                        "hook": hook.name,
                        "cache_key": cache_key,
                        "cache_hits": self._cache_hits,
                    },
                )
                await self._publish_event(
                    WorkflowEvent.HOOK_EXECUTION_COMPLETED,
                    {
                        "hook": hook.name,
                        "stage": hook.stage.value,
                        "status": cached_result.status,
                        "duration": cached_result.duration,
                        "cached": True,
                    },
                )
                return cached_result

            self._cache_misses += 1
            logger.debug(
                f"Cache miss for hook {hook.name}",
                extra={
                    "hook": hook.name,
                    "cache_key": cache_key,
                    "cache_misses": self._cache_misses,
                },
            )

        # TODO Phase 8: Implement direct adapter execution
        # Example:
        # if hook.name == "bandit":
        #     adapter = await depends.get(BanditAdapter)
        #     result = await adapter.check(files=[...])
        #     return self._convert_to_hook_result(result)

        try:
            # Placeholder for Phase 3-7
            result = HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.0,
            )

            # Cache result if caching enabled
            if self.settings.enable_caching and self._cache_adapter:
                await self._cache_adapter.set(cache_key, result)
                logger.debug(
                    f"Cached result for hook {hook.name}",
                    extra={
                        "hook": hook.name,
                        "cache_key": cache_key,
                        "status": result.status,
                    },
                )
        except Exception as exc:
            await self._publish_event(
                WorkflowEvent.HOOK_EXECUTION_FAILED,
                {
                    "hook": hook.name,
                    "stage": hook.stage.value,
                    "error": str(exc),
                },
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

    def _error_result(self, hook: HookDefinition, error: BaseException) -> HookResult:
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

    def _summarize_results(self, results: list[HookResult]) -> dict[str, t.Any]:
        """Summarize hook results for telemetry payloads."""
        counts = Counter(result.status for result in results)
        return {
            "counts": dict(counts),
            "total": len(results),
        }


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(HookOrchestratorAdapter)
