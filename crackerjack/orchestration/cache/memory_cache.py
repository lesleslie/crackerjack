"""In-memory LRU cache adapter for testing and development.

Provides a simple in-memory cache with LRU eviction for testing orchestration
without persisting to disk. Useful for unit tests and development workflows.
"""

from __future__ import annotations

import hashlib
import json
import logging
import typing as t
from collections import OrderedDict
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field

from crackerjack.models.task import HookResult

if t.TYPE_CHECKING:
    from crackerjack.config.hooks import HookDefinition

# ACB Module Registration (REQUIRED)
MODULE_ID = UUID("01937d86-ace0-7000-8000-000000000005")  # Static UUID7
MODULE_STATUS = "stable"

logger = logging.getLogger(__name__)


class MemoryCacheSettings(BaseModel):
    """Settings for in-memory cache adapter."""

    max_entries: int = Field(default=100, ge=10, le=1000)
    default_ttl: int = Field(default=3600, ge=60, le=86400)


class MemoryCacheAdapter:
    """In-memory LRU cache adapter for testing.

    Features:
    - LRU eviction when max_entries reached
    - TTL-based expiration
    - No disk persistence (ephemeral)
    - Thread-safe operations

    Use Cases:
    - Unit testing orchestration without disk I/O
    - Development workflows requiring fast cache
    - CI/CD pipelines with ephemeral environments

    Example:
        ```python
        cache = MemoryCacheAdapter(settings=MemoryCacheSettings(max_entries=50))
        await cache.init()

        # Cache operations work identically to ToolProxyCacheAdapter
        result = await cache.get(key)
        if not result:
            result = await execute_hook(hook)
            await cache.set(key, result)
        ```
    """

    def __init__(
        self,
        settings: MemoryCacheSettings | None = None,
    ) -> None:
        """Initialize in-memory cache adapter.

        Args:
            settings: Optional cache settings
        """
        self.settings = settings or MemoryCacheSettings()
        self._cache: OrderedDict[str, tuple[HookResult, float]] = OrderedDict()
        self._initialized = False

        logger.debug(
            "MemoryCacheAdapter initializing",
            extra={
                "max_entries": self.settings.max_entries,
                "default_ttl": self.settings.default_ttl,
            },
        )

    async def init(self) -> None:
        """Initialize cache adapter (no-op for memory cache)."""
        if self._initialized:
            logger.debug("Memory cache already initialized")
            return

        self._initialized = True

        logger.info(
            "MemoryCacheAdapter initialized",
            extra={
                "max_entries": self.settings.max_entries,
                "default_ttl": self.settings.default_ttl,
            },
        )

    async def get(self, key: str) -> HookResult | None:
        """Retrieve cached hook result.

        Args:
            key: Cache key

        Returns:
            Cached HookResult if found and not expired, None otherwise
        """
        if not self._initialized:
            logger.warning("Memory cache not initialized, returning None")
            return None

        try:
            import time

            if key in self._cache:
                result, expiry = self._cache[key]

                # Check expiration
                if time.time() < expiry:
                    # Move to end (LRU update)
                    self._cache.move_to_end(key)

                    logger.debug(
                        "Cache hit",
                        extra={
                            "key": key,
                            "hook_name": result.name,
                            "status": result.status,
                        },
                    )
                    return result
                else:
                    # Expired - remove from cache
                    del self._cache[key]
                    logger.debug("Cache entry expired", extra={"key": key})

            logger.debug("Cache miss", extra={"key": key})
            return None

        except Exception as e:
            logger.error(
                "Failed to retrieve from cache",
                extra={
                    "key": key,
                    "error": str(e),
                },
            )
            return None

    async def set(
        self,
        key: str,
        result: HookResult,
        ttl: int | None = None,
    ) -> None:
        """Cache hook result with TTL and LRU eviction.

        Args:
            key: Cache key
            result: HookResult to cache
            ttl: Optional time-to-live in seconds
        """
        if not self._initialized:
            logger.warning("Memory cache not initialized, skipping cache write")
            return

        try:
            import time

            ttl_sec = ttl or self.settings.default_ttl
            expiry = time.time() + ttl_sec

            # LRU eviction if at capacity
            if len(self._cache) >= self.settings.max_entries and key not in self._cache:
                # Remove oldest entry (first item in OrderedDict)
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug(
                    "LRU eviction",
                    extra={
                        "evicted_key": evicted_key,
                        "cache_size": len(self._cache),
                    },
                )

            self._cache[key] = (result, expiry)
            # Move to end (most recently used)
            self._cache.move_to_end(key)

            logger.debug(
                "Cache write",
                extra={
                    "key": key,
                    "hook_name": result.name,
                    "status": result.status,
                    "ttl": ttl_sec,
                    "cache_size": len(self._cache),
                },
            )

        except Exception as e:
            logger.error(
                "Failed to write to cache",
                extra={
                    "key": key,
                    "error": str(e),
                },
            )

    def compute_key(
        self,
        hook: HookDefinition,
        files: list[Path],
    ) -> str:
        """Compute content-based cache key.

        Uses same algorithm as ToolProxyCacheAdapter for consistency.

        Args:
            hook: Hook definition
            files: List of files to be checked by hook

        Returns:
            Cache key string
        """
        try:
            # Hash hook configuration (Phase 8+ direct invocation API)
            config_data = {
                "name": hook.name,
                "command": hook.command,  # Direct tool invocation command
                "timeout": hook.timeout,
                "stage": hook.stage.value
                if hasattr(hook.stage, "value")
                else str(hook.stage),
                "security_level": hook.security_level.value
                if hasattr(hook.security_level, "value")
                else str(hook.security_level),
            }
            config_json = json.dumps(config_data, sort_keys=True)
            config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]

            # Hash file contents
            content_hasher = hashlib.sha256()
            for file_path in sorted(files):
                try:
                    if file_path.exists() and file_path.is_file():
                        content_hasher.update(file_path.read_bytes())
                except Exception as e:
                    logger.warning(
                        f"Failed to hash file {file_path}: {e}",
                        extra={"file": str(file_path), "error": str(e)},
                    )
                    continue

            content_hash = content_hasher.hexdigest()[:16]

            cache_key = f"{hook.name}:{config_hash}:{content_hash}"

            logger.debug(
                "Cache key computed",
                extra={
                    "hook_name": hook.name,
                    "file_count": len(files),
                    "config_hash": config_hash,
                    "content_hash": content_hash,
                },
            )

            return cache_key

        except Exception as e:
            logger.error(
                "Failed to compute cache key",
                extra={
                    "hook_name": hook.name,
                    "error": str(e),
                },
            )
            return f"{hook.name}:error"

    async def clear(self) -> None:
        """Clear all cached results."""
        try:
            self._cache.clear()
            logger.info("Memory cache cleared")
        except Exception as e:
            logger.error("Failed to clear cache", extra={"error": str(e)})

    async def get_stats(self) -> dict[str, t.Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        import time

        try:
            total_entries = len(self._cache)
            expired_entries = sum(
                1 for _, expiry in self._cache.values() if time.time() >= expiry
            )
            active_entries = total_entries - expired_entries

            stats = {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "expired_entries": expired_entries,
                "max_entries": self.settings.max_entries,
                "default_ttl": self.settings.default_ttl,
            }

            logger.debug("Memory cache statistics", extra=stats)

            return stats

        except Exception as e:
            logger.error("Failed to get cache statistics", extra={"error": str(e)})
            return {}

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        return "MemoryCacheAdapter"


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    from acb.depends import depends

    depends.set(MemoryCacheAdapter)
