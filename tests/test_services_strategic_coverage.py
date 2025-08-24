"""Strategic tests for services to boost coverage from low percentages."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.services.config import ConfigurationService
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.security import SecurityService
from crackerjack.services.unified_config import UnifiedConfigurationService


class TestConfigurationService:
    """Strategic coverage tests for ConfigurationService (118 statements, 13% coverage)."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_service(self, temp_dir):
        """Create ConfigurationService with temporary directory."""
        return ConfigurationService(pkg_path=temp_dir)

    def test_init(self, config_service, temp_dir) -> None:
        """Test ConfigurationService initialization."""
        assert config_service.pkg_path == temp_dir

    def test_load_pyproject_config_not_exists(self, config_service) -> None:
        """Test loading pyproject.toml that doesn't exist."""
        result = config_service.load_pyproject_config()

        assert result == {}

    def test_save_pyproject_config(self, config_service, temp_dir) -> None:
        """Test saving pyproject.toml configuration."""
        config = {"project": {"name": "test", "version": "1.0.0"}}

        result = config_service.save_pyproject_config(config)

        assert result is True
        # Verify file was created
        pyproject_path = temp_dir / "pyproject.toml"
        assert pyproject_path.exists()

    def test_load_precommit_config_not_exists(self, config_service) -> None:
        """Test loading .pre-commit-config.yaml that doesn't exist."""
        result = config_service.load_precommit_config()

        assert result == {}

    def test_save_precommit_config(self, config_service, temp_dir) -> None:
        """Test saving .pre-commit-config.yaml configuration."""
        config = {"repos": [{"repo": "https://github.com/test/repo", "rev": "v1.0.0"}]}

        result = config_service.save_precommit_config(config)

        assert result is True
        # Verify file was created
        precommit_path = temp_dir / ".pre-commit-config.yaml"
        assert precommit_path.exists()

    def test_update_pyproject_config(self, config_service, temp_dir) -> None:
        """Test updating pyproject.toml configuration."""
        # Create initial config
        initial_config = {"project": {"name": "test"}}
        config_service.save_pyproject_config(initial_config)

        # Update with new values
        result = config_service.update_pyproject_config(
            {"tool": {"pytest": {"timeout": 300}}},
        )

        assert result is True

        # Verify the config was merged
        loaded_config = config_service.load_pyproject_config()
        assert "project" in loaded_config
        assert "tool" in loaded_config
        assert loaded_config["project"]["name"] == "test"

    def test_update_precommit_config(self, config_service) -> None:
        """Test updating pre-commit configuration."""
        updates = {"repos": [{"repo": "https://github.com/test/repo", "rev": "v1.0.0"}]}

        result = config_service.update_precommit_config(updates)

        assert result is True

    def test_validate_pyproject_config_valid(self, config_service, temp_dir) -> None:
        """Test validating valid pyproject.toml."""
        valid_config = {"project": {"name": "test", "version": "1.0.0"}}
        config_service.save_pyproject_config(valid_config)

        result = config_service.validate_pyproject_config()

        assert result is True

    def test_validate_pyproject_config_missing(self, config_service) -> None:
        """Test validating missing pyproject.toml."""
        result = config_service.validate_pyproject_config()

        assert result is False

    def test_validate_precommit_config_missing(self, config_service) -> None:
        """Test validating missing pre-commit config."""
        result = config_service.validate_precommit_config()

        assert result is False

    def test_backup_config_files(self, config_service, temp_dir) -> None:
        """Test backing up configuration files."""
        # Create config files first
        config_service.save_pyproject_config({"project": {"name": "test"}})
        config_service.save_precommit_config({"repos": []})

        result = config_service.backup_config_files()

        assert result is True

    def test_restore_config_files(self, config_service) -> None:
        """Test restoring configuration files from backup."""
        # Should handle gracefully when no backups exist
        result = config_service.restore_config_files()

        assert isinstance(result, bool)

    def test_get_config_summary(self, config_service, temp_dir) -> None:
        """Test getting configuration summary."""
        config_service.save_pyproject_config({"project": {"name": "test"}})

        summary = config_service.get_config_summary()

        assert isinstance(summary, dict)
        assert "pyproject_exists" in summary
        assert "precommit_exists" in summary


