import asyncio

import pytest

from crackerjack.services.enhanced_filesystem import (
    EnhancedFileSystemService,
    FileCache,
)


class TestFileCache:
    def test_cache_initialization(self):
        cache = FileCache()
        assert cache is not None
        assert hasattr(cache, "max_size")
        assert hasattr(cache, "default_ttl")
        assert hasattr(cache, "_cache")
        assert hasattr(cache, "_access_times")

    def test_cache_with_custom_params(self):
        cache = FileCache(max_size=500, default_ttl=120.0)
        assert cache.max_size == 500
        assert cache.default_ttl == 120.0

    def test_cache_default_values(self):
        cache = FileCache()
        assert cache.max_size == 1000
        assert cache.default_ttl == 300.0
        assert isinstance(cache._cache, dict)
        assert isinstance(cache._access_times, dict)

    def test_cache_put_basic(self):
        cache = FileCache()
        cache.put("test_key", "test_value")

        assert "test_key" in cache._cache
        assert "test_key" in cache._access_times

    def test_cache_get_basic(self):
        cache = FileCache()
        cache.put("test_key", "test_value")

        result = cache.get("test_key")
        assert result == "test_value"

    def test_cache_get_nonexistent(self):
        cache = FileCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_contains(self):
        cache = FileCache()
        cache.put("test_key", "test_value")

        assert cache.get("test_key") is not None
        assert cache.get("nonexistent") is None

    def test_cache_clear(self):
        cache = FileCache()
        cache.put("test_key", "test_value")
        cache.clear()

        assert len(cache._cache) == 0
        assert len(cache._access_times) == 0

    def test_cache_size(self):
        cache = FileCache()
        assert cache.get_stats()["entries"] == 0

        cache.put("key1", "value1")
        assert cache.get_stats()["entries"] == 1

        cache.put("key2", "value2")
        assert cache.get_stats()["entries"] == 2


class TestEnhancedFileSystemService:
    def test_filesystem_initialization(self):
        fs = EnhancedFileSystemService()
        assert fs is not None
        assert hasattr(fs, "cache")

    def test_filesystem_with_cache_size(self):
        fs = EnhancedFileSystemService(cache_size=500)
        assert fs.cache is not None
        assert fs.cache.max_size == 500

    def test_filesystem_default_cache(self):
        fs = EnhancedFileSystemService()
        assert fs.cache is not None
        assert isinstance(fs.cache, FileCache)

    @pytest.mark.asyncio
    async def test_filesystem_async_context(self):
        async def create_filesystem():
            return EnhancedFileSystemService()

        fs = await create_filesystem()
        assert fs is not None

    def test_filesystem_has_required_methods(self):
        fs = EnhancedFileSystemService()

        expected_attrs = ["cache"]

        for attr in expected_attrs:
            assert hasattr(fs, attr), f"Missing attribute: {attr}"

    @pytest.mark.asyncio
    async def test_filesystem_async_operations_basic(self):
        fs = EnhancedFileSystemService()

        assert fs.cache is not None
        fs.cache.put("async_test", "value")
        result = fs.cache.get("async_test")
        assert result == "value"

    def test_filesystem_cache_integration(self):
        fs = EnhancedFileSystemService()

        assert fs.cache.get_stats()["entries"] == 0
        fs.cache.put("integration_test", "data")
        assert fs.cache.get_stats()["entries"] == 1
        assert fs.cache.get("integration_test") is not None

    def test_multiple_filesystem_instances(self):
        fs1 = EnhancedFileSystemService()
        fs2 = EnhancedFileSystemService()

        assert fs1 is not fs2
        assert fs1.cache is not fs2.cache

        fs1.cache.put("fs1_key", "fs1_value")
        fs2.cache.put("fs2_key", "fs2_value")

        assert fs1.cache.get("fs1_key") == "fs1_value"
        assert fs2.cache.get("fs2_key") == "fs2_value"
        assert fs1.cache.get("fs2_key") is None
        assert fs2.cache.get("fs1_key") is None


class TestEnhancedFileSystemServiceEdgeCases:
    def test_filesystem_with_zero_cache_size(self):
        fs = EnhancedFileSystemService(cache_size=0)
        assert fs.cache.max_size == 0

    def test_filesystem_with_large_cache_size(self):
        fs = EnhancedFileSystemService(cache_size=10000)
        assert fs.cache.max_size == 10000

    def test_cache_with_special_characters(self):
        cache = FileCache()
        special_key = "key - with - special@chars#"
        cache.put(special_key, "special_value")

        assert cache.get(special_key) is not None
        assert cache.get(special_key) == "special_value"

    def test_cache_with_empty_value(self):
        cache = FileCache()
        cache.put("empty_key", "")

        assert cache.get("empty_key") == ""
        assert "empty_key" in cache._cache

    def test_cache_overwrite_value(self):
        cache = FileCache()
        cache.put("overwrite_key", "original")
        cache.put("overwrite_key", "updated")

        result = cache.get("overwrite_key")
        assert result == "updated"

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        cache = FileCache()

        async def put_operation(key: str, value: str):
            cache.put(key, value)

        async def get_operation(key: str):
            return cache.get(key)

        await asyncio.gather(
            put_operation("key1", "value1"),
            put_operation("key2", "value2"),
            put_operation("key3", "value3"),
        )

        assert cache.get_stats()["entries"] == 3

        results = await asyncio.gather(
            get_operation("key1"), get_operation("key2"), get_operation("key3")
        )

        assert results == ["value1", "value2", "value3"]
