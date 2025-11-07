# Test Parallelization Strategies Proposal

## Problem Statement

Currently, tests only run with 1 worker despite `pytest-xdist` being installed. The root cause is in `TestCommandBuilder.get_optimal_workers()` (line 26-30):

```python
def get_optimal_workers(self, options: OptionsProtocol) -> int:
    if hasattr(options, "test_workers") and options.test_workers:
        return options.test_workers

    return 1  # ❌ Always returns 1 when test_workers=0 (auto-detect)
```

**Configuration**: `settings/crackerjack.yaml:30` sets `test_workers: 0` (auto-detect), but the code treats `0` as falsy and falls back to `1`.

## Proposed Strategies

### Strategy 1: Auto-Detection with CPU-Based Scaling (Recommended)

**Description**: Intelligently detect optimal worker count based on CPU cores, with safety limits.

**Implementation**:

```python
import os
import multiprocessing


def get_optimal_workers(self, options: OptionsProtocol) -> int:
    """Calculate optimal worker count for parallel test execution.

    Logic:
    - test_workers > 0: Use explicit value
    - test_workers = 0: Auto-detect (CPU cores - 1, min 2, max 8)
    - test_workers < 0: Use abs(value) as divisor (e.g., -2 = cores/2)
    """
    if hasattr(options, "test_workers"):
        workers = options.test_workers

        if workers > 0:
            # Explicit worker count
            return workers
        elif workers == 0:
            # Auto-detect: use CPU cores - 1, bounded by [2, 8]
            cpu_count = multiprocessing.cpu_count()
            optimal = max(2, min(cpu_count - 1, 8))
            return optimal
        else:
            # Negative values: divide cores by abs(value)
            # e.g., -2 on 8-core = 4 workers
            cpu_count = multiprocessing.cpu_count()
            divisor = abs(workers)
            return max(1, cpu_count // divisor)

    # No test_workers attribute: default to 2 for safety
    return 2
```

**Configuration Examples**:

```yaml
# Auto-detect (recommended)
test_workers: 0  # → CPU cores - 1, capped at 2-8

# Explicit count
test_workers: 4  # → Always use 4 workers

# Fractional cores (conservative)
test_workers: -2  # → Half CPU cores (8 cores → 4 workers)
test_workers: -4  # → Quarter cores (8 cores → 2 workers)

# Disable parallelization
test_workers: 1  # → Single-threaded
```

**Pros**:

- ✅ Zero configuration for most users
- ✅ Adapts to different hardware (local vs CI)
- ✅ Safety bounds prevent resource exhaustion
- ✅ Flexible for power users (negative values)
- ✅ Backwards compatible (explicit values still work)

**Cons**:

- ⚠️ May be overly aggressive on high-core machines (mitigated by max=8)
- ⚠️ Requires `multiprocessing` import (stdlib, minimal cost)

**Test Impact**:

- 8-core MacBook: 0 → 7 workers (capped at 8)
- 4-core CI server: 0 → 3 workers
- 16-core workstation: 0 → 8 workers (capped)

______________________________________________________________________

### Strategy 2: Environment-Aware Detection

**Description**: Detect execution environment (local, CI, Docker) and adjust accordingly.

**Implementation**:

```python
import os
import multiprocessing
import sys


def get_optimal_workers(self, options: OptionsProtocol) -> int:
    """Environment-aware worker detection."""
    if hasattr(options, "test_workers") and options.test_workers > 0:
        return options.test_workers

    cpu_count = multiprocessing.cpu_count()

    # Detect environment
    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    is_docker = os.path.exists("/.dockerenv")
    is_low_memory = sys.platform == "darwin" and cpu_count <= 2

    if is_ci:
        # CI: Conservative (avoid timeouts)
        return min(4, max(2, cpu_count // 2))
    elif is_docker:
        # Docker: Very conservative (shared resources)
        return min(2, cpu_count)
    elif is_low_memory:
        # Low-spec machine: Sequential
        return 1
    else:
        # Local development: Aggressive
        return max(2, min(cpu_count - 1, 8))
```

**Pros**:

- ✅ Optimized for CI/CD pipelines
- ✅ Prevents Docker resource contention
- ✅ Adapts to low-spec machines
- ✅ Maximizes local dev speed

**Cons**:

- ⚠️ More complex logic (harder to debug)
- ⚠️ Requires environment detection (may be unreliable)
- ⚠️ Heuristics may not fit all environments

______________________________________________________________________

### Strategy 3: Adaptive Load-Based Scaling

**Description**: Start with conservative workers, scale up if tests complete quickly.

**Implementation**:

```python
import multiprocessing
import psutil  # Requires psutil dependency (already in pyproject.toml)


def get_optimal_workers(self, options: OptionsProtocol) -> int:
    """Adaptive worker count based on system load."""
    if hasattr(options, "test_workers") and options.test_workers > 0:
        return options.test_workers

    cpu_count = multiprocessing.cpu_count()

    # Check current system load
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem_percent = psutil.virtual_memory().percent

        # High load: conservative
        if cpu_percent > 70 or mem_percent > 80:
            return max(1, cpu_count // 4)

        # Medium load: moderate
        elif cpu_percent > 40 or mem_percent > 60:
            return max(2, cpu_count // 2)

        # Low load: aggressive
        else:
            return max(2, min(cpu_count - 1, 8))

    except Exception:
        # Fallback if psutil fails
        return max(2, cpu_count // 2)
```

**Pros**:

- ✅ Adapts to real-time system load
- ✅ Prevents resource starvation
- ✅ Works well on shared machines

**Cons**:

- ⚠️ Relies on psutil (already a dependency, but adds overhead)
- ⚠️ Non-deterministic (same command different results)
- ⚠️ May be too conservative during bursts

