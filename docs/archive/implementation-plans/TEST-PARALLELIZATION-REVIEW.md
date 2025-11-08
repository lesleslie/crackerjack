# Test Parallelization Strategies - Pytest Specialist Review

## Executive Summary

**Reviewer**: Pytest & Hypothesis Specialist
**Document**: TEST-PARALLELIZATION-STRATEGIES.md
**Test Suite Size**: ~3,084 tests
**Current Configuration**: pytest-xdist installed, but only 1 worker used
**Overall Assessment**: ⚠️ **Strategy needs refinement** - Good foundation but missing critical pytest-xdist considerations

______________________________________________________________________

## Critical Findings

### 🚨 HIGH PRIORITY ISSUES

#### 1. Missing pytest-xdist Native `-n auto` Discussion

**Issue**: The proposal implements custom CPU detection when pytest-xdist already provides `-n auto`:

```bash
# Native pytest-xdist feature (not discussed in proposal)
pytest -n auto  # Automatically uses CPU count
pytest -n logical  # Uses logical CPU count
```

**Impact**: Reinventing the wheel. pytest-xdist's `-n auto` already handles:

- CPU detection via `os.cpu_count()`
- Safe defaults
- Environment-aware scaling
- Battle-tested logic

**Recommendation**:

- Use `-n auto` as the default when `test_workers=0`
- Only implement custom logic if `-n auto` is insufficient
- Document why custom logic is needed over native pytest-xdist

#### 2. Missing Test Isolation & Fixture Scoping Discussion

**Issue**: With 3,084 tests and extensive DI fixtures (conftest.py has 30+ fixtures), parallel execution will face:

**Shared State Problems**:

```python
# From conftest.py - these fixtures modify global state
@pytest.fixture(autouse=True)
def reset_hook_lock_manager_singleton():
    """Reset HookLockManager singleton before/after each test."""
    HookLockManager._instance = None  # ⚠️ Shared singleton
    HookLockManager._initialized = False
```

**Database/Filesystem Concerns**:

```python
# Tests write to actual filesystem in temp directories
@pytest.fixture
def temp_pkg_path() -> Generator[Path, None, None]:
    """Temporary package path for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)  # ✅ Good - isolated temp dirs
```

**DI Container State**:

```python
# ACB depends system is modified during tests
depends.set(dep_type, dep_value)  # ⚠️ Global DI container
```

**Missing from Proposal**:

- No mention of `--dist` strategies (`loadscope`, `loadfile`, `loadgroup`)
- No discussion of fixture scope impact (session vs function)
- No guidance on avoiding shared state conflicts

**Recommendation**:

```python
# Add to test command builder
def _add_worker_options(self, cmd: list[str], options: OptionsProtocol) -> None:
    workers = self.get_optimal_workers(options)
    if workers > 1:
        cmd.extend(["-n", str(workers)])
        # ✅ CRITICAL: Add distribution strategy
        cmd.append("--dist=loadscope")  # Keeps same-class tests together
        # Alternative strategies:
        # --dist=loadfile  # Keeps tests from same file together (better for DI fixtures)
        # --dist=loadgroup # Requires @pytest.mark.xdist_group decorator
```

#### 3. Coverage Measurement with Parallel Tests

**Issue**: The proposal doesn't mention coverage measurement challenges with xdist.

**Current Configuration** (from pyproject.toml):

```toml
[tool.coverage.run]
parallel = false  # ⚠️ WRONG for xdist!
```

**Problem**: With `pytest-xdist`, each worker generates its own `.coverage` file. Without `parallel = true`, coverage data will be lost or corrupted.

**Required Changes**:

```toml
[tool.coverage.run]
parallel = true  # ✅ REQUIRED for xdist
data_file = ".coverage"  # Base name, workers append suffix

[tool.pytest.ini_options]
addopts = "--cov=crackerjack --cov-report=term-missing --cov-append"
```

**Post-Test Coverage Combination**:

```bash
# After parallel test run
coverage combine  # Merge .coverage.worker* files
coverage report   # Generate unified report
```

**Recommendation**: Update `TestCommandBuilder` to handle coverage combination:

```python
async def run_tests_with_coverage(self):
    """Run tests and combine coverage from parallel workers."""
    # Run tests with xdist
    await self._run_pytest_command()

    # Combine coverage data if parallel
    if self.workers > 1:
        await self._combine_coverage()
```

#### 4. Flaky Test Detection Risk

**Issue**: Parallelization can expose timing-dependent tests that pass serially but fail in parallel.

**From conftest.py** - Complex async fixtures:

```python
@pytest.fixture(scope="session", autouse=True)
def event_loop():  # ⚠️ Async tests may race
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

**Detection Strategy Missing**:

- No mention of `pytest-rerunfailures` for flaky test detection
- No guidance on running tests multiple times to find non-deterministic failures
- No discussion of async test isolation

**Recommendation**:

```bash
# Before enabling parallelization, detect flaky tests
pytest --count=10 -x  # Run each test 10 times, stop on first failure

# After enabling, auto-retry flaky tests
pytest -n auto --reruns 2 --reruns-delay 1  # Retry failed tests twice
```

______________________________________________________________________

## Strategy-Specific Analysis

### Strategy 1: CPU-Based Scaling (Recommended in Proposal)

**Pytest-Specific Concerns**:

✅ **Good**:

- Simple implementation
- Predictable behavior
- Safety bounds prevent resource exhaustion

❌ **Bad**:

- Ignores pytest-xdist's native `-n auto` (why reinvent?)
- No consideration for I/O-bound vs CPU-bound tests
- Hardcoded max=8 may be too conservative for large suites

**Better Alternative**:

```python
def get_optimal_workers(self, options: OptionsProtocol) -> int:
    """Calculate optimal worker count for parallel test execution."""
    if hasattr(options, "test_workers"):
        workers = options.test_workers

        if workers > 0:
            return workers
        elif workers == 0:
            # ✅ Use pytest-xdist native auto-detection
            return "auto"  # Return string "auto" for pytest -n auto
        else:
            # Negative values: custom scaling
            cpu_count = multiprocessing.cpu_count()
            divisor = abs(workers)
            return max(1, cpu_count // divisor)

    return "auto"  # Default to pytest-xdist auto-detection


def _add_worker_options(self, cmd: list[str], options: OptionsProtocol) -> None:
    workers = self.get_optimal_workers(options)

    if workers == "auto":
        cmd.extend(["-n", "auto"])
        cmd.append("--dist=loadfile")  # Keep DI fixtures together
    elif isinstance(workers, int) and workers > 1:
        cmd.extend(["-n", str(workers)])
        cmd.append("--dist=loadfile")
```

**Rationale**: Let pytest-xdist handle CPU detection (it's better at it), use our custom logic only for fractional workers.

### Strategy 2: Environment-Aware Detection

**Pytest-Specific Concerns**:

❌ **Problematic**:

- CI detection (`os.getenv("CI")`) is fragile
- Docker detection (`os.path.exists("/.dockerenv")`) unreliable
- Heuristics conflict with pytest-xdist's `-n auto` logic

**Better Approach**: Use pytest-xdist environment variables instead:

```bash
# In CI
export PYTEST_XDIST_WORKER_COUNT=4

# In pytest-xdist
pytest -n $PYTEST_XDIST_WORKER_COUNT
```

**Recommendation**: **Reject this strategy** - too complex, unreliable, and conflicts with pytest-xdist best practices.

### Strategy 3: Load-Based Scaling

**Pytest-Specific Concerns**:

❌ **Rejected**:

- Non-deterministic (violates pytest philosophy)
- Adds psutil overhead on every test run
- Makes debugging impossible ("works on my machine" syndrome)

**Recommendation**: **Do not implement** - breaks pytest's deterministic execution model.

### Strategy 4: Test-Suite-Aware Scaling

**Pytest-Specific Concerns**:

⚠️ **Mixed**:

- Reasonable idea (small suites don't benefit from parallelization)
- Implementation is naive (counting `def test_` misses parametrization)

**Better Implementation**:

```python
def _should_parallelize(self, pkg_path: Path) -> bool:
    """Determine if test suite is large enough to benefit from parallelization."""
    # Use pytest collection API instead of text parsing
    import subprocess

    result = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=pkg_path,
    )

    # Count actual test items (includes parametrized tests)
    test_count = len([line for line in result.stdout.split("\n") if "::" in line])

    return test_count >= 50  # Threshold for parallelization
```

**However**: With 3,084 tests, this project **always** benefits from parallelization. This strategy is **not needed**.

______________________________________________________________________

## Missing Pytest-Specific Considerations

### 1. Fixture Scope and Parallelization

**Problem**: Session-scoped fixtures run once per worker, not once globally.

**From conftest.py**:

```python
@contextmanager
def acb_depends_context(injection_map: dict[type, Any]):
    """Context manager for setting up ACB dependency injection in tests."""
    # ⚠️ This modifies global `depends` container
    depends.set(dep_type, dep_value)
