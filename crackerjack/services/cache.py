import hashlib
import json
import time
import typing as t
from dataclasses import asdict, dataclass, field
from pathlib import Path

from crackerjack.models.task import HookResult


@dataclass
class CacheEntry:
    key: str
    value: t.Any
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    ttl_seconds: int = 3600
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> int:
        return int(time.time() - self.created_at)

    def touch(self) -> None:
        self.accessed_at = time.time()
        self.access_count += 1

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "CacheEntry":
        """Create from dict loaded from JSON."""
        return cls(**data)


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0
    total_size_bytes: int = 0

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
            "total_size_mb": round(self.total_size_bytes / 1024 / 1024, 2),
        }


class InMemoryCache:
    def __init__(self, max_entries: int = 1000, default_ttl: int = 3600) -> None:
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._cache: dict[str, CacheEntry] = {}
        self.stats = CacheStats()

    def get(self, key: str) -> t.Any | None:
        entry = self._cache.get(key)

        if entry is None:
            self.stats.misses += 1
            return None

        if entry.is_expired:
            del self._cache[key]
            self.stats.misses += 1
            self.stats.evictions += 1
            return None

        entry.touch()
        self.stats.hits += 1
        return entry.value

    def set(self, key: str, value: t.Any, ttl_seconds: int | None = None) -> None:
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl

        if len(self._cache) >= self.max_entries:
            self._evict_lru()

        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
        )

        self.stats.total_entries = len(self._cache)

    def invalidate(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            self.stats.total_entries = len(self._cache)
            return True
        return False

    def clear(self) -> None:
        evicted = len(self._cache)
        self._cache.clear()
        self.stats.evictions += evicted
        self.stats.total_entries = 0

    def cleanup_expired(self) -> int:
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired]

        for key in expired_keys:
            del self._cache[key]

        self.stats.evictions += len(expired_keys)
        self.stats.total_entries = len(self._cache)
        return len(expired_keys)

    def _evict_lru(self) -> None:
        if not self._cache:
            return

        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].accessed_at)

        del self._cache[lru_key]
        self.stats.evictions += 1


class FileCache:
    def __init__(self, cache_dir: Path, namespace: str = "crackerjack") -> None:
        self.cache_dir = cache_dir / namespace
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = CacheStats()

    def get(self, key: str) -> t.Any | None:
        cache_file = self._get_cache_file(key)

        if not cache_file.exists():
            self.stats.misses += 1
            return None

        try:
            with cache_file.open(encoding="utf-8") as f:
                data = json.load(f)
                entry = CacheEntry.from_dict(data)

            if entry.is_expired:
                cache_file.unlink(missing_ok=True)
                self.stats.misses += 1
                self.stats.evictions += 1
                return None

            entry.touch()

            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f)

            self.stats.hits += 1
            return entry.value

        except (json.JSONDecodeError, FileNotFoundError, OSError, KeyError):
            self.stats.misses += 1
            cache_file.unlink(missing_ok=True)
            return None

    def set(self, key: str, value: t.Any, ttl_seconds: int = 3600) -> None:
        cache_file = self._get_cache_file(key)

        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
        )

        try:
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f)
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    def invalidate(self, key: str) -> bool:
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            cache_file.unlink()
            return True
        return False

    def clear(self) -> None:
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink(missing_ok=True)

    def cleanup_expired(self) -> int:
        removed = 0
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                with cache_file.open(encoding="utf-8") as f:
                    data = json.load(f)
                    entry = CacheEntry.from_dict(data)

                if entry.is_expired:
                    cache_file.unlink()
                    removed += 1
            except (json.JSONDecodeError, FileNotFoundError, OSError, KeyError):
                cache_file.unlink(missing_ok=True)
                removed += 1

        self.stats.evictions += removed
        return removed

    def _get_cache_file(self, key: str) -> Path:
        safe_key = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()
        return self.cache_dir / f"{safe_key}.cache"


class CrackerjackCache:
    def __init__(
        self,
        cache_dir: Path | None = None,
        enable_disk_cache: bool = True,
    ) -> None:
        self.cache_dir = cache_dir or Path.cwd() / ".crackerjack_cache"
        self.enable_disk_cache = enable_disk_cache

        self.hook_results_cache = InMemoryCache(max_entries=500, default_ttl=1800)
        self.file_hash_cache = InMemoryCache(max_entries=2000)
        self.config_cache = InMemoryCache(max_entries=100, default_ttl=7200)

        if enable_disk_cache:
            self.disk_cache = FileCache(self.cache_dir)

    def get_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
    ) -> HookResult | None:
        cache_key = self._get_hook_cache_key(hook_name, file_hashes)
        return self.hook_results_cache.get(cache_key)

    def set_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
        result: HookResult,
    ) -> None:
        cache_key = self._get_hook_cache_key(hook_name, file_hashes)
        self.hook_results_cache.set(cache_key, result, ttl_seconds=1800)

    def get_file_hash(self, file_path: Path) -> str | None:
        stat = file_path.stat()
        cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"
        return self.file_hash_cache.get(cache_key)

    def set_file_hash(self, file_path: Path, file_hash: str) -> None:
        stat = file_path.stat()
        cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"
        self.file_hash_cache.set(cache_key, file_hash, ttl_seconds=3600)

    def get_config_data(self, config_key: str) -> t.Any | None:
        return self.config_cache.get(f"config:{config_key}")

    def set_config_data(self, config_key: str, data: t.Any) -> None:
        self.config_cache.set(f"config:{config_key}", data, ttl_seconds=7200)

    def invalidate_hook_cache(self, hook_name: str | None = None) -> None:
        if hook_name:
            keys_to_remove = [
                key
                for key in self.hook_results_cache._cache
                if key.startswith(f"hook_result:{hook_name}:")
            ]
            for key in keys_to_remove:
                self.hook_results_cache.invalidate(key)
        else:
            self.hook_results_cache.clear()

    def cleanup_all(self) -> dict[str, int]:
        results = {
            "hook_results": self.hook_results_cache.cleanup_expired(),
            "file_hashes": self.file_hash_cache.cleanup_expired(),
            "config": self.config_cache.cleanup_expired(),
        }

        if self.enable_disk_cache:
            results["disk_cache"] = self.disk_cache.cleanup_expired()

        return results

    def get_cache_stats(self) -> dict[str, t.Any]:
        stats = {
            "hook_results": self.hook_results_cache.stats.to_dict(),
            "file_hashes": self.file_hash_cache.stats.to_dict(),
            "config": self.config_cache.stats.to_dict(),
        }

        if self.enable_disk_cache:
            stats["disk_cache"] = self.disk_cache.stats.to_dict()

        return stats

    def _get_hook_cache_key(self, hook_name: str, file_hashes: list[str]) -> str:
        hash_signature = hashlib.md5(
            ",".join(sorted(file_hashes)).encode(),
            usedforsecurity=False,
        ).hexdigest()
        return f"hook_result:{hook_name}:{hash_signature}"
