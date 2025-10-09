"""Adaptive execution strategy with dependency-aware batching.

Implements intelligent parallel execution that:
- Analyzes dependency graph to identify independent groups
- Executes hooks in waves (parallel within wave, sequential between waves)
- Maximizes parallelism while respecting dependencies
- Handles critical failures with early exit

This is the optimal strategy for mixed workloads with some dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import typing as t

from crackerjack.config.hooks import HookDefinition, SecurityLevel
from crackerjack.models.task import HookResult

# Module-level logger
logger = logging.getLogger(__name__)


class AdaptiveExecutionStrategy:
    """Adaptive execution with dependency-aware batching.

    Features:
    - Topological sort for dependency-aware wave computation
    - Parallel execution within each wave (independent hooks)
    - Sequential execution between waves (respects dependencies)
    - Early exit on critical security failures
    - Resource limiting via asyncio.Semaphore

    Algorithm:
    1. Compute execution waves using topological sort
    2. Wave 1: All hooks with zero dependencies (parallel)
    3. Wave 2: Hooks whose dependencies completed (parallel within wave)
    4. Wave N: Repeat until all hooks executed
    5. Stop early if critical hook fails

    Example:
        ```python
        # Dependency graph:
        # gitleaks → bandit
        # zuban → refurb
        # ruff-format (independent)

        strategy = AdaptiveExecutionStrategy(
            dependency_graph={"bandit": ["gitleaks"], "refurb": ["zuban"]}
        )

        # Execution waves:
        # Wave 1 (parallel): gitleaks, zuban, ruff-format
        # Wave 2 (parallel): bandit, refurb
        ```
    """

    def __init__(
        self,
        dependency_graph: dict[str, list[str]],
        max_parallel: int = 4,
        default_timeout: int = 300,
        stop_on_critical_failure: bool = True,
    ) -> None:
        """Initialize adaptive execution strategy.

        Args:
            dependency_graph: Hook dependencies (dependent → list of prerequisites)
            max_parallel: Maximum concurrent executions per wave
            default_timeout: Default timeout per hook in seconds
            stop_on_critical_failure: Stop execution if critical hook fails
        """
        self.dependency_graph = dependency_graph
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout
        self.stop_on_critical_failure = stop_on_critical_failure

        logger.debug(
            "AdaptiveExecutionStrategy initialized",
            extra={
                "dependency_count": len(dependency_graph),
                "max_parallel": max_parallel,
                "default_timeout": default_timeout,
                "stop_on_critical_failure": stop_on_critical_failure,
            },
        )

    async def execute(
        self,
        hooks: list[HookDefinition],
        max_parallel: int | None = None,
        timeout: int | None = None,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]]
        | None = None,
    ) -> list[HookResult]:
        """Execute hooks in dependency-aware waves.

        Args:
            hooks: List of hook definitions to execute
            max_parallel: Optional override for max concurrent executions per wave
            timeout: Optional override for default timeout
            executor_callable: Async function that executes a single hook

        Returns:
            List of HookResult objects (combined from all waves)
        """
        if not hooks:
            logger.debug("No hooks to execute")
            return []

        max_par = max_parallel or self.max_parallel
        timeout_sec = timeout or self.default_timeout

        logger.info(
            "Starting adaptive execution",
            extra={
                "hook_count": len(hooks),
                "max_parallel": max_par,
                "timeout": timeout_sec,
            },
        )

        # Compute execution waves using topological sort
        waves = self._compute_execution_waves(hooks)

        logger.info(
            f"Computed {len(waves)} execution waves",
            extra={
                "wave_count": len(waves),
                "waves": [
                    {
                        "wave_idx": idx,
                        "hook_count": len(wave),
                        "hooks": [h.name for h in wave],
                    }
                    for idx, wave in enumerate(waves, 1)
                ],
            },
        )

        # Execute each wave in parallel, waves sequentially
        all_results = []
        for wave_idx, wave_hooks in enumerate(waves, 1):
            logger.info(
                f"Executing wave {wave_idx}/{len(waves)}",
                extra={
                    "wave_idx": wave_idx,
                    "total_waves": len(waves),
                    "hooks_in_wave": len(wave_hooks),
                    "hook_names": [h.name for h in wave_hooks],
                },
            )

            # Execute this wave in parallel
            wave_results = await self._execute_wave(
                wave_hooks,
                max_parallel=max_par,
                timeout=timeout_sec,
                executor_callable=executor_callable,
            )

            all_results.extend(wave_results)

            logger.info(
                f"Wave {wave_idx} complete",
                extra={
                    "wave_idx": wave_idx,
                    "passed": sum(1 for r in wave_results if r.status == "passed"),
                    "failed": sum(1 for r in wave_results if r.status == "failed"),
                    "errors": sum(
                        1 for r in wave_results if r.status in ("timeout", "error")
                    ),
                },
            )

            # Check for critical failures that should stop execution
            if self.stop_on_critical_failure and self._has_critical_failure(
                wave_hooks, wave_results
            ):
                remaining_hooks = sum(len(w) for w in waves[wave_idx:])
                logger.warning(
                    "Critical failure detected, stopping execution",
                    extra={
                        "completed_waves": wave_idx,
                        "remaining_waves": len(waves) - wave_idx,
                        "remaining_hooks": remaining_hooks,
                    },
                )
                break

        logger.info(
            "Adaptive execution complete",
            extra={
                "total_hooks": len(all_results),
                "executed_waves": min(wave_idx, len(waves)),
                "total_waves": len(waves),
                "passed": sum(1 for r in all_results if r.status == "passed"),
                "failed": sum(1 for r in all_results if r.status == "failed"),
                "errors": sum(
                    1 for r in all_results if r.status in ("timeout", "error")
                ),
            },
        )

        return all_results

    def _compute_execution_waves(
        self,
        hooks: list[HookDefinition],
    ) -> list[list[HookDefinition]]:
        """Compute execution waves using topological sort.

        Algorithm:
        1. Build in-degree map (count of unsatisfied dependencies per hook)
        2. Wave 1: All hooks with zero dependencies
        3. After wave completes, decrement in-degree for dependent hooks
        4. Next wave: Hooks that now have zero dependencies
        5. Repeat until all hooks assigned to waves

        Returns:
            List of waves, each wave contains hooks that can execute in parallel

        Raises:
            ValueError: If circular dependency detected
        """
        # Build hook name → hook mapping
        hook_map = {hook.name: hook for hook in hooks}

        # Build in-degree map (count of dependencies per hook)
        in_degree = {hook.name: 0 for hook in hooks}
        for hook_name in hook_map:
            if hook_name in self.dependency_graph:
                # Count how many dependencies this hook has
                deps = self.dependency_graph[hook_name]
                # Only count dependencies that are actually in our hook list
                in_degree[hook_name] = sum(1 for dep in deps if dep in hook_map)

        logger.debug(
            "Computed in-degree map",
            extra={
                "in_degree": {name: degree for name, degree in in_degree.items()},
            },
        )

        # Compute waves
        waves = []
        remaining_hooks = set(hook_map.keys())
        iteration = 0
        max_iterations = len(hooks) + 1  # Prevent infinite loops

        while remaining_hooks:
            iteration += 1
            if iteration > max_iterations:
                # Safety check: prevent infinite loop
                logger.error(
                    "Max iterations exceeded, circular dependency suspected",
                    extra={
                        "remaining_hooks": list(remaining_hooks),
                        "iteration": iteration,
                    },
                )
                # Add all remaining hooks to final wave as fallback
                waves.append([hook_map[name] for name in remaining_hooks])
                break

            # Find all hooks with zero dependencies in this wave
            ready_hooks = [
                hook_map[name] for name in remaining_hooks if in_degree[name] == 0
            ]

            if not ready_hooks:
                # No hooks ready but hooks remain → circular dependency
                logger.error(
                    "Circular dependency detected",
                    extra={
                        "remaining_hooks": list(remaining_hooks),
                        "in_degrees": {
                            name: in_degree[name] for name in remaining_hooks
                        },
                    },
                )
                raise ValueError(
                    f"Circular dependency detected in hooks: {list(remaining_hooks)}"
                )

            # Add this wave
            waves.append(ready_hooks)

            logger.debug(
                f"Wave {len(waves)} ready",
                extra={
                    "wave_idx": len(waves),
                    "hooks": [h.name for h in ready_hooks],
                    "remaining_count": len(remaining_hooks) - len(ready_hooks),
                },
            )

            # Remove these hooks from remaining
            for hook in ready_hooks:
                remaining_hooks.remove(hook.name)

            # Update in-degrees for dependent hooks
            for hook in ready_hooks:
                # Find hooks that depend on this hook
                for dependent_name, deps in self.dependency_graph.items():
                    if hook.name in deps and dependent_name in remaining_hooks:
                        in_degree[dependent_name] -= 1
                        logger.debug(
                            f"Decremented in-degree for {dependent_name}",
                            extra={
                                "dependent": dependent_name,
                                "completed_dependency": hook.name,
                                "new_in_degree": in_degree[dependent_name],
                            },
                        )

        logger.debug(
            f"Computed {len(waves)} execution waves",
            extra={
                "wave_count": len(waves),
                "total_hooks": sum(len(wave) for wave in waves),
            },
        )

        return waves

    async def _execute_wave(
        self,
        hooks: list[HookDefinition],
        max_parallel: int,
        timeout: int,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]] | None,
    ) -> list[HookResult]:
        """Execute a single wave of hooks in parallel.

        Args:
            hooks: Hooks to execute in this wave
            max_parallel: Maximum concurrent executions
            timeout: Timeout per hook in seconds
            executor_callable: Async function that executes a single hook

        Returns:
            List of HookResult objects for this wave
        """
        if not hooks:
            return []

        semaphore = asyncio.Semaphore(max_parallel)

        async def execute_with_limit(hook: HookDefinition) -> HookResult:
            """Execute hook with semaphore and timeout."""
            async with semaphore:
                try:
                    hook_timeout = hook.timeout or timeout
                    logger.debug(
                        f"Executing hook {hook.name}",
                        extra={
                            "hook": hook.name,
                            "timeout": hook_timeout,
                        },
                    )

                    if executor_callable:
                        result = await asyncio.wait_for(
                            executor_callable(hook), timeout=hook_timeout
                        )
                    else:
                        # Placeholder if no executor provided
                        result = HookResult(
                            id=hook.name,
                            name=hook.name,
                            status="passed",
                            duration=0.0,
                        )

                    logger.debug(
                        f"Hook {hook.name} completed",
                        extra={
                            "hook": hook.name,
                            "status": result.status,
                            "duration": result.duration,
                        },
                    )
                    return result

                except TimeoutError:
                    logger.warning(
                        f"Hook {hook.name} timed out",
                        extra={
                            "hook": hook.name,
                            "timeout": hook_timeout,
                        },
                    )
                    return HookResult(
                        id=hook.name,
                        name=hook.name,
                        status="timeout",
                        duration=hook_timeout,
                    )
                except Exception as e:
                    logger.error(
                        f"Hook {hook.name} raised exception",
                        extra={
                            "hook": hook.name,
                            "exception": str(e),
                            "exception_type": type(e).__name__,
                        },
                    )
                    return HookResult(
                        id=hook.name,
                        name=hook.name,
                        status="error",
                        duration=0.0,
                    )

        # Create tasks for all hooks in this wave
        tasks = [execute_with_limit(hook) for hook in hooks]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any unexpected exceptions (shouldn't happen due to try/except above)
        final_results = []
        for hook, result in zip(hooks, results):
            if isinstance(result, HookResult):
                final_results.append(result)
            else:
                logger.error(
                    "Unexpected exception from gather",
                    extra={
                        "hook": hook.name,
                        "exception": str(result),
                        "exception_type": type(result).__name__,
                    },
                )
                final_results.append(
                    HookResult(
                        id=hook.name,
                        name=hook.name,
                        status="error",
                        duration=0.0,
                    )
                )

        return final_results

    def _has_critical_failure(
        self,
        hooks: list[HookDefinition],
        results: list[HookResult],
    ) -> bool:
        """Check if any critical failure occurred in wave results.

        Args:
            hooks: Hooks that were executed
            results: Results from execution

        Returns:
            True if a critical-level hook failed, False otherwise
        """
        for hook, result in zip(hooks, results):
            if hook.security_level == SecurityLevel.CRITICAL:
                if result.status in ("failed", "timeout", "error"):
                    logger.warning(
                        f"Critical hook {hook.name} failed",
                        extra={
                            "hook": hook.name,
                            "status": result.status,
                            "security_level": "critical",
                        },
                    )
                    return True

        return False

    def get_execution_order(
        self,
        hooks: list[HookDefinition],
    ) -> list[list[HookDefinition]]:
        """Return batches of hooks for execution (waves).

        Args:
            hooks: List of hook definitions

        Returns:
            List of batches (waves), each containing hooks that can execute in parallel
        """
        try:
            return self._compute_execution_waves(hooks)
        except ValueError as e:
            # Circular dependency detected, fall back to sequential
            logger.error(
                f"Failed to compute waves: {e}, falling back to sequential execution",
                extra={"error": str(e)},
            )
            return [[hook] for hook in hooks]  # Sequential fallback