```

**With xdist**: Each worker has its own Python process, so:

- ✅ Good: DI modifications are isolated per worker (no race conditions)
- ⚠️ Concern: Session fixtures run N times (once per worker)

**Recommendation**: Use `pytest-xdist` session fixtures carefully:

```python
# For truly shared resources (databases, etc.)
@pytest.fixture(scope="session")
def database_connection(tmp_path_factory, worker_id):
    """Session fixture that works with xdist."""
    if worker_id == "master":
        # Not executing in a worker, no special handling needed
        path = tmp_path_factory.mktemp("data")
    else:
        # Worker-specific temp directory
        root_tmp_dir = tmp_path_factory.getbasetemp().parent
        path = root_tmp_dir / f"data-{worker_id}"
        path.mkdir(exist_ok=True)

    # Each worker gets its own database
    return create_database(path)
```

### 2. Test Markers for Parallel Control

**Missing**: No discussion of test markers to control parallelization.

**Recommendation**: Add markers for serial-only tests:

```python
# In conftest.py
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "serial: mark test to run serially (not in parallel)"
    )


def pytest_collection_modifyitems(config, items):
    """Add xdist_group marker to serial tests."""
    for item in items:
        if "serial" in item.keywords:
            item.add_marker(pytest.mark.xdist_group(name="serial"))
```

**Usage**:

```python
@pytest.mark.serial
def test_modifies_global_state():
    """Tests that must run serially."""
    pass
```

### 3. Pytest-Benchmark Integration

**From pyproject.toml**:

```toml
[tool.pytest.benchmark]
disable_gc = true
warmup = false
```

**Issue**: Benchmarks should **never** run in parallel (results will be skewed).

**Recommendation**:

```python
def _add_worker_options(self, cmd: list[str], options: OptionsProtocol) -> None:
    # ✅ Disable parallelization for benchmarks
    if hasattr(options, "benchmark") and options.benchmark:
        return  # No -n flag for benchmarks

    workers = self.get_optimal_workers(options)
    if workers > 1:
        cmd.extend(["-n", str(workers)])
        cmd.append("--dist=loadfile")
```

### 4. Test Execution Time Analysis

**Missing**: No way to identify slow tests that bottleneck parallelization.

**Recommendation**: Add `--durations` flag:

```python
def _add_verbosity_options(self, cmd: list[str], options: OptionsProtocol) -> None:
    cmd.append("-v")
    cmd.extend(["--tb=short", "--strict-markers", "--strict-config"])

    # ✅ Show 10 slowest tests
    cmd.append("--durations=10")
```

**Why**: With `--dist=loadscope`, if one test class has a 60-second test, it will block that worker.

______________________________________________________________________

## Proposed Unit Tests - Quality Assessment

**From Proposal**:

```python
def test_optimal_workers_auto_detect():
    """Auto-detect uses CPU-based calculation."""
    options = MockOptions(test_workers=0)
    result = builder.get_optimal_workers(options)
    assert 2 <= result <= 8  # Bounded
```

**Issues**:

1. **Too Vague**: `assert 2 <= result <= 8` doesn't validate the actual logic
1. **Missing Edge Cases**: What about 1-core systems? 128-core servers?
1. **No pytest-xdist Integration Tests**: Doesn't test actual parallel execution

**Better Test Suite**:

```python
import multiprocessing
import pytest
from unittest.mock import patch, MagicMock


class TestWorkerCalculation:
    """Test worker count calculation logic."""

    def test_explicit_worker_count_respected(self):
        """Explicit worker count should be returned as-is."""
        options = MockOptions(test_workers=4)
        assert builder.get_optimal_workers(options) == 4

    def test_auto_detect_returns_auto_string(self):
        """Auto-detect should return 'auto' for pytest-xdist."""
        options = MockOptions(test_workers=0)
        assert builder.get_optimal_workers(options) == "auto"

    def test_fractional_workers_on_8_core(self):
        """Negative values divide CPU count correctly."""
        with patch("multiprocessing.cpu_count", return_value=8):
            options = MockOptions(test_workers=-2)
            assert builder.get_optimal_workers(options) == 4  # 8 / 2

    def test_fractional_workers_minimum_1(self):
        """Fractional workers never go below 1."""
        with patch("multiprocessing.cpu_count", return_value=2):
            options = MockOptions(test_workers=-4)
            assert builder.get_optimal_workers(options) == 1  # max(1, 2//4)

    def test_no_attribute_defaults_to_auto(self):
        """Missing test_workers attribute defaults to auto."""
        options = MockOptions()  # No test_workers attribute
        assert builder.get_optimal_workers(options) == "auto"


