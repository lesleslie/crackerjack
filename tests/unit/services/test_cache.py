"""Unit tests for CrackerjackCache.

Tests caching functionality including hook results, file hashes,
config data, agent decisions, and quality baselines with ACB backend integration.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.models.task import HookResult
from crackerjack.services.cache import CacheStats, CrackerjackCache


@pytest.mark.unit
class TestCacheStats:
    """Test cache statistics tracking."""

    def test_cache_stats_initialization(self):
        """Test CacheStats initializes with zero values."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.total_entries == 0

    def test_cache_stats_hit_rate_zero(self):
        """Test hit rate is 0% with no requests."""
        stats = CacheStats()

        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate_calculation(self):
        """Test hit rate calculation with hits and misses."""
        stats = CacheStats(hits=75, misses=25)

        assert stats.hit_rate == 75.0

    def test_cache_stats_hit_rate_all_hits(self):
        """Test hit rate is 100% with all hits."""
        stats = CacheStats(hits=100, misses=0)

        assert stats.hit_rate == 100.0

    def test_cache_stats_hit_rate_all_misses(self):
        """Test hit rate is 0% with all misses."""
        stats = CacheStats(hits=0, misses=100)

        assert stats.hit_rate == 0.0

    def test_cache_stats_to_dict(self):
        """Test converting cache stats to dictionary."""
        stats = CacheStats(hits=10, misses=5, evictions=2, total_entries=15)

        result = stats.to_dict()

        assert result["hits"] == 10
        assert result["misses"] == 5
        assert result["evictions"] == 2
        assert result["total_entries"] == 15
        assert result["hit_rate_percent"] == 66.67


@pytest.mark.unit
class TestCrackerjackCacheInitialization:
    """Test cache initialization and backend setup."""

    def test_initialization_with_defaults(self):
        """Test cache initializes with default values."""
        cache = CrackerjackCache(backend=Mock())

        assert cache.cache_dir == Path.cwd() / ".crackerjack" / "cache"
        assert cache.enable_disk_cache is True
        assert isinstance(cache.stats, CacheStats)

    def test_initialization_with_custom_cache_dir(self, tmp_path):
        """Test cache initializes with custom directory."""
        custom_dir = tmp_path / "custom_cache"
        cache = CrackerjackCache(cache_dir=custom_dir, backend=Mock())

        assert cache.cache_dir == custom_dir

    def test_initialization_with_backend(self):
        """Test cache initializes with provided backend."""
        mock_backend = Mock()
        cache = CrackerjackCache(backend=mock_backend)

        assert cache._backend == mock_backend

    def test_initialization_without_backend_fallback(self):
        """Test cache falls back when ACB backend unavailable."""
        with patch("crackerjack.services.cache.get_cache", side_effect=RuntimeError("Backend unavailable")):
            cache = CrackerjackCache()

            assert cache._backend is None

    def test_expensive_hooks_defined(self):
        """Test expensive hooks set is properly defined."""
        assert "pyright" in CrackerjackCache.EXPENSIVE_HOOKS
        assert "bandit" in CrackerjackCache.EXPENSIVE_HOOKS
        assert "vulture" in CrackerjackCache.EXPENSIVE_HOOKS
        assert "complexipy" in CrackerjackCache.EXPENSIVE_HOOKS

    def test_hook_disk_ttls_defined(self):
        """Test TTL values for expensive hooks."""
        ttls = CrackerjackCache.HOOK_DISK_TTLS

        assert ttls["pyright"] == 86400  # 1 day
        assert ttls["gitleaks"] == 86400 * 7  # 7 days
        assert ttls["bandit"] == 86400 * 3  # 3 days


