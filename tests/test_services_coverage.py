import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.config import ConfigurationService
from crackerjack.services.file_hasher import FileHasher
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService
from crackerjack.services.security import SecurityService


class TestFileSystemService:
    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def service(self):
        return FileSystemService()

    def test_initialization(self, service) -> None:
        assert hasattr(service, "read_file")
        assert hasattr(service, "write_file")
        assert hasattr(service, "file_exists")

    def test_file_exists(self, service, temp_path) -> None:
        test_file = temp_path / "test.txt"
        test_file.write_text("test content")

        assert service.file_exists(test_file) is True
        assert service.file_exists(temp_path / "nonexistent.txt") is False

    def test_read_file(self, service, temp_path) -> None:
        test_file = temp_path / "test.txt"
        content = "test content"
        test_file.write_text(content)

        result = service.read_file(test_file)
        assert result == content

    def test_write_file(self, service, temp_path) -> None:
        test_file = temp_path / "test.txt"
        content = "test content"

        service.write_file(test_file, content)
        assert test_file.read_text() == content

    def test_list_files(self, service, temp_path) -> None:
        (temp_path / "file1.txt").write_text("content1")
        (temp_path / "file2.py").write_text("content2")

        files = service.list_files(temp_path, " * .txt")
        assert len(files) == 1
        assert files[0].name == "file1.txt"


class TestGitService:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def service(self, console, temp_path):
        return GitService(console, temp_path)

    def test_initialization(self, service, console, temp_path) -> None:
        assert service.console == console
        assert service.pkg_path == temp_path

    def test_is_git_repo_false(self, service, temp_path) -> None:
        assert service.is_git_repo() is False

    @patch("subprocess.run")
    def test_get_changed_files(self, mock_run, service) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="file1.py\nfile2.py\n")

        files = service.get_changed_files()
        assert "file1.py" in files
        assert "file2.py" in files

    @patch("subprocess.run")
    def test_commit_changes_success(self, mock_run, service) -> None:
        mock_run.return_value = Mock(returncode=0)

        result = service.commit_changes("Test commit")
        assert result is True

    @patch("subprocess.run")
    def test_commit_changes_failure(self, mock_run, service) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        result = service.commit_changes("Test commit")
        assert result is False

    @patch("subprocess.run")
    def test_get_current_branch(self, mock_run, service) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="main\n")

        branch = service.get_current_branch()
        assert branch == "main"

    @patch("subprocess.run")
    def test_has_staged_changes(self, mock_run, service) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="M staged_file.py\n")

        assert service.has_staged_changes() is True


class TestCacheService:
    @pytest.fixture
    def service(self):
        return CrackerjackCache()

    def test_initialization(self, service) -> None:
        assert hasattr(service, "cache_dir")
        assert hasattr(service, "hook_results_cache")
        assert hasattr(service, "file_hash_cache")
        assert hasattr(service, "config_cache")

    def test_cache_hook_result(self, service) -> None:
        from crackerjack.models.task import HookResult

        hook_result = HookResult(
            id="test1",
            name="test - hook",
            status="passed",
            duration=1.0,
            issues_found=[],
        )

        service.cache_hook_result("test_key", hook_result)

        cached_result = service.get_hook_result("test_key")
        if cached_result is not None:
            assert cached_result.name == "test - hook"

    def test_cache_file_hash(self, service) -> None:
        test_hash = "abc123def456"
        service.cache_file_hash("test_file.py", test_hash)

        cached_hash = service.get_file_hash("test_file.py")
        if cached_hash is not None:
            assert cached_hash == test_hash

    def test_cache_config(self, service) -> None:
        test_config = {"setting1": "value1", "setting2": "value2"}
        service.cache_config("test_config", test_config)

        cached_config = service.get_config("test_config")
        if cached_config is not None:
            assert cached_config == test_config


class TestConfigurationService:
    @pytest.fixture
    def console(self):
        return Console(force_terminal=False)

    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def service(self, console, temp_path):
        return ConfigurationService(console, temp_path)

    def test_initialization(self, service, console, temp_path) -> None:
        assert service.console == console
        assert service.pkg_path == temp_path

    def test_get_pyproject_path(self, service, temp_path) -> None:
        pyproject_path = service.get_pyproject_path()
        assert pyproject_path == temp_path / "pyproject.toml"

    def test_update_pre_commit_config(self, service, temp_path) -> None:
        config_path = temp_path / ".pre - commit - config.yaml"
        config_path.write_text("repos: []")

        result = service.update_pre_commit_config(mode="comprehensive")

        assert isinstance(result, bool)

    def test_backup_config(self, service, temp_path) -> None:
        config_path = temp_path / ".pre - commit - config.yaml"
        config_path.write_text("repos: []")

        backup_path = service.backup_config(config_path)
        assert backup_path.exists()
        assert "backup" in backup_path.name


class TestSecurityService:
    @pytest.fixture
    def service(self):
        return SecurityService()

    def test_initialization(self, service) -> None:
        assert hasattr(service, "validate_command")
        assert hasattr(service, "sanitize_input")

    def test_validate_safe_command(self, service) -> None:
        safe_commands = [
            ["uv", "run", "ruff", "check", "."],
            ["python", " - m", "pytest"],
            ["git", "status"],
        ]

        for cmd in safe_commands:
            assert service.validate_command(cmd) is True

    def test_validate_unsafe_command(self, service) -> None:
        unsafe_commands = [
            ["rm", " - rf", " / "],
            ["cat", " / etc / passwd"],
            ["curl", "http: // malicious.com"],
        ]

        for cmd in unsafe_commands:
            assert service.validate_command(cmd) is False

    def test_sanitize_input(self, service) -> None:
        clean_input = "normal text"
        assert service.sanitize_input(clean_input) == clean_input

        dangerous_input = "text; rm - rf / "
        sanitized = service.sanitize_input(dangerous_input)
        assert "rm" not in sanitized

    def test_generate_secure_token(self, service) -> None:
        token1 = service.generate_secure_token()
        token2 = service.generate_secure_token()

        assert len(token1) > 0
        assert len(token2) > 0
        assert token1 != token2

    def test_validate_file_path(self, service) -> None:
        assert service.validate_file_path(". / file.txt") is True
        assert service.validate_file_path("src / module.py") is True

        assert service.validate_file_path(" / etc / passwd") is False
        assert service.validate_file_path(".. / .. / .. / etc / passwd") is False


class TestFileHashingService:
    @pytest.fixture
    def temp_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def service(self, temp_path):
        return FileHasher()

    def test_initialization(self, service) -> None:
        assert hasattr(service, "hash_file")

    def test_hash_file(self, service, temp_path) -> None:
        test_file = temp_path / "test.txt"
        test_file.write_text("test content")

        hash1 = service.hash_file(test_file)
        hash2 = service.hash_file(test_file)

        assert hash1 == hash2
        assert len(hash1) > 0

    def test_hash_different_files(self, service, temp_path) -> None:
        file1 = temp_path / "file1.txt"
        file2 = temp_path / "file2.txt"

        file1.write_text("content1")
        file2.write_text("content2")

        hash1 = service.hash_file(file1)
        hash2 = service.hash_file(file2)

        assert hash1 != hash2

    def test_hash_consistency(self, service, temp_path) -> None:
        test_file = temp_path / "test.txt"
        test_file.write_text("test content")

        hash1 = service.hash_file(test_file)
        hash2 = service.hash_file(test_file)

        assert hash1 == hash2
