"""Comprehensive tests for GlobalLockConfig class.

Tests cover:
- Directory creation and permissions (0o700)
- Session ID generation (hostname + PID)
- Lock file path generation
- Configuration validation
- from_options() class method functionality
"""

import os
import tempfile
import unittest.mock
from pathlib import Path

import pytest

from crackerjack.config.global_lock_config import GlobalLockConfig


class TestGlobalLockConfig:
    """Test GlobalLockConfig functionality and protocol compliance."""

    def test_default_initialization(self):
        """Test default configuration values."""
        config = GlobalLockConfig()

        assert config.enabled is True
        assert config.timeout_seconds == 600.0
        assert config.stale_lock_hours == 2.0
        assert config.session_heartbeat_interval == 30.0
        assert config.max_retry_attempts == 3
        assert config.retry_delay_seconds == 5.0
        assert config.enable_lock_monitoring is True

        # Default lock directory should be ~/.crackerjack/locks
        expected_dir = Path.home() / ".crackerjack" / "locks"
        assert config.lock_directory == expected_dir

    def test_lock_directory_creation_and_permissions(self, tmp_path):
        """Test that lock directory is created with proper permissions (0o700)."""
        lock_dir = tmp_path / "custom_locks"

        GlobalLockConfig(lock_directory=lock_dir)

        # Directory should be created
        assert lock_dir.exists()
        assert lock_dir.is_dir()

        # Should have restrictive permissions (owner only)
        stat_result = lock_dir.stat()
        permissions = stat_result.st_mode & 0o777
        assert permissions == 0o700

    def test_session_id_generation(self):
        """Test unique session ID generation using hostname + PID."""
        config = GlobalLockConfig()

        # Session ID should include hostname and PID
        expected_id = f"{config.hostname}_{os.getpid()}"
        assert config.session_id == expected_id

        # Should be deterministic for same process
        assert config.session_id == config.session_id

    def test_hostname_property(self):
        """Test hostname property returns current system hostname."""
        config = GlobalLockConfig()

        # Should match socket.gethostname()
        import socket

        expected_hostname = socket.gethostname()
        assert config.hostname == expected_hostname

    def test_lock_file_path_generation(self, tmp_path):
        """Test lock file path generation for hooks."""
        lock_dir = tmp_path / "locks"
        config = GlobalLockConfig(lock_directory=lock_dir)

        # Test various hook names
        hook_names = ["complexipy", "bandit", "ruff", "pytest"]

        for hook_name in hook_names:
            lock_path = config.get_lock_path(hook_name)

            # Should be in the lock directory
            assert lock_path.parent == lock_dir

            # Should have .lock extension
            assert lock_path.suffix == ".lock"

            # Should match hook name
            assert lock_path.stem == hook_name

            # Full path should be correct
            expected_path = lock_dir / f"{hook_name}.lock"
            assert lock_path == expected_path

    def test_heartbeat_file_path_generation(self, tmp_path):
        """Test heartbeat file path generation for hooks."""
        lock_dir = tmp_path / "locks"
        config = GlobalLockConfig(lock_directory=lock_dir)

        hook_name = "test_hook"
        heartbeat_path = config.get_heartbeat_path(hook_name)

        # Should be in the lock directory with .heartbeat extension
        expected_path = lock_dir / f"{hook_name}.heartbeat"
        assert heartbeat_path == expected_path

    def test_is_valid_lock_file_nonexistent(self, tmp_path):
        """Test lock file validation for non-existent files."""
        lock_dir = tmp_path / "locks"
        config = GlobalLockConfig(lock_directory=lock_dir)

        lock_path = lock_dir / "nonexistent.lock"
        assert not config.is_valid_lock_file(lock_path)

    def test_is_valid_lock_file_fresh(self, tmp_path):
        """Test lock file validation for fresh files."""
        lock_dir = tmp_path / "locks"
        config = GlobalLockConfig(lock_directory=lock_dir, stale_lock_hours=2.0)

        # Create a fresh lock file
        lock_path = lock_dir / "fresh.lock"
        lock_path.write_text('{"test": "data"}')

        assert config.is_valid_lock_file(lock_path)

    def test_is_valid_lock_file_stale(self, tmp_path):
        """Test lock file validation for stale files."""
        lock_dir = tmp_path / "locks"
        config = GlobalLockConfig(
            lock_directory=lock_dir, stale_lock_hours=0.001
        )  # 3.6 seconds

        # Create a lock file
        lock_path = lock_dir / "stale.lock"
        lock_path.write_text('{"test": "data"}')

        # Mock the file modification time to be old
        import time

        old_time = time.time() - 3600  # 1 hour ago
        os.utime(lock_path, (old_time, old_time))

        assert not config.is_valid_lock_file(lock_path)

    def test_from_options_with_mock_options(self):
        """Test from_options() class method with mock CLI options."""
        # Mock options object with CLI attributes
        mock_options = unittest.mock.Mock()
        mock_options.disable_global_locks = False
        mock_options.global_lock_timeout = 300
        mock_options.global_lock_dir = None

        config = GlobalLockConfig.from_options(mock_options)

        assert config.enabled is True
        assert config.timeout_seconds == 300.0
        assert config.lock_directory == Path.home() / ".crackerjack" / "locks"

    def test_from_options_with_disabled_locks(self):
        """Test from_options() with disabled global locks."""
        mock_options = unittest.mock.Mock()
        mock_options.disable_global_locks = True
        mock_options.global_lock_timeout = 600
        mock_options.global_lock_dir = None

        config = GlobalLockConfig.from_options(mock_options)

        assert config.enabled is False
        assert config.timeout_seconds == 600.0

    def test_from_options_with_custom_directory(self, tmp_path):
        """Test from_options() with custom lock directory."""
        custom_dir = str(tmp_path / "custom_locks")

        mock_options = unittest.mock.Mock()
        mock_options.disable_global_locks = False
        mock_options.global_lock_timeout = 600
        mock_options.global_lock_dir = custom_dir

        config = GlobalLockConfig.from_options(mock_options)

        assert config.enabled is True
        assert config.lock_directory == Path(custom_dir)
        assert config.lock_directory.exists()

    def test_configuration_validation_types(self):
        """Test configuration validation with various data types."""
        # Test with valid types
        config = GlobalLockConfig(
            enabled=False,
            timeout_seconds=120.5,
            stale_lock_hours=1.5,
            session_heartbeat_interval=15.0,
            max_retry_attempts=5,
            retry_delay_seconds=2.5,
            enable_lock_monitoring=False,
        )

        assert config.enabled is False
        assert config.timeout_seconds == 120.5
        assert config.stale_lock_hours == 1.5
        assert config.session_heartbeat_interval == 15.0
        assert config.max_retry_attempts == 5
        assert config.retry_delay_seconds == 2.5
        assert config.enable_lock_monitoring is False

    def test_multiple_config_instances_independent(self, tmp_path):
        """Test that multiple GlobalLockConfig instances are independent."""
        dir1 = tmp_path / "locks1"
        dir2 = tmp_path / "locks2"

        config1 = GlobalLockConfig(lock_directory=dir1, timeout_seconds=300)
        config2 = GlobalLockConfig(lock_directory=dir2, timeout_seconds=600)

        assert config1.lock_directory != config2.lock_directory
        assert config1.timeout_seconds != config2.timeout_seconds

        # Both directories should be created
        assert dir1.exists()
        assert dir2.exists()

    def test_lock_path_special_characters(self, tmp_path):
        """Test lock path generation with special characters in hook names."""
        lock_dir = tmp_path / "locks"
        config = GlobalLockConfig(lock_directory=lock_dir)

        # Test hook names with various characters (should be sanitized or handled)
        hook_names = [
            "hook-with-dashes",
            "hook_with_underscores",
            "hook.with.dots",
            "UPPERCASE_HOOK",
        ]

        for hook_name in hook_names:
            lock_path = config.get_lock_path(hook_name)

            # Should still generate valid path
            assert lock_path.parent == lock_dir
            assert lock_path.suffix == ".lock"
            assert hook_name in str(lock_path)

    def test_session_id_uniqueness_across_processes(self):
        """Test that session IDs are unique across different processes (mocked)."""
        config1 = GlobalLockConfig()

        with unittest.mock.patch("os.getpid", return_value=12345):
            config2 = GlobalLockConfig()

            # Should have different PIDs in session ID
            assert config1.session_id != config2.session_id
            assert "12345" in config2.session_id

    def test_directory_permissions_on_existing_directory(self, tmp_path):
        """Test that permissions are set correctly on existing directories."""
        lock_dir = tmp_path / "existing_locks"
        lock_dir.mkdir(mode=0o755)  # Create with different permissions

        # Initialize config with existing directory
        GlobalLockConfig(lock_directory=lock_dir)

        # Permissions should be updated to 0o700
        stat_result = lock_dir.stat()
        permissions = stat_result.st_mode & 0o777
        assert permissions == 0o700

    def test_post_init_creates_nested_directories(self, tmp_path):
        """Test that __post_init__ creates nested directory structure."""
        nested_dir = tmp_path / "level1" / "level2" / "locks"

        GlobalLockConfig(lock_directory=nested_dir)

        # All nested directories should be created
        assert nested_dir.exists()
        assert nested_dir.parent.exists()
        assert nested_dir.parent.parent.exists()

        # Final directory should have correct permissions
        stat_result = nested_dir.stat()
        permissions = stat_result.st_mode & 0o777
        assert permissions == 0o700