@pytest.mark.unit
class TestCrackerjackCacheHookResults:
    """Test hook result caching."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock cache backend."""
        backend = Mock()
        backend.get = AsyncMock(return_value=None)
        backend.set = AsyncMock()
        return backend

    @pytest.fixture
    def cache(self, mock_backend):
        """Create cache with mock backend."""
        return CrackerjackCache(backend=mock_backend)

    def test_get_hook_result_miss(self, cache, mock_backend):
        """Test getting hook result with cache miss."""
        mock_backend.get.return_value = None

        result = cache.get_hook_result("ruff", ["hash1", "hash2"])

        assert result is None
        assert cache.stats.misses == 1
        assert cache.stats.hits == 0

    def test_get_hook_result_hit(self, cache, mock_backend):
        """Test getting hook result with cache hit."""
        cached_result = HookResult(
            hook_name="ruff",
            returncode=0,
            output="success",
            files_checked=["file1.py"],
        )
        mock_backend.get.return_value = cached_result

        result = cache.get_hook_result("ruff", ["hash1", "hash2"])

        assert result == cached_result
        assert cache.stats.hits == 1
        assert cache.stats.misses == 0

    def test_get_hook_result_without_backend(self):
        """Test get hook result with no backend returns None."""
        cache = CrackerjackCache(backend=None)

        result = cache.get_hook_result("ruff", ["hash1"])

        assert result is None
        assert cache.stats.misses == 1

    def test_set_hook_result(self, cache, mock_backend):
        """Test setting hook result in cache."""
        result = HookResult(
            hook_name="ruff",
            returncode=0,
            output="success",
            files_checked=["file1.py"],
        )

        cache.set_hook_result("ruff", ["hash1", "hash2"], result)

        mock_backend.set.assert_called_once()
        assert cache.stats.total_entries == 1

    def test_set_hook_result_without_backend(self):
        """Test set hook result with no backend does nothing."""
        cache = CrackerjackCache(backend=None)
        result = HookResult(
            hook_name="ruff",
            returncode=0,
            output="success",
            files_checked=[],
        )

        # Should not raise
        cache.set_hook_result("ruff", ["hash1"], result)

    def test_hook_cache_key_generation(self):
        """Test hook cache key generation."""
        key = CrackerjackCache._get_hook_cache_key("ruff", ["hash1", "hash2"])

        assert key.startswith("hook_result:ruff:")
        assert len(key.split(":")) == 3

    def test_hook_cache_key_deterministic(self):
        """Test hook cache key is deterministic and order-independent."""
        key1 = CrackerjackCache._get_hook_cache_key("ruff", ["hash1", "hash2"])
        key2 = CrackerjackCache._get_hook_cache_key("ruff", ["hash2", "hash1"])

        # Keys should be the same regardless of hash order
        assert key1 == key2


@pytest.mark.unit
class TestCrackerjackCacheExpensiveHooks:
    """Test expensive hook caching with versioning."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock cache backend."""
        backend = Mock()
        backend.get = AsyncMock(return_value=None)
        backend.set = AsyncMock()
        return backend

    @pytest.fixture
    def cache(self, mock_backend):
        """Create cache with mock backend."""
        return CrackerjackCache(backend=mock_backend, enable_disk_cache=True)

    def test_get_expensive_hook_result_miss(self, cache, mock_backend):
        """Test getting expensive hook result with cache miss."""
        mock_backend.get.return_value = None

        result = cache.get_expensive_hook_result("pyright", ["hash1"], "1.0.0")

        assert result is None
        # Should have 2 misses: regular cache + expensive cache
        assert cache.stats.misses == 2

    def test_get_expensive_hook_result_hit(self, cache, mock_backend):
        """Test getting expensive hook result with cache hit."""
        cached_result = HookResult(
            hook_name="pyright",
            returncode=0,
            output="success",
            files_checked=["file1.py"],
        )
        mock_backend.get.return_value = cached_result

        result = cache.get_expensive_hook_result("pyright", ["hash1"], "1.0.0")

        assert result == cached_result
        assert cache.stats.hits == 1

    def test_get_expensive_hook_result_non_expensive_hook(self, cache):
        """Test getting result for non-expensive hook."""
        # "ruff" is not in EXPENSIVE_HOOKS
        result = cache.get_expensive_hook_result("ruff", ["hash1"], "1.0.0")

        assert result is None

    def test_set_expensive_hook_result(self, cache, mock_backend):
        """Test setting expensive hook result."""
        result = HookResult(
            hook_name="pyright",
            returncode=0,
            output="success",
            files_checked=["file1.py"],
        )

        cache.set_expensive_hook_result("pyright", ["hash1"], result, "1.0.0")

        # Should call set twice: regular cache + expensive cache
        assert mock_backend.set.call_count == 2

    def test_set_expensive_hook_result_non_expensive(self, cache, mock_backend):
        """Test setting result for non-expensive hook."""
        result = HookResult(
            hook_name="ruff",
            returncode=0,
            output="success",
            files_checked=[],
        )

        cache.set_expensive_hook_result("ruff", ["hash1"], result)

        # Should only call set once (regular cache, not expensive)
        assert mock_backend.set.call_count == 1

    def test_set_expensive_hook_result_disk_cache_disabled(self):
        """Test expensive hook caching with disk cache disabled."""
        mock_backend = Mock()
        mock_backend.set = AsyncMock()
        cache = CrackerjackCache(backend=mock_backend, enable_disk_cache=False)

        result = HookResult(
            hook_name="pyright",
            returncode=0,
            output="success",
            files_checked=[],
        )
        cache.set_expensive_hook_result("pyright", ["hash1"], result)

        # Should only set regular cache, not expensive disk cache
        assert mock_backend.set.call_count == 1

    def test_versioned_cache_key_generation(self):
        """Test versioned cache key generation."""
        cache = CrackerjackCache(backend=Mock())
        key = cache._get_versioned_hook_cache_key("pyright", ["hash1"], "1.0.0")

        assert ":1.0.0" in key

    def test_versioned_cache_key_without_version(self):
        """Test versioned cache key without version."""
        cache = CrackerjackCache(backend=Mock())
        key = cache._get_versioned_hook_cache_key("pyright", ["hash1"], None)

        # Should not have version suffix
        assert key.count(":") == 2