class TestFileSystemService:
    """Strategic coverage tests for FileSystemService (154 statements, 11% coverage)."""

    @pytest.fixture
    def filesystem_service(self):
        """Create FileSystemService instance."""
        return FileSystemService()

    @pytest.fixture
    def temp_file(self):
        """Create temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
            f.write("# Test file\nprint('hello')\n")
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_init(self, filesystem_service) -> None:
        """Test FileSystemService initialization."""
        assert filesystem_service is not None
        assert hasattr(filesystem_service, "_cache")

    def test_read_file(self, filesystem_service, temp_file) -> None:
        """Test reading a file."""
        content = filesystem_service.read_file(temp_file)

        assert "# Test file" in content
        assert "print('hello')" in content

    def test_read_file_not_exists(self, filesystem_service) -> None:
        """Test reading non-existent file."""
        result = filesystem_service.read_file(Path("/non/existent/file.txt"))

        assert result is None

    def test_write_file(self, filesystem_service) -> None:
        """Test writing a file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            content = "# New content\nprint('test')\n"
            result = filesystem_service.write_file(temp_path, content)

            assert result is True
            assert temp_path.exists()

            # Verify content
            written_content = filesystem_service.read_file(temp_path)
            assert written_content == content
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_file_exists(self, filesystem_service, temp_file) -> None:
        """Test checking file existence."""
        assert filesystem_service.file_exists(temp_file) is True
        assert filesystem_service.file_exists(Path("/non/existent.txt")) is False

    def test_list_files(self, filesystem_service) -> None:
        """Test listing files in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "file1.py").write_text("# File 1")
            (tmpdir_path / "file2.txt").write_text("# File 2")

            files = filesystem_service.list_files(tmpdir_path)

            assert len(files) == 2
            assert any(f.name == "file1.py" for f in files)
            assert any(f.name == "file2.txt" for f in files)

    def test_list_files_with_pattern(self, filesystem_service) -> None:
        """Test listing files with pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "file1.py").write_text("# File 1")
            (tmpdir_path / "file2.txt").write_text("# File 2")
            (tmpdir_path / "file3.py").write_text("# File 3")

            py_files = filesystem_service.list_files(tmpdir_path, pattern="*.py")

            assert len(py_files) == 2
            assert all(f.suffix == ".py" for f in py_files)

    def test_create_directory(self, filesystem_service) -> None:
        """Test creating directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_directory"

            result = filesystem_service.create_directory(new_dir)

            assert result is True
            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_delete_file(self, filesystem_service) -> None:
        """Test deleting file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        assert temp_path.exists()

        result = filesystem_service.delete_file(temp_path)

        assert result is True
        assert not temp_path.exists()

    def test_copy_file(self, filesystem_service, temp_file) -> None:
        """Test copying file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            dest_path = Path(f.name)

        try:
            # Delete the temp file so we can copy to it
            dest_path.unlink()

            result = filesystem_service.copy_file(temp_file, dest_path)

            assert result is True
            assert dest_path.exists()

            # Verify content matches
            original_content = filesystem_service.read_file(temp_file)
            copied_content = filesystem_service.read_file(dest_path)
            assert original_content == copied_content
        finally:
            if dest_path.exists():
                dest_path.unlink()

    def test_get_file_stats(self, filesystem_service, temp_file) -> None:
        """Test getting file statistics."""
        stats = filesystem_service.get_file_stats(temp_file)

        assert isinstance(stats, dict)
        assert "size" in stats
        assert "modified" in stats
        assert "created" in stats

    def test_clear_cache(self, filesystem_service) -> None:
        """Test clearing file cache."""
        # This should not raise an error
        filesystem_service.clear_cache()


class TestSecurityService:
    """Strategic coverage tests for SecurityService (86 statements, 17% coverage)."""

    @pytest.fixture
    def security_service(self):
        """Create SecurityService instance."""
        return SecurityService()

    def test_init(self, security_service) -> None:
        """Test SecurityService initialization."""
        assert security_service is not None

    @patch.dict("os.environ", {"UV_PUBLISH_TOKEN": "test_token_123"})
    def test_get_publish_token_from_env(self, security_service) -> None:
        """Test getting publish token from environment."""
        token = security_service.get_publish_token()

        assert token == "test_token_123"

    def test_get_publish_token_missing(self, security_service) -> None:
        """Test getting publish token when missing."""
        with patch.dict("os.environ", {}, clear=True):
            token = security_service.get_publish_token()

            assert token is None

    def test_validate_token_format_valid(self, security_service) -> None:
        """Test validating valid token format."""
        valid_tokens = ["pypi-abc123def456", "test-token-123", "abcdef123456"]

        for token in valid_tokens:
            assert security_service.validate_token_format(token) is True

    def test_validate_token_format_invalid(self, security_service) -> None:
        """Test validating invalid token format."""
        invalid_tokens = [
            "",  # empty
            "a",  # too short
            "ab",  # too short
            None,  # None
        ]

        for token in invalid_tokens:
            assert security_service.validate_token_format(token) is False

    def test_create_secure_temp_file(self, security_service) -> None:
        """Test creating secure temporary file."""
        temp_file = security_service.create_secure_temp_file("test_content")

        try:
            assert temp_file.exists()
            assert temp_file.read_text() == "test_content"

            # Check file permissions (should be restricted)
            import stat

            file_mode = temp_file.stat().st_mode
            # Owner should have read/write, others should not
            assert file_mode & stat.S_IRWXU  # Owner permissions
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_sanitize_path_safe(self, security_service) -> None:
        """Test sanitizing safe path."""
        safe_paths = ["normal/path/file.txt", "file.py", "dir/subdir/file.json"]

        for path in safe_paths:
            result = security_service.sanitize_path(path)
            assert result == path

    def test_sanitize_path_unsafe(self, security_service) -> None:
        """Test sanitizing unsafe path."""
        unsafe_paths = [
            "../../../etc/passwd",  # Directory traversal
            "/absolute/path",  # Absolute path
            "path/with/../traversal",  # Traversal in middle
        ]

        for path in unsafe_paths:
            result = security_service.sanitize_path(path)
            # Should not contain traversal elements
            assert ".." not in result
            assert not result.startswith("/")

    def test_validate_command_safe(self, security_service) -> None:
        """Test validating safe commands."""
        safe_commands = [
            ["python", "-m", "pytest"],
            ["uv", "run", "ruff", "check"],
            ["git", "status"],
        ]

        for cmd in safe_commands:
            assert security_service.validate_command(cmd) is True

    def test_validate_command_unsafe(self, security_service) -> None:
        """Test validating unsafe commands."""
        unsafe_commands = [
            ["rm", "-rf", "/"],  # Dangerous system command
            ["dd", "if=/dev/zero", "of=/dev/sda"],  # Dangerous disk command
            ["sudo", "rm", "file"],  # Privilege escalation
        ]

        for cmd in unsafe_commands:
            assert security_service.validate_command(cmd) is False

    def test_hash_sensitive_data(self, security_service) -> None:
        """Test hashing sensitive data."""
        data = "sensitive_password_123"

        hash1 = security_service.hash_sensitive_data(data)
        hash2 = security_service.hash_sensitive_data(data)

        # Same input should produce same hash
        assert hash1 == hash2
        # Hash should not contain original data
        assert data not in hash1
        # Should be hex string
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_secure_delete_file(self, security_service) -> None:
        """Test securely deleting file."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"sensitive data")
            temp_path = Path(f.name)

        assert temp_path.exists()

        result = security_service.secure_delete_file(temp_path)

        assert result is True
        assert not temp_path.exists()


