> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | Executors

# Executors

Execution engines and task runners for intelligent hook execution, caching, and progress tracking.

## Overview

The executors package provides specialized execution engines for running quality hooks with various optimization strategies. Executors handle parallel execution, result caching, progress tracking, LSP integration, and lock management to ensure efficient and reliable quality checks.

## Executor Types

### Core Executors

- **`hook_executor.py`** - Base hook executor with sequential and parallel execution
- **`async_hook_executor.py`** - Asynchronous hook execution for concurrent workflows
- **`cached_hook_executor.py`** - Smart caching for repeated hook executions
- **`progress_hook_executor.py`** - Real-time progress tracking and reporting
- **`individual_hook_executor.py`** - Single-hook execution with detailed reporting

### Specialized Executors

- **`lsp_aware_hook_executor.py`** - LSP-optimized execution for type checking
- **`hook_lock_manager.py`** - Lock management to prevent concurrent execution conflicts
- **`tool_proxy.py`** - Proxy layer for tool execution with error handling

## Core Components

### HookExecutor

Base executor providing fundamental hook execution capabilities:

**Features:**

- **Sequential Execution** - Run hooks one after another
- **Parallel Execution** - Run compatible hooks concurrently
- **Strategy Execution** - Execute predefined hook strategies (fast/comprehensive)
- **Retry Logic** - Automatic retry for formatting hooks
- **Progress Callbacks** - Optional progress tracking hooks
- **Timeout Management** - Per-hook and global timeout enforcement
- **Result Aggregation** - Collect and summarize execution results

**Usage:**

```python
from crackerjack.executors import HookExecutor
from pathlib import Path

executor = HookExecutor(
    console=console,
    pkg_path=Path.cwd(),
    verbose=True,
    quiet=False,
    debug=False,
    use_incremental=True,  # Enable incremental execution
)

# Execute strategy
result = executor.execute_strategy(
    strategy_name="fast_hooks", parallel=True, max_workers=4
)
```

### AsyncHookExecutor

Asynchronous executor for concurrent workflow integration:

**Features:**

- **True Async Execution** - Native asyncio support
- **Concurrent Hook Groups** - Run independent hook groups in parallel
- **Event Loop Integration** - Works with existing event loops
- **Async Context Managers** - Proper resource cleanup
- **Backpressure Handling** - Prevents system overload

**Usage:**

```python
from crackerjack.executors import AsyncHookExecutor


async def run_hooks():
    executor = AsyncHookExecutor(console=console, pkg_path=pkg_path)

    # Run hooks asynchronously
    result = await executor.execute_strategy_async("fast_hooks")

    return result
```

### CachedHookExecutor

Smart caching executor with intelligent cache invalidation:

**Features:**

- **Result Caching** - Cache hook execution results
- **File-Based Invalidation** - Invalidate cache when files change
- **Smart Cache Manager** - Intelligent cache key generation
- **Hit Rate Tracking** - Monitor cache effectiveness
- **TTL Management** - Time-based cache expiration
- **Memory Efficient** - LRU eviction for large projects

**Cache Strategy:**

```python
from crackerjack.executors import CachedHookExecutor, SmartCacheManager

cache_manager = SmartCacheManager(
    cache_dir=Path(".crackerjack/cache"),
    ttl_seconds=3600,  # 1 hour
    max_cache_size_mb=100,
)

executor = CachedHookExecutor(
    console=console, pkg_path=pkg_path, cache_manager=cache_manager
)

# First execution - cache miss
result1 = executor.execute_strategy("fast_hooks")
print(f"Cache hits: {result1.cache_hits}, misses: {result1.cache_misses}")

# Second execution - cache hit (if no files changed)
result2 = executor.execute_strategy("fast_hooks")
print(f"Performance gain: {result2.performance_gain:.1%}")
```

### ProgressHookExecutor

Real-time progress tracking with rich console output:

**Features:**

- **Live Progress Display** - Real-time progress bars
- **Task Tracking** - Individual hook progress
- **Time Estimates** - Remaining time calculations
- **Success/Failure Visualization** - Color-coded status
- **Detailed Reporting** - Per-hook execution details