class TestCommandBuilding:
    """Test pytest command construction with workers."""

    def test_auto_workers_adds_n_auto(self):
        """Auto worker detection adds '-n auto' to command."""
        options = MockOptions(test_workers=0)
        cmd = builder.build_command(options)

        assert "-n" in cmd
        assert "auto" in cmd[cmd.index("-n") + 1]
        assert "--dist=loadfile" in cmd  # Distribution strategy

    def test_explicit_workers_adds_n_count(self):
        """Explicit worker count adds '-n <count>'."""
        options = MockOptions(test_workers=4)
        cmd = builder.build_command(options)

        assert "-n" in cmd
        assert "4" == cmd[cmd.index("-n") + 1]

    def test_single_worker_omits_n_flag(self):
        """Single worker should not add -n flag."""
        options = MockOptions(test_workers=1)
        cmd = builder.build_command(options)

        assert "-n" not in cmd

    def test_benchmark_mode_disables_parallelization(self):
        """Benchmark mode should run serially."""
        options = MockOptions(test_workers=4, benchmark=True)
        cmd = builder.build_command(options)

        # Should have benchmark flags but NO -n flag
        assert "--benchmark-only" in cmd
        assert "-n" not in cmd


@pytest.mark.integration
class TestActualParallelExecution:
    """Integration tests for actual parallel test execution."""

    def test_parallel_execution_faster_than_serial(self, tmp_path):
        """Parallel execution should be faster for large test suites."""
        import subprocess
        import time

        # Create a project with 100 slow tests
        test_file = tmp_path / "test_slow.py"
        test_file.write_text("""
import time
import pytest

@pytest.mark.parametrize("i", range(100))
def test_slow(i):
    time.sleep(0.1)  # 100 * 0.1s = 10s total
""")

        # Serial execution
        start = time.time()
        subprocess.run(["pytest", "-n", "1"], cwd=tmp_path, check=True)
        serial_time = time.time() - start

        # Parallel execution
        start = time.time()
        subprocess.run(["pytest", "-n", "auto"], cwd=tmp_path, check=True)
        parallel_time = time.time() - start

        # Parallel should be at least 2x faster (conservative)
        assert parallel_time < serial_time / 2

    def test_parallel_coverage_merges_correctly(self, tmp_path):
        """Coverage data should merge correctly from multiple workers."""
        # This test would verify coverage.py parallel mode
        # Implementation depends on coverage workflow
        pass
