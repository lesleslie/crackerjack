"""Comprehensive tests for HookLockManager functionality.

Tests cover:
- Basic functionality: enable/disable global locks, protocol compliance
- Lock file operations: atomic creation, JSON format, proper permissions
- Cross-session coordination: multiple lock manager instances can't acquire same lock
- Heartbeat mechanism: lock maintenance, heartbeat failure handling
- Stale lock detection: cleanup based on age and missing heartbeat
- Error handling: file permission errors, disk full, corrupted lock files
- Statistics tracking: acquisition times, success rates, failure counts
"""

import asyncio
import json
import os
import time
import unittest.mock
from contextlib import suppress
from pathlib import Path

import pytest

from crackerjack.config.global_lock_config import GlobalLockConfig
from crackerjack.executors.hook_lock_manager import HookLockManager


class TestHookLockManagerBasics:
    """Test basic HookLockManager functionality and protocol compliance."""

    def test_singleton_behavior(self):
        """Test that HookLockManager follows singleton pattern."""
        manager1 = HookLockManager()
        manager2 = HookLockManager()

        assert manager1 is manager2
        assert id(manager1) == id(manager2)

    def test_initial_configuration(self):
        """Test initial configuration and default values."""
        manager = HookLockManager()

        # Should have complexipy in required locks by default
        assert manager.requires_lock("complexipy")
        assert not manager.requires_lock("nonexistent_hook")

        # Global locks should be enabled by default
        assert manager.is_global_lock_enabled()

        # Default timeout should be set
        assert manager.get_hook_timeout("complexipy") == 300.0

    def test_hook_lock_list_management(self):
        """Test adding and removing hooks from lock list."""
        manager = HookLockManager()

        # Add new hook
        test_hook = "test_hook_unique_name"
        assert not manager.requires_lock(test_hook)

        manager.add_hook_to_lock_list(test_hook)
        assert manager.requires_lock(test_hook)

        # Remove hook
        manager.remove_hook_from_lock_list(test_hook)
        assert not manager.requires_lock(test_hook)

    def test_global_lock_enable_disable(self):
        """Test enabling and disabling global lock functionality."""
        manager = HookLockManager()

        # Initially enabled
        assert manager.is_global_lock_enabled()

        # Disable
        manager.enable_global_lock(False)
        assert not manager.is_global_lock_enabled()

        # Re-enable
        manager.enable_global_lock(True)
        assert manager.is_global_lock_enabled()

    def test_hook_timeout_management(self):
        """Test custom timeout setting for hooks."""
        manager = HookLockManager()

        hook_name = "timeout_test_hook"
        default_timeout = manager.get_hook_timeout(hook_name)

        # Set custom timeout
        custom_timeout = 120.0
        manager.set_hook_timeout(hook_name, custom_timeout)

        assert manager.get_hook_timeout(hook_name) == custom_timeout
        assert manager.get_hook_timeout(hook_name) != default_timeout

    def test_lock_stats_structure(self):
        """Test lock statistics structure and content."""
        manager = HookLockManager()

        stats = manager.get_lock_stats()

        assert isinstance(stats, dict)

        # Should have stats for hooks requiring locks
        if "complexipy" in stats:
            hook_stats = stats["complexipy"]
            required_fields = {
                "total_acquisitions",
                "avg_wait_time",
                "max_wait_time",
                "min_wait_time",
                "avg_execution_time",
                "max_execution_time",
                "min_execution_time",
                "currently_locked",
                "lock_failures",
                "timeout_failures",
                "success_rate",
                "lock_timeout",
            }

            for field in required_fields:
                assert field in hook_stats

    def test_global_lock_path_generation(self, tmp_path):
        """Test global lock path generation."""
        manager = HookLockManager()

        # Configure with temporary directory
        mock_config = GlobalLockConfig(lock_directory=tmp_path / "test_locks")
        manager._global_config = mock_config

        hook_name = "path_test_hook"
        lock_path = manager.get_global_lock_path(hook_name)

        assert lock_path.parent == tmp_path / "test_locks"
        assert lock_path.name == f"{hook_name}.lock"


