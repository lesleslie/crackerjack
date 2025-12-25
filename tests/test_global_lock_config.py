"""Tests for GlobalLockConfig class.

Tests cover:
- Directory creation
- Lock file path generation
- Configuration property access
- Parameter API compatibility
"""

import tempfile
from pathlib import Path

import pytest

from crackerjack.config.global_lock_config import GlobalLockConfig


class TestGlobalLockConfig:
    """Test GlobalLockConfig functionality."""

    def test_default_initialization(self):
        """Test default configuration values."""
        config = GlobalLockConfig()

        assert config.enabled is True
        assert config.timeout_seconds == 1800.0
        assert config.stale_lock_hours == 2.0
        assert config.session_heartbeat_interval == 30.0
        assert config.max_retry_attempts == 3
        assert config.retry_delay_seconds == 5.0
        assert config.enable_lock_monitoring is True

        # Default lock directory should be ~/.crackerjack/locks
        expected_dir = Path.home() / ".crackerjack" / "locks"
        assert config.lock_directory == expected_dir

    def test_lock_directory_creation(self, tmp_path):
        """Test that lock directory is created."""
        lock_dir = tmp_path / "custom_locks"

        config = GlobalLockConfig(lock_directory=lock_dir)

        # Directory should be created
        assert lock_dir.exists()
        assert lock_dir.is_dir()

    def test_hostname_property(self):
        """Test hostname property returns current system hostname."""
        import socket

        config = GlobalLockConfig()
        expected_hostname = socket.gethostname()
        assert config.hostname == expected_hostname

    def test_session_id_generation(self):
        """Test session ID generation creates a unique ID."""
        config = GlobalLockConfig()

        # Session ID should be a non-empty string
        assert isinstance(config.session_id, str)
        assert len(config.session_id) > 0

        # Should be deterministic for same instance
        assert config.session_id == config.session_id

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

    def test_configuration_validation_types(self):
        """Test configuration with various data types."""
        # Test with valid types using backwards compatibility API
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

        # Test hook names with various characters (should sanitize / to _)
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

    def test_lock_path_sanitizes_slashes(self, tmp_path):
        """Test that lock path generation sanitizes forward slashes."""
        lock_dir = tmp_path / "locks"
        config = GlobalLockConfig(lock_directory=lock_dir)

        hook_name = "hook/with/slashes"
        lock_path = config.get_lock_path(hook_name)

        # Slashes should be converted to underscores
        expected_path = lock_dir / "hook_with_slashes.lock"
        assert lock_path == expected_path

    def test_nested_directories_creation(self, tmp_path):
        """Test that nested directory structure is created."""
        nested_dir = tmp_path / "level1" / "level2" / "locks"

        config = GlobalLockConfig(lock_directory=nested_dir)

        # All nested directories should be created
        assert nested_dir.exists()
        assert nested_dir.parent.exists()
        assert nested_dir.parent.parent.exists()


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

            # Verify file exists and is readable
            assert lock_path.exists()
            assert lock_path.read_text() == json.dumps(lock_data)

    def test_multiple_sequential_config_creation(self, tmp_path):
        """Test multiple GlobalLockConfig instances created sequentially."""
        results = []

        for i in range(5):
            lock_dir = tmp_path / f"locks_{i}"
            config = GlobalLockConfig(lock_directory=lock_dir)
            results.append(
                {
                    "index": i,
                    "session_id": config.session_id,
                    "directory": str(config.lock_directory),
                    "exists": lock_dir.exists(),
                }
            )

        # Verify all configs were created successfully
        assert len(results) == 5

        # Each instance gets a unique session ID
        session_ids = [r["session_id"] for r in results]
        assert len(set(session_ids)) == 5  # Each instance is unique

        # All session IDs should be non-empty strings
        assert all(isinstance(sid, str) and len(sid) > 0 for sid in session_ids)

        # All directories should exist
        assert all(r["exists"] for r in results)
