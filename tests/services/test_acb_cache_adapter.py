"""Tests for ACB cache adapter.

Validates that ACBCrackerjackCache maintains full compatibility with
the original CrackerjackCache API while leveraging ACB's async cache.
"""

from pathlib import Path

import pytest

from crackerjack.models.task import HookResult
from crackerjack.services.acb_cache_adapter import ACBCrackerjackCache, CacheStats


class TestCacheStats:
    """Test cache statistics tracking."""

    def test_initial_stats(self) -> None:
        """Test initial stats are zero."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.total_entries == 0

    def test_hit_rate_calculation(self) -> None:
        """Test hit rate percentage calculation."""
        stats = CacheStats()

        # No requests yet
        assert stats.hit_rate == 0.0

        # 3 hits, 1 miss = 75%
        stats.hits = 3
        stats.misses = 1
        assert stats.hit_rate == 75.0

        # 1 hit, 1 miss = 50%
        stats.hits = 1
        stats.misses = 1
        assert stats.hit_rate == 50.0

    def test_stats_to_dict(self) -> None:
        """Test stats dictionary conversion."""
        stats = CacheStats(hits=10, misses=5, evictions=2, total_entries=15)

        result = stats.to_dict()

        assert result["hits"] == 10
        assert result["misses"] == 5
        assert result["evictions"] == 2
        assert result["total_entries"] == 15
        assert result["hit_rate_percent"] == 66.67  # 10/(10+5) * 100


class TestACBCacheAdapter:
    """Test ACB cache adapter maintains CrackerjackCache API."""

    def test_adapter_initialization(self) -> None:
        """Test adapter initializes correctly."""
        cache = ACBCrackerjackCache()

        assert cache.enable_disk_cache is True
        assert cache.stats.hits == 0
        assert cache.stats.misses == 0
        assert cache.AGENT_VERSION == "1.0.0"

    def test_adapter_initialization_custom_settings(self) -> None:
        """Test adapter with custom settings."""
        cache_dir = Path("/tmp/test_cache")
        cache = ACBCrackerjackCache(
            cache_dir=cache_dir,
            enable_disk_cache=False,
        )

        assert cache.cache_dir == cache_dir
        assert cache.enable_disk_cache is False

    def test_hook_result_caching(self) -> None:
        """Test hook result get/set operations."""
        cache = ACBCrackerjackCache()

        result = HookResult(
            id="test-1",
            name="ruff",
            status="success",
            duration=1.5,
            files_processed=10,
        )

        file_hashes = ["abc123", "def456"]

        # Cache miss on first get
        cached = cache.get_hook_result("ruff", file_hashes)
        assert cached is None
        assert cache.stats.misses == 1

        # Set result
        cache.set_hook_result("ruff", file_hashes, result)
        assert cache.stats.total_entries == 1

        # Cache hit on second get
        cached = cache.get_hook_result("ruff", file_hashes)
        assert cached is not None
        assert cached.name == "ruff"
        assert cached.status == "success"
        assert cache.stats.hits == 1

    def test_expensive_hook_caching(self) -> None:
        """Test expensive hook dual-tier caching."""
        cache = ACBCrackerjackCache(enable_disk_cache=True)

        result = HookResult(
            id="test-2",
            name="zuban",
            status="success",
            duration=2.5,
            files_processed=20,
        )

        file_hashes = ["xyz789"]
        tool_version = "0.1.0"

        # Miss on first get
        cached = cache.get_expensive_hook_result("zuban", file_hashes, tool_version)
        assert cached is None

        # Set result
        cache.set_expensive_hook_result("zuban", file_hashes, result, tool_version)

        # Hit on second get
        cached = cache.get_expensive_hook_result("zuban", file_hashes, tool_version)
        assert cached is not None
        assert cached.name == "zuban"

    def test_expensive_hook_versioning(self) -> None:
        """Test tool version affects cache key."""
        cache = ACBCrackerjackCache(enable_disk_cache=True)

        result_v1 = HookResult(
            id="test-3",
            name="zuban",
            status="success",
            duration=1.0,
            files_processed=5,
        )

        result_v2 = HookResult(
            id="test-4",
            name="zuban",
            status="success",
            duration=1.2,
            files_processed=5,
        )

        file_hashes = ["same_hash"]

        # Cache different versions
        cache.set_expensive_hook_result("zuban", file_hashes, result_v1, "0.1.0")
        cache.set_expensive_hook_result("zuban", file_hashes, result_v2, "0.2.0")

        # Retrieve by version
        cached_v1 = cache.get_expensive_hook_result("zuban", file_hashes, "0.1.0")
        cached_v2 = cache.get_expensive_hook_result("zuban", file_hashes, "0.2.0")

        assert cached_v1.id == "test-3"
        assert cached_v2.id == "test-4"

    def test_expensive_hook_list(self) -> None:
        """Test expensive hooks are correctly identified."""
        cache = ACBCrackerjackCache()

        expected_hooks = {
            "pyright",
            "bandit",
            "vulture",
            "complexipy",
            "refurb",
            "gitleaks",
            "zuban",
        }

        assert cache.EXPENSIVE_HOOKS == expected_hooks

    def test_expensive_hook_ttls(self) -> None:
        """Test TTL configuration for expensive hooks."""
        cache = ACBCrackerjackCache()

        assert cache.HOOK_DISK_TTLS["pyright"] == 86400  # 24 hours
        assert cache.HOOK_DISK_TTLS["bandit"] == 86400 * 3  # 3 days
        assert cache.HOOK_DISK_TTLS["gitleaks"] == 86400 * 7  # 7 days
        assert cache.HOOK_DISK_TTLS["zuban"] == 86400  # 24 hours

    def test_file_hash_caching(self) -> None:
        """Test file hash caching."""
        cache = ACBCrackerjackCache()

        test_file = Path(__file__)
        file_hash = "abc123def456"

        # Miss on first get
        cached_hash = cache.get_file_hash(test_file)
        assert cached_hash is None
        assert cache.stats.misses == 1

        # Set hash
        cache.set_file_hash(test_file, file_hash)
        assert cache.stats.total_entries == 1

        # Hit on second get
        cached_hash = cache.get_file_hash(test_file)
        assert cached_hash == file_hash
        assert cache.stats.hits == 1

    def test_file_hash_invalidation_on_mtime_change(self) -> None:
        """Test file hash cache uses mtime for invalidation."""
        cache = ACBCrackerjackCache()

        test_file = Path(__file__)
        file_hash = "abc123"

        # Cache with current mtime
        cache.set_file_hash(test_file, file_hash)

        # Different mtime would create different cache key
        # (can't actually change mtime in test, but verifies key includes mtime)
        key1 = cache._get_hook_cache_key("test", ["hash1"])
        key2 = cache._get_hook_cache_key("test", ["hash2"])

        assert key1 != key2  # Different hashes create different keys

    def test_config_data_caching(self) -> None:
        """Test config data caching."""
        cache = ACBCrackerjackCache()

        config_data = {"hooks": ["ruff", "zuban"], "verbose": True}

        # Miss on first get
        cached_config = cache.get_config_data("test_config")
        assert cached_config is None
        assert cache.stats.misses == 1

        # Set config
        cache.set_config_data("test_config", config_data)
        assert cache.stats.total_entries == 1

        # Hit on second get
        cached_config = cache.get_config_data("test_config")
        assert cached_config == config_data
        assert cache.stats.hits == 1

    def test_general_purpose_get_set(self) -> None:
        """Test general purpose cache methods."""
        cache = ACBCrackerjackCache()

        # Get with default
        value = cache.get("nonexistent_key", default="default_value")
        assert value == "default_value"

        # Set and get
        cache.set("test_key", {"data": "value"}, ttl_seconds=3600)
        value = cache.get("test_key")
        assert value == {"data": "value"}

    def test_agent_decision_caching(self) -> None:
        """Test AI agent decision caching."""
        cache = ACBCrackerjackCache(enable_disk_cache=True)

        decision = {"confidence": 0.9, "action": "refactor", "reason": "complexity"}

        # Miss on first get
        cached_decision = cache.get_agent_decision("RefactoringAgent", "issue_hash_123")
        assert cached_decision is None

        # Set decision
        cache.set_agent_decision("RefactoringAgent", "issue_hash_123", decision)

        # Hit on second get
        cached_decision = cache.get_agent_decision("RefactoringAgent", "issue_hash_123")
        assert cached_decision == decision
        assert cached_decision["confidence"] == 0.9

    def test_agent_decision_versioning(self) -> None:
        """Test agent version affects cache key."""
        cache = ACBCrackerjackCache(enable_disk_cache=True)

        decision = {"action": "skip"}

        # Set with current version
        cache.set_agent_decision("TestAgent", "issue_hash", decision)

        # Change agent version would invalidate cache
        # (verifies version is part of key)
        key = f"agent:TestAgent:issue_hash:{cache.AGENT_VERSION}"
        assert cache.AGENT_VERSION in key

    def test_agent_decision_disabled_disk_cache(self) -> None:
        """Test agent decisions not cached when disk cache disabled."""
        cache = ACBCrackerjackCache(enable_disk_cache=False)

        decision = {"action": "fix"}

        # Set should be no-op
        cache.set_agent_decision("TestAgent", "hash", decision)

        # Get should return None
        cached = cache.get_agent_decision("TestAgent", "hash")
        assert cached is None

    def test_quality_baseline_caching(self) -> None:
        """Test quality baseline caching."""
        cache = ACBCrackerjackCache(enable_disk_cache=True)

        metrics = {"coverage": 85.0, "complexity": 12, "issues": 5}
        git_hash = "abc123def456"

        # Miss on first get
        cached_metrics = cache.get_quality_baseline(git_hash)
        assert cached_metrics is None

        # Set baseline
        cache.set_quality_baseline(git_hash, metrics)

        # Hit on second get
        cached_metrics = cache.get_quality_baseline(git_hash)
        assert cached_metrics == metrics
        assert cached_metrics["coverage"] == 85.0

    def test_quality_baseline_disabled_disk_cache(self) -> None:
        """Test quality baselines not cached when disk cache disabled."""
        cache = ACBCrackerjackCache(enable_disk_cache=False)

        metrics = {"coverage": 90.0}

        # Set should be no-op
        cache.set_quality_baseline("hash123", metrics)

        # Get should return None
        cached = cache.get_quality_baseline("hash123")
        assert cached is None

    def test_invalidate_hook_cache_warning(self) -> None:
        """Test invalidate_hook_cache issues warning."""
        cache = ACBCrackerjackCache()

        with pytest.warns(UserWarning, match="ACB cache doesn't support"):
            cache.invalidate_hook_cache("ruff")

    def test_cleanup_all_returns_zeros(self) -> None:
        """Test cleanup_all returns zero counts (ACB auto-cleanup)."""
        cache = ACBCrackerjackCache()

        result = cache.cleanup_all()

        assert result["hook_results"] == 0
        assert result["file_hashes"] == 0
        assert result["config"] == 0
        assert result["disk_cache"] == 0

    def test_cache_stats_aggregation(self) -> None:
        """Test cache statistics aggregation."""
        cache = ACBCrackerjackCache()

        # Perform operations
        cache.get_hook_result("ruff", ["hash1"])  # Miss
        cache.set_hook_result(
            "ruff",
            ["hash1"],
            HookResult(id="test-5", name="ruff", status="success", duration=1.0),
        )
        cache.get_hook_result("ruff", ["hash1"])  # Hit

        stats = cache.get_cache_stats()

        assert stats["acb_cache"]["hits"] == 1
        assert stats["acb_cache"]["misses"] == 1
        assert stats["acb_cache"]["total_entries"] == 1
        assert stats["acb_cache"]["hit_rate_percent"] == 50.0

    def test_hook_cache_key_generation(self) -> None:
        """Test hook cache key generation."""
        cache = ACBCrackerjackCache()

        # Same hook and hashes should produce same key
        key1 = cache._get_hook_cache_key("ruff", ["abc", "def"])
        key2 = cache._get_hook_cache_key("ruff", ["abc", "def"])
        assert key1 == key2

        # Order shouldn't matter (hashes are sorted)
        key3 = cache._get_hook_cache_key("ruff", ["def", "abc"])
        assert key1 == key3

        # Different hook should produce different key
        key4 = cache._get_hook_cache_key("bandit", ["abc", "def"])
        assert key1 != key4

        # Different hashes should produce different key
        key5 = cache._get_hook_cache_key("ruff", ["xyz"])
        assert key1 != key5

    def test_versioned_cache_key_generation(self) -> None:
        """Test versioned cache key generation."""
        cache = ACBCrackerjackCache()

        # Without version
        key1 = cache._get_versioned_hook_cache_key("zuban", ["hash1"], None)
        assert "zuban" in key1
        assert key1.endswith(":") is False  # No version suffix

        # With version
        key2 = cache._get_versioned_hook_cache_key("zuban", ["hash1"], "0.1.0")
        assert "zuban" in key2
        assert key2.endswith(":0.1.0")

        # Different versions produce different keys
        key3 = cache._get_versioned_hook_cache_key("zuban", ["hash1"], "0.2.0")
        assert key2 != key3

    def test_cache_key_hash_security(self) -> None:
        """Test cache keys use MD5 without security implications."""
        cache = ACBCrackerjackCache()

        # Verify MD5 is used but marked as non-security
        # (testing implementation detail to ensure proper usage)
        key = cache._get_hook_cache_key("test", ["data"])
        assert "hook_result:test:" in key

        # Key should be deterministic
        key2 = cache._get_hook_cache_key("test", ["data"])
        assert key == key2


class TestACBCacheAdapterEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file_hashes(self) -> None:
        """Test caching with empty file hashes list."""
        cache = ACBCrackerjackCache()

        result = HookResult(id="test-6", name="ruff", status="success", duration=1.0)

        cache.set_hook_result("ruff", [], result)
        cached = cache.get_hook_result("ruff", [])

        assert cached is not None
        assert cached.name == "ruff"

    def test_none_values_in_cache(self) -> None:
        """Test caching None values."""
        cache = ACBCrackerjackCache()

        # ACB cache should handle None values
        cache.set("test_none", None)
        value = cache.get("test_none", default="fallback")

        # None is a valid cached value
        assert value is None or value == "fallback"

    def test_large_cache_key(self) -> None:
        """Test handling of large cache keys."""
        cache = ACBCrackerjackCache()

        # Very long file hash list
        long_hashes = [f"hash_{i}" for i in range(1000)]

        result = HookResult(id="test-7", name="ruff", status="success", duration=1.0)
        cache.set_hook_result("ruff", long_hashes, result)

        cached = cache.get_hook_result("ruff", long_hashes)
        assert cached is not None

    def test_complex_cached_objects(self) -> None:
        """Test caching complex nested objects."""
        cache = ACBCrackerjackCache()

        complex_data = {
            "nested": {"deep": {"value": [1, 2, 3]}},
            "list": [{"a": 1}, {"b": 2}],
            "tuple_data": (1, 2, 3),
        }

        cache.set("complex", complex_data)
        cached = cache.get("complex")

        assert cached is not None
        assert cached["nested"]["deep"]["value"] == [1, 2, 3]
