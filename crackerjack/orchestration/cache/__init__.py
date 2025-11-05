"""Cache adapters for hook orchestration.

This package provides caching strategies for hook results:
- ToolProxyCacheAdapter: Bridges to existing tool_proxy cache infrastructure
- MemoryCacheAdapter: In-memory LRU cache for testing
- RedisCacheAdapter: Redis-backed caching (Phase 4+)

Cache Strategy:
- Content-based keys: {hook_name}:{config_hash}:{content_hash}
- TTL support: Configurable time-to-live per result
- Cache invalidation: Automatic on file content changes
"""

from __future__ import annotations

__all__ = [
    "ToolProxyCacheAdapter",
    "MemoryCacheAdapter",
]


# Lazy imports
from typing import Any


def __getattr__(name: str) -> Any:
    if name == "ToolProxyCacheAdapter":
        from crackerjack.orchestration.cache.tool_proxy_cache import (
            ToolProxyCacheAdapter,
        )

        return ToolProxyCacheAdapter
    elif name == "MemoryCacheAdapter":
        from crackerjack.orchestration.cache.memory_cache import MemoryCacheAdapter

        return MemoryCacheAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
