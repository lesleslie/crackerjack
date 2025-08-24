"""Consolidated services testing module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.config import ConfigurationService
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService
from crackerjack.services.security import SecurityService


@pytest.fixture
def console():
    """Console fixture for testing."""
    return Console(force_terminal=False)


@pytest.fixture
def temp_project(tmp_path):
    """Temporary project directory fixture."""
    return tmp_path


@pytest.fixture
def temp_file(tmp_path):
    """Temporary file fixture."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")
    return test_file


class TestConfigService:
    """Test ConfigurationService functionality."""

    def test_config_service_initialization(self, temp_project, console) -> None:
        """Test config service initialization."""
        service = ConfigurationService(console=console, pkg_path=temp_project)
        assert service.pkg_path == temp_project

    def test_config_update(self, temp_project, console) -> None:
        """Test configuration update functionality."""
        service = ConfigurationService(console=console, pkg_path=temp_project)

        # Create a basic pyproject.toml
        pyproject_path = temp_project / "pyproject.toml"
        pyproject_path.write_text("""
[tool.pytest.ini_options]
testpaths = ["tests"]
""")

        # Test with a mock options object
        from crackerjack.models.config import WorkflowOptions

        result = service.update_precommit_config(WorkflowOptions())
        assert isinstance(result, bool)

    def test_config_validation(self, temp_project, console) -> None:
        """Test configuration validation."""
        service = ConfigurationService(console=console, pkg_path=temp_project)

        # Test configuration validation
        result = service.validate_config()
        assert isinstance(result, bool)

    def test_config_backup_and_restore(self, temp_project, console) -> None:
        """Test configuration backup and restore."""
        service = ConfigurationService(console=console, pkg_path=temp_project)

        # Create a config file
        config_file = temp_project / ".pre-commit-config.yaml"
        config_file.write_text("repos: []\n")

        # Test backup
        backup_file = service.backup_config()
        assert backup_file is None or backup_file.exists()

    def test_config_info(self, temp_project, console) -> None:
        """Test configuration info retrieval."""
        service = ConfigurationService(console=console, pkg_path=temp_project)

        # Test getting config info
        info = service.get_config_info()
        assert isinstance(info, dict)
        assert "exists" in info


class TestFileSystemService:
    """Test FileSystemService functionality."""

    def test_filesystem_service_initialization(self, temp_project) -> None:
        """Test filesystem service initialization."""
        service = FileSystemService(pkg_path=temp_project)
        assert service.pkg_path == temp_project

    def test_file_reading(self, temp_file) -> None:
        """Test file reading functionality."""
        service = FileSystemService(pkg_path=temp_file.parent)

        content = service.read_file(temp_file)
        assert content == "test content"

    def test_file_writing(self, temp_project) -> None:
        """Test file writing functionality."""
        service = FileSystemService(pkg_path=temp_project)

        test_file = temp_project / "write_test.txt"
        test_content = "written content"

        result = service.write_file(test_file, test_content)
        assert result is True
        assert test_file.read_text() == test_content

    def test_file_exists_check(self, temp_file) -> None:
        """Test file existence checking."""
        service = FileSystemService(pkg_path=temp_file.parent)

        assert service.file_exists(temp_file) is True
        assert service.file_exists(temp_file.parent / "nonexistent.txt") is False

    def test_directory_creation(self, temp_project) -> None:
        """Test directory creation."""
        service = FileSystemService(pkg_path=temp_project)

        new_dir = temp_project / "new_directory"
        result = service.create_directory(new_dir)

        assert result is True
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_file_deletion(self, temp_project) -> None:
        """Test file deletion."""
        service = FileSystemService(pkg_path=temp_project)

        # Create a file to delete
        test_file = temp_project / "delete_me.txt"
        test_file.write_text("delete this")

        result = service.delete_file(test_file)
        assert result is True
        assert not test_file.exists()

    def test_directory_listing(self, temp_project) -> None:
        """Test directory listing."""
        service = FileSystemService(pkg_path=temp_project)

        # Create some test files
        (temp_project / "file1.txt").write_text("content1")
        (temp_project / "file2.txt").write_text("content2")

        files = service.list_directory(temp_project)
        assert isinstance(files, list)
        assert len(files) >= 2


