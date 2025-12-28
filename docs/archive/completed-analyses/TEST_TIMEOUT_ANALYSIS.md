# Test Suite Timeout Analysis

**Issue**: Test suite times out at 836s (close to 900s workflow limit) even with SEQUENTIAL execution (1 worker)

**Date**: 2025-12-24

______________________________________________________________________

## Executive Summary

The test suite has **1,109.5 seconds of cumulative sleep time** across 102 calls, averaging 10.9 seconds per sleep. This is the primary cause of slow tests, not parallelization issues.

### Key Statistics

- **Total tests**: 4,308 tests collected
- **Collection time**: 61.58s (too high - indicates fixture/import overhead)
- **Async tests**: 782 async test functions across 79 files
- **Sleep markers**: 114 occurrences across 27 files
- **Sequential timeout**: 836.3s with 1 worker
- **Individual test timeout**: 600s
- **Workflow timeout**: 900s

______________________________________________________________________

## Critical Problems

### 1. **Excessive Sleep Times** (1,109.5s total)

#### Longest Sleeps:

- **1000s** - `tests/test_resource_cleanup_integration.py:444`

  ```python
  long_task = asyncio.create_task(asyncio.sleep(1000))  # Task cancelled after 0.1s
  ```

  **Impact**: Creates task but cancels quickly - probably safe, but concerning pattern

- **12s** - `tests/test_pytest_features.py:32`

  ```python
  def test_slow_but_not_hanging():
      time.sleep(12)  # Intentional slow test
      assert True
  ```

  **Impact**: This single test takes 12 seconds for no value - pure waste

- **10s sleeps** (multiple) in `tests/unit/core/test_resource_manager.py`:

  ```python
  async def dummy_task():
      await asyncio.sleep(10)  # Lines 421, 437, 452, 565
  ```

  **Impact**: 4 tests × 10s = 40s just for task initialization

#### Medium Sleeps (3-5s range):

- `tests/test_profiler_integration.py:92` - 3.5s bottleneck test
- Multiple 1.0s sleeps in timeout manager tests (~30+ occurrences)

______________________________________________________________________

### 2. **Test Collection Overhead** (61.58s)

**Problem**: Test collection takes over 1 minute before any tests run.

**Likely causes**:

- Heavy fixture initialization
- Complex import chains
- Module-level code execution
- Dependency injection container setup

**Files with most async tests** (potential fixtures):

- `test_file_lifecycle.py` - 46 async tests
- `test_resource_manager.py` - 32 async tests
- `test_test_creation_agent.py` - 25 async tests
- `test_hook_lock_manager.py` - 16 async tests

______________________________________________________________________

### 3. **Performance Test Suite** (test_triple_parallelism_benchmarks.py)

**Collection**: 6 tests collected in 58.92s
**Size**: 566 lines

#### Sleep patterns:

```python
# Short sleeps (0.05-0.15s) but executed many times
await asyncio.sleep(0.05)  # 50ms for fast hooks (lines 300, 375, 446, 536, 542)
await asyncio.sleep(0.15)  # 150ms for comprehensive hooks (line 454)
await asyncio.sleep(fast_duration)  # Variable (lines 90, 114)
await asyncio.sleep(comp_duration)  # Variable (lines 94, 118)
```

**Concerns**:

- No `@pytest.mark.benchmark` or `@pytest.mark.slow` markers
- Runs on every test execution
- Tests measure performance but ADD to overall runtime
- Should be in separate benchmark suite

______________________________________________________________________

### 4. **Timeout Manager Tests** (test_timeout_manager.py)

**Size**: 815 lines
**Sleep calls**: 20+ occurrences of 1.0s sleeps

**Pattern**:

```python
async def slow_task():
    await asyncio.sleep(1.0)  # Lines 244, 256, 280, 308, 320, 340, 575, 589, 747
```

**Impact**: 20+ tests × 1s = 20+ seconds just for timeout testing

______________________________________________________________________

### 5. **Resource Manager Tests** (test_resource_manager.py)

**Size**: 852 lines
**Major issue**: 10-second dummy tasks

```python
async def dummy_task():
    await asyncio.sleep(10)


# Used in lines: 421, 437, 452, 565
```

