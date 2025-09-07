"""Performance-optimized caching layer for expensive operations.

This module provides intelligent caching for git operations, file system checks,
and command results to significantly improve workflow performance.
"""

import asyncio
import builtins
import hashlib
import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from weakref import WeakValueDictionary

from crackerjack.services.logging import get_logger


@dataclass
class CacheEntry:
    """Represents a cached value with metadata."""

    value: t.Any
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 300  # Default 5 minutes
    invalidation_keys: set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl_seconds <= 0:  # Permanent cache
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)

    def access(self) -> t.Any:
        """Mark entry as accessed and return value."""
        self.access_count += 1
        self.last_accessed = datetime.now()
        return self.value


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage_bytes: int = 0

    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class PerformanceCache:
    """High-performance async cache with intelligent invalidation."""

    def __init__(
        self,
        max_memory_mb: int = 50,
        default_ttl_seconds: int = 300,
        cleanup_interval_seconds: int = 60,
    ):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds

        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._stats = CacheStats()
        self._logger = get_logger("crackerjack.performance_cache")
        self._cleanup_task: asyncio.Task[None] | None = None
        self._invalidation_map: dict[str, set[str]] = {}

        # Weak reference cache for heavy objects
        self._weak_cache: WeakValueDictionary[str, t.Any] = WeakValueDictionary()

    async def start(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._logger.info("Performance cache started")

    async def stop(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            self._logger.info("Performance cache stopped")

    def get(
        self,
        key: str,
        default: t.Any = None,
    ) -> t.Any:
        """Get value from cache."""
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return default

            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                return default

            self._stats.hits += 1
            return entry.access()

    async def get_async(
        self,
        key: str,
        default: t.Any = None,
    ) -> t.Any:
        """Async version of get for compatibility."""
        return self.get(key, default)

    def set(
        self,
        key: str,
        value: t.Any,
        ttl_seconds: int | None = None,
        invalidation_keys: set[str] | None = None,
    ) -> None:
        """Set value in cache."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        inv_keys = invalidation_keys or set()

        entry = CacheEntry(
            value=value,
            created_at=datetime.now(),
            ttl_seconds=ttl,
            invalidation_keys=inv_keys,
        )

        with self._lock:
            self._cache[key] = entry

            # Update invalidation map
            for inv_key in inv_keys:
                if inv_key not in self._invalidation_map:
                    self._invalidation_map[inv_key] = set()
                self._invalidation_map[inv_key].add(key)

            # Check memory usage and evict if needed
            self._check_memory_pressure()

    async def set_async(
        self,
        key: str,
        value: t.Any,
        ttl_seconds: int | None = None,
        invalidation_keys: builtins.set[str] | None = None,
    ) -> None:
        """Async version of set for compatibility."""
        self.set(key, value, ttl_seconds, invalidation_keys)

    def invalidate(self, invalidation_key: str) -> int:
        """Invalidate all entries with given invalidation key."""
        with self._lock:
            if invalidation_key not in self._invalidation_map:
                return 0

            keys_to_remove = self._invalidation_map[invalidation_key].copy()
            count = 0

            for key in keys_to_remove:
                if key in self._cache:
                    del self._cache[key]
                    count += 1
                    self._stats.evictions += 1

            # Clean up invalidation map
            del self._invalidation_map[invalidation_key]

            self._logger.debug(
                f"Invalidated {count} cache entries for key: {invalidation_key}"
            )
            return count

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._invalidation_map.clear()
            self._stats.evictions += count
            self._logger.info(f"Cleared {count} cache entries")

    def get_stats(self) -> CacheStats:
        """Get cache performance statistics."""
        with self._lock:
            stats = CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                memory_usage_bytes=self._estimate_memory_usage(),
            )
            return stats

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage of cache entries."""
        # Simplified estimation - in production would use more sophisticated method
        total_size = 0
        for entry in self._cache.values():
            if isinstance(entry.value, str | bytes):
                total_size += len(entry.value)
            elif isinstance(entry.value, list | tuple):
                total_size += len(entry.value) * 100  # Rough estimate
            elif isinstance(entry.value, dict):
                total_size += len(entry.value) * 200  # Rough estimate
            else:
                total_size += 1000  # Default estimate for other objects

        return total_size

    def _check_memory_pressure(self) -> None:
        """Check memory usage and evict entries if needed."""
        if self._estimate_memory_usage() > self.max_memory_bytes:
            self._evict_lru_entries()

    def _evict_lru_entries(self) -> None:
        """Evict least recently used entries to free memory."""
        if not self._cache:
            return

        # Sort entries by last access time (oldest first)
        entries_by_access = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed,
        )

        # Remove oldest 25% of entries
        evict_count = max(1, len(entries_by_access) // 4)

        for key, _ in entries_by_access[:evict_count]:
            del self._cache[key]
            self._stats.evictions += 1

        self._logger.debug(f"Evicted {evict_count} LRU cache entries")

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for expired entries."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                self._cleanup_expired_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cache cleanup loop: {e}")

    def _cleanup_expired_entries(self) -> None:
        """Clean up expired cache entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]
                self._stats.evictions += 1

            if expired_keys:
                self._logger.debug(f"Cleaned up {len(expired_keys)} expired entries")


class GitOperationCache:
    """Specialized cache for Git operations."""

    def __init__(self, cache: PerformanceCache):
        self.cache = cache
        self._logger = get_logger("crackerjack.git_cache")

    def _make_repo_key(self, repo_path: Path, operation: str, params: str = "") -> str:
        """Create cache key for git operation."""
        repo_hash = hashlib.md5(
            str(repo_path).encode(), usedforsecurity=False
        ).hexdigest()[:8]
        param_hash = (
            hashlib.md5(params.encode(), usedforsecurity=False).hexdigest()[:8]
            if params
            else ""
        )
        return f"git:{repo_hash}:{operation}:{param_hash}"

    def get_branch_info(self, repo_path: Path) -> t.Any:
        """Get cached branch information."""
        key = self._make_repo_key(repo_path, "branch_info")
        return self.cache.get(key)

    def set_branch_info(
        self,
        repo_path: Path,
        branch_info: t.Any,
        ttl_seconds: int = 60,
    ) -> None:
        """Cache branch information."""
        key = self._make_repo_key(repo_path, "branch_info")
        invalidation_keys = {f"git_repo:{repo_path}"}
        self.cache.set(key, branch_info, ttl_seconds, invalidation_keys)

    def get_file_status(self, repo_path: Path) -> t.Any:
        """Get cached file status."""
        key = self._make_repo_key(repo_path, "file_status")
        return self.cache.get(key)

    def set_file_status(
        self,
        repo_path: Path,
        file_status: t.Any,
        ttl_seconds: int = 30,
    ) -> None:
        """Cache file status."""
        key = self._make_repo_key(repo_path, "file_status")
        invalidation_keys = {f"git_repo:{repo_path}", "git_files"}
        self.cache.set(key, file_status, ttl_seconds, invalidation_keys)

    def invalidate_repo(self, repo_path: Path) -> None:
        """Invalidate all cache entries for a repository."""
        self.cache.invalidate(f"git_repo:{repo_path}")
        self._logger.debug(f"Invalidated git cache for repo: {repo_path}")


class FileSystemCache:
    """Specialized cache for file system operations."""

    def __init__(self, cache: PerformanceCache):
        self.cache = cache
        self._logger = get_logger("crackerjack.filesystem_cache")

    def _make_file_key(self, file_path: Path, operation: str) -> str:
        """Create cache key for file operation."""
        file_hash = hashlib.md5(
            str(file_path).encode(), usedforsecurity=False
        ).hexdigest()[:8]
        return f"fs:{file_hash}:{operation}"

    def get_file_stats(self, file_path: Path) -> t.Any:
        """Get cached file statistics."""
        key = self._make_file_key(file_path, "stats")
        return self.cache.get(key)

    def set_file_stats(
        self,
        file_path: Path,
        stats: t.Any,
        ttl_seconds: int = 60,
    ) -> None:
        """Cache file statistics."""
        key = self._make_file_key(file_path, "stats")
        invalidation_keys = {f"file:{file_path}"}
        self.cache.set(key, stats, ttl_seconds, invalidation_keys)

    def invalidate_file(self, file_path: Path) -> None:
        """Invalidate cache entries for a specific file."""
        self.cache.invalidate(f"file:{file_path}")


class CommandResultCache:
    """Specialized cache for command execution results."""

    def __init__(self, cache: PerformanceCache):
        self.cache = cache
        self._logger = get_logger("crackerjack.command_cache")

    def _make_command_key(self, command: list[str], cwd: Path | None = None) -> str:
        """Create cache key for command execution."""
        cmd_str = " ".join(command)
        cwd_str = str(cwd) if cwd else ""
        combined = f"{cmd_str}:{cwd_str}"
        cmd_hash = hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()[
            :12
        ]
        return f"cmd:{cmd_hash}"

    def get_command_result(
        self,
        command: list[str],
        cwd: Path | None = None,
    ) -> t.Any:
        """Get cached command result."""
        key = self._make_command_key(command, cwd)
        return self.cache.get(key)

    def set_command_result(
        self,
        command: list[str],
        result: t.Any,
        cwd: Path | None = None,
        ttl_seconds: int = 120,
    ) -> None:
        """Cache command execution result."""
        key = self._make_command_key(command, cwd)
        invalidation_keys = {"commands"}
        if cwd:
            invalidation_keys.add(f"cwd:{cwd}")

        self.cache.set(key, result, ttl_seconds, invalidation_keys)

    def invalidate_commands(self) -> None:
        """Invalidate all cached command results."""
        self.cache.invalidate("commands")


# Global cache instance for the application
_global_cache: PerformanceCache | None = None
_cache_lock = Lock()


def get_performance_cache() -> PerformanceCache:
    """Get global performance cache instance."""
    global _global_cache
    with _cache_lock:
        if _global_cache is None:
            _global_cache = PerformanceCache()
        return _global_cache


def get_git_cache() -> GitOperationCache:
    """Get Git operation cache instance."""
    return GitOperationCache(get_performance_cache())


def get_filesystem_cache() -> FileSystemCache:
    """Get file system cache instance."""
    return FileSystemCache(get_performance_cache())


def get_command_cache() -> CommandResultCache:
    """Get command result cache instance."""
    return CommandResultCache(get_performance_cache())
