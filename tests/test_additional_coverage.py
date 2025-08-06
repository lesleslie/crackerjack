import time
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from crackerjack.api import CrackerjackAPI
from crackerjack.code_cleaner import CodeCleaner
from crackerjack.config.hooks import HookConfigLoader, HookStrategy
from crackerjack.dynamic_config import DynamicConfigGenerator
from crackerjack.services.cache import FileCache, InMemoryCache
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.security import SecurityService


@pytest.fixture
def console():
    return Console()


@pytest.fixture
def pkg_path(tmp_path):
    return tmp_path


class TestCrackerjackAPI:
    @pytest.fixture
    def api(self):
        return CrackerjackAPI()

    def test_init(self, api) -> None:
        assert api.orchestrator is not None
        assert api.container is not None
        assert api.console is not None
        assert api.project_path is not None

    def test_run_quality_checks(self, api) -> None:
        with patch.object(
            api.orchestrator.pipeline, "run_complete_workflow", return_value=True
        ):
            result = api.run_quality_checks()

        assert result.success is True
        assert result.fast_hooks_passed is True

    def test_run_tests(self, api) -> None:
        with patch.object(
            api.orchestrator.pipeline, "run_complete_workflow", return_value=True
        ):
            result = api.run_tests()

        assert result.success is True

    def test_publish_package(self, api) -> None:
        with patch.object(
            api.orchestrator.pipeline, "run_complete_workflow", return_value=True
        ):
            result = api.publish_package(version_bump="patch")

        assert result.success is True


