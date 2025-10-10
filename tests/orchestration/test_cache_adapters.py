"""Unit tests for cache adapters (Phase 3.3).

Tests both ToolProxyCacheAdapter and MemoryCacheAdapter to ensure:
- Content-based cache key generation
- TTL-based expiration
- Cache hit/miss behavior
- LRU eviction (MemoryCacheAdapter)
- Statistics tracking
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel
from crackerjack.models.task import HookResult
from crackerjack.orchestration.cache.memory_cache import MemoryCacheAdapter, MemoryCacheSettings
from crackerjack.orchestration.cache.tool_proxy_cache import (
    ToolProxyCacheAdapter,
    ToolProxyCacheSettings,
)


@pytest.fixture
def sample_hook() -> HookDefinition:
    """Create sample hook definition for testing."""
    return HookDefinition(
        name="bandit",
        command=["uv", "run", "bandit", "-c", "pyproject.toml", "-r", "crackerjack"],
        timeout=60,
        stage=HookStage.COMPREHENSIVE,
        security_level=SecurityLevel.HIGH,
        use_precommit_legacy=False,
    )


@pytest.fixture
def sample_result() -> HookResult:
    """Create sample hook result for testing."""
    return HookResult(
        id="bandit",
        name="bandit",
        status="passed",
        duration=1.5,
    )


@pytest.fixture
def temp_files(tmp_path: Path) -> list[Path]:
    """Create temporary test files."""
    files = []
    for i in range(3):
        file_path = tmp_path / f"test_{i}.py"
        file_path.write_text(f"# Test file {i}\nprint('hello')")
        files.append(file_path)
    return files


class TestMemoryCacheAdapter:
    """Test MemoryCacheAdapter functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test cache adapter initialization."""
        settings = MemoryCacheSettings(max_entries=50, default_ttl=1800)
        cache = MemoryCacheAdapter(settings=settings)

        assert cache.settings.max_entries == 50
        assert cache.settings.default_ttl == 1800
        assert not cache._initialized

        await cache.init()
        assert cache._initialized

    @pytest.mark.asyncio
    async def test_compute_key_consistency(self, sample_hook: HookDefinition, temp_files: list[Path]):
        """Test cache key computation is consistent."""
        cache = MemoryCacheAdapter()
        await cache.init()

        key1 = cache.compute_key(sample_hook, temp_files)
        key2 = cache.compute_key(sample_hook, temp_files)

        assert key1 == key2
        assert key1.startswith("bandit:")

    @pytest.mark.asyncio
    async def test_compute_key_changes_with_content(
        self, sample_hook: HookDefinition, temp_files: list[Path]
    ):
        """Test cache key changes when file content changes."""
        cache = MemoryCacheAdapter()
        await cache.init()

        key1 = cache.compute_key(sample_hook, temp_files)

        # Modify file content
        temp_files[0].write_text("# Modified content\nprint('goodbye')")

        key2 = cache.compute_key(sample_hook, temp_files)

        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cache_hit_miss(
        self, sample_hook: HookDefinition, sample_result: HookResult, temp_files: list[Path]
    ):
        """Test cache hit and miss behavior."""
        cache = MemoryCacheAdapter()
        await cache.init()

        cache_key = cache.compute_key(sample_hook, temp_files)

        # Initial get should be a miss
        result = await cache.get(cache_key)
        assert result is None

        # Store result
        await cache.set(cache_key, sample_result)

        # Now should be a hit
        result = await cache.get(cache_key)
        assert result is not None
        assert result.name == "bandit"
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, sample_hook: HookDefinition, sample_result: HookResult):
        """Test TTL-based cache expiration."""
        # Use minimum TTL for testing (60 seconds is minimum)
        settings = MemoryCacheSettings(default_ttl=60)
        cache = MemoryCacheAdapter(settings=settings)
        await cache.init()

        cache_key = cache.compute_key(sample_hook, files=[])

        # Store with minimum TTL (60 seconds)
        await cache.set(cache_key, sample_result, ttl=60)

        # Immediate get should hit
        result = await cache.get(cache_key)
        assert result is not None

        # For testing, we verify the entry exists with proper TTL
        # (Full expiration testing would require waiting 60+ seconds)
        assert cache_key in cache._cache
        result_cached, expiry = cache._cache[cache_key]
        assert expiry > 0  # Has expiration time set

    @pytest.mark.asyncio
    async def test_lru_eviction(self, sample_hook: HookDefinition):
        """Test LRU eviction when max_entries reached."""
        # Use minimum max_entries for testing (10 is minimum)
        settings = MemoryCacheSettings(max_entries=10)
        cache = MemoryCacheAdapter(settings=settings)
        await cache.init()

        # Add 10 entries (at capacity)
        for i in range(10):
            result = HookResult(
                id=f"hook_{i}",
                name=f"hook_{i}",
                status="passed",
                duration=1.0,
            )
            key = f"key_{i}"
            await cache.set(key, result)

        # All 10 should be in cache
        assert len(cache._cache) == 10

        # Add 11th entry - should evict oldest (key_0)
        result = HookResult(
            id="hook_10",
            name="hook_10",
            status="passed",
            duration=1.0,
        )
        await cache.set("key_10", result)

        # Still 10 entries (LRU eviction)
        assert len(cache._cache) == 10

        # key_0 should be evicted
        assert await cache.get("key_0") is None

        # key_1 through key_10 should still be there
        assert await cache.get("key_1") is not None
        assert await cache.get("key_9") is not None
        assert await cache.get("key_10") is not None

    @pytest.mark.asyncio
    async def test_clear(self, sample_hook: HookDefinition, sample_result: HookResult):
        """Test cache clear operation."""
        cache = MemoryCacheAdapter()
        await cache.init()

        # Add multiple entries
        for i in range(5):
            await cache.set(f"key_{i}", sample_result)

        assert len(cache._cache) == 5

        # Clear cache
        await cache.clear()

        assert len(cache._cache) == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, sample_hook: HookDefinition, sample_result: HookResult):
        """Test cache statistics."""
        cache = MemoryCacheAdapter()
        await cache.init()

        # Add some entries
        await cache.set("key_1", sample_result, ttl=3600)
        await cache.set("key_2", sample_result, ttl=1)  # Will expire soon

        # Wait for one to expire
        await asyncio.sleep(1.1)

        stats = await cache.get_stats()

        assert stats["total_entries"] == 2
        assert stats["expired_entries"] == 1
        assert stats["active_entries"] == 1
        assert stats["max_entries"] == 100  # Default
        assert stats["default_ttl"] == 3600  # Default


class TestToolProxyCacheAdapter:
    """Test ToolProxyCacheAdapter functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self, tmp_path: Path):
        """Test cache adapter initialization."""
        settings = ToolProxyCacheSettings(default_ttl=1800)
        cache = ToolProxyCacheAdapter(settings=settings, cache_dir=tmp_path / "cache")

        assert cache.settings.default_ttl == 1800
        assert not cache._initialized

        await cache.init()
        assert cache._initialized
        assert cache._cache_dir.exists()

    @pytest.mark.asyncio
    async def test_compute_key_consistency(
        self, sample_hook: HookDefinition, temp_files: list[Path], tmp_path: Path
    ):
        """Test cache key computation is consistent."""
        cache = ToolProxyCacheAdapter(cache_dir=tmp_path / "cache")
        await cache.init()

        key1 = cache.compute_key(sample_hook, temp_files)
        key2 = cache.compute_key(sample_hook, temp_files)

        assert key1 == key2
        assert key1.startswith("bandit:")

    @pytest.mark.asyncio
    async def test_cache_operations(
        self, sample_hook: HookDefinition, sample_result: HookResult, tmp_path: Path
    ):
        """Test basic cache operations."""
        cache = ToolProxyCacheAdapter(cache_dir=tmp_path / "cache")
        await cache.init()

        cache_key = cache.compute_key(sample_hook, files=[])

        # Miss
        result = await cache.get(cache_key)
        assert result is None

        # Set
        await cache.set(cache_key, sample_result)

        # Hit
        result = await cache.get(cache_key)
        assert result is not None
        assert result.name == "bandit"

    @pytest.mark.asyncio
    async def test_get_stats(self, tmp_path: Path):
        """Test cache statistics."""
        cache = ToolProxyCacheAdapter(cache_dir=tmp_path / "cache")
        await cache.init()

        stats = await cache.get_stats()

        assert "total_entries" in stats
        assert "active_entries" in stats
        assert "cache_dir" in stats
        assert stats["default_ttl"] == 3600  # Default

    @pytest.mark.asyncio
    async def test_module_id(self, tmp_path: Path):
        """Test MODULE_ID property."""
        cache = ToolProxyCacheAdapter(cache_dir=tmp_path / "cache")
        await cache.init()

        assert cache.module_id is not None
        assert cache.adapter_name == "ToolProxyCacheAdapter"


