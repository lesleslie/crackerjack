import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from crackerjack.models.task import HookResult
from crackerjack.services.cache import (
    CacheEntry,
    CacheStats,
    CrackerjackCache,
    FileCache,
    InMemoryCache,
)


class TestCacheEntry:
    def test_cache_entry_creation(self) -> None:
        entry = CacheEntry(key="test_key", value="test_value")

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.ttl_seconds == 3600
        assert entry.access_count == 0
        assert isinstance(entry.created_at, float)
        assert isinstance(entry.accessed_at, float)

    def test_is_expired_not_expired(self) -> None:
        entry = CacheEntry(key="test", value="data", ttl_seconds=10)

        assert entry.is_expired is False

    def test_is_expired_expired(self) -> None:
        entry = CacheEntry(key="test", value="data", ttl_seconds=1)

        with patch("time.time", return_value=entry.created_at + 2):
            assert entry.is_expired is True

    def test_age_seconds(self) -> None:
        entry = CacheEntry(key="test", value="data")

        with patch("time.time", return_value=entry.created_at + 5):
            assert entry.age_seconds == 5

    def test_touch(self) -> None:
        entry = CacheEntry(key="test", value="data")
        initial_access_count = entry.access_count
        initial_accessed_at = entry.accessed_at

        time.sleep(0.01)
        entry.touch()

        assert entry.access_count == initial_access_count + 1
        assert entry.accessed_at > initial_accessed_at


class TestCacheStats:
    def test_cache_stats_creation(self) -> None:
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.total_entries == 0
        assert stats.total_size_bytes == 0

    def test_hit_rate_zero_requests(self) -> None:
        stats = CacheStats()

        assert stats.hit_rate == 0.0

    def test_hit_rate_with_data(self) -> None:
        stats = CacheStats(hits=75, misses=25)

        assert stats.hit_rate == 75.0

    def test_to_dict(self) -> None:
        stats = CacheStats(
            hits=10,
            misses=5,
            evictions=2,
            total_entries=8,
            total_size_bytes=1024 * 1024,
        )

        result = stats.to_dict()

        expected = {
            "hits": 10,
            "misses": 5,
            "evictions": 2,
            "total_entries": 8,
            "hit_rate_percent": 66.67,
            "total_size_mb": 1.0,
        }

        assert result == expected