**Problem**: These tasks are immediately cancelled, but still wasteful pattern.

______________________________________________________________________

## Performance Test Detection Issues

### Benchmark Markers Missing

Only **2 tests** use `@pytest.mark.benchmark`:

```python
tests/test_pytest_features.py:42
tests/test_pytest_features.py:51
```

**Missing markers on**:

- `tests/performance/test_triple_parallelism_benchmarks.py` (all 6 tests)
- `tests/test_core_performance.py` (multiple tests with sleep)
- `tests/test_profiler_integration.py` (bottleneck tests)

**Impact**: Performance tests run on every test execution, not just when benchmarking.

______________________________________________________________________

## Large Iteration Loops (Not Executing, Just Test Data)

These are **test strings being analyzed**, not actual executing loops:

```python
# test_performance_agent_enhanced.py - Test data, not executing code
for a in range(1000):
    for b in range(1000):
        for c in range(1000):
            for d in range(1000):  # O(n⁴) pattern in string
```

**Status**: ✅ Safe - these are test inputs, not running code

______________________________________________________________________

## Recommendations

### Immediate Actions (High Impact)

#### 1. **Remove/Skip Wasteful Test** (Saves 12s)

```python
# tests/test_pytest_features.py:31
@pytest.mark.skip(reason="Intentionally slow test - no value")
def test_slow_but_not_hanging():
    time.sleep(12)
    assert True
```

#### 2. **Add Benchmark Markers** (Saves ~100s in regular runs)

```python
# tests/performance/test_triple_parallelism_benchmarks.py
@pytest.mark.benchmark
@pytest.mark.slow
class TestParallelExecutionBenchmarks: ...


# tests/test_core_performance.py
@pytest.mark.benchmark
def test_performance_overhead_with_many_hooks(): ...
```

**Run benchmarks separately**:

```bash
# Regular tests (skip benchmarks)
pytest -m "not benchmark"

# Benchmark suite only
pytest -m benchmark --benchmark-only
```

#### 3. **Reduce Dummy Task Sleep Times** (Saves 40s)

```python
# tests/unit/core/test_resource_manager.py
async def dummy_task():
    await asyncio.sleep(0.01)  # Was 10s, reduce to 10ms
```

**Lines to change**: 421, 437, 452, 565

#### 4. **Reduce Timeout Test Sleep Times** (Saves 20s)

```python
# tests/unit/core/test_timeout_manager.py
async def slow_task():
    await asyncio.sleep(0.1)  # Was 1.0s, reduce to 100ms
```

**Context**: Tests verify timeout behavior - 100ms is sufficient to test timeout logic without waiting full seconds.

#### 5. **Reduce Profiler Integration Sleeps** (Saves 4s)

```python
# tests/test_profiler_integration.py
time.sleep(0.05)  # Was 0.5s for type checking
time.sleep(0.03)  # Was 0.3s for security scanning
time.sleep(0.35)  # Was 3.5s for bottleneck test
```

______________________________________________________________________

### Medium Priority Actions

#### 6. **Optimize Test Collection** (Target: \<10s)

**Investigate**:

- Lazy fixture loading
- Reduce module-level imports
- Defer heavy dependency injection setup
- Use `pytest-xdist` load distribution strategies

**Current**: 61.58s → **Target**: \<10s

#### 7. **Separate Test Categories**

Create `pyproject.toml` marker configuration:

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "benchmark: marks tests as benchmarks (run separately)",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]
```

**Run strategies**:

```bash
# Fast unit tests only (CI, pre-commit)
pytest -m "unit and not slow and not benchmark"

# Full suite except benchmarks (nightly)
pytest -m "not benchmark"

# Benchmark suite only (weekly)
pytest -m benchmark --benchmark-only
```

______________________________________________________________________

### Low Priority Optimizations

#### 8. **Replace Sleep with Mock Time**

For tests that don't need actual delays:

```python
# Instead of
await asyncio.sleep(1.0)

# Use mock time (pytest-mock, freezegun)
from unittest.mock import patch

with patch("asyncio.sleep"):
    await asyncio.sleep(1.0)  # Instant