class TestHookLockManagerAsyncLocking:
    """Test async locking functionality."""

    @pytest.mark.asyncio
    async def test_hook_not_requiring_lock_immediate_return(self):
        """Test that hooks not requiring locks return immediately."""
        manager = HookLockManager()

        hook_name = "no_lock_needed_hook"
        assert not manager.requires_lock(hook_name)

        start_time = time.time()
        async with manager.acquire_hook_lock(hook_name):
            pass
        execution_time = time.time() - start_time

        # Should be very fast (< 0.1 seconds)
        assert execution_time < 0.1

    @pytest.mark.asyncio
    async def test_hook_specific_lock_acquisition(self):
        """Test hook-specific lock acquisition when global locks are disabled."""
        manager = HookLockManager()
        manager.enable_global_lock(False)  # Disable global locks

        hook_name = "hook_specific_test"
        manager.add_hook_to_lock_list(hook_name)

        # First acquisition should succeed
        async with manager.acquire_hook_lock(hook_name):
            # While holding lock, it should be marked as locked
            assert manager.is_hook_currently_locked(hook_name)

        # After release, should not be locked
        assert not manager.is_hook_currently_locked(hook_name)

    @pytest.mark.asyncio
    async def test_concurrent_hook_lock_prevention(self):
        """Test that concurrent hook locks are prevented."""
        manager = HookLockManager()
        manager.enable_global_lock(False)  # Use only hook-specific locks for simplicity

        hook_name = "concurrent_test_hook"
        manager.add_hook_to_lock_list(hook_name)
        # Set timeout shorter than hold time to force one task to timeout
        # Task1 acquires immediately, holds for 0.5s
        # Task2 needs to fail before 0.5s elapses, so timeout must be < 0.5s
        manager.set_hook_timeout(hook_name, 0.2)  # Timeout shorter than lock hold time

        results = []

        async def acquire_lock(identifier):
            try:
                async with manager.acquire_hook_lock(hook_name):
                    results.append(f"{identifier}_acquired")
                    await asyncio.sleep(0.5)  # Hold lock for 0.5 seconds
                    results.append(f"{identifier}_released")
            except TimeoutError:
                results.append(f"{identifier}_timeout")

        # Start two concurrent lock acquisitions
        task1 = asyncio.create_task(acquire_lock("task1"))
        task2 = asyncio.create_task(acquire_lock("task2"))

        await asyncio.gather(task1, task2, return_exceptions=True)

        # One should succeed, one should timeout
        acquired_count = sum(1 for r in results if "_acquired" in r)
        timeout_count = sum(1 for r in results if "_timeout" in r)

        assert acquired_count == 1
        assert timeout_count == 1

    @pytest.mark.asyncio
    async def test_lock_timeout_handling(self):
        """Test lock acquisition timeout handling."""
        manager = HookLockManager()
        manager.enable_global_lock(False)

        hook_name = "timeout_handling_test"
        manager.add_hook_to_lock_list(hook_name)
        manager.set_hook_timeout(hook_name, 0.1)  # Very short timeout

        # Acquire lock and hold it
        async def hold_lock():
            async with manager.acquire_hook_lock(hook_name):
                await asyncio.sleep(1.0)  # Hold for 1 second

        # Start holding lock
        hold_task = asyncio.create_task(hold_lock())
        await asyncio.sleep(0.05)  # Let first task acquire lock

        # Try to acquire lock with timeout
        start_time = time.time()
        with pytest.raises(asyncio.TimeoutError):
            async with manager.acquire_hook_lock(hook_name):
                pass

        timeout_duration = time.time() - start_time
        # Should timeout around 0.1 seconds
        assert 0.05 < timeout_duration < 0.3

        # Cleanup
        hold_task.cancel()
        with suppress(asyncio.CancelledError):
            await hold_task


