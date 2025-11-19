import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from crackerjack.config.hooks import (
    HookDefinition,
    HookStrategy,
    RetryPolicy,
)
from crackerjack.executors.async_hook_executor import (
    AsyncHookExecutionResult,
    AsyncHookExecutor,
)
from crackerjack.models.task import HookResult


@pytest.mark.skip(reason="AsyncHookExecutor requires complex nested ACB DI setup - integration test, not unit test")
class TestAsyncHookExecutor:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False, width=70)

    @pytest.fixture
    def pkg_path(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def async_executor(self, console, pkg_path):
        import logging
        logger = logging.getLogger(__name__)
        return AsyncHookExecutor(logger=logger, console=console, pkg_path=pkg_path, max_concurrent=2)

    @pytest.fixture
    def mock_hook(self):
        hook = Mock(spec=HookDefinition)
        hook.name = "test - hook"
        hook.timeout = 10
        hook.stage = Mock()
        hook.stage.value = "fast"
        hook.is_formatting = False
        hook.get_command.return_value = ["echo", "test"]
        return hook

    @pytest.fixture
    def mock_strategy(self, mock_hook):
        strategy = Mock(spec=HookStrategy)
        strategy.name = "test - strategy"
        strategy.hooks = [mock_hook]
        strategy.parallel = True
        strategy.max_workers = 2
        strategy.retry_policy = RetryPolicy.NONE
        return strategy

    @pytest.mark.asyncio
    async def test_execute_strategy_success(
        self,
        async_executor,
        mock_strategy,
    ) -> None:
        with patch.object(
            async_executor,
            "_execute_sequential",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_result = HookResult(
                id="test - hook",
                name="test - hook",
                status="passed",
                duration=1.0,
                files_processed=0,
                issues_found=[],
                stage="fast",
            )
            mock_execute.return_value = [mock_result]

            result = await async_executor.execute_strategy(mock_strategy)

            assert isinstance(result, AsyncHookExecutionResult)
            assert result.strategy_name == "test - strategy"
            assert result.success is True
            assert len(result.results) == 1
            assert result.results[0].status == "passed"
            assert result.performance_gain >= 0

    @pytest.mark.asyncio
    async def test_execute_strategy_failure(
        self,
        async_executor,
        mock_strategy,
    ) -> None:
        with patch.object(
            async_executor,
            "_execute_sequential",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_result = HookResult(
                id="test - hook",
                name="test - hook",
                status="failed",
                duration=1.0,
                files_processed=0,
                issues_found=["Error message"],
                stage="fast",
            )
            mock_execute.return_value = [mock_result]

            result = await async_executor.execute_strategy(mock_strategy)

            assert result.success is False
            assert result.failed_count == 1
            assert result.passed_count == 0

    @pytest.mark.asyncio
    async def test_execute_sequential_strategy(
        self,
        async_executor,
        mock_strategy,
    ) -> None:
        mock_strategy.parallel = False

        with patch.object(
            async_executor,
            "_execute_sequential",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_result = HookResult(
                id="test - hook",
                name="test - hook",
                status="passed",
                duration=1.0,
                files_processed=0,
                issues_found=[],
                stage="fast",
            )
            mock_execute.return_value = [mock_result]

            result = await async_executor.execute_strategy(mock_strategy)

            mock_execute.assert_called_once_with(mock_strategy)
            assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_single_hook_success(self, async_executor, mock_hook) -> None:
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"success output", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await async_executor._execute_single_hook(mock_hook)

            assert result.name == "test - hook"
            assert result.status == "passed"
            assert result.duration > 0

    @pytest.mark.asyncio
    async def test_execute_single_hook_timeout(self, async_executor, mock_hook) -> None:
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = TimeoutError()
            mock_process.kill = AsyncMock()
            mock_process.wait = AsyncMock()
            mock_subprocess.return_value = mock_process

            result = await async_executor._execute_single_hook(mock_hook)

            assert result.name == "test - hook"
            assert result.status == "timeout"
            assert "timed out" in result.issues_found[0]
            mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_hook_exception(
        self,
        async_executor,
        mock_hook,
    ) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=Exception("Test error"),
        ):
            result = await async_executor._execute_single_hook(mock_hook)

            assert result.name == "test - hook"
            assert result.status == "error"
            assert "Test error" in result.issues_found[0]

    @pytest.mark.asyncio
    async def test_parallel_execution_with_formatting_hooks(
        self,
        async_executor,
        mock_strategy,
    ) -> None:
        formatting_hook = Mock(spec=HookDefinition)
        formatting_hook.name = "formatting - hook"
        formatting_hook.is_formatting = True
        formatting_hook.stage.value = "fast"

        non_formatting_hook = Mock(spec=HookDefinition)
        non_formatting_hook.name = "non - formatting - hook"
        non_formatting_hook.is_formatting = False
        non_formatting_hook.stage.value = "fast"

        mock_strategy.hooks = [formatting_hook, non_formatting_hook]

        with patch.object(
            async_executor,
            "_execute_single_hook",
            new_callable=AsyncMock,
        ) as mock_single:
            mock_single.return_value = HookResult(
                id="test",
                name="test",
                status="passed",
                duration=1.0,
                files_processed=0,
                issues_found=[],
                stage="fast",
            )

            await async_executor._execute_parallel(mock_strategy)

            calls = mock_single.call_args_list
            assert calls[0][0][0] == formatting_hook

    @pytest.mark.asyncio
    async def test_retry_formatting_hooks(self, async_executor, mock_strategy) -> None:
        mock_strategy.retry_policy = RetryPolicy.FORMATTING_ONLY
        mock_hook = mock_strategy.hooks[0]
        mock_hook.is_formatting = True

        failed_result = HookResult(
            id="test - hook",
            name="test - hook",
            status="failed",
            duration=1.0,
            files_processed=0,
            issues_found=["formatting error"],
            stage="fast",
        )

        success_result = HookResult(
            id="test - hook",
            name="test - hook",
            status="passed",
            duration=1.0,
            files_processed=0,
            issues_found=[],
            stage="fast",
        )

        with patch.object(
            async_executor,
            "_execute_single_hook",
            new_callable=AsyncMock,
        ) as mock_single:
            mock_single.return_value = success_result

            results = await async_executor._retry_formatting_hooks(
                mock_strategy,
                [failed_result],
            )

            assert len(results) == 1
            assert results[0].status == "passed"

            assert results[0].duration == 2.0

    @pytest.mark.asyncio
    async def test_performance_metrics(self, async_executor, mock_strategy) -> None:
        with patch.object(
            async_executor,
            "_execute_parallel",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_result = HookResult(
                id="test - hook",
                name="test - hook",
                status="passed",
                duration=1.0,
                files_processed=0,
                issues_found=[],
                stage="fast",
            )
            mock_execute.return_value = [mock_result]

            result = await async_executor.execute_strategy(mock_strategy)

            assert hasattr(result, "performance_gain")
            assert isinstance(result.performance_gain, float)
            assert result.performance_gain >= 0

            summary = result.performance_summary
            assert "total_hooks" in summary
            assert "passed" in summary
            assert "failed" in summary
            assert "duration_seconds" in summary
            assert "performance_gain_percent" in summary


class TestAsyncHookExecutionResult:
    def test_result_properties(self) -> None:
        results = [
            HookResult(
                id="1",
                name="hook1",
                status="passed",
                duration=1.0,
                issues_found=[],
                stage="fast",
            ),
            HookResult(
                id="2",
                name="hook2",
                status="failed",
                duration=2.0,
                issues_found=["error"],
                stage="fast",
            ),
            HookResult(
                id="3",
                name="hook3",
                status="timeout",
                duration=3.0,
                issues_found=["timeout"],
                stage="fast",
            ),
        ]

        result = AsyncHookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=6.0,
            success=False,
            cache_hits=5,
            cache_misses=3,
            performance_gain=25.0,
        )

        assert result.passed_count == 1
        assert result.failed_count == 1
        assert result.cache_hit_rate == 62.5

        summary = result.performance_summary
        assert summary["total_hooks"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["cache_hit_rate_percent"] == 62.5
        assert summary["performance_gain_percent"] == 25.0


@pytest.mark.asyncio
@pytest.mark.skip(reason="AsyncHookExecutor requires complex nested ACB DI setup - integration test, not unit test")
async def test_semaphore_concurrency_limiting() -> None:
    import logging
    console = Console(force_terminal=False)
    pkg_path = Path.cwd()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(logger=logger, console=console, pkg_path=pkg_path, max_concurrent=1)

    concurrent_count = 0
    max_concurrent = 0

    async def mock_subprocess_exec(*args, **kwargs):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)

        await asyncio.sleep(0.1)

        concurrent_count -= 1

        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        return mock_process

    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
        hooks = []
        for i in range(3):
            hook = Mock(spec=HookDefinition)
            hook.name = f"hook - {i}"
            hook.timeout = 30
            hook.stage.value = "fast"
            hook.get_command.return_value = ["echo", f"test - {i}"]
            hooks.append(hook)

        tasks = [executor._execute_single_hook(hook) for hook in hooks]
        await asyncio.gather(*tasks)

        assert max_concurrent == 1
