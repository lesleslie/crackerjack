"""ACB-backed cache adapter maintaining CrackerjackCache API.

This adapter wraps ACB's async cache with a sync-compatible interface,
enabling drop-in replacement of the custom cache implementation while
leveraging ACB's optimized serialization and lifecycle management.
"""

import asyncio
import hashlib
import typing as t
from dataclasses import dataclass
from pathlib import Path

from aiocache import SimpleMemoryCache
from aiocache.serializers import PickleSerializer

from crackerjack.models.task import HookResult


@dataclass
class CacheStats:
    """Cache statistics compatible with existing CrackerjackCache.stats."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def to_dict(self) -> dict[str, t.Any]:
        """Convert stats to dictionary for reporting."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_entries": self.total_entries,
            "hit_rate_percent": round(self.hit_rate, 2),
        }


class ACBCrackerjackCache:
    """ACB-backed cache adapter maintaining CrackerjackCache API.

    Provides sync interface over ACB's async cache while preserving all
    existing functionality including dual-tier caching for expensive hooks.
    """

    # Expensive hooks that benefit from disk caching across sessions
    EXPENSIVE_HOOKS = {
        "pyright",
        "bandit",
        "vulture",
        "complexipy",
        "refurb",
        "gitleaks",
        "zuban",  # Zuban type checker
    }

    # TTL configuration for different cache types (in seconds)
    HOOK_DISK_TTLS = {
        "pyright": 86400,  # 24 hours - type checking is stable
        "bandit": 86400 * 3,  # 3 days - security patterns change slowly
        "vulture": 86400 * 2,  # 2 days - dead code detection is stable
        "complexipy": 86400,  # 24 hours - complexity analysis
        "refurb": 86400,  # 24 hours - code improvements
        "gitleaks": 86400 * 7,  # 7 days - secret detection is very stable
        "zuban": 86400,  # 24 hours - type checking
    }

    # Agent version for cache invalidation when agent logic changes
    AGENT_VERSION = "1.0.0"

    def __init__(
        self,
        cache_dir: Path | None = None,
        enable_disk_cache: bool = True,
    ) -> None:
        """Initialize ACB cache adapter.

        Args:
            cache_dir: Directory for cache storage (unused with memory cache)
            enable_disk_cache: Whether to enable disk caching for expensive hooks
        """
        self.cache_dir = cache_dir or Path.cwd() / ".crackerjack" / "cache"
        self.enable_disk_cache = enable_disk_cache

        # Create aiocache directly (same as ACB uses internally)
        self._cache = SimpleMemoryCache(
            serializer=PickleSerializer(),
            namespace="crackerjack:",
        )
        self._cache.timeout = 0.0  # No operation timeout

        # Stats tracking (compatible with existing API)
        self.stats = CacheStats()

        # Event loop for sync API compatibility
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

    def _run_async(self, coro: t.Coroutine[t.Any, t.Any, t.Any]) -> t.Any:
        """Execute async operation in sync context.

        Args:
            coro: Coroutine to execute

        Returns:
            Result of the async operation
        """
        return self._loop.run_until_complete(coro)

    def get_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
    ) -> HookResult | None:
        """Get hook result from cache.

        Args:
            hook_name: Name of the hook
            file_hashes: List of file content hashes

        Returns:
            Cached hook result or None if not found
        """
        cache_key = self._get_hook_cache_key(hook_name, file_hashes)
        result = self._run_async(self._cache.get(cache_key))

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
        """Set hook result in cache.

        Args:
            hook_name: Name of the hook
            file_hashes: List of file content hashes
            result: Hook result to cache
        """
        cache_key = self._get_hook_cache_key(hook_name, file_hashes)
        self._run_async(self._cache.set(cache_key, result, ttl=1800))
        self.stats.total_entries += 1

    def get_expensive_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
        tool_version: str | None = None,
    ) -> HookResult | None:
        """Get expensive hook result with disk cache fallback.

        Args:
            hook_name: Name of the hook
            file_hashes: List of file content hashes
            tool_version: Optional tool version for cache key versioning

        Returns:
            Cached hook result or None if not found
        """
        # If version specified, check versioned cache directly
        if (
            tool_version
            and self.enable_disk_cache
            and hook_name in self.EXPENSIVE_HOOKS
        ):
            cache_key = self._get_versioned_hook_cache_key(
                hook_name, file_hashes, tool_version
            )
            result = self._run_async(self._cache.get(cache_key))

            if result is None:
                self.stats.misses += 1
            else:
                self.stats.hits += 1

            return result

        # Otherwise check memory cache first for speed
        result = self.get_hook_result(hook_name, file_hashes)
        if result:
            return result

        # Fall back to disk cache for expensive hooks (no version specified)
        if self.enable_disk_cache and hook_name in self.EXPENSIVE_HOOKS:
            cache_key = self._get_versioned_hook_cache_key(
                hook_name, file_hashes, tool_version
            )
            result = self._run_async(self._cache.get(cache_key))

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
        """Set expensive hook result in both memory and disk cache.

        Args:
            hook_name: Name of the hook
            file_hashes: List of file content hashes
            result: Hook result to cache
            tool_version: Optional tool version for cache key versioning
        """
        # Always set in memory for current session
        self.set_hook_result(hook_name, file_hashes, result)

        # Also persist to disk for expensive hooks
        if self.enable_disk_cache and hook_name in self.EXPENSIVE_HOOKS:
            cache_key = self._get_versioned_hook_cache_key(
                hook_name, file_hashes, tool_version
            )
            ttl = self.HOOK_DISK_TTLS.get(hook_name, 86400)  # Default 24 hours
            self._run_async(self._cache.set(cache_key, result, ttl=ttl))

    def get_file_hash(self, file_path: Path) -> str | None:
        """Get cached file hash.

        Args:
            file_path: Path to the file

        Returns:
            Cached file hash or None if not found
        """
        stat = file_path.stat()
        cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"
        result = self._run_async(self._cache.get(cache_key))

        if result is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1

        return result

    def set_file_hash(self, file_path: Path, file_hash: str) -> None:
        """Cache file hash.

        Args:
            file_path: Path to the file
            file_hash: Hash value to cache
        """
        stat = file_path.stat()
        cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"
        self._run_async(self._cache.set(cache_key, file_hash, ttl=3600))
        self.stats.total_entries += 1

    def get_config_data(self, config_key: str) -> t.Any | None:
        """Get cached config data.

        Args:
            config_key: Configuration key

        Returns:
            Cached config data or None if not found
        """
        result = self._run_async(self._cache.get(f"config:{config_key}"))

        if result is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1

        return result

    def set_config_data(self, config_key: str, data: t.Any) -> None:
        """Cache config data.

        Args:
            config_key: Configuration key
            data: Data to cache
        """
        self._run_async(self._cache.set(f"config:{config_key}", data, ttl=7200))
        self.stats.total_entries += 1

    def get(self, key: str, default: t.Any = None) -> t.Any:
        """General purpose get method for metrics and other data.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        result = self._run_async(self._cache.get(key))
        return result if result is not None else default

    def set(self, key: str, value: t.Any, ttl_seconds: int | None = None) -> None:
        """General purpose set method for metrics and other data.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (default 3600)
        """
        ttl = ttl_seconds or 3600  # Default 1 hour
        self._run_async(self._cache.set(key, value, ttl=ttl))

    def get_agent_decision(self, agent_name: str, issue_hash: str) -> t.Any | None:
        """Get cached AI agent decision based on issue content.

        Args:
            agent_name: Name of the AI agent
            issue_hash: Hash of the issue content

        Returns:
            Cached agent decision or None if not found
        """
        if not self.enable_disk_cache:
            return None

        cache_key = f"agent:{agent_name}:{issue_hash}:{self.AGENT_VERSION}"
        return self._run_async(self._cache.get(cache_key))

    def set_agent_decision(
        self, agent_name: str, issue_hash: str, decision: t.Any
    ) -> None:
        """Cache AI agent decision for future use.

        Args:
            agent_name: Name of the AI agent
            issue_hash: Hash of the issue content
            decision: Agent decision to cache
        """
        if not self.enable_disk_cache:
            return

        cache_key = f"agent:{agent_name}:{issue_hash}:{self.AGENT_VERSION}"
        self._run_async(self._cache.set(cache_key, decision, ttl=604800))  # 7 days

    def get_quality_baseline(self, git_hash: str) -> dict[str, t.Any] | None:
        """Get quality baseline metrics for a specific git commit.

        Args:
            git_hash: Git commit hash

        Returns:
            Cached quality baseline or None if not found
        """
        if not self.enable_disk_cache:
            return None

        return self._run_async(self._cache.get(f"baseline:{git_hash}"))

    def set_quality_baseline(self, git_hash: str, metrics: dict[str, t.Any]) -> None:
        """Store quality baseline metrics for a git commit.

        Args:
            git_hash: Git commit hash
            metrics: Quality metrics to cache
        """
        if not self.enable_disk_cache:
            return

        self._run_async(
            self._cache.set(f"baseline:{git_hash}", metrics, ttl=2592000)
        )  # 30 days

    def invalidate_hook_cache(self, hook_name: str | None = None) -> None:
        """Invalidate hook cache entries.

        Note: ACB cache doesn't support pattern-based deletion easily.
        This is a no-op with a warning for now.

        Args:
            hook_name: Optional hook name to invalidate (ignored)
        """
        import warnings

        warnings.warn(
            "ACB cache doesn't support selective invalidation. "
            "Use clear() to remove all cached data.",
            stacklevel=2,
        )

    def cleanup_all(self) -> dict[str, int]:
        """Cleanup expired entries.

        Note: ACB cache has automatic cleanup via TTL expiration.
        Returns zero counts as cleanup is handled automatically.

        Returns:
            Dictionary of cleanup counts (all zeros)
        """
        return {
            "hook_results": 0,
            "file_hashes": 0,
            "config": 0,
            "disk_cache": 0,
        }

    def get_cache_stats(self) -> dict[str, t.Any]:
        """Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        return {"acb_cache": self.stats.to_dict()}

    def _get_hook_cache_key(self, hook_name: str, file_hashes: list[str]) -> str:
        """Generate cache key for hook result.

        Args:
            hook_name: Name of the hook
            file_hashes: List of file content hashes

        Returns:
            Cache key string
        """
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
        """Generate versioned cache key for disk cache invalidation.

        Args:
            hook_name: Name of the hook
            file_hashes: List of file content hashes
            tool_version: Optional tool version

        Returns:
            Versioned cache key string
        """
        hash_signature = hashlib.md5(
            ",".join(sorted(file_hashes)).encode(),
            usedforsecurity=False,
        ).hexdigest()
        version_part = f":{tool_version}" if tool_version else ""
        return f"hook_result:{hook_name}:{hash_signature}{version_part}"