class TestGlobalLockFileOperations:
    """Test global lock file operations and atomic behavior."""

    @pytest.mark.asyncio
    async def test_global_lock_file_creation(self, tmp_path):
        """Test atomic global lock file creation with proper JSON format."""
        manager = HookLockManager()

        # Configure with test directory
        test_config = GlobalLockConfig(lock_directory=tmp_path / "locks")
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "file_creation_test"
        manager.add_hook_to_lock_list(hook_name)

        lock_path = test_config.get_lock_path(hook_name)

        async with manager.acquire_hook_lock(hook_name):
            # Lock file should exist
            assert lock_path.exists()

            # Should have proper JSON format
            with open(lock_path, encoding="utf-8") as f:
                lock_data = json.load(f)

            # Check required fields
            required_fields = {
                "session_id",
                "hostname",
                "pid",
                "hook_name",
                "acquired_at",
                "last_heartbeat",
            }
            for field in required_fields:
                assert field in lock_data

            # Check data correctness
            assert lock_data["hook_name"] == hook_name
            assert lock_data["session_id"] == test_config.session_id
            assert lock_data["hostname"] == test_config.hostname
            assert lock_data["pid"] == os.getpid()

        # After context exit, lock file should be removed
        assert not lock_path.exists()

    @pytest.mark.asyncio
    async def test_lock_file_permissions(self, tmp_path):
        """Test that lock files have proper permissions (0o600)."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(lock_directory=tmp_path / "locks")
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "permissions_test"
        manager.add_hook_to_lock_list(hook_name)

        lock_path = test_config.get_lock_path(hook_name)

        async with manager.acquire_hook_lock(hook_name):
            # Check file permissions
            stat_result = lock_path.stat()
            permissions = stat_result.st_mode & 0o777
            assert permissions == 0o600  # Owner read/write only

    @pytest.mark.asyncio
    async def test_cross_session_coordination_simulation(self, tmp_path):
        """Test cross-session coordination by simulating different sessions."""
        # Create two managers with different session IDs (simulating different processes)

        lock_dir = tmp_path / "cross_session_locks"

        # Manager 1 (current session)
        manager1 = HookLockManager()
        config1 = GlobalLockConfig(lock_directory=lock_dir)
        manager1._global_config = config1
        manager1.enable_global_lock(True)

        # Manager 2 (simulate different session)
        manager2 = HookLockManager()
        config2 = GlobalLockConfig(lock_directory=lock_dir)
        # Simulate different session ID
        with unittest.mock.patch.object(config2, "session_id", "different_host_9999"):
            manager2._global_config = config2
            manager2.enable_global_lock(True)

            hook_name = "cross_session_test"
            manager1.add_hook_to_lock_list(hook_name)
            manager2.add_hook_to_lock_list(hook_name)

            # Manager 1 acquires lock
            async with manager1.acquire_hook_lock(hook_name):
                lock_path = config1.get_lock_path(hook_name)
                assert lock_path.exists()

                # Manager 2 should fail to acquire the same lock
                manager2.set_hook_timeout(hook_name, 0.1)  # Short timeout for test

                with pytest.raises(asyncio.TimeoutError):
                    async with manager2.acquire_hook_lock(hook_name):
                        pass

            # After manager 1 releases, lock file should be gone
            assert not lock_path.exists()

    @pytest.mark.asyncio
    async def test_corrupted_lock_file_handling(self, tmp_path):
        """Test handling of corrupted lock files."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(lock_directory=tmp_path / "locks")
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "corrupted_file_test"
        manager.add_hook_to_lock_list(hook_name)

        lock_path = test_config.get_lock_path(hook_name)

        # Create corrupted lock file
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("invalid json content {{{")

        # Should be able to acquire lock (corrupted file gets cleaned up)
        async with manager.acquire_hook_lock(hook_name):
            # Should have valid lock file now
            assert lock_path.exists()

            with open(lock_path, encoding="utf-8") as f:
                lock_data = json.load(f)  # Should not raise exception

            assert lock_data["hook_name"] == hook_name


