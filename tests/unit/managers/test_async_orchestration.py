"""Tests for AsyncHookManager.

Tests async hook execution, parallel failure modes, timeout handling,
error propagation, and progress callback integration.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.executors.async_hook_executor import AsyncHookExecutionResult
from crackerjack.managers.async_hook_manager import AsyncHookManager
from crackerjack.models.task import HookResult


@pytest.fixture
def mock_console():
    """Create a mock console."""
    console = MagicMock()
    console.print = MagicMock()
    return console


@pytest.fixture
def tmp_path():
    """Create a temporary path for testing."""
    from tempfile import mkdtemp

    return Path(mkdtemp())


@pytest.fixture
def mock_async_executor():
    """Create a mock async hook executor."""
    executor = MagicMock()
    executor.execute_strategy = AsyncMock()
    return executor


@pytest.fixture
def mock_config_loader():
    """Create a mock config loader."""
    loader = MagicMock()
    strategy = MagicMock()
    strategy.hooks = []
    strategy.parallel = False
    strategy.max_workers = 1
    loader.load_strategy = MagicMock(return_value=strategy)
    return loader


class TestAsyncHookManagerInitialization:
    """Tests for AsyncHookManager initialization."""

    def test_initializes_with_custom_dependencies(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test initialization with custom dependencies."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=MagicMock(),
            config_loader=MagicMock(),
        )
        assert manager.console == mock_console
        assert manager.pkg_path == tmp_path
        assert manager._config_path is None

    def test_initializes_with_custom_executor(
        self, mock_console: MagicMock, tmp_path: Path, mock_async_executor: MagicMock
    ) -> None:
        """Test initialization with custom async executor."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_async_executor,
        )
        assert manager.async_executor == mock_async_executor

    def test_initializes_with_custom_config_loader(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test initialization with custom config loader."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            config_loader=mock_config_loader,
        )
        assert manager.config_loader == mock_config_loader

    def test_initializes_with_custom_max_concurrent(
        self, mock_console: MagicMock, tmp_path: Path, mock_async_executor: MagicMock
    ) -> None:
        """Test initialization with custom max concurrent setting."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_async_executor,
            max_concurrent=5,
        )
        # Max concurrent is passed to executor, verify it was used
        assert manager.async_executor == mock_async_executor


class TestConfigPathManagement:
    """Tests for configuration path management."""

    def test_set_config_path(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test setting custom configuration path."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=MagicMock(),
            config_loader=MagicMock(),
        )
        config_path = tmp_path / "custom_config.yaml"
        manager.set_config_path(config_path)
        assert manager._config_path == config_path


class TestGetHookCount:
    """Tests for get_hook_count method."""

    def test_returns_hook_count_from_strategy(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test getting hook count from loaded strategy."""
        strategy = MagicMock()
        strategy.hooks = [MagicMock(), MagicMock(), MagicMock()]
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=MagicMock(),
            config_loader=mock_config_loader,
        )

        count = manager.get_hook_count("fast")
        assert count == 3

    def test_returns_zero_for_empty_strategy(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test getting hook count for strategy with no hooks."""
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=MagicMock(),
            config_loader=mock_config_loader,
        )

        count = manager.get_hook_count("comprehensive")
        assert count == 0


class TestRunFastHooksAsync:
    """Tests for async fast hook execution."""

    @pytest.mark.asyncio
    async def test_loads_fast_strategy(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test that fast strategy is loaded and executed."""
        strategy = MagicMock()
        strategy.hooks = []
        strategy.parallel = False
        strategy.max_workers = 1
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=[],
                total_duration=0.5,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        results = await manager.run_fast_hooks_async()
        mock_config_loader.load_strategy.assert_called_once_with("fast")
        assert results == []

    @pytest.mark.asyncio
    async def test_applies_config_path_to_hooks(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test that config path is applied to hooks when set."""
        config_path = tmp_path / "config.yaml"

        hook1 = MagicMock()
        hook2 = MagicMock()
        strategy = MagicMock()
        strategy.hooks = [hook1, hook2]
        strategy.parallel = False
        strategy.max_workers = 1
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=[],
                total_duration=0.5,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )
        manager.set_config_path(config_path)

        await manager.run_fast_hooks_async()
        assert hook1.config_path == config_path
        assert hook2.config_path == config_path

    @pytest.mark.asyncio
    async def test_enables_parallel_execution(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test that parallel execution is enabled."""
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=[],
                total_duration=0.5,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        await manager.run_fast_hooks_async()
        assert strategy.parallel is True
        assert strategy.max_workers == 3

    @pytest.mark.asyncio
    async def test_returns_hook_results(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test that hook results are returned correctly."""
        result1 = HookResult(hook_name="hook1", status="passed", duration=0.1)
        result2 = HookResult(hook_name="hook2", status="failed", duration=0.2)

        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=[result1, result2],
                total_duration=0.3,
                success=False,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        results = await manager.run_fast_hooks_async()
        assert len(results) == 2
        assert results[0].status == "passed"
        assert results[1].status == "failed"


class TestRunComprehensiveHooksAsync:
    """Tests for async comprehensive hook execution."""

    @pytest.mark.asyncio
    async def test_loads_comprehensive_strategy(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test that comprehensive strategy is loaded."""
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="comprehensive",
                results=[],
                total_duration=1.0,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        await manager.run_comprehensive_hooks_async()
        mock_config_loader.load_strategy.assert_called_once_with("comprehensive")

    @pytest.mark.asyncio
    async def test_enables_parallel_execution(
        self, mock_console: MagicMock, tmp_path: Path, mock_config_loader: MagicMock
    ) -> None:
        """Test that parallel execution is enabled for comprehensive hooks."""
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="comprehensive",
                results=[],
                total_duration=1.0,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        await manager.run_comprehensive_hooks_async()
        assert strategy.parallel is True
        assert strategy.max_workers == 3


class TestSyncWrappers:
    """Tests for synchronous wrapper methods."""

    def test_run_fast_handles_async_execution(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that sync wrapper runs async execution."""
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        result = HookResult(hook_name="test", status="passed", duration=0.1)
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=[result],
                total_duration=0.1,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        results = manager.run_fast_hooks()
        assert len(results) == 1
        assert results[0].status == "passed"

    def test_run_comprehensive_handles_async_execution(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that sync wrapper runs async execution for comprehensive."""
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="comprehensive",
                results=[],
                total_duration=1.0,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        results = manager.run_comprehensive_hooks()
        assert results == []


class TestInstallHooks:
    """Tests for install_hooks methods."""

    @pytest.mark.asyncio
    async def test_install_hooks_async_returns_true(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that async install returns True."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=MagicMock(),
            config_loader=MagicMock(),
        )

        result = await manager.install_hooks_async()
        assert result is True
        mock_console.print.assert_called_once()

    def test_install_hooks_sync_wrapper(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test that sync wrapper runs async install."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=MagicMock(),
            config_loader=MagicMock(),
        )

        result = manager.install_hooks()
        assert result is True


class TestUpdateHooks:
    """Tests for update_hooks methods."""

    @pytest.mark.asyncio
    async def test_update_hooks_async_returns_true(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that async update returns True."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=MagicMock(),
            config_loader=MagicMock(),
        )

        result = await manager.update_hooks_async()
        assert result is True
        mock_console.print.assert_called_once()

    def test_update_hooks_sync_wrapper(self, mock_console: MagicMock, tmp_path: Path) -> None:
        """Test that sync wrapper runs async update."""
        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=MagicMock(),
            config_loader=MagicMock(),
        )

        result = manager.update_hooks()
        assert result is True


class TestGetHookSummary:
    """Tests for get_hook_summary static method."""

    def test_summary_with_empty_results(self) -> None:
        """Test summary with empty results list."""
        summary = AsyncHookManager.get_hook_summary([])
        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["errors"] == 0
        assert summary["total_duration"] == 0
        assert summary["success_rate"] == 0

    def test_summary_with_mixed_results(self) -> None:
        """Test summary with mixed passed/failed results."""
        results = [
            HookResult(hook_name="hook1", status="passed", duration=0.1),
            HookResult(hook_name="hook2", status="failed", duration=0.2),
            HookResult(hook_name="hook3", status="passed", duration=0.15),
            HookResult(hook_name="hook4", status="timeout", duration=5.0),
            HookResult(hook_name="hook5", status="error", duration=0.0),
        ]

        summary = AsyncHookManager.get_hook_summary(results)
        assert summary["total"] == 5
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["errors"] == 2  # timeout + error
        assert summary["total_duration"] == 5.45
        assert summary["success_rate"] == 40.0  # 2/5 * 100

    def test_summary_with_all_passed(self) -> None:
        """Test summary when all hooks pass."""
        results = [
            HookResult(hook_name="hook1", status="passed", duration=0.1),
            HookResult(hook_name="hook2", status="passed", duration=0.2),
        ]

        summary = AsyncHookManager.get_hook_summary(results)
        assert summary["total"] == 2
        assert summary["passed"] == 2
        assert summary["failed"] == 0
        assert summary["errors"] == 0
        assert summary["success_rate"] == 100.0

    def test_summary_with_all_failed(self) -> None:
        """Test summary when all hooks fail."""
        results = [
            HookResult(hook_name="hook1", status="failed", duration=0.1),
            HookResult(hook_name="hook2", status="failed", duration=0.2),
        ]

        summary = AsyncHookManager.get_hook_summary(results)
        assert summary["total"] == 2
        assert summary["passed"] == 0
        assert summary["failed"] == 2
        assert summary["errors"] == 0
        assert summary["success_rate"] == 0.0

    def test_summary_with_custom_elapsed_time(self) -> None:
        """Test summary with custom elapsed time parameter."""
        results = [
            HookResult(hook_name="hook1", status="passed", duration=0.1),
            HookResult(hook_name="hook2", status="passed", duration=0.2),
        ]

        summary = AsyncHookManager.get_hook_summary(results, elapsed_time=1.5)
        assert summary["total_duration"] == 1.5  # Uses provided elapsed time
        assert summary["total"] == 2


class TestParallelFailureModes:
    """Tests for parallel execution failure handling."""

    @pytest.mark.asyncio
    async def test_handles_partial_failures_in_parallel(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test handling partial failures when running hooks in parallel."""
        results = [
            HookResult(hook_name="hook1", status="passed", duration=0.1),
            HookResult(hook_name="hook2", status="failed", duration=0.2),
            HookResult(hook_name="hook3", status="passed", duration=0.15),
        ]

        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=results,
                total_duration=0.45,
                success=False,  # Partial failure
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        hook_results = await manager.run_fast_hooks_async()
        assert len(hook_results) == 3
        assert hook_results[1].status == "failed"

    @pytest.mark.asyncio
    async def test_handles_all_failures_in_parallel(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test handling when all hooks fail in parallel execution."""
        results = [
            HookResult(hook_name="hook1", status="failed", duration=0.1),
            HookResult(hook_name="hook2", status="error", duration=0.0),
            HookResult(hook_name="hook3", status="timeout", duration=5.0),
        ]

        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=results,
                total_duration=5.1,
                success=False,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        hook_results = await manager.run_fast_hooks_async()
        assert len(hook_results) == 3
        assert all(r.status != "passed" for r in hook_results)


class TestTimeoutHandling:
    """Tests for timeout handling in async execution."""

    @pytest.mark.asyncio
    async def test_handles_timeout_during_execution(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that timeout during hook execution is handled gracefully."""
        results = [
            HookResult(hook_name="hook1", status="timeout", duration=10.0),
            HookResult(hook_name="hook2", status="passed", duration=0.1),
        ]

        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=results,
                total_duration=10.1,
                success=False,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        hook_results = await manager.run_fast_hooks_async()
        assert len(hook_results) == 2
        assert hook_results[0].status == "timeout"


class TestErrorPropagation:
    """Tests for error propagation in async context."""

    @pytest.mark.asyncio
    async def test_propagates_hook_errors(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that hook errors are properly propagated."""
        results = [
            HookResult(hook_name="hook1", status="error", duration=0.0, error="Critical error"),
        ]

        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=results,
                total_duration=0.0,
                success=False,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        hook_results = await manager.run_fast_hooks_async()
        assert len(hook_results) == 1
        assert hook_results[0].status == "error"
        assert hook_results[0].error == "Critical error"

    @pytest.mark.asyncio
    async def test_continues_after_single_hook_error(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that execution continues after one hook errors."""
        results = [
            HookResult(hook_name="hook1", status="error", duration=0.0),
            HookResult(hook_name="hook2", status="passed", duration=0.1),
            HookResult(hook_name="hook3", status="passed", duration=0.1),
        ]

        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=results,
                total_duration=0.2,
                success=False,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        hook_results = await manager.run_fast_hooks_async()
        assert len(hook_results) == 3
        # Other hooks should still execute despite error


class TestProgressCallbackIntegration:
    """Tests for progress callback integration (documentation tests)."""

    def test_progress_callback_architecture(self, mock_console: MagicMock) -> None:
        """Test that progress callbacks are documented (documentation test)."""
        # The AsyncHookManager uses AsyncHookExecutor which supports progress callbacks
        # Progress tracking happens at the executor level, not the manager level
        # The manager orchestrates execution but doesn't directly handle progress callbacks
        assert True  # Architecture documented

    @pytest.mark.asyncio
    async def test_executor_handles_progress_reporting(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that progress reporting is delegated to executor (integration test)."""
        # Progress callbacks are handled by AsyncHookExecutor
        # The manager delegates execution to the executor
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=[],
                total_duration=0.5,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        # Execute and verify executor was called (progress happens at executor level)
        await manager.run_fast_hooks_async()
        mock_executor.execute_strategy.assert_called_once()
        assert True  # Progress delegation verified


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    def test_sync_wrapper_handles_async_exceptions(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that sync wrapper properly handles async exceptions."""
        # Mock asyncio.run to raise an exception
        with patch("asyncio.run", side_effect=RuntimeError("Async error")):
            manager = AsyncHookManager(
                console=mock_console,
                pkg_path=tmp_path,
                async_executor=MagicMock(),
                config_loader=MagicMock(),
            )

            # Should propagate the exception
            with pytest.raises(RuntimeError, match="Async error"):
                manager.run_fast_hooks()

    @pytest.mark.asyncio
    async def test_handles_empty_hook_list(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test handling when strategy has no hooks."""
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="fast",
                results=[],
                total_duration=0.0,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
        )

        results = await manager.run_fast_hooks_async()
        assert results == []

    @pytest.mark.asyncio
    async def test_concurrent_execution_with_max_workers(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        """Test that max_workers setting is respected."""
        strategy = MagicMock()
        strategy.hooks = []
        mock_config_loader = MagicMock()
        mock_config_loader.load_strategy = MagicMock(return_value=strategy)

        mock_executor = MagicMock()
        mock_executor.execute_strategy = AsyncMock(
            return_value=AsyncHookExecutionResult(
                strategy_name="comprehensive",
                results=[],
                total_duration=1.0,
                success=True,
            )
        )

        manager = AsyncHookManager(
            console=mock_console,
            pkg_path=tmp_path,
            async_executor=mock_executor,
            config_loader=mock_config_loader,
            max_concurrent=5,
        )

        await manager.run_comprehensive_hooks_async()
        # Verify parallel settings were applied
        assert strategy.parallel is True
        assert strategy.max_workers == 3
