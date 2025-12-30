# Implementation Plan: Logging & Progress Bar Fixes

**Date**: 2025-11-26
**Status**: Ready for Review
**Complexity**: Medium

______________________________________________________________________

## Problem Statement

### Issue 1: Unwanted Logging Output

Logging messages appear when running `python -m crackerjack run` without `--debug` flag:

```
2025-11-26 02:29:41 [info] Application started [acb.adapters.logger.structlog]
[ 2025-11-26 02:29:04.095 ] INFO in acb.adapters.logger[ 298 ] App path: /Users/les/Projects/session-mgmt-mcp
INFO: Registering LoggerProtocol with fresh logger instance
```

**Expected Behavior by Flag**:

- **No flags**: Clean output, no logging messages
- **`--verbose`**: More detailed progress information (not low-level logs)
- **`--debug`**: ALL logging output including ACB internals

______________________________________________________________________

### Issue 2: Progress Bar Repetition

Progress bars show repeated output instead of updating on the same line, making the output verbose and difficult to read.

**Expected**: Progress bars should update in-place on a single line (standard Rich behavior).

______________________________________________________________________

## Root Cause Analysis

### Logging Issue Root Causes

#### 1. **ACB Logger Auto-Initialization** (PRIMARY)

**File**: `.venv/lib/python3.13/site-packages/acb/logger.py:61-104`

ACB's logger automatically initializes at **module import time** and calls `_log_app_info()`, which unconditionally logs startup information:

```python
def _initialize_logger() -> None:
    """Initialize logger during import, unless in testing mode."""
    if _is_testing():
        return

    logger_class = _get_logger_adapter()
    logger_instance = logger_class()
    logger_instance.init()  # ← This calls _log_app_info()
    depends.set(logger_class, logger_instance)
```

**Location of Messages**:

- `acb/adapters/logger/structlog.py:320-328` - "Application started" message
- `acb/adapters/logger/loguru.py:296-299` - "App path" message

#### 2. **Dependency Guard Warnings** (SECONDARY)

**File**: `crackerjack/utils/dependency_guard.py:17-94`

The `ensure_logger_dependency()` function prints INFO/WARNING messages to stdout when validating logger registration:

```python
# Line 86
print("INFO: Registering LoggerProtocol with fresh logger instance")

# Line 30
print(
    "WARNING: Logger dependency was registered as empty tuple, replacing with fresh instance"
)
```

#### 3. **Config Module Side-Effects** (TERTIARY)

**File**: `crackerjack/config/__init__.py:110-133`

Logger initialization happens during config module import, triggering ACB's startup logging before CLI flags are processed.

### Progress Bar Issue Root Causes

#### 1. **Conflicting Transient Settings**

**Hook Progress**: `transient=False` (persists after completion)
**Test Progress**: `transient=True` (clears after completion)

This inconsistency doesn't directly cause repetition but creates visual confusion.

#### 2. **Possible Terminal Detection Issues**

No explicit terminal mode detection (`force_terminal`, `is_terminal`) found in progress bar initialization. Rich may not be detecting interactive terminal correctly.

#### 3. **ACB Console Wrapper Abstraction**

Using ACB's Console wrapper may hide Rich's terminal detection configuration that controls live-updating behavior.

______________________________________________________________________

## Proposed Solutions

### Solution 1: Control ACB Logger Verbosity

#### Verbosity Level Definitions

| Flag Combination | ACB Logger Level | STDOUT Output | STDERR Output | Use Case |
|------------------|------------------|---------------|---------------|----------|
| **None** | WARNING | Clean progress bars only | Silent (no JSON) | Default production use |
| **`--verbose`** | WARNING | Detailed progress info | Silent (no JSON) | User wants more context |
| **`--debug`** | DEBUG | ALL logging (human-readable) | Structured JSON logs | Troubleshooting/development |

**Key Principles**:

- `--verbose` is for **user-facing** detailed information (stdout only)
- `--debug` is for **developer-level** logging (stdout + structured JSON to stderr)
- Structured JSON logging should **always go to stderr** (never stdout)
- Default mode suppresses ALL logging (clean UX)

#### A. Suppress Auto-Initialization Logging (RECOMMENDED)

**Approach**: Set environment variables before ACB logger initializes to control startup verbosity AND disable stderr JSON output by default.

**Implementation**: Add early environment setup in `crackerjack/__main__.py` BEFORE any imports:

```python
# At the very top of __main__.py, before all imports
import sys
import os

# Suppress ACB logger startup messages by default
# Disable stderr JSON sink unless --debug is provided
if "--debug" not in sys.argv:
    os.environ["ACB_LOGGER_DEBUG_MODE"] = "0"
    os.environ["ACB_LOG_LEVEL"] = "WARNING"
    os.environ["ACB_DISABLE_STRUCTURED_STDERR"] = "1"  # Disable JSON to stderr
```

**Rationale**:

- ACB's structlog adapter enables stderr JSON output by default (`enable_stderr_sink: True`)
- Users don't need structured JSON logs during normal operation
- Only developers debugging need machine-readable JSON logs
- Setting `ACB_DISABLE_STRUCTURED_STDERR=1` turns off stderr JSON sink early

**Challenge**: This happens before argument parsing, but `sys.argv` check is sufficient for early suppression.

#### B. Reconfigure Logger After CLI Parse

**Approach**: After parsing CLI flags, ensure logger is at correct verbosity level AND enable stderr JSON sink for debug mode.

**Implementation**: Add logger reconfiguration in `__main__.py` after flag processing:

```python
# After line 293-296 where flags are processed
def _configure_logger_verbosity(debug: bool, verbose: bool) -> None:
    """Configure logger verbosity and output streams based on CLI flags.

    Output Configuration:
    - No flags: WARNING level, stdout only (no stderr JSON)
    - --verbose: WARNING level, stdout only (no stderr JSON)
    - --debug: DEBUG level, stdout + stderr JSON (full structured logging)
    """
    from acb.depends import depends
    from crackerjack.models.protocols import LoggerProtocol

    try:
        logger = depends.get_sync(LoggerProtocol)
        if debug:
            # Enable full debug logging + structured JSON to stderr
            if hasattr(logger, "_logger"):
                logger._logger.setLevel("DEBUG")
            os.environ["ACB_LOG_LEVEL"] = "DEBUG"
            os.environ["CRACKERJACK_DEBUG"] = "1"
            # Enable stderr JSON sink for structured logging
            if "ACB_DISABLE_STRUCTURED_STDERR" in os.environ:
                del os.environ["ACB_DISABLE_STRUCTURED_STDERR"]
            os.environ["ACB_FORCE_STRUCTURED_STDERR"] = "1"
        else:
            # Keep clean output (WARNING level, no stderr JSON)
            if hasattr(logger, "_logger"):
                logger._logger.setLevel("WARNING")
            os.environ["ACB_LOG_LEVEL"] = "WARNING"
            # Ensure stderr JSON remains disabled
            os.environ["ACB_DISABLE_STRUCTURED_STDERR"] = "1"
    except Exception:
        pass  # Logger not available yet


# Call after flag processing
_configure_logger_verbosity(debug=debug, verbose=verbose)
```

#### C. Silence Dependency Guard Prints (REQUIRED)

**Approach**: Replace `print()` statements with conditional logging based on `--debug` flag.

**File**: `crackerjack/utils/dependency_guard.py`

**Changes**:

```python
import os


def _should_log_debug() -> bool:
    """Check if debug logging is enabled."""
    return os.environ.get("CRACKERJACK_DEBUG") == "1"


# Before (Line 86)
print("INFO: Registering LoggerProtocol with fresh logger instance")

# After
if _should_log_debug():
    print("INFO: Registering LoggerProtocol with fresh logger instance")
```

Apply to all INFO/WARNING messages in the file (lines 30, 62, 86).

______________________________________________________________________

### Solution 2: Fix Progress Bar Behavior

#### A. Standardize Transient Setting (RECOMMENDED)

**Approach**: Use consistent `transient=True` for both hook and test progress bars to ensure they update in-place and clear after completion.

**File**: `crackerjack/executors/progress_hook_executor.py:120-139`

**Change**:

```python
def _create_progress_bar(self) -> Progress:
    """Create configured progress bar with appropriate columns."""
    return Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}", justify="left"),
        BarColumn(bar_width=20),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=self.console,
        transient=True,  # ← Changed from False to True (consistent with test progress)
        refresh_per_second=10,  # Explicit refresh rate for smooth updates
    )
```

**Rationale**:

- Test progress already uses `transient=True`
- Consistency prevents visual artifacts
- Progress bars should clear on success (standard CLI behavior)
- Error output will still be visible (comes after progress completes)

#### B. Add Explicit Terminal Detection (IF NEEDED)

**Approach**: Configure Rich Console with explicit terminal mode detection if standardizing transient doesn't fully resolve the issue.

**File**: `crackerjack/config/__init__.py` (where Console is initialized)

**Add**:

```python
def _create_rich_console() -> Console:
    """Create Rich console with proper terminal detection."""
    import sys
    from rich.console import Console as RichConsole

    # Detect if we're in an interactive terminal
    is_interactive = sys.stdout.isatty() and sys.stderr.isatty()

    return RichConsole(
        width=get_console_width(),
        force_terminal=is_interactive,
        force_interactive=is_interactive,
    )
```

______________________________________________________________________

## Implementation Strategy

### Phase 1: Logging Fixes (High Priority)

#### Step 1.1: Early ACB Logger Suppression + Disable Stderr JSON

**File**: `crackerjack/__main__.py` (Top of file, before imports)

```python
"""Crackerjack - Opinionated Python project management tool."""

import sys
import os

# Suppress ACB logger startup messages and stderr JSON unless --debug is provided
# Must happen before any ACB imports
if "--debug" not in sys.argv:
    os.environ["ACB_LOGGER_DEBUG_MODE"] = "0"
    os.environ["ACB_LOG_LEVEL"] = "WARNING"
    os.environ["ACB_DISABLE_STRUCTURED_STDERR"] = "1"  # No JSON to stderr by default

# Now safe to import ACB-dependent modules
import asyncio
import typing as t
# ... rest of imports
```

**Key Change**: Added `ACB_DISABLE_STRUCTURED_STDERR` to prevent JSON logging to stderr during normal operation.

#### Step 1.2: Silence Dependency Guard Prints

**File**: `crackerjack/utils/dependency_guard.py`

Add helper function at top:

```python
import os


def _should_log_debug() -> bool:
    """Check if debug logging is enabled via CRACKERJACK_DEBUG env var."""
    return os.environ.get("CRACKERJACK_DEBUG") == "1"
```

Modify all print statements:

- Line 30: `if _should_log_debug(): print("WARNING: ...")`
- Line 62: `if _should_log_debug(): print("WARNING: ...")`
- Line 86: `if _should_log_debug(): print("INFO: ...")`

#### Step 1.3: Post-Parse Logger Configuration + Enable Stderr JSON for Debug

**File**: `crackerjack/__main__.py` (After line 296)

```python
# After setup_debug_and_verbose_flags() call
def _configure_logger_verbosity(debug: bool) -> None:
    """Configure logger verbosity and stderr JSON output.

    Stream Configuration:
    - Default/Verbose: WARNING level, no stderr JSON (clean UX)
    - Debug: DEBUG level, enable stderr JSON (structured logs for troubleshooting)
    """
    if debug:
        os.environ["ACB_LOG_LEVEL"] = "DEBUG"
        os.environ["CRACKERJACK_DEBUG"] = "1"
        # Enable structured JSON logging to stderr for debug mode
        if "ACB_DISABLE_STRUCTURED_STDERR" in os.environ:
            del os.environ["ACB_DISABLE_STRUCTURED_STDERR"]
        os.environ["ACB_FORCE_STRUCTURED_STDERR"] = "1"
    # If not debug, keep WARNING level and disabled stderr JSON from early init


_configure_logger_verbosity(debug=debug)
```

**Key Addition**: Debug mode now explicitly enables stderr JSON sink via `ACB_FORCE_STRUCTURED_STDERR`.

### Phase 2: Progress Bar Fixes (Medium Priority)

#### Step 2.1: Standardize Transient Setting

**File**: `crackerjack/executors/progress_hook_executor.py` (Line 132)

Change:

```python
transient = (True,)  # Consistent with test progress - clears after completion
refresh_per_second = (10,)  # Smooth single-line updates
```

#### Step 2.2: Test Across Workflows

Run comprehensive tests:

```bash
python -m crackerjack run --run-tests
python -m crackerjack run
python -m crackerjack run --verbose
python -m crackerjack run --debug
```

______________________________________________________________________

## Testing Plan

### Test Case 1: Default Run (No Flags)

```bash
python -m crackerjack run
```

**Expected**:

- ✅ No "Application started" messages
- ✅ No "App path" messages
- ✅ No "Registering LoggerProtocol" messages
- ✅ Progress bar updates on single line
- ✅ Progress bar clears after completion
- ✅ Clean, production-ready output

### Test Case 2: Verbose Mode

```bash
python -m crackerjack run --verbose
```

**Expected**:

- ✅ NO ACB startup messages (not user-facing detail)
- ✅ NO JSON output to stderr (stderr should be silent)
- ✅ More detailed progress descriptions on stdout
- ✅ Enhanced user-facing information
- ✅ Progress bar updates on single line
- ✅ Log level still at WARNING (no low-level logs)

### Test Case 3: Debug Mode

```bash
python -m crackerjack run --debug
```

**Expected**:

- ✅ Full logging output to stdout (ACB startup messages visible)
- ✅ Structured JSON logs to stderr (machine-readable format)
- ✅ Dependency guard messages visible on stdout
- ✅ "Application started" message appears on stdout
- ✅ "Registering LoggerProtocol" appears on stdout
- ✅ Progress bar updates on single line (stdout)
- ✅ ALL internal logging visible on stdout
- ✅ Stderr contains only structured JSON logs (no progress bars)

### Test Case 4: AI Debug Mode

```bash
python -m crackerjack run --ai-debug --run-tests
```

**Expected**:

- ✅ Structured JSON logging to stderr (for AI consumption)
- ✅ Human-readable output to stdout
- ✅ AI agent debug messages on stdout
- ✅ ACB logger messages on stdout (debug mode active)
- ✅ Progress bars for both hooks and tests update cleanly on stdout
- ✅ Clean separation: stderr = JSON only, stdout = human-readable + progress

### Test Case 5: With Tests

```bash
python -m crackerjack run --run-tests
```

**Expected**:

- ✅ No unwanted logging
- ✅ Hook progress bar updates in-place
- ✅ Test progress bar updates in-place
- ✅ Both progress bars clear after completion

______________________________________________________________________

## Risk Assessment

### Logging Fixes

**Risk Level**: Low
**Reason**: Changes are isolated to verbosity control, no functional logic affected

**Potential Issues**:

- Early `sys.argv` check may miss unusual argument formats
- ACB logger may have internal state that resists reconfiguration

**Mitigation**:

- Test with various argument formats (`-d`, `--debug`, combined flags)
- Keep `--debug` behavior unchanged (show everything)
- Document expected verbosity levels clearly

### Progress Bar Fixes

**Risk Level**: Low-Medium
**Reason**: Changes core user experience (visual output)

**Potential Issues**:

- Changing `transient=True` may hide important error context
- Terminal detection changes could break non-interactive environments (CI/CD)

**Mitigation**:

- Test in multiple terminal environments (term, Terminal.app, VSCode)
- Verify CI/CD pipeline output remains readable
- Keep fallback behavior for non-TTY environments
- Error messages print AFTER progress clears (still visible)

______________________________________________________________________

## Files to Modify

### Phase 1: Logging Fixes (Priority 1)

1. **`crackerjack/__main__.py`**

   - Add early ACB logger suppression (top of file)
   - Add post-parse logger configuration (after line 296)

1. **`crackerjack/utils/dependency_guard.py`**

   - Add `_should_log_debug()` helper
   - Wrap print statements at lines 30, 62, 86

### Phase 2: Progress Bar Fixes (Priority 2)

1. **`crackerjack/executors/progress_hook_executor.py`**
   - Change `transient=False` to `transient=True` (line 132)
   - Add `refresh_per_second=10`

### Optional: Terminal Detection (If Needed)

1. **`crackerjack/config/__init__.py`**
   - Add explicit terminal detection (only if Phase 2 insufficient)

______________________________________________________________________

## Success Criteria

1. ✅ Running `python -m crackerjack run` shows NO ACB logger startup messages on stdout
1. ✅ Running `python -m crackerjack run` produces NO output to stderr (silent)
1. ✅ Running `python -m crackerjack run --verbose` shows NO low-level logs (user detail only on stdout)
1. ✅ Running `python -m crackerjack run --verbose` produces NO output to stderr (silent)
1. ✅ Running `python -m crackerjack run --debug` shows ALL logging output on stdout
1. ✅ Running `python -m crackerjack run --debug` produces structured JSON logs to stderr ONLY
1. ✅ Progress bars update on single line (no repetition)
1. ✅ Progress bars clear after completion (transient behavior)
1. ✅ All existing tests pass
1. ✅ CI/CD pipeline output remains readable (stdout for humans, stderr for machines)
1. ✅ External projects (session-mgmt-mcp) benefit from fixes

______________________________________________________________________

## Rollback Plan

If issues arise:

1. Remove early environment variable setting in `__main__.py`
1. Restore print statements in `dependency_guard.py`
1. Revert `transient=True` → `transient=False` change
1. Git commit: `git revert <commit-hash>`

______________________________________________________________________

## Implementation Order

1. ✅ **Plan created and documented**
1. **Review with specialized agents** (code-reviewer, python-pro)
1. **Implement Phase 1** (logging fixes)
1. **Test logging behavior** across all flag combinations
1. **Implement Phase 2** (progress bar fixes)
1. **Test progress bar behavior** across workflows
1. **Run full quality workflow** (`python -m crackerjack run --run-tests`)
1. **Update changelog and documentation**

______________________________________________________________________

## Next Steps

Ready for agent review and implementation approval.
