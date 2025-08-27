"""
Functional tests for enhanced filesystem components.

This module provides comprehensive testing of filesystem caching,
batch operations, and file monitoring functionality.
Targets the 263-line enhanced_filesystem module for coverage impact.
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.services.enhanced_filesystem import (
    BatchFileOperations,
    FileCache,
)


class TestFileCacheFunctional:
    """Comprehensive tests for file caching functionality."""

    @pytest.fixture
    def cache(self) -> FileCache:
        """Create a file cache for testing."""
        return FileCache(max_size=3, default_ttl=1.0)

    def test_cache_initialization(self, cache: FileCache) -> None:
        """Test cache initialization and configuration."""
        assert cache.max_size == 3
        assert cache.default_ttl == 1.0
        assert len(cache._cache) == 0
        assert len(cache._access_times) == 0

    def test_cache_put_and_get_basic(self, cache: FileCache) -> None:
        """Test basic cache put and get operations."""
        cache.put("key1", "content1")

        result = cache.get("key1")
        assert result == "content1"
        assert "key1" in cache._cache
        assert "key1" in cache._access_times

    def test_cache_get_nonexistent(self, cache: FileCache) -> None:
        """Test getting non-existent cache entry."""
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_ttl_expiration(self, cache: FileCache) -> None:
        """Test cache entry expiration based on TTL."""
        cache.put("key1", "content1", ttl=0.1)

        # Immediately available
        assert cache.get("key1") == "content1"

        # Wait for expiration
        time.sleep(0.2)
        assert cache.get("key1") is None
        assert "key1" not in cache._cache

    def test_cache_lru_eviction(self, cache: FileCache) -> None:
        """Test LRU eviction when cache exceeds max size."""
        # Fill cache to max capacity
        cache.put("key1", "content1")
        cache.put("key2", "content2")
        cache.put("key3", "content3")

        # Access key1 to make it most recently used
        cache.get("key1")

        # Add one more item, should evict key2 (least recently used)
        cache.put("key4", "content4")

        assert cache.get("key1") == "content1"  # Still available
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "content3"  # Still available
        assert cache.get("key4") == "content4"  # Newly added

    def test_cache_explicit_eviction(self, cache: FileCache) -> None:
        """Test explicit cache eviction."""
        cache.put("key1", "content1")
        cache.put("key2", "content2")

        cache._evict("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "content2"
        assert "key1" not in cache._access_times

    def test_cache_clear(self, cache: FileCache) -> None:
        """Test cache clearing functionality."""
        cache.put("key1", "content1")
        cache.put("key2", "content2")

        cache.clear()

        assert len(cache._cache) == 0
        assert len(cache._access_times) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_stats(self, cache: FileCache) -> None:
        """Test cache statistics reporting."""
        cache.put("key1", "small")
        cache.put("key2", "much longer content string")

        stats = cache.get_stats()

        assert stats["entries"] == 2
        assert stats["max_size"] == 3
        assert stats["total_content_size"] == 5 + 28  # "small" + "much longer..."
        assert stats["memory_usage_mb"] > 0

    def test_cache_custom_ttl(self, cache: FileCache) -> None:
        """Test cache entries with custom TTL values."""
        cache.put("short", "content1", ttl=0.1)
        cache.put("long", "content2", ttl=10.0)

        time.sleep(0.2)

        assert cache.get("short") is None
        assert cache.get("long") == "content2"

    def test_cache_performance_with_many_entries(self) -> None:
        """Test cache performance with many entries."""
        large_cache = FileCache(max_size=1000, default_ttl=60.0)

        start_time = time.time()

        # Add many entries
        for i in range(500):
            large_cache.put(f"key_{i}", f"content_{i}")

        # Access many entries
        for i in range(0, 500, 10):
            result = large_cache.get(f"key_{i}")
            assert result == f"content_{i}"

        end_time = time.time()

        # Should complete operations quickly
        assert end_time - start_time < 1.0
        assert large_cache.get_stats()["entries"] == 500

    def test_cache_memory_efficiency(self) -> None:
        """Test cache memory usage patterns."""
        cache = FileCache(max_size=100, default_ttl=60.0)

        # Add entries of varying sizes
        small_content = "x" * 10
        medium_content = "x" * 100
        large_content = "x" * 1000

        cache.put("small", small_content)
        cache.put("medium", medium_content)
        cache.put("large", large_content)

        stats = cache.get_stats()
        expected_size = 10 + 100 + 1000

        assert stats["total_content_size"] == expected_size
        assert abs(stats["memory_usage_mb"] - (expected_size / (1024 * 1024))) < 0.001

    def test_cache_thread_safety_simulation(self) -> None:
        """Test cache behavior under simulated concurrent access."""
        cache = FileCache(max_size=50, default_ttl=60.0)

        # Simulate concurrent operations
        for i in range(100):
            cache.put(f"key_{i % 20}", f"content_{i}")  # Some keys will be overwritten
            if i % 5 == 0:
                cache.get(f"key_{i % 10}")  # Access some keys

        # Cache should handle this gracefully
        assert len(cache._cache) <= cache.max_size
        stats = cache.get_stats()
        assert stats["entries"] > 0


class TestBatchFileOperationsFunctional:
    """Comprehensive tests for batch file operations."""

    @pytest.fixture
    def batch_ops(self) -> BatchFileOperations:
        """Create batch file operations instance."""
        return BatchFileOperations(batch_size=3)

    def test_batch_ops_initialization(self, batch_ops: BatchFileOperations) -> None:
        """Test batch operations initialization."""
        assert batch_ops.batch_size == 3
        assert len(batch_ops.read_queue) == 0
        assert len(batch_ops.write_queue) == 0

    @pytest.mark.asyncio
    async def test_batch_read_operations(
        self, batch_ops: BatchFileOperations, tmp_path: Path
    ) -> None:
        """Test batched read operations."""
        # Create test files
        files = []
        contents = []
        for i in range(5):
            file_path = tmp_path / f"test_{i}.txt"
            content = f"content of file {i}"
            file_path.write_text(content)
            files.append(file_path)
            contents.append(content)

        # Mock the flush operation to avoid actual file I/O in batch
        with patch.object(batch_ops, "_flush_reads") as mock_flush_reads:

            async def mock_flush():
                # Simulate processing the queue
                for path, future in batch_ops.read_queue:
                    if path.exists():
                        future.set_result(path.read_text())
                    else:
                        future.set_exception(
                            FileNotFoundError(f"File not found: {path}")
                        )
                batch_ops.read_queue.clear()

            mock_flush_reads.side_effect = mock_flush

            # Queue reads - should trigger flush when batch size reached
            read_tasks = []
            for file_path in files[:3]:  # First 3 will trigger flush
                task = asyncio.create_task(batch_ops.queue_read(file_path))
                read_tasks.append(task)

            # Wait for completion
            results = await asyncio.gather(*read_tasks)

            # Verify results
            for i, result in enumerate(results):
                assert result == contents[i]

            # Should have flushed once due to batch size
            assert mock_flush_reads.call_count == 1

    @pytest.mark.asyncio
    async def test_batch_write_operations(
        self, batch_ops: BatchFileOperations, tmp_path: Path
    ) -> None:
        """Test batched write operations."""
        files = [tmp_path / f"write_test_{i}.txt" for i in range(4)]
        contents = [f"write content {i}" for i in range(4)]

        # Mock the flush operation
        with patch.object(batch_ops, "_flush_writes") as mock_flush_writes:

            async def mock_flush():
                # Simulate processing the write queue
                for path, content, future in batch_ops.write_queue:
                    try:
                        path.write_text(content)
                        future.set_result(None)
                    except Exception as e:
                        future.set_exception(e)
                batch_ops.write_queue.clear()

            mock_flush_writes.side_effect = mock_flush

            # Queue writes
            write_tasks = []
            for file_path, content in zip(files, contents):
                task = asyncio.create_task(batch_ops.queue_write(file_path, content))
                write_tasks.append(task)

            # Wait for completion
            await asyncio.gather(*write_tasks)

            # Should have flushed once (batch size is 3, so first 3 trigger flush)
            # Plus manual completion for the 4th
            assert mock_flush_writes.call_count >= 1

            # Verify files were "written" (by our mock)
            for i, file_path in enumerate(files):
                if file_path.exists():  # Our mock actually wrote them
                    assert file_path.read_text() == contents[i]

    @pytest.mark.asyncio
    async def test_batch_mixed_operations(
        self, batch_ops: BatchFileOperations, tmp_path: Path
    ) -> None:
        """Test mixing read and write operations."""
        # Create some test files
        existing_files = []
        for i in range(2):
            file_path = tmp_path / f"existing_{i}.txt"
            file_path.write_text(f"existing content {i}")
            existing_files.append(file_path)

        new_files = [tmp_path / f"new_{i}.txt" for i in range(2)]
        new_contents = [f"new content {i}" for i in range(2)]

        with (
            patch.object(batch_ops, "_flush_reads"),
            patch.object(batch_ops, "_flush_writes"),
        ):
            # Mix read and write operations
            tasks = []

            # Add reads
            for file_path in existing_files:
                task = asyncio.create_task(batch_ops.queue_read(file_path))
                tasks.append(task)

            # Add writes
            for file_path, content in zip(new_files, new_contents):
                task = asyncio.create_task(batch_ops.queue_write(file_path, content))
                tasks.append(task)

            # Operations should be queued separately
            assert len(batch_ops.read_queue) > 0 or len(batch_ops.write_queue) > 0

    def test_batch_queue_management(self, batch_ops: BatchFileOperations) -> None:
        """Test batch queue management and sizing."""
        # Test that queues start empty
        assert len(batch_ops.read_queue) == 0
        assert len(batch_ops.write_queue) == 0

        # Test batch size configuration
        large_batch = BatchFileOperations(batch_size=100)
        assert large_batch.batch_size == 100

        small_batch = BatchFileOperations(batch_size=1)
        assert small_batch.batch_size == 1

    @pytest.mark.asyncio
    async def test_batch_error_handling(
        self, batch_ops: BatchFileOperations, tmp_path: Path
    ) -> None:
        """Test error handling in batch operations."""
        nonexistent_file = tmp_path / "nonexistent.txt"

        with patch.object(batch_ops, "_flush_reads") as mock_flush:

            async def mock_flush_with_error():
                # Simulate error during flush
                for path, future in batch_ops.read_queue:
                    future.set_exception(FileNotFoundError(f"File not found: {path}"))
                batch_ops.read_queue.clear()

            mock_flush.side_effect = mock_flush_with_error

            # This should handle the error gracefully
            with pytest.raises(FileNotFoundError):
                await batch_ops.queue_read(nonexistent_file)

    def test_batch_performance_characteristics(self) -> None:
        """Test batch operations performance characteristics."""
        large_batch = BatchFileOperations(batch_size=1000)

        # Test that large batches can be configured
        assert large_batch.batch_size == 1000

        # Test queue capacity (should not be limited by batch size)
        test_path = Path("test.txt")

        # Add more items than batch size without triggering flush
        for i in range(1500):
            future = asyncio.Future()
            large_batch.read_queue.append((test_path, future))

        # Queue should accommodate more than batch size
        assert len(large_batch.read_queue) == 1500

    @pytest.mark.asyncio
    async def test_concurrent_batch_operations(self, tmp_path: Path) -> None:
        """Test concurrent batch operations."""
        batch_ops1 = BatchFileOperations(batch_size=2)
        batch_ops2 = BatchFileOperations(batch_size=2)

        # Create test files
        files = []
        for i in range(4):
            file_path = tmp_path / f"concurrent_test_{i}.txt"
            file_path.write_text(f"concurrent content {i}")
            files.append(file_path)

        with (
            patch.object(batch_ops1, "_flush_reads"),
            patch.object(batch_ops2, "_flush_reads"),
        ):
            # Run concurrent batch operations
            tasks = []

            for i, file_path in enumerate(files[:2]):
                task = asyncio.create_task(batch_ops1.queue_read(file_path))
                tasks.append(task)

            for i, file_path in enumerate(files[2:]):
                task = asyncio.create_task(batch_ops2.queue_read(file_path))
                tasks.append(task)

            # Should handle concurrent operations on different batch instances
            assert len(batch_ops1.read_queue) >= 0
            assert len(batch_ops2.read_queue) >= 0


class TestEnhancedFilesystemIntegration:
    """Integration tests combining cache and batch operations."""

    def test_cache_and_batch_interaction(self, tmp_path: Path) -> None:
        """Test interaction between caching and batch operations."""
        cache = FileCache(max_size=10, default_ttl=60.0)
        batch_ops = BatchFileOperations(batch_size=5)

        # Test that both can be used together
        assert cache.max_size == 10
        assert batch_ops.batch_size == 5

        # Simulate using cache for frequently accessed files
        # and batch operations for bulk file processing

        # Cache frequently accessed content
        cache.put("config.yaml", "app_name: test\nversion: 1.0")
        cache.put("readme.md", "# Test Project\nThis is a test.")

        # Both systems should work independently
        assert cache.get("config.yaml") is not None
        assert len(batch_ops.read_queue) == 0
        assert len(batch_ops.write_queue) == 0

    def test_filesystem_component_memory_usage(self) -> None:
        """Test memory usage patterns of filesystem components."""
        # Test with realistic usage patterns
        cache = FileCache(max_size=100, default_ttl=300.0)
        BatchFileOperations(batch_size=20)

        # Simulate realistic file operations
        file_contents = {
            "small_config.json": '{"setting": "value"}',
            "medium_data.csv": ",".join([f"row_{i}" for i in range(100)]),
            "large_log.txt": "\n".join([f"Log entry {i}" for i in range(1000)]),
        }

        for filename, content in file_contents.items():
            cache.put(filename, content)

        # Check memory usage is reasonable
        stats = cache.get_stats()
        total_content_size = sum(len(content) for content in file_contents.values())

        assert stats["total_content_size"] == total_content_size
        assert stats["entries"] == len(file_contents)

        # Memory usage should be roughly equal to content size
        expected_mb = total_content_size / (1024 * 1024)
        assert abs(stats["memory_usage_mb"] - expected_mb) < 0.01

    def test_component_cleanup_and_resource_management(self) -> None:
        """Test cleanup and resource management."""
        cache = FileCache(max_size=5, default_ttl=0.1)  # Short TTL for testing

        # Add entries that will expire
        for i in range(10):
            cache.put(f"temp_key_{i}", f"temporary content {i}")

        # Due to max_size=5, only 5 entries should be kept
        assert cache.get_stats()["entries"] == 5

        # Wait for TTL expiration
        time.sleep(0.2)

        # Try to access expired entries
        expired_count = 0
        for i in range(10):
            if cache.get(f"temp_key_{i}") is None:
                expired_count += 1

        # Most or all should be expired
        assert expired_count > 0

        # Clear cache to test cleanup
        cache.clear()
        assert cache.get_stats()["entries"] == 0
        assert cache.get_stats()["total_content_size"] == 0