______________________________________________________________________

### Strategy 4: Test-Suite-Aware Scaling

**Description**: Adjust workers based on test suite characteristics (count, duration).

**Implementation**:

```python
import multiprocessing
from pathlib import Path


def get_optimal_workers(self, options: OptionsProtocol) -> int:
    """Scale workers based on test suite size."""
    if hasattr(options, "test_workers") and options.test_workers > 0:
        return options.test_workers

    cpu_count = multiprocessing.cpu_count()

    # Estimate test count (quick heuristic)
    test_count = self._estimate_test_count()

    if test_count < 10:
        # Small suite: sequential is faster (avoid overhead)
        return 1
    elif test_count < 50:
        # Medium suite: 2-4 workers
        return min(4, max(2, cpu_count // 2))
    else:
        # Large suite: aggressive parallelization
        return max(4, min(cpu_count - 1, 8))


def _estimate_test_count(self) -> int:
    """Quick estimate of test count by counting test_ functions."""
    test_dir = self.pkg_path / "tests"
    if not test_dir.exists():
        return 0

    count = 0
    for test_file in test_dir.rglob("test_*.py"):
        try:
            content = test_file.read_text()
            count += content.count("def test_")
        except Exception:
            pass

    return count
```

**Pros**:

- ✅ Optimized per project (small vs large suites)
- ✅ Avoids overhead for tiny test suites
- ✅ Scales naturally as project grows

**Cons**:

- ⚠️ Adds filesystem I/O (test file parsing)
- ⚠️ Heuristic may be inaccurate (fixtures, parametrize)
- ⚠️ Overhead on every test run

______________________________________________________________________

## Comparison Matrix

| Strategy | Complexity | Performance | Reliability | CI-Friendly | Maintenance |
|----------|-----------|-------------|-------------|-------------|-------------|
| **1. CPU-Based (Recommended)** | Low | High | High | ✅ Yes | Easy |
| 2. Environment-Aware | Medium | High | Medium | ✅ Yes | Medium |
| 3. Load-Based | High | Medium | Medium | ⚠️ Maybe | Hard |
| 4. Test-Suite-Aware | Medium | Medium | High | ✅ Yes | Medium |

## Recommendation

**Implement Strategy 1 (CPU-Based Scaling)** with the following rationale:

1. **Simplicity**: Single `multiprocessing.cpu_count()` call, minimal logic
1. **Predictability**: Deterministic behavior (same hardware = same workers)
1. **Safety**: Bounded by `[2, 8]` to prevent resource exhaustion
1. **Flexibility**: Supports explicit values, auto-detect, and fractional modes
1. **Zero Configuration**: Works out-of-the-box for 95% of users

### Implementation Plan

1. Update `TestCommandBuilder.get_optimal_workers()` with new logic
1. Add unit tests for all worker calculation modes
1. Update documentation in `CLAUDE.md` and `settings/crackerjack.yaml`
1. Test on local (8-core) and CI (4-core) environments
1. Monitor for any test flakiness or timeouts

### Migration Path

**No breaking changes** - existing configurations continue to work:

- `test_workers: 4` → Still uses 4 workers
- `test_workers: 1` → Still sequential
- `test_workers: 0` → **NEW**: Auto-detects (current behavior is 1, new is CPU-based)

### Risk Mitigation

1. **Flaky tests**: Upper bound of 8 workers prevents excessive parallelism
1. **Shared fixtures**: pytest-xdist handles this via `--dist loadscope`
1. **Resource contention**: Lower bound of 2 ensures some parallelism
1. **CI timeouts**: Explicit `test_workers` in CI config overrides auto-detect

______________________________________________________________________

## Open Questions for Review

1. Should we add a `CRACKERJACK_TEST_WORKERS` environment variable override?
1. Should the upper bound be configurable (e.g., `max_test_workers` setting)?
1. Should we log the selected worker count for debugging?
1. Should we add a `--test-workers` CLI flag for one-off overrides?

______________________________________________________________________

## Testing Plan

```python
# tests/test_test_command_builder.py


def test_optimal_workers_explicit():
    """Explicit worker count is respected."""
    options = MockOptions(test_workers=4)
    assert builder.get_optimal_workers(options) == 4


def test_optimal_workers_auto_detect():
    """Auto-detect uses CPU-based calculation."""
    options = MockOptions(test_workers=0)
    result = builder.get_optimal_workers(options)
    assert 2 <= result <= 8  # Bounded


def test_optimal_workers_fractional():
    """Negative values divide CPU count."""
    options = MockOptions(test_workers=-2)
    cpu_count = multiprocessing.cpu_count()
    expected = max(1, cpu_count // 2)
    assert builder.get_optimal_workers(options) == expected


def test_optimal_workers_no_attribute():
    """Missing test_workers attribute defaults to 2."""
    options = MockOptions()  # No test_workers
    assert builder.get_optimal_workers(options) == 2
```

______________________________________________________________________

## Expected Performance Impact

**Before** (1 worker):

- Test suite: ~60 seconds
- CPU utilization: 12% (1 core active)

**After** (7 workers on 8-core MacBook):

- Test suite: ~15-20 seconds (3-4x faster)
- CPU utilization: 70-80% (7 cores active)

**CI Impact** (4-core GitHub Actions):

- Before: ~45 seconds
- After: ~15-20 seconds (2-3x faster with 3 workers)

______________________________________________________________________

## References

- pytest-xdist docs: https://pytest-xdist.readthedocs.io/
- Current implementation: `crackerjack/managers/test_command_builder.py:26-30`
- Configuration: `settings/crackerjack.yaml:30`
- Related: PHASE-6 parallelization (hooks, not tests)
