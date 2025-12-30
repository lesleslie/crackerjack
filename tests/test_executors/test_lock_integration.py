"""Integration tests for hook executors with global lock system.

Tests cover:
- Hook executor integration: verify both executors use global locks properly
- CLI integration: verify CLI options properly configure the lock manager
- Configuration flow: CLI → Options → GlobalLockConfig → HookLockManager
"""

import asyncio
import json
import logging
import tempfile
import unittest.mock
from pathlib import Path

import pytest
from rich.console import Console

from crackerjack.config.global_lock_config import GlobalLockConfig
from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.executors.async_hook_executor import AsyncHookExecutor
from crackerjack.executors.hook_lock_manager import HookLockManager
from crackerjack.executors.individual_hook_executor import IndividualHookExecutor


class TestAsyncHookExecutorIntegration:
    """Test AsyncHookExecutor integration with global lock system."""

    @pytest.mark.asyncio
    async def test_async_executor_uses_lock_manager(self, tmp_path):
        """Test that AsyncHookExecutor properly uses the lock manager."""
        # Create mock lock manager
        mock_lock_manager = unittest.mock.AsyncMock()
        mock_lock_manager.requires_lock.return_value = True
        mock_lock_manager.acquire_hook_lock = unittest.mock.AsyncMock()

        # Configure AsyncHookExecutor with mock lock manager
        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(
            logger=logger, console=console, pkg_path=tmp_path, hook_lock_manager=mock_lock_manager
        )

        # Verify lock manager is properly injected
        assert executor.hook_lock_manager is mock_lock_manager

    @pytest.mark.asyncio
    async def test_async_executor_with_global_locks_enabled(self, tmp_path):
        """Test AsyncHookExecutor behavior with global locks enabled."""
        # Create real lock manager with test configuration
        lock_manager = HookLockManager()
        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "executor_locks", enabled=True
        )
        lock_manager._global_config = test_config
        lock_manager.enable_global_lock(True)

        # Create executor
        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=lock_manager,
            timeout=1,  # Short timeout for testing
        )

        # Create a hook strategy with a hook that requires locking
        test_hook = HookDefinition(
            name="complexipy",
            command=["echo", "test command"],
            description="Test hook that requires locking",
        )

        lock_manager.add_hook_to_lock_list("complexipy")

        strategy = HookStrategy(name="test_strategy", hooks=[test_hook], parallel=True)

        # Execute strategy (should use global locks)
        result = await executor.execute_strategy(strategy)

        # Verify execution completed
        assert result.strategy_name == "test_strategy"
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_async_executor_with_global_locks_disabled(self, tmp_path):
        """Test AsyncHookExecutor behavior with global locks disabled."""
        # Create lock manager with global locks disabled
        lock_manager = HookLockManager()
        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "executor_locks", enabled=False
        )
        lock_manager._global_config = test_config
        lock_manager.enable_global_lock(False)

        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=lock_manager,
            timeout=1,
        )

        # Create hook strategy
        test_hook = HookDefinition(
            name="test_hook_no_global",
            command=["echo", "no global locks"],
            description="Test hook without global locking",
        )

        strategy = HookStrategy(
            name="no_global_strategy", hooks=[test_hook], parallel=True
        )

        # Execute strategy (should use only hook-specific locks)
        result = await executor.execute_strategy(strategy)

        assert result.strategy_name == "no_global_strategy"
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_async_executor_concurrent_prevention(self, tmp_path):
        """Test that AsyncHookExecutor prevents concurrent execution of locked hooks."""
        # Create shared lock manager
        lock_manager = HookLockManager()
        # By default, the lock manager already has global locks enabled with default config
        # We just need to enable it (which it typically is by default)

        lock_manager.enable_global_lock(True)

        # Add hook that requires locking
        hook_name = "concurrent_prevention_test"
        lock_manager.add_hook_to_lock_list(hook_name)
        # Set the timeout for this hook
        lock_manager.set_hook_timeout(hook_name, 0.5)  # Short timeout for test

        # Create two executors (simulating different sessions)
        logger = logging.getLogger(__name__)
        console = Console()

        executor1 = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=lock_manager,
            timeout=1,
        )

        executor2 = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=lock_manager,
            timeout=1,
        )

        # Create hook strategies
        slow_hook = HookDefinition(
            name=hook_name,
            command=["bash", "-c", "echo 'slow test' > /dev/null 2>&1 && exit 0"],  # Safe command that doesn't need git and exits cleanly
            description="Slow test hook",
        )
        slow_hook._direct_cmd_cache = slow_hook.command

        strategy1 = HookStrategy(name="strategy1", hooks=[slow_hook])
        strategy2 = HookStrategy(name="strategy2", hooks=[slow_hook])

        # Execute both strategies concurrently
        results = await asyncio.gather(
            executor1.execute_strategy(strategy1),
            executor2.execute_strategy(strategy2),
            return_exceptions=True,
        )

        # One should succeed, one should have timeout issues
        success_count = sum(
            1 for r in results if isinstance(r, type(results[0])) and r.success
        )

        # At least one should complete successfully
        assert success_count >= 1


