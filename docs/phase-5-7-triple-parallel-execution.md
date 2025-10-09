# Phase 5-7: Triple Parallel Execution Implementation Plan

## Executive Summary

**Goal**: Implement three-tier parallel execution where QA adapters, execution strategies, and individual hooks all run concurrently, maximizing throughput while maintaining dependency ordering.

**Timeline**: Week 4-5
**Current Status**: Phase 4 (Configuration Management) complete
**Dependencies**: Phases 1-4 (ACB infrastructure, adapters, orchestration, config)

## Architecture Overview

### Current State (Phase 4)
```
HookManager
  ├─> run_fast_hooks() → sequential
  ├─> run_comprehensive_hooks() → sequential
  └─> run_hooks() → fast THEN comprehensive

HookOrchestratorAdapter
  ├─> _execute_parallel() → hooks within a strategy
  └─> _execute_sequential() → hooks within a strategy
```

### Target State (Phase 5-7)
```
HookManager
  ├─> run_fast_hooks() ─┐
  ├─> run_comprehensive_hooks() ─┼─> ALL CONCURRENT
  └─> run_hooks() ─┘

HookOrchestratorAdapter
  ├─> _execute_parallel() → concurrent hooks (respecting dependencies)
  ├─> _execute_sequential() → fallback for critical dependencies
  └─> _execute_adaptive() → NEW: dynamic parallel/sequential mix
```

## Three Tiers of Parallelism

### Tier 1: Strategy-Level Parallelism
**Scope**: Multiple HookStrategy executions in parallel

```python
# Current (sequential)
fast_results = await orchestrator.execute_strategy(fast_strategy)
comprehensive_results = await orchestrator.execute_strategy(comprehensive_strategy)

# Target (parallel)
fast_task = orchestrator.execute_strategy(fast_strategy)
comprehensive_task = orchestrator.execute_strategy(comprehensive_strategy)
results = await asyncio.gather(fast_task, comprehensive_task)
```

**Benefits**:
- Fast hooks (5s) and comprehensive hooks (30s) run simultaneously
- Total execution time: max(fast, comprehensive) instead of sum(fast + comprehensive)
- ~40% time savings (5s + 30s = 35s → max(5s, 30s) = 30s)

### Tier 2: Hook-Level Parallelism
**Scope**: Multiple hooks within a strategy execute in parallel (already implemented)

**Current Implementation**:
- `ParallelExecutionStrategy`: Uses asyncio.Semaphore for resource limiting
- `SequentialExecutionStrategy`: One-at-a-time with early exit

**Enhancement Needed**:
- **Adaptive Execution**: Mix parallel and sequential based on dependency graph
- **Dependency Batching**: Group independent hooks into concurrent batches

### Tier 3: Adapter-Level Parallelism
**Scope**: Multiple QA adapters checking different files simultaneously (Phase 8+)

**Example**:
```python
# Within a single hook execution
bandit_adapter = await depends.get(BanditAdapter)

# Current (sequential)
for file in files:
    result = await bandit_adapter.check(file)

# Target (parallel)
tasks = [bandit_adapter.check(file) for file in files]
results = await asyncio.gather(*tasks)
```

**Status**: Placeholder for Phase 8 (direct adapter calls)

## Implementation Tasks

### Task 1: Strategy-Level Parallelism in HookManager

**File**: `crackerjack/managers/hook_manager.py`

**Changes**:
1. Make `run_fast_hooks()` return coroutine when orchestration enabled
2. Make `run_comprehensive_hooks()` return coroutine when orchestration enabled
3. Update `run_hooks()` to execute both strategies concurrently

**Implementation**:
```python
def run_hooks(self) -> list[HookResult]:
    """Execute fast and comprehensive hooks in parallel."""
    if self.orchestration_enabled:
        import asyncio

        # Execute both strategies concurrently
        fast_task = self._run_fast_hooks_orchestrated()
        comp_task = self._run_comprehensive_hooks_orchestrated()

        fast_results, comp_results = asyncio.run(
            asyncio.gather(fast_task, comp_task)
        )

        return fast_results + comp_results

    # Legacy path (sequential)
    fast_results = self.run_fast_hooks()
    comprehensive_results = self.run_comprehensive_hooks()
    return fast_results + comprehensive_results
```

