# Root Cause Analysis: Hooks Showing "1 issue" Instead of Actual Count

## Problem Statement

From user testing in `../acb` project:

- **ruff-check**: Correctly shows 95 E402 violations ✅
- **ruff-format**: Shows "1 issue" but has 0 actual issues (config error) ❌
- **codespell**: Shows "1 issue" but has 0 actual issues (config error) ❌
- **complexipy**: Shows "1 issue" but has 0 violations above threshold ❌

## Root Cause

**Location**: `crackerjack/orchestration/hook_orchestrator.py:939-956`

```python
def _calculate_total_issues(
    self, qa_result: t.Any, status: str, issues: list[str]
) -> int:
    """Calculate the total count of issues from qa_result."""
    # Get the actual total count of issues from qa_result
    # This may be larger than len(issues) if issues were truncated for display
    total_issues = (
        qa_result.issues_found if hasattr(qa_result, "issues_found") else len(issues)
    )

    # Ensure failed hooks always have at least 1 issue count
    if status == "failed":
        total_issues = max(total_issues, 1)  # ← THIS IS THE BUG

    return total_issues
```

### The Bug

**Line 952-953**: `max(total_issues, 1)` forces failed hooks to show at least "1 issue" even when:

- No actual code issues were found (`qa_result.issues_found = 0`)
- The failure is due to a configuration error
- The failure is due to a tool error (missing binary, invalid args, etc.)

### Why This Happens

1. **Tool Configuration Errors**: When tools like ruff-format or codespell have config issues:

   - They exit with code 1
   - Adapter returns `QAResult(status=ERROR, issues_found=0)`
   - `_determine_status()` returns `"failed"` (line 838)
   - `_calculate_total_issues()` forces `max(0, 1) = 1`
   - Display shows "1 issue"

1. **Reporting Tools with No Violations**: When tools like complexipy find no violations:

   - They exit with code 0
   - Adapter returns `QAResult(status=SUCCESS, issues_found=0)`
   - `_determine_status()` returns `"passed"` (line 836)
   - Display shows "0 issues" ✅ (this case works correctly)

## Data Flow Example

### Case 1: ruff-format with config error

```
RuffAdapter.check()
↓
ToolExecutionResult(exit_code=1, raw_output="", error_output="Config error")
↓
RuffAdapter.parse_output() → [] (no issues parsed)
↓
QAResult(
    status=ERROR,
    issues_found=0,  # No parseable issues
    details=""
)
↓
_determine_status() → "failed" (because status=ERROR)
↓
_build_issues_list() → [] (no details)
↓
_extract_error_details() → ["Hook ruff-format failed with no detailed output (exit code: 1)"]
↓
_calculate_total_issues(qa_result.issues_found=0, status="failed")
   → max(0, 1) = 1  ← FORCED TO 1
↓
HookResult(
    issues_found=["Hook ruff-format failed with no detailed output (exit code: 1)"],
    issues_count=1  ← Shows "1 issue" in display
)
```

### Case 2: ruff-check with 95 violations (works correctly)

```
RuffAdapter.check()
↓
ToolExecutionResult(exit_code=1, raw_output="[JSON with 95 violations]")
↓
RuffAdapter.parse_output() → [95 ToolIssue objects]
↓
QAResult(
    status=FAILURE,
    issues_found=95,  # Actual count
    details="file1.py:1:1: E402...\n...\n... and 85 more issues"
)
↓
_determine_status() → "failed"
↓
_build_issues_list() → [10 detail lines] (truncated for display)
↓
_calculate_total_issues(qa_result.issues_found=95, status="failed")
   → max(95, 1) = 95  ✅ Correct count
↓
HookResult(
    issues_found=[...10 detail lines...],
    issues_count=95  ← Shows "95 issues" correctly
)
```

## Why Was This Design Decision Made?

The `max(total_issues, 1)` logic was likely added to ensure that failed hooks always show:

- **Something** in the issues column (not 0)
- **Visual indication** that the hook failed
- **Prevents confusion** where a failed hook shows "0 issues"

However, this creates a **misleading display** when:

1. The failure is a configuration error (not code issues)
1. The tool has an error (binary not found, invalid args)
1. The adapter couldn't parse the output

## Solution Options

### Option 1: Only force "1 issue" for errors WITHOUT exit codes

