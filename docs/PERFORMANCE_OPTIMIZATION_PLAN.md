# Performance Optimization Plan: BatchProcessor

**Date**: 2026-02-05
**Status**: Analysis Complete, Implementation Pending
**Baseline**: 61.8s for 5 issues (~12.4s per issue)

---

## Executive Summary

Profiling reveals **I/O wait is the primary bottleneck**, consuming 89% of execution time (55.2s out of 62s total). The async architecture is not providing benefits because agents perform blocking file operations.

**Target**: Reduce from 12.4s per issue to <3s per issue (4x speedup)
**Target**: Process 10 issues in <30s (currently ~120s estimated)

---

## Profiling Results Summary

### Baseline Performance (5 issues, parallel)

| Metric | Value | Percentage |
|--------|-------|------------|
| **Total Duration** | 62.0s | 100% |
| **I/O Wait (select.kqueue)** | 55.2s | 89% |
| **Agent Processing** | 6.9s | 11% |
| **Event Loop Overhead** | Minimal | <1% |

### Per-Agent Breakdown

| Agent | Duration | Issues | Avg per Issue |
|-------|----------|--------|---------------|
| ImportOptimizationAgent | ~2s | 2 | 1.0s |
| TestSpecialistAgent | ~2s | 1 | 2.0s |
| TestCreationAgent | 6.9s | 1 | 6.9s |
| DependencyAgent | Failed | 1 | N/A |

**Key Insight**: TestCreationAgent is 7x slower than other agents (pytest discovery overhead)

---

## Bottleneck Analysis

### 1. I/O Wait Dominance (CRITICAL)

**Problem**: 89% of time spent in `select.kqueue` waiting for file I/O

**Root Causes**:
- Agents use `Path.read_text()` and `Path.write_text()` (blocking I/O)
- File operations not truly async despite async wrapper
- Each agent does multiple file reads/writes per issue

**Evidence**:
```
235   55.187    0.235   55.187    0.235 {method 'control' of 'select.kqueue' objects}
```

**Impact**: Prevents parallelization benefits - 5 issues in parallel should be ~5x faster, but we're only getting ~2x

### 2. TestCreationAgent Slowness (HIGH)

**Problem**: 6.9s for one issue (11% of total time)

**Root Cause**: Pytest discovery is expensive
- TestCreationAgent calls pytest for analysis
- Pytest discovery overhead is high
- Not cached across issues

**Evidence**:
```
1    0.000    0.000    6.903    6.903 test_creation_agent.py:148(analyze_and_fix)
1    0.000    0.000    6.768    6.768 test_creation_agent.py:529(_find_untested_functions)
```

### 3. Agent Initialization (MEDIUM)

**Problem**: Lazy loading causes repeated imports

**Current Behavior**:
- Each agent imported on first use
- Import overhead not significant compared to I/O, but adds up

**Impact**: Minor (<100ms per agent), but easy to fix

### 4. Sequential Fix Application (MEDIUM)

**Problem**: TestCreationAgent applies fixes sequentially

**Current Behavior**:
```python
async def _apply_all_fix_types_in_sequence(self, ...) -> None:
    # Calls each fix type one by one
```

**Impact**: Could parallelize independent fix types

---

## Optimization Strategy

### Phase 1: Critical I/O Optimizations (Target: 3x speedup)

#### 1.1 Implement Async File I/O Pool

**Current** (blocking):
```python
content = Path(file_path).read_text()
Path(file_path).write_text(new_content)
```

**Optimized** (async thread pool):
```python
from concurrent.futures import ThreadPoolExecutor
from functools import partial

async def async_read_file(file_path: Path) -> str:
    """Read file asynchronously using thread pool."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return await loop.run_in_executor(pool, file_path.read_text)

async def async_write_file(file_path: Path, content: str) -> None:
    """Write file asynchronously using thread pool."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        await loop.run_in_executor(pool, partial(file_path.write_text, content))
```

**Implementation**: Add to `AgentContext` as `async_get_file_content()` and `async_write_file_content()`

**Expected Impact**: 2-3x speedup (I/O no longer blocks event loop)

