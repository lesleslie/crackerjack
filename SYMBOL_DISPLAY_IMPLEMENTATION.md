# Symbol Display Implementation - Summary

## Overview

Implemented **Option 1 (Symbol with Legend)** from the UX design options to clearly distinguish configuration/tool errors from actual code violations.

## Changes Made

### 1. Added `is_config_error` Field to HookResult

**File**: `crackerjack/models/task.py`

**Change**: Added boolean field to track config/tool errors:

```python
@dataclass
class HookResult:
    # ... existing fields ...
    is_config_error: bool = (
        False  # Whether failure is due to config/tool error (not code issues)
    )
```

**Purpose**: Allows the display layer to distinguish between:

- Code quality failures (`is_config_error=False`) → Show issue count
- Config/tool errors (`is_config_error=True`) → Show warning symbol

______________________________________________________________________

### 2. Set `is_config_error` Flag in Hook Orchestrator

**File**: `crackerjack/orchestration/hook_orchestrator.py`

**Change**: Detect config errors when creating HookResult:

```python
def _create_success_result(
    self, hook: HookDefinition, qa_result: t.Any, start_time: float
) -> HookResult:
    # ... existing code ...

    # Determine if this is a config/tool error (not code issues)
    is_config_error = (
        status == "failed"
        and hasattr(qa_result, "status")
        and qa_result.status == QAResultStatus.ERROR
    )

    return HookResult(
        # ... other fields ...
        is_config_error=is_config_error,  # Mark config/tool errors
    )
```

**Logic**:

- If `status == "failed"` AND `qa_result.status == QAResultStatus.ERROR`
- Then `is_config_error = True`
- This leverages the existing `QAResultStatus.ERROR` enum value

______________________________________________________________________

### 3. Display Warning Symbol for Config Errors

**File**: `crackerjack/core/phase_coordinator.py`

**Change**: Show `⚠️` instead of `0` for config errors:

```python
def _build_results_table(self, results: list[HookResult]) -> Table:
    # ... table setup ...

    for result in results:
        status_style = self._status_style(result.status)

        if result.status == "passed":
            issues_display = "0"
        elif hasattr(result, "is_config_error") and result.is_config_error:
            # Config/tool error - show warning symbol instead of misleading count
            issues_display = "⚠️"
        else:
            # For failed hooks with code violations, use issues_count
            issues_display = str(result.issues_count or 0)

        table.add_row(
            self._strip_ansi(result.name),
            f"[{status_style}]{result.status.upper()}[/{status_style}]",
            f"{result.duration:.2f}s",
            issues_display,
        )

    return table
```

______________________________________________________________________

### 4. Add Legend Footer

**File**: `crackerjack/core/phase_coordinator.py`

**Change**: Show legend when config errors are present:

```python
def _render_rich_hook_results(self, suite_name: str, results: list[HookResult]) -> None:
    """Render hook results in Rich format."""
    stats = self._calculate_hook_statistics(results)
    summary_text = self._build_summary_text(stats)
    table = self._build_results_table(results)
    panel = self._build_results_panel(suite_name, table, summary_text)

    self.console.print(panel)

    # Add legend if any config errors are present
    has_config_errors = any(
        hasattr(r, "is_config_error") and r.is_config_error for r in results
    )
    if has_config_errors:
        self.console.print(
            "[dim]⚠️  = Configuration or tool error (not code issues)[/dim]"
        )

    self.console.print()
```

**Behavior**:

- Legend only appears when at least one hook has `is_config_error=True`
- Uses `[dim]` style for subtlety
- Placed between the results panel and the blank line separator

______________________________________________________________________

## Expected Output

### Before (Confusing):

```
Fast Hooks Results:
┌──────────────┬────────┬──────────┬────────┐
│ Hook         │ Status │ Duration │ Issues │
├──────────────┼────────┼──────────┼────────┤
│ ruff-format  │ FAILED │ 0.05s    │ 0      │  ← Why FAILED with 0?
│ codespell    │ FAILED │ 0.03s    │ 0      │  ← Why FAILED with 0?
│ ruff-check   │ FAILED │ 0.15s    │ 95     │  ← Clear: 95 violations
│ complexipy   │ PASSED │ 2.50s    │ 0      │  ← Clear: passed
└──────────────┴────────┴──────────┴────────┘
```

### After (Clear):

```
Fast Hooks Results:
┌──────────────┬────────┬──────────┬────────┐
│ Hook         │ Status │ Duration │ Issues │
├──────────────┼────────┼──────────┼────────┤
│ ruff-format  │ FAILED │ 0.05s    │ ⚠️      │  ← Config error!
│ codespell    │ FAILED │ 0.03s    │ ⚠️      │  ← Config error!
│ ruff-check   │ FAILED │ 0.15s    │ 95     │  ← 95 code violations
│ complexipy   │ PASSED │ 2.50s    │ 0      │  ← No issues
└──────────────┴────────┴──────────┴────────┘

⚠️  = Configuration or tool error (not code issues)
```

