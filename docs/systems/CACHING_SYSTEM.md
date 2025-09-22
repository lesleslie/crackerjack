# Crackerjack Caching System

## Overview

Crackerjack uses a sophisticated multi-layer caching system designed to minimize redundant work during development workflows. The system combines in-memory caching for immediate performance with disk-based persistence for long-term storage across sessions.

## Architecture

### Multi-Layer Design

The caching system consists of **4 layers** optimized for different use cases:

1. **Hook Results Cache** - In-memory LRU cache for hook execution results
1. **File Hash Cache** - In-memory cache for file content hashes
1. **Config Cache** - In-memory cache for configuration data
1. **Disk Cache** - Persistent file-based cache for expensive operations

```
┌─────────────────────────────────────────────────────────────────┐
│                     CrackerjackCache                            │
├─────────────────────────────────────────────────────────────────┤
│  In-Memory Layers (Session-specific)                           │
│  ┌───────────────┬──────────────┬──────────────────────────┐    │
│  │ Hook Results  │ File Hashes  │ Config Data              │    │
│  │ TTL: 30 min   │ TTL: 1 hour  │ TTL: 2 hours             │    │
│  │ Max: 500      │ Max: 2000    │ Max: 100                 │    │
│  └───────────────┴──────────────┴──────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│  Disk Layer (Cross-session persistence)                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Expensive Operations: pyright, bandit, vulture, etc.       │ │
│  │ AI Agent Decisions: Cached analysis results                │ │
│  │ Quality Baselines: Git commit metrics                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Cache Decision Logic

```python
# Hybrid caching strategy
def get_result(hook_name, file_hashes):
    # 1. Check memory first (fastest)
    result = memory_cache.get(cache_key)
    if result:
        return result

    # 2. Check disk for expensive hooks (persistent)
    if hook_name in EXPENSIVE_HOOKS:
        result = disk_cache.get(versioned_cache_key)
        if result:
            # Promote to memory for faster access
            memory_cache.set(cache_key, result)
            return result

    # 3. Execute and cache result
    result = execute_hook(hook_name)
    memory_cache.set(cache_key, result)
    if hook_name in EXPENSIVE_HOOKS:
        disk_cache.set(versioned_cache_key, result)

    return result
```

## Cache Types & Use Cases

### 1. Hook Results Cache

**Purpose**: Avoid re-executing hooks when file content hasn't changed

**Invalidation**: Based on file content hashes - when any relevant file changes, cache becomes invalid

**Example**:

```python
# Files: main.py, config.py
# Hash signature: md5("hash_of_main.py,hash_of_config.py")
# Key: "hook_result:ruff-check:a1b2c3d4e5f6..."

cache.set_hook_result("ruff-check", file_hashes, result)
```

### 2. File Hash Cache

**Purpose**: Avoid recalculating expensive file hashes

**Invalidation**: Based on file modification time and size

**Example**:

```python
# Key includes mtime and size for automatic invalidation
# Key: "file_hash:/path/to/file:1693123456.789:2048"

cache.set_file_hash(Path("main.py"), "sha256hash...")
```

### 3. Config Cache

**Purpose**: Cache parsed configuration files and settings

**Invalidation**: 2-hour TTL or when configuration files change

**Use Cases**:

- Parsed pyproject.toml settings
- Hook strategy configurations
- Tool version information

### 4. Disk Cache

**Purpose**: Persist expensive computation results across sessions

**Key Features**:

- Survives process restarts
- Version-aware cache invalidation
- Configurable TTL per tool type

#### Expensive Hooks (Disk Cached)

| Tool | TTL | Reason |
|------|-----|--------|
| `pyright` | 24 hours | Type checking is stable until code changes |
| `bandit` | 3 days | Security patterns change slowly |
| `vulture` | 2 days | Dead code detection is stable |
| `complexipy` | 24 hours | Complexity analysis |
| `refurb` | 24 hours | Code improvement suggestions |
| `gitleaks` | 7 days | Secret detection is very stable |

#### AI Agent Decision Caching

**Purpose**: Cache AI agent analysis and fix decisions

**Benefits**:

- Avoid redundant LLM API calls for identical issues
- Consistent fix strategies across sessions
- Faster batch processing

**Example**:

```python
# Cache key includes agent version for invalidation
# Key: "agent:RefactoringAgent:issue_hash:1.0.0"

