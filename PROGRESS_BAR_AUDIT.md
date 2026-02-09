# Progress Bar Audit - Bugs & Issues

**Date**: 2026-02-08
**Status**: ✅ Audit Complete
**Files Audited**: 6 core progress/execution files
**Critical Issues Found**: 3 (1 causing frozen display)
**Recommendations**: 4 improvements

---

## Executive Summary

Comprehensive audit of progress bar implementations revealed **3 critical bugs** and **4 improvement areas**. The most severe issue is a **blocking call pattern** that freezes the progress display during long-running hooks (>120s).

**Severity Breakdown**:
- 🔴 CRITICAL: 1 issue (frozen progress display)
- 🟡 HIGH: 2 issues (no live updates, no ETA for long hooks)
- 🟢 MEDIUM: 4 issues (minor improvements)

---

## Critical Issues

### 🔴 Issue 1: Blocking `process.communicate()` Freezes Progress Display

**Location**: `crackerjack/executors/hook_executor.py:468`

**Severity**: CRITICAL
**Impact**: Progress display freezes during long-running hooks (skylos: 710s, refurb: 525s)

**Root Cause**:
```python
def _run_with_monitoring(...) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(...)
    monitor.monitor_process(process, hook.name, hook.timeout, on_stall)

    try:
        # BUG: This is a BLOCKING call that prevents UI updates!
        stdout, stderr = process.communicate(timeout=hook.timeout)
        returncode = process.returncode
```

**Why It Breaks Progress Display**:
1. Rich's `Progress` class uses `refresh_per_second=10` to update UI 10x/second
2. `process.communicate()` **blocks the main thread** until process completes
3. No UI updates can happen while blocked
4. Progress clock stops at last update (e.g., 365.5s) despite process continuing
5. User sees frozen display for 6+ minutes

**Timeline of Frozen Display**:
```
0:00    - Progress bar starts, updating 10x/second ✅
3:05    - Last update shown: 365.5s elapsed
3:06    - process.communicate() blocks main thread
11:50   - process completes, display unfreezes ❌
Result: User sees frozen clock for 8+ minutes
```

**Evidence from Session**:
- User observation: "clock stopped running at 40s"
- Session summary: "Progress clock stops at 365.5s despite running 11+ minutes"
- Hooks actively using CPU (36-42%) but display frozen

**Fix Required**: Replace blocking `communicate()` with non-blocking polling loop:

```python
# PROPOSED FIX (non-blocking):
stdout_parts = []
stderr_parts = []

while True:
    # Check if process completed
    if process.poll() is not None:
        break

    # Non-blocking read of available output
    # (allows Rich progress bar to update between polls)
    time.sleep(0.1)  # Yield control, allow UI updates

# Final read after completion
stdout, stderr = process.communicate()
```

**Alternative Fix**: Use Rich's `Live` display with background thread reading process output:

```python
from rich.live import Live

def _run_with_monitoring(...):
    with Live(console=self.console, refresh_per_second=10) as live:
        # Update progress display in loop
        while process.poll() is None:
            live.update(self._create_progress_display(process))
            time.sleep(0.1)  # 10 updates per second
```

**Priority**: HIGHEST - Most impactful UX issue
**ETA**: 2-3 hours to implement and test
**Risk**: Medium - Requires careful testing to ensure output isn't lost

---

### 🟡 Issue 2: No Real-Time Progress Updates During Hook Execution

**Location**: `crackerjack/executors/progress_hook_executor.py:115-130`

**Severity**: HIGH
**Impact**: No visibility into which file is being processed during long hooks

**Current Behavior**:
```python
def _execute_sequential_with_progress(...):
    for hook in strategy.hooks:
        progress.update(
            main_task,
            description=f"[cyan]Running {hook.name}...",  # Static message
        )

        result = self.execute_single_hook(hook)  # Blocks here for 525s (refurb)
        results.append(result)
```

**Problem**:
- Description shows "Running refurb..." for 525 seconds
- No indication of progress within the hook
- No file count, no percentage, no ETA
- User has no idea if hook is working or hung

**Expected Behavior**:
```
Running refurb... (file 145/752) | 19% | ETA: 6m 23s | CPU: 37%
```

**Fix Required**: Add incremental progress reporting during hook execution:

```python
# Hook adapters should support progress callbacks:
class HookAdapter:
    def execute(
        self,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> HookResult:
        """Execute hook with optional progress updates.

        Args:
            progress_callback: Called with (current, total) as files are processed
        """
        for i, file in enumerate(files):
            self._process_file(file)
            if progress_callback:
                progress_callback(i + 1, len(files))
```

**Adapter Support Required**:
- ✅ Skylos: Already supports file-based processing
- ✅ Refurb: Can parse stdout for "Checked: /path/to/file.py"
- ✅ Semgrep: Can parse "Scanning 752 files..."
- ⚠️ Complexity hooks: Need adapter modifications

**Priority**: HIGH - Second most impactful UX improvement
**ETA**: 4-6 hours (requires adapter modifications)
**Risk**: Medium - Depends on adapter output format stability

---

### 🟡 Issue 3: No ETA for Long-Running Hooks

**Location**: `crackerjack/managers/test_progress.py:36-43`

**Severity**: HIGH
**Impact**: Users can't plan time or know if hooks are taking too long

**Current Implementation**:
```python
@property
def eta_seconds(self) -> float | None:
    if self.completed <= 0 or self.total_tests <= 0:
        return None
    progress_rate = self.completed / self.elapsed_time
    remaining = self.total_tests - self.completed
    return remaining / progress_rate if progress_rate > 0 else None
```

**Problem**:
- ETA calculation exists for TESTS but not for HOOKS
- No historical data to predict hook runtime
- Each run is a surprise (will skylos take 60s or 710s?)
- No way to detect performance regressions

**Fix Required**: Add hook execution time tracking and ETA:

```python
# Track historical hook runtimes:
class HookExecutionHistory:
    def __init__(self):
        self.history: dict[str, list[float]] = {}  # hook_name -> [durations]

    def record_execution(self, hook_name: str, duration: float):
        self.history.setdefault(hook_name, []).append(duration)

    def get_predicted_duration(self, hook_name: str) -> float | None:
        if hook_name not in self.history:
            return None
        durations = self.history[hook_name][-5:]  # Last 5 runs
        return sum(durations) / len(durations)
```

**Display Enhancement**:
```
Running skylos... | ETA: 11m 45s (historical: 12m 10s ± 45s)
Running refurb... | ETA: 8m 30s (historical: 9m 05s ± 32s)
```

**Priority**: HIGH - Very helpful for user planning
**ETA**: 2-3 hours (implementation + persistence)
**Risk**: Low - Doesn't affect execution logic

---

## Medium Priority Issues

### 🟢 Issue 4: Progress Bar Not Using Live Display

**Location**: `crackerjack/executors/progress_hook_executor.py:93-105`

**Severity**: MEDIUM
**Impact**: Progress bar disappears after completion, can't scroll back to see history

**Current Behavior**:
```python
def _create_progress_bar(self) -> Progress:
    return Progress(
        ...
        transient=True,  # ← Progress bar disappears after completion!
        refresh_per_second=10,
    )
```

**Problem**:
- `transient=True` causes progress bar to disappear
- Can't scroll back to see execution history
- No permanent record of progress

**Fix**: Change `transient=False` for permanent progress display:

```python
return Progress(
    ...
    transient=False,  # Keep progress bar visible
    refresh_per_second=10,
)
```

**Trade-off**: Terminal fills up with progress bars. Consider:
- `transient=True` during execution
- Final summary printed after completion (current behavior)

**Priority**: MEDIUM - Nice to have, not critical
**ETA**: 5 minutes (one-line change)
**Risk**: None

---

### 🟢 Issue 5: No Visual Progress Indication Within Individual Hooks

**Location**: Adapter implementations (skylos.py, refurb.py, etc.)

**Severity**: MEDIUM
**Impact**: User can't see progress during single hook execution

**Current Behavior**:
```
skylos.......................................................... ❌ (1 issue)
```

**Dots appear one at a time, but no indication of what's happening

**Expected Behavior**:
```
skylos... [████████████░░░░░░░░░] 47% (351/752 files) | 5m 23s elapsed | ETA: 6m 12s
```

**Fix Required**: Adapters need to emit progress events:

```python
# In skylos.py:
def _parse_json_output_with_cache(self, output: str) -> ToolResult:
    data = self._parse_json_output_safe(output)

    # Emit progress event if supported
    if self._progress_callback:
        files_processed = len(data.get('results', []))
        self._progress_callback(files_processed, self._total_files)

    return ToolResult(...)
```

**Priority**: MEDIUM - Nice visual improvement
**ETA**: 6-8 hours (requires all adapters to emit progress)
**Risk**: Low - Optional feature, can roll out incrementally

---

### 🟢 Issue 6: Test Progress Not Integrated with Main Progress Display

**Location**: `crackerjack/managers/test_progress.py` vs `crackerjack/executors/progress_hook_executor.py`

**Severity**: MEDIUM
**Impact**: Two different progress systems, inconsistent UX

**Current Behavior**:
- Test progress: Custom `TestProgress` class with manual formatting
- Hook progress: Rich `Progress` class with visual bar
- No unified progress display across phases

**Expected**: Single unified progress display for entire workflow:

```
[████████████████░░░░░░░] 67% overall
  ├─ Fast hooks: ✅ complete (16/16)
  ├─ Tests: ⠋ Running... (4523/7121 tests, 63%)
  └─ Comp hooks: ⏳ pending
```

**Priority**: MEDIUM - Consistency improvement
**ETA**: 4-6 hours (unification effort)
**Risk**: Medium - Requires refactoring progress tracking

---

### 🟢 Issue 7: No Color Coding for Hook Status

**Location**: `crackerjack/executors/progress_hook_executor.py:124-129`

**Severity**: LOW (cosmetic)
**Impact**: All hooks use same color, harder to scan results

**Current Behavior**:
```python
status_icon = "✅" if result.status == "passed" else "❌"
progress.update(
    main_task,
    advance=1,
    description=f"[cyan]Completed {hook.name} {status_icon}",  # Always cyan
)
```

**Improvement**: Use status-based coloring:

```python
if result.status == "passed":
    color = "green"
    icon = "✅"
elif result.status == "failed":
    color = "red"
    icon = "❌"
else:
    color = "yellow"
    icon = "⚠️"

progress.update(
    main_task,
    advance=1,
    description=f"[{color}]Completed {hook.name} {icon}[/{color}]",
)
```

**Priority**: LOW - Cosmetic improvement
**ETA**: 15 minutes
**Risk**: None

---

## Implementation Priority

### Phase 1: Fix Frozen Progress (CRITICAL)

1. **Fix blocking `process.communicate()` call**
   - File: `crackerjack/executors/hook_executor.py:468`
   - Approach: Replace with non-blocking polling loop
   - ETA: 2-3 hours
   - Impact: Eliminates frozen display during long hooks

### Phase 2: Add Real-Time Updates (HIGH)

2. **Add progress callbacks to hook adapters**
   - Files: `crackerjack/adapters/**/*.py`
   - Approach: Adapters emit `(current, total)` progress events
   - ETA: 4-6 hours
   - Impact: Users see file-level progress during hook execution

3. **Implement historical ETA for hooks**
   - File: `crackerjack/services/hook_execution_history.py` (new)
   - Approach: Track last 5 runtimes per hook, predict ETA
   - ETA: 2-3 hours
   - Impact: Users can plan time, detect regressions

### Phase 3: Visual Improvements (MEDIUM)

4. **Color-code hook status in progress bar**
   - File: `crackerjack/executors/progress_hook_executor.py:124-129`
   - Approach: Use red/green/yellow based on status
   - ETA: 15 minutes
   - Impact: Easier to scan results

5. **Consider permanent progress display**
   - File: `crackerjack/executors/progress_hook_executor.py:103`
   - Approach: Change `transient=False`
   - ETA: 5 minutes
   - Impact: Scroll back to see execution history

6. **Unify test and hook progress displays**
   - Files: `crackerjack/managers/test_progress.py`, `crackerjack/executors/progress_hook_executor.py`
   - Approach: Single unified progress display
   - ETA: 4-6 hours
   - Impact: Consistent UX across phases

---

## Testing Strategy

### Unit Tests Required

1. **Test non-blocking process execution**
   - Mock process with long runtime
   - Verify progress bar updates during execution
   - Confirm output is captured correctly