**Usage:**

```python
from crackerjack.executors import ProgressHookExecutor
from rich.progress import Progress

with Progress() as progress:
    executor = ProgressHookExecutor(
        console=console, pkg_path=pkg_path, progress=progress
    )

    # Progress automatically tracked and displayed
    result = executor.execute_strategy("comprehensive_hooks")
```

### IndividualHookExecutor

Execute single hooks with detailed error reporting:

**Features:**

- **Single Hook Focus** - Detailed execution of one hook
- **Enhanced Error Reporting** - Full error context and stack traces
- **Debugging Support** - Verbose output for troubleshooting
- **Exit Code Handling** - Proper subprocess exit code interpretation
- **Output Streaming** - Real-time stdout/stderr streaming

**Usage:**

```python
from crackerjack.executors import IndividualHookExecutor

executor = IndividualHookExecutor(
    console=console,
    pkg_path=pkg_path,
    debug=True,  # Enable debug output
)

# Execute single hook
result = executor.execute_hook(
    hook_name="ruff-check",
    files=[Path("src/main.py")],  # Optional file targeting
)

if not result.success:
    print(f"Hook failed with exit code: {result.exit_code}")
    print(f"Error output:\n{result.stderr}")
```

### LSPAwareHookExecutor

LSP-optimized executor for ultra-fast type checking:

**Features:**

- **LSP Integration** - Communicates with running LSP servers
- **Incremental Analysis** - Only check changed files
- **Fallback Support** - Falls back to direct execution if LSP unavailable
- **Server Health Checking** - Monitors LSP server status
- **Shared State** - Leverages LSP server's incremental compilation

**Performance:**

```
Traditional execution:  ~30-60s
LSP-aware execution:    ~2-5s (10-20x faster)
```

**Usage:**

```python
from crackerjack.executors import LSPAwareHookExecutor

executor = LSPAwareHookExecutor(
    console=console, pkg_path=pkg_path, lsp_enabled=True, fallback_enabled=True
)

# Uses LSP server if available, falls back otherwise
result = executor.execute_type_checking()
```

### HookLockManager

Prevents concurrent execution conflicts with file-based locking:

**Features:**

- **File-Based Locks** - Prevents multiple simultaneous executions
- **Timeout Support** - Configurable lock acquisition timeout
- **Deadlock Prevention** - Automatic lock release on timeout
- **Atomic Operations** - Thread-safe lock management
- **Context Manager Support** - Automatic lock cleanup

**Usage:**

```python
from crackerjack.executors import HookLockManager

lock_manager = HookLockManager(
    lock_dir=Path(".crackerjack/locks"),
    timeout=60,  # seconds
)

with lock_manager.acquire_lock("fast_hooks"):
    # Only one process can execute this block at a time
    result = executor.execute_strategy("fast_hooks")
```

### ToolProxy

Proxy layer for tool execution with unified error handling:

**Features:**

- **Unified Interface** - Consistent tool execution API
- **Error Normalization** - Standardized error reporting
- **Output Parsing** - Structured output from various tools
- **Retry Logic** - Configurable retry for transient failures
- **Timeout Enforcement** - Prevents hung processes

**Usage:**

```python
from crackerjack.executors import ToolProxy

proxy = ToolProxy(console=console, timeout=120, retries=1)

# Execute tool through proxy
result = proxy.execute_tool(tool_name="ruff", args=["check", "src"], cwd=pkg_path)
```

## Execution Patterns

### Sequential Execution

```python
from crackerjack.executors import HookExecutor

executor = HookExecutor(console=console, pkg_path=pkg_path)

# Execute hooks one by one
result = executor.execute_strategy(
    strategy_name="fast_hooks",
    parallel=False,  # Sequential execution
)

print(f"Total duration: {result.total_duration:.2f}s")
```

### Parallel Execution

```python
# Execute compatible hooks in parallel
result = executor.execute_strategy(
    strategy_name="comprehensive_hooks",
    parallel=True,
    max_workers=4,  # Number of parallel workers
)

print(f"Concurrent execution: {result.concurrent_execution}")
print(f"Duration: {result.total_duration:.2f}s")
```

