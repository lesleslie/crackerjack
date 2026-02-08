# HTTP Connection Pool Implementation Plan

## Phase 2.2: Create Connection Pool for HTTP Operations

### Analysis Summary

**Files Found Using aiohttp Without Pooling:**

1. **crackerjack/core/service_watchdog.py** (line 351)
   - Creates session inline during health checks
   - Context: `_perform_health_check()` method
   - Pattern: `async with aiohttp.ClientSession() as session`

2. **crackerjack/mcp/service_watchdog.py** (line 63)
   - Creates session once in `start()` method
   - Context: Service lifecycle management
   - Pattern: `self.session = aiohttp.ClientSession(timeout=...)`
   - Note: Already has instance variable, better than others

3. **crackerjack/adapters/ai/registry.py** (line 334)
   - Creates session inline for Ollama availability check
   - Context: `_check_provider_availability()` method
   - Pattern: `async with aiohttp.ClientSession() as session`

4. **crackerjack/services/version_checker.py** (line 139)
   - Creates session inline for PyPI API calls
   - Context: `_fetch_latest_version()` method with retry decorator
   - Pattern: `async with aiohttp.ClientSession(timeout=timeout) as session`

**Total: 4 files, 5 locations using aiohttp without centralized pooling**

### Problem Statement

Each file creates its own `aiohttp.ClientSession` instances, which:
- Creates new TCP connections for each request
- Increases overhead from connection establishment
- Prevents connection reuse
- Limits performance potential (15-25% improvement possible)

### Solution Design

#### 1. Connection Pool Manager (`crackerjack/services/connection_pool.py`)

**Pattern**: Singleton with lazy initialization

**Key Features**:
- Thread-safe singleton using `asyncio.Lock`
- Centralized `aiohttp.ClientSession` management
- Configurable connection limits and timeouts
- Proper lifecycle management (startup/shutdown)
- Context manager support for cleanup

**Interface**:
```python
class HTTPConnectionPool:
    """Singleton HTTP connection pool manager."""

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create shared session."""

    async def close(self) -> None:
        """Close all connections and cleanup."""

    async def __aenter__(self) -> HTTPConnectionPool:
        """Async context manager entry."""

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
```

**Configuration** (via Oneiric settings):
```yaml
http_connection_pool:
  max_connections: 100
  max_per_host: 30
  connect_timeout: 10.0
  total_timeout: 30.0
```

#### 2. Migration Strategy

**Priority Order**:
1. **version_checker.py** - High frequency (called often during checks)
2. **ai/registry.py** - Medium frequency (AI provider selection)
3. **mcp/service_watchdog.py** - Low frequency (already has instance variable)
4. **core/service_watchdog.py** - Low frequency (health checks only)

**Pattern for Each Migration**:
```python
# Before (current pattern)
async with aiohttp.ClientSession(timeout=timeout) as session:
    async with session.get(url) as response:
        return await response.text()

# After (with connection pool)
from crackerjack.services.connection_pool import get_http_pool

pool = await get_http_pool()
async with pool.get_session() as session:
    async with session.get(url) as response:
        return await response.text()
```

#### 3. Lifecycle Management

**Startup** (during application init):
```python
# In crackerjack/config.py or __main__.py
async def initialize_connection_pool():
    pool = await get_http_pool()
    # Pool is now ready for use
```

**Shutdown** (during application cleanup):
```python
# In signal handlers or atexit
async def cleanup_connection_pool():
    pool = await get_http_pool()
    await pool.close()
```

### Implementation Checklist

- [ ] Create `crackerjack/services/connection_pool.py`
- [ ] Add configuration to Oneiric settings
- [ ] Update `crackerjack/services/version_checker.py`
- [ ] Update `crackerjack/adapters/ai/registry.py`
- [ ] Update `crackerjack/mcp/service_watchdog.py`
- [ ] Update `crackerjack/core/service_watchdog.py`
- [ ] Add tests for connection pool
- [ ] Verify quality checks pass
- [ ] Document performance improvement

### Expected Performance Improvement

**Conservative Estimates**:
- **15-25% faster** HTTP operations (connection reuse)
- **Reduced latency** from eliminating TCP handshake overhead
- **Lower memory usage** from fewer socket objects
- **Better resource utilization** with connection limits

**Measurement Plan**:
1. Baseline: Measure current HTTP operation times
2. After implementation: Measure new times
3. Compare: Calculate improvement percentage
4. Document: Add results to performance report

### Testing Strategy

**Unit Tests**:
- Singleton initialization
- Session reuse
- Lifecycle management (open/close)
- Error handling

**Integration Tests**:
- Real HTTP requests through pool
- Concurrent requests
- Timeout handling
- Connection limits

**Performance Tests**:
- Benchmark: N requests with pool vs without
- Measure: Latency, throughput, memory
- Verify: 15%+ improvement

### Risks and Mitigations

**Risk**: Breaking changes to existing code
- **Mitigation**: Gradual migration, test each file independently

**Risk**: Connection leaks
- **Mitigation**: Proper async context managers, cleanup handlers

**Risk**: Configuration complexity
- **Mitigation**: Sensible defaults, optional configuration

**Risk**: Thread safety issues
- **Mitigation**: Use `asyncio.Lock` for singleton initialization

### Success Criteria

1. All 4 files updated to use connection pool
2. Quality checks pass (ruff, pytest, mypy)
3. Performance improvement measured (target: 15%+)
4. No connection leaks in tests
5. Documentation complete

### Rollback Plan

If issues arise:
1. Revert individual file changes
2. Disable connection pool via configuration
3. Fall back to direct `aiohttp.ClientSession` creation
4. Document issues for future resolution

### Next Steps

1. Implement connection pool manager
2. Add configuration
3. Migrate files one by one (starting with version_checker)
4. Test thoroughly
5. Measure performance
6. Document results
