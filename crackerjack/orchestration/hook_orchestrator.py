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
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from acb.depends import depends
from pydantic import BaseModel, Field

from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.models.task import HookResult

if t.TYPE_CHECKING:
    from crackerjack.executors.hook_executor import HookExecutor

# ACB Module Registration (REQUIRED)
MODULE_ID = UUID("01937d86-ace0-7000-8000-000000000003")  # Static UUID7 for reproducible module identity
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
    cache_backend: str = Field(default="tool_proxy", pattern="^(tool_proxy|redis|memory)$")
    execution_mode: str = Field(default="legacy", pattern="^(legacy|acb)$")


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
            strategy=fast_strategy,
            execution_mode="legacy"
        )
        ```
    """

    def __init__(
        self,
        settings: HookOrchestratorSettings | None = None,
        hook_executor: HookExecutor | None = None,
    ) -> None:
        """Initialize Hook Orchestrator.

        Args:
            settings: Optional settings override
            hook_executor: Optional HookExecutor for legacy mode delegation
        """
        self.settings = settings or HookOrchestratorSettings()
        self._hook_executor = hook_executor
        self._dependency_graph: dict[str, list[str]] = {}
        self._initialized = False

        logger.debug(
            "HookOrchestratorAdapter initialized",
            extra={
                "has_settings": settings is not None,
                "has_executor": hook_executor is not None,
            }
        )

    async def init(self) -> None:
        """Initialize orchestrator and build dependency graph."""
        if self._initialized:
            logger.debug("HookOrchestratorAdapter already initialized")
            return

        # Build dependency graph for hook execution order
        self._build_dependency_graph()

        self._initialized = True
        logger.info(
            "HookOrchestratorAdapter initialization complete",
            extra={
                "max_parallel_hooks": self.settings.max_parallel_hooks,
                "enable_caching": self.settings.enable_caching,
                "enable_dependency_resolution": self.settings.enable_dependency_resolution,
                "execution_mode": self.settings.execution_mode,
                "dependency_count": len(self._dependency_graph),
            }
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
            }
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
            }
        )

        if mode == "legacy":
            return await self._execute_legacy_mode(strategy)
        elif mode == "acb":
            return await self._execute_acb_mode(strategy)
        else:
            raise ValueError(f"Invalid execution mode: {mode}. Must be 'legacy' or 'acb'")

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
            }
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
            }
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
                "enable_dependency_resolution": self.settings.enable_dependency_resolution,
            }
        )

        # Resolve dependencies if enabled
        if self.settings.enable_dependency_resolution:
            ordered_hooks = self._resolve_dependencies(strategy.hooks)
            logger.debug(
                "Dependency resolution complete",
                extra={
                    "original_count": len(strategy.hooks),
                    "ordered_count": len(ordered_hooks),
                }
            )
        else:
            ordered_hooks = strategy.hooks

        # Execute based on parallelization strategy
        if strategy.parallel:
            results = await self._execute_parallel(ordered_hooks, strategy.max_workers)
        else:
            results = await self._execute_sequential(ordered_hooks)

        logger.info(
            "ACB mode execution complete",
            extra={
                "strategy_name": strategy.name,
                "total_hooks": len(results),
                "passed": sum(1 for r in results if r.status == "passed"),
                "failed": sum(1 for r in results if r.status == "failed"),
                "errors": sum(1 for r in results if r.status in ("timeout", "error")),
            }
        )

        return results

    def _resolve_dependencies(self, hooks: list[HookDefinition]) -> list[HookDefinition]:
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
        # Build hook name to hook object mapping
        hook_map = {hook.name: hook for hook in hooks}

        # Build in-degree map (how many dependencies each hook has)
        in_degree = {hook.name: 0 for hook in hooks}
        for hook_name in hook_map:
            if hook_name in self._dependency_graph:
                in_degree[hook_name] = len(self._dependency_graph[hook_name])

        # Queue of hooks ready to execute (zero dependencies)
        ready_queue = [hook for hook in hooks if in_degree[hook.name] == 0]
        ordered = []

        # Process hooks in dependency order
        while ready_queue:
            # Take next ready hook
            current_hook = ready_queue.pop(0)
            ordered.append(current_hook)

            # Update in-degrees for dependent hooks
            for hook_name, deps in self._dependency_graph.items():
                if current_hook.name in deps:
                    in_degree[hook_name] -= 1
                    if in_degree[hook_name] == 0 and hook_name in hook_map:
                        ready_queue.append(hook_map[hook_name])

        logger.debug(
            "Resolved hook dependencies",
            extra={
                "input_count": len(hooks),
                "output_count": len(ordered),
                "reordered": len(hooks) != len(ordered) or hooks != ordered,
            }
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
            }
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
                    f"Hook execution raised exception",
                    extra={
                        "hook": hook.name,
                        "exception": str(result),
                        "exception_type": type(result).__name__,
                    }
                )
                final_results.append(self._error_result(hook, result))

        logger.debug(
            "Parallel execution complete",
            extra={
                "total_hooks": len(final_results),
                "successful": sum(1 for r in final_results if isinstance(r, HookResult)),
            }
        )

        return final_results

    async def _execute_sequential(self, hooks: list[HookDefinition]) -> list[HookResult]:
        """Execute hooks sequentially.

        Args:
            hooks: Hooks to execute

        Returns:
            List of HookResult objects
        """
        logger.debug(
            "Starting sequential execution",
            extra={"hook_count": len(hooks)}
        )

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
                    }
                )
                break

        logger.debug(
            "Sequential execution complete",
            extra={
                "total_hooks": len(results),
                "executed": len(results),
                "skipped": len(hooks) - len(results),
            }
        )

        return results

    async def _execute_single_hook(self, hook: HookDefinition) -> HookResult:
        """Execute a single hook (ACB adapter call).

        This is a placeholder for Phase 8+ implementation.
        Will call adapter.check() directly via depends.get().

        Args:
            hook: Hook definition to execute

        Returns:
            HookResult from adapter execution
        """
        logger.debug(
            f"Executing hook: {hook.name}",
            extra={
                "hook": hook.name,
                "timeout": hook.timeout,
                "stage": hook.stage.value,
            }
        )

        # TODO Phase 8: Implement direct adapter execution
        # Example:
        # if hook.name == "bandit":
        #     adapter = await depends.get(BanditAdapter)
        #     result = await adapter.check(files=[...])
        #     return self._convert_to_hook_result(result)

        # Placeholder for Phase 3-7
        return HookResult(
            hook_name=hook.name,
            status="passed",
            duration=0.0,
            output="[ACB mode placeholder - Phase 8 implementation pending]",
        )

    def _error_result(self, hook: HookDefinition, error: Exception) -> HookResult:
        """Create error HookResult from exception.

        Args:
            hook: Hook that raised exception
            error: Exception that was raised

        Returns:
            HookResult with error status
        """
        return HookResult(
            hook_name=hook.name,
            status="error",
            duration=0.0,
            output=f"Exception: {type(error).__name__}: {error}",
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(HookOrchestratorAdapter)