#### 1.2 Batch File Operations

**Concept**: Group file operations and execute in parallel

**Implementation**:
```python
async def batch_read_files(file_paths: list[Path]) -> dict[Path, str]:
    """Read multiple files in parallel."""
    tasks = [async_read_file(fp) for fp in file_paths]
    contents = await asyncio.gather(*tasks)
    return dict(zip(file_paths, contents))
```

**Expected Impact**: Additional 1.2x speedup for multi-file operations

### Phase 2: Agent-Specific Optimizations (Target: 2x speedup)

#### 2.1 Cache Pytest Discovery Results

**Problem**: TestCreationAgent calls pytest for each issue

**Solution**: Cache test discovery results
```python
@lru_cache(maxsize=128)
def _get_pytest_tests(project_path: str) -> set[str]:
    """Cache pytest test discovery."""
    # Run pytest --collect-only once
    # Return set of test node IDs
```

**Expected Impact**: TestCreationAgent: 6.9s → 1s (7x speedup for this agent)

#### 2.2 Pre-Initialize Common Agents

**Current**: Lazy loading
```python
if agent_name not in self._agents:
    from crackerjack.agents.xxx import XXXAgent
    self._agents[agent_name] = XXXAgent(self.context)
```

**Optimized**: Eager load top 3 agents
```python
def __init__(self, ...):
    # Pre-load common agents
    self._get_agent("ImportOptimizationAgent")  # Most common
    self._get_agent("FormattingAgent")           # Common
    self._get_agent("TestSpecialistAgent")       # Common
```

**Expected Impact**: Minimal (<100ms total), but improves perceived responsiveness

### Phase 3: Advanced Optimizations (Target: 1.5x speedup)

#### 3.1 Parallel Fix Application

**Current**: Sequential fix application in TestCreationAgent
**Optimized**: Parallel independent fixes

```python
async def _apply_fixes_parallel(self, ...) -> None:
    """Apply independent fix types in parallel."""
    tasks = [
        self._add_imports(),
        self._create_fixtures(),
        self._update_config(),
    ]
    await asyncio.gather(*tasks)
```

**Expected Impact**: 1.5x speedup for TestCreationAgent

#### 3.2 Streaming Results (Optional)

**Concept**: Return results as they complete instead of waiting for all

**Implementation**:
```python
async def process_batch_streaming(
    self,
    issues: list[Issue],
) -> AsyncIterator[BatchIssueResult]:
    """Process issues and yield results as they complete."""
    tasks = [self._process_single_issue(issue) for issue in issues]
    for task in asyncio.as_completed(tasks):
        yield await task
```

**Expected Impact**: Better perceived performance, no actual speedup

---

## Implementation Priority

### Week 7: Critical Optimizations (P0)

1. ✅ **Fix DependencyAgent** (COMPLETE)
   - Added to BatchProcessor._get_agent()

2. **Implement Async File I/O** (HIGH PRIORITY)
   - Add `async_read_file()` and `async_write_file()` utilities
   - Update AgentContext to use async I/O
   - Update all agents to use async I/O
   - **Expected Impact**: 2-3x speedup

3. **Cache Pytest Discovery** (HIGH PRIORITY)
   - Implement `_get_pytest_tests()` with LRU cache
   - Update TestCreationAgent to use cache
   - **Expected Impact**: TestCreationAgent 6.9s → 1s

### Week 8: Polish Optimizations (P1)

4. **Pre-Initialize Common Agents** (MEDIUM PRIORITY)
   - Eager load top 3 agents in BatchProcessor.__init__()
   - **Expected Impact**: Minor improvement in responsiveness

5. **Parallel Fix Application** (MEDIUM PRIORITY)
   - Update TestCreationAgent to apply fixes in parallel
   - **Expected Impact**: 1.5x speedup for TestCreationAgent

6. **Performance Validation** (REQUIRED)
   - Re-run profiling after optimizations
   - Measure actual improvement
   - Target: <30s for 10 issues

---

## Expected Performance Improvements

### Before Optimization (Baseline)

