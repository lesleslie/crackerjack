# AI Autofix Bugs - Analysis and Fix Plan

**Date**: 2026-01-21
**Status**: Analysis Complete, Fixes Pending
**Priority**: HIGH

______________________________________________________________________

## Problem Description

The AI agent autofix system has three critical bugs:

1. **Issue Miscounting**: Reports "225 issues to fix" when actual count is 189 (167+18+3+1)
1. **False Success**: Claims "All issues resolved in 1 iteration!" when same 189 errors persist
1. **Failed Fixes**: AI agents claim success but no actual fixes are applied

### Example from session-buddy run:

```
→ Iteration 1/5: 225 issues to fix
✓ All issues resolved in 1 iteration(s)!
✅ AI agents applied fixes, retrying comprehensive hooks...

[Same errors persist]
- zuban :: FAILED | issues=167
- pyscn :: FAILED | issues=18
- creosote :: FAILED | issues=3
- refurb :: FAILED | issues=1
```

______________________________________________________________________

## Root Cause Analysis

### Bug 1: Issue Miscounting (225 vs 189)

**Location**: `crackerjack/core/autofix_coordinator.py:_parse_hook_results_to_issues()`

**Problem**:

- `_parse_hook_results_to_issues()` creates Issue objects from hook output
- For zuban/mypy output, each line becomes an Issue object
- Multi-line errors (error line + note lines) may be counted multiple times
- Example zuban output:
  ```
  file.py:10: error: Message
  file.py:10: note: Suggestion
  ```
  This creates 2 Issue objects instead of 1

**Evidence**:

- Line 506-517: Parses all hook results and extends issues list
- Line 681-698: `_parse_type_checker_output()` processes each line separately
- Line 705-706: Only filters out "note" and "help" lines, but some slip through

### Bug 2: False Success Detection

**Location**: `crackerjack/core/autofix_coordinator.py:_apply_ai_agent_fixes()`

**Problem**:

- Line 341-343: Reports "All issues resolved" when `current_issue_count == 0`
- This triggers when `_collect_current_issues()` returns empty list
- `_collect_current_issues()` (line 572-636) runs hardcoded check commands that may fail silently:
  - Line 585: `f"./{pkg_name}"` assumes package directory exists
  - Line 613-628: Try/except catches exceptions but only logs warnings
  - If all commands fail, returns empty issues list → False success!

**Evidence**:

- User's console shows same 189 errors before and after "fix"
- Success message printed immediately after iteration 1
- No actual code changes occurred

### Bug 3: Failed Fixes

**Location**: `crackerjack/core/autofix_coordinator.py:_run_ai_fix_iteration()`

**Problem**:

- Line 464-493: Checks `fixes_count > 0` to determine if fixes were applied
- Line 484-493: If `not fix_result.success and remaining_count > 0`, warns and returns False
- **BUT**: If `fix_result.success=True` with `remaining_count > 0`, returns True anyway!
- This happens because AgentCoordinator merges results with AND logic:
  ```python
  # coordinator.py:56-68
  success=self.success and other.success  # All agents must succeed
  ```
- If some agents can't fix issues but others succeed, overall success=True with remaining_issues

**Evidence**:

- "All issues resolved" printed but errors persist
- No git changes, no file modifications
- AI agents likely can't handle session-buddy specific issues

______________________________________________________________________

## Implementation Plan

### Fix 1: Improve Issue Parsing Accuracy

**File**: `crackerjack/core/autofix_coordinator.py`

**Changes**:

1. **Deduplicate issues by location** (Line 506-517):

   ```python
   def _parse_hook_results_to_issues(self, hook_results: Sequence[object]) -> list[Issue]:
       issues: list[Issue] = []
       # ... existing parsing ...

       # NEW: Deduplicate by (file_path, line_number, message)
       seen = set()
       unique_issues = []
       for issue in issues:
           key = (issue.file_path, issue.line_number, issue.message)
           if key not in seen:
               seen.add(key)
               unique_issues.append(issue)

       self.logger.info(f"Parsed {len(issues)} issues, {len(unique_issues)} unique")
       return unique_issues
   ```

1. **Better multi-line error handling** (Line 700-707):

   ```python
   def _should_parse_line(self, line: str) -> bool:
       if not line:
           return False
       # Skip all contextual note/help lines
       if any(pattern in line.lower() for pattern in [": note:", ": help:", "note: ", "help: "]):
           return False
       # Skip summary lines
       if line.startswith(("Found", "Checked", "N errors found")):
           return False
       return True
   ```

### Fix 2: Fix False Success Detection

**File**: `crackerjack/core/autofix_coordinator.py`

**Changes**:

