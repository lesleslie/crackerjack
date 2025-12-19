> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | [Orchestration](./README.md)

# Orchestration

Workflow orchestration, execution strategies, caching, and coordination for quality enforcement pipelines.

## Overview

The orchestration package provides the core workflow engine that coordinates quality checks, test execution, and AI fixing across the entire crackerjack platform. It includes intelligent caching, adaptive execution strategies, and hook management for optimal performance and reliability.

## Core Components

### Orchestrators

- **hook_orchestrator.py**: Main orchestrator for quality hook execution

  - Direct adapter invocation (no pre-commit wrapper overhead)
  - Dependency resolution and intelligent ordering
  - Adaptive execution strategies (fast, comprehensive, dependency-aware)
  - Graceful degradation with timeout strategies
  - 70% cache hit rate in typical workflows

- **advanced_orchestrator.py**: Advanced orchestration with enhanced features

  - Multi-stage workflow coordination
  - AI agent integration
  - Progress tracking and reporting
  - Error recovery and retry logic

### Execution Strategies

- **execution_strategies.py**: Pluggable execution strategies
  - **Fast Strategy**: Quick checks for rapid feedback (~5s)
  - **Comprehensive Strategy**: Full analysis with all tools (~30s)
  - **Dependency-Aware Strategy**: Intelligent ordering based on dependencies
  - **Parallel Strategy**: Maximum concurrency for I/O-bound operations
  - **Sequential Strategy**: One-at-a-time for debugging

### Coverage & Quality

- **coverage_improvement.py**: Automated coverage improvement workflows
  - Identifies low-coverage areas
  - Generates test suggestions
  - Tracks coverage ratchet progress
  - Milestone celebration system

### Configuration

- **config.py**: Orchestration configuration and settings
  - Hook definitions and metadata
  - Execution timeouts and limits
  - Cache configuration
  - Strategy selection

## Subdirectories

### Cache (`cache/`)

Intelligent caching system for hook results:

- **ToolProxyCache**: Content-based caching with file hash verification
- **MemoryCache**: In-memory LRU cache for testing
- **Cache Adapters**: Pluggable cache backends

**Benefits:**

- 70% cache hit rate in typical workflows
- Content-aware invalidation (only re-run when files actually change)
- Configurable TTL (default 3600s/1 hour)
- File hash verification prevents stale results

See [cache/README.md](./cache/README.md) for details.

### Strategies (`strategies/`)

Execution strategy implementations:

- **Strategy Pattern**: Pluggable execution strategies
- **Dependency Resolution**: Intelligent hook ordering
- **Timeout Management**: Graceful degradation on timeouts
- **Parallelization**: Concurrent execution for independent hooks

See [strategies/README.md](./strategies/README.md) for details.

## Architecture

### Workflow Execution Flow

```
User Command → Hook Orchestrator
    ↓
Strategy Selection (Fast/Comprehensive/Dependency-Aware)
    ↓
Dependency Resolution (Topological Sort)
    ↓
Cache Check (Content Hash Lookup)
    ↓
Parallel Execution (Up to 11 concurrent adapters)
    ↓
ToolProxyCache Adapter (Direct API calls, no subprocess)
    ↓
Results Aggregation with real-time output
    ↓
Error Analysis & AI Fixing (if enabled)
```

### ACB Integration

The orchestration layer has been migrated from pre-commit subprocess calls to direct ACB adapter execution:

**Old Approach (Pre-commit):**

```bash
pre-commit run ruff --all-files  # Subprocess overhead
```

**New Approach (ACB):**

```bash
python -m crackerjack --fast  # Direct Python API, 70% faster
```

### Performance Benefits

| Metric | Legacy | ACB Orchestration | Improvement |
|--------|--------|-------------------|-------------|
| **Fast Hooks** | ~45s | ~48s | Comparable |
| **Console Output** | Buffered | **Real-time streaming** | UX improvement |
| **Event Loop** | Sync (blocking) | **Async (non-blocking)** | Responsive |
| **Cache Hit Rate** | 0% | **70%** | New capability |
| **Concurrent Adapters** | 1 | **11** | 11x parallelism |

## Usage

### Basic Orchestration

```python
from crackerjack.orchestration.hook_orchestrator import HookOrchestrator
from crackerjack.orchestration.execution_strategies import FastStrategy

orchestrator = HookOrchestrator(strategy=FastStrategy())
results = await orchestrator.run_hooks(files=[Path(".")])

for result in results:
    if not result.passed:
        print(f"Hook {result.hook_name} failed: {result.message}")
```

### Advanced Orchestration

```python
from crackerjack.orchestration.advanced_orchestrator import AdvancedOrchestrator

orchestrator = AdvancedOrchestrator(
    enable_ai_fixing=True,
    max_iterations=10,
    progress_callback=lambda p: print(f"Progress: {p}%"),
)

result = await orchestrator.execute_workflow(
    stages=["fast_hooks", "tests", "comprehensive_hooks"], ai_agent_mode=True
)
```