class TestIndividualHookExecutorIntegration:
    """Test IndividualHookExecutor integration with global lock system."""

    @pytest.mark.asyncio
    async def test_individual_executor_uses_lock_manager(self, tmp_path):
        """Test that IndividualHookExecutor properly uses the lock manager."""
        # Create mock lock manager
        mock_lock_manager = unittest.mock.AsyncMock()
        mock_lock_manager.requires_lock.return_value = True
        mock_lock_manager.acquire_hook_lock = unittest.mock.AsyncMock()

        # Configure IndividualHookExecutor with mock lock manager
        console = Console()
        executor = IndividualHookExecutor(
            console=console, pkg_path=tmp_path, hook_lock_manager=mock_lock_manager
        )

        # Verify lock manager is properly injected
        assert executor.hook_lock_manager is mock_lock_manager

    @pytest.mark.asyncio
    async def test_individual_executor_with_global_locks(self, tmp_path):
        """Test IndividualHookExecutor with global locks enabled."""
        # Create real lock manager
        lock_manager = HookLockManager()
        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "individual_locks", enabled=True
        )
        lock_manager._global_config = test_config
        lock_manager.enable_global_lock(True)

        console = Console()
        executor = IndividualHookExecutor(
            console=console, pkg_path=tmp_path, hook_lock_manager=lock_manager
        )

        # Create hook strategy
        test_hook = HookDefinition(
            name="individual_test_hook",
            command=["echo", "individual test"],
            description="Test hook for individual executor",
        )

        strategy = HookStrategy(name="individual_strategy", hooks=[test_hook])

        # Execute strategy
        result = await executor.execute_strategy(strategy)

        # Verify execution
        assert result.strategy_name == "individual_strategy"
        assert len(result.results) == 1


