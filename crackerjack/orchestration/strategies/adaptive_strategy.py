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
from contextlib import suppress

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
        progress_callback: t.Callable[[int, int], None] | None = None,
        progress_start_callback: t.Callable[[int, int], None] | None = None,
    ) -> list[HookResult]:
        """Execute hooks in dependency-aware waves.

        Args:
            hooks: List of hook definitions to execute
            max_parallel: Optional override for max concurrent executions per wave
            timeout: Optional override for default timeout
            executor_callable: Async function that executes a single hook
            progress_callback: Optional callback(completed, total) for progress updates

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
        total_hooks = len(hooks)
        completed_hooks = 0

        # Initial progress report
        if progress_callback:
            progress_callback(0, total_hooks)

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
            # Define per-hook completion notifier to update progress incrementally
            def on_hook_start() -> None:
                nonlocal completed_hooks
                # Use started count as the metric to tick the progress bar
                started = completed_hooks + 1
                if progress_start_callback:
                    progress_start_callback(started, total_hooks)

            def on_hook_complete() -> None:
                nonlocal completed_hooks
                completed_hooks += 1
                if progress_callback:
                    progress_callback(completed_hooks, total_hooks)

            wave_results = await self._execute_wave(
                wave_hooks,
                max_parallel=max_par,
                timeout=timeout_sec,
                executor_callable=executor_callable,
                on_hook_complete=on_hook_complete,
                on_hook_start=on_hook_start,
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
        hook_map = {hook.name: hook for hook in hooks}
        in_degree = self._build_in_degree_map(hooks, hook_map)

        logger.debug(
            "Computed in-degree map",
            extra={
                "in_degree": {name: degree for name, degree in in_degree.items()},
            },
        )

        waves = self._compute_waves_from_dependencies(hooks, hook_map, in_degree)

        logger.debug(
            f"Computed {len(waves)} execution waves",
            extra={
                "wave_count": len(waves),
                "total_hooks": sum(len(wave) for wave in waves),
            },
        )

        return waves

    def _build_in_degree_map(
        self,
        hooks: list[HookDefinition],
        hook_map: dict[str, HookDefinition],
    ) -> dict[str, int]:
        """Build in-degree map counting dependencies per hook."""
        in_degree = {hook.name: 0 for hook in hooks}
        for hook_name in hook_map:
            if hook_name in self.dependency_graph:
                deps = self.dependency_graph[hook_name]
                in_degree[hook_name] = sum(1 for dep in deps if dep in hook_map)
        return in_degree

    def _compute_waves_from_dependencies(
        self,
        hooks: list[HookDefinition],
        hook_map: dict[str, HookDefinition],
        in_degree: dict[str, int],
    ) -> list[list[HookDefinition]]:
        """Compute waves by iteratively processing hooks with satisfied dependencies."""
        waves: list[list[HookDefinition]] = []
        remaining_hooks = set(hook_map.keys())
        iteration = 0
        max_iterations = len(hooks) + 1

        while remaining_hooks:
            iteration += 1
            if self._check_max_iterations_exceeded(
                iteration, max_iterations, remaining_hooks, hook_map, waves
            ):
                break

            ready_hooks = self._find_ready_hooks(remaining_hooks, in_degree, hook_map)
            self._validate_wave_progress(ready_hooks, remaining_hooks, in_degree)

            waves.append(ready_hooks)
            self._log_wave_ready(waves, ready_hooks, remaining_hooks)

            self._update_dependencies_after_wave(
                ready_hooks, remaining_hooks, in_degree
            )

        return waves

    def _check_max_iterations_exceeded(
        self,
        iteration: int,
        max_iterations: int,
        remaining_hooks: set[str],
        hook_map: dict[str, HookDefinition],
        waves: list[list[HookDefinition]],
    ) -> bool:
        """Check if max iterations exceeded and handle fallback."""
        if iteration > max_iterations:
            logger.error(
                "Max iterations exceeded, circular dependency suspected",
                extra={
                    "remaining_hooks": list(remaining_hooks),
                    "iteration": iteration,
                },
            )
            waves.append([hook_map[name] for name in remaining_hooks])
            return True
        return False

    def _find_ready_hooks(
        self,
        remaining_hooks: set[str],
        in_degree: dict[str, int],
        hook_map: dict[str, HookDefinition],
    ) -> list[HookDefinition]:
        """Find all hooks with zero dependencies in current wave."""
        return [hook_map[name] for name in remaining_hooks if in_degree[name] == 0]

    def _validate_wave_progress(
        self,
        ready_hooks: list[HookDefinition],
        remaining_hooks: set[str],
        in_degree: dict[str, int],
    ) -> None:
        """Validate that wave has ready hooks or raise circular dependency error."""
        if not ready_hooks:
            logger.error(
                "Circular dependency detected",
                extra={
                    "remaining_hooks": list(remaining_hooks),
                    "in_degrees": {name: in_degree[name] for name in remaining_hooks},
                },
            )
            raise ValueError(
                f"Circular dependency detected in hooks: {list(remaining_hooks)}"
            )

    def _log_wave_ready(
        self,
        waves: list[list[HookDefinition]],
        ready_hooks: list[HookDefinition],
        remaining_hooks: set[str],
    ) -> None:
        """Log wave readiness information."""
        logger.debug(
            f"Wave {len(waves)} ready",
            extra={
                "wave_idx": len(waves),
                "hooks": [h.name for h in ready_hooks],
                "remaining_count": len(remaining_hooks) - len(ready_hooks),
            },
        )

    def _update_dependencies_after_wave(
        self,
        ready_hooks: list[HookDefinition],
        remaining_hooks: set[str],
        in_degree: dict[str, int],
    ) -> None:
        """Update in-degrees after wave completion."""
        for hook in ready_hooks:
            remaining_hooks.remove(hook.name)

        for hook in ready_hooks:
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

    async def _execute_wave(
        self,
        hooks: list[HookDefinition],
        max_parallel: int,
        timeout: int,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]] | None,
        on_hook_complete: t.Callable[[], None] | None = None,
        on_hook_start: t.Callable[[], None] | None = None,
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
                self._notify_hook_start(on_hook_start)
                result = await self._execute_single_hook_in_wave(
                    hook, timeout, executor_callable
                )
                self._notify_hook_complete(on_hook_complete)
                return result

        tasks = [execute_with_limit(hook) for hook in hooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._process_wave_results(hooks, results)

    def _notify_hook_start(self, on_hook_start: t.Callable[[], None] | None) -> None:
        """Notify that hook execution has started."""
        if on_hook_start:
            with suppress(Exception):
                on_hook_start()

    def _notify_hook_complete(
        self, on_hook_complete: t.Callable[[], None] | None
    ) -> None:
        """Notify that hook execution has completed."""
        if on_hook_complete:
            with suppress(Exception):
                on_hook_complete()

    async def _execute_single_hook_in_wave(
        self,
        hook: HookDefinition,
        timeout: int,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]] | None,
    ) -> HookResult:
        """Execute a single hook with timeout and error handling."""
        try:
            hook_timeout = hook.timeout or timeout
            logger.debug(
                f"Executing hook {hook.name}",
                extra={
                    "hook": hook.name,
                    "timeout": hook_timeout,
                },
            )

            result = await self._run_hook_with_executor(
                hook, hook_timeout, executor_callable
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
            return self._create_timeout_result(hook, hook.timeout or timeout)
        except Exception as e:
            return self._create_error_result(hook, e)

    async def _run_hook_with_executor(
        self,
        hook: HookDefinition,
        hook_timeout: int,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]] | None,
    ) -> HookResult:
        """Run hook with executor or return placeholder."""
        if executor_callable:
            return await asyncio.wait_for(executor_callable(hook), timeout=hook_timeout)
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="passed",
            duration=0.0,
        )

    def _create_timeout_result(
        self, hook: HookDefinition, hook_timeout: int
    ) -> HookResult:
        """Create HookResult for timeout condition."""
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

    def _create_error_result(
        self, hook: HookDefinition, exception: Exception
    ) -> HookResult:
        """Create HookResult for exception condition."""
        logger.error(
            f"Hook {hook.name} raised exception",
            extra={
                "hook": hook.name,
                "exception": str(exception),
                "exception_type": type(exception).__name__,
            },
        )
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="error",
            duration=0.0,
        )

    def _process_wave_results(
        self,
        hooks: list[HookDefinition],
        results: list[HookResult | BaseException],
    ) -> list[HookResult]:
        """Process results from asyncio.gather, converting exceptions to HookResults."""
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
