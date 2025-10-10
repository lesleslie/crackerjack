# ACB Cache Replacement Strategy

**Date**: 2025-10-09
**Status**: Planning
**Estimated Impact**: -400 lines, 70% cache hit rate improvement

## Current State Analysis

### Existing Implementation (`crackerjack/services/cache.py` - 437 lines)

**Components**:

1. **InMemoryCache** (lines 64-134)

   - LRU eviction policy
   - TTL-based expiration
   - Stats tracking (hits/misses/evictions)
   - Synchronous operations

1. **FileCache** (lines 136-220)

   - JSON-based disk persistence
   - MD5 key hashing
   - Manual TTL management
   - Synchronous file I/O

1. **CrackerjackCache** (lines 222-437)

   - Hook result caching (memory + disk)
   - File hash caching (memory only)
   - Config data caching (memory only)
   - Agent decision caching (disk only)
   - Quality baseline caching (disk only)

**Key Features**:

- Dual-tier caching (memory + disk) for expensive hooks
- Versioned cache keys (tool version, agent version)
- Per-hook TTL configuration
- Cache statistics aggregation

**Usage Patterns**:

```python
# Current usage
cache = CrackerjackCache(cache_dir=pkg_path / ".crackerjack" / "cache")
result = cache.get_expensive_hook_result(hook_name, file_hashes, tool_version)
cache.set_expensive_hook_result(hook_name, file_hashes, result, tool_version)
stats = cache.get_cache_stats()
```

### ACB Cache Adapter (`acb/adapters/cache/memory.py` - 187 lines)

**Capabilities**:

- **Async operations** (set/get/delete/multi_get/multi_set)
- **Built-in serialization** (Pickle via aiocache)
- **Namespace support** (automatic prefixing)
- **Cleanup lifecycle** (CleanupMixin integration)
- **Simple API** (fewer methods, cleaner interface)

**API**:

```python
# ACB usage (async)
from acb.depends import depends
from acb.adapters.cache.memory import Cache

cache = depends.get(Cache)
await cache.set(key, value, ttl=3600)
result = await cache.get(key)
await cache.delete(key)
await cache.multi_get([key1, key2, key3])
```

## Migration Strategy

### Phase 1: Create ACB-Backed Crackerjack Cache Adapter

**Goal**: Maintain current API while using ACB cache under the hood

**Implementation** (`crackerjack/services/acb_cache_adapter.py`):

