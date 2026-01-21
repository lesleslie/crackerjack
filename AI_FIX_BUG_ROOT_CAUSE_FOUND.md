# AI-Fix Bug - ROOT CAUSE IDENTIFIED AND FIXED

## The Bug

When running `python -m crackerjack run --comp --ai-fix`, the AI fixer was reporting:

```
✓ All issues resolved in 0 iteration(s)!
```

Even when 5 comprehensive hooks failed with 237 total issues.

## Root Cause: CASE SENSITIVITY MISMATCH

### The Silent Killer

The autofix_coordinator was checking for **uppercase** status values, but HookResult objects use **lowercase** status values.

**In HookResult (actual data model):**

```python
status = "passed" if return_code == 0 else "failed"  # LOWERCASE!
```

**In autofix_coordinator.py (BEFORE FIX):**

```python
# Line 287 - VALIDATION FAILING
valid_statuses = ["Passed", "Failed", "Skipped", "Error"]  # UPPERCASE!
return status in valid_statuses  # Always returns False for lowercase "failed"

# Line 478 - STATUS CHECK FAILING
if getattr(result, "status", "") != "Failed":  # Never matches lowercase "failed"
    continue  # Skips all hooks!

# Line 114 - EXTRACTION FAILING
and getattr(result, "status", "") == "Failed":  # Never matches lowercase
```

### Impact

1. **All HookResult objects failed validation** - rejected before any processing
1. **No failed hooks were detected** - all skipped due to case mismatch
1. **Zero issues extracted** - empty issue list
1. **"0 iterations" reported** - AI fixer thought there were no issues to fix

## The Fix

### 1. Fixed Validation (Line 287-289)

```python
# BEFORE (WRONG)
valid_statuses = ["Passed", "Failed", "Skipped", "Error"]
return status in valid_statuses

# AFTER (CORRECT)
# HookResult uses lowercase status values: "passed", "failed", "skipped", "error"
valid_statuses = ["passed", "failed", "skipped", "error", "timeout"]
return status in valid_statuses
```

### 2. Fixed Status Check (Line 472)

```python
# BEFORE (WRONG)
if getattr(result, "status", "") != "Failed":
    continue

# AFTER (CORRECT)
if status.lower() != "failed":
    continue
```

### 3. Fixed Extract Failed Hooks (Line 114)

```python
# BEFORE (WRONG)
and getattr(result, "status", "") == "Failed":

# AFTER (CORRECT)
and getattr(result, "status", "").lower() == "failed":
```

## Files Modified

1. **`crackerjack/core/autofix_coordinator.py`** (3 critical fixes)

   - Validation to accept lowercase status values
   - Status checks to use case-insensitive comparison
   - Extract failed hooks to use case-insensitive comparison

1. **`crackerjack/executors/hook_executor.py`** (already fixed earlier)

   - Populate `output` and `error` fields

1. **`crackerjack/executors/async_hook_executor.py`** (already had correct code)

   - Lines 535-536: Already populating `output` and `error` fields correctly

1. **`crackerjack/plugins/hooks.py`** (fixed earlier)

   - Populate `output` and `error` fields for plugin hooks

1. **Test files**

   - Updated to use lowercase status values to match HookResult data model

## Test Results

```bash
✅ All 50 autofix-related tests passing
   - 22 integration tests (including 2 regression tests)
   - 28 existing autofix coordinator tests

✅ All 16 fast quality hooks passing

✅ Both regression tests passing
   - test_regression_raw_output_not_used
   - test_regression_multiple_hook_failures_extracted
```

## Verification

The fix ensures that:

- ✅ HookResult validation passes for actual lowercase status values
- ✅ Failed hooks are correctly detected and processed
- ✅ Issues are extracted from hook output (stdout/stderr)
- ✅ AI agent iteration loop processes issues correctly
- ✅ Multiple iterations occur until issues are fixed or max iterations reached

## Key Insights

`★ Insight ─────────────────────────────────────`
**Case Sensitivity Bugs** are particularly insidious because:

1. They don't cause crashes - just silent failures
1. No error messages explaining WHY validation failed
1. Objects are created correctly but silently rejected
1. Assumptions about data ("status should be Title Case") don't match reality

**Prevention Strategy**:

- Always match the actual data model, not assumptions
- Write tests that use real data structures, not Mock objects with made-up values
- Use case-insensitive comparisons when dealing with string status values
- Add debug logging to see what's actually being processed
  `─────────────────────────────────────────────────`

## Expected Behavior After Fix

When running `python -m crackerjack run --comp --ai-fix` with failures:

```
❌ Comprehensive hooks attempt 1: 5/10 passed

Comprehensive Hook Results:
 - zuban :: FAILED | issues=60
 - refurb :: FAILED | issues=48
 - complexipy :: FAILED | issues=9

🤖 AI AGENT FIXING Attempting automated fixes
----------------------------------------------------------------------

→ Iteration 1/5: 117 issues to fix
[AI agents process issues...]

→ Iteration 2/5: 45 issues to fix
[AI agents process remaining issues...]

→ Iteration 3/5: 12 issues to fix
[AI agents process remaining issues...]

✓ All issues resolved in 3 iteration(s)!
✅ AI agents applied fixes, retrying comprehensive hooks...

✅ Comprehensive hooks attempt 2: 10/10 passed
```

**Status**: ✅ FIXED and TESTED

**Date**: 2026-01-21

**Severity**: Critical (main feature completely broken due to case sensitivity mismatch)

**Resolution**: Complete with comprehensive test coverage
