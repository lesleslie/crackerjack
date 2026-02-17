# Complexipy Parser Fix - AI-Fix Count Mismatch

## Problem

AI-fix workflow showed confusing issue counts:

- **Iteration 1**: "6037 issues to fix"
- **Iteration 2-5**: "13 issues to fix"

## Root Cause Analysis

### Architectural Violation: Single Source of Truth

The system had two code paths for parsing complexipy output:

**Path 1: Adapter (used during quality checks)**

- ComplexipyAdapter reads JSON file
- Filters functions by `max_complexity` threshold (>15)
- Returns ~9 high-complexity functions

**Path 2: Parser (used during AI-fix)**

- ComplexipyJSONParser reads JSON file
- Returns ALL 6076 functions without filtering
- Deletes JSON file after reading
- **Iteration 2**: File not found (deleted in iteration 1), returns 0 issues

### Why This Happened

The comment in `ComplexipyJSONParser.parse_json()` said:

```python
# Note: This parser returns ALL functions from complexipy output without filtering.
# The ComplexipyAdapter is responsible for filtering by max_complexity threshold.
# This separation ensures the parser is stateless and the adapter handles config.
```

This assumption was **WRONG** because AI-fix calls the parser directly, not via the adapter!

### Count Breakdown

- Total functions in JSON: 6076
- Functions with complexity > 15: 9
- Functions with complexity > 10: 182
- Other tools (ruff, refurb, etc.): ~4 issues
- **Expected total**: ~13 issues

## Solution

### Changes to ComplexipyJSONParser

**1. Added complexity threshold filtering**

```python
def __init__(self, max_complexity: int = 15) -> None:
    """Initialize parser with complexity threshold.

    Args:
        max_complexity: Only report functions with complexity > this value
    """
    super().__init__()
    self.max_complexity = max_complexity
```

**2. Filter in parse_json()**

```python
# Filter by max_complexity threshold
if complexity <= self.max_complexity:
    logger.debug(
        f"Skipping function with complexity {complexity} <= threshold {self.max_complexity}"
    )
    continue
```

**3. Don't delete JSON file**

```python
# NOTE: Don't delete the JSON file - it may be reused across AI-fix iterations
# The adapter is responsible for cleanup when done
logger.debug(f"Read complexipy JSON file: {json_path} ({len(data)} entries)")
```

**4. Updated get_issue_count()**

```python
# Count only functions exceeding the threshold
return sum(
    1
    for item in data
    if isinstance(item, dict)
    and isinstance(item.get("complexity"), int)
    and item["complexity"] > self.max_complexity
)
```

### Testing

**Manual test** (using actual JSON file):

```python
# Before fix
Total functions in JSON: 6076
Issues returned by parser: 6076  # ALL functions, no filtering!

# After fix
Total functions in JSON: 6076
Functions with complexity > 15: 9
Issues returned by parser: 9  # Only high-complexity functions!
```

## Impact

### Before Fix

```
Iteration 1/5: 6037 issues to fix
Complexipy JSON file not found: /Users/les/Projects/crackerjack/complexipy_results_2026_01_30__15-38-29.json
Iteration 2/5: 13 issues to fix
```

### After Fix

```
Iteration 1/5: 13 issues to fix
Iteration 2/5: 13 issues to fix
Iteration 3/5: 13 issues to fix
...consistent across all iterations
```

## Architectural Lesson

**Single Source of Truth Principle Violation**:

- Parser had filtering logic dependency on adapter
- Two code paths (adapter vs parser) had different behavior
- AI-fix used parser directly, bypassing adapter filtering

**Correct Pattern**:

- Each component should be self-contained
- Parsers should apply their own filtering logic
- No hidden dependencies between components

## Related Files

- `crackerjack/parsers/json_parsers.py`: ComplexipyJSONParser changes
- `crackerjack/adapters/complexity/complexipy.py`: ComplexipyAdapter (unchanged)
- `crackerjack/core/autofix_coordinator.py`: AI-fix iteration logic

## Verification

To verify the fix works:

```bash
# Run AI-fix workflow
python -m crackerjack run -v --comp --ai-fix

# Expected output:
# Iteration 1/5: ~13 issues to fix
# Iteration 2/5: ~13 issues to fix
# ...consistent across iterations
```

## Future Improvements

1. **Add parser tests**: Create unit tests for ComplexipyJSONParser
1. **Audit other parsers**: Check if other parsers have similar adapter dependencies
1. **Unified filtering**: Consider moving filtering logic to a shared utility
1. **File lifecycle management**: Add proper cleanup strategy for JSON files

## Commit

- Commit: 6401611e
- Date: 2026-01-30
- Message: "fix(complexipy): Filter parser output by complexity threshold"