**Testing Requirements**:
- Verify both strategies execute concurrently
- Measure execution time improvement (should be ~max(fast, comp) not sum)
- Ensure results are correctly combined
- Test error handling (one strategy fails, other continues)

### Task 2: Adaptive Execution Strategy

**New File**: `crackerjack/orchestration/strategies/adaptive_strategy.py`

**Purpose**: Dynamically mix parallel and sequential execution based on dependency graph

**Algorithm**:
1. Analyze dependency graph to identify independent groups
2. Create execution waves:
   - Wave 1: All hooks with zero dependencies (parallel)
   - Wave 2: Hooks whose dependencies completed (parallel within wave)
   - Wave N: Repeat until all hooks executed
3. Each wave executes hooks in parallel
4. Waves execute sequentially (respect dependencies)

**Example**:
```python
# Dependency graph:
# gitleaks → bandit
# zuban → refurb
# ruff-format (independent)
# ruff-check (independent)

# Execution waves:
# Wave 1 (parallel): gitleaks, zuban, ruff-format, ruff-check
# Wave 2 (parallel): bandit, refurb
```

**Benefits**:
- Maximizes parallelism while respecting dependencies
- Better than pure parallel (respects dependencies)
- Better than pure sequential (parallel where possible)

**Implementation**:
```python
class AdaptiveExecutionStrategy:
    """Adaptive execution with dependency-aware batching."""

    def __init__(
        self,
        dependency_graph: dict[str, list[str]],
        max_parallel: int = 4,
        default_timeout: int = 300,
    ) -> None:
        self.dependency_graph = dependency_graph
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout

    async def execute(
        self,
        hooks: list[HookDefinition],
        max_parallel: int | None = None,
        timeout: int | None = None,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]] | None = None,
    ) -> list[HookResult]:
        """Execute hooks in dependency-aware waves."""
        if not hooks:
            return []

        # Compute execution waves using topological sort
        waves = self._compute_execution_waves(hooks)

        # Execute each wave in parallel, waves sequentially
        all_results = []
        for wave_idx, wave_hooks in enumerate(waves, 1):
            logger.info(
                f"Executing wave {wave_idx}/{len(waves)}",
                extra={
                    "wave_idx": wave_idx,
                    "total_waves": len(waves),
                    "hooks_in_wave": len(wave_hooks),
                    "hook_names": [h.name for h in wave_hooks],
                }
            )

            # Execute this wave in parallel
            wave_results = await self._execute_wave(
                wave_hooks,
                max_parallel=max_parallel or self.max_parallel,
                timeout=timeout or self.default_timeout,
                executor_callable=executor_callable,
            )

            all_results.extend(wave_results)

            # Check for critical failures that should stop execution
            if self._has_critical_failure(wave_results):
                logger.warning("Critical failure in wave, stopping execution")
                break

        return all_results

    def _compute_execution_waves(
        self,
        hooks: list[HookDefinition],
    ) -> list[list[HookDefinition]]:
        """Compute execution waves using topological sort.

        Returns:
            List of waves, each wave contains hooks that can execute in parallel
        """
        # Build hook name → hook mapping
        hook_map = {hook.name: hook for hook in hooks}

        # Build in-degree map (count of dependencies per hook)
        in_degree = {hook.name: 0 for hook in hooks}
        for hook_name in hook_map:
            if hook_name in self.dependency_graph:
                in_degree[hook_name] = len(self.dependency_graph[hook_name])

        # Compute waves
        waves = []
        remaining_hooks = set(hook_map.keys())

        while remaining_hooks:
            # Find all hooks with zero dependencies in this wave
            ready_hooks = [
                hook_map[name]
                for name in remaining_hooks
                if in_degree[name] == 0
            ]

            if not ready_hooks:
                # Circular dependency detected
                logger.error(
                    "Circular dependency detected",
                    extra={"remaining_hooks": list(remaining_hooks)}
                )
                # Add all remaining hooks to final wave as fallback
                waves.append([hook_map[name] for name in remaining_hooks])
                break

            # Add this wave
            waves.append(ready_hooks)

            # Remove these hooks from remaining
            for hook in ready_hooks:
                remaining_hooks.remove(hook.name)

            # Update in-degrees for dependent hooks
            for hook in ready_hooks:
                for dependent_name, deps in self.dependency_graph.items():
                    if hook.name in deps and dependent_name in remaining_hooks:
                        in_degree[dependent_name] -= 1

        return waves

    async def _execute_wave(
        self,
        hooks: list[HookDefinition],
        max_parallel: int,
        timeout: int,
        executor_callable: t.Callable[[HookDefinition], t.Awaitable[HookResult]] | None,
    ) -> list[HookResult]:
        """Execute a single wave of hooks in parallel."""
        semaphore = asyncio.Semaphore(max_parallel)

        async def execute_with_limit(hook: HookDefinition) -> HookResult:
            async with semaphore:
                if executor_callable:
                    return await asyncio.wait_for(
                        executor_callable(hook),
                        timeout=hook.timeout or timeout
                    )
                else:
                    return HookResult(
                        hook_name=hook.name,
                        status="passed",
                        duration=0.0,
                        output="[Placeholder]",
                    )

        tasks = [execute_with_limit(hook) for hook in hooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        final_results = []
        for hook, result in zip(hooks, results):
            if isinstance(result, HookResult):
                final_results.append(result)
            else:
                final_results.append(
                    HookResult(
                        hook_name=hook.name,
                        status="error",
                        duration=0.0,
                        output=f"Exception: {result}",
                    )
                )

        return final_results

    def _has_critical_failure(self, results: list[HookResult]) -> bool:
        """Check if any critical failure occurred in results."""
        # This would require tracking security levels
        # For now, just check for errors
        return any(r.status in ("error", "timeout") for r in results)
```

