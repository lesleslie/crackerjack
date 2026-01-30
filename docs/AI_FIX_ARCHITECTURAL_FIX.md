# AI-Fix Architectural Fix

## Problem

AI-fix workflow was showing confusing issue counts:
- **Iteration 1**: "6035 issues to fix"
- **Iteration 2-5**: "12 issues to fix"

This happened because of an **architectural mismatch** between two layers:

### Layer Mismatch

**Layer 1: Hook Execution (Adapter)**
- Runs tools and collects raw output
- Counts ALL output lines liberally
- Example: complexipy outputs 6076 functions

**Layer 2: Parser Factory**
- Parses output and extracts issues
- Applies business logic filtering (thresholds, patterns)
- Example: Filters to ~9 functions with complexity > 15

**Layer 3: AI-Fix Iteration**
- Uses filtered issues from parser
- But displays issue counts from adapter
- Result: Shows "6035 issues" but only gets 12 to fix

### Affected Tools

Tools with **heavy filtering logic** in their adapters:

| Tool | Raw Output | Filtered Issues | Filter Type |
|------|------------|-----------------|-------------|
| **complexipy** | 6076 functions | ~9 functions | Complexity threshold (>15) |
| **refurb** | All output lines | ~5-10 lines | "[FURB" prefix pattern |
| **creosote** | Multiple sections | ~3-8 deps | "unused" dependency filter |

## Root Cause

**Violation of Single Source of Truth Principle**:

The system had two different definitions of "issue count":
1. **Adapter Layer**: "How many lines of output did the tool produce?"
2. **Parser Layer**: "How many actionable issues after filtering?"

These definitions don't match for tools that do heavy filtering, causing:
- Confusing iteration reports
- AI agents receiving different counts than displayed
- User mistrust in the AI-fix system

## Solution: Option 3 (Pragmatic)

**Skip complexipy, refurb, and creosote in AI-fix iterations**

### Implementation

Modified `/Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py`:

```python
def _parse_single_hook_result(self, result: object) -> list[Issue]:
    # ... existing validation ...

    hook_name = getattr(result, "name", "")

    # Skip tools that do heavy filtering in their adapters
    if hook_name in ("complexipy", "refurb", "creosote"):
        self.logger.info(
            f"Skipping '{hook_name}' for AI-fix: tool requires manual review "
            f"due to complex filtering logic (thresholds, patterns, etc)"
        )
        self.console.print(
            f"[dim]ℹ Skipping {hook_name} for AI-fix (requires manual review)[/dim]"
        )
        return []

    # Continue with normal parsing...
```

### Why This Solution?

1. **Honest about AI capabilities**: These tools require manual review due to complex filtering
2. **Eliminates confusion**: No more "6035 issues" → "12 issues" mismatch
3. **Tools still run**: Issues are still reported, just not auto-fixed
4. **Pragmatic**: Minimal code change, maximum clarity

### Behavior Changes

**Before**:
```
Iteration 1/5: 6035 issues to fix
  (AI agents receive 12 issues, confused user)
```

**After**:
```
ℹ Skipping complexipy for AI-fix (requires manual review)
ℹ Skipping refurb for AI-fix (requires manual review)
ℹ Skipping creosote for AI-fix (requires manual review)
Iteration 1/5: 12 issues to fix
  (AI agents receive 12 issues, honest reporting)
```

## Testing

Added comprehensive tests in `/Users/les/Projects/crackerjack/tests/core/autofix_coordinator_bugfix_test.py`:

```python
class TestAIFixToolSkipping:
    """Test that tools with heavy filtering are skipped in AI-fix iterations."""

    def test_complexipy_skipped_in_ai_fix(self, coordinator):
        """complexipy should be skipped for AI-fix iterations."""

    def test_refurb_skipped_in_ai_fix(self, coordinator):
        """refurb should be skipped for AI-fix iterations."""

    def test_creosote_skipped_in_ai_fix(self, coordinator):
        """creosote should be skipped for AI-fix iterations."""

    def test_regular_tools_not_skipped(self, coordinator):
        """Regular tools like ruff should NOT be skipped."""
```

All tests pass: ✅ 15/15 tests passing

## Alternative Solutions Considered

### Option 1: Single Source of Truth (Ideal)
**Approach**: Always parse first, then count

**Pros**:
- Architecturally correct
- Consistent issue counts

**Cons**:
- Requires significant refactoring
- Need to unify adapter/parser interfaces
- High risk of breaking changes

### Option 2: Count Filtered Issues
**Approach**: Make adapters return filtered counts

**Pros**:
- More accurate than current
- Tools still participate in AI-fix

**Cons**:
- Requires changes to all adapters
- Still misleading (AI can't fix complex complexity issues)
- Doesn't address root cause

### Option 3: Skip Problematic Tools (SELECTED) ✅
**Approach**: Don't run AI-fix for tools with heavy filtering

**Pros**:
- Minimal code change
- Honest about AI capabilities
- Eliminates confusion
- Tools still report issues

**Cons**:
- These tools require manual review
- Slightly reduced AI-fix scope

## User Impact

### Positive Changes
- **Clear reporting**: Issue counts match what AI agents actually fix
- **Honest expectations**: Users know which tools require manual review
- **Faster iterations**: AI agents focus on issues they can actually fix

### Manual Review Required
Users will need to manually address:
- **complexipy**: High-complexity functions (>15 cyclomatic complexity)
- **refurb**: Code modernization suggestions
- **creosote**: Unused import dependencies

These tools require architectural decisions that AI agents cannot reliably make.

## Future Improvements

### Short Term
1. Add "Manual Review" section to quality reports
2. Highlight skipped tools clearly in output
3. Document why each tool requires manual review

### Long Term
1. Consider implementing Option 1 (Single Source of Truth)
2. Make adapters return both raw and filtered counts
3. Add AI agent capabilities for complexity reduction (with user confirmation)

## Related Documentation

- **Original Issue**: AI-fix workflow showing "6035 issues to fix" then "12 issues to fix"
- **Architectural Analysis**: See architect-reviewer agent analysis in conversation history
- **Parser Fix**: See `docs/PARSER_FACTORY_FIX.md` for related parser improvements
- **Test Coverage**: See `tests/core/autofix_coordinator_bugfix_test.py::TestAIFixToolSkipping`

## Summary

This fix resolves the AI-fix issue count confusion by:
1. **Identifying** tools with heavy filtering logic
2. **Skipping** them in AI-fix iterations
3. **Reporting** clearly why they're skipped
4. **Testing** the behavior comprehensively

The solution is **pragmatic**, **honest**, and **minimal** - fixing the immediate problem while keeping the door open for future architectural improvements.
