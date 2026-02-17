import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from crackerjack.models.task import HookResult
from crackerjack.services.cache import CrackerjackCache, CacheStats


@pytest.fixture
def temp_cache_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


def test_cache_stats_initialization():
    """Test initialization of CacheStats."""
    stats = CacheStats()

    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.evictions == 0
    assert stats.total_entries == 0
    assert stats.hit_rate == 0.0


def test_cache_stats_hit_rate_calculation():
    """Test hit rate calculation in CacheStats."""
    stats = CacheStats()
    stats.hits = 80
    stats.misses = 20

    assert stats.hit_rate == 80.0  # 80/(80+20) = 0.8 = 80%


def test_cache_stats_to_dict():
    """Test converting CacheStats to dictionary."""
    stats = CacheStats()
    stats.hits = 80
    stats.misses = 20
    stats.evictions = 5
    stats.total_entries = 105

    stats_dict = stats.to_dict()

    assert stats_dict["hits"] == 80
    assert stats_dict["misses"] == 20
    assert stats_dict["evictions"] == 5
    assert stats_dict["total_entries"] == 105
    assert stats_dict["hit_rate_percent"] == 80.0


def test_crackerjack_cache_initialization(temp_cache_dir):
    """Test initialization of CrackerjackCache."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    assert cache.cache_dir == temp_cache_dir
    assert cache.enable_disk_cache is True
    assert isinstance(cache.stats, CacheStats)
    assert cache._backend is None  # Because get_cache() returns None


def test_crackerjack_cache_initialization_with_backend(temp_cache_dir):
    """Test initialization of CrackerjackCache with custom backend."""
    mock_backend = Mock()
    cache = CrackerjackCache(cache_dir=temp_cache_dir, backend=mock_backend)

    assert cache._backend == mock_backend


def test_get_hook_result_no_backend(temp_cache_dir):
    """Test get_hook_result when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    result = cache.get_hook_result("test_hook", ["hash1", "hash2"])

    assert result is None
    assert cache.stats.misses == 1


def test_set_hook_result_no_backend(temp_cache_dir):
    """Test set_hook_result when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # Create a mock HookResult
    mock_result = Mock(spec=HookResult)

    # This should not raise an exception even though backend is None
    cache.set_hook_result("test_hook", ["hash1", "hash2"], mock_result)

    # Stats should not change since nothing was stored
    assert cache.stats.total_entries == 0


def test_get_expensive_hook_result_no_backend(temp_cache_dir):
    """Test get_expensive_hook_result when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    result = cache.get_expensive_hook_result("zuban", ["hash1", "hash2"])

    assert result is None
    assert cache.stats.misses == 1


def test_set_expensive_hook_result_no_backend(temp_cache_dir):
    """Test set_expensive_hook_result when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # Create a mock HookResult
    mock_result = Mock(spec=HookResult)

    # This should not raise an exception even though backend is None
    cache.set_expensive_hook_result("zuban", ["hash1", "hash2"], mock_result)

    # Stats should not change since nothing was stored
    assert cache.stats.total_entries == 0


def test_get_file_hash_no_backend(temp_cache_dir):
    """Test get_file_hash when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # Create a temporary file to test with
    test_file = temp_cache_dir / "test_file.txt"
    test_file.write_text("test content")

    result = cache.get_file_hash(test_file)

    assert result is None
    assert cache.stats.misses == 1


def test_set_file_hash_no_backend(temp_cache_dir):
    """Test set_file_hash when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # Create a temporary file to test with
    test_file = temp_cache_dir / "test_file.txt"
    test_file.write_text("test content")

    # This should not raise an exception even though backend is None
    cache.set_file_hash(test_file, "test_hash")

    # Stats should not change since nothing was stored
    assert cache.stats.total_entries == 0


def test_get_config_data_no_backend(temp_cache_dir):
    """Test get_config_data when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    result = cache.get_config_data("test_config")

    assert result is None
    assert cache.stats.misses == 1


def test_set_config_data_no_backend(temp_cache_dir):
    """Test set_config_data when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # This should not raise an exception even though backend is None
    cache.set_config_data("test_config", {"key": "value"})

    # Stats should not change since nothing was stored
    assert cache.stats.total_entries == 0


def test_get_set_no_backend(temp_cache_dir):
    """Test get/set methods when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # Test get with default
    result = cache.get("test_key", "default_value")
    assert result == "default_value"

    # Test get without default
    result = cache.get("test_key")
    assert result is None

    # Test set (should not raise exception)
    cache.set("test_key", "test_value")


def test_get_agent_decision_no_backend(temp_cache_dir):
    """Test get_agent_decision when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    result = cache.get_agent_decision("test_agent", "test_issue")

    assert result is None


def test_set_agent_decision_no_backend(temp_cache_dir):
    """Test set_agent_decision when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # This should not raise an exception even though backend is None
    cache.set_agent_decision("test_agent", "test_issue", {"decision": "fix"})


def test_get_quality_baseline_no_backend(temp_cache_dir):
    """Test get_quality_baseline when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    result = cache.get_quality_baseline("test_git_hash")

    assert result is None


def test_set_quality_baseline_no_backend(temp_cache_dir):
    """Test set_quality_baseline when no backend is available."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # This should not raise an exception even though backend is None
    cache.set_quality_baseline("test_git_hash", {"metric": "value"})


def test_invalidate_hook_cache():
    """Test invalidate_hook_cache static method."""
    # This should not raise an exception
    CrackerjackCache.invalidate_hook_cache()
    CrackerjackCache.invalidate_hook_cache("test_hook")


def test_cleanup_all():
    """Test cleanup_all static method."""
    result = CrackerjackCache.cleanup_all()

    expected = {
        "hook_results": 0,
        "file_hashes": 0,
        "config": 0,
        "disk_cache": 0,
    }

    assert result == expected


def test_get_cache_stats(temp_cache_dir):
    """Test get_cache_stats method."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    stats = cache.get_cache_stats()

    assert "cache" in stats
    assert isinstance(stats["cache"], dict)


def test_get_hook_cache_key():
    """Test _get_hook_cache_key static method."""
    # This method is static, so we can call it directly
    key = CrackerjackCache._get_hook_cache_key("test_hook", ["hash1", "hash2"])

    assert key.startswith("hook_result:test_hook:")
    assert len(key) > len("hook_result:test_hook:")


def test_get_versioned_hook_cache_key(temp_cache_dir):
    """Test _get_versioned_hook_cache_key method."""
    cache = CrackerjackCache(cache_dir=temp_cache_dir)

    # Without version
    key = cache._get_versioned_hook_cache_key("test_hook", ["hash1", "hash2"])
    base_key = cache._get_hook_cache_key("test_hook", ["hash1", "hash2"])
    assert key == base_key

    # With version
    key_with_version = cache._get_versioned_hook_cache_key("test_hook", ["hash1", "hash2"], "1.0.0")
    assert key_with_version.startswith(base_key)
    assert ":1.0.0" in key_with_version