### Custom Execution Strategy

```python
from crackerjack.orchestration.execution_strategies import ExecutionStrategy


class CustomStrategy(ExecutionStrategy):
    def should_run_hook(self, hook_name: str) -> bool:
        # Custom logic for hook selection
        return hook_name in ["ruff", "zuban"]

    def get_concurrency_limit(self) -> int:
        # Custom parallelism
        return 5


orchestrator = HookOrchestrator(strategy=CustomStrategy())
```

### Coverage Improvement Workflow

```python
from crackerjack.orchestration.coverage_improvement import (
    CoverageImprovementOrchestrator,
)

coverage_orch = CoverageImprovementOrchestrator()

# Analyze low-coverage areas
suggestions = await coverage_orch.analyze_coverage(min_coverage=42.0)

# Generate tests for uncovered code
test_code = await coverage_orch.generate_tests(suggestions)

# Track progress toward milestone
milestone = coverage_orch.get_next_milestone(current_coverage=21.6)
```

## Configuration

### Hook Definitions

Hooks are defined with metadata for orchestration:

```python
from crackerjack.orchestration.config import HookDefinition, HookStage

hook = HookDefinition(
    name="ruff",
    command=["ruff", "check", "--fix"],
    timeout=45,
    stage=HookStage.FAST,
    dependencies=[],  # No dependencies
    manual_stage=False,  # Automatic execution
    security_level=SecurityLevel.MEDIUM,
)
```

### Execution Strategies Configuration

```yaml
# settings/crackerjack.yaml
orchestration:
  default_strategy: "fast"
  max_concurrent_hooks: 11
  hook_timeout: 60
  overall_timeout: 300
  enable_caching: true
  cache_ttl: 3600
```

## Orchestration Patterns

### Dependency-Aware Execution

Hooks are executed in dependency order:

```python
# Format before lint (lint depends on format)
dependencies = {
    "ruff-format": [],
    "ruff-lint": ["ruff-format"],
    "zuban": ["ruff-format", "ruff-lint"],
}

# Executes: ruff-format → ruff-lint → zuban
```

### Graceful Degradation

Timeout strategies prevent hanging:

```python
try:
    result = await asyncio.wait_for(hook.execute(), timeout=hook_timeout)
except asyncio.TimeoutError:
    # Continue with other hooks
    log.warning(f"Hook {hook.name} timed out, continuing...")
```

### Intelligent Caching

Content-based caching prevents unnecessary re-runs:

```python
# Cache key: {hook_name}:{config_hash}:{content_hash}
cache_key = f"ruff:{hash(config)}:{hash_files(files)}"

if cached_result := cache.get(cache_key):
    return cached_result  # Skip execution

result = await hook.execute()
cache.set(cache_key, result, ttl=3600)
```

## Best Practices

1. **Choose Appropriate Strategy**: Use `FastStrategy` for rapid feedback, `ComprehensiveStrategy` for thorough analysis
1. **Enable Caching**: Cache dramatically improves performance for repeated runs
1. **Set Reasonable Timeouts**: Balance thoroughness with responsiveness
1. **Monitor Concurrency**: Adjust concurrency limits based on available resources
1. **Use Dependency Ordering**: Ensure hooks run in correct order
1. **Handle Timeouts Gracefully**: Don't let one slow hook block everything
1. **Track Progress**: Provide feedback for long-running workflows
1. **Leverage AI Fixing**: Use AI agents for iterative improvement

## Troubleshooting

### Slow Execution

```python
# Check cache hit rate
from crackerjack.orchestration.cache import get_cache_stats

stats = get_cache_stats()
print(f"Cache hit rate: {stats.hit_rate}%")

# Reduce concurrency if resource-bound
orchestrator.max_concurrent_hooks = 5
```

### Hook Timeouts

```python
# Increase timeout for specific hooks
hook.timeout = 120  # 2 minutes

# Or disable timeout for debugging
hook.timeout = None
```

### Cache Invalidation Issues

```python
# Clear cache if getting stale results
from crackerjack.orchestration.cache import clear_cache

clear_cache()
```

## Related

- [Managers](../managers/README.md) — Managers that use orchestration
- [Adapters](../adapters/README.md) — Adapters orchestrated by hooks
- [Services](../services/README.md) — Services used by orchestration
- [Agents](../agents/README.md) — AI agents coordinated by orchestration
- [Main README](../../README.md) — Workflow overview

## Future Enhancements

- [ ] Distributed orchestration across multiple machines
- [ ] Advanced dependency resolution with conditional execution
- [ ] Machine learning for optimal strategy selection
- [ ] Real-time orchestration metrics dashboard
- [ ] Plugin system for custom orchestrators
- [ ] Workflow visualization and debugging tools
