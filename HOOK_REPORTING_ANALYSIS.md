# Hook Reporting Issue Analysis

## Executive Summary

The hook reporting system has two distinct issues that cause misleading output:

1. **Fast hooks (ruff-format, codespell, ruff-check)**: Show "1 issue" with no details
2. **Comprehensive hooks (complexipy)**: Show "Hook failed with no detailed output"

Both issues stem from how adapter errors are handled and reported in the orchestrator.

## Root Cause Analysis

### Issue 1: Fast Hooks Showing "1 Issue" with No Details

**Location**: `crackerjack/orchestration/hook_orchestrator.py:903-905`

```python
if not issues:
    # Failed hook with no details and no issues
    issues = [
        f"Hook {hook.name} failed with no detailed output (exit code: {qa_result.exit_code if hasattr(qa_result, 'exit_code') else 'unknown'})"
    ]
```

**Problem Flow**:
1. Adapter executes successfully but finds issues
2. Adapter returns `QAResult` with `issues_found > 0` but `details=""` or `None`
3. `_build_issues_list()` tries to parse `details` but finds nothing
4. `_extract_error_details()` creates fallback generic message
5. Table shows `issues_count=1` (the generic message) instead of actual issue count

**Actual vs Expected**:
- **Actual**: `ruff-format FAILED 5.31s 1` with message "Hook ruff-format failed with no detailed output"
- **Expected**: `ruff-format FAILED 5.31s 15` with actual file/line details

### Issue 2: Complexipy Not Showing Issue Details

**Location**: `crackerjack/adapters/_tool_adapter_base.py:514-532`

```python
# Build details from issues
details_lines = []
for issue in issues[:10]:  # Limit to first 10 for readability
    loc = str(issue.file_path)
    if issue.line_number:
        loc += f":{issue.line_number}"
    if issue.column_number:
        loc += f":{issue.column_number}"
    details_lines.append(f"{loc}: {issue.message}")

if len(issues) > 10:
    details_lines.append(f"... and {len(issues) - 10} more issues")

return QAResult(
    status=status,
    message=message,
    details="\n".join(details_lines),
    files_checked=target_files,
    files_modified=exec_result.files_modified,
    issues_found=len(issues),
)
```

**Problem**: The base adapter **DOES** build details correctly, so the issue must be in:
1. How complexipy adapter parses its output
2. How the result is passed through the orchestrator
3. How the phase coordinator displays it

**Key Suspect**: `complexipy.json` file reading
- Complexipy outputs to `complexipy.json` file
- If file doesn't exist or is malformed, falls back to stdout parsing
- Fallback may be failing silently

## Code Flow Diagram

```
1. HookOrchestrator._execute_single_hook()
   └─> 2. HookOrchestrator._run_adapter()
       └─> 3. ComplexipyAdapter.check()
           └─> 4. BaseToolAdapter.check()
               └─> 5. ComplexipyAdapter.parse_output()
                   ├─> Read complexipy.json file
                   ├─> Parse JSON data
                   └─> Return ToolIssue[] list
           └─> 6. BaseToolAdapter._build_details() [LINE 514]
               └─> Builds details string from issues
           └─> 7. Return QAResult with details
       └─> 8. HookOrchestrator._create_success_result()
           ├─> _determine_status() [LINE 823]
           ├─> _build_issues_list() [LINE 841]
           └─> _extract_error_details() [LINE 881]
   └─> 9. Return HookResult
       └─> issues_found: list[str]  # Generic messages, not actual issues!
       └─> issues_count: int        # Total count (correct)

10. PhaseCoordinator._build_results_table()
    └─> Shows issues_count in table [LINE 650]

11. PhaseCoordinator._display_hook_failures()
    └─> Shows issues_found list [LINE 827-838]
        └─> PROBLEM: issues_found contains generic messages, not actual issues!
```

## The Core Problem

The orchestrator is **double-processing** the adapter results:

1. **Adapter** (`ComplexipyAdapter`) creates detailed `QAResult.details` string ✅
2. **Orchestrator** (`_build_issues_list`) tries to **re-parse** `details` string ❌
3. If parsing fails, orchestrator creates **generic fallback message** ❌
4. **Original detailed output is lost** ❌

## Solution Strategy

### Option 1: Pass Through Adapter Details (Recommended)

**Change**: In `hook_orchestrator.py`, use adapter's `details` directly instead of re-parsing

```python
def _build_issues_list(self, qa_result: t.Any) -> list[str]:
    """Build the issues list from the QA result."""
    if qa_result.issues_found == 0:
        return []

    # NEW: Use adapter's pre-formatted details directly
    if qa_result.details:
        detail_lines = [
            line.strip()
            for line in qa_result.details.split("\n")
            if line.strip() and not line.strip().startswith("...")
        ]
        return detail_lines if detail_lines else []

    # Fallback for adapters that don't provide details
    return [f"{qa_result.issues_found} issues found (run with --ai-debug for full details)"]
```

**Pros**:
- Minimal changes
- Preserves adapter formatting
- Works for all adapters

**Cons**:
- Still requires adapters to populate `details` correctly

### Option 2: Store Structured Issues in HookResult

**Change**: Add `structured_issues: list[ToolIssue]` to `HookResult` dataclass