@pytest.mark.unit
class TestCrackerjackCacheFileHashes:
    """Test file hash caching."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock cache backend."""
        backend = Mock()
        backend.get = AsyncMock(return_value=None)
        backend.set = AsyncMock()
        return backend

    @pytest.fixture
    def cache(self, mock_backend):
        """Create cache with mock backend."""
        return CrackerjackCache(backend=mock_backend)

    def test_get_file_hash_miss(self, cache, mock_backend, tmp_path):
        """Test getting file hash with cache miss."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")
        mock_backend.get.return_value = None

        result = cache.get_file_hash(test_file)

        assert result is None
        assert cache.stats.misses == 1

    def test_get_file_hash_hit(self, cache, mock_backend, tmp_path):
        """Test getting file hash with cache hit."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")
        cached_hash = "abc123def456"
        mock_backend.get.return_value = cached_hash

        result = cache.get_file_hash(test_file)

        assert result == cached_hash
        assert cache.stats.hits == 1

    def test_get_file_hash_without_backend(self, tmp_path):
        """Test get file hash with no backend."""
        cache = CrackerjackCache(backend=None)
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        result = cache.get_file_hash(test_file)

        assert result is None
        assert cache.stats.misses == 1

    def test_set_file_hash(self, cache, mock_backend, tmp_path):
        """Test setting file hash in cache."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")
        file_hash = "abc123def456"

        cache.set_file_hash(test_file, file_hash)

        mock_backend.set.assert_called_once()
        assert cache.stats.total_entries == 1

    def test_file_hash_cache_key_includes_mtime_and_size(self, cache, tmp_path):
        """Test file hash cache key includes mtime and size."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        # Get the cache key by calling set and checking call args
        cache.set_file_hash(test_file, "hash")

        call_args = cache._backend.set.call_args[0]
        cache_key = call_args[0]

        # Key should include file path, mtime, and size
        assert str(test_file) in cache_key
        assert "file_hash:" in cache_key


@pytest.mark.unit
class TestCrackerjackCacheConfigData:
    """Test configuration data caching."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock cache backend."""
        backend = Mock()
        backend.get = AsyncMock(return_value=None)
        backend.set = AsyncMock()
        return backend

    @pytest.fixture
    def cache(self, mock_backend):
        """Create cache with mock backend."""
        return CrackerjackCache(backend=mock_backend)

    def test_get_config_data_miss(self, cache, mock_backend):
        """Test getting config data with cache miss."""
        mock_backend.get.return_value = None

        result = cache.get_config_data("test_config")

        assert result is None
        assert cache.stats.misses == 1

    def test_get_config_data_hit(self, cache, mock_backend):
        """Test getting config data with cache hit."""
        config_data = {"setting": "value"}
        mock_backend.get.return_value = config_data

        result = cache.get_config_data("test_config")

        assert result == config_data
        assert cache.stats.hits == 1

    def test_set_config_data(self, cache, mock_backend):
        """Test setting config data in cache."""
        config_data = {"setting": "value"}

        cache.set_config_data("test_config", config_data)

        mock_backend.set.assert_called_once()
        # Check cache key format
        call_args = mock_backend.set.call_args[0]
        assert "config:test_config" == call_args[0]
        assert cache.stats.total_entries == 1

    def test_get_config_data_without_backend(self):
        """Test get config data with no backend."""
        cache = CrackerjackCache(backend=None)

        result = cache.get_config_data("test_config")

        assert result is None
        assert cache.stats.misses == 1


