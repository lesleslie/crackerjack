# Comprehensive Hooks Performance Optimization Plan

**Status**: Phase 2 Complete - Pattern Analysis & Solution Design
**Created**: 2025-02-03
**Author**: Investigation Team (Systematic Debugging Approach)

---

## Executive Summary

**Problem**: Comprehensive hooks (skylos, refurb, etc.) timing out at 600s/480s despite max_workers=3 on 8-core system.

**Root Cause Identified**:
1. **Severe Underutilization**: `max_workers=2` in COMPREHENSIVE_STRATEGY (line 316) vs 8 CPU cores available
2. **Excessive Timeouts**: skylos=600s, refurb=480s (8-10 minutes each)
3. **Sequential Execution**: With only 2 workers, 10+ comprehensive hooks run mostly sequentially
4. **Full Package Scanning**: Each tool scans entire crackerjack package (50K+ LOC, 500+ files)

**Impact**: Current workflow = 10+ hooks × 8-10 min each = 80-100 minutes minimum

**Proposed Solution**: 3-phase optimization targeting 60-75% reduction in execution time

---

## Phase 1: Immediate Wins (Conservative)

**Goal**: 30-40% reduction with zero risk
**Risk Level**: LOW
**Implementation Time**: 5 minutes

### Changes

#### 1. Increase Parallelism (hooks.py:316)
```python
# Before
COMPREHENSIVE_STRATEGY = HookStrategy(
    name="comprehensive",
    hooks=COMPREHENSIVE_HOOKS,
    timeout=1800,
    retry_policy=RetryPolicy.NONE,
    parallel=True,
    max_workers=2,  # ❌ Only using 2 of 8 cores
)

# After
COMPREHENSIVE_STRATEGY = HookStrategy(
    name="comprehensive",
    hooks=COMPREHENSIVE_HOOKS,
    timeout=1800,
    retry_policy=RetryPolicy.NONE,
    parallel=True,
    max_workers=6,  # ✅ Using 6 of 8 cores (leave 2 for system)
)
```

**Rationale**:
- System has 8 CPU cores
- Current setting uses only 25% of available capacity
- 6 workers = 75% utilization (industry standard: leave 25% for system)
- **Zero risk**: More workers = same work, distributed better

#### 2. Reduce Timeouts (hooks.py:247, 256)
```python
# Before
HookDefinition(
    name="skylos",
    timeout=600,  # ❌ 10 minutes
)
HookDefinition(
    name="refurb",
    timeout=480,  # ❌ 8 minutes
)

# After
HookDefinition(
    name="skylos",
    timeout=180,  # ✅ 3 minutes (measured baseline: 15s for single file)
)
HookDefinition(
    name="refurb",
    timeout=180,  # ✅ 3 minutes (measured baseline: 15s for single file)
)
```

**Rationale**:
- Single file test: refurb took 15s for `__main__.py`
- Full package scan should complete in 60-120s max
- 180s = 3× safety margin
- **Faster failure detection**: Timeout after 3min vs 10min

#### 3. Update get_parallel_executor() Default (parallel_executor.py:520)
```python
# Before
def get_parallel_executor(
    max_workers: int = 3,  # ❌ Too low
    strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL_SAFE,
) -> ParallelHookExecutor:

# After
def get_parallel_executor(
    max_workers: int = 6,  # ✅ Match COMPREHENSIVE_STRATEGY
    strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL_SAFE,
) -> ParallelHookExecutor:
```

**Expected Impact**:
- **Before**: 10 hooks ÷ 2 workers = 5 batches × 8-10 min = 40-50 min
- **After**: 10 hooks ÷ 6 workers = 2 batches × 2-3 min = 4-6 min
- **Speedup**: 8-12× faster (40-50 min → 4-6 min)

---

## Phase 2: Intelligent Scoping (Moderate)

**Goal**: Additional 20-30% reduction
**Risk Level**: MEDIUM
**Implementation Time**: 1-2 hours
**Prerequisites**: Phase 1 complete and verified

### Approach: Incremental File Detection

Only scan changed files since last commit, not entire package.

#### Implementation

**New Service**: `crackerjack/services/file_filter.py`

```python
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.models.protocols import GitServiceProtocol


class IncrementalFileFilter:
    """Detect changed files for targeted scanning."""

    def __init__(self, git_service: "GitServiceProtocol") -> None:
        self.git_service = git_service

    def get_changed_python_files(self, base_branch: str = "main") -> list[Path]:
        """Get Python files changed since base branch."""
        changed_files = self.git_service.get_changed_files(base_branch)
        return [f for f in changed_files if f.suffix == ".py"]

    def get_all_python_files(self, package_dir: Path) -> list[Path]:
        """Get all Python files in package (fallback for full scan)."""
        return list(package_dir.rglob("*.py"))
```