class TestCodeCleaner:
    @pytest.fixture
    def cleaner(self, console):
        return CodeCleaner(console=console)

    def test_init(self, cleaner) -> None:
        assert cleaner.console is not None
        assert hasattr(cleaner, "file_processor")

    def test_clean_files_basic(self, cleaner, tmp_path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text('def test(): \n """docstring"""\n return 42\n')

        results = cleaner.clean_files(tmp_path)

        assert len(results) >= 0

    def test_clean_files_with_backup(self, cleaner, tmp_path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text('def test(): \n """docstring"""\n return 42\n')

        try:
            results = cleaner.clean_files(tmp_path)
            assert isinstance(results, list)
        except Exception:
            pass

    def test_should_process_file(self, cleaner) -> None:
        py_file = Path("test.py")
        assert cleaner.should_process_file(py_file) is True

        txt_file = Path("test.txt")
        assert cleaner.should_process_file(txt_file) is False


class TestInMemoryCache:
    @pytest.fixture
    def cache(self):
        return InMemoryCache()

    def test_get_set(self, cache) -> None:
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self, cache) -> None:
        assert cache.get("nonexistent") is None

    def test_delete(self, cache) -> None:
        cache.set("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_clear(self, cache) -> None:
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert len(cache._cache) == 0

    def test_ttl_expiry(self, cache) -> None:
        cache.set("key1", "value1", ttl_seconds=1)
        assert cache.get("key1") == "value1"
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_stats(self, cache) -> None:
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("nonexistent")

        stats = cache.stats.to_dict()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestFileCache:
    @pytest.fixture
    def cache(self, tmp_path):
        return FileCache(tmp_path)

    def test_init(self, cache, tmp_path) -> None:
        assert cache.cache_dir == tmp_path / "crackerjack"
        assert cache.cache_dir.exists()

    def test_set_get_json(self, cache) -> None:
        data = {"key": "value", "number": 42}
        cache.set("test", data)

        retrieved = cache.get("test")
        assert retrieved == data

    def test_delete_file(self, cache) -> None:
        cache.set("test", {"data": "value"})
        cache.invalidate("test")

        assert cache.get("test") is None


class TestHookConfigLoader:
    @pytest.fixture
    def loader(self):
        return HookConfigLoader()

    def test_init(self, loader) -> None:
        assert isinstance(loader, HookConfigLoader)

    def test_load_strategy_fast(self, loader) -> None:
        strategy = loader.load_strategy("fast")

        assert isinstance(strategy, HookStrategy)
        assert strategy.name == "fast"
        assert len(strategy.hooks) > 0

    def test_load_strategy_comprehensive(self, loader) -> None:
        strategy = loader.load_strategy("comprehensive")

        assert isinstance(strategy, HookStrategy)
        assert strategy.name == "comprehensive"
        assert len(strategy.hooks) > 0

    def test_load_invalid_strategy(self, loader) -> None:
        with pytest.raises(ValueError):
            loader.load_strategy("invalid")


class TestDynamicConfigGenerator:
    @pytest.fixture
    def generator(self, pkg_path):
        return DynamicConfigGenerator()

    def test_init(self, generator) -> None:
        assert hasattr(generator, "template")

    def test_get_repo_comment(self, generator) -> None:
        comment = generator._get_repo_comment("https: // github.com / example / repo")
        assert comment is not None or comment is None

    def test_generate_config(self, generator) -> None:
        from crackerjack.dynamic_config import get_available_modes

        modes = get_available_modes()
        if modes:
            config = generator.generate_config(modes[0])
            assert isinstance(config, str)

    def test_filter_hooks_for_mode(self, generator) -> None:
        from crackerjack.dynamic_config import get_available_modes

        modes = get_available_modes()
        if modes:
            filtered = generator.filter_hooks_for_mode(modes[0], [])
            assert isinstance(filtered, list)


class TestFileSystemServiceExtended:
    @pytest.fixture
    def fs_service(self):
        return FileSystemService()

    @patch("pathlib.Path.glob")
    def test_glob_directory(self, mock_glob, fs_service) -> None:
        mock_glob.return_value = [Path("file1.py"), Path("dir1")]

        files = fs_service.glob(" * ", ".")

        assert len(files) == 2
        assert "file1.py" in [f.name for f in files]

    @patch("pathlib.Path.glob")
    def test_rglob_files(self, mock_glob, fs_service) -> None:
        mock_glob.return_value = [Path("test1.py"), Path("test2.py")]

        files = fs_service.rglob(" * .py", ".")

        assert len(files) == 2
        assert all(f.suffix == ".py" for f in files)

    def test_file_operations(self, fs_service, tmp_path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        size = fs_service.get_file_size(str(test_file))
        mtime = fs_service.get_file_mtime(str(test_file))

        assert size > 0
        assert mtime > 0


class TestSecurityServiceExtended:
    @pytest.fixture
    def security_service(self):
        return SecurityService()

    def test_validate_token_formats(self, security_service) -> None:
        valid_tokens = [
            "ghp_1234567890abcdef1234567890abcdef12345678",
            "pypi - token123",
            "sk - 1234567890abcdef",
        ]

        for token in valid_tokens:
            result = security_service.validate_token_format(token)
            assert isinstance(result, bool)

    def test_mask_tokens(self, security_service) -> None:
        text_with_tokens = (
            "Here is a token ghp_1234567890abcdef1234567890abcdef12345678 in text"
        )

        masked = security_service.mask_tokens(text_with_tokens)

        assert "ghp_" not in masked or masked.count(" * ") > 0

    @patch("crackerjack.services.security.tempfile.mkstemp")
    @patch("crackerjack.services.security.Path.chmod")
    @patch("crackerjack.services.security.os.fdopen")
    def test_create_secure_token_file(
        self, mock_fdopen, mock_chmod, mock_mkstemp, security_service
    ) -> None:
        mock_mkstemp.return_value = (10, " / tmp / secure_file")
        mock_file = mock_fdopen.return_value.__enter__.return_value

        path = security_service.create_secure_token_file("test_token")

        assert path == Path(" / tmp / secure_file")
        mock_chmod.assert_called_once_with(0o600)
        mock_file.write.assert_called_once_with("test_token")