```

______________________________________________________________________

## Recommended Implementation Plan

### Phase 1: Foundation (Week 1)

1. **Update pyproject.toml**:

```toml
[tool.coverage.run]
parallel = true  # ✅ Required for xdist
```

2. **Update TestCommandBuilder**:

```python
def get_optimal_workers(self, options: OptionsProtocol) -> str | int:
    """Return 'auto' or explicit worker count."""
    if hasattr(options, "test_workers"):
        workers = options.test_workers

        if workers > 0:
            return workers
        elif workers == 0:
            return "auto"  # Use pytest-xdist auto-detection
        else:
            # Fractional workers
            cpu_count = multiprocessing.cpu_count()
            return max(1, cpu_count // abs(workers))

    return "auto"


def _add_worker_options(self, cmd: list[str], options: OptionsProtocol) -> None:
    # Skip for benchmarks
    if hasattr(options, "benchmark") and options.benchmark:
        return

    workers = self.get_optimal_workers(options)

    if workers == "auto":
        cmd.extend(["-n", "auto", "--dist=loadfile"])
    elif isinstance(workers, int) and workers > 1:
        cmd.extend(["-n", str(workers), "--dist=loadfile"])
```

3. **Add test markers**:

```python
# In conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "serial: mark test to run serially")
```

### Phase 2: Validation (Week 2)

1. **Run flaky test detection**:

```bash
pytest --count=10 -x -m "not slow"  # Fast tests only
```

2. **Compare results**:

```bash
# Baseline (serial)
pytest -n 1 --duration=20  # Show 20 slowest tests

# Parallel
pytest -n auto --duration=20

# Compare coverage
coverage report --show-missing
```

3. **Fix any flaky tests** exposed by parallelization

### Phase 3: Optimization (Week 3)

1. **Identify bottlenecks**:

```bash
pytest -n auto --durations=0 > timings.txt
# Analyze timings.txt for slow tests
```

2. **Consider test splitting**:

```python
# For very slow test classes
@pytest.mark.xdist_group(name="slow_integration")
class TestSlowIntegration:
    """Tests that should run on dedicated worker."""

    pass
```

3. **Monitor CI performance**:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: python -m crackerjack --run-tests
  env:
    PYTEST_XDIST_WORKER_COUNT: 4  # Explicit for CI
```

______________________________________________________________________

## Risk Mitigation

### High Risk: Test Flakiness

**Likelihood**: High (3,084 tests, async fixtures, DI container)
**Impact**: High (CI failures, false positives)

**Mitigation**:

1. Use `pytest-rerunfailures` plugin:

```bash
pytest -n auto --reruns 2 --reruns-delay 1
```

2. Add flaky test detection to CI:

```yaml
- name: Detect flaky tests
  run: pytest --count=5 -x  # Run each test 5 times
  continue-on-error: true  # Don't block builds
```

### Medium Risk: Coverage Data Loss

**Likelihood**: Medium (requires config change)
**Impact**: High (no coverage reports)

**Mitigation**:

1. Enable `parallel = true` in coverage config
1. Add coverage combine step:

```python
async def _combine_coverage(self):
    """Combine coverage data from parallel workers."""
    import subprocess

    subprocess.run(["coverage", "combine"], check=True)
```

### Low Risk: Shared Resource Conflicts

**Likelihood**: Low (temp directories are isolated)
**Impact**: Medium (test failures)

**Mitigation**:

1. Use `--dist=loadfile` to keep tests from same file together
1. Review singleton patterns (e.g., `HookLockManager`)
1. Consider worker-specific temp directories:

```python
@pytest.fixture
def worker_temp_dir(tmp_path_factory, worker_id):
    """Worker-specific temp directory."""
    if worker_id == "master":
        return tmp_path_factory.mktemp("data")

    base = tmp_path_factory.getbasetemp().parent
    path = base / f"data-{worker_id}"
    path.mkdir(exist_ok=True)
    return path
```

______________________________________________________________________

## Expected Performance Impact (Revised)

**Before** (1 worker):

- Test suite: ~60 seconds (estimated)
- CPU utilization: 12% (1 core active)

**After** (pytest -n auto on 8-core MacBook):

- Test suite: ~10-15 seconds (4-6x faster, accounting for overhead)
- CPU utilization: 70-80% (7-8 cores active)
- **Caveat**: Assumes no serialization bottlenecks

**CI Impact** (4-core GitHub Actions):

- Before: ~45 seconds (estimated)
- After: ~12-15 seconds (3x faster with 3-4 workers)
- **Caveat**: CI may have I/O limits

______________________________________________________________________

## Open Questions for Implementation

1. **Should we use `-n auto` or custom CPU detection?**

   - **Recommendation**: Use `-n auto` by default
   - Custom logic only for fractional workers (test_workers < 0)

1. **What distribution strategy should we use?**

   - **Recommendation**: `--dist=loadfile` (keeps DI fixtures together)
   - Alternative: `--dist=loadscope` (keeps test classes together)

1. **How should we handle coverage merging?**

   - **Recommendation**: Automatic `coverage combine` in TestManager
   - Add to post-test cleanup phase

1. **Should we add flaky test detection?**

   - **Recommendation**: Yes, as optional `--detect-flaky` flag
   - Runs tests multiple times to find non-deterministic failures

1. **What about benchmark tests?**

   - **Recommendation**: Always disable parallelization for benchmarks
   - Add to `_add_worker_options` logic

______________________________________________________________________

## Summary

**Verdict**: Strategy 1 (CPU-Based) is a reasonable starting point, but **use pytest-xdist's `-n auto` instead of custom CPU detection**.

**Critical Missing Pieces**:

1. ❌ No discussion of `-n auto` (the most important feature!)
1. ❌ No coverage parallel mode configuration
1. ❌ No test isolation/fixture scope considerations
1. ❌ No distribution strategy (`--dist`) discussion
1. ❌ No flaky test detection plan

**Recommended Changes**:

1. ✅ Use `-n auto` as default for `test_workers=0`
1. ✅ Enable `parallel = true` in coverage config
1. ✅ Add `--dist=loadfile` to keep DI fixtures isolated
1. ✅ Disable parallelization for benchmarks
1. ✅ Add comprehensive unit and integration tests
1. ✅ Include flaky test detection in testing plan

**Complexity Recommendation**: Start with `-n auto` and `--dist=loadfile`. Only add custom logic if pytest-xdist's auto-detection is insufficient.

______________________________________________________________________

## References

- pytest-xdist docs: https://pytest-xdist.readthedocs.io/
- Coverage.py parallel mode: https://coverage.readthedocs.io/en/latest/cmd.html#combining-data-files
- pytest fixtures and xdist: https://pytest-xdist.readthedocs.io/en/latest/known-limitations.html
- Flaky test detection: https://github.com/pytest-dev/pytest-rerunfailures
