# Issue Count Summary - Total Fix

## Problem

The summary totals in both the Rich table footer and plain text output were showing incorrect issue counts. For example:

```
╰────── Total: 14 | Passed: 11 | Failed: 3 | Issues found: 30 ───────╯
```

But all 3 failed hooks were config errors (showing "!"), so the total should be **0 issues**, not 30.

## Root Cause

The `_calculate_hook_statistics()` method was counting error detail lines as "issues" for config errors.

**The Bug** (phase_coordinator.py:564-571):

```python
for r in results:
    if r.status == "passed":
        continue
    # Use issues_count if available
    if hasattr(r, "issues_count") and r.issues_count > 0:
        total_issues += r.issues_count
    elif r.issues_found:  # ❌ COUNTS ERROR DETAIL LINES!
        total_issues += len(r.issues_found)
```

**Why This Failed**:

1. Config errors have `issues_count=0` (correct)
1. Condition `r.issues_count > 0` evaluates to False
1. Falls through to `elif r.issues_found:`
1. `issues_found` contains error detail lines (traceback)
1. Example: 10 traceback lines → counted as "10 issues"

**The Math**:

- 3 failed fast hooks × ~10 detail lines each = **30 "issues"** ❌
- 1 failed comprehensive hook × ~10 detail lines = **10 "issues"** ❌

## The Fix

### 1. Fixed Summary Calculation

**File**: `crackerjack/core/phase_coordinator.py:561-577`

**Before**:

```python
total_issues = 0
for r in results:
    if r.status == "passed":
        continue
    if hasattr(r, "issues_count") and r.issues_count > 0:
        total_issues += r.issues_count
    elif r.issues_found:  # ❌ Counts error details
        total_issues += len(r.issues_found)
```

**After**:

```python
# Calculate total issues using issues_count (which may be larger than len(issues_found))
# Passed hooks always contribute 0 issues
# Config errors (is_config_error=True) also contribute 0 issues
total_issues = 0
for r in results:
    if r.status == "passed":
        continue
    # Skip config errors - they're not code quality issues
    if hasattr(r, "is_config_error") and r.is_config_error:
        continue  # ✅ SKIP CONFIG ERRORS
    # Use issues_count directly (don't fall back to len(issues_found))
    # because issues_found may contain error detail lines, not actual issues
    if hasattr(r, "issues_count"):
        total_issues += r.issues_count
    elif r.issues_found:
        # Legacy fallback for old HookResults without issues_count
        total_issues += len(r.issues_found)
```

### 2. Fixed Plain Text Output

**File**: `crackerjack/core/phase_coordinator.py:590-610`

The plain text output (`issues=10`) also needed the same fix to show "!" for config errors.

**Before**:

```python
def _print_plain_hook_result(self, result: HookResult) -> None:
    issues = (
        "0"
        if result.status == "passed"
        else str(len(result.issues_found) if result.issues_found else 0)  # ❌ Same bug
    )
    self.console.print(
        f"  - {name} :: {status} | {duration} | issues={issues}",
    )
```

**After**:

```python
def _print_plain_hook_result(self, result: HookResult) -> None:
    # Determine issues display (matches Rich table logic)
    if result.status == "passed":
        issues = "0"
    elif hasattr(result, "is_config_error") and result.is_config_error:
        # Config/tool error - show simple symbol instead of misleading count
        issues = "!"  # ✅ SHOW SYMBOL
    else:
        # For failed hooks with code violations, use issues_count
        # Don't fall back to len(issues_found) - it may contain error detail lines
        issues = str(result.issues_count if hasattr(result, "issues_count") else 0)

    self.console.print(
        f"  - {name} :: {status} | {duration} | issues={issues}",
    )
```

## Expected Behavior After Fix

### Before (Incorrect)

**Rich Table**:

```
╭──────────────────────── Fast Hook Results ─────────────────────────╮
│   ruff-format                 FAILED           39.75s          !   │
│   ruff-check                  FAILED            2.90s          !   │
│   codespell                   FAILED            5.15s          !   │
╰────── Total: 14 | Passed: 11 | Failed: 3 | Issues found: 30 ───────╯
                                                               ^^^ WRONG!
```

**Plain Text**:

```
Fast Hook Results:
  - ruff-format :: FAILED | 39.75s | issues=10  ← WRONG!
  - ruff-check :: FAILED | 2.90s | issues=10   ← WRONG!
  - codespell :: FAILED | 5.15s | issues=10    ← WRONG!
```

### After (Correct)

**Rich Table**:

```
╭──────────────────────── Fast Hook Results ─────────────────────────╮
│   ruff-format                 FAILED           39.75s          !   │
│   ruff-check                  FAILED            2.90s          !   │
│   codespell                   FAILED            5.15s          !   │
╰────── Total: 14 | Passed: 11 | Failed: 3 | Issues found: 0 ────────╯
                                                               ^ CORRECT!
!  = Configuration or tool error (not code issues)
```

**Plain Text**:

```
Fast Hook Results:
  - ruff-format :: FAILED | 39.75s | issues=!  ✅ CORRECT!
  - ruff-check :: FAILED | 2.90s | issues=!   ✅ CORRECT!
  - codespell :: FAILED | 5.15s | issues=!    ✅ CORRECT!
```

## All Four Fixes Summary

This is the **fourth and final fix** in the issue count display system:

1. ✅ **Display Fallback Bug** (../implementation/FINAL_IMPLEMENTATION_SUMMARY.md): Fixed `len(issues_found)` fallback in Rich table display
1. ✅ **Emoji Panel Width** (../implementation/FINAL_IMPLEMENTATION_SUMMARY.md): Changed from ⚠️ to "!" for terminal compatibility
1. ✅ **Error Details Display** (../implementation/ERROR_DETAILS_DISPLAY_FIX.md): Added traceback to `details` field for better debugging
1. ✅ **Summary Total Calculation** (THIS FIX): Fixed total issue count to exclude config errors

## Benefits

### 1. Accurate Totals

- ✅ Config errors don't inflate issue counts
- ✅ Summary totals match individual hook displays
- ✅ "0 issues found" when all failures are config errors

### 2. Consistent Display

- ✅ Rich table and plain text show same information
- ✅ "!" symbol used consistently across formats
- ✅ No confusion between error details and code issues

### 3. Correct Semantics

- ✅ Config errors explicitly excluded from issue counts
- ✅ Total reflects actual code quality problems
- ✅ Users see true impact at a glance

## Files Modified

**`crackerjack/core/phase_coordinator.py`**:

- Lines 561-577: Skip config errors in summary calculation
- Lines 590-610: Show "!" for config errors in plain text output

**Total Changes**: 1 file, ~20 lines modified

## Testing

### Manual Verification

Run in a project with config errors (like ../acb):

```bash
cd /Users/les/Projects/acb
python -m crackerjack run
```

Expected results:

- Individual hooks with config errors show "!"
- Summary total shows "0 issues found" (not 30 or 10)
- Both Rich table and plain text formats match

### Automated Testing

All existing unit tests continue to pass:

- 9 tests in `tests/unit/orchestration/test_issue_count_fix.py` ✅
- Integration with previous fixes maintained ✅

## Summary

Successfully fixed the fourth and final bug in the issue count display system. Config errors no longer inflate summary totals, providing users with accurate information about actual code quality issues versus tool/configuration problems.

All four fixes work together to provide a complete, accurate, and intuitive display of hook results.