class TestGlobalLockConfigEdgeCases:
    """Test edge cases and error conditions for GlobalLockConfig."""

    def test_lock_directory_with_pathlib_path(self, tmp_path):
        """Test configuration with pathlib.Path object."""
        lock_dir_path = tmp_path / "pathlib_locks"

        config = GlobalLockConfig(lock_directory=lock_dir_path)

        assert config.lock_directory == lock_dir_path
        assert lock_dir_path.exists()

    def test_zero_timeout_configuration(self):
        """Test configuration with edge case timeout values."""
        config = GlobalLockConfig(
            timeout_seconds=0.0, stale_lock_hours=0.0, session_heartbeat_interval=0.1
        )

        assert config.timeout_seconds == 0.0
        assert config.stale_lock_hours == 0.0
        assert config.session_heartbeat_interval == 0.1

    def test_very_long_hook_names(self, tmp_path):
        """Test lock path generation with very long hook names."""
        lock_dir = tmp_path / "locks"
        config = GlobalLockConfig(lock_directory=lock_dir)

        # Test with very long hook name
        long_hook_name = "very_long_hook_name_" * 10  # 200+ characters
        lock_path = config.get_lock_path(long_hook_name)

        # Should still generate valid path
        assert lock_path.parent == lock_dir
        assert lock_path.suffix == ".lock"

    @pytest.mark.parametrize("invalid_timeout", [-1, -10.5])
    def test_negative_timeout_handling(self, invalid_timeout):
        """Test behavior with negative timeout values."""
        # Configuration should accept negative values (validation may be elsewhere)
        config = GlobalLockConfig(timeout_seconds=invalid_timeout)
        assert config.timeout_seconds == invalid_timeout

    def test_from_options_with_missing_attributes(self):
        """Test from_options() with incomplete options object."""
        # Mock options with missing attributes
        mock_options = unittest.mock.Mock()
        mock_options.disable_global_locks = False
        mock_options.global_lock_timeout = 300
        # Missing global_lock_dir attribute
        del mock_options.global_lock_dir

        # Should handle missing attributes gracefully
        config = GlobalLockConfig.from_options(mock_options)

        assert config.enabled is True
        assert config.timeout_seconds == 300.0
        # Should fall back to default directory
        assert config.lock_directory == Path.home() / ".crackerjack" / "locks"

    def test_file_permission_errors_handling(self, tmp_path, monkeypatch):
        """Test handling of file permission errors during directory creation."""
        # This test simulates permission errors that might occur in real scenarios
        lock_dir = tmp_path / "permission_denied"

        # Mock mkdir to raise PermissionError
        original_mkdir = Path.mkdir

        def mock_mkdir(self, *args, **kwargs):
            if self == lock_dir:
                raise PermissionError("Permission denied")
            return original_mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        # Should raise the permission error
        with pytest.raises(PermissionError, match="Permission denied"):
            GlobalLockConfig(lock_directory=lock_dir)


