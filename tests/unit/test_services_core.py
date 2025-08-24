"""Unit tests for core services - targeting high-impact, low-coverage modules.

Focus on services critical for 42% coverage target:
- FileSystemService
- GitService
- ConfigurationService
- DebugService
- SecurityService
"""

from unittest.mock import Mock, patch

import pytest

from crackerjack.services.config import ConfigurationService
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService
from crackerjack.services.metrics import MetricsCollector
from crackerjack.services.security import SecurityService


@pytest.mark.unit
class TestFileSystemService:
    """Test filesystem service operations."""

    def test_init(self) -> None:
        """Test FileSystemService initialization."""
        fs = FileSystemService()
        assert fs is not None

    def test_read_file_exists(self, temp_dir) -> None:
        """Test reading an existing file."""
        test_file = temp_dir / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)

        fs = FileSystemService()
        content = fs.read_file(str(test_file))
        assert content == test_content

    def test_read_file_not_exists(self, temp_dir) -> None:
        """Test reading non-existent file."""
        fs = FileSystemService()
        non_existent = temp_dir / "does_not_exist.txt"

        with pytest.raises(FileNotFoundError):
            fs.read_file(str(non_existent))

    def test_write_file(self, temp_dir) -> None:
        """Test writing file."""
        fs = FileSystemService()
        test_file = temp_dir / "write_test.txt"
        content = "Test content"

        fs.write_file(str(test_file), content)

        assert test_file.exists()
        assert test_file.read_text() == content

    def test_file_exists_true(self, temp_dir) -> None:
        """Test file_exists for existing file."""
        fs = FileSystemService()
        test_file = temp_dir / "exists.txt"
        test_file.write_text("content")

        assert fs.file_exists(str(test_file)) is True

    def test_file_exists_false(self, temp_dir) -> None:
        """Test file_exists for non-existent file."""
        fs = FileSystemService()
        non_existent = temp_dir / "does_not_exist.txt"

        assert fs.file_exists(str(non_existent)) is False

    def test_create_directory(self, temp_dir) -> None:
        """Test directory creation."""
        fs = FileSystemService()
        new_dir = temp_dir / "new_directory"

        fs.create_directory(str(new_dir))

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_create_directory_nested(self, temp_dir) -> None:
        """Test nested directory creation."""
        fs = FileSystemService()
        nested_dir = temp_dir / "level1" / "level2" / "level3"

        fs.create_directory(str(nested_dir))

        assert nested_dir.exists()
        assert nested_dir.is_dir()


@pytest.mark.unit
class TestGitService:
    """Test git service operations."""

    def test_init(self) -> None:
        """Test GitService initialization."""
        git = GitService()
        assert git is not None

    @patch("subprocess.run")
    def test_is_git_repo_true(self, mock_run) -> None:
        """Test is_git_repo returns True for git repository."""
        mock_run.return_value = Mock(returncode=0)

        git = GitService()
        result = git.is_git_repo()

        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_is_git_repo_false(self, mock_run) -> None:
        """Test is_git_repo returns False for non-git directory."""
        mock_run.return_value = Mock(returncode=128)

        git = GitService()
        result = git.is_git_repo()

        assert result is False

    @patch("subprocess.run")
    def test_get_current_branch(self, mock_run) -> None:
        """Test getting current git branch."""
        mock_run.return_value = Mock(returncode=0, stdout=b"main\n")

        git = GitService()
        branch = git.get_current_branch()

        assert branch == "main"

    @patch("subprocess.run")
    def test_has_uncommitted_changes_true(self, mock_run) -> None:
        """Test detecting uncommitted changes."""
        mock_run.return_value = Mock(returncode=0, stdout=b"M file.py\n")

        git = GitService()
        has_changes = git.has_uncommitted_changes()

        assert has_changes is True

    @patch("subprocess.run")
    def test_has_uncommitted_changes_false(self, mock_run) -> None:
        """Test clean working directory."""
        mock_run.return_value = Mock(returncode=0, stdout=b"")

        git = GitService()
        has_changes = git.has_uncommitted_changes()

        assert has_changes is False

    @patch("subprocess.run")
    def test_create_commit(self, mock_run) -> None:
        """Test creating git commit."""
        mock_run.return_value = Mock(returncode=0)

        git = GitService()
        git.create_commit("Test commit message")

        mock_run.assert_called()

    @patch("subprocess.run")
    def test_push_to_remote(self, mock_run) -> None:
        """Test pushing to remote repository."""
        mock_run.return_value = Mock(returncode=0)

        git = GitService()
        git.push_to_remote("origin", "main")

        mock_run.assert_called()


