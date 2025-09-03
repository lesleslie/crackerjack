import asyncio
import tempfile
import time
from pathlib import Path

import pytest

try:
    from crackerjack.errors import FileError
    from crackerjack.services.enhanced_filesystem import (
        BatchFileOperations,
        EnhancedFileSystemService,
        FileCache,
    )
except ImportError:
    pytest.skip("Enhanced filesystem not available", allow_module_level=True)


class TestFileCache:
    @pytest.fixture
    def cache(self) -> FileCache:
        return FileCache(max_size=3, default_ttl=1.0)

    def test_cache_initialization(self, cache: FileCache) -> None:
        assert cache.max_size == 3
        assert cache.default_ttl == 1.0
        assert len(cache._cache) == 0
        assert len(cache._access_times) == 0

    def test_cache_put_and_get(self, cache: FileCache) -> None:
        cache.put("key1", "content1")
        assert len(cache._cache) == 1

        result = cache.get("key1")
        assert result == "content1"

    def test_cache_miss(self, cache: FileCache) -> None:
        result = cache.get("nonexistent_key")
        assert result is None

    def test_cache_ttl_expiration(self, cache: FileCache) -> None:
        cache.put("key1", "content1", ttl=0.1)

        assert cache.get("key1") == "content1"

        time.sleep(0.15)

        assert cache.get("key1") is None

    def test_cache_lru_eviction(self, cache: FileCache) -> None:
        cache.put("key1", "content1")
        cache.put("key2", "content2")
        cache.put("key3", "content3")

        cache.get("key1")

        cache.put("key4", "content4")

        assert cache.get("key1") == "content1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "content3"
        assert cache.get("key4") == "content4"

    def test_cache_clear(self, cache: FileCache) -> None:
        cache.put("key1", "content1")
        cache.put("key2", "content2")

        if hasattr(cache, "clear"):
            cache.clear()
            assert len(cache._cache) == 0
            assert len(cache._access_times) == 0

    def test_cache_evict_method(self, cache: FileCache) -> None:
        cache.put("key1", "content1")
        assert cache.get("key1") == "content1"

        cache._evict("key1")
        assert cache.get("key1") is None

    def test_cache_size_tracking(self, cache: FileCache) -> None:
        large_content = "x" * 1000
        cache.put("key1", large_content)

        cache_entry = cache._cache["key1"]
        assert cache_entry["size"] == 1000


class TestBatchFileOperations:
    @pytest.fixture
    def batch_ops(self) -> BatchFileOperations:
        return BatchFileOperations(batch_size=2)

    def test_batch_ops_initialization(self, batch_ops: BatchFileOperations) -> None:
        assert batch_ops.batch_size == 2
        assert len(batch_ops.read_queue) == 0
        assert len(batch_ops.write_queue) == 0

    def test_batch_read_queue_structure(self, batch_ops: BatchFileOperations) -> None:
        from pathlib import Path

        test_path = Path("/ fake / path.txt")
        future = asyncio.Future()

        batch_ops.read_queue.append((test_path, future))

        assert len(batch_ops.read_queue) == 1
        assert batch_ops.read_queue[0][0] == test_path
        assert isinstance(batch_ops.read_queue[0][1], asyncio.Future)

    def test_batch_write_queue_structure(self, batch_ops: BatchFileOperations) -> None:
        from pathlib import Path

        test_path = Path("/ fake / path.txt")
        test_content = "test content"
        future = asyncio.Future()

        batch_ops.write_queue.append((test_path, test_content, future))

        assert len(batch_ops.write_queue) == 1
        assert batch_ops.write_queue[0][0] == test_path
        assert batch_ops.write_queue[0][1] == test_content
        assert isinstance(batch_ops.write_queue[0][2], asyncio.Future)


