import asyncio
import time
import typing as t
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from crackerjack.config.hooks import HookDefinition, SecurityLevel
from crackerjack.services.logging import get_logger
from crackerjack.services.performance_cache import get_performance_cache


class ExecutionStrategy(Enum):
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


@dataclass
class ExecutionResult:
    operation_id: str
    success: bool
    duration_seconds: float
    output: str = ""
    error: str = ""
    exit_code: int = 0
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])


@dataclass
class ParallelExecutionResult:
    group_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration_seconds: float
    results: list[ExecutionResult]

    @property
    def success_rate(self) -> float:
        return (
            self.successful_operations / self.total_operations
            if self.total_operations > 0
            else 0.0
        )

    @property
    def overall_success(self) -> bool:
        return self.failed_operations == 0


class ParallelHookExecutor:
    def __init__(
        self,
        max_workers: int = 3,
        timeout_seconds: int = 300,
        strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL_SAFE,
    ):
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        self.strategy = strategy
        self._logger = get_logger("crackerjack.parallel_executor")
        self._cache = get_performance_cache()

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


class AsyncCommandExecutor:
    def __init__(
        self,
        max_workers: int = 4,
        cache_results: bool = True,
    ):
        self.max_workers = max_workers
        self.cache_results = cache_results
        self._logger = get_logger("crackerjack.async_executor")
        self._cache = get_performance_cache()
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)

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
            import subprocess

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
        from crackerjack.services.performance_cache import get_command_cache

        cache_result = get_command_cache().get_command_result(command, cwd)
        return t.cast(ExecutionResult | None, cache_result)

    async def _cache_result(
        self,
        command: list[str],
        result: ExecutionResult,
        ttl_seconds: int,
        cwd: Path | None = None,
    ) -> None:
        from crackerjack.services.performance_cache import get_command_cache

        command_cache = get_command_cache()
        command_cache.set_command_result(command, result, cwd, ttl_seconds)

    def __del__(self) -> None:
        if hasattr(self, "_thread_pool"):
            self._thread_pool.shutdown(wait=False)


_parallel_executor: ParallelHookExecutor | None = None
_async_executor: AsyncCommandExecutor | None = None


def get_parallel_executor(
    max_workers: int = 3,
    strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL_SAFE,
) -> ParallelHookExecutor:
    global _parallel_executor
    if _parallel_executor is None:
        _parallel_executor = ParallelHookExecutor(
            max_workers=max_workers,
            strategy=strategy,
        )
    return _parallel_executor


def get_async_executor(max_workers: int = 4) -> AsyncCommandExecutor:
    global _async_executor
    if _async_executor is None:
        _async_executor = AsyncCommandExecutor(max_workers=max_workers)
    return _async_executor