```python
def _calculate_total_issues(
    self, qa_result: t.Any, status: str, issues: list[str]
) -> int:
    """Calculate the total count of issues from qa_result."""
    total_issues = (
        qa_result.issues_found if hasattr(qa_result, "issues_found") else len(issues)
    )

    # Only force "1 issue" if hook truly failed with no parseable output
    # AND no exit code information (unexpected errors)
    if status == "failed":
        if total_issues == 0 and not hasattr(qa_result, "metadata"):
            # Unexpected failure - show "1 issue" to indicate problem
            total_issues = 1
        elif total_issues == 0 and qa_result.status != QAResultStatus.ERROR:
            # Tool found issues but adapter couldn't parse them
            total_issues = max(len(issues), 1)

    return total_issues
```

**Pros**:

- Fixes the misleading "1 issue" for config errors
- Preserves the safety net for unexpected failures
- Uses `qa_result.status` to distinguish error types

**Cons**:

- More complex logic
- May still show "1 issue" in some edge cases

### Option 2: Never force "1 issue" - trust the adapter

```python
def _calculate_total_issues(
    self, qa_result: t.Any, status: str, issues: list[str]
) -> int:
    """Calculate the total count of issues from qa_result."""
    return qa_result.issues_found if hasattr(qa_result, "issues_found") else len(issues)
```

**Pros**:

- Simple, clear logic
- Trusts the adapter's issue count
- No misleading "1 issue" for config errors

**Cons**:

- Failed hooks with no parseable output will show "0 issues"
- Users might be confused why a failed hook shows "0"
- Loses the visual cue in the issues column

### Option 3: Use exit code or status to determine behavior (RECOMMENDED)

```python
def _calculate_total_issues(
    self, qa_result: t.Any, status: str, issues: list[str]
) -> int:
    """Calculate the total count of issues from qa_result."""
    total_issues = (
        qa_result.issues_found if hasattr(qa_result, "issues_found") else len(issues)
    )

    # Only force "1 issue" for genuine parsing failures (not config/tool errors)
    if status == "failed" and total_issues == 0:
        # Check if this is a config/tool error vs parsing failure
        if hasattr(qa_result, "status") and qa_result.status == QAResultStatus.ERROR:
            # Config/tool error - show actual count (0)
            return 0
        else:
            # Parsing failure - show "1" to indicate problem
            return 1

    return total_issues
```

**Pros**:

- Distinguishes between config errors (show 0) and parsing failures (show 1)
- Uses `QAResultStatus.ERROR` as the discriminator
- Clear semantic distinction

**Cons**:

- Assumes adapters correctly set `status=ERROR` for config issues

## Recommended Fix

**Option 3** is the recommended solution because:

1. It uses the existing `QAResultStatus` enum to distinguish error types
1. Config/tool errors (status=ERROR) show 0 issues (truthful)
1. Parsing failures (status=FAILURE) can still show 1 issue if needed
1. Preserves semantic correctness while maintaining useful visual cues

## Testing Plan

### Test Cases

1. **Hook with config error** (ruff-format, codespell):

   - qa_result.status = ERROR
   - qa_result.issues_found = 0
   - Expected: issues_count = 0

1. **Hook with code violations** (ruff-check with 95 E402s):

   - qa_result.status = FAILURE
   - qa_result.issues_found = 95
   - Expected: issues_count = 95

1. **Reporting tool with no violations** (complexipy):

   - qa_result.status = SUCCESS
   - qa_result.issues_found = 0
   - Expected: status="passed", issues_count = 0

1. **Hook with parsing failure** (tool output in unexpected format):

   - qa_result.status = FAILURE
   - qa_result.issues_found = 0
   - Expected: issues_count = 1 (or 0, depending on implementation)

## Files to Modify

1. `crackerjack/orchestration/hook_orchestrator.py`:

   - Modify `_calculate_total_issues()` (lines 939-956)

1. `tests/unit/orchestration/test_hook_result_details.py`:

   - Add test for config error case
   - Add test for parsing failure case

1. `tests/integration/test_hook_reporting_e2e.py`:

   - Add end-to-end test with actual tool config error

## Impact Assessment

### Breaking Changes

- **None** - This is a bug fix for misleading display

### Affected Components

- Hook result display in phase coordinator
- MCP server status reporting
- Any code that relies on `issues_count` field

### Backward Compatibility

- Fully compatible - only changes the `issues_count` value
- No changes to HookResult structure or API