class TestInMemoryCache:
    def test_inmemorycache_creation(self) -> None:
        cache = InMemoryCache()

        assert cache.max_entries == 1000
        assert cache.default_ttl == 3600
        assert isinstance(cache.stats, CacheStats)
        assert len(cache._cache) == 0

    def test_inmemorycache_custom_params(self) -> None:
        cache = InMemoryCache(max_entries=500, default_ttl=1800)

        assert cache.max_entries == 500
        assert cache.default_ttl == 1800

    def test_get_miss(self) -> None:
        cache = InMemoryCache()

        result = cache.get("nonexistent")

        assert result is None
        assert cache.stats.misses == 1
        assert cache.stats.hits == 0

    def test_set_and_get_hit(self) -> None:
        cache = InMemoryCache()

        cache.set("test_key", "test_value")
        result = cache.get("test_key")

        assert result == "test_value"
        assert cache.stats.hits == 1
        assert cache.stats.misses == 0

    def test_get_expired_entry(self) -> None:
        cache = InMemoryCache()
        cache.set("test_key", "test_value", ttl_seconds=1)

        original_entry = cache._cache["test_key"]
        with patch("time.time", return_value=original_entry.created_at + 2):
            result = cache.get("test_key")

        assert result is None
        assert cache.stats.misses == 1
        assert cache.stats.evictions == 1
        assert "test_key" not in cache._cache

    def test_set_with_custom_ttl(self) -> None:
        cache = InMemoryCache()

        cache.set("test_key", "test_value", ttl_seconds=7200)
        entry = cache._cache["test_key"]

        assert entry.ttl_seconds == 7200

    def test_set_with_max_entries_eviction(self) -> None:
        cache = InMemoryCache(max_entries=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.get("key1")

        cache.set("key3", "value3")

        assert "key1" in cache._cache
        assert "key2" not in cache._cache
        assert "key3" in cache._cache
        assert cache.stats.evictions == 1

    def test_invalidate_existing_key(self) -> None:
        cache = InMemoryCache()
        cache.set("test_key", "test_value")

        result = cache.invalidate("test_key")

        assert result is True
        assert "test_key" not in cache._cache
        assert cache.stats.total_entries == 0

    def test_invalidate_nonexistent_key(self) -> None:
        cache = InMemoryCache()

        result = cache.invalidate("nonexistent")

        assert result is False

    def test_clear(self) -> None:
        cache = InMemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert len(cache._cache) == 0
        assert cache.stats.evictions == 2
        assert cache.stats.total_entries == 0

    def test_cleanup_expired(self) -> None:
        cache = InMemoryCache()

        cache.set("valid_key", "valid_value", ttl_seconds=3600)
        cache.set("expired_key1", "expired_value1", ttl_seconds=1)
        cache.set("expired_key2", "expired_value2", ttl_seconds=1)

        original_entries = list(cache._cache.values())
        with patch("time.time", return_value=original_entries[0].created_at + 2):
            removed_count = cache.cleanup_expired()

        assert removed_count == 2
        assert "valid_key" in cache._cache
        assert "expired_key1" not in cache._cache
        assert "expired_key2" not in cache._cache
        assert cache.stats.evictions == 2


class TestFileCache:
    def test_filecache_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            cache = FileCache(cache_dir, namespace="test")

            assert cache.cache_dir == cache_dir / "test"
            assert cache.cache_dir.exists()
            assert isinstance(cache.stats, CacheStats)

    def test_get_miss(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))

            result = cache.get("nonexistent")

            assert result is None
            assert cache.stats.misses == 1

    def test_set_and_get_hit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))

            cache.set("test_key", "test_value")
            result = cache.get("test_key")

            assert result == "test_value"
            assert cache.stats.hits == 1

    def test_get_expired_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))
            cache.set("test_key", "test_value", ttl_seconds=1)

            with patch("time.time", return_value=time.time() + 2):
                result = cache.get("test_key")

            assert result is None
            assert cache.stats.misses == 1
            assert cache.stats.evictions == 1

    def test_set_with_custom_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))

            cache.set("test_key", "test_value", ttl_seconds=7200)

            cache_file = cache._get_cache_file("test_key")
            with cache_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["ttl_seconds"] == 7200

    def test_invalidate_existing_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))
            cache.set("test_key", "test_value")

            result = cache.invalidate("test_key")

            assert result is True
            cache_file = cache._get_cache_file("test_key")
            assert not cache_file.exists()

    def test_invalidate_nonexistent_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))

            result = cache.invalidate("nonexistent")

            assert result is False

    def test_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))
            cache.set("key1", "value1")
            cache.set("key2", "value2")

            cache.clear()

            cache_files = list(cache.cache_dir.glob(" * .cache"))
            assert len(cache_files) == 0

    def test_cleanup_expired(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))

            cache.set("valid_key", "valid_value", ttl_seconds=3600)
            cache.set("expired_key", "expired_value", ttl_seconds=1)

            with patch("time.time", return_value=time.time() + 2):
                removed_count = cache.cleanup_expired()

            assert removed_count == 1
            assert cache.stats.evictions == 1

    def test_get_with_corrupted_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = FileCache(Path(temp_dir))

            cache_file = cache._get_cache_file("corrupted_key")
            cache_file.write_text("invalid pickle data")

            result = cache.get("corrupted_key")

            assert result is None
            assert cache.stats.misses == 1
            assert not cache_file.exists()