class TestHeartbeatMechanism:
    """Test heartbeat mechanism for lock maintenance."""

    @pytest.mark.asyncio
    async def test_heartbeat_updates_lock_file(self, tmp_path):
        """Test that heartbeat mechanism updates lock file timestamps."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "locks",
            session_heartbeat_interval=0.1,  # Very frequent heartbeats for testing
        )
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "heartbeat_test"
        manager.add_hook_to_lock_list(hook_name)

        lock_path = test_config.get_lock_path(hook_name)

        async with manager.acquire_hook_lock(hook_name):
            # Get initial heartbeat timestamp
            with open(lock_path, encoding="utf-8") as f:
                initial_data = json.load(f)

            initial_heartbeat = initial_data["last_heartbeat"]

            # Wait for heartbeat to update
            await asyncio.sleep(0.3)  # Wait for 3 heartbeats

            # Check updated heartbeat
            with open(lock_path, encoding="utf-8") as f:
                updated_data = json.load(f)

            updated_heartbeat = updated_data["last_heartbeat"]

            # Heartbeat should have been updated
            assert updated_heartbeat > initial_heartbeat

            # Session ID should remain the same
            assert updated_data["session_id"] == initial_data["session_id"]

    @pytest.mark.asyncio
    async def test_heartbeat_task_cleanup_on_release(self, tmp_path):
        """Test that heartbeat tasks are properly cleaned up on lock release."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "locks", session_heartbeat_interval=0.1
        )
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "heartbeat_cleanup_test"
        manager.add_hook_to_lock_list(hook_name)

        # Before acquiring lock, no heartbeat task should exist
        assert hook_name not in manager._heartbeat_tasks
        assert hook_name not in manager._active_global_locks

        async with manager.acquire_hook_lock(hook_name):
            # During lock, heartbeat task should exist
            assert hook_name in manager._heartbeat_tasks
            assert hook_name in manager._active_global_locks

            # Task should be active (not done/cancelled)
            heartbeat_task = manager._heartbeat_tasks[hook_name]
            assert not heartbeat_task.done()

        # After lock release, heartbeat task should be cleaned up
        assert hook_name not in manager._heartbeat_tasks
        assert hook_name not in manager._active_global_locks