### Task 3: Integration of Adaptive Strategy into Orchestrator

**File**: `crackerjack/orchestration/hook_orchestrator.py`

**Changes**:
1. Import `AdaptiveExecutionStrategy`
2. Update `_execute_acb_mode()` to use adaptive strategy
3. Add configuration option for strategy selection

**Implementation**:
```python
async def _execute_acb_mode(self, strategy: HookStrategy) -> list[HookResult]:
    """Execute hooks via direct adapter calls (ACB-powered)."""
    logger.debug(
        "Using ACB direct adapter execution mode",
        extra={
            "strategy_name": strategy.name,
            "enable_dependency_resolution": self.settings.enable_dependency_resolution,
        }
    )

    # NEW: Use adaptive strategy for optimal parallelism
    if self.settings.enable_dependency_resolution:
        from crackerjack.orchestration.strategies.adaptive_strategy import (
            AdaptiveExecutionStrategy,
        )

        execution_strategy = AdaptiveExecutionStrategy(
            dependency_graph=self._dependency_graph,
            max_parallel=strategy.max_workers or self.settings.max_parallel_hooks,
            default_timeout=self.settings.default_timeout,
        )

        results = await execution_strategy.execute(
            hooks=strategy.hooks,
            executor_callable=self._execute_single_hook,
        )
    elif strategy.parallel:
        results = await self._execute_parallel(strategy.hooks, strategy.max_workers)
    else:
        results = await self._execute_sequential(strategy.hooks)

    logger.info(
        "ACB mode execution complete",
        extra={
            "strategy_name": strategy.name,
            "total_hooks": len(results),
            "passed": sum(1 for r in results if r.status == "passed"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "errors": sum(1 for r in results if r.status in ("timeout", "error")),
        }
    )

    return results
```

### Task 4: Configuration Support

**File**: `crackerjack/orchestration/config.py`

**Changes**:
Add new configuration options:
```python
@dataclass
class OrchestrationConfig:
    # ... existing fields ...

    # Triple parallelism settings (Phase 5-7)
    enable_strategy_parallelism: bool = True  # Run fast + comprehensive concurrently
    enable_adaptive_execution: bool = True    # Use adaptive strategy (dependency-aware)
    max_concurrent_strategies: int = 2        # Usually 2 (fast + comprehensive)
```

### Task 5: Testing

**New File**: `tests/orchestration/test_adaptive_strategy.py`

**Test Coverage**:
1. **Wave Computation**:
   - Test zero dependencies (all in wave 1)
   - Test simple dependencies (A → B creates 2 waves)
   - Test diamond dependencies (A → B,C → D creates 3 waves)
   - Test circular dependency detection

