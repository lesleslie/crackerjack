# Error Details Display Fix - Summary

## Problem

When tools failed with exceptions (like complexipy's RuntimeError), the error details weren't being displayed. Instead, users saw generic "Hook X failed with no detailed output (exit code: unknown)" messages.

**Example**: Complexipy failing due to Settings initialization conflict showed no error details.

## Root Cause Analysis

### The Data Flow

1. **Exception Caught** (`_tool_adapter_base.py:290-303`)

   - Tool execution fails with RuntimeError
   - Exception handler creates QAResult with `message` field set
   - **BUT** `details` field was not being set

1. **QAResult Structure** (`models/qa_results.py:60-67`)

   - Has both `message` (summary) and `details` (full output) fields
   - `_create_result()` wasn't accepting/setting `details` parameter

1. **Display Logic** (`hook_orchestrator.py:917`)

   - `_extract_error_details()` checks `if qa_result.details:`
   - Empty string evaluates to False, skips using the error message
   - Falls through to generic fallback message

### The Bug Chain

```python
# Step 1: Exception raised
ComplexipySettings(...) → RuntimeError: "Settings require async initialization"

# Step 2: Exception caught (_tool_adapter_base.py:292-295)
except Exception as e:
    return self._create_result(
        status=QAResultStatus.ERROR,
        message=f"Tool execution failed: {e}",  # ✅ Message set
        start_time=start_time,
    )

# Step 3: _create_result() doesn't set details (_tool_adapter_base.py:566-578)
return QAResult(
    check_id=self.module_id,
    check_name=self.adapter_name,
    status=status,
    message=message,  # ✅ Has error message
    # ❌ details field not set (defaults to "")
    files_checked=files or [],
    execution_time_ms=elapsed_ms,
)

# Step 4: Display logic (_extract_error_details, line 917)
if hasattr(qa_result, "details") and qa_result.details:  # ❌ Empty string = False
    error_message = qa_result.details[:500]
    # This block never executes

# Step 5: Fallback message shown
issues = [f"Hook {hook.name} failed with no detailed output..."]
```

## The Fix

### 1. Updated `_create_result()` Signature

**File**: `crackerjack/adapters/_tool_adapter_base.py:546-578`

**Before**:

```python
def _create_result(
    self,
    status: QAResultStatus,
    message: str,
    start_time: float,
    files: list[Path] | None = None,
) -> QAResult:
```

**After**:

```python
def _create_result(
    self,
    status: QAResultStatus,
    message: str,
    start_time: float,
    files: list[Path] | None = None,
    details: str | None = None,  # ✅ NEW PARAMETER
) -> QAResult:
    """Create a QAResult with standard fields.

    Args:
        details: Optional detailed error output
    """
    return QAResult(
        # ... other fields ...
        details=details or "",  # ✅ SET DETAILS FIELD
    )
```

### 2. Updated Exception Handlers

**File**: `crackerjack/adapters/_tool_adapter_base.py:280-303`

**Before**:

```python
except Exception as e:
    return self._create_result(
        status=QAResultStatus.ERROR,
        message=f"Tool execution failed: {e}",
        start_time=start_time,
    )
```

**After**:

```python
except Exception as e:
    error_msg = f"Tool execution failed: {e}"
    # Include full traceback in details for better debugging
    import traceback

    error_details = f"{error_msg}\n\nFull traceback:\n{traceback.format_exc()}"
    return self._create_result(
        status=QAResultStatus.ERROR,
        message=error_msg,  # Summary for logs
        details=error_details,  # Full traceback for display
        start_time=start_time,
    )
```

**Also updated timeout handler**:

```python
except TimeoutError:
    timeout_msg = f"Tool execution timed out after {self.settings.timeout_seconds}s"
    return self._create_result(
        status=QAResultStatus.ERROR,
        message=timeout_msg,
        details=timeout_msg,  # ✅ Set details for timeouts too
        start_time=start_time,
    )
```

## Expected Behavior After Fix

### Before (Generic Error)

```
Details for failing hooks:
  - complexipy (failed)
      - Hook complexipy failed with no detailed output (exit code: unknown)
```

### After (Detailed Error)

```
Details for failing hooks:
  - complexipy (failed)
      - Tool execution failed: Settings require async initialization. Use 'await Settings.create_async()' instead.

      Full traceback:
      Traceback (most recent call last):
        File ".../adapters/_tool_adapter_base.py", line 281, in check
          exec_result = await self._execute_tool(command, target_files, start_time)
        File ".../adapters/complexity/complexipy.py", line 109, in init
          self.settings = ComplexipySettings(max_complexity=max_complexity)
        File ".../acb/config.py", line 45, in __init__
          raise RuntimeError("Settings require async initialization...")
      RuntimeError: Settings require async initialization. Use 'await Settings.create_async()' instead.
```

## Benefits

### 1. Better Debugging Experience

- ✅ Full traceback shown instead of generic message
- ✅ Exact error location and cause visible
- ✅ Stack trace helps identify configuration issues

### 2. Faster Issue Resolution

- ✅ No need to guess what went wrong
- ✅ Clear indication of Settings initialization conflicts
- ✅ Error messages guide users to solutions

### 3. Consistent Error Reporting

- ✅ All exceptions now provide detailed output
- ✅ Timeouts include timeout duration in details
- ✅ Tool failures show actual error messages

### 4. Backward Compatible

- ✅ `details` parameter is optional (defaults to None)
- ✅ Existing calls to `_create_result()` still work
- ✅ All existing code continues to function

## Related Issues Addressed

This fix addresses the user's report:

> "here is the complexipy failure still with no error details:"
>
> ```
> complexipy: FAILED, 2.42s, ⚠️
> Hook complexipy failed with no detailed output (exit code: unknown)
> ```

Now complexipy (and all other tools) will show:

1. **What failed**: The actual RuntimeError message
1. **Why it failed**: Settings require async initialization
1. **Where it failed**: Full traceback showing line 109 in complexipy.py
1. **How to fix**: Error message suggests using `await Settings.create_async()`

## Files Modified

1. **`crackerjack/adapters/_tool_adapter_base.py`**:
   - Lines 546-578: Added `details` parameter to `_create_result()`
   - Lines 280-303: Updated exception handlers to pass error details

**Total Changes**: 1 file, ~25 lines modified

## Testing

### Manual Verification

Run crackerjack in a project with tool failures:

```bash
cd /Users/les/Projects/acb
python -m crackerjack run --verbose
```

Expected: Error details now show in "Details for failing hooks" section

### Automated Testing

Existing unit tests continue to pass:

- All 9 tests in `tests/unit/orchestration/test_issue_count_fix.py` ✅
- Backward compatibility maintained ✅

## Summary

Successfully fixed the error details display issue by ensuring that exception messages and tracebacks are captured in the `details` field of QAResult. This provides users with actionable debugging information instead of generic "failed with no detailed output" messages.

The fix is:

- ✅ **Minimal**: Only 1 file changed, ~25 lines
- ✅ **Safe**: Backward compatible, optional parameter
- ✅ **Effective**: Provides full tracebacks for all tool failures
- ✅ **Production-ready**: No breaking changes, existing tests pass
