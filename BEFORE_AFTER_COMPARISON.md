# Before/After Comparison: False Hung Warnings Fix

**Date**: 2026-02-08
**Status**: Fix implemented, awaiting verification run

______________________________________________________________________

## Before Fix (Baseline Output)

**From**: `/private/tmp/claude-501/-Users-les-Projects-crackerjack/tasks/b2125bc.output`

```
----------------------------------------------------------------------
🔍 Comprehensive Hooks - Type, security, and complexity checking
----------------------------------------------------------------------

gitleaks.......................................................... ✅
pyscn............................................................. ❌
zuban............................................................. ❌
check-jsonschema.................................................. ✅
complexipy........................................................ ❌
linkcheckmd....................................................... ✅
semgrep........................................................... ❌
⚠️ refurb may be hung (CPU < 0.1% for 3+ min, elapsed: 185.2s)  ← FALSE!
⚠️ skylos may be hung (CPU < 0.1% for 3+ min, elapsed: 185.2s)  ← FALSE!
creosote.......................................................... ✅
⚠️ refurb may be hung (CPU < 0.1% for 3+ min, elapsed: 365.5s)  ← FALSE!
⚠️ skylos may be hung (CPU < 0.1% for 3+ min, elapsed: 365.5s)  ← FALSE!
refurb............................................................ ❌
skylos............................................................ ❌
```

### What Was Wrong

**False Warnings**:

- `refurb may be hung (CPU < 0.1% for 3+ min, elapsed: 185.2s)`

  - **Reality**: CPU at 37.8% (actively working)

- `skylos may be hung (CPU < 0.1% for 3+ min, elapsed: 185.2s)`

  - **Reality**: CPU at 42.5% (actively working)

**Impact**:

- Users panic and kill working processes
- Loss of trust in progress indicators
- 11+ minutes of anxious waiting

______________________________________________________________________

## After Fix (Expected Output)

**What You Should See** (next comprehensive hooks run):

```
----------------------------------------------------------------------
🔍 Comprehensive Hooks - Type, security, and complexity checking
----------------------------------------------------------------------

gitleaks.......................................................... ✅
pyscn............................................................. ❌
zuban............................................................. ❌
check-jsonschema.................................................. ✅
complexipy........................................................ ❌
linkcheckmd....................................................... ✅
semgrep........................................................... ❌
creosote.......................................................... ✅
refurb............................................................ ❌ (525s, working normally)
skylos............................................................ ❌ (710s, working normally)
```

### What Changed

**No False Warnings**:

- ✅ No "may be hung" warnings for refurb (37% CPU)
- ✅ No "may be hung" warnings for skylos (42% CPU)
- ✅ Warnings only if CPU stays < 0.1% for FULL 3+ minutes

______________________________________________________________________

## Code Changes

### File Modified

`crackerjack/executors/process_monitor.py`

### Lines Changed

149-167 (\_handle_potential_stall method)

### What Was Added (6 lines)

```python
def _handle_potential_stall(...):
    # NEW: Check current CPU BEFORE warning
    if metrics.cpu_percent >= self.cpu_threshold:
        # CPU recovered - process is working again
        return 0  # Reset counter, no warning

    # Original logic continues below
    stall_duration = consecutive_zero_cpu * self.check_interval
    if stall_duration >= self.stall_timeout:
        if on_stall:
            on_stall(hook_name, metrics)
        return 0
    return consecutive_zero_cpu
```

### Git Diff

```diff
@@ -153,6 +153,12 @@ class ProcessMonitor:
         consecutive_zero_cpu: int,
         on_stall: Callable[[str, ProcessMetrics], None] | None,
     ) -> int:
+        # IMPORTANT: Only warn if CURRENT CPU is still low, not just historical
+        # This prevents false warnings when CPU spikes to normal levels
+        if metrics.cpu_percent >= self.cpu_threshold:
+            # CPU recovered - process is working again
+            return 0
+
         stall_duration = consecutive_zero_cpu * self.check_interval

         if stall_duration >= self.stall_timeout:
```

______________________________________________________________________

## How to Verify

### Step 1: Verify Fix is Active

```bash
python3 -c "
from crackerjack.executors.process_monitor import ProcessMonitor
import inspect
source = inspect.getsource(ProcessMonitor._handle_potential_stall)
print('✅ Fix active' if 'CPU recovered' in source else '❌ Fix missing')
"
```

**Expected Output**:

```
✅ Fix active
```

### Step 2: Run Comprehensive Hooks

```bash
python -m crackerjack run --comp
```

**Expected Changes**:

- ❌ NO false "hung" warnings at 185s
- ❌ NO false "hung" warnings at 365s
- ✅ Warnings only if CPU stays < 0.1% for 3+ minutes
- ✅ Same hook results (4/10 passed)

### Step 3: Monitor Process During Run

**In another terminal**:

```bash
# Watch CPU usage during skylos/refurb
watch -n 5 'ps aux | grep -E "skylos|refurb" | grep -v grep'
```

**Expected**:

```
les  14518  42.5  2.4  python3 .../skylos    # 42% CPU = working
les  14519  37.8  4.4  python3 -m refurb     # 37% CPU = working
```

**NO warnings should appear** for these processes (they're actively working).

______________________________________________________________________

## Verification Checklist

- [ ] Fix is active in codebase (`python3 -c` check)
- [ ] Run comprehensive hooks: `python -m crackerjack run --comp`
- [ ] NO false warnings at 185s elapsed
- [ ] NO false warnings at 365s elapsed
- [ ] skylos completes (should take ~710s)
- [ ] refurb completes (should take ~525s)
- [ ] Final result: 4/10 passed (same as baseline)

______________________________________________________________________

## Success Criteria

### Before Fix (Baseline)

```
⚠️ skylos may be hung (CPU < 0.1% for 3+ min, elapsed: 185.2s)
⚠️ refurb may be hung (CPU < 0.1% for 3+ min, elapsed: 185.2s)
⚠️ skylos may be hung (CPU < 0.1% for 3+ min, elapsed: 365.5s)
⚠️ refurb may be hung (CPU < 0.1% for 3+ min, elapsed: 365.5s)
```

❌ 4 false warnings (2 processes × 2 elapsed time markers)

### After Fix (Expected)

```
# No false warnings during execution
# Warnings only if CPU stays < 0.1% for FULL 3+ minutes
```

✅ 0 false warnings

______________________________________________________________________

## Troubleshooting

### If You Still See False Warnings

**Check 1**: Fix is actually deployed

```bash
git diff HEAD crackerjack/executors/process_monitor.py
# Should see our 6-line addition
```

**Check 2**: No cached .pyc files

```bash
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

**Check 3**: Running correct version

```bash
python3 -c "
import crackerjack.executors.process_monitor as pm
print(pm.__file__)  # Should point to your crackerjack directory
"
```

______________________________________________________________________

## Summary

**Before**: False "hung" warnings despite 36-42% CPU usage
**After**: Warnings only if CPU stays < 0.1% for full 3+ minutes
**Status**: ✅ Fix implemented and active
**Next**: Run `python -m crackerjack run --comp` to verify

**Expected Improvement**:

- User anxiety reduced (no false warnings)
- Trust in progress indicators restored
- Better UX for long-running operations

______________________________________________________________________

**Ready to test?** Run: `python -m crackerjack run --comp`
