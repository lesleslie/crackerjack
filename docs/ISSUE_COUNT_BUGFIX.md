# Issue Counting Discrepancy Bug Fix

## Problem

**Symptom**: AI fixing reports a different number of issues than the comprehensive hooks table.

**Example**:
- Comprehensive hooks table shows: `zuban: 10 issues`
- AI fixing iteration shows: `9 issues to fix`

## Root Cause

Two layers were using **different issue counting logic**:

1. **Hook Execution Layer** (`crackerjack/executors/hook_executor.py:628-629`)
   ```python
   # OLD CODE - Counted ALL non-empty lines
   if error_output:
       return [line.strip() for line in error_output.split("\n") if line.strip()]
   ```

2. **AI Fixing Layer** (`crackerjack/core/autofix_coordinator.py:939-955`)
   ```python
   # Filtered out notes, help, summaries, headers
   def _should_parse_line(self, line: str) -> bool:
       if any(pattern in line_lower for pattern in (": note:", ": help:", "note: ", "help: ")):
           return False  # Filters these out
       # ... more filtering
   ```

**Result**: If zuban/mypy/pyright output 10 lines where 1 is a "note:" or "help:" message:
- Hook layer: Counts all 10 lines → `issues_count = 10`
- AI fixing layer: Filters out the note line → `9 issues to fix`

## Solution

Created a **shared utility module** that both layers use for consistent issue detection.

### Files Changed

1. **Created** `crackerjack/utils/issue_detection.py`
   - `should_count_as_issue()` - Centralized line filtering logic
   - `count_issues_from_output()` - Count issues using shared filter
   - `extract_issue_lines()` - Extract issue lines using shared filter

2. **Updated** `crackerjack/executors/hook_executor.py`
   - Line 17: Added import of `extract_issue_lines`
   - Line 630: Changed from simple line split to `extract_issue_lines(error_output, tool_name=hook.name)`

3. **Updated** `crackerjack/core/autofix_coordinator.py`
   - Line 20: Added import of `should_count_as_issue`
   - Lines 940-952: Refactored `_should_parse_line()` to delegate to shared utility

4. **Created** `tests/unit/utils/test_issue_detection.py`
   - 20 comprehensive tests covering all filtering scenarios
   - Integration tests verifying consistency between layers

## What Gets Filtered

The shared utility filters out:

1. **Empty lines** - Whitespace only
2. **Comment lines** - Lines starting with `#`
3. **Notes and help** - Lines containing `: note:`, `: help:`, `note: `, `help: `
4. **Summary lines** - Lines starting with:
   - `Found`, `Checked`, `N errors found`, `errors in`
   - `Success`, `Summary`, `Total`
5. **Separator lines** - Lines starting with or containing only:
   - `===`, `---`, `Errors:`
   - Box drawing characters: `┌`, `└`, `├`, `┼`, `┤`, `┃`
6. **Header lines** - Exact matches:
   - `Path`, `File`, `Function`
   - `File | Function | Complexity`, `Path | Function | Complexity`
   - `File | Line | Issue`, `Function | Complexity`

## Impact

✅ **Consistent counting**: Both layers now report identical issue counts

✅ **Accurate reporting**: Hook execution no longer counts non-issue lines

✅ **DRY principle**: Single source of truth for issue detection

✅ **Well-tested**: 20 tests ensuring correct filtering behavior

## Example

Before fix:
```
Comprehensive hooks table: zuban reported 10 issues
AI fixing iteration: 9 issues to fix
❌ Discrepancy: 1 issue difference
```

After fix:
```
Comprehensive hooks table: zuban reported 9 issues
AI fixing iteration: 9 issues to fix
✅ Consistent: No discrepancy
```

## Testing

Run the test suite:
```bash
python -m pytest tests/unit/utils/test_issue_detection.py -v
# All 20 tests pass ✅
```

The fix ensures that:
- Note lines are never counted as issues
- Help text is never counted as issues
- Summary lines are never counted as issues
- Headers and separators are never counted as issues
- Actual error messages ARE counted as issues

## Architectural Improvement

This fix follows the **DRY principle** (Don't Repeat Yourself):

- **Before**: Two separate implementations of line filtering logic
- **After**: Single shared utility used by both layers

Benefits:
- Easier to maintain (change once, applies everywhere)
- Consistent behavior across all layers
- Better testability (test the utility, not each layer)
- Clearer intent (well-documented filtering rules)