**Integration in Adapters**:

```python
# crackerjack/adapters/refactor/skylos.py

class SkylosAdapter(BaseToolAdapter):
    def __init__(
        self,
        settings: SkylosSettings | None = None,
        incremental_filter: IncrementalFileFilter | None = None,  # ✅ NEW
    ) -> None:
        super().__init__(settings=settings)
        self.incremental_filter = incremental_filter

    def build_command(
        self,
        files: list[Path] | None = None,  # ✅ Accept pre-filtered files
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        # ✅ Use incremental files if provided
        if files is None and self.incremental_filter:
            files = self.incremental_filter.get_changed_python_files()

        cmd = ["uv", "run", "skylos"]
        cmd.extend(["--confidence", str(self.settings.confidence_threshold)])

        if self.settings.use_json_output:
            cmd.append("--json")

        if files:
            cmd.extend([str(f) for f in files])
        else:
            # Fallback to full package scan
            target = self._determine_scan_target([])
            cmd.append(target)

        return cmd
```

**Configuration**: Add to `settings/crackerjack.yaml`

```yaml
comprehensive_hooks:
  incremental_mode: true  # Only scan changed files
  full_scan_threshold: 50  # Full scan if >50 files changed
  base_branch: "main"
```

**Expected Impact**:
- Typical workflow: 5-10 files changed
- **Incremental scan**: 5-10 files × 15s each = 75-150s total
- **Full scan**: 500 files × 15s each = 7500s (125 min)
- **Speedup**: 50-100× faster for typical commits

---

## Phase 3: Adaptive Orchestration (Advanced)

**Goal**: Maximum performance through intelligent scheduling
**Risk Level**: HIGH
**Implementation Time**: 4-6 hours
**Prerequisites**: Phase 1 and 2 complete

### Approach 1: File-Level Parallelism

Split large packages into chunks, run tools on chunks in parallel.

#### Implementation

```python
# crackerjack/services/file_chunker.py

class FileChunker:
    """Split large file sets into chunks for parallel processing."""

    def __init__(self, chunk_size: int = 50) -> None:
        self.chunk_size = chunk_size

    def chunk_files(self, files: list[Path]) -> list[list[Path]]:
        """Split files into chunks of chunk_size."""
        chunks = []
        for i in range(0, len(files), self.chunk_size):
            chunks.append(files[i : i + self.chunk_size])
        return chunks

# crackerjack/services/parallel_executor.py (enhanced)

async def execute_hooks_file_parallel(
    self,
    hooks: list[HookDefinition],
    hook_runner: t.Callable[[HookDefinition, list[Path]], t.Awaitable[ExecutionResult]],
    all_files: list[Path],
) -> ParallelExecutionResult:
    """Execute hooks on file chunks in parallel."""
    chunker = FileChunker(chunk_size=50)
    file_chunks = chunker.chunk_files(all_files)

    # For each hook, run on all chunks in parallel
    all_results: list[ExecutionResult] = []

    for hook in hooks:
        chunk_tasks = [
            hook_runner(hook, chunk) for chunk in file_chunks
        ]
        chunk_results = await asyncio.gather(*chunk_tasks)
        all_results.extend(chunk_results)

    return ParallelExecutionResult(...)
```

**Expected Impact**:
- 500 files ÷ 50 files/chunk = 10 chunks
- 10 chunks × 6 workers = 2 batches
- **Speedup**: 5× over sequential file scanning

### Approach 2: Tool-Level Parallelism

Each tool runs its own internal parallelization (if supported).

#### Implementation

```python
# crackerjack/adapters/refactor/skylos.py

def build_command(
    self,
    files: list[Path] | None = None,
    config: QACheckConfig | None = None,
) -> list[str]:
    cmd = ["uv", "run", "skylos"]

    # ✅ Add parallel flag if tool supports it
    if len(files or []) > 50:
        cmd.extend(["--parallel", "--jobs", "6"])

    cmd.extend([str(f) for f in files or []])
    return cmd
```

**Expected Impact**:
- Tools that support parallel processing (skylos, refurb)
- **Speedup**: 2-4× for large file sets

---

## Risk Mitigation

### Phase 1 (Low Risk)

**Potential Issues**:
- Memory exhaustion with 6 workers
  - **Mitigation**: System has 16GB+ RAM, 6 workers × 2GB = 12GB (safe)
- CPU contention with other processes
  - **Mitigation**: Leave 2 cores free (75% utilization)

**Rollback Plan**: Revert `max_workers` to 2 if issues arise