```python
@dataclass
class HookResult:
    id: str
    name: str
    status: str
    duration: float
    files_processed: int = 0
    issues_found: list[str] | None = None  # Formatted strings for display
    structured_issues: list[ToolIssue] | None = None  # NEW: Structured data
    issues_count: int = 0
    ...
```

**Pros**:
- Preserves full structured data
- Enables rich formatting
- Better for AI agent integration

**Cons**:
- Larger refactor
- Changes public API
- Overkill for simple fix

### Option 3: Fix Adapter Output Format (Targeted)

**Change**: Ensure complexipy adapter returns proper details in expected format

**Investigate**:
1. Is `complexipy.json` file being created?
2. Is JSON parsing succeeding?
3. Is `_build_details()` being called?
4. Is `details` string populated in `QAResult`?

## Testing Plan

### Test 1: Verify Adapter Details Population

```python
async def test_complexipy_details_population():
    """Verify that ComplexipyAdapter populates details in QAResult."""
    adapter = ComplexipyAdapter()
    await adapter.init()

    # Run on test file with known complexity issues
    result = await adapter.check(files=[Path("tests/fixtures/complex_code.py")])

    # Verify details are populated
    assert result.details is not None
    assert len(result.details) > 0
    assert "complexity" in result.details.lower()

    # Verify issues_found matches actual issues
    assert result.issues_found > 0
    assert result.issues_found == len(result.details.split("\n"))
```

### Test 2: Verify Orchestrator Preserves Details

```python
async def test_orchestrator_preserves_adapter_details():
    """Verify that HookOrchestrator preserves adapter details in HookResult."""
    hook = HookDefinition(name="complexipy", ...)
    orchestrator = HookOrchestratorAdapter()
    await orchestrator.init()

    # Execute hook
    result = await orchestrator._execute_single_hook(hook)

    # Verify issues_found contains actual details, not generic messages
    assert result.issues_found is not None
    assert len(result.issues_found) > 0
    assert "failed with no detailed output" not in result.issues_found[0]

    # Verify issues_count matches issues_found length
    assert result.issues_count == len(result.issues_found)
```

### Test 3: Verify Phase Coordinator Display

```python
async def test_phase_coordinator_displays_details():
    """Verify that PhaseCoordinator displays actual issue details."""
    coordinator = PhaseCoordinator(...)

    # Create mock result with known details
    mock_result = HookResult(
        name="complexipy",
        status="failed",
        issues_found=["crackerjack/foo.py:123: Complexity 25"],
        issues_count=1,
        ...
    )

    # Capture display output
    with patch("rich.console.Console.print") as mock_print:
        coordinator._print_single_hook_failure(mock_result)

        # Verify actual details are displayed
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("crackerjack/foo.py:123" in call for call in calls)
        assert any("Complexity 25" in call for call in calls)
```

## Implementation Priority

1. **Investigate** (15 min): Run complexipy manually and verify `complexipy.json` file creation
2. **Debug** (15 min): Add logging to `_build_issues_list()` to see what `qa_result.details` contains
3. **Fix** (30 min): Implement Option 1 (pass through adapter details)
4. **Test** (45 min): Create comprehensive tests as outlined above
5. **Validate** (15 min): Run full test suite and verify output

## Files to Modify

### Primary Changes
- `crackerjack/orchestration/hook_orchestrator.py`
  - Method: `_build_issues_list()` (line 841)
  - Method: `_extract_error_details()` (line 881)

### Test Files to Create
- `tests/unit/orchestration/test_hook_result_details.py`
- `tests/integration/test_hook_reporting_e2e.py`

## Expected Outcome

### Before
```
❌ Fast hooks attempt 1: 11/14 passed in 49.17s

╭──────────────────────── Fast Hook Results ─────────────────────────╮
│                                                                    │
│   Hook                        Status         Duration     Issues   │
│  ────────────────────────────────────────────────────────────────  │
│   ruff-format                 FAILED            5.31s          1   │
│   codespell                   FAILED            2.84s          1   │
│   ruff-check                  FAILED            1.71s          1   │
│                                                                    │
╰─────── Total: 14 | Passed: 11 | Failed: 3 | Issues found: 3 ───────╯

Details for failing fast hooks:
  - ruff-format (failed)
      - Hook ruff-format failed with no detailed output (exit code: unknown)
```

### After
```
❌ Fast hooks attempt 1: 11/14 passed in 49.17s

╭──────────────────────── Fast Hook Results ─────────────────────────╮
│                                                                    │
│   Hook                        Status         Duration     Issues   │
│  ────────────────────────────────────────────────────────────────  │
│   ruff-format                 FAILED            5.31s         15   │
│   codespell                   FAILED            2.84s          7   │
│   ruff-check                  FAILED            1.71s         23   │
│                                                                    │
╰─────── Total: 14 | Passed: 11 | Failed: 3 | Issues found: 45 ──────╯

Details for failing fast hooks:
  - ruff-format (failed)
      - crackerjack/core/phase_coordinator.py:123: Trailing whitespace
      - crackerjack/agents/refactoring.py:456: Line too long (95 > 88)
      - crackerjack/models/task.py:78: Missing blank line
      ... and 12 more issues
```

## Notes

- The issue affects **both fast and comprehensive hooks**
- All hooks using ACB adapters are affected
- Subprocess-based hooks (via `_run_subprocess`) work correctly
- The fix should be applied to the orchestrator, not individual adapters