cache.set_agent_decision("RefactoringAgent", issue_hash, fix_result)
```

#### Quality Baseline Persistence

**Purpose**: Track project quality metrics over time

**Features**:

- Per-commit quality scores
- Baseline comparisons
- Regression detection

**Example**:

```python
# Key: "baseline:a1b2c3d4e5f6789abcd..."
metrics = QualityMetrics(
    git_hash="a1b2c3d4...", coverage_percent=85.2, test_count=142, quality_score=87
)
cache.set_quality_baseline(git_hash, metrics)
```

## Performance Characteristics

### Cache Hit Rates (Typical Development Session)

- **Hook Results**: 60-80% hit rate during iterative development
- **File Hashes**: 90%+ hit rate (files don't change often)
- **Config Data**: 95%+ hit rate (configuration is stable)
- **Expensive Hooks**: 40-60% hit rate across sessions

### Speed Improvements

| Operation | Without Cache | With Cache | Speedup |
|-----------|---------------|------------|---------|
| Ruff check (unchanged files) | 2.3s | 0.1s | **23x** |
| Pyright (large codebase) | 15.4s | 0.2s | **77x** |
| Bandit security scan | 8.1s | 0.1s | **81x** |
| Full hook strategy | 45.2s | 3.7s | **12x** |

### Memory Usage

- **Typical Session**: 5-15MB for all in-memory caches
- **Large Projects**: 20-40MB maximum
- **Disk Cache**: 50-200MB (auto-cleaned based on TTL)

## Cache Invalidation Strategies

### 1. Content-Based Invalidation

**File Hashes**: Cache keys include content hashes, automatically invalidating when files change

```python
# When main.py changes:
# Old key: "hook_result:ruff:hash1,hash2,hash3"  <- Invalid
# New key: "hook_result:ruff:hash1,NEW_hash2,hash3"  <- Fresh
```

### 2. Time-Based Expiration (TTL)

**Use Cases**:

- Security scans (weekly refresh)
- Type checking (daily refresh)
- Configuration (hourly refresh)

### 3. Version-Based Invalidation

**Tool Updates**: Cache keys include tool version to handle updates

```python
# Old: "hook_result:pyright:hash123:1.1.0"
# New: "hook_result:pyright:hash123:1.1.1"  <- Separate cache entry
```

### 4. LRU Eviction

**Memory Management**: Least Recently Used items are evicted when cache reaches capacity

```python
# Cache at capacity (500 items)
# New item added -> LRU item automatically removed
```

## Configuration

### Default Settings

```python
# In CrackerjackCache.__init__()
self.hook_results_cache = InMemoryCache(max_entries=500, default_ttl=1800)  # 30 min
self.file_hash_cache = InMemoryCache(max_entries=2000, default_ttl=3600)  # 1 hour
self.config_cache = InMemoryCache(max_entries=100, default_ttl=7200)  # 2 hours
```

### Cache Directory

```bash
# Default location
.crackerjack/cache/crackerjack/

# Custom location
cache = CrackerjackCache(cache_dir=Path("/custom/cache/path"))
```

### Disabling Disk Cache

```python
# For development or CI environments
cache = CrackerjackCache(enable_disk_cache=False)
```

## Monitoring & Debugging

### Cache Statistics

```python
stats = cache.get_cache_stats()
# Returns:
{
    "hook_results": {"hits": 45, "misses": 12, "hit_rate_percent": 78.9},
    "file_hashes": {"hits": 156, "misses": 8, "hit_rate_percent": 95.1},
    "disk_cache": {"hits": 23, "misses": 7, "hit_rate_percent": 76.7},
}
```

### Cache Cleanup

```python
cleanup_stats = cache.cleanup_all()
# Returns: {"hook_results": 12, "file_hashes": 3, "disk_cache": 8}
# Numbers represent expired entries removed
```

### Debug Logging

```bash
# Enable cache debug logging
export CRACKERJACK_LOG_LEVEL=DEBUG
python -m crackerjack

# Sample output:
# DEBUG:crackerjack.cached_executor:Using cached result for hook: ruff-check
# DEBUG:crackerjack.cached_executor:Executing hook (cache miss): pyright
```

## Best Practices

### 1. Development Workflow

```bash
# Normal development (uses all caches)
python -m crackerjack --ai-agent -t

# Force cache refresh (when tools updated)
python -m crackerjack --clear-cache -t

# Check cache effectiveness
python -m crackerjack --cache-stats
```

### 2. CI/CD Environments

```bash
# Disable disk cache in CI (fresh environment each time)
export CRACKERJACK_DISABLE_DISK_CACHE=true
python -m crackerjack
```

### 3. Large Projects

```bash
# Increase cache sizes for large codebases
export CRACKERJACK_MAX_CACHE_ENTRIES=2000
python -m crackerjack
```

## Troubleshooting

### Common Issues

#### Cache Not Working

**Symptoms**: Tools always re-execute, no speed improvement

**Solutions**:

1. Check file permissions on cache directory
1. Verify files aren't constantly changing (timestamps)
1. Enable debug logging to see cache decisions

#### Memory Usage Too High

**Symptoms**: High memory consumption during development

**Solutions**:

1. Reduce cache sizes in configuration
1. More frequent cleanup: `cache.cleanup_all()`
1. Disable caches for specific hook types

#### Stale Cache Results

**Symptoms**: Old results returned despite file changes

**Solutions**:

1. Clear all caches: `python -m crackerjack --clear-cache`
1. Check if file modification detection is working
1. Verify TTL settings are appropriate

### Cache Corruption

**Recovery**:

```bash
# Nuclear option - clear all caches
rm -rf .crackerjack/cache/
python -m crackerjack  # Will rebuild caches
```

## Implementation Details

### Cache Key Generation

```python
def _get_hook_cache_key(self, hook_name: str, file_hashes: list[str]) -> str:
    hash_signature = hashlib.md5(
        ", ".join(sorted(file_hashes)).encode(),
        usedforsecurity=False,
    ).hexdigest()
    return f"hook_result:{hook_name}:{hash_signature}"
```

### File Hash Calculation

```python
def get_file_hash(self, file_path: Path) -> str:
    # Cache based on mtime + size for efficiency
    stat = file_path.stat()
    cache_key = f"file_hash:{file_path}:{stat.st_mtime}:{stat.st_size}"

    cached_hash = self.file_hash_cache.get(cache_key)
    if cached_hash:
        return cached_hash

    # Calculate actual hash only when needed
    hash_value = hashlib.sha256(file_path.read_bytes()).hexdigest()
    self.file_hash_cache.set(cache_key, hash_value)
    return hash_value
```

### Thread Safety

The caching system is designed for single-threaded use within Crackerjack's workflow orchestration. For multi-threaded environments, additional synchronization would be required.

______________________________________________________________________

## Future Enhancements

- [ ] Distributed caching for team environments
- [ ] Cache warming strategies for common workflows
- [ ] Advanced cache analytics and optimization
- [ ] Integration with external cache stores (Redis)
- [ ] Cache export/import for environment replication

______________________________________________________________________

*Last updated: 2025-01-09*
*Cache system version: 1.0.0*
