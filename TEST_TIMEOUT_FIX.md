# Test Timeout Fix - Summary

## Problem Statement

Tests were timing out when run through Crackerjack but passing when run directly with pytest.

## Root Cause Analysis

**Dual Timeout Mismatch:**

1. **pytest-timeout** (30 minutes): Configured in `test_command_builder.py:231-237`

   ```python
   def get_test_timeout(self, options: OptionsProtocol) -> int:
       if hasattr(options, "test_timeout") and options.test_timeout:
           return options.test_timeout
       if hasattr(options, "benchmark") and options.benchmark:
           return 1800  # 30 minutes
       return 1800  # 30 minutes default
   ```

1. **subprocess timeout** (10 minutes): Hardcoded in `test_executor.py:23,43,158`

   ```python
   # BEFORE (BROKEN):
   def execute_with_progress(self, cmd: list[str], timeout: int = 600)
   def execute_with_ai_progress(self, cmd: list[str], ..., timeout: int = 600)
   ```

**The Problem:** The subprocess wrapper (600s) killed pytest BEFORE pytest's internal timeout (1800s) could trigger, causing confusing "timeout" failures when running through Crackerjack that didn't occur when running pytest directly.

## Solution

**Align timeouts** to use the same default value (1800s = 30 minutes):

```python
# AFTER (FIXED):
def execute_with_progress(self, cmd: list[str], timeout: int = 1800)  # 30 min
def execute_with_ai_progress(self, cmd: list[str], ..., timeout: int = 1800)  # 30 min
def _execute_test_process_with_progress(self, ..., timeout: int = 1800)  # 30 min
```

## Changes Made

**File:** `crackerjack/managers/test_executor.py`

1. Line 23: `timeout: int = 600` → `timeout: int = 1800`
1. Line 43: `timeout: int = 600` → `timeout: int = 1800`
1. Line 393: `timeout: int` → `timeout: int = 1800` (added default)

All three method signatures now default to 1800 seconds (30 minutes), matching the pytest-timeout configuration.

## Benefits

1. **Consistent behavior**: Tests now have the same timeout whether run via pytest or Crackerjack
1. **No premature timeouts**: Subprocess wrapper no longer kills tests before pytest's timeout
1. **Proper timeout hierarchy**: pytest-timeout (1800s) > subprocess timeout (1800s)
1. **Better debugging**: Test failures are now actual test failures, not wrapper timeouts

## Validation

Run tests with:

```bash
python -m crackerjack run --run-tests --skip-hooks
```

Expected behavior:

- Tests passing with pytest directly should now also pass through Crackerjack
- No more "timeout" errors unless tests genuinely exceed 30 minutes

## Future Improvements

Consider making the subprocess timeout configurable via settings:

```python
class TestSettings(Settings):
    test_timeout: int = 1800  # pytest timeout
    subprocess_timeout: int = 1800  # subprocess wrapper timeout (can be higher)
```

This would allow:

- subprocess_timeout > test_timeout for safety margin
- Different timeouts for different test scenarios
- Override via settings/crackerjack.yaml