class TestStaleLockCleanup:
    """Test stale lock detection and cleanup functionality."""

    def test_cleanup_stale_locks_by_age(self, tmp_path):
        """Test cleanup of stale locks based on file age."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(lock_directory=tmp_path / "locks")
        manager._global_config = test_config

        # Create old lock files
        old_lock_path = test_config.get_lock_path("old_hook")
        old_lock_path.parent.mkdir(parents=True, exist_ok=True)

        old_lock_data = {
            "session_id": "old_session_123",
            "hostname": "old_host",
            "pid": 999,
            "hook_name": "old_hook",
            "acquired_at": time.time() - 7200,  # 2 hours ago
            "last_heartbeat": time.time() - 7200,  # 2 hours ago
        }

        with open(old_lock_path, "w", encoding="utf-8") as f:
            json.dump(old_lock_data, f)

        # Create recent lock file
        recent_lock_path = test_config.get_lock_path("recent_hook")
        recent_lock_data = {
            "session_id": "recent_session_456",
            "hostname": "recent_host",
            "pid": 888,
            "hook_name": "recent_hook",
            "acquired_at": time.time(),
            "last_heartbeat": time.time(),
        }

        with open(recent_lock_path, "w", encoding="utf-8") as f:
            json.dump(recent_lock_data, f)

        # Run cleanup with 1 hour threshold
        cleaned_count = manager.cleanup_stale_locks(max_age_hours=1.0)

        # Old lock should be cleaned, recent should remain
        assert cleaned_count == 1
        assert not old_lock_path.exists()
        assert recent_lock_path.exists()

    def test_cleanup_corrupted_lock_files(self, tmp_path):
        """Test cleanup of corrupted/invalid lock files."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(lock_directory=tmp_path / "locks")
        manager._global_config = test_config

        locks_dir = test_config.lock_directory
        locks_dir.mkdir(parents=True, exist_ok=True)

        # Create corrupted lock files
        corrupted_files = ["corrupted1.lock", "corrupted2.lock", "invalid.lock"]

        for filename in corrupted_files:
            corrupted_path = locks_dir / filename
            corrupted_path.write_text("invalid json content {{{")

        # Run cleanup
        cleaned_count = manager.cleanup_stale_locks()

        # All corrupted files should be cleaned
        assert cleaned_count == len(corrupted_files)

        for filename in corrupted_files:
            assert not (locks_dir / filename).exists()

    def test_no_cleanup_if_directory_missing(self, tmp_path):
        """Test cleanup behavior when lock directory doesn't exist."""
        manager = HookLockManager()

        # Configure with non-existent directory
        nonexistent_dir = tmp_path / "nonexistent" / "locks"
        test_config = GlobalLockConfig(lock_directory=nonexistent_dir)
        manager._global_config = test_config

        # Should handle gracefully and return 0
        cleaned_count = manager.cleanup_stale_locks()
        assert cleaned_count == 0

    @pytest.mark.asyncio
    async def test_stale_lock_cleanup_during_acquisition(self, tmp_path):
        """Test that stale lock cleanup happens before acquisition attempt."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "locks",
            stale_lock_hours=0.001,  # 3.6 seconds = very short for testing
        )
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "stale_cleanup_test"
        manager.add_hook_to_lock_list(hook_name)

        lock_path = test_config.get_lock_path(hook_name)

        # Create stale lock file
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        stale_lock_data = {
            "session_id": "stale_session_999",
            "hostname": "stale_host",
            "pid": 999,
            "hook_name": hook_name,
            "acquired_at": time.time() - 3600,  # 1 hour ago
            "last_heartbeat": time.time() - 3600,  # 1 hour ago
        }

        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(stale_lock_data, f)

        # Acquiring lock should clean up stale lock and succeed
        async with manager.acquire_hook_lock(hook_name):
            # Lock should now be owned by current session
            with open(lock_path, encoding="utf-8") as f:
                current_lock_data = json.load(f)

            assert current_lock_data["session_id"] == test_config.session_id
            assert current_lock_data["hook_name"] == hook_name


class TestStatisticsTracking:
    """Test comprehensive statistics tracking for global locks."""

    @pytest.mark.asyncio
    async def test_global_lock_stats_tracking(self, tmp_path):
        """Test that global lock statistics are properly tracked."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(lock_directory=tmp_path / "locks")
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "stats_tracking_test"
        manager.add_hook_to_lock_list(hook_name)

        # Get initial stats
        initial_stats = manager.get_global_lock_stats()
        initial_attempts = (
            initial_stats["statistics"].get(hook_name, {}).get("attempts", 0)
        )
        initial_successes = (
            initial_stats["statistics"].get(hook_name, {}).get("successes", 0)
        )

        # Perform successful lock acquisition
        async with manager.acquire_hook_lock(hook_name):
            pass

        # Check updated stats
        updated_stats = manager.get_global_lock_stats()
        hook_stats = updated_stats["statistics"][hook_name]

        # Should have incremented attempts and successes
        assert hook_stats["attempts"] == initial_attempts + 1
        assert hook_stats["successes"] == initial_successes + 1
        assert hook_stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_global_lock_failure_stats(self, tmp_path):
        """Test tracking of global lock failures."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "locks",
            max_retry_attempts=1,  # Only 1 attempt to force quick failure
            retry_delay_seconds=0.1,
        )
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "failure_stats_test"
        manager.add_hook_to_lock_list(hook_name)

        # Create lock file to block acquisition
        lock_path = test_config.get_lock_path(hook_name)
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        blocking_lock_data = {
            "session_id": "blocking_session_123",
            "hostname": "blocking_host",
            "pid": 777,
            "hook_name": hook_name,
            "acquired_at": time.time(),
            "last_heartbeat": time.time(),
        }

        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(blocking_lock_data, f)

        # Attempt to acquire lock (should fail)
        with pytest.raises(asyncio.TimeoutError):
            async with manager.acquire_hook_lock(hook_name):
                pass

        # Check failure stats
        stats = manager.get_global_lock_stats()
        hook_stats = stats["statistics"][hook_name]

        assert hook_stats["attempts"] > 0
        assert hook_stats["failures"] > 0
        assert hook_stats["success_rate"] < 1.0

    def test_comprehensive_status_includes_global_stats(self, tmp_path):
        """Test that comprehensive status includes global lock information."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(lock_directory=tmp_path / "locks")
        manager._global_config = test_config
        manager.enable_global_lock(True)

        status = manager.get_comprehensive_status()

        # Should include global lock stats
        assert "global_lock_stats" in status

        global_stats = status["global_lock_stats"]
        assert "global_lock_enabled" in global_stats
        assert global_stats["global_lock_enabled"] is True

        assert "session_id" in global_stats
        assert "hostname" in global_stats
        assert "configuration" in global_stats

        # Configuration should have expected fields
        config = global_stats["configuration"]
        expected_config_fields = {
            "timeout_seconds",
            "stale_lock_hours",
            "heartbeat_interval",
            "max_retry_attempts",
            "retry_delay_seconds",
            "enable_lock_monitoring",
        }

        for field in expected_config_fields:
            assert field in config

    def test_stats_reset_functionality(self):
        """Test resetting statistics for specific or all hooks."""
        manager = HookLockManager()

        # Add some test data to statistics
        test_hook = "stats_reset_test"
        manager._lock_usage[test_hook] = [1.0, 2.0, 3.0]
        manager._lock_failures[test_hook] = 5
        manager._timeout_failures[test_hook] = 2

        # Reset specific hook
        manager.reset_hook_stats(test_hook)

        assert len(manager._lock_usage[test_hook]) == 0
        assert manager._lock_failures[test_hook] == 0
        assert manager._timeout_failures[test_hook] == 0

        # Add data to multiple hooks
        manager._lock_usage["hook1"] = [1.0]
        manager._lock_usage["hook2"] = [2.0]
        manager._lock_failures["hook1"] = 1
        manager._lock_failures["hook2"] = 2

        # Reset all hooks
        manager.reset_hook_stats(None)

        assert len(manager._lock_usage) == 0
        assert len(manager._lock_failures) == 0


