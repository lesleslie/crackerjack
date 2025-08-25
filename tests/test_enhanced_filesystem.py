import tempfile
import time
from pathlib import Path

import pytest

from crackerjack.errors import FileError
from crackerjack.services.enhanced_filesystem import (
    EnhancedFileSystemService,
    FileCache,
)


class TestFileCache:
    def test_cache_initialization(self) -> None:
        cache = FileCache(max_size=100, default_ttl=60.0)
        assert cache.max_size == 100
        assert cache.default_ttl == 60.0
        assert len(cache._cache) == 0

    def test_cache_put_and_get(self) -> None:
        cache = FileCache()
        content = "test content"

        cache.put("key1", content)
        retrieved = cache.get("key1")

        assert retrieved == content

    def test_cache_miss(self) -> None:
        cache = FileCache()
        assert cache.get("nonexistent") is None

    def test_cache_ttl_expiration(self) -> None:
        cache = FileCache(default_ttl=0.1)
        content = "test content"

        cache.put("key1", content)
        assert cache.get("key1") == content

        time.sleep(0.2)
        assert cache.get("key1") is None

    def test_cache_custom_ttl(self) -> None:
        cache = FileCache(default_ttl=1.0)
        content = "test content"

        cache.put("key1", content, ttl=0.1)
        assert cache.get("key1") == content

        time.sleep(0.2)
        assert cache.get("key1") is None

    def test_cache_lru_eviction(self) -> None:
        cache = FileCache(max_size=2)

        cache.put("key1", "content1")
        cache.put("key2", "content2")

        cache.get("key1")

        cache.put("key3", "content3")

        assert cache.get("key1") == "content1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "content3"

    def test_cache_clear(self) -> None:
        cache = FileCache()
        cache.put("key1", "content1")
        cache.put("key2", "content2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert len(cache._cache) == 0

    def test_cache_stats(self) -> None:
        cache = FileCache(max_size=100)
        cache.put("key1", "short")
        cache.put("key2", "longer content")

        stats = cache.get_stats()

        assert stats["entries"] == 2
        assert stats["max_size"] == 100
        assert stats["total_content_size"] > 0
        assert stats["memory_usage_mb"] > 0


class TestBatchFileOperations:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)


class TestEnhancedFileSystemService:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)

    @pytest.fixture
    def fs_service(self):
        return EnhancedFileSystemService(
            cache_size=100,
            cache_ttl=60.0,
            batch_size=5,
            enable_async=True,
        )

    @pytest.fixture
    def sync_fs_service(self):
        return EnhancedFileSystemService(enable_async=False)

    def test_service_initialization(self, fs_service) -> None:
        assert fs_service.cache.max_size == 100
        assert fs_service.cache.default_ttl == 60.0
        assert fs_service.batch_ops is not None
        assert fs_service.enable_async is True

    def test_read_file_with_caching(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "cached_read.txt"
        test_content = "cached content"
        test_file.write_text(test_content)

        content1 = fs_service.read_file(test_file)
        assert content1 == test_content

        content2 = fs_service.read_file(test_file)
        assert content2 == test_content

        cache_key = fs_service._get_cache_key(test_file)
        cached_content = fs_service.cache.get(cache_key)
        assert cached_content == test_content

    def test_write_file_invalidates_cache(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "cache_invalidation.txt"
        original_content = "original"
        new_content = "new content"

        test_file.write_text(original_content)

        fs_service.read_file(test_file)

        fs_service.write_file(test_file, new_content)

        content = fs_service.read_file(test_file)
        assert content == new_content

    def test_cache_invalidation_on_file_modification(
        self,
        fs_service,
        temp_dir,
    ) -> None:
        test_file = temp_dir / "external_modification.txt"
        original_content = "original"
        modified_content = "modified"

        test_file.write_text(original_content)

        content1 = fs_service.read_file(test_file)
        assert content1 == original_content

        time.sleep(0.1)
        test_file.write_text(modified_content)

        content2 = fs_service.read_file(test_file)
        assert content2 == modified_content

    def test_file_operations_sync_fallback(self, sync_fs_service, temp_dir) -> None:
        test_file = temp_dir / "sync_fallback.txt"
        test_content = "sync content"

        sync_fs_service.write_file(test_file, test_content)
        content = sync_fs_service.read_file(test_file)

        assert content == test_content
        assert sync_fs_service.batch_ops is None

    def test_error_handling_nonexistent_file(self, fs_service, temp_dir) -> None:
        nonexistent_file = temp_dir / "does_not_exist.txt"

        with pytest.raises(FileError, match="File does not exist"):
            fs_service.read_file(nonexistent_file)

    def test_error_handling_invalid_content_type(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "invalid_content.txt"

        with pytest.raises(TypeError, match="Content must be a string"):
            fs_service.write_file(test_file, 123)

    def test_file_exists(self, fs_service, temp_dir) -> None:
        existing_file = temp_dir / "exists.txt"
        nonexistent_file = temp_dir / "does_not_exist.txt"

        existing_file.write_text("content")

        assert fs_service.file_exists(existing_file) is True
        assert fs_service.file_exists(nonexistent_file) is False

    def test_create_directory(self, fs_service, temp_dir) -> None:
        new_dir = temp_dir / "new" / "nested" / "directory"

        fs_service.create_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_delete_file(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "to_delete.txt"
        test_file.write_text("content")

        fs_service.read_file(test_file)

        fs_service.delete_file(test_file)

        assert not test_file.exists()

        cache_key = fs_service._get_cache_key(test_file)
        assert fs_service.cache.get(cache_key) is None

    def test_list_files(self, fs_service, temp_dir) -> None:
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "file3.py").write_text("content3")

        all_files = list(fs_service.list_files(temp_dir))
        assert len(all_files) == 3

        txt_files = list(fs_service.list_files(temp_dir, "*.txt"))
        assert len(txt_files) == 2

    def test_get_cache_stats(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "stats_test.txt"
        test_file.write_text("test content for stats")

        fs_service.read_file(test_file)

        stats = fs_service.get_cache_stats()

        assert stats["entries"] == 1
        assert stats["total_content_size"] > 0
        assert stats["memory_usage_mb"] > 0

    def test_clear_cache(self, fs_service, temp_dir) -> None:
        test_file = temp_dir / "clear_test.txt"
        test_file.write_text("cached content")

        fs_service.read_file(test_file)

        stats_before = fs_service.get_cache_stats()
        assert stats_before["entries"] == 1

        fs_service.clear_cache()

        stats_after = fs_service.get_cache_stats()
        assert stats_after["entries"] == 0


class TestPerformanceAndIntegration:
    def test_cache_memory_efficiency(self) -> None:
        fs_service = EnhancedFileSystemService(cache_size=100, cache_ttl=3600)

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_dir = Path(tmp_dir)

            for i in range(150):
                file_path = temp_dir / f"memory_test_{i}.txt"
                content = f"memory test content {i}"
                file_path.write_text(content)
                fs_service.read_file(file_path)

            stats = fs_service.get_cache_stats()

            assert stats["entries"] <= 100
            assert stats["memory_usage_mb"] < 100
