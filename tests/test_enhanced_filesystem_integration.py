import time

import pytest

from crackerjack.services.enhanced_filesystem import (
    BatchFileOperations,
    FileCache,
)


class TestFileCacheAdvanced:
    @pytest.fixture
    def cache(self) -> FileCache:
        return FileCache(max_size=3, default_ttl=1.0)

    def test_cache_initialization(self, cache: FileCache) -> None:
        assert cache.max_size == 3
        assert cache.default_ttl == 1.0
        assert len(cache._cache) == 0
        assert len(cache._access_times) == 0

    def test_cache_put_and_get_basic(self, cache: FileCache) -> None:
        cache.put("key1", "content1")

        result = cache.get("key1")
        assert result == "content1"
        assert "key1" in cache._cache
        assert "key1" in cache._access_times

    def test_cache_get_nonexistent(self, cache: FileCache) -> None:
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_ttl_expiration(self, cache: FileCache) -> None:
        cache.put("key1", "content1", ttl=0.1)

        assert cache.get("key1") == "content1"

        time.sleep(0.2)
        assert cache.get("key1") is None
        assert "key1" not in cache._cache

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

    def test_cache_explicit_eviction(self, cache: FileCache) -> None:
        cache.put("key1", "content1")
        cache.put("key2", "content2")

        cache._evict("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "content2"
        assert "key1" not in cache._access_times

    def test_cache_clear(self, cache: FileCache) -> None:
        cache.put("key1", "content1")
        cache.put("key2", "content2")

        cache.clear()

        assert len(cache._cache) == 0
        assert len(cache._access_times) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_size_tracking(self, cache: FileCache) -> None:
        cache.put("key1", "small")
        cache.put("key2", "much longer content string")

        assert cache._cache["key1"]["size"] == 5
        assert cache._cache["key2"]["size"] == 26
        assert len(cache._cache) == 2

    def test_cache_custom_ttl(self, cache: FileCache) -> None:
        cache.put("short", "content1", ttl=0.1)
        cache.put("long", "content2", ttl=10.0)

        time.sleep(0.2)

        assert cache.get("short") is None
        assert cache.get("long") == "content2"

    def test_cache_get_stats(self, cache: FileCache) -> None:
        cache.put("key1", "content1")
        cache.put("key2", "longer content string here")

        stats = cache.get_stats()
        assert stats["entries"] == 2
        assert stats["max_size"] == 3
        assert stats["total_content_size"] == 8 + 26
        assert "memory_usage_mb" in stats


class TestBatchFileOperationsBasic:
    @pytest.fixture
    def batch(self) -> BatchFileOperations:
        return BatchFileOperations(batch_size=3)

    def test_batch_initialization(self, batch: BatchFileOperations) -> None:
        assert batch.batch_size == 3
        assert len(batch.read_queue) == 0
        assert len(batch.write_queue) == 0

    def test_batch_basic_functionality(self, batch: BatchFileOperations) -> None:
        assert batch.batch_size == 3
        assert len(batch.read_queue) == 0
        assert len(batch.write_queue) == 0