class TestGlobalLockConfigIntegration:
    """Integration tests for GlobalLockConfig with real filesystem operations."""

    def test_real_filesystem_integration(self):
        """Test with real filesystem in temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_dir = Path(temp_dir) / "integration_locks"
            config = GlobalLockConfig(lock_directory=lock_dir)

            # Test full workflow
            assert lock_dir.exists()

            # Test lock file creation
            hook_name = "integration_test_hook"
            lock_path = config.get_lock_path(hook_name)

            # Create lock file
            lock_data = {"test": "integration", "session": config.session_id}
            import json

            lock_path.write_text(json.dumps(lock_data))

            # Verify file is valid
            assert config.is_valid_lock_file(lock_path)

            # Test heartbeat file
            heartbeat_path = config.get_heartbeat_path(hook_name)
            heartbeat_path.write_text("heartbeat data")

            assert heartbeat_path.exists()

    def test_concurrent_config_creation(self):
        """Test multiple GlobalLockConfig instances created concurrently."""
        import threading

        results = []

        def create_config(index):
            with tempfile.TemporaryDirectory() as temp_dir:
                lock_dir = Path(temp_dir) / f"concurrent_locks_{index}"
                config = GlobalLockConfig(lock_directory=lock_dir)
                results.append(
                    {
                        "index": index,
                        "session_id": config.session_id,
                        "directory": str(config.lock_directory),
                        "exists": lock_dir.exists(),
                    }
                )

        # Create multiple configs concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_config, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all configs were created successfully
        assert len(results) == 5

        # All should have unique session IDs (same PID, same hostname, but different instances)
        session_ids = [r["session_id"] for r in results]
        assert len(set(session_ids)) == 1  # Same process, so same session ID

        # All directories should exist
        assert all(r["exists"] for r in results)
