# AI Fix Bug: ruff-check Issues Not Parsed in Iteration 1

**Date**: 2026-01-25
**Severity**: High (AI fix feature fails to detect issues in first iteration)
**Status**: ✅ FIXED

## The Bug

When running `python -m crackerjack run --ai-fix`, the AI fix iteration loop reported:

```
Fast Hook Results:
 - ruff-check :: FAILED | issues=12

🤖 AI AGENT FIXING Attempting automated fixes for fast hook failures
----------------------------------------------------------------------

→ Iteration 1/5: 0 issues to fix        # ❌ WRONG! Should be 12 issues
→ Iteration 2/5: 2 issues to fix        # ✅ Suddenly detected 2 issues
→ Iteration 3/5: 2 issues to fix        # ❌ No progress
⚠ No progress for 3 iterations (2 issues remain)
```

**Root Cause**: ruff-check output format incompatibility with AI issue parser.

## Technical Analysis

### Phase 1: Root Cause Investigation

**Data Flow Trace**:

1. **Fast Hooks (Iteration 0)**:

   - `ruff-check` runs with `--fix` flag
   - ruff auto-fixes some issues, reports 12 remaining
   - Multi-line diagnostic output format (not parseable)

1. **Iteration 1**:

   - AI fixer calls `_parse_hook_results_to_issues()`
   - Parser expects single-line format: `file:line:col CODE message`
   - Actual ruff --fix output: multi-line with `--> file:line:col` arrows
   - **Result**: 0 issues parsed (regex doesn't match)

1. **Iterations 2-3**:

   - AI fixer calls `_collect_current_issues()`
   - Runs ruff WITHOUT --fix flag
   - Gets single-line format that parser can handle
   - **Result**: Successfully parses 2 issues

### The Output Format Problem

**Old ruff-check command** (in `crackerjack/config/tool_commands.py`):

```python
"ruff-check": [
    "uv", "run", "python", "-m", "ruff",
    "check",
    "--fix",  # ❌ PROBLEM: Changes output format
    "--extension", ".py: python",
    f"./{package_name}",
],
```

**With --fix, ruff outputs** (multi-line format):

```
F811 Redefinition of unused `DocCleanupAnalyzer` from line 21
  --> scripts/docs_cleanup.py:55:7
   |
55 | class DocCleanupAnalyzer:
   |       ^^^^^^^^^^^^^^^^^^ `DocCleanupAnalyzer` redefined here
   |
help: Remove definition: `DocCleanupAnalyzer`
```

**Parser regex** (in `autofix_coordinator.py:_parse_ruff_output`):

```python
pattern = re.compile(r"^(.+?):(\d+):(\d+):?\s*([A-Z]\d+)\s+(.+)$")
```

This pattern expects: `file:line:col CODE message` (single line)

## The Fix

### Solution: Use `--output-format concise`

**Updated ruff-check command** (line 149-150):

```python
"ruff-check": [
    "uv", "run", "python", "-m", "ruff",
    "check",
    "--output-format", "concise",  # ✅ FIX: Single-line parseable format
    "--extension", ".py: python",
    f"./{package_name}",
],
```

**With --output-format concise, ruff outputs**:

```
scripts/docs_cleanup.py:55:7: F811 Redefinition of unused `DocCleanupAnalyzer` from line 21
scripts/docs_cleanup.py:238:9: C901 `generate_report` is too complex (16 > 15)
Found 2 errors.
```

**This matches the parser regex perfectly!**

## Why This Approach?

### Option Analysis

1. **❌ Keep --fix, add multi-line parser**

   - Complex regex needed for multi-line format
   - Fragile (ruff output format may change)
   - Mixing concerns (auto-fix + issue detection)

1. **❌ Run ruff twice (--fix then check)**

   - Slower (runs ruff twice)
   - Redundant work
   - Confusing workflow

1. **✅ Use --output-format concise (CHOSEN)**

   - Single ruff run
   - Parseable output for AI agents
   - AI agents fix issues, not ruff --fix
   - Clear separation of concerns
   - **Faster + more reliable**

## Rationale: Why Not Use --fix?

The crackerjack philosophy is:

1. **ruff-format**: Handles formatting (runs first, auto-fixes)
1. **ruff-check**: Reports issues for AI agents to fix
1. **AI agents**: Intelligently fix reported issues

Using `--fix` on ruff-check undermines this workflow:

- ruff --fix makes blind changes without context
- AI agents understand codebase context and make better fixes
- Separation allows for smarter, targeted fixes

## Verification

### Test Results

**Before fix**:

```
→ Iteration 1/5: 0 issues to fix      # ❌ Parser failed
→ Iteration 2/5: 2 issues to fix      # ✅ Different code path
```

**After fix**:

```
→ Iteration 1/5: 12 issues to fix     # ✅ Parser succeeds
→ Iteration 2/5: 5 issues to fix      # ✅ Progress!
→ Iteration 3/5: 0 issues to fix      # ✅ All resolved
✓ All issues resolved in 3 iteration(s)!
```

### Test Coverage

All 28 integration tests pass:

```bash
pytest tests/test_core_autofix_coordinator.py
=================== 28 passed in 62.70s ===================
```

## Impact

**Benefits**:

- ✅ AI fix iteration 1 now correctly detects all ruff issues
- ✅ Faster convergence (fewer iterations needed)
- ✅ Clearer workflow (format → check → AI fix)
- ✅ Better separation of concerns

**No Breaking Changes**:

- ruff-format still handles auto-formatting
- ruff-check still detects issues
- AI agents still fix issues (now with correct input)

## Related Issues

This is different from the previous case sensitivity bug (fixed 2026-01-21):

- **Previous bug**: Case mismatch (`"Failed"` vs `"failed"`)
- **This bug**: Output format incompatibility (`--fix` multi-line vs concise single-line)

Both caused "0 issues to fix" but had different root causes.

## Files Modified

- `crackerjack/config/tool_commands.py` (line 149-150)
  - Replaced `--fix` with `--output-format concise`
  - No other changes needed

## Documentation

**Key Insight**:

```
★ Insight ─────────────────────────────────────
Tool output format matters! When integrating
external tools, always control output format
explicitly. Don't assume default formats match
your parser's expectations.
─────────────────────────────────────────────────
```

## References

- ruff output formats: `ruff check --help`
- AI fix implementation: `crackerjack/core/autofix_coordinator.py`
- Tool command configuration: `crackerjack/config/tool_commands.py`
