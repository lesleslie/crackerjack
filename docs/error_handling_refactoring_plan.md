# Error Handling Decorator Refactoring Plan

## Current Complexity Violations

1. **`retry` decorator** - Complexity: 42

   - Lines 305-362
   - Issues: Nested decorator pattern, async/sync branching, retry logic with backoff

1. **`graceful_degradation`** - Complexity: 21

   - Lines 520-597
   - Issues: Nested decorator pattern, async/sync branching, warning logic, callable fallback handling

1. **`validate_args`** - Complexity: 21

   - Lines 474-517
   - Issues: Nested decorator pattern, async/sync branching, type checking, validator iteration

1. **`_safe_console_print`** - Complexity: 21

   - Lines 29-69
   - Issues: Retry loop, exception handling, errno checking, fallback logic

## Refactoring Strategy

### 1. `_safe_console_print` (21 → ≤15)

**Extract helpers:**

- `_is_would_block_error(e: Exception) -> bool` - Check if error is EAGAIN/EWOULDBLOCK
- `_fallback_stderr_write(message: str, include_traceback: bool)` - Final fallback write

**Result:** Main function focuses on retry loop, delegates error detection and fallback

### 2. `retry` (42 → ≤15)

**Extract helpers:**

- `_create_async_retry_wrapper()` - Async retry wrapper creation
- `_create_sync_retry_wrapper()` - Sync retry wrapper creation
- `_execute_with_retry()` - Core retry logic (can be shared pattern)

**Result:** Decorator becomes a simple dispatcher, each wrapper has focused retry logic

### 3. `graceful_degradation` (21 → ≤15)

**Extract helpers:**

- `_handle_degradation_error()` - Warning + fallback resolution logic
- `_create_async_degradation_wrapper()` - Async wrapper creation
- `_create_sync_degradation_wrapper()` - Sync wrapper creation

**Result:** Clean separation of error handling, warning, and wrapper creation

### 4. `validate_args` (21 → ≤15)

**Extract helpers:**

- `_normalize_validators()` - Convert single validators to lists
- `_create_validator_function()` - Build the validation closure
- Already has: `_create_async_validation_wrapper()`, `_create_sync_validation_wrapper()`

**Result:** Decorator becomes a simple orchestrator of validator normalization and wrapper creation

## Implementation Order

1. Start with `_safe_console_print` (simplest, foundational)
1. Refactor `retry` (most complex, biggest impact)
1. Refactor `graceful_degradation` (similar pattern to retry)
1. Refactor `validate_args` (already partially extracted)

## Testing Strategy

- All existing tests must pass unchanged
- No functional behavior changes
- Preserve all error messages and logging
- Verify complexity reduction with Ruff

## Success Criteria

✅ All functions ≤15 complexity
✅ All tests pass
✅ No functional changes
✅ Clear, descriptive helper names
✅ Preserved logging/console output
