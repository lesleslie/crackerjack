# regex_utils.py - Implementation Analysis

**File**: crackerjack/services/regex_utils.py
**Lines**: 405
**Statements**: 179 (from coverage report)
**Status**: 0% coverage → Target 70-75%

---

## Implementation Structure

### Public Functions (9)

#### 1. test_pattern_immediately(pattern, replacement, test_cases, description) (lines 8-67)
**Purpose**: Test regex pattern immediately with test cases
**Returns**: dict with test results, warnings, errors
**Logic**:
- Compiles pattern using CompiledPatternCache
- Runs test cases (input, expected) pairs
- Returns detailed results dict
- Checks for performance warnings (.*.*, .+.+)
- Handles invalid patterns (catches ValueError)

**Returns dict structure**:
```python
{
    "pattern": str,
    "replacement": str,
    "description": str,
    "all_passed": bool,
    "test_results": [{"test_case": int, "input": str, "expected": str, "actual": str, "passed": bool}],
    "warnings": [str],
    "errors": [str]
}
```

#### 2. print_pattern_test_report(results) (lines 70-86)
**Purpose**: Print formatted test report (no-op function for now)
**Logic**: Does nothing (all pass statements)

#### 3. quick_pattern_test(pattern, replacement, test_cases, description) (lines 88-97)
**Purpose**: Quick pattern test wrapper that returns bool
**Logic**: Calls test_pattern_immediately, prints report, returns all_passed

#### 4. find_safe_pattern_for_text(text) (lines 100-108)
**Purpose**: Find which SAFE_PATTERNS match given text
**Returns**: list of pattern names that match
**Logic**: Iterates SAFE_PATTERNS, tests each, returns matches

#### 5. suggest_migration_for_re_sub(original_pattern, original_replacement, sample_text) (lines 147-183)
**Purpose**: Suggest migration from re.sub to SAFE_PATTERNS
**Returns**: dict with migration suggestions
**Logic**:
- Checks for forbidden patterns (spaces in \g<1>)
- Finds existing safe patterns that match sample_text
- Determines suggested name
- Builds test cases

**Returns dict structure**:
```python
{
    "original_pattern": str,
    "original_replacement": str,
    "existing_matches": [str],
    "needs_new_pattern": bool,
    "safety_issues": [str],
    "suggested_name": str,
    "test_cases_needed": [(input, expected)]
}
```

#### 6. print_migration_suggestion(suggestion) (lines 186-203)
**Purpose**: Print migration suggestion (no-op function for now)
**Logic**: Does nothing (all pass statements)

#### 7. audit_file_for_re_sub(file_path) (lines 206-241)
**Purpose**: Audit a Python file for unsafe re.sub usage
**Returns**: list of findings dicts
**Logic**:
- Reads file content
- Searches for re.sub(pattern, replacement, text) patterns
- Returns findings with line numbers, patterns, and suggestions

#### 8. audit_codebase_re_sub() (lines 244-257)
**Purpose**: Audit entire crackerjack codebase for unsafe re.sub
**Returns**: dict mapping file paths to findings
**Logic**:
- Scans crackerjack directory for *.py files
- Skips test files and __pycache__
- Calls audit_file_for_re_sub for each
- Returns aggregated findings

#### 9. replace_unsafe_regex_with_safe_patterns(content) (lines 260-286)
**Purpose**: Replace unsafe re.sub calls with SAFE_PATTERNS in code
**Returns**: Modified content or original content
**Logic**:
- Splits content into lines
- Checks for existing SAFE_PATTERNS import
- Processes each line:
  - Fixes replacement syntax issues
  - Processes re.sub patterns
  - Adds import if needed
- Returns modified content if any changes made

---

## Private Functions (11)

#### 1. _determine_suggested_name(original_pattern) (lines 111-126)
**Purpose**: Generate suggested pattern name from pattern
**Returns**: str (suggested name)
**Logic**:
- Checks for known patterns (python command, double dash, token, password)
- Extracts keywords using regex
- Returns "fix_.*_pattern" or "fix_custom_pattern"

#### 2. _build_test_cases(original_pattern, sample_text) (lines 129-144)
**Purpose**: Build test cases for pattern testing
**Returns**: list of (input, expected) tuples
**Logic**:
- Adds sample_text as first test case if provided
- Adds default test cases if "-" in pattern