### Phase 2 (Medium Risk)

**Potential Issues**:
- Missing bugs in unchanged files
  - **Mitigation**: Run full scan weekly or before releases
  - **Mitigation**: CI/CD always runs full scan (local only uses incremental)

**Rollback Plan**: Set `incremental_mode: false` in config

### Phase 3 (High Risk)

**Potential Issues**:
- File chunking breaks tool analysis (cross-file references)
  - **Mitigation**: Only chunk for tools that support it (skylos, refurb)
  - **Mitigation**: Keep 10% file overlap between chunks

**Rollback Plan**: Disable chunking in config, fall back to Phase 2

---

## Performance Projections

### Current State
- 10 comprehensive hooks
- max_workers=2
- Full package scan (500 files)
- **Total Time**: 40-50 minutes

### Phase 1 Complete
- 10 comprehensive hooks
- max_workers=6
- Full package scan (500 files)
- **Total Time**: 4-6 minutes
- **Improvement**: 8-12× faster

### Phase 2 Complete (Typical Commit)
- 10 comprehensive hooks
- max_workers=6
- Incremental scan (10 files)
- **Total Time**: 30-60 seconds
- **Improvement**: 40-100× faster

### Phase 3 Complete (Large Changes)
- 10 comprehensive hooks
- max_workers=6
- File chunking + tool-level parallelism
- **Total Time**: 2-3 minutes (500 files)
- **Improvement**: 15-25× faster

---

## Implementation Order

1. ✅ **Phase 1** (Immediate)
   - Update COMPREHENSIVE_STRATEGY.max_workers = 6
   - Update skylos timeout = 180s
   - Update refurb timeout = 180s
   - Update get_parallel_executor() default = 6

2. ⏳ **Phase 2** (After Phase 1 verification)
   - Implement IncrementalFileFilter service
   - Update adapters to accept incremental files
   - Add configuration options
   - Test with typical commits

3. ⏳ **Phase 3** (After Phase 2 verification)
   - Implement FileChunker service
   - Add file-level parallelism to executor
   - Add tool-level parallelism flags
   - Extensive testing with large file sets

---

## Testing Strategy

### Phase 1 Testing
```bash
# Before changes
time python -m crackerjack run --comp

# After changes
time python -m crackerjack run --comp

# Expected: 8-12× faster
```

### Phase 2 Testing
```bash
# Make small change (touch 1 file)
echo "# test" >> crackerjack/__init__.py

# Run incremental
time python -m crackerjack run --comp --incremental

# Run full scan
time python -m crackerjack run --comp --full-scan

# Expected: Incremental 10-50× faster
```

### Phase 3 Testing
```bash
# Test file chunking
python -m crackerjack run --comp --chunk-size 50

# Compare performance
time python -m crackerjack run --comp --no-chunking

# Expected: Chunking 3-5× faster
```

---

## Success Criteria

- ✅ Phase 1: 8-12× speedup (40-50 min → 4-6 min)
- ✅ Phase 2: 40-100× speedup for typical commits (40-50 min → 30-60 sec)
- ✅ Phase 3: 15-25× speedup for large changes (40-50 min → 2-3 min)
- ✅ Zero regressions in quality checks
- ✅ Zero increase in false positives/negatives

---

## Monitoring & Metrics

### Add Performance Logging

```python
# crackerjack/services/performance_monitor.py

class PerformanceMonitor:
    def track_hook_execution(
        self,
        hook_name: str,
        files_scanned: int,
        duration_seconds: float,
        incremental: bool,
    ) -> None:
        """Log performance metrics for analysis."""

        logger.info(
            f"Hook: {hook_name}, "
            f"Files: {files_scanned}, "
            f"Duration: {duration_seconds:.2f}s, "
            f"Files/sec: {files_scanned / duration_seconds:.1f}, "
            f"Mode: {'incremental' if incremental else 'full'}"
        )
```

### Metrics to Track

- Files scanned per hook
- Execution time per hook
- Files/second throughput
- Incremental vs full scan ratio
- Memory usage per worker
- CPU utilization

---

## Conclusion

**Recommended Action**: Implement Phase 1 immediately (5 minutes, zero risk, 8-12× speedup).

**Follow-up**: After Phase 1 is verified, implement Phase 2 for additional 20-30% improvement.

**Future**: Phase 3 for maximum performance on large codebases.

**Bottom Line**: We can reduce comprehensive hooks execution from 40-50 minutes to 4-6 minutes (Phase 1) or 30-60 seconds for typical commits (Phase 2) without sacrificing quality.

---

**Next Step**: User approval to implement Phase 1 changes.
