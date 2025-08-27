"""
Strategic tests for enhanced filesystem service targeting advanced capabilities.
Focus: caching, error handling, service logic, coverage.
Target: 60-80% coverage of 263 statements.
"""

import hashlib
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.errors import FileError
from crackerjack.services.enhanced_filesystem import (
    EnhancedFileSystemService,
    FileCache,
)


class TestFileCache:
    """Test FileCache caching logic and LRU eviction."""

    @pytest.fixture
    def cache(self):
        return FileCache(max_size=3, default_ttl=1.0)

    def test_cache_initialization(self):
        """Test FileCache initialization with custom parameters."""
        cache = FileCache(max_size=100, default_ttl=600.0)
        assert cache.max_size == 100
        assert cache.default_ttl == 600.0
        assert cache._cache == {}
        assert cache._access_times == {}

    def test_cache_put_and_get(self, cache):
        """Test basic cache put and get operations."""
        cache.put("key1", "content1")

        result = cache.get("key1")
        assert result == "content1"

    def test_cache_miss(self, cache):
        """Test cache miss returns None."""
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_ttl_expiration(self, cache):
        """Test cache entries expire based on TTL."""
        cache.put("key1", "content1", ttl=0.1)

        # Content should be available immediately
        assert cache.get("key1") == "content1"

        # Wait for TTL to expire
        time.sleep(0.2)

        # Content should be expired
        result = cache.get("key1")
        assert result is None

    def test_cache_lru_eviction(self, cache):
        """Test LRU eviction when cache reaches max size."""
        # Fill cache to max capacity
        cache.put("key1", "content1")
        cache.put("key2", "content2")
        cache.put("key3", "content3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add new entry, should evict key2 (least recently used)
        cache.put("key4", "content4")

        assert cache.get("key1") == "content1"  # Still present
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "content3"  # Still present
        assert cache.get("key4") == "content4"  # New entry

    def test_cache_clear(self, cache):
        """Test cache clear functionality."""
        cache.put("key1", "content1")
        cache.put("key2", "content2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert len(cache._cache) == 0
        assert len(cache._access_times) == 0

    def test_cache_stats(self, cache):
        """Test cache statistics calculation."""
        cache.put("key1", "short")
        cache.put("key2", "much longer content")

        stats = cache.get_stats()

        assert stats["entries"] == 2
        assert stats["max_size"] == 3
        assert stats["total_content_size"] == len("short") + len("much longer content")
        assert stats["memory_usage_mb"] > 0

    def test_cache_custom_ttl(self, cache):
        """Test cache with custom TTL per entry."""
        cache.put("short_ttl", "content1", ttl=0.1)
        cache.put("long_ttl", "content2", ttl=10.0)

        time.sleep(0.2)

        assert cache.get("short_ttl") is None  # Expired
        assert cache.get("long_ttl") == "content2"  # Still valid

    def test_cache_evict_method(self, cache):
        """Test internal eviction method."""
        cache.put("key1", "content1")
        assert cache.get("key1") == "content1"

        # Test internal eviction
        cache._evict("key1")
        assert cache.get("key1") is None

    def test_cache_evict_lru_empty(self, cache):
        """Test LRU eviction with empty access times."""
        # Should not raise error with empty access times
        cache._evict_lru()


class TestEnhancedFileSystemService:
    """Test EnhancedFileSystemService with caching, error handling, and service operations."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def enhanced_fs(self):
        return EnhancedFileSystemService(
            cache_size=10, cache_ttl=1.0, batch_size=2, enable_async=True
        )

    @pytest.fixture
    def sync_fs(self):
        return EnhancedFileSystemService(enable_async=False)

    def test_service_initialization(self):
        """Test EnhancedFileSystemService initialization with various configurations."""
        # Test with defaults
        fs = EnhancedFileSystemService()
        assert fs.cache.max_size == 1000
        assert fs.cache.default_ttl == 300.0
        assert fs.batch_ops is not None
        assert fs.enable_async is True

        # Test async disabled
        fs_sync = EnhancedFileSystemService(enable_async=False)
        assert fs_sync.batch_ops is None
        assert fs_sync.enable_async is False

    def test_read_file_caching(self, enhanced_fs, temp_dir):
        """Test file reading with caching."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("cached content")

        # First read - should cache
        content1 = enhanced_fs.read_file(test_file)
        assert content1 == "cached content"

        # Mock the internal direct read method to verify cache hit
        with patch.object(
            enhanced_fs, "_read_file_direct", return_value="new content"
        ) as mock_read:
            content2 = enhanced_fs.read_file(test_file)
            # Should get cached content, not call direct read
            assert content2 == "cached content"
            mock_read.assert_not_called()

    def test_cache_invalidation_on_file_change(self, enhanced_fs, temp_dir):
        """Test cache invalidation when file is modified."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("original content")

        # First read
        content1 = enhanced_fs.read_file(test_file)
        assert content1 == "original content"

        # Modify file (change mtime)
        time.sleep(0.1)
        test_file.write_text("modified content")

        # Should detect file change and re-read
        content2 = enhanced_fs.read_file(test_file)
        assert content2 == "modified content"

    def test_write_file_cache_eviction(self, enhanced_fs, temp_dir):
        """Test writing file evicts cache entry."""
        test_file = temp_dir / "test.txt"

        # Write and read to populate cache
        enhanced_fs.write_file(test_file, "initial content")
        enhanced_fs.read_file(test_file)

        # Write again - should evict cache
        enhanced_fs.write_file(test_file, "updated content")

        # Read should get updated content from disk
        content = enhanced_fs.read_file(test_file)
        assert content == "updated content"

    def test_cache_key_generation(self, enhanced_fs, temp_dir):
        """Test cache key generation uses file path hash."""
        test_file = temp_dir / "test.txt"

        cache_key = enhanced_fs._get_cache_key(test_file)

        expected_path = str(test_file.resolve())
        expected_hash = hashlib.md5(
            expected_path.encode(), usedforsecurity=False
        ).hexdigest()
        assert cache_key == expected_hash

    def test_get_from_cache_nonexistent_file(self, enhanced_fs, temp_dir):
        """Test cache lookup for nonexistent file returns None."""
        nonexistent_file = temp_dir / "nonexistent.txt"
        cache_key = "test_key"

        result = enhanced_fs._get_from_cache(cache_key, nonexistent_file)
        assert result is None

    def test_get_from_cache_file_modified(self, enhanced_fs, temp_dir):
        """Test cache invalidation when file is modified after caching."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("original content")

        cache_key = enhanced_fs._get_cache_key(test_file)

        # Populate cache and timestamp
        enhanced_fs.cache.put(cache_key, "cached content")
        enhanced_fs._file_timestamps[str(test_file)] = (
            test_file.stat().st_mtime - 1
        )  # Older timestamp

        # Should detect modification and invalidate cache
        result = enhanced_fs._get_from_cache(cache_key, test_file)
        assert result is None

    def test_file_error_handling_read(self, enhanced_fs, temp_dir):
        """Test FileError handling for read operations."""
        nonexistent_file = temp_dir / "nonexistent.txt"

        with pytest.raises(FileError, match="File does not exist"):
            enhanced_fs.read_file(nonexistent_file)

    def test_file_error_handling_permission_read(self, enhanced_fs, temp_dir):
        """Test FileError handling for read permission errors."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(
            Path, "read_text", side_effect=PermissionError("Access denied")
        ):
            with pytest.raises(FileError, match="Permission denied reading file"):
                enhanced_fs.read_file(test_file)

    def test_file_error_handling_unicode_decode(self, enhanced_fs, temp_dir):
        """Test FileError handling for unicode decode errors."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(
            Path,
            "read_text",
            side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid"),
        ):
            with pytest.raises(FileError, match="Unable to decode file as UTF-8"):
                enhanced_fs.read_file(test_file)

    def test_file_error_handling_os_error_read(self, enhanced_fs, temp_dir):
        """Test FileError handling for OS errors on read."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(Path, "read_text", side_effect=OSError("Disk error")):
            with pytest.raises(FileError, match="System error reading file"):
                enhanced_fs.read_file(test_file)

    def test_file_error_handling_write_permission(self, enhanced_fs, temp_dir):
        """Test FileError handling for write permission errors."""
        test_file = temp_dir / "test.txt"

        with patch.object(
            Path, "write_text", side_effect=PermissionError("Access denied")
        ):
            with pytest.raises(FileError, match="Permission denied writing file"):
                enhanced_fs.write_file(test_file, "content")

    def test_file_error_handling_os_error_write(self, enhanced_fs, temp_dir):
        """Test FileError handling for OS errors on write."""
        test_file = temp_dir / "test.txt"

        with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
            with pytest.raises(FileError, match="System error writing file"):
                enhanced_fs.write_file(test_file, "content")

    def test_file_error_handling_mkdir_error(self, enhanced_fs, temp_dir):
        """Test FileError handling for directory creation errors."""
        test_file = temp_dir / "nested" / "test.txt"

        with patch.object(Path, "mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(FileError, match="Cannot create parent directory"):
                enhanced_fs.write_file(test_file, "content")

    def test_write_file_type_validation(self, enhanced_fs, temp_dir):
        """Test write_file validates content is string."""
        test_file = temp_dir / "test.txt"

        with pytest.raises(TypeError, match="Content must be a string"):
            enhanced_fs.write_file(test_file, b"bytes content")

    def test_create_directory(self, enhanced_fs, temp_dir):
        """Test directory creation."""
        new_dir = temp_dir / "new_directory"

        enhanced_fs.create_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_create_nested_directories(self, enhanced_fs, temp_dir):
        """Test creating nested directories."""
        nested_dir = temp_dir / "level1" / "level2" / "level3"

        enhanced_fs.create_directory(nested_dir)

        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_create_directory_error(self, enhanced_fs, temp_dir):
        """Test directory creation error handling."""
        new_dir = temp_dir / "new_directory"

        with patch.object(Path, "mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(FileError, match="Cannot create directory"):
                enhanced_fs.create_directory(new_dir)

    def test_delete_file(self, enhanced_fs, temp_dir):
        """Test file deletion and cache cleanup."""
        test_file = temp_dir / "delete_me.txt"
        test_file.write_text("content to delete")

        # Read to populate cache
        enhanced_fs.read_file(test_file)

        # Delete file
        enhanced_fs.delete_file(test_file)

        assert not test_file.exists()

    def test_delete_nonexistent_file(self, enhanced_fs, temp_dir):
        """Test deleting nonexistent file doesn't raise error."""
        nonexistent_file = temp_dir / "nonexistent.txt"

        # Should not raise error
        enhanced_fs.delete_file(nonexistent_file)

    def test_delete_file_error(self, enhanced_fs, temp_dir):
        """Test delete file error handling."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
            with pytest.raises(FileError, match="Cannot delete file"):
                enhanced_fs.delete_file(test_file)

    def test_list_files_with_pattern(self, enhanced_fs, temp_dir):
        """Test listing files with glob patterns."""
        # Create test files
        (temp_dir / "test.txt").write_text("content")
        (temp_dir / "test.py").write_text("python content")
        (temp_dir / "readme.md").write_text("markdown content")

        # List all files
        all_files = list(enhanced_fs.list_files(temp_dir, "*"))
        assert len(all_files) == 3

        # List only .txt files
        txt_files = list(enhanced_fs.list_files(temp_dir, "*.txt"))
        assert len(txt_files) == 1
        assert txt_files[0].name == "test.txt"

    def test_list_files_invalid_directory(self, enhanced_fs, temp_dir):
        """Test listing files in non-directory raises error."""
        test_file = temp_dir / "not_a_directory.txt"
        test_file.write_text("content")

        with pytest.raises(FileError, match="Path is not a directory"):
            list(enhanced_fs.list_files(test_file))

    def test_list_files_os_error(self, enhanced_fs, temp_dir):
        """Test listing files with OS error."""
        with patch.object(Path, "glob", side_effect=OSError("Permission denied")):
            with pytest.raises(FileError, match="Cannot list files in directory"):
                list(enhanced_fs.list_files(temp_dir))

    def test_file_exists(self, enhanced_fs, temp_dir):
        """Test file existence check."""
        existing_file = temp_dir / "exists.txt"
        existing_file.write_text("content")
        nonexistent_file = temp_dir / "nonexistent.txt"

        assert enhanced_fs.file_exists(existing_file) is True
        assert enhanced_fs.file_exists(nonexistent_file) is False

    def test_exists_method(self, enhanced_fs, temp_dir):
        """Test exists method (alias for file_exists)."""
        existing_file = temp_dir / "exists.txt"
        existing_file.write_text("content")

        assert enhanced_fs.exists(existing_file) is True
        assert enhanced_fs.exists("nonexistent.txt") is False

    def test_mkdir_method(self, enhanced_fs, temp_dir):
        """Test mkdir method."""
        new_dir = temp_dir / "mkdir_test"

        enhanced_fs.mkdir(new_dir)
        assert new_dir.exists()

        # Test with parents
        nested_dir = temp_dir / "parent" / "child"
        enhanced_fs.mkdir(nested_dir, parents=True)
        assert nested_dir.exists()

    def test_mkdir_error(self, enhanced_fs, temp_dir):
        """Test mkdir method error handling."""
        new_dir = temp_dir / "mkdir_test"

        with patch.object(Path, "mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(FileError, match="Cannot create directory"):
                enhanced_fs.mkdir(new_dir)

    def test_cache_stats_and_clear(self, enhanced_fs, temp_dir):
        """Test cache statistics and clear functionality."""
        # Create and read files to populate cache
        for i in range(3):
            file = temp_dir / f"cache_test{i}.txt"
            file.write_text(f"content{i}")
            enhanced_fs.read_file(file)

        # Get stats
        stats = enhanced_fs.get_cache_stats()
        assert stats["entries"] == 3

        # Clear cache
        enhanced_fs.clear_cache()

        stats_after = enhanced_fs.get_cache_stats()
        assert stats_after["entries"] == 0

    def test_string_path_handling(self, enhanced_fs, temp_dir):
        """Test service handles both string and Path objects."""
        test_file = temp_dir / "string_test.txt"

        # Use string path
        enhanced_fs.write_file(str(test_file), "string path content")
        content = enhanced_fs.read_file(str(test_file))

        assert content == "string path content"
        assert enhanced_fs.file_exists(str(test_file))

    def test_sync_filesystem_async_disabled(self, sync_fs, temp_dir):
        """Test sync filesystem behavior when async is disabled."""
        test_file = temp_dir / "sync_test.txt"
        test_file.write_text("sync content")

        # Sync operations should work normally
        content = sync_fs.read_file(test_file)
        assert content == "sync content"

        sync_fs.write_file(test_file, "sync write")
        assert test_file.read_text() == "sync write"

    def test_direct_file_operations(self, enhanced_fs, temp_dir):
        """Test internal direct file operations."""
        test_file = temp_dir / "direct_test.txt"

        # Test direct read of nonexistent file
        with pytest.raises(FileError):
            enhanced_fs._read_file_direct(test_file)

        # Test direct write and read
        enhanced_fs._write_file_direct(test_file, "direct content")
        content = enhanced_fs._read_file_direct(test_file)
        assert content == "direct content"

    def test_cache_with_file_timestamps(self, enhanced_fs, temp_dir):
        """Test cache behavior with file timestamp tracking."""
        test_file = temp_dir / "timestamp_test.txt"
        test_file.write_text("original")

        # Read to populate cache and timestamps
        enhanced_fs.read_file(test_file)

        # Verify timestamp was recorded
        assert str(test_file) in enhanced_fs._file_timestamps

        # Clear cache should also clear timestamps
        enhanced_fs.clear_cache()
        assert str(test_file) not in enhanced_fs._file_timestamps