#### 3. _check_for_safe_patterns_import(lines) (lines 289-294)
**Purpose**: Check if SAFE_PATTERNS import exists
**Returns**: bool

#### 4. _fix_replacement_syntax_issues(line) (lines 297-303)
**Purpose**: Fix spacing in \g<1> replacement syntax
**Returns**: corrected line
**Logic**: Finds `\g < 1`, `\g< 1`, `\g <1` patterns and fixes to `\g<1>`

#### 5. _process_re_sub_patterns(line, has_safe_patterns_import) (lines 306-324)
**Purpose**: Process re.sub patterns in line
**Returns**: tuple (modified_line, replaced, needs_import)
**Logic**:
- Searches for re.sub(pattern, replacement, text)
- Identifies safe pattern equivalent
- Returns replacement or original line

#### 6. _identify_safe_pattern(pattern, replacement) (lines 327-337)
**Purpose**: Identify safe pattern name from pattern/replacement
**Returns**: str (pattern name) or None
**Logic**:
- Checks for fix_hyphenated_names: `(\w+)\s*-\s*(\w+)` with `\1-\2` or `\g<1>-\g<2>`
- Checks for mask_tokens: pattern has "token", replacement has "*"
- Checks for fix_python_command_spacing: pattern has `python\s*-\s*m`
- Returns None if no match

#### 7. _replace_with_safe_pattern(line, re_sub_match, safe_pattern_name) (lines 340-360)
**Purpose**: Replace re.sub call with safe pattern
**Returns**: tuple (new_line, replaced, needs_import)
**Logic**:
- Extracts text before and after re.sub match
- Checks for assignment pattern
- Delegates to assignment or direct replacement handler

#### 8. _handle_assignment_pattern(line, assign_match, before_re_sub, after_re_sub, safe_pattern_name) (lines 363-373)
**Purpose**: Handle re.sub in assignment context
**Returns**: tuple (new_line, replaced, needs_import)
**Logic**: Converts `var = re.sub(...)` to `var = SAFE_PATTERNS['name'].apply(text_var)`

#### 9. _handle_direct_replacement(line, re_sub_match, safe_pattern_name) (lines 376-386)
**Purpose**: Handle direct re.sub replacement
**Returns**: tuple (new_line, replaced, needs_import)
**Logic**: Replaces re.sub call with `SAFE_PATTERNS['name'].apply(text_var)`

#### 10. _extract_source_variable(line) (lines 389-393)
**Purpose**: Extract source variable name from re.sub call
**Returns**: str (variable name or "text")
**Logic**: Searches for third parameter to re.sub (the source text)

#### 11. _find_import_insertion_point(lines) (lines 396-405)
**Purpose**: Find best line to insert import statement
**Returns**: int (line number)
**Logic**: Finds last import line, returns next line number

---

## Testing Strategy

### Test Groups (estimated 30-35 tests)

#### Group 1: test_pattern_immediately() (6 tests) ⭐ CRITICAL
- ✅ Valid pattern with all tests passing
- ✅ Valid pattern with some tests failing
- ✅ Invalid pattern (raises ValueError) → errors list
- ✅ Performance warning for .*.* pattern
- ✅ Performance warning for .+.+ pattern
- ✅ Both warnings for patterns with both constructs

#### Group 2: print_pattern_test_report() (1 test)
- ✅ Function runs without error (no-op)

#### Group 3: quick_pattern_test() (3 tests)
- ✅ Returns True when all tests pass
- ✅ Returns False when some tests fail
- ✅ Calls print_pattern_test_report

#### Group 4: find_safe_pattern_for_text() (3 tests)
- ✅ Returns empty list when no patterns match
- ✅ Returns matching pattern names
- ✅ Handles exceptions from pattern.test()

#### Group 5: suggest_migration_for_re_sub() (6 tests) ⭐ CRITICAL
- ✅ Detects forbidden patterns (spaces in \g<1>)
- ✅ Finds existing safe patterns for sample_text
- ✅ Determines suggested name
- ✅ Builds test cases from sample_text
- ✅ Builds default test cases for "-" patterns
- ✅ Returns needs_new_pattern=False when matches exist