1. **Validate issue collection success** (Line 572-636):

   ```python
   def _collect_current_issues(self) -> list[Issue]:
       all_issues: list[Issue] = []

       for cmd, hook_name, timeout in check_commands:
           try:
               result = subprocess.run(cmd, ...)

               # NEW: Verify command actually ran
               if result.returncode is None:
                   self.logger.error(f"Command {hook_name} did not run")
                   continue

               # NEW: Only add issues if output is valid
               if result.returncode != 0 or result.stdout:
                   hook_issues = self._parse_hook_to_issues(...)

                   # NEW: Validate parsed issues
                   if hook_issues:
                       all_issues.extend(hook_issues)
                       self.logger.debug(f"{hook_name}: {len(hook_issues)} issues")

           except subprocess.TimeoutExpired:
               self.logger.warning(f"Timeout running {hook_name}")
           except Exception as e:
               self.logger.error(f"Error running {hook_name}: {e}")

       # NEW: Verify collection was successful
       if not all_issues and self.pkg_path.exists():
           self.logger.warning(
               f"No issues collected but expected issues - check commands may have failed"
           )

       return all_issues
   ```

1. **Verify actual fixes were applied** (Line 341-343):

   ```python
   # BEFORE:
   if current_issue_count == 0:
       self._report_iteration_success(iteration)
       return True

   # AFTER:
   if current_issue_count == 0:
       # NEW: Verify this isn't a false positive
       if iteration > 0:  # Only after at least one fix attempt
           # Double-check by running hooks again
           verification_issues = self._collect_current_issues()
           if not verification_issues:
               self._report_iteration_success(iteration)
               return True
           else:
               self.logger.warning(
                   f"False success detected: {len(verification_issues)} issues remain"
               )
               # Continue fixing
       else:
           self._report_iteration_success(iteration)
           return True
   ```

### Fix 3: Fix Success Detection Logic

**File**: `crackerjack/core/autofix_coordinator.py`

**Changes**:

1. **Require remaining_count == 0 for success** (Line 489-493):

   ```python
   # BEFORE:
   if fixes_count > 0:
       # ... logging ...
       if remaining_count > 0:
           # Log partial progress
       return True  # BUG: Returns True even with remaining issues!

   # AFTER:
   if fixes_count > 0:
       self.logger.info(
           f"Fixed {fixes_count} issues with confidence {fix_result.confidence:.2f}"
       )

       # CHANGED: Only return True if ALL issues fixed
       if remaining_count == 0:
           self.logger.info("All issues fixed")
           return True
       else:
           self.console.print(
               f"[yellow]⚠ Partial progress: {fixes_count} fixes applied, "
               f"{remaining_count} issues remain[/yellow]"
           )
           # Continue to next iteration instead of returning True
           return False  # CHANGED: Continue fixing
   ```

1. **Add validation step after each iteration** (Line 362-365):

   ```python
   if not self._run_ai_fix_iteration(coordinator, loop, issues):
       # NEW: Verify this isn't a recoverable failure
       verification_issues = self._collect_current_issues()
       if len(verification_issues) < current_issue_count:
           # Progress made, continue
           previous_issue_count = len(verification_issues)
           continue
       else:
           # No progress, stop
       return False
   ```

### Fix 4: Make Issue Collection Robust

**File**: `crackerjack/core/autofix_coordinator.py`

**Changes**:

1. **Dynamic path detection** (Line 577):

   ```python
   # BEFORE:
   pkg_name = self.pkg_path.name
   cmd = ["uv", "run", "zuban", "mypy", f"./{pkg_name}"]

   # AFTER:
   # Detect package directory
   pkg_dirs = [
       self.pkg_path / self.pkg_path.name,  # crackerjack/crackerjack
       self.pkg_path,  # crackerjack
   ]
   pkg_dir = None
   for d in pkg_dirs:
       if d.exists() and d.is_dir():
           pkg_dir = d
           break

   if not pkg_dir:
       self.logger.error(f"Cannot find package directory in {self.pkg_path}")
       pkg_dir = self.pkg_path  # Fallback

   cmd = ["uv", "run", "zuban", "mypy", "--config-file", "mypy.ini", str(pkg_dir)]
   ```

1. **Add fallback collection** (Line 632):

   ```python
   # NEW: If all commands fail, try parsing hook results
   if not all_issues:
       self.logger.warning("Primary collection failed, using hook result parsing")
       # This uses the original hook results passed to the function
       all_issues = self._parse_fallback_results()

   return all_issues
   ```

______________________________________________________________________

## Testing Plan

1. **Unit Tests**:

   - Test issue parsing with various tool outputs
   - Test deduplication logic
   - Test success detection with various FixResult scenarios

1. **Integration Tests**:

   - Run autofix on known issues
   - Verify issue count accuracy
   - Verify no false success claims

1. **Manual Testing**:

   - Run on session-buddy with AI fix enabled
   - Verify actual issues match reported count
   - Verify fixes are actually applied

______________________________________________________________________

## Rollback Plan

If fixes cause regressions:

1. Revert specific changes via git
1. Keep improved logging for debugging
1. File follow-up issues for remaining problems

______________________________________________________________________

## Success Criteria

✅ Issue count matches actual errors (within 5% tolerance)
✅ No false success claims when issues persist
✅ AI agents either apply actual fixes or accurately report failure
✅ Console output reflects reality
