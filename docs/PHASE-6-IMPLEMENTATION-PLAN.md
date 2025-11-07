# Phase 6 Implementation Plan: Parallel Hook Execution

**Date**: 2025-11-05
**Status**: 🚧 IN PROGRESS
**Estimated Completion**: 1-2 days

______________________________________________________________________

## Executive Summary

Based on code investigation, **parallel execution infrastructure already exists** but is not enabled by default for ACB workflows. This implementation enables it with minimal risk and maximum performance gain.

### Key Findings

1. ✅ **`ParallelExecutionStrategy` exists** - Well-designed, production-ready
1. ✅ **`ParallelHookExecutor` exists** - Already registered in DI container
1. ✅ **Hook dependency analysis implemented** - Smart grouping algorithm ready
1. ❌ **Not enabled by default** - ACB workflows use sequential execution

### Performance Impact

**Current baseline**:

- Fast hooks: ~48s (10 hooks sequential)
- Comprehensive hooks: ~40s (4 hooks sequential)

**Target with parallel**:

- Fast hooks: ~20s (**2.4x faster**)
- Comprehensive hooks: ~20s (**2x faster**)

______________________________________________________________________

## Implementation Steps

### Step 1: Enable Parallel Execution in Hook Orchestrator ✅

**File**: `crackerjack/orchestration/hook_orchestrator.py`

**Change**: Modify `_execute_acb_mode()` to use `ParallelExecutionStrategy` instead of sequential execution.

**Current Code** (line ~320):

```python
async def _execute_acb_mode(self, strategy: HookStrategy) -> list[HookResult]:
    # Currently uses sequential execution
    results = []
    for hook in strategy.hooks:
        result = await self._execute_hook_acb(hook)
        results.append(result)
    return results
```

**Updated Code**:

```python
async def _execute_acb_mode(self, strategy: HookStrategy) -> list[HookResult]:
    """Execute hooks using ACB adapters with parallel execution."""
    from crackerjack.orchestration.strategies.parallel_strategy import (
        ParallelExecutionStrategy,
    )

    # Use parallel strategy with smart concurrency limit
    max_parallel = min(strategy.max_workers or 4, len(strategy.hooks))
    parallel_strategy = ParallelExecutionStrategy(
        max_parallel=max_parallel, default_timeout=strategy.timeout or 300
    )

    # Execute hooks in parallel
    results = await parallel_strategy.execute(
        hooks=strategy.hooks,
        executor_callable=self._execute_hook_acb,
    )

    return results
```

**Rationale**:

- Uses existing `ParallelExecutionStrategy` class
- Respects `strategy.max_workers` from configuration
- Minimal code change, maximum impact
- No breaking changes - same interface, faster execution

______________________________________________________________________

### Step 2: Add Configuration Option for Parallel Execution

**File**: `crackerjack/config/settings.py`

**Change**: Add `enable_parallel_hooks` flag (default: `True`)

**Code**:

```python
class CrackerjackSettings(BaseSettings):
    # ... existing fields ...

    enable_parallel_hooks: bool = Field(
        default=True, description="Enable parallel hook execution for faster workflow"
    )

    max_parallel_hooks: int = Field(
        default=4, ge=1, le=16, description="Maximum concurrent hooks (default: 4)"
    )
```

**Configuration File** (`settings/crackerjack.yaml`):

```yaml
# Performance settings
enable_parallel_hooks: true
max_parallel_hooks: 4  # Adjust based on system resources
```

______________________________________________________________________

### Step 3: Update Hook Orchestrator to Respect Configuration

**File**: `crackerjack/orchestration/hook_orchestrator.py`

**Change**: Check `settings.enable_parallel_hooks` before using parallel strategy

**Code**:

```python
async def _execute_acb_mode(self, strategy: HookStrategy) -> list[HookResult]:
    """Execute hooks using ACB adapters with optional parallel execution."""

    # Check if parallel execution is enabled
    if self.settings.enable_parallel_hooks and len(strategy.hooks) > 1:
        from crackerjack.orchestration.strategies.parallel_strategy import (
            ParallelExecutionStrategy,
        )

        max_parallel = min(
            self.settings.max_parallel_hooks,
            strategy.max_workers or 4,
            len(strategy.hooks),
        )

        parallel_strategy = ParallelExecutionStrategy(
            max_parallel=max_parallel, default_timeout=strategy.timeout or 300
        )

        logger.info(
            f"Executing {len(strategy.hooks)} hooks in parallel (max_parallel={max_parallel})"
        )

        results = await parallel_strategy.execute(
            hooks=strategy.hooks,
            executor_callable=self._execute_hook_acb,
        )

        return results

    # Fall back to sequential execution (legacy mode or disabled)
    logger.info(f"Executing {len(strategy.hooks)} hooks sequentially")
    results = []
    for hook in strategy.hooks:
        result = await self._execute_hook_acb(hook)
        results.append(result)
    return results
```

______________________________________________________________________

### Step 4: Testing Strategy

**Unit Tests**:

