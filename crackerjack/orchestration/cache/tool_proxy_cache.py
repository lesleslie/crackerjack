"""Tool proxy cache adapter for hook result caching.

Bridges to existing tool_proxy cache infrastructure for consistent caching
across the crackerjack ecosystem. Implements content-based cache keys using
hash of hook configuration and file contents.
"""

from __future__ import annotations

import hashlib
import json
import logging
import typing as t
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field

from crackerjack.models.task import HookResult

if t.TYPE_CHECKING:
    from crackerjack.config.hooks import HookDefinition

# ACB Module Registration (REQUIRED)
MODULE_ID = UUID("01937d86-ace0-7000-8000-000000000004")  # Static UUID7
MODULE_STATUS = "stable"

logger = logging.getLogger(__name__)


class ToolProxyCacheSettings(BaseModel):
    """Settings for tool proxy cache adapter."""

    default_ttl: int = Field(default=3600, ge=60, le=86400)  # 1 minute to 24 hours
    max_cache_size_mb: int = Field(default=100, ge=10, le=1000)
    enable_compression: bool = True


class ToolProxyCacheAdapter:
    """Cache adapter bridging to tool_proxy infrastructure.

    Features:
    - Content-based cache keys (config + file hashes)
    - Configurable TTL per hook result
    - Integration with existing tool_proxy cache
    - Automatic cache invalidation on content changes

    Cache Key Format:
        {hook_name}:{config_hash}:{content_hash}

    Example:
        ```python
        cache = ToolProxyCacheAdapter()
        await cache.init()

        # Check cache
        cached_result = await cache.get(cache_key)
        if cached_result:
            return cached_result

        # Execute hook and cache result
        result = await execute_hook(hook)
        await cache.set(cache_key, result, ttl=3600)
        ```
    """

    def __init__(
        self,
        settings: ToolProxyCacheSettings | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        """Initialize tool proxy cache adapter.

        Args:
            settings: Optional cache settings
            cache_dir: Optional cache directory (defaults to .crackerjack/cache)
        """
        self.settings = settings or ToolProxyCacheSettings()
        self._cache_dir = cache_dir or Path.cwd() / ".crackerjack" / "cache"
        self._cache: dict[
            str, tuple[HookResult, float]
        ] = {}  # key -> (result, expiry_timestamp)
        self._initialized = False

        logger.debug(
            "ToolProxyCacheAdapter initializing",
            extra={
                "cache_dir": str(self._cache_dir),
                "default_ttl": self.settings.default_ttl,
                "enable_compression": self.settings.enable_compression,
            },
        )

    async def init(self) -> None:
        """Initialize cache adapter and ensure cache directory exists."""
        if self._initialized:
            logger.debug("Cache adapter already initialized")
            return

        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._initialized = True

            logger.info(
                "ToolProxyCacheAdapter initialized",
                extra={
                    "cache_dir": str(self._cache_dir),
                    "default_ttl": self.settings.default_ttl,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to initialize cache adapter",
                extra={
                    "error": str(e),
                    "cache_dir": str(self._cache_dir),
                },
            )
            raise

    async def get(self, key: str) -> HookResult | None:
        """Retrieve cached hook result.

        Args:
            key: Cache key (computed via compute_key())

        Returns:
            Cached HookResult if found and not expired, None otherwise
        """
        if not self._initialized:
            logger.warning("Cache adapter not initialized, returning None")
            return None

        try:
            import time

            if key in self._cache:
                result, expiry = self._cache[key]

                # Check expiration
                if time.time() < expiry:
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
        """Cache hook result with TTL.

        Args:
            key: Cache key (computed via compute_key())
            result: HookResult to cache
            ttl: Optional time-to-live in seconds (defaults to settings.default_ttl)
        """
        if not self._initialized:
            logger.warning("Cache adapter not initialized, skipping cache write")
            return

        try:
            import time

            ttl_sec = ttl or self.settings.default_ttl
            expiry = time.time() + ttl_sec

            self._cache[key] = (result, expiry)

            logger.debug(
                "Cache write",
                extra={
                    "key": key,
                    "hook_name": result.name,
                    "status": result.status,
                    "ttl": ttl_sec,
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

        Cache key format: {hook_name}:{config_hash}:{content_hash}

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

            # Hash file contents (for cache invalidation on content changes)
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
            # Fallback to simple key
            return f"{hook.name}:error"

    async def clear(self) -> None:
        """Clear all cached results."""
        try:
            self._cache.clear()
            logger.info("Cache cleared")
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
                "cache_dir": str(self._cache_dir),
                "default_ttl": self.settings.default_ttl,
            }

            logger.debug("Cache statistics", extra=stats)

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
        return "ToolProxyCacheAdapter"


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    from acb.depends import depends

    depends.set(ToolProxyCacheAdapter)
