# Test Management Refactoring Plan

## Objective

Reduce complexity violations in test management files to ≤15 per method while preserving all functionality.

## Files to Refactor

### 1. test_manager.py - `_parse_test_statistics` (Complexity 33)

**Current Issues:**

- Complex regex pattern matching with multiple fallback strategies
- Mixed concerns: parsing summary, extracting metrics, calculating totals, handling fallbacks
- Deep conditional nesting for different output formats

**Refactoring Strategy:**
Break into focused helper methods:

1. `_extract_pytest_summary` - Find summary line in output
1. `_extract_duration_from_summary` - Parse duration
1. `_extract_test_metrics` - Parse individual metrics (passed, failed, etc.)
1. `_calculate_total_tests` - Sum metrics
1. `_extract_coverage_from_output` - Parse coverage percentage
1. `_fallback_count_tests` - Manual counting when parsing fails

**Expected Complexity After Refactoring:**

- Main method: ~8-10
- Each helper: 3-6

### 2. test_command_builder.py - Verification Needed

**Status:** Need to verify if complexity violation exists

- The `build_command` method (lines 30-40) appears simple
- May need to check if there's a different method with high complexity

## Implementation Steps

1. Create helper methods for test statistics parsing
1. Extract regex patterns to constants
1. Simplify conditional logic with early returns
1. Test each extraction independently
1. Verify all test execution logic preserved

## Success Criteria

- All methods ≤15 complexity
- All existing tests pass
- No behavior changes in test execution
- Coverage maintained
- pytest integration intact

## Risk Assessment

**Low Risk:**

- Pure refactoring (extract method pattern)
- No logic changes
- Well-tested code paths

**Mitigation:**

- Run full test suite after each refactoring step
- Verify against baseline behavior