2. **Execution**:
   - Test parallel execution within waves
   - Test sequential execution between waves
   - Test timeout handling per hook
   - Test exception isolation (one hook fails, wave continues)

3. **Critical Failures**:
   - Test early exit on critical hook failure
   - Test continuation on non-critical failures

**New File**: `tests/managers/test_hook_manager_triple_parallel.py`

**Test Coverage**:
1. **Strategy-Level Parallelism**:
   - Test concurrent execution of fast + comprehensive
   - Measure execution time (should be ~max not sum)
   - Test result combining (fast + comprehensive)
   - Test error handling (one strategy fails)

2. **Configuration**:
   - Test enable_strategy_parallelism flag
   - Test enable_adaptive_execution flag
   - Test max_concurrent_strategies limit

3. **Integration**:
   - Test full workflow with triple parallelism enabled
   - Compare performance with/without parallelism
   - Test with various dependency graphs

## Performance Expectations

### Current Performance (Sequential)
```
run_hooks() execution time:
  = fast_hooks (5s) + comprehensive_hooks (30s)
  = 35 seconds total
```

### Phase 5-7 Performance (Triple Parallel)
```
run_hooks() execution time:
  = max(fast_hooks (5s), comprehensive_hooks (30s))
  = 30 seconds total

Speedup: 35s → 30s = 14% improvement
```

**Additional Improvements**:
- Within comprehensive_hooks: parallel where possible
- Example: gitleaks, zuban, ruff-format, ruff-check all run in wave 1
- Wave 1 duration: max(gitleaks, zuban, ruff-format, ruff-check) ≈ 8s (instead of 20s sequential)
- **Total speedup: 35s → 22s = 37% improvement**

## Rollout Strategy

### Step 1: Implement Adaptive Strategy (Week 4, Day 1-2)
- Create `adaptive_strategy.py`
- Write unit tests for wave computation
- Verify dependency-aware batching

### Step 2: Integrate into Orchestrator (Week 4, Day 3)
- Update `_execute_acb_mode()` to use adaptive strategy
- Add configuration options
- Test orchestrator with adaptive execution

### Step 3: Enable Strategy-Level Parallelism (Week 4, Day 4)
- Update `run_hooks()` in HookManager
- Add configuration flag
- Test concurrent strategy execution

### Step 4: Comprehensive Testing (Week 4, Day 5)
- Integration tests for triple parallelism
- Performance benchmarking
- Error handling scenarios

### Step 5: Documentation & Monitoring (Week 5, Day 1-2)
- Update CLAUDE.md with parallelism details
- Add logging for parallelism metrics
- Document configuration options

### Step 6: Validation & Tuning (Week 5, Day 3-5)
- Run full test suite with parallelism enabled
- Tune max_parallel_hooks for optimal performance
- Identify and fix any race conditions

## Risk Mitigation

### Risk 1: Race Conditions
**Mitigation**: Use asyncio.Semaphore for resource limiting, no shared mutable state

### Risk 2: Resource Exhaustion
**Mitigation**: Configurable limits (max_parallel_hooks, max_concurrent_strategies)

### Risk 3: Dependency Resolution Bugs
**Mitigation**: Comprehensive unit tests for wave computation, fallback to sequential

### Risk 4: Debugging Complexity
**Mitigation**: Structured logging with wave/hook context, execution timeline visualization

### Risk 5: Performance Regression
**Mitigation**: Benchmarking suite, A/B comparison with sequential execution

## Success Criteria

1. ✅ All existing tests pass with parallelism enabled
2. ✅ New tests for adaptive strategy pass (>90% coverage)
3. ✅ Integration tests for strategy-level parallelism pass
4. ✅ Performance improvement ≥30% over sequential execution
5. ✅ No race conditions or deadlocks detected
6. ✅ Graceful degradation when parallelism fails
7. ✅ Configuration options work as expected
8. ✅ Logging provides clear execution visibility

## Next Steps

After Phase 5-7 completion:
- **Phase 8**: Pre-commit Infrastructure Removal (replace subprocess with direct adapter calls)
- **Phase 9**: MCP Server Enhancement (expose orchestration capabilities)
- **Phase 10**: Final Integration & Testing (production readiness)