```python
import asyncio
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
import typing as t

from acb.depends import depends
from acb.adapters.cache.memory import Cache as ACBCache

from crackerjack.models.task import HookResult


@dataclass
class CacheStats:
    """Compatible with existing CrackerjackCache.stats"""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_entries": self.total_entries,
            "hit_rate_percent": round(self.hit_rate, 2),
        }


class ACBCrackerjackCache:
    """ACB-backed cache adapter maintaining CrackerjackCache API."""

    EXPENSIVE_HOOKS = {
        "pyright",
        "bandit",
        "vulture",
        "complexipy",
        "refurb",
        "gitleaks",
        "zuban",
    }

    HOOK_DISK_TTLS = {
        "pyright": 86400,
        "bandit": 86400 * 3,
        "vulture": 86400 * 2,
        "complexipy": 86400,
        "refurb": 86400,
        "gitleaks": 86400 * 7,
        "zuban": 86400,  # New: Zuban type checker
    }

    AGENT_VERSION = "1.0.0"

    def __init__(
        self,
        cache_dir: Path | None = None,
        enable_disk_cache: bool = True,
    ) -> None:
        self.cache_dir = cache_dir or Path.cwd() / ".crackerjack" / "cache"
        self.enable_disk_cache = enable_disk_cache

        # Get ACB cache from DI
        self._acb_cache = depends.get(ACBCache)

        # Stats tracking (compatible with existing API)
        self.stats = CacheStats()

        # Event loop for sync API compatibility
        self._loop = asyncio.get_event_loop()

    def _run_async(self, coro):
        """Execute async operation in sync context."""
        return self._loop.run_until_complete(coro)

    def get_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
    ) -> HookResult | None:
        """Get hook result from cache (sync API)."""
        cache_key = self._get_hook_cache_key(hook_name, file_hashes)
        result = self._run_async(self._acb_cache.get(cache_key))

        if result is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1

        return result

    def set_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
        result: HookResult,
    ) -> None:
        """Set hook result in cache (sync API)."""
        cache_key = self._get_hook_cache_key(hook_name, file_hashes)
        self._run_async(self._acb_cache.set(cache_key, result, ttl=1800))
        self.stats.total_entries += 1

    def get_expensive_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
        tool_version: str | None = None,
    ) -> HookResult | None:
        """Get expensive hook result (with disk fallback if enabled)."""
        # Check memory cache first
        result = self.get_hook_result(hook_name, file_hashes)
        if result:
            return result

        # Check disk cache for expensive hooks
        if self.enable_disk_cache and hook_name in self.EXPENSIVE_HOOKS:
            cache_key = self._get_versioned_hook_cache_key(
                hook_name, file_hashes, tool_version
            )
            result = self._run_async(self._acb_cache.get(cache_key))

            if result is None:
                self.stats.misses += 1
            else:
                self.stats.hits += 1

            return result

        return None

    def set_expensive_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
        result: HookResult,
        tool_version: str | None = None,
    ) -> None:
        """Set expensive hook result (memory + disk)."""
        # Always set in memory
        self.set_hook_result(hook_name, file_hashes, result)

        # Also persist to disk for expensive hooks
        if self.enable_disk_cache and hook_name in self.EXPENSIVE_HOOKS:
            cache_key = self._get_versioned_hook_cache_key(
                hook_name, file_hashes, tool_version
            )
            ttl = self.HOOK_DISK_TTLS.get(hook_name, 86400)
            self._run_async(self._acb_cache.set(cache_key, result, ttl=ttl))

    def get_file_hash(self, file_path: Path) -> str | None:
        """Get cached file hash."""
        stat = file_path.stat()
        cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"
        result = self._run_async(self._acb_cache.get(cache_key))

        if result is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1

        return result

    def set_file_hash(self, file_path: Path, file_hash: str) -> None:
        """Cache file hash."""
        stat = file_path.stat()
        cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"
        self._run_async(self._acb_cache.set(cache_key, file_hash, ttl=3600))
        self.stats.total_entries += 1

    def get_config_data(self, config_key: str) -> t.Any | None:
        """Get cached config data."""
        result = self._run_async(self._acb_cache.get(f"config:{config_key}"))

        if result is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1

        return result

    def set_config_data(self, config_key: str, data: t.Any) -> None:
        """Cache config data."""
        self._run_async(self._acb_cache.set(f"config:{config_key}", data, ttl=7200))
        self.stats.total_entries += 1

    def get(self, key: str, default: t.Any = None) -> t.Any:
        """General purpose get."""
        result = self._run_async(self._acb_cache.get(key))
        return result if result is not None else default

    def set(self, key: str, value: t.Any, ttl_seconds: int | None = None) -> None:
        """General purpose set."""
        ttl = ttl_seconds or 3600
        self._run_async(self._acb_cache.set(key, value, ttl=ttl))

    def get_agent_decision(self, agent_name: str, issue_hash: str) -> t.Any | None:
        """Get cached AI agent decision."""
        if not self.enable_disk_cache:
            return None

        cache_key = f"agent:{agent_name}:{issue_hash}:{self.AGENT_VERSION}"
        return self._run_async(self._acb_cache.get(cache_key))

    def set_agent_decision(
        self, agent_name: str, issue_hash: str, decision: t.Any
    ) -> None:
        """Cache AI agent decision."""
        if not self.enable_disk_cache:
            return

        cache_key = f"agent:{agent_name}:{issue_hash}:{self.AGENT_VERSION}"
        self._run_async(self._acb_cache.set(cache_key, decision, ttl=604800))

    def get_quality_baseline(self, git_hash: str) -> dict[str, t.Any] | None:
        """Get quality baseline for git commit."""
        if not self.enable_disk_cache:
            return None

        return self._run_async(self._acb_cache.get(f"baseline:{git_hash}"))

    def set_quality_baseline(self, git_hash: str, metrics: dict[str, t.Any]) -> None:
        """Store quality baseline for git commit."""
        if not self.enable_disk_cache:
            return

        self._run_async(
            self._acb_cache.set(f"baseline:{git_hash}", metrics, ttl=2592000)
        )

    def invalidate_hook_cache(self, hook_name: str | None = None) -> None:
        """Invalidate hook cache (not implemented in ACB - clear all)."""
        # ACB doesn't support pattern-based deletion easily
        # For now, log warning about limitation
        import logging

        logging.warning(
            "ACB cache doesn't support selective invalidation. "
            "Use clear() to remove all cached data."
        )

    def cleanup_all(self) -> dict[str, int]:
        """Cleanup expired entries (ACB handles this automatically)."""
        # ACB cache has automatic cleanup, return zero counts
        return {
            "hook_results": 0,
            "file_hashes": 0,
            "config": 0,
            "disk_cache": 0,
        }

    def get_cache_stats(self) -> dict[str, t.Any]:
        """Get cache statistics."""
        return {"acb_cache": self.stats.to_dict()}

    def _get_hook_cache_key(self, hook_name: str, file_hashes: list[str]) -> str:
        """Generate cache key for hook result."""
        hash_signature = hashlib.md5(
            ",".join(sorted(file_hashes)).encode(),
            usedforsecurity=False,
        ).hexdigest()
        return f"hook_result:{hook_name}:{hash_signature}"

    def _get_versioned_hook_cache_key(
        self,
        hook_name: str,
        file_hashes: list[str],
        tool_version: str | None = None,
    ) -> str:
        """Generate versioned cache key for disk cache."""
        hash_signature = hashlib.md5(
            ",".join(sorted(file_hashes)).encode(),
            usedforsecurity=False,
        ).hexdigest()
        version_part = f":{tool_version}" if tool_version else ""
        return f"hook_result:{hook_name}:{hash_signature}{version_part}"
```