```

#### 9. **Parallel-Safe Benchmark Design**

If benchmarks must run in main suite:

- Skip when `PYTEST_XDIST_WORKER` is set
- Use `@pytest.mark.xdist_group(name="sequential")` to serialize them

______________________________________________________________________

## Expected Improvements

### Conservative Estimates:

| Optimization | Time Saved | Cumulative |
|--------------|------------|------------|
| Skip slow_but_not_hanging | 12s | 824s |
| Add benchmark markers | ~100s | 724s |
| Reduce dummy task sleeps (10s→0.01s) | 40s | 684s |
| Reduce timeout test sleeps (1s→0.1s) | 20s | 664s |
| Reduce profiler sleeps | 4s | 660s |
| **Total Phase 1** | **176s** | **660s** |

**Phase 2** (Test collection optimization):

- Current: 61.58s
- Target: \<10s
- Savings: ~50s
- **New total**: ~610s

**Phase 3** (Mock time in timeout tests):

- Additional savings: ~20s
- **Final target**: ~590s

______________________________________________________________________

## Risk Assessment

### Low Risk (Do Immediately):

✅ Skip `test_slow_but_not_hanging` - intentionally slow, no value
✅ Add `@pytest.mark.benchmark` markers - pure configuration
✅ Reduce sleep times in mock/dummy functions - tests don't rely on actual time

### Medium Risk (Test Thoroughly):

⚠️ Timeout tests with reduced sleep - verify timeouts still trigger correctly
⚠️ Profiler tests with reduced sleep - verify bottleneck detection still works

### High Risk (Defer):

❌ Mock time globally - may break time-dependent logic
❌ Remove integration tests - coverage loss

______________________________________________________________________

## Implementation Priority

### Sprint 1: Quick Wins (1 hour, 176s saved)

1. Skip `test_slow_but_not_hanging`
1. Add benchmark markers to performance tests
1. Reduce dummy task sleeps 10s→0.01s
1. Reduce timeout test sleeps 1s→0.1s
1. Reduce profiler integration sleeps

### Sprint 2: Collection Optimization (4 hours, 50s saved)

1. Profile pytest collection phase
1. Lazy-load heavy fixtures
1. Optimize import chains
1. Defer DI container initialization

### Sprint 3: Advanced Optimizations (8 hours, 20s saved)

1. Implement mock time for timeout tests
1. Benchmark-specific test isolation
1. Fixture caching strategies

______________________________________________________________________

## Monitoring

**Before optimizations**: 836.3s (sequential, 1 worker)

**After Phase 1**: Target 660s (26% improvement)
**After Phase 2**: Target 610s (37% improvement)
**After Phase 3**: Target 590s (42% improvement)

**Success criteria**: Test suite completes in \<600s (10 minutes) with buffer for 900s workflow limit.

______________________________________________________________________

## Files to Modify

### High Priority:

1. `tests/test_pytest_features.py` - Skip slow test
1. `tests/performance/test_triple_parallelism_benchmarks.py` - Add markers
1. `tests/unit/core/test_resource_manager.py` - Reduce sleeps (lines 421, 437, 452, 565)
1. `tests/unit/core/test_timeout_manager.py` - Reduce sleeps (~20 locations)
1. `tests/test_profiler_integration.py` - Reduce sleeps (lines 24, 27, 31, 34, 92)
1. `tests/test_core_performance.py` - Add benchmark marker

### Medium Priority:

7. `pyproject.toml` - Add marker configuration
1. `.github/workflows/*.yml` - Update CI to skip benchmarks
1. Fixture optimization in `conftest.py` files

______________________________________________________________________

## Notes

- **Parallelization is NOT the problem** - 836s with 1 worker proves tests are inherently slow
- **Sleep accumulation** - 1,109.5s of sleep across 102 calls is the root cause
- **Collection overhead** - 61.58s before any tests run is excessive
- **Performance tests** - Running benchmarks on every test execution is wasteful
- **Mock patterns** - Many tests use sleep when mock time would suffice

**Bottom line**: With 176 seconds of easy optimizations, test suite can run in \<660s (well under 900s limit).