class TestCrackerjackCache:
    def test_crackerjackcache_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            cache = CrackerjackCache(cache_dir=cache_dir)

            assert cache.cache_dir == cache_dir
            assert cache.enable_disk_cache is True
            assert isinstance(cache.hook_results_cache, InMemoryCache)
            assert isinstance(cache.file_hash_cache, InMemoryCache)
            assert isinstance(cache.config_cache, InMemoryCache)
            assert hasattr(cache, "disk_cache")

    def test_crackerjackcache_without_disk_cache(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        assert cache.enable_disk_cache is False
        assert not hasattr(cache, "disk_cache")

    def test_get_hook_result_miss(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        result = cache.get_hook_result("test_hook", ["hash1", "hash2"])

        assert result is None

    def test_set_and_get_hook_result(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        hook_result = HookResult(
            id="test_hook_id",
            name="test_hook",
            status="success",
            duration=1.5,
            files_processed=2,
            issues_found=[],
        )

        cache.set_hook_result("test_hook", ["hash1", "hash2"], hook_result)
        result = cache.get_hook_result("test_hook", ["hash1", "hash2"])

        assert result == hook_result

    def test_get_file_hash_miss(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)
            result = cache.get_file_hash(temp_path)

            assert result is None

    def test_set_and_get_file_hash(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)
            test_hash = "abc123def456"

            cache.set_file_hash(temp_path, test_hash)
            result = cache.get_file_hash(temp_path)

            assert result == test_hash

    def test_get_config_data_miss(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        result = cache.get_config_data("test_config")

        assert result is None

    def test_set_and_get_config_data(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        test_data = {"key": "value", "number": 42}

        cache.set_config_data("test_config", test_data)
        result = cache.get_config_data("test_config")

        assert result == test_data

    def test_invalidate_hook_cache_specific(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        hook_result = HookResult(
            id="test_hook_id",
            name="test_hook",
            status="success",
            duration=1.0,
            files_processed=1,
            issues_found=[],
        )

        cache.set_hook_result("test_hook", ["hash1"], hook_result)
        cache.set_hook_result("other_hook", ["hash2"], hook_result)

        cache.invalidate_hook_cache("test_hook")

        assert cache.get_hook_result("test_hook", ["hash1"]) is None
        assert cache.get_hook_result("other_hook", ["hash2"]) is not None

    def test_invalidate_hook_cache_all(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        hook_result = HookResult(
            id="test_hook_id",
            name="test_hook",
            status="success",
            duration=1.0,
            files_processed=1,
            issues_found=[],
        )

        cache.set_hook_result("test_hook", ["hash1"], hook_result)
        cache.set_hook_result("other_hook", ["hash2"], hook_result)

        cache.invalidate_hook_cache()

        assert cache.get_hook_result("test_hook", ["hash1"]) is None
        assert cache.get_hook_result("other_hook", ["hash2"]) is None

    def test_cleanup_all_without_disk_cache(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        results = cache.cleanup_all()

        assert "hook_results" in results
        assert "file_hashes" in results
        assert "config" in results
        assert "disk_cache" not in results

    def test_cleanup_all_with_disk_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = CrackerjackCache(cache_dir=Path(temp_dir), enable_disk_cache=True)

            results = cache.cleanup_all()

            assert "hook_results" in results
            assert "file_hashes" in results
            assert "config" in results
            assert "disk_cache" in results

    def test_get_cache_stats_without_disk_cache(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        stats = cache.get_cache_stats()

        assert "hook_results" in stats
        assert "file_hashes" in stats
        assert "config" in stats
        assert "disk_cache" not in stats

    def test_get_cache_stats_with_disk_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = CrackerjackCache(cache_dir=Path(temp_dir), enable_disk_cache=True)

            stats = cache.get_cache_stats()

            assert "hook_results" in stats
            assert "file_hashes" in stats
            assert "config" in stats
            assert "disk_cache" in stats

    def test_hook_cache_key_generation(self) -> None:
        cache = CrackerjackCache(enable_disk_cache=False)

        key1 = cache._get_hook_cache_key("test_hook", ["hash1", "hash2"])
        key2 = cache._get_hook_cache_key("test_hook", ["hash2", "hash1"])

        assert key1 == key2

        key3 = cache._get_hook_cache_key("test_hook", ["hash1", "hash2"])
        assert key1 == key3
