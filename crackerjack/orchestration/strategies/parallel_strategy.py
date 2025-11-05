"""Parallel execution strategy for hook orchestration.

Implements concurrent hook execution with resource limits, timeout handling,
and exception isolation. Uses asyncio.Semaphore for throttling.
"""

from __future__ import annotations

import asyncio
import logging
import typing as t

from crackerjack.config.hooks import HookDefinition
from crackerjack.models.task import HookResult

# Module-level logger
logger = logging.getLogger(__name__)


class ParallelExecutionStrategy:
    """Parallel execution strategy with resource limits.

    Features:
    - Concurrent execution using asyncio.gather()
    - Semaphore-based resource limiting (max concurrent hooks)
    - Per-hook timeout handling with asyncio.wait_for()
    - Exception isolation (one failure doesn't stop others)
    - Structured logging for execution flow

    Use when:
    - Hooks are independent (no dependencies)
    - Want to maximize throughput
    - System has sufficient resources

    Example:
        ```python
        strategy = ParallelExecutionStrategy(max_parallel=3)
        results = await strategy.execute(hooks=[hook1, hook2, hook3], timeout=300)
        ```
    """

    def __init__(
        self,
        max_parallel: int = 3,
        default_timeout: int = 300,
    ) -> None:
        """Initialize parallel execution strategy.

        Args:
            max_parallel: Maximum concurrent hook executions
            default_timeout: Default timeout per hook in seconds
        """
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout
        self.semaphore: asyncio.Semaphore | None = None

        logger.debug(
            "ParallelExecutionStrategy initialized",
            extra={
                "max_parallel": max_parallel,
                "default_timeout": default_timeout,
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
        """Execute hooks in parallel with resource limits.

        Args:
            hooks: List of hook definitions to execute
            max_parallel: Optional override for max concurrent executions
            timeout: Optional override for default timeout
            executor_callable: Async function that executes a single hook

        Returns:
            List of HookResult objects (same order as input hooks)
        """
        if not hooks:
            logger.debug("No hooks to execute")
            return []

        max_par = max_parallel or self.max_parallel
        timeout_sec = timeout or self.default_timeout

        # Create fresh semaphore for this execution
        self.semaphore = asyncio.Semaphore(max_par)

        logger.info(
            "Starting parallel execution",
            extra={
                "hook_count": len(hooks),
                "max_parallel": max_par,
                "timeout": timeout_sec,
            },
        )

        async def execute_with_limit(hook: HookDefinition) -> HookResult:
            """Execute hook with semaphore and timeout."""
            async with self.semaphore:  # type: ignore
                try:
                    hook_timeout = hook.timeout or timeout_sec
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
                        result = self._placeholder_result(hook)

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
                        issues_found=[f"Hook timed out after {hook_timeout}s"],
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
                        issues_found=[f"Exception: {type(e).__name__}: {e}"],
                    )

        # Create tasks for all hooks
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
                final_results.append(self._error_result(hook, result))

        logger.info(
            "Parallel execution complete",
            extra={
                "total_hooks": len(final_results),
                "passed": sum(1 for r in final_results if r.status == "passed"),
                "failed": sum(1 for r in final_results if r.status == "failed"),
                "errors": sum(
                    1 for r in final_results if r.status in ("timeout", "error")
                ),
            },
        )

        return final_results

    def get_execution_order(
        self,
        hooks: list[HookDefinition],
    ) -> list[list[HookDefinition]]:
        """Return batches of hooks for execution.

        Parallel strategy can execute all hooks in a single batch.

        Args:
            hooks: List of hook definitions

        Returns:
            List containing one batch with all hooks
        """
        return [hooks] if hooks else []

    def _placeholder_result(self, hook: HookDefinition) -> HookResult:
        """Create placeholder result when no executor provided."""
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="passed",
            duration=0.0,
        )

    def _error_result(self, hook: HookDefinition, error: BaseException) -> HookResult:
        """Create error HookResult from exception."""
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="error",
            duration=0.0,
            issues_found=[f"Exception: {type(error).__name__}: {error}"],
        )