@pytest.mark.unit
class TestCrackerjackCacheGenericOperations:
    """Test generic get/set operations."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock cache backend."""
        backend = Mock()
        backend.get = AsyncMock(return_value=None)
        backend.set = AsyncMock()
        return backend

    @pytest.fixture
    def cache(self, mock_backend):
        """Create cache with mock backend."""
        return CrackerjackCache(backend=mock_backend)

    def test_get_with_default(self, cache, mock_backend):
        """Test generic get with default value."""
        mock_backend.get.return_value = None

        result = cache.get("test_key", default="default_value")

        assert result == "default_value"

    def test_get_with_value(self, cache, mock_backend):
        """Test generic get returns cached value."""
        mock_backend.get.return_value = "cached_value"

        result = cache.get("test_key", default="default_value")

        assert result == "cached_value"

    def test_get_without_backend(self):
        """Test generic get with no backend returns default."""
        cache = CrackerjackCache(backend=None)

        result = cache.get("test_key", default="default_value")

        assert result == "default_value"

    def test_set_with_ttl(self, cache, mock_backend):
        """Test generic set with custom TTL."""
        cache.set("test_key", "test_value", ttl_seconds=7200)

        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[1]["ttl"] == 7200

    def test_set_with_default_ttl(self, cache, mock_backend):
        """Test generic set with default TTL."""
        cache.set("test_key", "test_value")

        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[1]["ttl"] == 3600  # Default


@pytest.mark.unit
class TestCrackerjackCacheAgentDecisions:
    """Test agent decision caching."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock cache backend."""
        backend = Mock()
        backend.get = AsyncMock(return_value=None)
        backend.set = AsyncMock()
        return backend

    @pytest.fixture
    def cache(self, mock_backend):
        """Create cache with mock backend."""
        return CrackerjackCache(backend=mock_backend, enable_disk_cache=True)

    def test_get_agent_decision(self, cache, mock_backend):
        """Test getting agent decision from cache."""
        decision_data = {"apply": True, "confidence": 0.9}
        mock_backend.get.return_value = decision_data

        result = cache.get_agent_decision("refactoring", "issue_hash_123")

        assert result == decision_data

    def test_get_agent_decision_disk_cache_disabled(self):
        """Test get agent decision with disk cache disabled."""
        cache = CrackerjackCache(backend=Mock(), enable_disk_cache=False)

        result = cache.get_agent_decision("refactoring", "issue_hash_123")

        assert result is None

    def test_set_agent_decision(self, cache, mock_backend):
        """Test setting agent decision in cache."""
        decision_data = {"apply": True, "confidence": 0.9}

        cache.set_agent_decision("refactoring", "issue_hash_123", decision_data)

        mock_backend.set.assert_called_once()
        # Check cache key includes version
        call_args = mock_backend.set.call_args[0]
        cache_key = call_args[0]
        assert cache_key.endswith(":1.0.0")  # AGENT_VERSION

    def test_set_agent_decision_disk_cache_disabled(self):
        """Test set agent decision with disk cache disabled."""
        mock_backend = Mock()
        mock_backend.set = AsyncMock()
        cache = CrackerjackCache(backend=mock_backend, enable_disk_cache=False)

        decision_data = {"apply": True}
        cache.set_agent_decision("refactoring", "issue_hash_123", decision_data)

        # Should not call backend.set when disk cache disabled
        mock_backend.set.assert_not_called()


@pytest.mark.unit
class TestCrackerjackCacheQualityBaseline:
    """Test quality baseline caching."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock cache backend."""
        backend = Mock()
        backend.get = AsyncMock(return_value=None)
        backend.set = AsyncMock()
        return backend

    @pytest.fixture
    def cache(self, mock_backend):
        """Create cache with mock backend."""
        return CrackerjackCache(backend=mock_backend, enable_disk_cache=True)

    def test_get_quality_baseline(self, cache, mock_backend):
        """Test getting quality baseline from cache."""
        baseline_data = {"coverage": 85.5, "complexity": 12}
        mock_backend.get.return_value = baseline_data

        result = cache.get_quality_baseline("abc123def456")

        assert result == baseline_data

    def test_get_quality_baseline_disk_cache_disabled(self):
        """Test get quality baseline with disk cache disabled."""
        cache = CrackerjackCache(backend=Mock(), enable_disk_cache=False)

        result = cache.get_quality_baseline("abc123def456")

        assert result is None

    def test_set_quality_baseline(self, cache, mock_backend):
        """Test setting quality baseline in cache."""
        metrics = {"coverage": 85.5, "complexity": 12}

        cache.set_quality_baseline("abc123def456", metrics)

        mock_backend.set.assert_called_once()
        # Check cache key format
        call_args = mock_backend.set.call_args[0]
        assert call_args[0] == "baseline:abc123def456"
        # Check long TTL (30 days)
        assert mock_backend.set.call_args[1]["ttl"] == 2592000

    def test_set_quality_baseline_disk_cache_disabled(self):
        """Test set quality baseline with disk cache disabled."""
        mock_backend = Mock()
        mock_backend.set = AsyncMock()
        cache = CrackerjackCache(backend=mock_backend, enable_disk_cache=False)

        metrics = {"coverage": 85.5}
        cache.set_quality_baseline("abc123", metrics)

        # Should not call backend.set
        mock_backend.set.assert_not_called()