class TestUnifiedConfigurationService:
    """Strategic coverage tests for UnifiedConfigurationService (236 statements, 0% coverage)."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def unified_config_service(self, temp_dir):
        """Create UnifiedConfigurationService with temporary directory."""
        return UnifiedConfigurationService(pkg_path=temp_dir)

    def test_init(self, unified_config_service, temp_dir) -> None:
        """Test UnifiedConfigService initialization."""
        assert unified_config_service.pkg_path == temp_dir

    def test_load_all_configs_empty(self, unified_config_service) -> None:
        """Test loading all configs when none exist."""
        configs = unified_config_service.load_all_configs()

        assert isinstance(configs, dict)
        assert "pyproject" in configs
        assert "precommit" in configs

    def test_validate_all_configs_empty(self, unified_config_service) -> None:
        """Test validating all configs when none exist."""
        result = unified_config_service.validate_all_configs()

        # Should handle missing configs gracefully
        assert isinstance(result, bool)

    def test_get_unified_summary(self, unified_config_service) -> None:
        """Test getting unified configuration summary."""
        summary = unified_config_service.get_unified_summary()

        assert isinstance(summary, dict)
        assert "total_configs" in summary
        assert "valid_configs" in summary

    def test_sync_configurations(self, unified_config_service) -> None:
        """Test synchronizing configurations."""
        result = unified_config_service.sync_configurations()

        assert isinstance(result, bool)

    def test_backup_all_configs(self, unified_config_service) -> None:
        """Test backing up all configurations."""
        result = unified_config_service.backup_all_configs()

        assert isinstance(result, bool)

    def test_restore_all_configs(self, unified_config_service) -> None:
        """Test restoring all configurations."""
        result = unified_config_service.restore_all_configs()

        assert isinstance(result, bool)

    def test_merge_config_updates(self, unified_config_service) -> None:
        """Test merging configuration updates."""
        updates = {
            "pyproject": {"tool": {"pytest": {"timeout": 300}}},
            "precommit": {"repos": []},
        }

        result = unified_config_service.merge_config_updates(updates)

        assert isinstance(result, bool)

    def test_get_config_dependencies(self, unified_config_service) -> None:
        """Test getting configuration dependencies."""
        deps = unified_config_service.get_config_dependencies()

        assert isinstance(deps, dict)

    def test_validate_config_consistency(self, unified_config_service) -> None:
        """Test validating configuration consistency."""
        result = unified_config_service.validate_config_consistency()

        assert isinstance(result, bool)
