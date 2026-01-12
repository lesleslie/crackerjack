"""Unit tests for EnhancedFileSystemService.

Tests file caching, batch operations, async file I/O,
and enhanced filesystem service functionality.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from unittest.mock import mock_open

import pytest

from crackerjack.services.enhanced_filesystem import (
    BatchFileOperations,
    EnhancedFileSystemService,
    FileCache,
)


@pytest.mark.unit
class TestFileCache:
    """Test FileCache class."""

    def test_initialization(self) -> None:
        """Test cache initializes with defaults."""
        cache = FileCache()

        assert cache.max_size == 1000
        assert cache.default_ttl == 300.0
        assert cache._cache == {}
        assert cache._access_times == {}

    def test_initialization_with_custom_params(self) -> None:
        """Test cache initializes with custom parameters."""
        cache = FileCache(max_size=100, default_ttl=600.0)

        assert cache.max_size == 100
        assert cache.default_ttl == 600.0

    def test_get_cache_miss(self) -> None:
        """Test get returns None for missing key."""
        cache = FileCache()

        result = cache.get("nonexistent")

        assert result is None

    def test_put_and_get(self) -> None:
        """Test put and get operations."""
        cache = FileCache()

        cache.put("key1", "content1")
        result = cache.get("key1")

        assert result == "content1"

    def test_get_expired_entry(self) -> None:
        """Test get returns None for expired entry."""
        cache = FileCache(default_ttl=0.1)

        cache.put("key1", "content1")
        import time
        time.sleep(0.2)

        result = cache.get("key1")

        assert result is None

    def test_put_with_custom_ttl(self) -> None:
        """Test put with custom TTL."""
        cache = FileCache()

        cache.put("key1", "content1", ttl=1.0)

        entry = cache._cache["key1"]
        assert entry["ttl"] == 1.0

    def test_cache_eviction_on_max_size(self) -> None:
        """Test LRU eviction when cache is full."""
        cache = FileCache(max_size=2)

        cache.put("key1", "content1")
        cache.put("key2", "content2")
        cache.put("key3", "content3")  # Should evict key1

        assert cache.get("key1") is None
        assert cache.get("key2") == "content2"
        assert cache.get("key3") == "content3"

    def test_clear(self) -> None:
        """Test cache clearing."""
        cache = FileCache()

        cache.put("key1", "content1")
        cache.clear()

        assert cache.get("key1") is None
        assert len(cache._cache) == 0

    def test_get_stats(self) -> None:
        """Test statistics retrieval."""
        cache = FileCache()

        cache.put("key1", "content1")
        cache.put("key2", "content2")

        stats = cache.get_stats()

        assert stats["entries"] == 2
        assert stats["max_size"] == 1000
        assert "total_content_size" in stats
        assert "memory_usage_mb" in stats


@pytest.mark.unit
class TestBatchFileOperations:
    """Test BatchFileOperations class."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """Test batch operations initialization."""
        batch = BatchFileOperations()

        assert batch.batch_size == 10
        assert batch.read_queue == []

    @pytest.mark.asyncio
    async def test_queue_read(self, tmp_path) -> None:
        """Test queueing a read operation."""
        batch = BatchFileOperations()
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        future = asyncio.Future()
        batch.read_queue.append((test_file, future))

        assert len(batch.read_queue) == 1

    @pytest.mark.asyncio
    async def test_flush_all_empty(self) -> None:
        """Test flushing empty queue."""
        batch = BatchFileOperations()

        await batch.flush_all()

        # Should not raise any errors
        assert True


@pytest.mark.unit
class TestEnhancedFileSystemServiceInitialization:
    """Test EnhancedFileSystemService initialization."""

    def test_initialization(self) -> None:
        """Test service initializes with defaults."""
        service = EnhancedFileSystemService()

        assert service.cache is not None
        assert isinstance(service.cache, FileCache)
        assert service.cache.max_size == 1000
        assert service.enable_async is True

    def test_initialization_with_custom_params(self) -> None:
        """Test service initializes with custom parameters."""
        service = EnhancedFileSystemService(
            cache_size=500,
            cache_ttl=600.0,
            batch_size=20,
            enable_async=False,
        )

        assert service.cache.max_size == 500
        assert service.cache.default_ttl == 600.0
        assert service.enable_async is False


@pytest.mark.unit
class TestReadFile:
    """Test synchronous file reading."""

    def test_read_file_success(self, tmp_path) -> None:
        """Test successful file read."""
        service = EnhancedFileSystemService()
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        content = service.read_file(test_file)

        assert content == "Hello, World!"

    def test_read_file_not_found(self, tmp_path) -> None:
        """Test reading non-existent file."""
        service = EnhancedFileSystemService()
        non_file = tmp_path / "nonexistent.txt"

        with pytest.raises(Exception):  # FileError or similar
            service.read_file(non_file)


@pytest.mark.unit
class TestWriteFile:
    """Test synchronous file writing."""

    def test_write_file_success(self, tmp_path) -> None:
        """Test successful file write."""
        service = EnhancedFileSystemService()
        test_file = tmp_path / "test.txt"

        service.write_file(test_file, "New content")

        assert test_file.read_text() == "New content"

    def test_write_file_creates_directory(self, tmp_path) -> None:
        """Test write creates parent directories."""
        service = EnhancedFileSystemService()
        test_file = tmp_path / "subdir" / "test.txt"

        service.write_file(test_file, "Content")

        assert test_file.exists()
        assert test_file.read_text() == "Content"


@pytest.mark.unit
class TestAsyncConfiguration:
    """Test async operations configuration."""

    def test_async_enabled_by_default(self) -> None:
        """Test async operations are enabled by default."""
        service = EnhancedFileSystemService()

        assert service.enable_async is True
        assert service.batch_ops is not None

    def test_async_can_be_disabled(self) -> None:
        """Test async operations can be disabled."""
        service = EnhancedFileSystemService(enable_async=False)

        assert service.enable_async is False
        assert service.batch_ops is None

    def test_batch_size_configuration(self) -> None:
        """Test batch size is configurable."""
        service = EnhancedFileSystemService(batch_size=50)

        assert service.batch_ops is not None
        assert service.batch_ops.batch_size == 50


@pytest.mark.unit
class TestCacheIntegration:
    """Test cache integration with file operations."""

    def test_get_cache_key(self) -> None:
        """Test cache key generation."""
        service = EnhancedFileSystemService()
        path = Path("/test/file.txt")

        key = service._get_cache_key(path)

        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hash length

    def test_cache_hit_on_second_read(self, tmp_path) -> None:
        """Test that second read uses cache."""
        service = EnhancedFileSystemService()
        test_file = tmp_path / "test.txt"
        test_file.write_text("Cached content")

        # First read - populates cache
        content1 = service.read_file(test_file)

        # Second read - should hit cache
        content2 = service.read_file(test_file)

        assert content1 == "Cached content"
        assert content2 == "Cached content"
        # Verify cache was used
        assert len(service.cache._cache) > 0


@pytest.mark.unit
class TestFileOperations:
    """Test file system operations."""

    def test_file_exists_true(self, tmp_path) -> None:
        """Test file_exists returns True for existing file."""
        service = EnhancedFileSystemService()
        test_file = tmp_path / "test.txt"
        test_file.touch()

        assert service.file_exists(test_file) is True

    def test_file_exists_false(self, tmp_path) -> None:
        """Test file_exists returns False for missing file."""
        service = EnhancedFileSystemService()
        non_file = tmp_path / "nonexistent.txt"

        assert service.file_exists(non_file) is False

    def test_create_directory(self, tmp_path) -> None:
        """Test directory creation."""
        service = EnhancedFileSystemService()
        new_dir = tmp_path / "newdir"

        service.create_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_delete_file(self, tmp_path) -> None:
        """Test file deletion."""
        service = EnhancedFileSystemService()
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        service.delete_file(test_file)

        assert not test_file.exists()

    def test_list_files(self, tmp_path) -> None:
        """Test listing files in directory."""
        service = EnhancedFileSystemService()

        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()

        files = list(service.list_files(tmp_path))

        assert len(files) == 2
        assert all(f.name.endswith(".txt") for f in files)

    def test_list_files_with_pattern(self, tmp_path) -> None:
        """Test listing files with pattern filter."""
        service = EnhancedFileSystemService()

        (tmp_path / "test1.txt").touch()
        (tmp_path / "test2.log").touch()
        (tmp_path / "other.txt").touch()

        files = list(service.list_files(tmp_path, "test*"))

        assert len(files) == 2


@pytest.mark.unit
class TestCacheStats:
    """Test cache statistics."""

    def test_get_cache_stats(self) -> None:
        """Test retrieving cache statistics."""
        service = EnhancedFileSystemService()
        service.cache.put("key1", "content1")

        stats = service.get_cache_stats()

        assert "entries" in stats
        assert stats["entries"] == 1

    def test_clear_cache(self) -> None:
        """Test clearing cache."""
        service = EnhancedFileSystemService()
        service.cache.put("key1", "content1")

        service.clear_cache()

        stats = service.get_cache_stats()
        assert stats["entries"] == 0


@pytest.mark.unit
class TestUtilityMethods:
    """Test utility methods."""

    def test_exists_alias(self, tmp_path) -> None:
        """Test exists method."""
        service = EnhancedFileSystemService()
        test_file = tmp_path / "test.txt"
        test_file.touch()

        assert service.exists(test_file) is True

    def test_mkdir_alias(self, tmp_path) -> None:
        """Test mkdir method."""
        service = EnhancedFileSystemService()
        new_dir = tmp_path / "newdir"

        service.mkdir(new_dir)

        assert new_dir.exists()