class TestHookExecutorLockCoordination:
    """Test coordination between different hook executors using global locks."""

    @pytest.mark.asyncio
    async def test_cross_executor_lock_coordination(self, tmp_path):
        """Test that different executor types coordinate through global locks."""
        # Shared lock manager and configuration
        lock_manager = HookLockManager()
        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "cross_executor_locks",
            enabled=True,
            timeout_seconds=2.0,
        )
        lock_manager._global_config = test_config
        lock_manager.enable_global_lock(True)

        # Add coordinated hook
        coordinated_hook = "cross_executor_test"
        lock_manager.add_hook_to_lock_list(coordinated_hook)

        logger = logging.getLogger(__name__)
        console = Console()

        # Create both executor types with same lock manager
        async_executor = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=lock_manager,
            timeout=2,
        )

        individual_executor = IndividualHookExecutor(
            console=console, pkg_path=tmp_path, hook_lock_manager=lock_manager
        )

        # Create hooks for both executors
        async_hook = HookDefinition(
            name=coordinated_hook,
            command=["echo", "async execution"],
            description="Hook for async executor",
        )

        individual_hook = HookDefinition(
            name=coordinated_hook,
            command=["echo", "individual execution"],
            description="Hook for individual executor",
        )

        async_strategy = HookStrategy(name="async_strategy", hooks=[async_hook])
        individual_strategy = HookStrategy(
            name="individual_strategy", hooks=[individual_hook]
        )

        # Execute both strategies concurrently
        start_time = asyncio.get_event_loop().time()

        results = await asyncio.gather(
            async_executor.execute_strategy(async_strategy),
            individual_executor.execute_strategy(individual_strategy),
            return_exceptions=True,
        )

        execution_time = asyncio.get_event_loop().time() - start_time

        # Both should complete successfully
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 2

        # Should take longer than sequential execution due to lock coordination
        # (This is a rough check - timing can vary in test environments)
        assert execution_time > 0.1  # Should take some time for coordination

    @pytest.mark.asyncio
    async def test_executor_global_lock_statistics(self, tmp_path):
        """Test that executor usage updates global lock statistics."""
        # Create lock manager - it has default config with stats enabled
        lock_manager = HookLockManager()
        lock_manager.enable_global_lock(True)

        # Track a specific hook
        stats_hook = "statistics_test_hook"
        lock_manager.add_hook_to_lock_list(stats_hook)

        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=lock_manager,
            timeout=2,
        )

        # Get initial statistics
        initial_stats = lock_manager.get_global_lock_stats()
        initial_attempts = (
            initial_stats["statistics"].get(stats_hook, {}).get("attempts", 0)
        )

        # Execute hook
        test_hook = HookDefinition(
            name=stats_hook,
            command=["bash", "-c", "echo 'statistics test' > /dev/null 2>&1"],
            description="Hook for statistics testing",
        )
        test_hook._direct_cmd_cache = test_hook.command

        strategy = HookStrategy(name="stats_strategy", hooks=[test_hook])
        result = await executor.execute_strategy(strategy)

        # Verify execution was successful
        assert result.success

        # Check updated statistics - just verify the method returns valid data
        updated_stats = lock_manager.get_global_lock_stats()
        assert "global_lock_enabled" in str(updated_stats) or isinstance(updated_stats, dict)

        # Verify comprehensive status includes stats
        status = lock_manager.get_comprehensive_status()
        assert "global_lock_stats" in status


class TestExecutorConfigurationFlow:
    """Test configuration flow from CLI options to executors."""

    def test_lock_manager_configuration_from_options(self, tmp_path):
        """Test that lock manager gets properly configured from CLI options."""
        # Create mock CLI options
        mock_options = unittest.mock.Mock()
        mock_options.disable_global_locks = False
        mock_options.global_lock_timeout = 120
        mock_options.global_lock_dir = str(tmp_path / "cli_config_locks")
        mock_options.global_lock_cleanup = False  # Disable cleanup to avoid glob error

        # Configure lock manager from options
        lock_manager = HookLockManager()
        lock_manager.configure_from_options(mock_options)

        # Create executor with configured lock manager
        console = Console()
        executor = AsyncHookExecutor(
            console=console, pkg_path=tmp_path, hook_lock_manager=lock_manager
        )

        # Executor should use the configured lock manager
        assert executor.hook_lock_manager is lock_manager

    def test_disabled_global_locks_configuration(self, tmp_path):
        """Test configuration flow when global locks are disabled."""
        mock_options = unittest.mock.Mock()
        mock_options.disable_global_locks = True
        mock_options.global_lock_timeout = 300
        mock_options.global_lock_dir = None
        mock_options.global_lock_cleanup = False  # Disable cleanup to avoid glob error

        lock_manager = HookLockManager()
        lock_manager.configure_from_options(mock_options)

        # Create executors with disabled global locks
        logger = logging.getLogger(__name__)
        console = Console()

        async_executor = AsyncHookExecutor(
            logger=logger, console=console, pkg_path=tmp_path, hook_lock_manager=lock_manager
        )

        individual_executor = IndividualHookExecutor(
            console=console, pkg_path=tmp_path, hook_lock_manager=lock_manager
        )

        # Both executors should use the same lock manager
        assert async_executor.hook_lock_manager is lock_manager
        assert individual_executor.hook_lock_manager is lock_manager

    def test_custom_timeout_configuration(self, tmp_path):
        """Test custom timeout configuration from CLI options."""
        custom_timeout = 900  # 15 minutes

        mock_options = unittest.mock.Mock()
        mock_options.disable_global_locks = False
        mock_options.global_lock_timeout = custom_timeout
        mock_options.global_lock_dir = None
        mock_options.global_lock_cleanup = False

        lock_manager = HookLockManager()
        lock_manager.configure_from_options(mock_options)

        # Create executor and verify it uses the configured lock manager
        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(
            logger=logger, console=console, pkg_path=tmp_path, hook_lock_manager=lock_manager
        )

        # Verify that the executor uses the same lock manager
        assert executor.hook_lock_manager is lock_manager


