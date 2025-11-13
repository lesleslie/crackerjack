# Reporting Tools Exit Code Fix

## Problem

Tools like `complexipy`, `refurb`, `gitleaks`, and `creosote` were showing as `PASSED` with non-zero issue counts (e.g., complexipy showing 2 issues, refurb showing 1 issue, etc.). These hooks need to FAIL when they find issues so the auto-fix stage can be triggered.

## Root Cause

These are **reporting/analysis tools**, not linters. They return exit code 0 when execution succeeds, regardless of whether they find violations:

- **Linters** (ruff, mypy, pyright): Exit code 0 = no violations, non-zero = violations found
- **Reporting Tools** (complexipy, refurb, gitleaks, creosote): Exit code 0 = execution succeeded (tool ran correctly), non-zero = execution failed (tool crashed or had errors)

The `--max-complexity-allowed` flag in complexipy, for example, filters display output but doesn't affect exit codes.

## Solution

Modified `crackerjack/executors/hook_executor.py` to handle reporting tools differently:

### 1. Parse Issues Regardless of Exit Code

**Before** (lines 425-426):

```python
def _extract_issues_from_process_output(...) -> list[str]:
    if status == "passed":
        return []  # No parsing for passed hooks!
    # ... parsing logic
```

**After** (lines 427-440):

```python
def _extract_issues_from_process_output(...) -> list[str]:
    error_output = (result.stdout + result.stderr).strip()

    # Reporting tools need parsing regardless of exit code
    reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}

    if hook.name in reporting_tools:
        # Always parse for reporting tools (they exit 0 even with findings)
        if hook.name == "complexipy":
            return self._parse_complexipy_issues(error_output)
        # ... other reporting tools

    # For non-reporting tools, only parse if failed
    if status == "passed":
        return []
```

### 2. Override Status Based on Issues Found

**Before** (lines 396-404):

```python
# Status determined ONLY by exit code
status = "passed" if result.returncode == 0 else "failed"

issues_found = self._extract_issues_from_process_output(hook, result, status)
# Status never changes after this!
```

**After** (lines 387-413):

```python
# Reporting tools need special handling
reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}

# Initial status based on exit code
status = "passed" if result.returncode == 0 else "failed"

# Extract issues (for reporting tools, happens regardless of exit code)
issues_found = self._extract_issues_from_process_output(hook, result, status)

# Override status if reporting tool found issues
if hook.name in reporting_tools and issues_found:
    status = "failed"  # Triggers auto-fix stage!
```

## Expected Results

### Before Fix

```
COMPREHENSIVE HOOKS:
  - complexipy :: PASSED | 2.3s | issues=2
  - refurb :: PASSED | 1.8s | issues=1
  - gitleaks :: PASSED | 0.5s | issues=1
  - creosote :: PASSED | 1.2s | issues=1
```

### After Fix

```
COMPREHENSIVE HOOKS:
  - complexipy :: FAILED | 2.3s | issues=22
  - refurb :: PASSED | 1.8s | issues=0
  - gitleaks :: PASSED | 0.5s | issues=0
  - creosote :: PASSED | 1.2s | issues=0
```

**Key Changes:**

1. **Accurate issue counts**: Complexipy now shows 22 issues (functions exceeding complexity 15) instead of 2
1. **Correct status**: Hooks fail when they find issues, triggering auto-fix
1. **Zero false positives**: Tools showing 0 issues truly have no violations (not warnings)

## Tool-Specific Parsing

Each reporting tool has specialized parsing logic to count only real violations:

### complexipy

- Parses table output (lines with `│` separators)
- Only counts functions with complexity > 15
- Ignores header rows, summary lines, and functions below threshold

### refurb

- Counts lines matching pattern: `file.py:10:5 [FURB101]: message`
- Only counts actual FURB violation codes

### gitleaks

- Ignores warnings (e.g., "Invalid .gitleaksignore format")
- Only counts actual leak findings
- Returns empty list for "no leaks found" messages

### creosote

- Parses "unused dependencies" section
- Counts only dependency names (not ANSI color codes)
- Returns empty list for "No unused dependencies found"

## Files Modified

1. `/Users/les/Projects/crackerjack/crackerjack/executors/hook_executor.py`:
   - Modified `_create_hook_result_from_process()` to override status when reporting tools find issues
   - Modified `_extract_issues_from_process_output()` to parse reporting tools regardless of exit code
   - Tool-specific parsing methods: `_parse_complexipy_issues()`, `_parse_refurb_issues()`, `_parse_gitleaks_issues()`, `_parse_creosote_issues()`