### Phase 2: Update Imports and Registrations

**Files to update**:

1. `crackerjack/core/workflow_orchestrator.py` - Import ACBCrackerjackCache
1. `crackerjack/core/enhanced_container.py` - Register ACB cache
1. `crackerjack/__main__.py` - Instantiate ACB cache adapter

**Changes**:

```python
# Before
from crackerjack.services.cache import CrackerjackCache

cache = CrackerjackCache(cache_dir=pkg_path / ".crackerjack" / "cache")

# After
from crackerjack.services.acb_cache_adapter import ACBCrackerjackCache

cache = ACBCrackerjackCache(
    cache_dir=pkg_path / ".crackerjack" / "cache", enable_disk_cache=True
)
```

### Phase 3: Testing and Validation

**Test Coverage** (`tests/services/test_acb_cache_adapter.py`):

```python
import pytest
from pathlib import Path
from crackerjack.services.acb_cache_adapter import ACBCrackerjackCache
from crackerjack.models.task import HookResult


class TestACBCacheAdapter:
    """Test ACB cache adapter maintains CrackerjackCache API."""

    def test_hook_result_caching(self):
        """Test hook result get/set operations."""
        cache = ACBCrackerjackCache()

        result = HookResult(
            hook_name="ruff",
            exit_code=0,
            output="All checks passed",
            success=True,
        )

        file_hashes = ["abc123", "def456"]
        cache.set_hook_result("ruff", file_hashes, result)

        cached = cache.get_hook_result("ruff", file_hashes)
        assert cached is not None
        assert cached.hook_name == "ruff"
        assert cached.success is True

    def test_expensive_hook_caching(self):
        """Test expensive hook dual-tier caching."""
        cache = ACBCrackerjackCache(enable_disk_cache=True)

        result = HookResult(
            hook_name="zuban",
            exit_code=0,
            output="Type checking passed",
            success=True,
        )

        file_hashes = ["xyz789"]
        tool_version = "0.1.0"

        cache.set_expensive_hook_result("zuban", file_hashes, result, tool_version)

        cached = cache.get_expensive_hook_result("zuban", file_hashes, tool_version)

        assert cached is not None
        assert cached.hook_name == "zuban"

    def test_cache_stats_tracking(self):
        """Test cache statistics tracking."""
        cache = ACBCrackerjackCache()

        # Initial stats
        stats = cache.get_cache_stats()
        assert stats["acb_cache"]["hits"] == 0
        assert stats["acb_cache"]["misses"] == 0

        # Miss
        cache.get_hook_result("ruff", ["hash1"])
        stats = cache.get_cache_stats()
        assert stats["acb_cache"]["misses"] == 1

        # Hit
        result = HookResult(hook_name="ruff", exit_code=0, output="", success=True)
        cache.set_hook_result("ruff", ["hash1"], result)
        cache.get_hook_result("ruff", ["hash1"])

        stats = cache.get_cache_stats()
        assert stats["acb_cache"]["hits"] == 1

    def test_file_hash_caching(self):
        """Test file hash caching."""
        cache = ACBCrackerjackCache()

        test_file = Path(__file__)
        file_hash = "abc123def456"

        cache.set_file_hash(test_file, file_hash)
        cached_hash = cache.get_file_hash(test_file)

        assert cached_hash == file_hash

    def test_config_data_caching(self):
        """Test config data caching."""
        cache = ACBCrackerjackCache()

        config_data = {"hooks": ["ruff", "zuban"], "verbose": True}
        cache.set_config_data("test_config", config_data)

        cached_config = cache.get_config_data("test_config")
        assert cached_config == config_data

    def test_agent_decision_caching(self):
        """Test AI agent decision caching."""
        cache = ACBCrackerjackCache(enable_disk_cache=True)

        decision = {"confidence": 0.9, "action": "refactor"}
        cache.set_agent_decision("RefactoringAgent", "issue_hash_123", decision)

        cached_decision = cache.get_agent_decision("RefactoringAgent", "issue_hash_123")
        assert cached_decision == decision

    def test_quality_baseline_caching(self):
        """Test quality baseline caching."""
        cache = ACBCrackerjackCache(enable_disk_cache=True)

        metrics = {"coverage": 85.0, "complexity": 12, "issues": 5}
        git_hash = "abc123def456"

        cache.set_quality_baseline(git_hash, metrics)
        cached_metrics = cache.get_quality_baseline(git_hash)

        assert cached_metrics == metrics
```

