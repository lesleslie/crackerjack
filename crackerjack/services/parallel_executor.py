import asyncio
import logging
import subprocess
import time
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from crackerjack.config.hooks import HookDefinition, SecurityLevel
from crackerjack.models.protocols import (
    AsyncCommandExecutorProtocol,
    ParallelHookExecutorProtocol,
    PerformanceCacheProtocol,
    ServiceProtocol,
)
from crackerjack.models.results import ExecutionResult, ParallelExecutionResult

logger = logging.getLogger(__name__)


class ExecutionStrategy(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL_SAFE = "parallel_safe"
    PARALLEL_AGGRESSIVE = "parallel_aggressive"


@dataclass
class ExecutionGroup:
    name: str
    operations: list[t.Any]
    max_workers: int = 3
    timeout_seconds: int = 300
    dependencies: set[str] = field(default_factory=set)
    security_level: SecurityLevel = SecurityLevel.MEDIUM


class ParallelHookExecutor(ParallelHookExecutorProtocol, ServiceProtocol):
    """Executes hooks in parallel or sequentially based on defined strategies.

    This service manages the concurrent execution of various hooks (e.g., linting, formatting)
    to optimize performance and provide faster feedback loops. It supports different execution
    strategies and handles dependencies between hooks.
    """

    def __init__(
        self,
        logger: object | None = None,
        cache: PerformanceCacheProtocol | None = None,
        max_workers: int = 3,
        timeout_seconds: int = 300,
        strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL_SAFE,
    ):
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        self.strategy = strategy
        self._logger = logger or logging.getLogger("crackerjack.parallel_executor")
        self._cache = cache

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    async def async_cleanup(self) -> None:
        """Async cleanup for any remaining tasks."""
        with suppress(RuntimeError):
            loop = asyncio.get_running_loop()
            pending_tasks = (
                task
                for task in asyncio.all_tasks(loop)
                if not task.done()
                and ("hook" in str(task).lower() or "parallel" in str(task).lower())
            )

            for task in pending_tasks:
                if not task.done():
                    try:
                        task.cancel()
                        await asyncio.wait_for(task, timeout=0.1)
                    except (TimeoutError, asyncio.CancelledError):
                        pass
                    except RuntimeError as e:
                        if "Event loop is closed" in str(e):
                            return
                        else:
                            raise

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    def analyze_hook_dependencies(
        self,
        hooks: list[HookDefinition],
    ) -> dict[str, list[HookDefinition]]:
        groups: dict[str, list[HookDefinition]] = {
            "formatting": [],
            "validation": [],
            "security": [],
            "comprehensive": [],
        }

        for hook in hooks:
            if hook.is_formatting or hook.security_level == SecurityLevel.LOW:
                groups["formatting"].append(hook)
            elif hook.security_level == SecurityLevel.CRITICAL:
                groups["security"].append(hook)
            elif hook.name in {"check-yaml", "check-json", "check-toml"}:
                groups["validation"].append(hook)
            else:
                groups["comprehensive"].append(hook)

        return {k: v for k, v in groups.items() if v}

    def can_execute_in_parallel(
        self,
        hook1: HookDefinition,
        hook2: HookDefinition,
    ) -> bool:
        if hook1.security_level != hook2.security_level:
            return False

        if hook1.is_formatting and not hook2.is_formatting:
            return False

        safe_parallel_combinations = [
            (lambda h: h.is_formatting, lambda h: h.is_formatting),
            (
                lambda h: h.name in {"check-yaml", "check-json", "check-toml"},
                lambda h: h.name in {"check-yaml", "check-json", "check-toml"},
            ),
            (
                lambda h: not h.is_formatting
                and h.security_level == SecurityLevel.MEDIUM,
                lambda h: not h.is_formatting
                and h.security_level == SecurityLevel.MEDIUM,
            ),
        ]

        for check1, check2 in safe_parallel_combinations:
            if check1(hook1) and check2(hook2):
                return True

        return False

    async def execute_hooks_parallel(
        self,
        hooks: list[HookDefinition],
        hook_runner: t.Callable[[HookDefinition], t.Awaitable[ExecutionResult]],
    ) -> ParallelExecutionResult:
        start_time = time.time()

        if self.strategy == ExecutionStrategy.SEQUENTIAL:
            return await self._execute_sequential(hooks, hook_runner, start_time)

        groups = self.analyze_hook_dependencies(hooks)
        all_results: list[ExecutionResult] = []

        self._logger.info(
            f"Executing {len(hooks)} hooks in {len(groups)} parallel groups"
        )

        for group_name, group_hooks in groups.items():
            if len(group_hooks) == 1 or not self._can_parallelize_group(group_hooks):
                for hook in group_hooks:
                    result = await hook_runner(hook)
                    all_results.append(result)
            else:
                group_results = await self._execute_group_parallel(
                    group_hooks,
                    hook_runner,
                    group_name,
                )
                all_results.extend(group_results)

        total_duration = time.time() - start_time
        successful = sum(1 for r in all_results if r.success)
        failed = len(all_results) - successful

        return ParallelExecutionResult(
            group_name="all_hooks",
            total_operations=len(hooks),
            successful_operations=successful,
            failed_operations=failed,
            total_duration_seconds=total_duration,
            results=all_results,
        )

    async def _execute_sequential(
        self,
        hooks: list[HookDefinition],
        hook_runner: t.Callable[[HookDefinition], t.Awaitable[ExecutionResult]],
        start_time: float,
    ) -> ParallelExecutionResult:
        results: list[ExecutionResult] = []

        for hook in hooks:
            result = await hook_runner(hook)
            results.append(result)

        total_duration = time.time() - start_time
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        return ParallelExecutionResult(
            group_name="sequential",
            total_operations=len(hooks),
            successful_operations=successful,
            failed_operations=failed,
            total_duration_seconds=total_duration,
            results=results,
        )

    def _can_parallelize_group(self, hooks: list[HookDefinition]) -> bool:
        if len(hooks) < 2:
            return False

        for i, hook1 in enumerate(hooks):
            for hook2 in hooks[i + 1 :]:
                if not self.can_execute_in_parallel(hook1, hook2):
                    return False

        return True

    async def _execute_group_parallel(
        self,
        hooks: list[HookDefinition],
        hook_runner: t.Callable[[HookDefinition], t.Awaitable[ExecutionResult]],
        group_name: str,
    ) -> list[ExecutionResult]:
        self._logger.debug(f"Executing {len(hooks)} {group_name} hooks in parallel")

        max_workers = min(self.max_workers, len(hooks))

        semaphore = asyncio.Semaphore(max_workers)

        async def run_with_semaphore(hook: HookDefinition) -> ExecutionResult:
            async with semaphore:
                return await hook_runner(hook)

        tasks = [run_with_semaphore(hook) for hook in hooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results: list[ExecutionResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ExecutionResult(
                    operation_id=hooks[i].name,
                    success=False,
                    duration_seconds=0.0,
                    error=str(result),
                )
                processed_results.append(error_result)
                self._logger.error(
                    f"Hook {hooks[i].name} failed with exception: {result}"
                )
            else:
                processed_results.append(t.cast(ExecutionResult, result))

        successful = sum(1 for r in processed_results if r.success)
        self._logger.info(
            f"Parallel {group_name} execution: {successful}/{len(hooks)} succeeded"
        )

        return processed_results


class AsyncCommandExecutor(AsyncCommandExecutorProtocol, ServiceProtocol):
    """Executes shell commands asynchronously, with caching capabilities.

    This service provides a robust way to run external commands without blocking
    the main event loop, supporting parallel execution and caching of results
    to improve performance and responsiveness.
    """

    def __init__(
        self,
        logger: object | None = None,
        cache: PerformanceCacheProtocol | None = None,
        max_workers: int = 4,
        cache_results: bool = True,
    ):
        self.max_workers = max_workers
        self.cache_results = cache_results
        self._logger = logger or logging.getLogger("crackerjack.async_executor")
        self._cache = cache
        from concurrent.futures import ThreadPoolExecutor

        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)

    def shutdown(self) -> None:
        if hasattr(self, "_thread_pool"):
            self._thread_pool.shutdown(wait=True)

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    async def async_cleanup(self) -> None:
        """Async cleanup for any remaining command executor tasks."""
        with suppress(RuntimeError):
            loop = asyncio.get_running_loop()
            pending_tasks = (
                task
                for task in asyncio.all_tasks(loop)
                if not task.done()
                and ("command" in str(task).lower() or "async" in str(task).lower())
            )

            for task in pending_tasks:
                if not task.done():
                    try:
                        task.cancel()
                        await asyncio.wait_for(task, timeout=0.1)
                    except (TimeoutError, asyncio.CancelledError):
                        pass
                    except RuntimeError as e:
                        if "Event loop is closed" in str(e):
                            return
                        else:
                            raise

    async def execute_command(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int = 60,
        cache_ttl: int = 120,
    ) -> ExecutionResult:
        if self.cache_results:
            cached_result = await self._get_cached_result(command, cwd)
            if cached_result:
                self._logger.debug(
                    f"Using cached result for command: {' '.join(command)}"
                )
                return cached_result

        start_time = time.time()
        result = await self._run_command_async(command, cwd, timeout)
        result.duration_seconds = time.time() - start_time

        if self.cache_results and result.success:
            await self._cache_result(command, result, cache_ttl, cwd)

        return result

    async def execute_commands_batch(
        self,
        commands: list[tuple[list[str], Path | None]],
        timeout: int = 60,
    ) -> list[ExecutionResult]:
        self._logger.info(f"Executing {len(commands)} commands in batch")

        tasks = [self.execute_command(cmd, cwd, timeout) for cmd, cwd in commands]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results: list[ExecutionResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ExecutionResult(
                    operation_id=f"command_{i}",
                    success=False,
                    duration_seconds=0.0,
                    error=str(result),
                )
                processed_results.append(error_result)
            else:
                processed_results.append(t.cast(ExecutionResult, result))

        successful = sum(1 for r in processed_results if r.success)
        self._logger.info(
            f"Batch execution: {successful}/{len(commands)} commands succeeded"
        )

        return processed_results

    async def _run_command_async(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int = 60,
    ) -> ExecutionResult:
        loop = asyncio.get_event_loop()

        def run_sync_command() -> ExecutionResult:
            try:
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )

                return ExecutionResult(
                    operation_id=" ".join(command),
                    success=result.returncode == 0,
                    duration_seconds=0.0,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                )

            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    operation_id=" ".join(command),
                    success=False,
                    duration_seconds=timeout,
                    error=f"Command timeout after {timeout}s",
                    exit_code=-1,
                )
            except Exception as e:
                return ExecutionResult(
                    operation_id=" ".join(command),
                    success=False,
                    duration_seconds=0.0,
                    error=str(e),
                    exit_code=-1,
                )

        return await loop.run_in_executor(self._thread_pool, run_sync_command)

    async def _get_cached_result(
        self,
        command: list[str],
        cwd: Path | None = None,
    ) -> ExecutionResult | None:
        if self._cache is None:
            return None
        cache_result = self._cache.get(self._get_cache_key(command, cwd))
        return t.cast(ExecutionResult | None, cache_result)

    async def _cache_result(
        self,
        command: list[str],
        result: ExecutionResult,
        ttl_seconds: int,
        cwd: Path | None = None,
    ) -> None:
        if self._cache is None:
            return
        self._cache.set(self._get_cache_key(command, cwd), result, ttl_seconds)

    def _get_cache_key(self, command: list[str], cwd: Path | None) -> str:
        key_parts = [" ".join(command)]
        if cwd:
            key_parts.append(str(cwd))
        return ":".join(key_parts)


_parallel_executor: ParallelHookExecutor | None = None
_async_executor: AsyncCommandExecutor | None = None


def get_parallel_executor(
    max_workers: int = 3,
    strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL_SAFE,
) -> ParallelHookExecutor:
    global _parallel_executor
    if _parallel_executor is None:
        _parallel_executor = ParallelHookExecutor(
            # logger = logger  # Migrated from ACB,
            cache=None,
            max_workers=max_workers,
            strategy=strategy,
        )
    return _parallel_executor


def get_async_executor(max_workers: int = 4) -> AsyncCommandExecutor:
    global _async_executor
    if _async_executor is None:
        _async_executor = AsyncCommandExecutor(
            # logger = logger  # Migrated from ACB,
            cache=None,
            max_workers=max_workers,
        )
    return _async_executor