### Cached Execution

```python
from crackerjack.executors import CachedHookExecutor

cached_executor = CachedHookExecutor(console=console, pkg_path=pkg_path)

# First run - populates cache
result1 = cached_executor.execute_strategy("fast_hooks")

# Second run - uses cache for unchanged files
result2 = cached_executor.execute_strategy("fast_hooks")

print(f"Cache hit rate: {result2.cache_hit_rate:.1%}")
print(f"Performance gain: {result2.performance_gain:.1%}")
```

### Async Execution

```python
from crackerjack.executors import AsyncHookExecutor


async def run_quality_checks():
    executor = AsyncHookExecutor(console=console, pkg_path=pkg_path)

    # Run multiple hook strategies concurrently
    fast_result, comp_result = await asyncio.gather(
        executor.execute_strategy_async("fast_hooks"),
        executor.execute_strategy_async("comprehensive_hooks"),
    )

    return fast_result, comp_result
```

### Progress Tracking

```python
from crackerjack.executors import ProgressHookExecutor
from rich.progress import Progress

with Progress() as progress:
    executor = ProgressHookExecutor(
        console=console, pkg_path=pkg_path, progress=progress
    )

    # Progress bars automatically displayed
    result = executor.execute_strategy("comprehensive_hooks")
```

## HookExecutionResult

All executors return `HookExecutionResult` with comprehensive execution data:

```python
@dataclass
class HookExecutionResult:
    strategy_name: str  # Strategy executed
    results: list[HookResult]  # Individual hook results
    total_duration: float  # Total execution time
    success: bool  # Overall success status
    concurrent_execution: bool  # Was execution parallel?
    cache_hits: int  # Number of cache hits
    cache_misses: int  # Number of cache misses
    performance_gain: float  # Performance improvement %

    @property
    def failed_count(self) -> int:
        """Number of failed hooks."""

    @property
    def passed_count(self) -> int:
        """Number of passed hooks."""

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate percentage."""

    @property
    def performance_summary(self) -> dict:
        """Comprehensive performance metrics."""
```

## Configuration

Executors are configured through ACB Settings:

```yaml
# settings/crackerjack.yaml

# Executor configuration
executor_type: "cached"  # base, cached, async, progress
max_parallel_hooks: 4
hook_timeout: 300
retry_attempts: 1

# Cache configuration
cache_enabled: true
cache_ttl: 3600  # 1 hour
cache_max_size_mb: 100
cache_dir: ".crackerjack/cache"

# LSP configuration
lsp_executor_enabled: true
lsp_fallback_enabled: true
lsp_server_timeout: 30

# Progress tracking
progress_enabled: true
progress_style: "rich"  # rich, simple, none

# Lock management
lock_enabled: true
lock_timeout: 60
lock_dir: ".crackerjack/locks"
```

## Usage Examples

### Basic Hook Execution

```python
from crackerjack.executors import HookExecutor
from pathlib import Path

executor = HookExecutor(console=console, pkg_path=Path.cwd(), verbose=True)

# Execute fast hooks
result = executor.execute_strategy("fast_hooks")

if result.success:
    print(f"✅ All {result.passed_count} hooks passed")
    print(f"Duration: {result.total_duration:.2f}s")
else:
    print(f"❌ {result.failed_count} hooks failed")
    for hook_result in result.results:
        if hook_result.status == "failed":
            print(f"  - {hook_result.name}: {hook_result.message}")
```

### Cached Execution with Metrics

```python
from crackerjack.executors import CachedHookExecutor

executor = CachedHookExecutor(console=console, pkg_path=pkg_path)

# Multiple executions to demonstrate caching
for i in range(3):
    result = executor.execute_strategy("fast_hooks")
    print(f"Run {i + 1}:")
    print(f"  Duration: {result.total_duration:.2f}s")
    print(f"  Cache hits: {result.cache_hits}")
    print(f"  Cache hit rate: {result.cache_hit_rate:.1%}")
    print(f"  Performance gain: {result.performance_gain:.1%}")
```