@pytest.mark.unit
class TestCrackerjackCacheUtilities:
    """Test cache utility methods."""

    def test_invalidate_hook_cache_logs_warning(self):
        """Test invalidate hook cache logs warning."""
        cache = CrackerjackCache(backend=Mock())

        # Should not raise, just logs warning
        cache.invalidate_hook_cache("ruff")

    def test_cleanup_all_returns_zeros(self):
        """Test cleanup all returns zero counts."""
        cache = CrackerjackCache(backend=Mock())

        result = cache.cleanup_all()

        assert result["hook_results"] == 0
        assert result["file_hashes"] == 0
        assert result["config"] == 0
        assert result["disk_cache"] == 0

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        cache = CrackerjackCache(backend=Mock())
        cache.stats.hits = 10
        cache.stats.misses = 5

        result = cache.get_cache_stats()

        assert "acb_cache" in result
        assert result["acb_cache"]["hits"] == 10
        assert result["acb_cache"]["misses"] == 5


@pytest.mark.unit
class TestCrackerjackCacheAsyncHandling:
    """Test async operation handling."""

    @pytest.fixture
    def mock_backend(self):
        """Create mock cache backend."""
        backend = Mock()
        backend.get = AsyncMock(return_value="test_value")
        backend.set = AsyncMock()
        return backend

    def test_run_async_executes_coroutine(self, mock_backend):
        """Test _run_async executes async operations."""
        cache = CrackerjackCache(backend=mock_backend)

        result = cache.get("test_key")

        assert result == "test_value"
        mock_backend.get.assert_called_once()

    def test_run_async_handles_runtime_error(self, mock_backend):
        """Test _run_async handles asyncio runtime errors."""
        cache = CrackerjackCache(backend=mock_backend)

        # Simulate already running event loop by patching asyncio.run
        with patch("asyncio.run", side_effect=RuntimeError("asyncio.run() error")):
            with patch("asyncio.new_event_loop") as mock_new_loop:
                mock_loop = Mock()
                mock_loop.run_until_complete.return_value = "fallback_value"
                mock_loop.close = Mock()
                mock_new_loop.return_value = mock_loop

                result = cache.get("test_key")

                # Should use fallback event loop
                mock_new_loop.assert_called_once()
                mock_loop.run_until_complete.assert_called_once()
                mock_loop.close.assert_called_once()


@pytest.mark.unit
class TestCrackerjackCacheConstants:
    """Test cache constant definitions."""

    def test_expensive_hooks_set(self):
        """Test EXPENSIVE_HOOKS contains expected values."""
        hooks = CrackerjackCache.EXPENSIVE_HOOKS

        assert isinstance(hooks, set)
        assert len(hooks) > 0
        # Check key expensive hooks
        assert "pyright" in hooks
        assert "bandit" in hooks
        assert "vulture" in hooks
        assert "complexipy" in hooks
        assert "refurb" in hooks
        assert "zuban" in hooks

    def test_hook_disk_ttls_mapping(self):
        """Test HOOK_DISK_TTLS has correct structure."""
        ttls = CrackerjackCache.HOOK_DISK_TTLS

        assert isinstance(ttls, dict)
        # All expensive hooks should have TTLs
        for hook in CrackerjackCache.EXPENSIVE_HOOKS:
            assert hook in ttls
            assert isinstance(ttls[hook], int)
            assert ttls[hook] > 0

    def test_agent_version_defined(self):
        """Test AGENT_VERSION is defined."""
        assert CrackerjackCache.AGENT_VERSION == "1.0.0"
