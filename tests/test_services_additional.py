from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.errors import ConfigError, FileError
from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.config import ConfigurationService
from crackerjack.services.file_hasher import FileHasher
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService
from crackerjack.services.security import SecurityService


@pytest.fixture
def console():
    return Console()


@pytest.fixture
def pkg_path(tmp_path):
    return tmp_path


class TestGitService:
    @pytest.fixture
    def git_service(self, console, pkg_path):
        return GitService(console, pkg_path)

    def test_init(self, git_service, console, pkg_path) -> None:
        assert git_service.console == console
        assert git_service.pkg_path == pkg_path

    def test_is_git_repo_true(self, git_service) -> None:
        with patch.object(Path, "exists", return_value=True):
            assert git_service.is_git_repo() is True

    def test_is_git_repo_false(self, git_service) -> None:
        with patch.object(Path, "exists", return_value=False):
            assert git_service.is_git_repo() is False

    @patch("subprocess.run")
    def test_get_changed_files(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="file1.py\nfile2.py\n")

        files = git_service.get_changed_files()

        assert files == ["file1.py", "file2.py"]
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_changed_files_error(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=1)

        files = git_service.get_changed_files()

        assert files == []

    @patch("subprocess.run")
    def test_commit_success(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=0)

        result = git_service.commit("Test commit")

        assert result is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_commit_failure(self, mock_run, git_service) -> None:
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1),
        ]

        result = git_service.commit("Test commit")

        assert result is False

    @patch("subprocess.run")
    def test_push_success(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=0)

        result = git_service.push()

        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_add_files(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=0)

        result = git_service.add_files(["file1.py", "file2.py"])

        assert result is True
        mock_run.assert_called_once()


class TestFileSystemService:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    def test_init(self, fs_service) -> None:
        assert fs_service is not None
        assert hasattr(fs_service, "read_file")
        assert fs_service._file_cache == {}

    @patch("pathlib.Path.read_text")
    def test_read_file_success(self, mock_read, fs_service) -> None:
        mock_read.return_value = "file content"

        content = fs_service.read_file("test.py")

        assert content == "file content"
        mock_read.assert_called_once()

    @patch("pathlib.Path.read_text")
    def test_read_file_with_cache(self, mock_read, fs_service) -> None:
        mock_read.return_value = "file content"

        content1 = fs_service.read_file("test.py")

        content2 = fs_service.read_file("test.py")

        assert content1 == content2 == "file content"
        mock_read.assert_called_once()

    @patch("pathlib.Path.read_text")
    def test_read_file_error(self, mock_read, fs_service) -> None:
        mock_read.side_effect = FileNotFoundError()

        with pytest.raises(FileError):
            fs_service.read_file("nonexistent.py")

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.parent", new_callable=Mock)
    def test_write_file_success(self, mock_parent, mock_write, fs_service) -> None:
        mock_parent.mkdir = Mock()

        fs_service.write_file("test.py", "content")

        mock_write.assert_called_once_with("content", encoding="utf - 8")

    @patch("pathlib.Path.exists")
    def test_exists(self, mock_exists, fs_service) -> None:
        mock_exists.return_value = True

        result = fs_service.exists("test.py")

        assert result is True
        mock_exists.assert_called_once()

    @patch("pathlib.Path.mkdir")
    def test_mkdir(self, mock_mkdir, fs_service) -> None:
        fs_service.mkdir("test_dir", parents=True)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestConfigurationService:
    @pytest.fixture
    def config_service(self, console, pkg_path):
        return ConfigurationService(console, pkg_path)

    def test_init(self, config_service, console, pkg_path) -> None:
        assert config_service.console == console
        assert config_service.pkg_path == pkg_path
        assert config_service.pyproject_path == pkg_path / "pyproject.toml"

    @patch("pathlib.Path.exists")
    def test_pyproject_exists_true(self, mock_exists, config_service) -> None:
        mock_exists.return_value = True

        assert config_service.pyproject_exists() is True

    @patch("pathlib.Path.exists")
    def test_pyproject_exists_false(self, mock_exists, config_service) -> None:
        mock_exists.return_value = False

        assert config_service.pyproject_exists() is False

    @patch("pathlib.Path.read_text")
    def test_read_pyproject_success(self, mock_read, config_service) -> None:
        mock_read.return_value = """
[project]
name = "test - project"
version = "1.0.0"
"""

        data = config_service.read_pyproject()

        assert data["project"]["name"] == "test - project"
        assert data["project"]["version"] == "1.0.0"

    @patch("pathlib.Path.read_text")
    def test_read_pyproject_invalid(self, mock_read, config_service) -> None:
        mock_read.return_value = "invalid toml"

        with pytest.raises(ConfigError):
            config_service.read_pyproject()