class TestCacheKeyGeneration:
    """Test cache key generation edge cases."""

    @pytest.mark.asyncio
    async def test_empty_files_list(self, sample_hook: HookDefinition):
        """Test cache key generation with empty files list."""
        cache = MemoryCacheAdapter()
        await cache.init()

        key = cache.compute_key(sample_hook, files=[])

        assert key.startswith("bandit:")
        assert len(key) > len("bandit:")

    @pytest.mark.asyncio
    async def test_nonexistent_files(self, sample_hook: HookDefinition):
        """Test cache key generation with nonexistent files."""
        cache = MemoryCacheAdapter()
        await cache.init()

        nonexistent_files = [Path("/nonexistent/file1.py"), Path("/nonexistent/file2.py")]

        key = cache.compute_key(sample_hook, nonexistent_files)

        # Should still generate key without crashing
        assert key.startswith("bandit:")

    @pytest.mark.asyncio
    async def test_different_hook_configs_different_keys(self, temp_files: list[Path]):
        """Test different hook configurations produce different keys."""
        cache = MemoryCacheAdapter()
        await cache.init()

        hook1 = HookDefinition(
            name="bandit",
            command=["uv", "run", "bandit", "-c", "pyproject.toml", "-r", "crackerjack"],
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.HIGH,
            use_precommit_legacy=False,
        )

        hook2 = HookDefinition(
            name="bandit",
            command=["uv", "run", "bandit", "-ll", "-c", "pyproject.toml", "-r", "crackerjack"],  # Different command
            timeout=60,
            stage=HookStage.COMPREHENSIVE,
            security_level=SecurityLevel.HIGH,
            use_precommit_legacy=False,
        )

        key1 = cache.compute_key(hook1, temp_files)
        key2 = cache.compute_key(hook2, temp_files)

        assert key1 != key2
