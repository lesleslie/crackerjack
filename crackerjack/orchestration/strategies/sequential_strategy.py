"""Sequential execution strategy for hook orchestration.

Implements one-at-a-time hook execution with support for early exit on
critical failures and dependency ordering.
"""

from __future__ import annotations

import asyncio
import logging
import typing as t

from crackerjack.config.hooks import HookDefinition, SecurityLevel
from crackerjack.models.task import HookResult

# Module-level logger
logger = logging.getLogger(__name__)


class SequentialExecutionStrategy:
    """Sequential execution strategy for dependent hooks.

    Features:
    - One-at-a-time execution (respects dependencies)
    - Early exit on critical security failures
    - Per-hook timeout handling
    - Comprehensive logging for debugging

    Use when:
    - Hooks have dependencies (gitleaks → bandit)
    - Resource constraints require sequential execution
    - Debugging requires isolated execution
    - Critical failures should stop the pipeline

    Example:
        ```python
        strategy = SequentialExecutionStrategy()
        results = await strategy.execute(hooks=[hook1, hook2, hook3], timeout=300)
        ```
    """

    def __init__(
        self,
        default_timeout: int = 300,
        stop_on_critical_failure: bool = True,
    ) -> None:
        """Initialize sequential execution strategy.

        Args:
            default_timeout: Default timeout per hook in seconds
            stop_on_critical_failure: Stop execution if critical hook fails
        """
        self.default_timeout = default_timeout
        self.stop_on_critical_failure = stop_on_critical_failure

        logger.debug(
            "SequentialExecutionStrategy initialized",
            extra={
                "default_timeout": default_timeout,
                "stop_on_critical_failure": stop_on_critical_failure,
            },
        )

    async def execute(
        self,
        hooks: list[HookDefinition],
        max_parallel: int | None = None,  # Ignored for sequential
        timeout: int | None = None,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]]
        | None = None,
    ) -> list[HookResult]:
        """Execute hooks sequentially.

        Args:
            hooks: List of hook definitions to execute
            max_parallel: Ignored (kept for protocol compatibility)
            timeout: Optional override for default timeout
            executor_callable: Async function that executes a single hook

        Returns:
            List of HookResult objects (may be partial if early exit)
        """
        if not hooks:
            logger.debug("No hooks to execute")
            return []

        timeout_sec = timeout or self.default_timeout
        self._log_execution_start(hooks, timeout_sec)

        results = []
        for idx, hook in enumerate(hooks, 1):
            result = await self._execute_single_hook(
                hook, idx, len(hooks), timeout_sec, executor_callable
            )
            results.append(result)

            if self._should_stop_execution(hook, result):
                self._log_early_exit(hook, results, hooks)
                break

        self._log_execution_complete(results, hooks)
        return results

    def _log_execution_start(
        self, hooks: list[HookDefinition], timeout_sec: int
    ) -> None:
        """Log sequential execution start information."""
        logger.info(
            "Starting sequential execution",
            extra={
                "hook_count": len(hooks),
                "timeout": timeout_sec,
                "stop_on_critical_failure": self.stop_on_critical_failure,
            },
        )

    async def _execute_single_hook(
        self,
        hook: HookDefinition,
        idx: int,
        total_hooks: int,
        timeout_sec: int,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]] | None,
    ) -> HookResult:
        """Execute a single hook with error handling."""
        try:
            hook_timeout = hook.timeout or timeout_sec
            self._log_hook_execution(hook, idx, total_hooks, hook_timeout)

            result = await self._run_hook(hook, hook_timeout, executor_callable)
            self._log_hook_completion(hook, result)
            return result

        except TimeoutError:
            return self._handle_timeout(hook, hook.timeout or timeout_sec)
        except Exception as e:
            return self._handle_exception(hook, e)

    def _log_hook_execution(
        self, hook: HookDefinition, idx: int, total_hooks: int, hook_timeout: int
    ) -> None:
        """Log hook execution start."""
        logger.debug(
            f"Executing hook {idx}/{total_hooks}: {hook.name}",
            extra={
                "hook": hook.name,
                "hook_index": idx,
                "total_hooks": total_hooks,
                "timeout": hook_timeout,
                "security_level": hook.security_level.value,
            },
        )

    async def _run_hook(
        self,
        hook: HookDefinition,
        hook_timeout: int,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]] | None,
    ) -> HookResult:
        """Run hook with executor or return placeholder."""
        if executor_callable:
            return await asyncio.wait_for(executor_callable(hook), timeout=hook_timeout)
        return self._placeholder_result(hook)

    def _log_hook_completion(self, hook: HookDefinition, result: HookResult) -> None:
        """Log hook execution completion."""
        logger.debug(
            f"Hook {hook.name} completed",
            extra={
                "hook": hook.name,
                "status": result.status,
                "duration": result.duration,
            },
        )

    def _handle_timeout(self, hook: HookDefinition, hook_timeout: int) -> HookResult:
        """Handle hook timeout error."""
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

    def _handle_exception(
        self, hook: HookDefinition, exception: Exception
    ) -> HookResult:
        """Handle hook execution exception."""
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
            issues_found=[f"Exception: {type(exception).__name__}: {exception}"],
        )

    def _log_early_exit(
        self,
        hook: HookDefinition,
        results: list[HookResult],
        hooks: list[HookDefinition],
    ) -> None:
        """Log early exit due to critical failure."""
        remaining_hooks = len(hooks) - len(results)
        logger.warning(
            f"Critical hook {hook.name} failed, stopping execution",
            extra={
                "hook": hook.name,
                "security_level": hook.security_level.value,
                "executed_hooks": len(results),
                "remaining_hooks": remaining_hooks,
            },
        )

    def _log_execution_complete(
        self, results: list[HookResult], hooks: list[HookDefinition]
    ) -> None:
        """Log sequential execution completion."""
        logger.info(
            "Sequential execution complete",
            extra={
                "total_hooks": len(results),
                "executed": len(results),
                "skipped": len(hooks) - len(results),
                "passed": sum(1 for r in results if r.status == "passed"),
                "failed": sum(1 for r in results if r.status == "failed"),
                "errors": sum(1 for r in results if r.status in ("timeout", "error")),
            },
        )

    def get_execution_order(
        self,
        hooks: list[HookDefinition],
    ) -> list[list[HookDefinition]]:
        """Return batches of hooks for execution.

        Sequential strategy returns one hook per batch.

        Args:
            hooks: List of hook definitions

        Returns:
            List of batches, each containing one hook
        """
        return [[hook] for hook in hooks]

    def _should_stop_execution(
        self,
        hook: HookDefinition,
        result: HookResult,
    ) -> bool:
        """Determine if execution should stop based on hook result.

        Early exit conditions:
        - stop_on_critical_failure is True
        - Hook security level is CRITICAL
        - Result status is failed, timeout, or error

        Args:
            hook: Hook definition that was executed
            result: Result from hook execution

        Returns:
            True if execution should stop, False otherwise
        """
        if not self.stop_on_critical_failure:
            return False

        is_critical = hook.security_level == SecurityLevel.CRITICAL
        is_failure = result.status in ("failed", "timeout", "error")

        return is_critical and is_failure

    def _placeholder_result(self, hook: HookDefinition) -> HookResult:
        """Create placeholder result when no executor provided."""
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="passed",
            duration=0.0,
        )