@pytest.mark.unit
class TestConfigurationService:
    """Test configuration service."""

    def test_init(self) -> None:
        """Test ConfigurationService initialization."""
        config = ConfigurationService()
        assert config is not None

    def test_load_config_from_file(self, temp_dir) -> None:
        """Test loading configuration from file."""
        config_file = temp_dir / "pyproject.toml"
        config_content = """
[tool.crackerjack]
test_timeout = 120
test_workers = 4
        """.strip()
        config_file.write_text(config_content)

        config_service = ConfigurationService()
        loaded_config = config_service.load_config_from_file(str(config_file))

        assert loaded_config is not None

    def test_save_config_to_file(self, temp_dir) -> None:
        """Test saving configuration to file."""
        config_file = temp_dir / "test_config.toml"

        config_service = ConfigurationService()
        test_config = {"test_timeout": 60, "test_workers": 2}

        config_service.save_config_to_file(str(config_file), test_config)

        assert config_file.exists()

    def test_merge_configs(self) -> None:
        """Test merging configuration dictionaries."""
        config_service = ConfigurationService()

        base_config = {"timeout": 60, "workers": 2, "verbose": False}
        override_config = {"timeout": 120, "debug": True}

        merged = config_service.merge_configs(base_config, override_config)

        assert merged["timeout"] == 120  # Overridden
        assert merged["workers"] == 2  # From base
        assert merged["verbose"] is False  # From base
        assert merged["debug"] is True  # From override


@pytest.mark.unit
class TestDebugService:
    """Test debug service."""

    def test_init(self) -> None:
        """Test DebugService initialization."""
        debug = DebugService()
        assert debug is not None

    def test_log_debug_message(self) -> None:
        """Test logging debug message."""
        debug = DebugService()

        # Should not raise exception
        debug.log_debug("Test debug message")

    def test_log_error_message(self) -> None:
        """Test logging error message."""
        debug = DebugService()

        # Should not raise exception
        debug.log_error("Test error message")

    def test_log_info_message(self) -> None:
        """Test logging info message."""
        debug = DebugService()

        # Should not raise exception
        debug.log_info("Test info message")

    @patch("crackerjack.services.debug.Path.write_text")
    def test_write_debug_file(self, mock_write) -> None:
        """Test writing debug information to file."""
        debug = DebugService()

        debug.write_debug_file("debug_content", "test_session")

        mock_write.assert_called_once()

    def test_get_debug_info(self) -> None:
        """Test getting debug information."""
        debug = DebugService()

        debug_info = debug.get_debug_info()

        assert isinstance(debug_info, dict)
        assert "timestamp" in debug_info


@pytest.mark.unit
class TestSecurityService:
    """Test security service."""

    def test_init(self) -> None:
        """Test SecurityService initialization."""
        security = SecurityService()
        assert security is not None

    def test_sanitize_input_clean(self) -> None:
        """Test sanitizing clean input."""
        security = SecurityService()

        clean_input = "normal_text"
        result = security.sanitize_input(clean_input)

        assert result == clean_input

    def test_sanitize_input_malicious(self) -> None:
        """Test sanitizing malicious input."""
        security = SecurityService()

        malicious_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
        ]

        for malicious in malicious_inputs:
            result = security.sanitize_input(malicious)
            # Should be sanitized (implementation dependent)
            assert result != malicious or result == ""

    def test_validate_file_path_safe(self, temp_dir) -> None:
        """Test validating safe file path."""
        security = SecurityService()
        safe_path = str(temp_dir / "safe_file.txt")

        is_safe = security.validate_file_path(safe_path)

        assert is_safe is True

    def test_validate_file_path_unsafe(self) -> None:
        """Test validating unsafe file path."""
        security = SecurityService()

        unsafe_paths = [
            "../../../etc/passwd",
            "/etc/shadow",
            "~/.ssh/id_rsa",
        ]

        for unsafe_path in unsafe_paths:
            is_safe = security.validate_file_path(unsafe_path)
            assert is_safe is False

    def test_check_permissions(self, temp_dir) -> None:
        """Test checking file permissions."""
        security = SecurityService()
        test_file = temp_dir / "test_file.txt"
        test_file.write_text("content")

        has_permission = security.check_permissions(str(test_file), "read")

        # Should be able to read file we just created
        assert has_permission is True


@pytest.mark.unit
class TestMetricsCollector:
    """Test metrics service."""

    def test_init(self) -> None:
        """Test MetricsCollector initialization."""
        metrics = MetricsCollector()
        assert metrics is not None

    def test_record_metric(self) -> None:
        """Test recording a metric."""
        metrics = MetricsCollector()

        metrics.record_metric("test_metric", 42.0)

        # Should not raise exception
        assert True

    def test_get_metrics(self) -> None:
        """Test getting recorded metrics."""
        metrics = MetricsCollector()

        metrics.record_metric("metric1", 10.0)
        metrics.record_metric("metric2", 20.0)

        all_metrics = metrics.get_metrics()

        assert isinstance(all_metrics, dict)

    def test_clear_metrics(self) -> None:
        """Test clearing metrics."""
        metrics = MetricsCollector()

        metrics.record_metric("test_metric", 42.0)
        metrics.clear_metrics()

        all_metrics = metrics.get_metrics()
        assert len(all_metrics) == 0 or "test_metric" not in all_metrics

    def test_get_metric_summary(self) -> None:
        """Test getting metric summary."""
        metrics = MetricsCollector()

        # Record multiple values for same metric
        for i in range(5):
            metrics.record_metric("response_time", float(i * 10))

        summary = metrics.get_metric_summary("response_time")

        assert isinstance(summary, dict)
        # Should contain statistical information
        assert "count" in summary or "total" in summary