### LSP-Aware Type Checking

```python
from crackerjack.executors import LSPAwareHookExecutor

executor = LSPAwareHookExecutor(console=console, pkg_path=pkg_path, lsp_enabled=True)

# Fast type checking via LSP
result = executor.execute_type_checking()

print(f"Type checking completed in {result.total_duration:.2f}s")
print(f"Used LSP: {result.used_lsp}")
print(f"Speedup: {result.speedup_factor:.1f}x")
```

### Progress Tracking with Rich Console

```python
from crackerjack.executors import ProgressHookExecutor
from rich.progress import Progress
from rich.console import Console

console = Console()

with Progress() as progress:
    executor = ProgressHookExecutor(
        console=console, pkg_path=pkg_path, progress=progress
    )

    # Rich progress bars displayed automatically
    result = executor.execute_strategy("comprehensive_hooks")

    console.print(f"\n[green]✓[/green] Completed in {result.total_duration:.2f}s")
```

### Custom Hook Execution

```python
from crackerjack.config.hooks import HookDefinition, HookStage

custom_hook = HookDefinition(
    name="custom-check",
    command=["python", "-m", "my_tool"],
    timeout=120,
    stage=HookStage.COMPREHENSIVE,
    retry_on_failure=False,
)

executor = HookExecutor(console=console, pkg_path=pkg_path)

# Execute custom hook
result = executor.execute_hook(custom_hook)
```

## Integration with Workflows

Executors integrate seamlessly with ACB workflows:

```python
from crackerjack.workflows import CrackerjackWorkflowEngine
from crackerjack.executors import CachedHookExecutor

engine = CrackerjackWorkflowEngine()
executor = CachedHookExecutor(console=console, pkg_path=pkg_path)


# Register executor as workflow action
@engine.register_action("run_fast_hooks")
async def run_fast_hooks(context):
    result = executor.execute_strategy("fast_hooks")
    return {"success": result.success, "duration": result.total_duration}
```

## Best Practices

1. **Use Cached Executor** - Enable caching for repeated executions (development workflow)
1. **Enable Parallelization** - Run independent hooks in parallel when possible
1. **Configure Timeouts** - Set appropriate timeouts for long-running hooks
1. **Monitor Cache Performance** - Track cache hit rates and adjust TTL
1. **Use LSP Executor** - Enable LSP for 10-20x faster type checking
1. **Handle Lock Timeouts** - Configure lock timeouts to prevent deadlocks
1. **Track Progress** - Use ProgressHookExecutor for long-running operations
1. **Retry Formatting Only** - Only retry formatting hooks, not analysis hooks
1. **Async for Workflows** - Use AsyncHookExecutor for workflow integration
1. **Monitor Performance** - Track execution metrics and optimize slow hooks

## Performance Considerations

### Execution Time Comparison

```
Sequential (base executor):
  Fast hooks: ~15s
  Comprehensive hooks: ~45s

Parallel (max_workers=4):
  Fast hooks: ~5s (3x faster)
  Comprehensive hooks: ~15s (3x faster)

Cached (after warmup):
  Fast hooks: ~1s (15x faster)
  Comprehensive hooks: ~3s (15x faster)

LSP-aware (type checking):
  Traditional: ~30s
  LSP-aware: ~2s (15x faster)
```

### Memory Usage

```
Base executor: ~100MB
Cached executor: ~150MB (cache overhead)
Parallel executor: ~100MB + (50MB × workers)
LSP-aware: ~100MB (shares LSP server memory)
```

## Related

- [Hooks](../hooks/README.md) - Hook definitions and lifecycle
- [Workflows](../workflows/README.md) - Workflow integration
- [Config](../config/README.md) - Executor configuration
- [CLAUDE.md](../../docs/guides/CLAUDE.md) - Quality process overview

## Future Enhancements

- [ ] Distributed execution across multiple machines
- [ ] GPU-accelerated hook execution for large codebases
- [ ] Machine learning for optimal parallelization strategy
- [ ] Real-time execution monitoring dashboard
- [ ] Execution profiling and bottleneck detection
- [ ] Smart scheduling based on historical performance data
