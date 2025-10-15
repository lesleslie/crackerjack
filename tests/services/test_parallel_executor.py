import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.logger import Logger

from crackerjack.config.hooks import HookDefinition, SecurityLevel
from crackerjack.models.protocols import PerformanceCacheProtocol
from crackerjack.services.parallel_executor import (
    AsyncCommandExecutor,
    ExecutionResult,
    ExecutionStrategy,
    ParallelHookExecutor,
    ParallelExecutionResult,
)


@pytest.fixture
def mock_logger() -> MagicMock:
    return MagicMock(spec=Logger)


@pytest.fixture
def mock_cache() -> MagicMock:
    return MagicMock(spec=PerformanceCacheProtocol)


@pytest.fixture
def parallel_hook_executor(mock_logger: MagicMock, mock_cache: MagicMock) -> ParallelHookExecutor:
    return ParallelHookExecutor(logger=mock_logger, cache=mock_cache)


@pytest.fixture
def async_command_executor(mock_logger: MagicMock, mock_cache: MagicMock) -> AsyncCommandExecutor:
    executor = AsyncCommandExecutor(logger=mock_logger, cache=mock_cache)
    executor._thread_pool = MagicMock()  # Mock the thread pool
    return executor


@pytest.mark.asyncio
async def test_parallel_hook_executor_sequential_strategy(parallel_hook_executor: ParallelHookExecutor) -> None:
    parallel_hook_executor.strategy = ExecutionStrategy.SEQUENTIAL
    hooks = [
        HookDefinition(name="hook1", command=["echo", "1"], security_level=SecurityLevel.LOW),
        HookDefinition(name="hook2", command=["echo", "2"], security_level=SecurityLevel.LOW),
    ]
    mock_hook_runner = AsyncMock(side_effect=[
        ExecutionResult(operation_id="hook1", success=True, duration_seconds=1.0),
        ExecutionResult(operation_id="hook2", success=True, duration_seconds=1.0),
    ])

    result = await parallel_hook_executor.execute_hooks_parallel(hooks, mock_hook_runner)

    assert isinstance(result, ParallelExecutionResult)
    assert result.overall_success is True
    assert result.total_operations == 2
    assert mock_hook_runner.call_count == 2


@pytest.mark.asyncio
async def test_parallel_hook_executor_parallel_strategy(parallel_hook_executor: ParallelHookExecutor) -> None:
    parallel_hook_executor.strategy = ExecutionStrategy.PARALLEL_SAFE
    hooks = [
        HookDefinition(name="hook1", command=["echo", "1"], security_level=SecurityLevel.LOW, is_formatting=True),
        HookDefinition(name="hook2", command=["echo", "2"], security_level=SecurityLevel.LOW, is_formatting=True),
    ]
    mock_hook_runner = AsyncMock(side_effect=[
        ExecutionResult(operation_id="hook1", success=True, duration_seconds=1.0),
        ExecutionResult(operation_id="hook2", success=True, duration_seconds=1.0),
    ])

    result = await parallel_hook_executor.execute_hooks_parallel(hooks, mock_hook_runner)

    assert isinstance(result, ParallelExecutionResult)
    assert result.overall_success is True
    assert result.total_operations == 2
    assert mock_hook_runner.call_count == 2


@pytest.mark.asyncio
async def test_async_command_executor_execute_command(async_command_executor: AsyncCommandExecutor, mock_cache: MagicMock) -> None:
    mock_cache.get.return_value = None
    mock_cache.set.return_value = None

    # Mock the internal _run_command_async to return a successful result
    async_command_executor._run_command_async = AsyncMock(return_value=ExecutionResult(
        operation_id="test_command", success=True, duration_seconds=0.5, output="stdout", error="", exit_code=0
    ))

    command = ["echo", "hello"]
    result = await async_command_executor.execute_command(command)

    assert isinstance(result, ExecutionResult)
    assert result.success is True
    assert result.output == "stdout"
    async_command_executor._run_command_async.assert_called_once_with(command, None, 60)
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_async_command_executor_execute_command_cached(async_command_executor: AsyncCommandExecutor, mock_cache: MagicMock) -> None:
    cached_exec_result = ExecutionResult(operation_id="cached_command", success=True, duration_seconds=0.1, output="cached", error="", exit_code=0)
    mock_cache.get.return_value = cached_exec_result

    async_command_executor._run_command_async = AsyncMock() # Ensure it's not called

    command = ["echo", "cached"]
    result = await async_command_executor.execute_command(command)

    assert isinstance(result, ExecutionResult)
    assert result.success is True
    assert result.output == "cached"
    mock_cache.get.assert_called_once()
    async_command_executor._run_command_async.assert_not_called()


@pytest.mark.asyncio
async def test_async_command_executor_shutdown(async_command_executor: AsyncCommandExecutor) -> None:
    async_command_executor.shutdown()
    async_command_executor._thread_pool.shutdown.assert_called_once_with(wait=True)
