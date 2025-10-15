import asyncio
import builtins
import hashlib
import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from weakref import WeakValueDictionary

from acb.depends import Inject, depends
from acb.logger import Logger


@dataclass
class CacheEntry:
    value: t.Any
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 300
    invalidation_keys: set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)

    def access(self) -> t.Any:
        self.access_count += 1
        self.last_accessed = datetime.now()
        return self.value


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage_bytes: int = 0

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class PerformanceCache:
    @depends.inject
    def __init__(
        self,
        logger: Inject[Logger],
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
        self._logger = logger
        self._cleanup_task: asyncio.Task[None] | None = None
        self._invalidation_map: dict[str, set[str]] = {}

        self._weak_cache: WeakValueDictionary[str, t.Any] = WeakValueDictionary()

    async def start(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._logger.info("Performance cache started")

    async def stop(self) -> None:
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
        return self.get(key, default)

    def set(
        self,
        key: str,
        value: t.Any,
        ttl_seconds: int | None = None,
        invalidation_keys: set[str] | None = None,
    ) -> None:
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

            for inv_key in inv_keys:
                if inv_key not in self._invalidation_map:
                    self._invalidation_map[inv_key] = set()
                self._invalidation_map[inv_key].add(key)

            self._check_memory_pressure()

    async def set_async(
        self,
        key: str,
        value: t.Any,
        ttl_seconds: int | None = None,
        invalidation_keys: builtins.set[str] | None = None,
    ) -> None:
        self.set(key, value, ttl_seconds, invalidation_keys)

    def invalidate(self, invalidation_key: str) -> int:
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

            del self._invalidation_map[invalidation_key]

            self._logger.debug(
                f"Invalidated {count} cache entries for key: {invalidation_key}"
            )
            return count

    def clear(self) -> None:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._invalidation_map.clear()
            self._stats.evictions += count
            self._logger.info(f"Cleared {count} cache entries")

    def get_stats(self) -> CacheStats:
        with self._lock:
            stats = CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                memory_usage_bytes=self._estimate_memory_usage(),
            )
            return stats

    def _estimate_memory_usage(self) -> int:
        total_size = 0
        for entry in self._cache.values():
            if isinstance(entry.value, str | bytes):
                total_size += len(entry.value)
            elif isinstance(entry.value, list | tuple):
                total_size += len(entry.value) * 100
            elif isinstance(entry.value, dict):
                total_size += len(entry.value) * 200
            else:
                total_size += 1000

        return total_size

    def _check_memory_pressure(self) -> None:
        if self._estimate_memory_usage() > self.max_memory_bytes:
            self._evict_lru_entries()

    def _evict_lru_entries(self) -> None:
        if not self._cache:
            return

        entries_by_access = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed,
        )

        evict_count = max(1, len(entries_by_access) // 4)

        for key, _ in entries_by_access[:evict_count]:
            del self._cache[key]
            self._stats.evictions += 1

        self._logger.debug(f"Evicted {evict_count} LRU cache entries")

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                self._cleanup_expired_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cache cleanup loop: {e}")

    def _cleanup_expired_entries(self) -> None:
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
    def __init__(self, cache: PerformanceCache, logger: Logger):
        self.cache = cache
        self._logger = logger

    def _make_repo_key(self, repo_path: Path, operation: str, params: str = "") -> str:
        repo_hash = hashlib.md5(
            str(repo_path).encode(), usedforsecurity=False
        ).hexdigest()[:8]
        param_hash = (
            hashlib.md5(params.encode(), usedforsecurity=False).hexdigest()[:8]
            if params
            else ""
        )
        return f"git: {repo_hash}: {operation}: {param_hash}"

    def get_branch_info(self, repo_path: Path) -> t.Any:
        key = self._make_repo_key(repo_path, "branch_info")
        return self.cache.get(key)

    def set_branch_info(
        self,
        repo_path: Path,
        branch_info: t.Any,
        ttl_seconds: int = 60,
    ) -> None:
        key = self._make_repo_key(repo_path, "branch_info")
        invalidation_keys = {f"git_repo: {repo_path}"}
        self.cache.set(key, branch_info, ttl_seconds, invalidation_keys)

    def get_file_status(self, repo_path: Path) -> t.Any:
        key = self._make_repo_key(repo_path, "file_status")
        return self.cache.get(key)

    def set_file_status(
        self,
        repo_path: Path,
        file_status: t.Any,
        ttl_seconds: int = 30,
    ) -> None:
        key = self._make_repo_key(repo_path, "file_status")
        invalidation_keys = {f"git_repo: {repo_path}", "git_files"}
        self.cache.set(key, file_status, ttl_seconds, invalidation_keys)

    def invalidate_repo(self, repo_path: Path) -> None:
        self.cache.invalidate(f"git_repo: {repo_path}")
        self._logger.debug(f"Invalidated git cache for repo: {repo_path}")


class FileSystemCache:
    def __init__(self, cache: PerformanceCache, logger: Logger):
        self.cache = cache
        self._logger = logger

    def _make_file_key(self, file_path: Path, operation: str) -> str:
        file_hash = hashlib.md5(
            str(file_path).encode(), usedforsecurity=False
        ).hexdigest()[:8]
        return f"fs: {file_hash}: {operation}"

    def get_file_stats(self, file_path: Path) -> t.Any:
        key = self._make_file_key(file_path, "stats")
        return self.cache.get(key)

    def set_file_stats(
        self,
        file_path: Path,
        stats: t.Any,
        ttl_seconds: int = 60,
    ) -> None:
        key = self._make_file_key(file_path, "stats")
        invalidation_keys = {f"file: {file_path}"}
        self.cache.set(key, stats, ttl_seconds, invalidation_keys)

    def invalidate_file(self, file_path: Path) -> None:
        self.cache.invalidate(f"file: {file_path}")


class CommandResultCache:
    def __init__(self, cache: PerformanceCache, logger: Logger):
        self.cache = cache
        self._logger = logger

    def _make_command_key(self, command: list[str], cwd: Path | None = None) -> str:
        cmd_str = " ".join(command)
        cwd_str = str(cwd) if cwd else ""
        combined = f"{cmd_str}: {cwd_str}"
        cmd_hash = hashlib.md5(combined.encode(), usedforsecurity=False).hexdigest()[
            :12
        ]
        return f"cmd: {cmd_hash}"

    def get_command_result(
        self,
        command: list[str],
        cwd: Path | None = None,
    ) -> t.Any:
        key = self._make_command_key(command, cwd)
        return self.cache.get(key)

    def set_command_result(
        self,
        command: list[str],
        result: t.Any,
        cwd: Path | None = None,
        ttl_seconds: int = 120,
    ) -> None:
        key = self._make_command_key(command, cwd)
        invalidation_keys = {"commands"}
        if cwd:
            invalidation_keys.add(f"cwd: {cwd}")

        self.cache.set(key, result, ttl_seconds, invalidation_keys)

    def invalidate_commands(self) -> None:
        self.cache.invalidate("commands")


_global_cache: PerformanceCache | None = None
_cache_lock = Lock()


def get_performance_cache() -> PerformanceCache:
    global _global_cache
    with _cache_lock:
        if _global_cache is None:
            _global_cache = PerformanceCache()
        return _global_cache


def get_git_cache() -> GitOperationCache:
    performance_cache = get_performance_cache()
    return GitOperationCache(performance_cache, logger=performance_cache._logger)


def get_filesystem_cache() -> FileSystemCache:
    performance_cache = get_performance_cache()
    return FileSystemCache(performance_cache, logger=performance_cache._logger)


def get_command_cache() -> CommandResultCache:
    performance_cache = get_performance_cache()
    return CommandResultCache(performance_cache, logger=performance_cache._logger)
