# Orchestration Cache

> Crackerjack Docs: [Main](../../../README.md) | [CLAUDE.md](../../../docs/guides/CLAUDE.md) | [Orchestration](../README.md) | [Cache](./README.md)

High-performance caching infrastructure for hook execution results with content-based invalidation.

## Overview

The orchestration cache provides intelligent result caching for pre-commit hooks and QA checks. By using content-based cache keys (file hashes + configuration), it achieves **~70% cache hit rates** in typical workflows, dramatically reducing execution time for unchanged code.

## Key Components

### tool_proxy_cache.py - Content-Based Caching

**ToolProxyCacheAdapter** - Main cache implementation:

- Content-based cache keys using SHA256 file hashing
- Configurable TTL (time-to-live) per result
- Automatic invalidation on file content changes
- Integration with existing tool_proxy infrastructure
- Compression support for large results
- In-memory storage with optional disk persistence

**Cache Key Format:**

```
{hook_name}:{config_hash}:{content_hash}

Example:
ruff-format:a3f21b8c:7d9e4a2f
```

**ToolProxyCacheSettings** - Configuration model:

- `default_ttl` - Default time-to-live in seconds (default: 3600)
- `max_cache_size_mb` - Maximum cache size in MB (default: 100)
- `enable_compression` - Enable result compression (default: True)

### memory_cache.py - In-Memory Cache

**MemoryCacheAdapter** - Simple LRU cache:

- Fast in-memory storage
- Least Recently Used (LRU) eviction
- No persistence (ephemeral)
- Useful for testing and development

## Usage Examples

### Basic Caching

```python
from pathlib import Path
from crackerjack.orchestration.cache import ToolProxyCacheAdapter
from crackerjack.config.hooks import HookDefinition
from crackerjack.models.task import HookResult

# Initialize cache
cache = ToolProxyCacheAdapter()
await cache.init()

# Define hook and files
hook = HookDefinition(name="ruff-format", command=["ruff", "format"])
files = [Path("src/main.py"), Path("src/utils.py")]

# Compute cache key
cache_key = cache.compute_key(hook, files)

# Check cache before execution
cached_result = await cache.get(cache_key)
if cached_result:
    print(f"Cache hit! Skipping {hook.name}")
    return cached_result

# Execute hook and cache result
result = await execute_hook(hook)
await cache.set(cache_key, result, ttl=3600)
```

### Custom TTL Configuration

```python
from crackerjack.orchestration.cache import (
    ToolProxyCacheAdapter,
    ToolProxyCacheSettings,
)

# Configure cache with custom settings
settings = ToolProxyCacheSettings(
    default_ttl=7200,  # 2 hours
    max_cache_size_mb=250,
    enable_compression=True,
)

cache = ToolProxyCacheAdapter(settings=settings)
await cache.init()

# Cache critical hook results longer
security_result = await run_security_check()
await cache.set(cache_key, security_result, ttl=86400)  # 24 hours
```

### Cache Statistics

```python
# Get cache performance metrics
stats = await cache.get_stats()

print(f"Total entries: {stats['total_entries']}")
print(f"Active entries: {stats['active_entries']}")
print(f"Expired entries: {stats['expired_entries']}")
print(f"Cache directory: {stats['cache_dir']}")

# Calculate hit rate
hit_rate = stats["active_entries"] / stats["total_entries"]
print(f"Cache hit rate: {hit_rate:.1%}")
```

### Manual Cache Invalidation

```python
# Clear all cached results
await cache.clear()

# Clear specific hook results
for key in cache._cache.keys():
    if key.startswith("ruff-format:"):
        del cache._cache[key]
```

## Cache Key Computation

The cache key is computed from three components:

1. **Hook Name**: Identifies the tool (ruff-format, pyright, etc.)
1. **Config Hash**: SHA256 of hook configuration (command, timeout, stage, security level)
1. **Content Hash**: SHA256 of all input file contents

**Example computation:**

```python
# Hook configuration
config_data = {
    "name": "ruff-format",
    "command": ["ruff", "format", "--check"],
    "timeout": 60,
    "stage": "fast",
    "security_level": "low",
}
config_hash = hashlib.sha256(
    json.dumps(config_data, sort_keys=True).encode()
).hexdigest()[:16]

# File contents
content_hasher = hashlib.sha256()
for file_path in sorted(files):
    content_hasher.update(file_path.read_bytes())
content_hash = content_hasher.hexdigest()[:16]

# Final key
cache_key = f"{hook.name}:{config_hash}:{content_hash}"
# Result: "ruff-format:a3f21b8c7d9e4a2f:7b8c3e1d9f2a6b4c"
```