#### Group 6: print_migration_suggestion() (1 test)
- ✅ Function runs without error (no-op)

#### Group 7: audit_file_for_re_sub() (5 tests) ⭐ CRITICAL
- ✅ Finds re.sub calls in file
- ✅ Returns line numbers correctly
- ✅ Extracts pattern and replacement
- ✅ Handles file read errors
- ✅ Returns empty list when no re.sub found

#### Group 8: audit_codebase_re_sub() (3 tests)
- ✅ Scans crackerjack directory
- ✅ Skips test files
- ✅ Returns findings_by_file dict

#### Group 9: replace_unsafe_regex_with_safe_patterns() (4 tests) ⭐ CRITICAL
- ✅ Replaces re.sub with safe patterns
- ✅ Adds import when needed
- ✅ Fixes replacement syntax issues
- ✅ Returns original content when no changes

#### Group 10: _determine_suggested_name() (5 tests)
- ✅ Returns fix_python_command_spacing for python.*-.*m
- ✅ Returns fix_double_dash_spacing for \-\s*\-
- ✅ Returns fix_token_pattern for "token"
- ✅ Returns fix_password_pattern for "password"
- ✅ Returns fix_custom_pattern as fallback

#### Group 11: _build_test_cases() (3 tests)
- ✅ Adds sample_text test case
- ✅ Adds default test cases for "-" patterns
- ✅ Returns only sample test when no "-" in pattern

#### Group 12: _check_for_safe_patterns_import() (2 tests)
- ✅ Returns True when import exists
- ✅ Returns False when no import

#### Group 13: _fix_replacement_syntax_issues() (2 tests)
- ✅ Fixes \g < 1 spacing
- ✅ Fixes \g< 1 and \g <1 spacing

#### Group 14: _identify_safe_pattern() (4 tests)
- ✅ Identifies fix_hyphenated_names
- ✅ Identifies mask_tokens
- ✅ Identifies fix_python_command_spacing
- ✅ Returns None for unknown patterns

#### Group 15: _extract_source_variable() (2 tests)
- ✅ Extracts variable name from re.sub call
- ✅ Returns "text" as default

#### Group 16: _find_import_insertion_point() (2 tests)
- ✅ Finds insertion point after imports
- ✅ Returns 0 when no imports

---

## Key Testing Points

### MUST Test:
1. ✅ test_pattern_immediately() - all branches (errors, warnings, test results)
2. ✅ suggest_migration_for_re_sub() - forbidden pattern detection
3. ✅ audit_file_for_re_sub() - regex pattern matching
4. ✅ replace_unsafe_regex_with_safe_patterns() - line transformation
5. ✅ Safe pattern identification logic
6. ✅ Import insertion logic

### MOCK:
1. ✅ CompiledPatternCache (mock get_compiled_pattern)
2. ✅ SAFE_PATTERNS (mock dictionary)
3. ✅ File I/O (use tmp_path fixture)

### SKIP (intentionally):
1. ❌ print functions (no-ops, just verify they run)
2. ❌ Exact regex matching details (use approximate checks)

---

## Estimated Coverage

**Target**: 70-75% of 179 statements = 125-134 statements

**Achievable via**:
- 30-35 test methods
- Testing all public functions
- Testing core private helpers
- Testing error handling paths

**Uncovered** (~25-30%):
- Some regex edge cases
- Complex pattern matching scenarios
- Some print function internals
- Some exception handling edge cases

---

## Dependencies

- **CompiledPatternCache** from regex_patterns
- **SAFE_PATTERNS** from regex_patterns
- **re** (standard library)
- **pathlib.Path** (standard library)

---

## Complexity Assessment

**Expected Complexity**: Medium

- Pure functions with clear logic
- Regex pattern matching (moderate complexity)
- String manipulation (low-medium complexity)
- File I/O (simple read/write)
- No external dependencies beyond regex_patterns

---

## Test Creation Strategy

1. **Mock CompiledPatternCache**: Prevent actual regex compilation side effects
2. **Mock SAFE_PATTERNS**: Control safe pattern matching behavior
3. **Use tmp_path fixture**: For file audit tests
4. **Focus on core logic**: Pattern identification, migration, replacement
5. **Test error cases**: Invalid patterns, file read errors
6. **Avoid complex regex**: Use simple test patterns
