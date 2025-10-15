import asyncio
import hashlib
import logging
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    from acb.adapters import AdapterNotInstalled, import_adapter
except ImportError:  # pragma: no cover - acb package not available
    AdapterNotInstalled = RuntimeError  # type: ignore[assignment]
    import_adapter = None  # type: ignore[assignment]

try:
    from acb.depends import depends
except ImportError:  # pragma: no cover - acb DI not available
    depends = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from crackerjack.models.task import HookResult

logger = logging.getLogger(__name__)

Cache: Any | None = None
_cache_import_error: Exception | None = None

if import_adapter is not None:
    try:
        Cache = import_adapter("cache")
    except AdapterNotInstalled as exc:  # pragma: no cover - depends on env
        _cache_import_error = exc
        Cache = None
    except Exception as exc:  # pragma: no cover - defensive
        _cache_import_error = exc
        Cache = None


@dataclass
class CacheStats:
    """Cache statistics compatible with legacy cache implementation."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0

    @property
    def hit_rate(self) -> float:
        total_requests = self.hits + self.misses
        return (self.hits / total_requests * 100) if total_requests else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_entries": self.total_entries,
            "hit_rate_percent": round(self.hit_rate, 2),
        }


def get_cache() -> Any:
    """Return the configured cache backend from ACB."""
    if Cache is None or depends is None:
        reason = (
            f"{type(_cache_import_error).__name__}: {_cache_import_error}"
            if _cache_import_error is not None
            else "cache adapter import failed"
        )
        msg = (
            "ACB cache adapter is unavailable. "
            f"Resolve adapter configuration before continuing ({reason})."
        )
        raise RuntimeError(msg)
    try:
        return depends.get(Cache)
    except Exception as exc:  # pragma: no cover - runtime safety
        msg = (
            "Failed to resolve ACB cache adapter via dependency injection. "
            "Ensure adapters.yml specifies a valid cache adapter."
        )
        raise RuntimeError(msg) from exc


class ACBCrackerjackCache:
    """ACB-backed cache adapter with in-memory fallback when adapter missing."""

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
        "zuban": 86400,
    }

    AGENT_VERSION = "1.0.0"

    def __init__(
        self,
        cache_dir: Path | None = None,
        enable_disk_cache: bool = True,
        backend: Any | None = None,
    ) -> None:
        self.cache_dir = cache_dir or Path.cwd() / ".crackerjack" / "cache"
        self.enable_disk_cache = enable_disk_cache
        self.stats = CacheStats()

        if backend is not None:
            self._backend = backend
        else:
            self._backend = get_cache()

    def _run_async(self, coro: Awaitable[Any]) -> Any:
        async def _await(value: Awaitable[Any]) -> Any:
            return await value

        try:
            return asyncio.run(_await(coro))
        except RuntimeError as exc:
            message = str(exc)
            if "asyncio.run()" not in message:
                raise
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_await(coro))
            finally:
                loop.close()

    def get_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
    ) -> HookResult | None:
        cache_key = self._get_hook_cache_key(hook_name, file_hashes)
        result = self._run_async(self._backend.get(cache_key))
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
        cache_key = self._get_hook_cache_key(hook_name, file_hashes)
        self._run_async(self._backend.set(cache_key, result, ttl=1800))
        self.stats.total_entries += 1

    def get_expensive_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
        tool_version: str | None = None,
    ) -> HookResult | None:
        result = self.get_hook_result(hook_name, file_hashes)
        if result is not None:
            return result
        if not self.enable_disk_cache or hook_name not in self.EXPENSIVE_HOOKS:
            return None
        cache_key = self._get_versioned_hook_cache_key(
            hook_name,
            file_hashes,
            tool_version,
        )
        result = self._run_async(self._backend.get(cache_key))
        if result is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1
        return result

    def set_expensive_hook_result(
        self,
        hook_name: str,
        file_hashes: list[str],
        result: HookResult,
        tool_version: str | None = None,
    ) -> None:
        self.set_hook_result(hook_name, file_hashes, result)
        if not self.enable_disk_cache or hook_name not in self.EXPENSIVE_HOOKS:
            return
        cache_key = self._get_versioned_hook_cache_key(
            hook_name,
            file_hashes,
            tool_version,
        )
        ttl = self.HOOK_DISK_TTLS.get(hook_name, 86400)
        self._run_async(self._backend.set(cache_key, result, ttl=ttl))

    def get_file_hash(self, file_path: Path) -> str | None:
        stat = file_path.stat()
        cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"
        result = self._run_async(self._backend.get(cache_key))
        if result is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1
        return result

    def set_file_hash(self, file_path: Path, file_hash: str) -> None:
        stat = file_path.stat()
        cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"
        self._run_async(self._backend.set(cache_key, file_hash, ttl=3600))
        self.stats.total_entries += 1

    def get_config_data(self, config_key: str) -> Any | None:
        result = self._run_async(self._backend.get(f"config:{config_key}"))
        if result is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1
        return result

    def set_config_data(self, config_key: str, data: Any) -> None:
        self._run_async(self._backend.set(f"config:{config_key}", data, ttl=7200))
        self.stats.total_entries += 1

    def get(self, key: str, default: Any = None) -> Any:
        result = self._run_async(self._backend.get(key))
        return result if result is not None else default

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else 3600
        self._run_async(self._backend.set(key, value, ttl=ttl))

    def get_agent_decision(self, agent_name: str, issue_hash: str) -> Any | None:
        if not self.enable_disk_cache:
            return None
        cache_key = f"agent:{agent_name}:{issue_hash}:{self.AGENT_VERSION}"
        return self._run_async(self._backend.get(cache_key))

    def set_agent_decision(
        self,
        agent_name: str,
        issue_hash: str,
        decision: Any,
    ) -> None:
        if not self.enable_disk_cache:
            return
        cache_key = f"agent:{agent_name}:{issue_hash}:{self.AGENT_VERSION}"
        self._run_async(self._backend.set(cache_key, decision, ttl=604800))

    def get_quality_baseline(self, git_hash: str) -> dict[str, Any] | None:
        if not self.enable_disk_cache:
            return None
        return self._run_async(self._backend.get(f"baseline:{git_hash}"))

    def set_quality_baseline(
        self,
        git_hash: str,
        metrics: dict[str, Any],
    ) -> None:
        if not self.enable_disk_cache:
            return
        self._run_async(self._backend.set(f"baseline:{git_hash}", metrics, ttl=2592000))

    def invalidate_hook_cache(self, hook_name: str | None = None) -> None:
        logger.warning(
            "ACB cache fallback does not support selective invalidation (hook=%s).",
            hook_name,
        )

    def cleanup_all(self) -> dict[str, int]:
        return {
            "hook_results": 0,
            "file_hashes": 0,
            "config": 0,
            "disk_cache": 0,
        }

    def get_cache_stats(self) -> dict[str, Any]:
        return {"acb_cache": self.stats.to_dict()}

    def _get_hook_cache_key(self, hook_name: str, file_hashes: list[str]) -> str:
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
        version_part = f":{tool_version}" if tool_version else ""
        base_key = self._get_hook_cache_key(hook_name, file_hashes)
        return f"{base_key}{version_part}"


__all__ = ["ACBCrackerjackCache", "CacheStats", "Cache", "get_cache"]