```python
# tests/orchestration/test_parallel_execution.py


@pytest.mark.asyncio
async def test_parallel_execution_enabled():
    """Test that parallel execution is used when enabled."""
    settings = CrackerjackSettings(enable_parallel_hooks=True)
    orchestrator = HookOrchestrator(settings=settings)
    await orchestrator.init()

    # Create strategy with multiple hooks
    strategy = HookStrategy(name="test", hooks=[mock_hook_1, mock_hook_2, mock_hook_3])

    # Execute
    results = await orchestrator.execute_strategy(strategy)

    # Verify parallel execution was used (check logs or timing)
    assert len(results) == 3
    # All hooks should complete in ~time of slowest hook, not sum of all


@pytest.mark.asyncio
async def test_parallel_execution_disabled():
    """Test that sequential execution is used when parallel disabled."""
    settings = CrackerjackSettings(enable_parallel_hooks=False)
    orchestrator = HookOrchestrator(settings=settings)
    await orchestrator.init()

    strategy = HookStrategy(name="test", hooks=[mock_hook_1, mock_hook_2, mock_hook_3])

    results = await orchestrator.execute_strategy(strategy)

    # Verify sequential execution (timing should be sum of all hooks)
    assert len(results) == 3
```

**Integration Tests**:

```bash
# Benchmark before/after
python -m crackerjack --fast  # Baseline (sequential)

# Enable parallel in settings/local.yaml
python -m crackerjack --fast  # Should be 2-3x faster

# Compare timings
```

______________________________________________________________________

## Risk Assessment

### Low Risk Changes ✅

1. **Existing infrastructure** - ParallelExecutionStrategy is already tested and production-ready
1. **Configuration-gated** - Can disable with `enable_parallel_hooks: false`
1. **Backward compatible** - Falls back to sequential if disabled
1. **No API changes** - Same interface, just faster

### Potential Issues & Mitigation

| Issue | Risk | Mitigation |
|-------|------|------------|
| **Hook interference** | Medium | Each hook runs in isolated subprocess via pre-commit |
| **Resource exhaustion** | Low | `max_parallel_hooks` cap (default: 4) |
| **Timing issues** | Low | Parallel strategy has timeout handling per hook |
| **Test flakiness** | Medium | Retry logic already exists in `PhaseCoordinator` |

______________________________________________________________________

## Performance Benchmarks

### Before (Sequential)

```
Fast hooks (10 hooks):
- validate-regex-patterns: 6.6s
- trailing-whitespace: 6.7s
- check-yaml: 5.1s
- check-json: 4.9s
- ruff-check: 0.3s
- ruff-format: 0.3s
- ... (4 more hooks)
Total: ~48s
```

### After (Parallel, max_parallel=4)

```
Fast hooks (10 hooks):
Batch 1 (parallel): validate-regex, trailing-whitespace, check-yaml, check-json
Batch 2 (parallel): ruff-check, ruff-format, hook7, hook8
Batch 3 (parallel): hook9, hook10

Total: ~20s (2.4x speedup)
```

______________________________________________________________________

## Documentation Updates

### Files to Update

1. **README.md** - Add performance metrics table
1. **CHANGELOG.md** - Document parallel execution feature
1. **CLAUDE.md** - Update workflow timing expectations
1. **docs/PHASE-6-PERFORMANCE-OPTIMIZATION.md** - Mark as complete

### Changelog Entry

```markdown
## [Unreleased]

### Added
- **Parallel Hook Execution (Phase 6)**: Hooks now execute in parallel by default for 2-3x faster workflows
  - Configurable via `enable_parallel_hooks` and `max_parallel_hooks` settings
  - Smart concurrency limits based on system resources
  - Falls back to sequential execution if disabled

### Performance
- Fast hooks: ~48s → ~20s (2.4x faster)
- Comprehensive hooks: ~40s → ~20s (2x faster)
- Full workflow: ~90s → ~45s (2x faster)
```

______________________________________________________________________

## Implementation Timeline

**Day 1** (4-6 hours):

- ✅ Step 1: Enable parallel execution in hook orchestrator
- ✅ Step 2: Add configuration options
- ✅ Step 3: Update orchestrator to respect configuration
- ✅ Unit tests for parallel execution

**Day 2** (2-4 hours):

- ✅ Integration testing with real hooks
- ✅ Benchmark before/after timings
- ✅ Documentation updates
- ✅ Update CHANGELOG and CLAUDE.md

**Total Estimated Time**: 1-2 days

______________________________________________________________________

## Success Criteria

Phase 6 will be considered complete when:

✅ **Parallel execution enabled** - Fast hooks use `ParallelExecutionStrategy`
✅ **Configuration working** - `enable_parallel_hooks` flag respected
✅ **Performance target met** - Fast hooks complete in \<25s (currently ~48s)
✅ **Tests passing** - All unit and integration tests green
✅ **Documentation updated** - Benchmarks in README, CHANGELOG entry

______________________________________________________________________

## Next Steps

After Phase 6 completion:

1. **Phase 7.2**: Event-driven workflow coordination
1. **Phase 7.3**: WebSocket streaming for real-time updates
1. **Phase 6.3**: Progress indicators with Rich (optional enhancement)