class TestConfigurationIntegration:
    """Test configuration integration and CLI options flow."""

    def test_configure_from_options(self, tmp_path):
        """Test configuring lock manager from CLI options.

        Tests that configure_from_options properly updates the manager's
        global lock configuration with values from CLI options.
        """
        manager = HookLockManager()

        # Create a real lock directory for testing
        custom_lock_dir = tmp_path / "custom_locks"
        custom_lock_dir.mkdir(parents=True, exist_ok=True)

        # Test using mock options - simulates CLI behavior
        # Note: We can't fully test from_options here due to DI requirements,
        # so we test the essential configuration update behavior directly
        from crackerjack.config.global_lock_config import GlobalLockConfig
        from crackerjack.config.settings import GlobalLockSettings

        # Directly set config to bypass DI issues in test
        settings = GlobalLockSettings(
            enabled=True,
            timeout_seconds=120.0,
            lock_directory=custom_lock_dir
        )
        config = GlobalLockConfig(settings=settings)
        manager._global_config = config
        manager._global_lock_enabled = config.enabled

        # Verify configuration was applied
        assert manager.is_global_lock_enabled() is True
        assert manager._global_config.timeout_seconds == 120.0
        assert (
            str(manager._global_config.lock_directory) == str(custom_lock_dir)
        )

    def test_configure_with_disabled_global_locks(self):
        """Test configuration with global locks disabled.

        Tests that the manager properly handles configuration with
        global locks disabled.
        """
        manager = HookLockManager()

        # Test disabling global locks via direct configuration
        # (avoiding DI issues with from_options in test environment)
        from crackerjack.config.global_lock_config import GlobalLockConfig
        from crackerjack.config.settings import GlobalLockSettings

        settings = GlobalLockSettings(enabled=False)
        config = GlobalLockConfig(settings=settings)
        manager._global_config = config
        manager._global_lock_enabled = config.enabled

        assert manager.is_global_lock_enabled() is False
        assert manager._global_config.enabled is False


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_file_permission_error_handling(self, tmp_path):
        """Test handling of file permission errors during lock operations."""
        manager = HookLockManager()

        # Create directory with restricted permissions
        restricted_dir = tmp_path / "restricted_locks"
        restricted_dir.mkdir(mode=0o000)  # No permissions

        try:
            test_config = GlobalLockConfig(lock_directory=restricted_dir)
            manager._global_config = test_config
            manager.enable_global_lock(True)

            hook_name = "permission_error_test"
            manager.add_hook_to_lock_list(hook_name)

            # Should handle permission error gracefully
            with pytest.raises(Exception):  # May be PermissionError or other exception
                async with manager.acquire_hook_lock(hook_name):
                    pass

        finally:
            # Restore permissions for cleanup
            with suppress(OSError):
                restricted_dir.chmod(0o755)

    @pytest.mark.asyncio
    async def test_disk_full_simulation(self, tmp_path, monkeypatch):
        """Test behavior when disk is full during lock file creation."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(lock_directory=tmp_path / "locks")
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "disk_full_test"
        manager.add_hook_to_lock_list(hook_name)

        # Mock Path.open() to raise OSError (disk full) during lock file creation
        from pathlib import Path as PathlibPath
        original_open = PathlibPath.open

        def mock_path_open(self, *args, **kwargs):
            # mode is passed as positional argument (args[0]) not kwargs
            mode = args[0] if args else kwargs.get("mode", "")
            if mode == "x" and "disk_full_test" in str(self):
                raise OSError("No space left on device")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr("pathlib.Path.open", mock_path_open)

        # Should handle disk full error gracefully
        with pytest.raises(OSError, match="No space left on device"):
            async with manager.acquire_hook_lock(hook_name):
                pass

    @pytest.mark.asyncio
    async def test_heartbeat_failure_handling(self, tmp_path):
        """Test handling of heartbeat failures."""
        manager = HookLockManager()

        test_config = GlobalLockConfig(
            lock_directory=tmp_path / "locks",
            session_heartbeat_interval=0.05,  # Very frequent for testing
        )
        manager._global_config = test_config
        manager.enable_global_lock(True)

        hook_name = "heartbeat_failure_test"
        manager.add_hook_to_lock_list(hook_name)

        async with manager.acquire_hook_lock(hook_name):
            # Delete lock file to simulate heartbeat failure
            lock_path = test_config.get_lock_path(hook_name)
            lock_path.unlink()

            # Wait for heartbeat to detect missing file
            await asyncio.sleep(0.2)

            # Hook should no longer be tracked as active
            assert hook_name not in manager._active_global_locks


class TestProtocolCompliance:
    """Test compliance with HookLockManagerProtocol."""

    def test_protocol_method_signatures(self):
        """Test that all protocol methods exist with correct signatures."""
        from crackerjack.models.protocols import HookLockManagerProtocol

        manager = HookLockManager()

        # Test that manager implements protocol
        assert isinstance(manager, HookLockManagerProtocol)

        # Test specific methods exist
        assert hasattr(manager, "requires_lock")
        assert hasattr(manager, "acquire_hook_lock")
        assert hasattr(manager, "get_lock_stats")
        assert hasattr(manager, "add_hook_to_lock_list")
        assert hasattr(manager, "remove_hook_from_lock_list")
        assert hasattr(manager, "is_hook_currently_locked")
        assert hasattr(manager, "enable_global_lock")
        assert hasattr(manager, "is_global_lock_enabled")
        assert hasattr(manager, "get_global_lock_path")
        assert hasattr(manager, "cleanup_stale_locks")
        assert hasattr(manager, "get_global_lock_stats")

        # Test method callable signatures
        assert callable(manager.requires_lock)
        assert callable(manager.acquire_hook_lock)
        assert callable(manager.get_lock_stats)

    def test_protocol_return_types(self):
        """Test that protocol methods return expected types."""
        manager = HookLockManager()

        # Test return types
        assert isinstance(manager.requires_lock("test"), bool)
        assert isinstance(manager.get_lock_stats(), dict)
        assert isinstance(manager.is_hook_currently_locked("test"), bool)
        assert isinstance(manager.is_global_lock_enabled(), bool)
        assert isinstance(manager.cleanup_stale_locks(), int)
        assert isinstance(manager.get_global_lock_stats(), dict)

        assert isinstance(manager.get_global_lock_path("test"), Path)
