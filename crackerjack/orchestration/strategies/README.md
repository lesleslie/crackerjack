# Orchestration Strategies

> Crackerjack Docs: [Main](../../../README.md) | [CLAUDE.md](../../../docs/guides/CLAUDE.md) | [Orchestration](../README.md) | [Strategies](./README.md)

Execution strategy implementations for hook orchestration with parallel, sequential, and adaptive approaches.

## Overview

Orchestration strategies define how hooks are executed during quality assurance workflows. Crackerjack provides three core strategies optimized for different scenarios: **Sequential** (dependencies, debugging), **Parallel** (independent hooks, maximum throughput), and **Adaptive** (dependency-aware batching, optimal parallelism).

## Strategy Pattern

All strategies implement the `ExecutionStrategyProtocol`:

```python
@runtime_checkable
class ExecutionStrategyProtocol(Protocol):
    """Protocol for hook execution strategies."""

    async def execute(
        self,
        hooks: list[HookDefinition],
        max_parallel: int = 3,
        timeout: int = 300,
        executor_callable: Callable[[HookDefinition], Awaitable[HookResult]]
        | None = None,
    ) -> list[HookResult]:
        """Execute hooks according to strategy."""
        ...

    def get_execution_order(
        self,
        hooks: list[HookDefinition],
    ) -> list[list[HookDefinition]]:
        """Return batches of hooks for execution."""
        ...
```

## Available Strategies

### 1. SequentialExecutionStrategy - One-at-a-Time Execution

**File:** `sequential_strategy.py`

**Features:**

- One hook executes at a time (respects dependencies)
- Early exit on critical security failures
- Per-hook timeout handling with `asyncio.wait_for()`
- Comprehensive logging for debugging
- Predictable execution order

**Use Cases:**

- Hooks have dependencies (e.g., gitleaks → bandit)
- Resource constraints require sequential execution
- Debugging requires isolated execution
- Critical failures should stop the pipeline immediately

**Example:**

```python
from crackerjack.orchestration.strategies import SequentialExecutionStrategy

strategy = SequentialExecutionStrategy(
    default_timeout=300,
    stop_on_critical_failure=True,
)

results = await strategy.execute(
    hooks=[hook1, hook2, hook3],
    timeout=300,
    executor_callable=execute_single_hook,
)

# Execution order: hook1 → hook2 → hook3 (one at a time)
```

**Execution Flow:**

```
Time →
[========hook1========] (3s)
                        [========hook2========] (2s)
                                                [========hook3========] (4s)

Total time: 9s (sequential)
```

**Configuration:**

```python
SequentialExecutionStrategy(
    default_timeout=300,  # Default timeout per hook (seconds)
    stop_on_critical_failure=True,  # Stop if critical hook fails
)
```

### 2. ParallelExecutionStrategy - Concurrent Execution

**File:** `parallel_strategy.py`

**Features:**