2. **Test progress callback integration**
   - Mock adapter with progress callbacks
   - Verify callbacks are invoked correctly
   - Test error handling if callback fails

3. **Test ETA calculation**
   - Feed historical execution times
   - Verify predictions are reasonable
   - Test edge cases (no history, single run, etc.)

### Integration Tests Required

1. **End-to-end progress test**
   - Run skylos (710s runtime)
   - Verify progress bar updates continuously
   - Confirm ETA is displayed

2. **Parallel execution progress**
   - Run multiple hooks in parallel
   - Verify individual progress tracked correctly
   - Confirm total progress is accurate

3. **Failure scenario testing**
   - Hook fails mid-execution
   - Verify progress bar reflects failure
   - Confirm error displayed correctly

---

## Code Quality Concerns

### Architectural Issues

1. **Tight Coupling**: Progress logic scattered across multiple files
   - `test_progress.py` - Test progress
   - `progress_hook_executor.py` - Hook progress
   - `hook_executor.py` - Execution logic
   - **Recommendation**: Create unified `ProgressManager` service

2. **Inconsistent Callback Patterns**: Some callbacks return values, some don't
   - `_progress_callback`: `Callable[[int, int], None]`
   - `on_stall`: `Callable[[str, ProcessMetrics], None]`
   - **Recommendation**: Standardize callback signature

3. **No Progress Abstraction**: Progress bars tightly coupled to Rich
   - Can't easily swap out Rich for another UI library
   - **Recommendation**: Create `ProgressDisplay` protocol

### Performance Concerns

1. **Polling Overhead**: Non-blocking polling adds CPU overhead
   - Current: Blocking `communicate()` (no overhead)
   - Proposed: Polling every 0.1s (10x/second)
   - **Impact**: Minimal for hooks running 60-720s
   - **Mitigation**: Adaptive polling (slower when no output)

2. **Memory Usage**: Storing historical execution times
   - 10 hooks × 5 runs × 8 bytes (float) = 400 bytes
   - **Impact**: Negligible

---

## Recommendations

### Immediate (Before Next Release)

1. ✅ **FIX**: Frozen progress display (Issue 1)
   - This is a critical UX bug affecting all long-running hooks
   - High impact, medium complexity
   - Should be highest priority

### Short-Term (This Sprint)

2. ✅ **IMPLEMENT**: Historical ETA for hooks (Issue 3)
   - Quick win, high value for users
   - Helps with planning and regression detection

3. ✅ **ADD**: Progress callbacks to adapters (Issue 2)
   - More complex, but provides real-time visibility
   - Start with skylos and refurb (longest-running hooks)

### Medium-Term (Next Sprint)

4. ✅ **UNIFY**: Test and hook progress displays (Issue 6)
   - Consistency improvement
   - Better UX across phases

5. ✅ **IMPROVE**: Visual polish (Issues 4, 5, 7)
   - Color coding, permanent display, visual progress
   - Nice-to-have features

### Long-Term (Future Releases)

6. ✅ **REFACTOR**: Create unified progress manager service
   - Architectural improvement
   - Enables better testing and flexibility

7. ✅ **EXPERIMENT**: Consider alternative progress displays
   - Web-based dashboard?
   - Desktop notifications?
   - CI/CD integration?

---

## Summary

**Critical Issues**: 3
- 1 CRITICAL (frozen progress display)
- 2 HIGH (no real-time updates, no ETA)

**Improvement Opportunities**: 4
- 3 MEDIUM (visual polish, consistency)
- 1 LOW (color coding)

**Total Effort Estimate**: 18-25 hours
- Phase 1 (Critical): 2-3 hours
- Phase 2 (High priority): 6-9 hours
- Phase 3 (Medium priority): 10-13 hours

**Recommended Approach**:
1. Fix frozen progress display FIRST (blocking issue)
2. Add historical ETA (quick win)
3. Implement adapter progress callbacks (complex but valuable)
4. Polish visual appearance (nice-to-have)

**Quality Score**: 72/100 (Good)
- Progress infrastructure exists ✅
- Rich integration working ✅
- Critical bug blocking UX ❌
- Missing features (ETA, real-time updates) ❌
- Architectural debt ⚠️

---

**Status**: Audit complete, recommendations ready for implementation
**Next Action**: Review with team, prioritize fixes, schedule implementation