| Metric | Value |
|--------|-------|
| 5 issues | 62s |
| Per issue | 12.4s |
| 10 issues (est.) | ~124s |

### After Phase 1 Optimizations (Expected)

| Metric | Value | Improvement |
|--------|-------|-------------|
| 5 issues | ~20s | 3x faster |
| Per issue | 4s | 3x faster |
| 10 issues (est.) | ~40s | 3x faster |

### After All Optimizations (Target)

| Metric | Value | Improvement |
|--------|-------|-------------|
| 5 issues | ~15s | 4x faster |
| Per issue | 3s | 4x faster |
| 10 issues (est.) | ~30s | 4x faster |

---

## Success Criteria

### Performance Targets

- [ ] **Per-issue time**: <3s (currently 12.4s) - 4x improvement
- [ ] **10 issues**: <30s (currently ~124s estimated) - 4x improvement
- [ ] **I/O wait percentage**: <50% (currently 89%) - 2x improvement
- [ ] **TestCreationAgent**: <1s per issue (currently 6.9s) - 7x improvement

### Quality Gates

- [ ] All fast hooks passing (16/16)
- [ ] No regressions in agent functionality
- [ ] Batch processing still 100% success rate on validation tests

---

## Alternative Approaches Considered

### Option A: Process Pool (Rejected)

**Idea**: Use `ProcessPoolExecutor` for CPU-bound work

**Rejected Because**:
- Most work is I/O bound, not CPU bound
- Process spawning overhead is high
- IPC complexity not worth it

### Option B: Rewrite Agents in Rust (Rejected)

**Idea**: Port agents to Rust for performance

**Rejected Because**:
- Development time too long (weeks/months)
- Current bottleneck is I/O, not agent logic
- Would require major architecture changes

### Option C: Reduce Agent Functionality (Rejected)

**Idea**: Simplify agents to reduce work

**Rejected Because**:
- Would reduce fix quality/success rate
- Not a performance optimization, just doing less work
- Against project goals

---

## Risks & Mitigations

### Risk 1: Async I/O Breaking Changes

**Risk**: Converting to async I/O might break existing code

**Mitigation**:
- Keep synchronous methods as fallback
- Comprehensive testing after conversion
- Run on real test failures before deploying

### Risk 2: Cache Invalidation

**Risk**: Pytest cache might become stale

**Mitigation**:
- Invalidate cache when files change
- Add TTL to cache entries
- Provide cache clearing mechanism

### Risk 3: Thread Pool Exhaustion

**Risk**: Too many async I/O operations might exhaust thread pool

**Mitigation**:
- Limit ThreadPoolExecutor size
- Use semaphores to limit concurrency
- Monitor thread pool usage

---

## Implementation Timeline

### Week 7: Critical Optimizations

- **Day 1-2**: Async file I/O implementation
- **Day 3**: Pytest caching
- **Day 4**: Testing and validation
- **Day 5**: Performance measurement

### Week 8: Polish & Documentation

- **Day 1**: Pre-initialize agents
- **Day 2**: Parallel fix application
- **Day 3**: Comprehensive testing
- **Day 4**: Documentation updates
- **Day 5**: Final validation

---

## Monitoring & Metrics

### Key Metrics to Track

1. **Per-issue processing time**
   - Measure: Average time per issue
   - Target: <3s
   - Frequency: Every batch

2. **I/O wait percentage**
   - Measure: profiler `select.kqueue` time / total time
   - Target: <50%
   - Frequency: Weekly profiling

3. **Agent-specific performance**
   - Measure: Duration per agent type
   - Target: TestCreationAgent <1s
   - Frequency: Every batch

4. **Success rate**
   - Measure: % of issues fixed successfully
   - Target: ≥80%
   - Frequency: Every batch

---

## Next Steps

1. ✅ DependencyAgent fix (COMPLETE)
2. **Implement async file I/O utilities** (NEXT)
3. Update AgentContext with async methods
4. Update BatchProcessor to use async I/O
5. Implement pytest discovery caching
6. Re-profile and measure improvement
7. Update documentation

---

**Status**: Ready to begin Phase 1 implementation
**Next Action**: Implement async file I/O utilities