______________________________________________________________________

## Benefits

### 1. Clear Visual Distinction

- ✅ **Symbol vs Number**: Config errors use `⚠️`, code violations use numbers
- ✅ **No Confusion**: Users immediately understand FAILED ⚠️ ≠ code problem
- ✅ **Scannable**: Quick visual scan shows which failures need config fixes

### 2. Backward Compatible

- ✅ **No Breaking Changes**: Only adds new field and display logic
- ✅ **Graceful Degradation**: `hasattr()` checks ensure old HookResults still work
- ✅ **Existing Tests Pass**: All 9 unit tests passing

### 3. User Experience

- ✅ **Self-Documenting**: Legend explains the symbol
- ✅ **Contextual**: Legend only appears when relevant
- ✅ **Rich-Compatible**: Uses Rich emoji support for cross-terminal compatibility

### 4. Semantic Correctness

- ✅ **Leverages Existing Enums**: Uses `QAResultStatus.ERROR` distinction
- ✅ **Single Source of Truth**: Status determination centralized in orchestrator
- ✅ **Type-Safe**: Uses dataclass boolean field

______________________________________________________________________

## Testing

### Unit Tests

All existing tests pass (9/9):

```bash
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountFix::test_config_error_shows_zero_issues PASSED
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountFix::test_code_violations_show_actual_count PASSED
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountFix::test_parsing_failure_shows_one_issue PASSED
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountFix::test_passed_hook_with_zero_issues PASSED
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountFix::test_warning_status_shows_actual_count PASSED
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountFix::test_tool_error_with_stderr_output PASSED
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountEdgeCases::test_missing_qa_result_status_attribute PASSED
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountEdgeCases::test_status_passed_with_nonzero_issues PASSED
tests/unit/orchestration/test_issue_count_fix.py::TestIssueCountEdgeCases::test_large_issue_count PASSED
```

### Integration Testing

To verify in the user's ../acb project:

1. Run `python -m crackerjack` in the acb directory
1. Check the Fast Hooks Results table:
   - Config errors (ruff-format, codespell) should show `⚠️`
   - Code violations (ruff-check) should show actual count (e.g., 95)
   - Legend should appear at bottom if any `⚠️` present

______________________________________________________________________

## Alternative Symbol Options

If the warning triangle doesn't display well in some terminals, these alternatives can be used:

| Symbol | Meaning | Unicode | Pros | Cons |
|--------|---------|---------|------|------|
| `⚠️` | Warning (current) | U+26A0 | Universal, recognizable | Might need emoji support |
| `⚙️` | Gear/Config | U+2699 | Suggests config issue | Less intuitive |
| `❌` | Red X | U+274C | Clear error | Too similar to FAILED |
| `✗` | Cross | U+2717 | Simple | Less distinctive |
| `!` | Exclamation | ASCII | Max compatibility | Too generic |
| `ERR` | Text | ASCII | Explicit, compatible | Takes more space |

**Recommendation**: Stick with `⚠️` for its universal recognition and Rich's excellent emoji support.

______________________________________________________________________

## Files Modified

1. **`crackerjack/models/task.py`**: Added `is_config_error` field to HookResult
1. **`crackerjack/orchestration/hook_orchestrator.py`**: Set flag based on QAResultStatus.ERROR
1. **`crackerjack/core/phase_coordinator.py`**: Display symbol and legend

**Total Changes**: 3 files, ~20 lines of code added

______________________________________________________________________

## Future Enhancements

### Configuration Option

Add user preference for symbol choice:

```yaml
# settings/crackerjack.yaml
display:
  config_error_symbol: "⚠️"  # Options: ⚠️, ⚙️, ❌, !, ERR
  show_legend: true
```

### Tooltip/Help Text

In interactive mode, add hover help:

```
Issues: ⚠️  (Press 'h' for help)
```

### Color Coding

Add color to the symbol for extra visibility:

```python
issues_display = "[yellow]⚠️[/yellow]"  # Yellow warning
```

### Detailed Error Summary

After the legend, show specific errors:

```
⚠️  = Configuration or tool error (not code issues)

Config Errors:
- ruff-format: Invalid pyproject.toml configuration
- codespell: Binary not found in PATH
```

______________________________________________________________________

## Summary

Implemented a clean, intuitive UX solution that:

- **Eliminates confusion** between config errors and code violations
- **Maintains backward compatibility** with existing code
- **Provides clear visual feedback** via the `⚠️` symbol
- **Includes helpful context** via the legend footer
- **Passes all tests** without breaking existing functionality

The implementation is production-ready and can be further enhanced based on user feedback.