- Concurrent execution using `asyncio.gather()`
- Semaphore-based resource limiting (`asyncio.Semaphore`)
- Per-hook timeout handling
- Exception isolation (one failure doesn't stop others)
- Maximum throughput for independent hooks

**Use Cases:**

- Hooks are independent (no dependencies)
- Want to maximize throughput
- System has sufficient resources (CPU, memory)
- All hooks should complete regardless of individual failures

**Example:**

```python
from crackerjack.orchestration.strategies import ParallelExecutionStrategy

strategy = ParallelExecutionStrategy(
    max_parallel=4,
    default_timeout=300,
)

results = await strategy.execute(
    hooks=[hook1, hook2, hook3, hook4, hook5],
    max_parallel=4,  # Run up to 4 hooks concurrently
    timeout=300,
    executor_callable=execute_single_hook,
)

# Execution: hook1-4 run concurrently, then hook5
```

**Execution Flow:**

```
Time →
[====hook1====] (3s)
[====hook2====] (2s)
[====hook3====] (4s)
[====hook4====] (3s)
               [====hook5====] (2s)

Total time: 6s (parallel with max_parallel=4)
Speedup: 1.5x faster than sequential (9s)
```

**Configuration:**

```python
ParallelExecutionStrategy(
    max_parallel=4,  # Maximum concurrent executions
    default_timeout=300,  # Default timeout per hook (seconds)
)
```

### 3. AdaptiveExecutionStrategy - Dependency-Aware Batching

**File:** `adaptive_strategy.py`

**Features:**

- Topological sort for dependency-aware wave computation
- Parallel execution within each wave (independent hooks)
- Sequential execution between waves (respects dependencies)
- Early exit on critical security failures
- Optimal parallelism for mixed workloads

**Algorithm:**

1. Compute execution waves using topological sort
1. Wave 1: All hooks with zero dependencies (execute in parallel)
1. Wave 2: Hooks whose dependencies completed (execute in parallel)
1. Wave N: Repeat until all hooks executed
1. Stop early if critical hook fails

**Use Cases:**

- Mixed workload with some dependencies
- Want maximum parallelism while respecting dependencies
- Critical failures should stop dependent hooks
- Optimal strategy for most real-world scenarios

**Example:**

```python
from crackerjack.orchestration.strategies import AdaptiveExecutionStrategy

# Define dependency graph: dependent → [prerequisites]
dependency_graph = {
    "bandit": ["gitleaks"],  # bandit depends on gitleaks
    "refurb": ["zuban"],  # refurb depends on zuban
}

strategy = AdaptiveExecutionStrategy(
    dependency_graph=dependency_graph,
    max_parallel=4,
    default_timeout=300,
    stop_on_critical_failure=True,
)

results = await strategy.execute(
    hooks=[gitleaks, zuban, ruff_format, bandit, refurb],
    executor_callable=execute_single_hook,
)

# Wave 1 (parallel): gitleaks, zuban, ruff-format (no dependencies)
# Wave 2 (parallel): bandit, refurb (dependencies completed)
```

**Execution Flow:**

```
Dependency Graph:
gitleaks → bandit
zuban → refurb
ruff-format (independent)

Time →
Wave 1 (parallel):
[====gitleaks====] (3s)
[====zuban====] (2s)
[====ruff-format====] (1s)

Wave 2 (parallel):
                   [====bandit====] (3s)
                   [====refurb====] (2s)

Total time: 6s (adaptive batching)
Speedup: 1.5x faster than sequential (11s)
Optimal parallelism while respecting dependencies
```

**Configuration:**

```python
AdaptiveExecutionStrategy(
    dependency_graph={
        "bandit": ["gitleaks"],
        "refurb": ["zuban"],
    },
    max_parallel=4,  # Maximum concurrent executions per wave
    default_timeout=300,  # Default timeout per hook (seconds)
    stop_on_critical_failure=True,  # Stop if critical hook fails
)
```

## When to Use Each Strategy

| Scenario | Recommended Strategy | Reason |
|----------|---------------------|---------|
| Hooks have dependencies | Sequential or Adaptive | Respects execution order |
| All hooks independent | Parallel | Maximum throughput |
| Mixed dependencies | Adaptive | Optimal parallelism |
| Debugging flaky hooks | Sequential | Isolated execution |
| Resource constrained | Sequential | Controlled resource usage |
| Critical security gates | Sequential or Adaptive | Early exit on failure |
| Maximum speed | Parallel | All hooks run concurrently |

## Creating Custom Strategies

Implement the `ExecutionStrategyProtocol`:

```python
import asyncio
from crackerjack.config.hooks import HookDefinition
from crackerjack.models.task import HookResult


class CustomExecutionStrategy:
    """Custom execution strategy."""

    async def execute(
        self,
        hooks: list[HookDefinition],
        max_parallel: int = 3,
        timeout: int = 300,
        executor_callable: Callable[[HookDefinition], Awaitable[HookResult]]
        | None = None,
    ) -> list[HookResult]:
        """Custom execution logic."""
        results = []

        # Your custom execution logic here
        for hook in hooks:
            if executor_callable:
                result = await executor_callable(hook)
            else:
                result = self._placeholder_result(hook)
            results.append(result)

        return results

    def get_execution_order(
        self,
        hooks: list[HookDefinition],
    ) -> list[list[HookDefinition]]:
        """Define execution batches."""
        # Return custom batching logic
        return [[hook] for hook in hooks]

    def _placeholder_result(self, hook: HookDefinition) -> HookResult:
        """Placeholder when no executor provided."""
        return HookResult(
            id=hook.name,
            name=hook.name,
            status="passed",
            duration=0.0,
        )
```

## Integration with Hook Orchestration

Strategies are used by the hook orchestrator:

```python
from acb.depends import depends
from crackerjack.orchestration.strategies import AdaptiveExecutionStrategy
from crackerjack.models.protocols import HookOrchestratorProtocol


@depends.inject
async def run_hooks_with_strategy(
    orchestrator: HookOrchestratorProtocol = depends(),
) -> list[HookResult]:
    """Execute hooks using adaptive strategy."""
    # Define strategy
    strategy = AdaptiveExecutionStrategy(
        dependency_graph={"bandit": ["gitleaks"]},
        max_parallel=4,
    )

    # Execute via orchestrator
    results = await orchestrator.execute_strategy(
        strategy=strategy,
        execution_mode="acb",  # Direct adapter invocation
    )

    return results
```

## Performance Comparison

**Test scenario:** 10 hooks, 3 seconds each, 4 cores available

| Strategy | Execution Time | Speedup | Resource Usage |
|----------|----------------|---------|----------------|
| Sequential | 30s (10 × 3s) | 1x baseline | Low (1 core) |
| Parallel (max=4) | 9s (⌈10/4⌉ × 3s) | 3.3x faster | High (4 cores) |
| Adaptive (2 waves) | 15s (2 waves × 3s) | 2x faster | Medium (2-4 cores) |

**Recommendation:** Use Adaptive strategy for best balance of speed and resource efficiency.

## Best Practices

1. **Choose Strategy Appropriately**: Match strategy to workload characteristics
1. **Configure max_parallel**: Set based on available CPU cores and memory
1. **Set Reasonable Timeouts**: Hook timeouts should account for worst-case scenarios
1. **Handle Critical Failures**: Use `stop_on_critical_failure` for security hooks
1. **Monitor Performance**: Track execution times and adjust strategies
1. **Log Structured Data**: Strategies provide comprehensive logging for debugging
1. **Test Strategies**: Verify strategy behavior with test suites

## Configuration via Settings

```yaml
# settings/crackerjack.yaml
hook_execution:
  strategy: adaptive  # sequential, parallel, or adaptive
  max_parallel_hooks: 4
  default_timeout: 300
  stop_on_critical_failure: true

  # Dependency graph for adaptive strategy
  dependencies:
    bandit:
      - gitleaks
    refurb:
      - zuban
```

## Related Documentation

- [Orchestration Cache](../cache/README.md) - Caching for hook results
- [Hook Orchestration](../README.md) - Overall orchestration architecture
- [Models](../../models/README.md) - ExecutionStrategyProtocol definition
- [Core](../../core/README.md) - Workflow coordinators
- [CLAUDE.md](../../../docs/guides/CLAUDE.md) - Architecture patterns

## Future Enhancements

- Dynamic strategy selection based on workload analysis
- Resource-aware scheduling (CPU, memory constraints)
- Priority-based execution (critical hooks first)
- Distributed execution across multiple machines
- Machine learning-based dependency detection
- Real-time strategy adaptation based on performance metrics