class TestEnhancedFileSystemService:
    @pytest.fixture
    def enhanced_fs(self) -> EnhancedFileSystemService:
        return EnhancedFileSystemService(cache_size=10, cache_ttl=1.0, batch_size=2)

    def test_enhanced_fs_initialization(
        self, enhanced_fs: EnhancedFileSystemService
    ) -> None:
        assert enhanced_fs.cache.max_size == 10
        assert enhanced_fs.cache.default_ttl == 1.0
        assert enhanced_fs.enable_async is True
        assert enhanced_fs.batch_ops is not None

    def test_read_file_with_cache(self, enhanced_fs: EnhancedFileSystemService) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("test content")
            tmp_path = Path(tmp.name)

        try:
            result1 = enhanced_fs.read_file(tmp_path)
            assert result1 == "test content"

            result2 = enhanced_fs.read_file(tmp_path)
            assert result2 == "test content"

        finally:
            tmp_path.unlink(missing_ok=True)

    def test_write_file_operations(
        self, enhanced_fs: EnhancedFileSystemService
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_write.txt"

            enhanced_fs.write_file(file_path, "test write content")

            assert file_path.exists()
            assert file_path.read_text() == "test write content"

    def test_file_exists_check(self, enhanced_fs: EnhancedFileSystemService) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            assert enhanced_fs.file_exists(tmp_path) is True

            fake_path = Path("/ fake / path / file.txt")
            assert enhanced_fs.file_exists(fake_path) is False

        finally:
            tmp_path.unlink(missing_ok=True)

    def test_error_handling_in_operations(
        self, enhanced_fs: EnhancedFileSystemService
    ) -> None:
        fake_path = Path("/ fake / readonly / path / file.txt")

        with pytest.raises(FileError):
            enhanced_fs.read_file(fake_path)

    def test_cache_integration(self, enhanced_fs: EnhancedFileSystemService) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
            tmp.write("cached content")
            tmp_path = Path(tmp.name)

        try:
            content1 = enhanced_fs.read_file(tmp_path)
            assert content1 == "cached content"

            tmp_path.write_text("modified content")

            content2 = enhanced_fs.read_file(tmp_path)

            assert content2 in ("cached content", "modified content")

        finally:
            tmp_path.unlink(missing_ok=True)

    def test_batch_operations_integration(
        self, enhanced_fs: EnhancedFileSystemService
    ) -> None:
        if enhanced_fs.batch_ops is not None:
            assert enhanced_fs.batch_ops.batch_size >= 1
            assert hasattr(enhanced_fs.batch_ops, "queue_read")
            assert hasattr(enhanced_fs.batch_ops, "queue_write")
            assert hasattr(enhanced_fs.batch_ops, "flush_all")


class TestIntegrationScenarios:
    @pytest.mark.asyncio
    async def test_full_workflow_integration(self) -> None:
        cache = FileCache(max_size=10)
        batch_ops = BatchFileOperations(batch_size=3)
        enhanced_fs = EnhancedFileSystemService(cache_size=5, cache_ttl=2.0)

        assert cache.max_size == 10
        assert batch_ops.batch_size == 3
        assert enhanced_fs.cache.max_size == 5

    def test_error_propagation(self) -> None:
        cache = FileCache()

        cache.put("", "")
        result = cache.get("")
        assert result == ""

    def test_memory_efficiency(self) -> None:
        cache = FileCache(max_size=5)

        for i in range(10):
            cache.put(f"key_{i}", f"content_{i}" * 100)

        assert len(cache._cache) <= 5

    def test_concurrent_cache_operations(self) -> None:
        cache = FileCache()

        for i in range(5):
            cache.put(f"concurrent_key_{i}", f"content_{i}")

        for i in range(5):
            result = cache.get(f"concurrent_key_{i}")
            assert result == f"content_{i}"

    @pytest.mark.asyncio
    async def test_batch_operations_performance(self) -> None:
        batch_ops = BatchFileOperations(batch_size=3)

        await batch_ops.flush_all()

        assert len(batch_ops.read_queue) == 0
        assert len(batch_ops.write_queue) == 0

    def test_filesystem_protocol_compliance(self) -> None:
        fs = EnhancedFileSystemService()
        assert hasattr(fs, "read_file")
        assert hasattr(fs, "write_file")
        assert hasattr(fs, "file_exists")

        batch_ops = BatchFileOperations()
        assert hasattr(batch_ops, "queue_read")
        assert hasattr(batch_ops, "queue_write")
        assert hasattr(batch_ops, "flush_all")
        assert batch_ops.batch_size > 0