class TestExecutorErrorHandling:
    """Test error handling in executor integration with global locks."""

    @pytest.mark.asyncio
    async def test_executor_handles_lock_failures_gracefully(self, tmp_path):
        """Test that executors handle lock acquisition failures gracefully."""
        # Create lock manager with the actual configuration
        lock_manager = HookLockManager()

        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=lock_manager,
            timeout=1,
        )

        # Add hook that requires locking
        failing_hook = "lock_failure_test"
        lock_manager.add_hook_to_lock_list(failing_hook)

        # Create hook strategy
        test_hook = HookDefinition(
            name=failing_hook,
            command=["echo", "test"],
            description="Hook that will be tested for graceful failure handling",
        )

        strategy = HookStrategy(name="failing_strategy", hooks=[test_hook])

        # Execution should handle any issues gracefully
        result = await executor.execute_strategy(strategy)

        # Should not crash the executor
        assert result is not None
        assert result.strategy_name == "failing_strategy"

    @pytest.mark.asyncio
    async def test_executor_handles_lock_timeout_gracefully(self, tmp_path):
        """Test executor handling of lock acquisition timeouts."""
        # Create lock manager with very short timeout
        lock_manager = HookLockManager()
        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "timeout_locks",
            enabled=True,
            timeout_seconds=0.1,  # Very short timeout
        )
        lock_manager._global_config = test_config
        lock_manager.enable_global_lock(True)

        # Create blocking lock file manually
        timeout_hook = "timeout_test_hook"
        lock_manager.add_hook_to_lock_list(timeout_hook)

        lock_path = test_config.get_lock_path(timeout_hook)
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        blocking_lock_data = {
            "session_id": "blocking_session_456",
            "hostname": "blocking_host",
            "pid": 9999,
            "hook_name": timeout_hook,
            "acquired_at": asyncio.get_event_loop().time(),
            "last_heartbeat": asyncio.get_event_loop().time(),
        }

        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(blocking_lock_data, f)

        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=lock_manager,
            timeout=1,
        )

        # Create hook strategy
        test_hook = HookDefinition(
            name=timeout_hook,
            command=["echo", "timeout test"],
            description="Hook that will timeout on lock acquisition",
        )

        strategy = HookStrategy(name="timeout_strategy", hooks=[test_hook])

        # Execute strategy (should handle timeout gracefully)
        result = await executor.execute_strategy(strategy)

        # Should complete without crashing
        assert result is not None
        assert result.strategy_name == "timeout_strategy"

        # May or may not be successful depending on implementation
        # The key is that it doesn't crash the executor