## Cache Invalidation Strategy

Cache entries are automatically invalidated when:

1. **TTL Expiration**: Entry exceeds configured time-to-live
1. **Content Changes**: File content hash changes
1. **Configuration Changes**: Hook configuration modified
1. **Manual Invalidation**: Explicit `clear()` call

**Automatic Invalidation:**

```python
# First execution - cache miss
files = [Path("src/main.py")]
key = cache.compute_key(hook, files)
result1 = await cache.get(key)  # None

await execute_and_cache(hook, files, key)

# Second execution - cache hit (same content)
result2 = await cache.get(key)  # HookResult (cached)

# Modify file
Path("src/main.py").write_text("# Modified")

# Third execution - cache miss (content changed)
key_new = cache.compute_key(hook, files)  # Different content_hash
result3 = await cache.get(key_new)  # None
```

## Configuration

### Via Settings YAML

```yaml
# settings/crackerjack.yaml
cache:
  default_ttl: 3600
  max_cache_size_mb: 100
  enable_compression: true
  cache_dir: .crackerjack/cache
```

### Via Code

```python
from pathlib import Path
from crackerjack.orchestration.cache import (
    ToolProxyCacheAdapter,
    ToolProxyCacheSettings,
)

settings = ToolProxyCacheSettings(
    default_ttl=3600,
    max_cache_size_mb=100,
    enable_compression=True,
)

cache = ToolProxyCacheAdapter(
    settings=settings,
    cache_dir=Path.cwd() / ".crackerjack" / "cache",
)
```

## Performance Impact

**Before Caching:**

- Every hook executes on every run
- ~30-60s for comprehensive hooks
- Redundant work on unchanged files

**With 70% Cache Hit Rate:**

- Only 30% of hooks execute
- ~10-20s for comprehensive hooks
- 2-3x faster workflow execution

**Example Workflow:**

```
Without cache: 45s total (15 hooks × 3s each)
With cache:    15s total (5 misses × 3s each)
Speedup:       3x faster
```

## Best Practices

1. **Use Content-Based Keys**: Always compute keys from file content, not timestamps
1. **Configure TTL Appropriately**:
   - Fast hooks: 1 hour (3600s)
   - Comprehensive hooks: 2-4 hours (7200-14400s)
   - Security checks: 24 hours (86400s)
1. **Monitor Hit Rates**: Aim for 60-80% hit rates in typical development
1. **Clear Stale Entries**: Periodically clear expired entries
1. **Size Management**: Monitor cache size, adjust `max_cache_size_mb` if needed
1. **Compression**: Enable for large results (security scans, type checking)

## Architecture Integration

The cache integrates with:

- **Hook Orchestration**: `ExecutionStrategyProtocol` implementations
- **QA Adapters**: `QAAdapterProtocol` implementations
- **Performance Monitoring**: Cache hit rates tracked in metrics
- **ACB Module System**: Registered via `MODULE_ID` (UUID7)

```python
# ACB Integration
from acb.depends import depends
from crackerjack.orchestration.cache import ToolProxyCacheAdapter

# Register cache adapter
depends.set(ToolProxyCacheAdapter)


# Use via dependency injection
@depends.inject
async def execute_with_cache(
    cache: ToolProxyCacheAdapter = depends(),
) -> HookResult:
    """Execute hook with caching."""
    key = cache.compute_key(hook, files)

    # Check cache
    if cached := await cache.get(key):
        return cached

    # Execute and cache
    result = await execute_hook(hook)
    await cache.set(key, result)
    return result
```

## Related Documentation

- [Orchestration Strategies](../strategies/README.md) - Execution strategies using cache
- [Hook Orchestration](../README.md) - Overall orchestration
- [Models](../../models/README.md) - HookResult and cache protocols
- [CLAUDE.md](../../../docs/guides/CLAUDE.md) - Architecture patterns

## Future Enhancements

- Redis backend for distributed caching
- Cache warming strategies (pre-populate common files)
- Adaptive TTL based on change frequency
- Cache compression for disk persistence
- Multi-level caching (L1: memory, L2: disk, L3: Redis)
