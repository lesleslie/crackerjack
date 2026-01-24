# AI Fix Bug Fix Report

## Problem Summary

When running `python -m crackerjack run --comp --ai-fix` with comprehensive hook failures, the AI fixer reported:

```
✓ All issues resolved in 0 iteration(s)!
✅ AI agents applied fixes, retrying comprehensive hooks...
```

But then the exact same failures reappeared on the retry, with no actual fixes attempted.

## Root Cause Analysis

### Primary Issue: Field Name Mismatch

The bug occurred due to a **data model inconsistency** between how `HookResult` objects are created and how the AI fixer tries to read them.

**In `autofix_coordinator.py`:**

```python
# Line 505 - BEFORE FIX (incorrect)
raw_output = getattr(result, "raw_output", "")  # Returns empty string!
```

**In `crackerjack/models/task.py` (HookResult definition):**

```python
@dataclass
class HookResult:
    ...
    output: str | None = None      # This field exists
    error: str | None = None       # This field exists
    error_message: str | None = None
    # NO raw_output field!
```

### Secondary Issue: Fields Not Populated

Even after fixing the field names, the `output` and `error` fields were **not being populated** when HookResult objects were created in the hook executors.

**In `hook_executor.py` (line 486-498):**

```python
# BEFORE FIX - fields not populated
return HookResult(
    ...
    error_message=error_message,
    is_timeout=False,
    # Missing: output=result.stdout
    # Missing: error=result.stderr
)
```

## Impact

When `autofix_coordinator` tried to parse hook results into AI-fixable issues:

1. `getattr(result, "raw_output", "")` returned `""` (empty string)
1. `_parse_hook_to_issues(hook_name, "")` received no actual error output
1. No issues were extracted, even though 5 hooks had failed
1. `current_issue_count == 0` on iteration 0
1. AI fixer reported "All issues resolved in 0 iteration(s)!"
1. No actual fixing was attempted

## The Fix

### 1. Fixed autofix_coordinator.py (2 locations)

**File: `crackerjack/core/autofix_coordinator.py`**

```python
# Line 505 - AFTER FIX (correct)
output = getattr(result, "output", None) or ""
error = getattr(result, "error", None) or ""
error_message = getattr(result, "error_message", None) or ""

# Combine all available output sources
raw_output = output + error + error_message
```

Also fixed `_should_skip_autofix` method (line 299) with the same pattern.

### 2. Fixed hook_executor.py

**File: `crackerjack/executors/hook_executor.py`**

```python
# Line 498-500 - AFTER FIX
return HookResult(
    ...
    error_message=error_message,
    is_timeout=False,
    output=result.stdout,   # Store stdout for AI fixer
    error=result.stderr,    # Store stderr for AI fixer
)
```

### 3. Fixed async_hook_executor.py

**File: `crackerjack/executors/async_hook_executor.py`**

```python
# Line 535-540 - AFTER FIX
return HookResult(
    ...
    is_timeout=False,
    output=self._last_stdout.decode() if self._last_stdout else "",
    error=self._last_stderr.decode() if self._last_stderr else "",
)
```

## Verification

The fix ensures that:

1. ✅ HookResult objects contain the actual stdout/stderr from hook execution
1. ✅ The AI fixer can properly parse hook output into Issue objects
1. ✅ Multiple iterations will occur until issues are fixed or max iterations reached
1. ✅ Comprehensive hook failures (zuban, pyscn, creosote, complexipy, refurb) will be properly handled

## Expected Behavior After Fix

When running `python -m crackerjack run --comp --ai-fix` with failures:

```
❌ Comprehensive hooks attempt 1: 5/10 passed in 124.29s

🤖 AI AGENT FIXING Attempting automated fixes
----------------------------------------------------------------------

→ Iteration 1/5: 237 issues to fix
[AI agents process issues...]

→ Iteration 2/5: 145 issues to fix
[AI agents process remaining issues...]

...

✓ All issues resolved in 4 iteration(s)!
✅ AI agents applied fixes, retrying comprehensive hooks...
```

## Files Modified

1. `crackerjack/core/autofix_coordinator.py` - Fixed field access (2 methods)
1. `crackerjack/executors/hook_executor.py` - Populate output/error fields
1. `crackerjack/executors/async_hook_executor.py` - Populate output/error fields

## Testing

Run comprehensive hooks with AI fix enabled:

```bash
python -m crackerjack run --comp --ai-fix
```

Expected result: Multiple iteration loop with actual issue fixing attempts.

______________________________________________________________________

**Date**: 2026-01-20
**Severity**: Critical (main feature completely broken)
**Status**: Fixed
**Version**: v0.49.0+