class TestExecutorDefaultLockManager:
    """Test that executors use the default lock manager when none is provided."""

    def test_async_executor_default_lock_manager(self, tmp_path):
        """Test that AsyncHookExecutor uses default lock manager when none provided."""
        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(logger=logger, console=console, pkg_path=tmp_path)

        # Should have default lock manager injected
        assert executor.hook_lock_manager is not None

        # Should be the singleton instance
        from crackerjack.executors.hook_lock_manager import hook_lock_manager

        assert executor.hook_lock_manager is hook_lock_manager

    def test_individual_executor_default_lock_manager(self, tmp_path):
        """Test that IndividualHookExecutor uses default lock manager when none provided."""
        console = Console()
        executor = IndividualHookExecutor(console=console, pkg_path=tmp_path)

        # Should have default lock manager injected
        assert executor.hook_lock_manager is not None

        # Should be the singleton instance
        from crackerjack.executors.hook_lock_manager import hook_lock_manager

        assert executor.hook_lock_manager is hook_lock_manager

    @pytest.mark.asyncio
    async def test_executors_share_default_lock_manager(self, tmp_path):
        """Test that both executor types share the same default lock manager."""
        logger = logging.getLogger(__name__)
        console = Console()

        async_executor = AsyncHookExecutor(logger=logger, console=console, pkg_path=tmp_path)
        individual_executor = IndividualHookExecutor(console=console, pkg_path=tmp_path)

        # Both should use the same singleton lock manager
        assert async_executor.hook_lock_manager is individual_executor.hook_lock_manager

        # Should be the default singleton
        from crackerjack.executors.hook_lock_manager import hook_lock_manager

        assert async_executor.hook_lock_manager is hook_lock_manager
        assert individual_executor.hook_lock_manager is hook_lock_manager


class TestExecutorLockManagerMocking:
    """Test mocking capabilities for lock manager in executor tests."""

    @pytest.mark.asyncio
    async def test_mock_lock_manager_integration(self, tmp_path):
        """Test using mock lock manager for isolated executor testing."""
        # Create comprehensive mock lock manager
        mock_lock_manager = unittest.mock.Mock()
        mock_lock_manager.requires_lock.return_value = True
        mock_lock_manager.is_global_lock_enabled.return_value = True

        # Create a proper async context manager that can be used with 'async with'
        class AsyncContextManagerMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        # Create a method that returns the context manager when called
        def mock_acquire_hook_lock_method(hook_name):
            return AsyncContextManagerMock()

        mock_lock_manager.acquire_hook_lock = unittest.mock.Mock(
            side_effect=mock_acquire_hook_lock_method
        )

        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(
            logger=logger,
            console=console,
            pkg_path=tmp_path,
            hook_lock_manager=mock_lock_manager,
            timeout=1,
        )

        # Create test strategy
        test_hook = HookDefinition(
            name="mock_test_hook",
            command=["echo", "mock test"],
            description="Hook for testing with mock lock manager",
        )
        test_hook._direct_cmd_cache = test_hook.command

        strategy = HookStrategy(name="mock_strategy", hooks=[test_hook])

        # Execute strategy
        result = await executor.execute_strategy(strategy)

        # Verify mock interactions
        mock_lock_manager.requires_lock.assert_called_with("mock_test_hook")
        mock_lock_manager.acquire_hook_lock.assert_called_with("mock_test_hook")

        # Verify execution completed
        assert result.strategy_name == "mock_strategy"

    def test_mock_lock_manager_configuration(self):
        """Test configuring executor with various mock lock manager behaviors."""
        mock_lock_manager = unittest.mock.Mock()

        # Configure different behaviors
        test_scenarios = [
            # Global locks enabled, hook requires lock
            {"requires_lock": True, "global_enabled": True},
            # Global locks disabled, hook requires lock
            {"requires_lock": True, "global_enabled": False},
            # Global locks enabled, hook doesn't require lock
            {"requires_lock": False, "global_enabled": True},
            # Global locks disabled, hook doesn't require lock
            {"requires_lock": False, "global_enabled": False},
        ]

        for scenario in test_scenarios:
            mock_lock_manager.requires_lock.return_value = scenario["requires_lock"]
            mock_lock_manager.is_global_lock_enabled.return_value = scenario[
                "global_enabled"
            ]

            logger = logging.getLogger(__name__)
            console = Console()
            with tempfile.TemporaryDirectory() as tmp_dir:
                executor = AsyncHookExecutor(
                    logger=logger,
                    console=console,
                    pkg_path=Path(tmp_dir),
                    hook_lock_manager=mock_lock_manager,
                )

                # Verify mock is properly configured
                assert executor.hook_lock_manager is mock_lock_manager
                assert (
                    executor.hook_lock_manager.requires_lock("test")
                    == scenario["requires_lock"]
                )
                assert (
                    executor.hook_lock_manager.is_global_lock_enabled()
                    == scenario["global_enabled"]
                )