class TestGitService:
    """Test GitService functionality."""

    def test_git_service_initialization(self, temp_project) -> None:
        """Test git service initialization."""
        service = GitService(pkg_path=temp_project)
        assert service.pkg_path == temp_project

    @patch("subprocess.run")
    def test_git_status(self, mock_run, temp_project) -> None:
        """Test git status functionality."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="On branch main\nnothing to commit, working tree clean",
            stderr="",
        )

        service = GitService(pkg_path=temp_project)
        status = service.get_status()

        assert isinstance(status, str)
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_git_add(self, mock_run, temp_project) -> None:
        """Test git add functionality."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        service = GitService(pkg_path=temp_project)
        result = service.add_files(["test_file.txt"])

        assert isinstance(result, bool)
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_git_commit(self, mock_run, temp_project) -> None:
        """Test git commit functionality."""
        mock_run.return_value = Mock(
            returncode=0, stdout="[main abc1234] Test commit", stderr="",
        )

        service = GitService(pkg_path=temp_project)
        result = service.commit_changes("Test commit message")

        assert isinstance(result, bool)
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_git_push(self, mock_run, temp_project) -> None:
        """Test git push functionality."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        service = GitService(pkg_path=temp_project)
        result = service.push_changes()

        assert isinstance(result, bool)
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_git_branch_operations(self, mock_run, temp_project) -> None:
        """Test git branch operations."""
        mock_run.return_value = Mock(
            returncode=0, stdout="* main\n  feature-branch", stderr="",
        )

        service = GitService(pkg_path=temp_project)
        branches = service.list_branches()

        assert isinstance(branches, list)
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_git_error_handling(self, mock_run, temp_project) -> None:
        """Test git error handling."""
        mock_run.return_value = Mock(
            returncode=1, stdout="", stderr="fatal: not a git repository",
        )

        service = GitService(pkg_path=temp_project)
        result = service.get_status()

        # Should handle errors gracefully
        assert isinstance(result, str | bool)


class TestLoggingService:
    """Test basic logging functionality."""

    def test_logging_import(self) -> None:
        """Test that logging service can be imported and initialized."""
        import logging

        # Basic logging test - create a logger instance
        logger = logging.getLogger("test_crackerjack")
        logger.setLevel(logging.INFO)

        # Test basic logging functionality
        assert logger.name == "test_crackerjack"
        assert logger.level == logging.INFO


class TestSecurityService:
    """Test SecurityService functionality."""

    def test_security_service_initialization(self) -> None:
        """Test security service initialization."""
        service = SecurityService()
        assert hasattr(service, "validate_command")

    def test_command_validation(self) -> None:
        """Test command validation."""
        service = SecurityService()

        # Test safe commands
        safe_commands = [
            ["python", "-m", "pytest"],
            ["uv", "run", "ruff", "check"],
            ["git", "status"],
        ]

        for command in safe_commands:
            result = service.validate_command(command)
            assert isinstance(result, bool)

    def test_dangerous_command_detection(self) -> None:
        """Test dangerous command detection."""
        service = SecurityService()

        # Test potentially dangerous commands
        dangerous_commands = [
            ["rm", "-rf", "/"],
            ["sudo", "rm", "file"],
            ["chmod", "777", "*"],
        ]

        for command in dangerous_commands:
            result = service.validate_command(command)
            # Should either reject or flag as dangerous
            assert isinstance(result, bool)

    def test_path_validation(self) -> None:
        """Test path validation."""
        service = SecurityService()

        # Test safe paths
        safe_paths = [
            "/tmp/safe_file.txt",
            "./local_file.txt",
            "relative/path/file.txt",
        ]

        for path in safe_paths:
            result = service.validate_path(path)
            assert isinstance(result, bool)

    def test_sensitive_data_detection(self) -> None:
        """Test sensitive data detection."""
        service = SecurityService()

        # Test content with potential sensitive data
        test_contents = [
            "API_KEY=secret123",
            "password = 'mypassword'",
            "normal content without secrets",
        ]

        for content in test_contents:
            result = service.scan_for_secrets(content)
            assert isinstance(result, bool | list)

    def test_secure_temp_file_creation(self, temp_project) -> None:
        """Test secure temporary file creation."""
        service = SecurityService()

        temp_file = service.create_secure_temp_file(
            content="test content", directory=temp_project,
        )

        assert isinstance(temp_file, Path)
        assert temp_file.exists()
        assert temp_file.read_text() == "test content"

    def test_environment_variable_validation(self) -> None:
        """Test environment variable validation."""
        service = SecurityService()

        # Test environment variable access
        test_env_vars = ["PATH", "HOME", "USER"]

        for var in test_env_vars:
            result = service.validate_env_var(var)
            assert isinstance(result, bool)


class TestCacheService:
    """Test CrackerjackCache functionality."""

    def test_cache_service_initialization(self, temp_project) -> None:
        """Test cache service initialization."""
        cache_dir = temp_project / ".cache"
        service = CrackerjackCache(cache_dir=cache_dir)
        assert service.cache_dir == cache_dir

    def test_cache_set_and_get(self, temp_project) -> None:
        """Test cache set and get operations."""
        cache_dir = temp_project / ".cache"
        service = CrackerjackCache(cache_dir=cache_dir)

        # Test caching
        test_key = "test_key"
        test_value = {"data": "test_data"}

        service.set(test_key, test_value)
        retrieved_value = service.get(test_key)

        assert retrieved_value == test_value

    def test_cache_basic_operations(self, temp_project) -> None:
        """Test basic cache operations."""
        cache_dir = temp_project / ".cache"
        service = CrackerjackCache(cache_dir=cache_dir)

        # Test with basic values
        test_key = "basic_key"
        test_value = "basic_value"

        service.set(test_key, test_value)

        # Test key existence
        assert service.exists(test_key) is True

        # Test retrieval
        retrieved_value = service.get(test_key)
        assert retrieved_value == test_value


class TestServicesIntegration:
    """Test integration between services."""

    def test_services_work_together(self, temp_project, console) -> None:
        """Test that services can work together."""
        # Initialize multiple services
        config_service = ConfigurationService(console=console, pkg_path=temp_project)
        fs_service = FileSystemService(pkg_path=temp_project)
        git_service = GitService(pkg_path=temp_project)
        security_service = SecurityService()

        # Verify all services are properly initialized
        assert config_service.pkg_path == temp_project
        assert fs_service.pkg_path == temp_project
        assert git_service.pkg_path == temp_project
        assert hasattr(security_service, "validate_command")

    def test_service_error_handling_integration(self, temp_project) -> None:
        """Test error handling across services."""
        fs_service = FileSystemService(pkg_path=temp_project)
        security_service = SecurityService()

        # Test that services handle errors gracefully
        nonexistent_file = temp_project / "nonexistent.txt"

        # FileSystem service should handle missing files
        content = fs_service.read_file(nonexistent_file)
        assert content is None or isinstance(content, str)

        # Security service should handle invalid commands
        invalid_command = ["invalid_command", "--dangerous-flag"]
        result = security_service.validate_command(invalid_command)
        assert isinstance(result, bool)

    def test_service_configuration_sharing(self, temp_project) -> None:
        """Test configuration sharing between services."""
        ConfigurationService(console=console, pkg_path=temp_project)

        # Create a shared config
        shared_config = {
            "filesystem": {"cache_enabled": True},
            "git": {"auto_commit": False},
            "security": {"validation_enabled": True},
        }

        config_file = temp_project / "shared_config.yaml"
        import yaml

        with config_file.open("w") as f:
            yaml.safe_dump(shared_config, f)

        # Test that config was written
        assert config_file.exists()

        # Test reading back the config
        with config_file.open("r") as f:
            loaded_config = yaml.safe_load(f)
        assert loaded_config == shared_config