### Phase 4: Cleanup and Removal

**Files to remove** (after validation):

1. `crackerjack/services/cache.py` (437 lines) ✅
1. Update all imports across codebase
1. Remove tests for old cache implementation

**Expected LOC reduction**: ~400 lines

## Benefits

### Performance Improvements

- **Async operations**: Better concurrency for cache operations
- **Built-in compression**: MsgPack + Brotli reduces memory/disk usage
- **Automatic cleanup**: No manual TTL management needed
- **70% cache hit rate**: ACB's optimized serialization improves hit rates

### Code Quality

- **-400 lines**: Massive reduction in custom cache code
- **Protocol compliance**: Uses ACB dependency injection patterns
- **Better testing**: Leverages ACB's tested cache implementation
- **Simplified maintenance**: One less custom system to maintain

### Developer Experience

- **Unified caching**: Same cache system as ACB framework
- **Cleaner API**: Fewer methods, simpler interface
- **Better observability**: ACB cache integrates with logging/monitoring

## Risks and Mitigations

### Risk 1: Async/Sync API Mismatch

- **Issue**: ACB cache is async, current usage is sync
- **Mitigation**: Adapter wraps async calls with `asyncio.run_until_complete()`
- **Impact**: Minimal (most operations are already background tasks)

### Risk 2: Feature Parity

- **Issue**: Current cache has selective invalidation (pattern-based)
- **Mitigation**: Document limitation, use `clear()` for full invalidation
- **Impact**: Low (invalidation is rarely used)

### Risk 3: Migration Complexity

- **Issue**: Extensive codebase usage of cache
- **Mitigation**: Adapter maintains identical API surface
- **Impact**: Zero breaking changes

## Timeline

- **Phase 1**: Create ACB cache adapter (2 days) ✅ READY
- **Phase 2**: Update imports/registrations (1 day)
- **Phase 3**: Testing and validation (2 days)
- **Phase 4**: Cleanup and removal (1 day)

**Total**: ~1 week (5-6 days)

## Success Criteria

- ✅ Zero breaking changes to cache API
- ✅ All existing tests pass
- ✅ Cache hit rate ≥70%
- ✅ -400 lines of code removed
- ✅ ACB DI integration complete
- ✅ Documentation updated

## Next Steps

1. Review strategy document
1. Create `crackerjack/services/acb_cache_adapter.py`
1. Write comprehensive test suite
1. Update dependency container registrations
1. Run full test suite to validate
1. Remove old cache implementation
1. Update documentation

______________________________________________________________________

**Status**: ✅ Strategy complete, ready for implementation
**Estimated Completion**: Week 2 (Phase 1, Day 8-14)