class TestSecurityService:
    @pytest.fixture
    def security_service(self):
        return SecurityService()

    def test_init(self, security_service) -> None:
        assert security_service is not None
        assert hasattr(security_service, "validate_command")

    def test_validate_command_safe(self, security_service) -> None:
        result = security_service.validate_command(["echo", "hello"])
        assert result is True

    def test_validate_command_unsafe(self, security_service) -> None:
        result = security_service.validate_command(["rm", " - rf", " / "])
        assert result is False

    @patch("os.environ.get")
    def test_get_token_from_env(self, mock_env, security_service) -> None:
        mock_env.return_value = "test_token"

        token = security_service.get_token("TEST_TOKEN")

        assert token == "test_token"
        mock_env.assert_called_once_with("TEST_TOKEN")

    @patch("os.environ.get")
    @patch("subprocess.run")
    def test_get_token_from_keyring(self, mock_run, mock_env, security_service) -> None:
        mock_env.return_value = None
        mock_run.return_value = Mock(returncode=0, stdout="keyring_token")

        token = security_service.get_token("TEST_TOKEN")

        assert token == "keyring_token"


class TestFileHasher:
    @pytest.fixture
    def file_hasher(self):
        return FileHasher()

    def test_init(self, file_hasher) -> None:
        assert file_hasher._cache == {}
        assert file_hasher._hash_cache == {}

    @patch("pathlib.Path.stat")
    @patch("pathlib.Path.read_bytes")
    def test_get_file_hash(self, mock_read, mock_stat, file_hasher) -> None:
        mock_stat.return_value = Mock(st_mtime=12345)
        mock_read.return_value = b"file content"

        hash1 = file_hasher.get_file_hash(Path("test.py"))
        hash2 = file_hasher.get_file_hash(Path("test.py"))

        assert hash1 == hash2
        assert isinstance(hash1, str)
        mock_read.assert_called_once()

    def test_get_content_hash(self, file_hasher) -> None:
        content = "test content"
        hash_value = file_hasher.get_content_hash(content)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64

    @patch("pathlib.Path.iterdir")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.stat")
    @patch("pathlib.Path.read_bytes")
    def test_get_directory_hash(
        self, mock_read, mock_stat, mock_is_file, mock_iterdir, file_hasher
    ) -> None:
        file1 = Mock()
        file1.is_file.return_value = True
        file1.stat.return_value = Mock(st_mtime=12345)
        file1.read_bytes.return_value = b"content1"

        file2 = Mock()
        file2.is_file.return_value = True
        file2.stat.return_value = Mock(st_mtime=12346)
        file2.read_bytes.return_value = b"content2"

        mock_iterdir.return_value = [file1, file2]

        hash_value = file_hasher.get_directory_hash(Path("test_dir"))

        assert isinstance(hash_value, str)


class TestStructuredLogging:
    def test_correlation_id(self) -> None:
        from crackerjack.services.logging import get_correlation_id, set_correlation_id

        set_correlation_id("test - 123")
        assert get_correlation_id() == "test - 123"

    @patch("crackerjack.services.logging.structlog.configure")
    def test_setup_structured_logging(self, mock_configure) -> None:
        from crackerjack.services.logging import setup_structured_logging

        setup_structured_logging(debug=True)

        mock_configure.assert_called_once()

    def test_get_logger(self) -> None:
        from crackerjack.services.logging import get_logger

        logger = get_logger("test")

        assert logger is not None

    @patch("time.perf_counter")
    def test_log_performance(self, mock_perf_counter) -> None:
        from crackerjack.services.logging import log_performance

        mock_perf_counter.side_effect = [0, 1.5]

        @log_performance("test_operation")
        def test_func() -> str:
            return "result"

        result = test_func()

        assert result == "result"


class TestCrackerjackCache:
    @pytest.fixture
    def cache_service(self, pkg_path):
        return CrackerjackCache(pkg_path)

    def test_init(self, cache_service, pkg_path) -> None:
        assert cache_service.cache_dir == pkg_path
        assert cache_service.hook_results_cache is not None
        assert cache_service.file_hash_cache is not None
        assert cache_service.config_cache is not None

    def test_get_config_data(self, cache_service) -> None:
        cache_service.set_config_data("test_key", {"test": "value"})

        value = cache_service.get_config_data("test_key")
        assert value == {"test": "value"}

    def test_get_nonexistent_config(self, cache_service) -> None:
        value = cache_service.get_config_data("nonexistent")
        assert value is None

    def test_invalidate_hook_cache(self, cache_service) -> None:
        from crackerjack.models.task import HookResult

        result = HookResult(id="test", name="test hook", status="passed", duration=1.0)
        cache_service.set_hook_result("test_hook", ["hash1"], result)

        cache_service.invalidate_hook_cache("test_hook")

        cached_result = cache_service.get_hook_result("test_hook", ["hash1"])
        assert cached_result is None

    def test_get_cache_stats(self, cache_service) -> None:
        stats = cache_service.get_cache_stats()

        assert "hook_results" in stats
        assert "file_hashes" in stats
        assert "config" in stats
        assert isinstance(stats["hook_results"]["hits"], int)

    def test_cleanup_all(self, cache_service) -> None:
        results = cache_service.cleanup_all()

        assert "hook_results" in results
        assert "file_hashes" in results
        assert "config" in results
        assert isinstance(results["hook_results"], int)
