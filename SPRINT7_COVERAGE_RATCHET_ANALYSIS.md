# coverage_ratchet.py - Implementation Analysis

**File**: crackerjack/services/coverage_ratchet.py
**Lines**: 392
**Statements**: 190
**Status**: 0% coverage → Target 65-70%

---

## Implementation Structure

### Class: CoverageRatchetService

**Inherits**: CoverageRatchetProtocol
**Purpose**: Manage coverage ratchet system - ensures coverage never decreases below baseline

### Constants (2)
- **MILESTONES** (line 15): [15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 95, 100]
- **TOLERANCE_MARGIN** (line 17): 2.0 (percentage points allowed below baseline)

### Constructor (lines 19-30)
**Parameters**:
- `pkg_path: Path` - Project root path
- `console: Console | None = None` - Rich console for output

**Initialization**:
- Converts pkg_path to Path (with exception handling)
- Sets `ratchet_file = pkg_path / ".coverage-ratchet.json"`
- Sets `pyproject_file = pkg_path / "pyproject.toml"`

### Protocol Methods (12 no-op methods, lines 32-66)

**All empty implementations** (satisfy CoverageRatchetProtocol):
1. `initialize()` - Does nothing
2. `cleanup()` - Does nothing
3. `health_check()` - Returns True
4. `shutdown()` - Does nothing
5. `metrics()` - Returns empty dict
6. `is_healthy()` - Returns True
7. `register_resource(resource)` - Does nothing
8. `cleanup_resource(resource)` - Does nothing
9. `record_error(error)` - Does nothing
10. `increment_requests()` - Does nothing
11. `get_custom_metric(name)` - Returns None
12. `set_custom_metric(name, value)` - Does nothing

### Core Public Methods (13 methods)

#### 1. initialize_baseline(initial_coverage: float) (lines 68-92)
**Purpose**: Create initial ratchet file

**Logic**:
- If ratchet file exists, return early
- Creates JSON structure with:
  - `baseline`: initial_coverage
  - `current_minimum`: initial_coverage
  - `target`: 100.0
  - `last_updated`: ISO timestamp
  - `history`: list with one entry
  - `milestones_achieved`: empty list
  - `next_milestone`: calculated via _get_next_milestone()

**Side Effect**: Writes .coverage-ratchet.json file

#### 2. get_ratchet_data() -> dict[str, Any] (lines 94-97)
**Purpose**: Read ratchet JSON file

**Returns**: Empty dict if file doesn't exist

#### 3. get_status_report() -> dict[str, Any] (lines 99-100)
**Purpose**: Alias for get_ratchet_data()

#### 4. get_baseline() -> float (lines 102-105)
**Purpose**: Get baseline coverage

**Returns**: Baseline as float, or 0.0 if no baseline

#### 5. get_baseline_coverage() -> float (lines 107-108)
**Purpose**: Alias for get_baseline()

#### 6. update_baseline_coverage(new_coverage: float) -> bool (lines 110-112)
**Purpose**: Update baseline and return success

**Returns**: Result["success"] or Result["allowed"]

#### 7. is_coverage_regression(current_coverage: float) -> bool (lines 114-116)
**Purpose**: Check if coverage is below tolerance threshold

**Formula**: `current_coverage < (baseline - TOLERANCE_MARGIN)`

#### 8. calculate_coverage_gap() -> float (lines 118-126)
**Purpose**: Calculate points needed to reach next milestone

**Returns**: next_milestone - baseline, or 100.0 - baseline if no next milestone

#### 9. update_coverage(new_coverage: float) -> dict[str, Any] (lines 128-182) ⭐ CORE
**Purpose**: Main logic method - handles all coverage update scenarios

**Branches**:

1. **No ratchet file** (lines 129-138):
   - Calls initialize_baseline()
   - Returns: `{status: "initialized", allowed: True, baseline_updated: True, ...}`

2. **Coverage regression** (lines 143-152):
   - Condition: `new_coverage < (baseline - TOLERANCE_MARGIN)`
   - Returns: `{status: "regression", allowed: False, baseline_updated: False, ...}`

3. **Coverage improved** (lines 153-175):
   - Condition: `new_coverage > baseline + 0.01`
   - Checks milestones via _check_milestones()
   - Calls _update_baseline()
   - Calls _update_pyproject_requirement()
   - Returns: `{status: "improved", allowed: True, baseline_updated: True, ...}`

4. **Coverage maintained** (lines 177-182):
   - Within tolerance margin
   - Returns: `{status: "maintained", allowed: True, baseline_updated: False}`

#### 10. get_progress_visualization() -> str (lines 260-279)
**Purpose**: Generate ASCII progress bar

**Returns**: String with bar like "Coverage Progress: 65.00% [█████████████░░░░░░░] → 100%"

#### 11. get_coverage_improvement_needed() -> float (lines 281-287)
**Purpose**: Calculate points to next milestone

**Returns**: max(0.0, next_milestone - current_coverage)

#### 12. get_coverage_report() -> str | None (lines 347-362)
**Purpose**: Get formatted coverage report

**Returns**: String like "Coverage: 65.00% (next milestone: 70%, 92.9% there)" or None

#### 13. check_and_update_coverage() -> dict[str, Any] (lines 364-391) ⭐ CORE
**Purpose**: Read coverage.json and update ratchet

**Logic**:
- Checks if coverage.json exists
- Reads `totals.percent_covered` from coverage.json
- Calls update_coverage() with the value
- Returns result with "success" key added

**Exception Handling**: Returns error dict if exception occurs

### Private Helper Methods (4)

#### 1. _check_milestones(old, new, data) -> list[float] (lines 184-198)
**Purpose**: Find milestones achieved between old and new coverage

**Returns**: List of milestone values

#### 2. _get_next_milestone(coverage) -> float | None (lines 200-204)
**Purpose**: Get next milestone above current coverage

**Returns**: First milestone > coverage, or None if at 100%

#### 3. _update_baseline(new_coverage, data, milestones_hit) (lines 206-235)
**Purpose**: Update ratchet data with new coverage

**Side Effects**:
- Updates data dict in-place
- Appends to history
- Trims history to 50 entries max
- Writes ratchet file

#### 4. _update_pyproject_requirement(new_coverage) (lines 237-258)
**Purpose**: Update pyproject.toml coverage requirement

**Side Effects**:
- Reads pyproject.toml
- Calls update_coverage_requirement() from regex_patterns
- Writes updated file
- Prints console message

**Exception Handling**: Catches and prints warning on error

### Display Methods (2)

#### 1. display_milestone_celebration(milestones: list[float]) (lines 307-324)
**Purpose**: Display Rich console output for milestones

**Conditions**:
- 100%: Gold emoji "PERFECT! 100% COVERAGE ACHIEVED!"
- ≥90%: Gold "Approaching perfection!"
- ≥50%: Green "Great progress!"
- <50%: Cyan "Keep it up!"

#### 2. show_progress_with_spinner() (lines 326-345)
**Purpose**: Display Rich progress bar with spinner

**Uses**: Rich Progress with SpinnerColumn, BarColumn, etc.

### Private Analysis Method (1)

#### 1. _calculate_trend(data) -> str (lines 289-305)
**Purpose**: Analyze coverage trend from history

**Returns**:
- "improving" if last coverage > first coverage + 0.5
- "declining" if last coverage < first coverage - 0.5
- "stable" otherwise
- "insufficient_data" if <2 history entries

---

## Testing Strategy

### Test Groups (estimated 25-30 tests)

#### Group 1: Constructor & Protocol Methods (6 tests)
- ✅ Test constructor with Path
- ✅ Test constructor with string path
- ✅ Test console parameter (default vs provided)
- ✅ Test all protocol no-op methods
- ✅ Test ratchet_file path initialization
- ✅ Test pyproject_file path initialization

#### Group 2: Baseline Initialization (4 tests)
- ✅ Test initialize_baseline creates ratchet file
- ✅ Test initialize_baseline with existing file (idempotent)
- ✅ Test initial data structure (all fields present)
- ✅ Test console output message

#### Group 3: Coverage Update Logic (8 tests) ⭐ CRITICAL
- ✅ Test update_coverage with no ratchet file (initialization)
- ✅ Test update_coverage regression (below tolerance)
- ✅ Test update_coverage improvement (above baseline + 0.01)
- ✅ Test update_coverage maintained (within tolerance)
- ✅ Test tolerance_margin boundary condition
- ✅ Test improvement threshold (exactly 0.01%)
- ✅ Test regression detection (exactly at tolerance threshold)
- ✅ Test milestone detection during improvement

#### Group 4: Milestone Logic (4 tests)
- ✅ Test _check_milestones with no milestones
- ✅ Test _check_milestones with one milestone
- ✅ Test _check_milestones with multiple milestones
- ✅ Test _get_next_milestone (all scenarios)

#### Group 5: Baseline & Gap Calculations (3 tests)
- ✅ Test get_baseline with no file
- ✅ Test get_baseline with file
- ✅ Test calculate_coverage_gap

#### Group 6: Progress Visualization (3 tests)
- ✅ Test get_progress_visualization with no data
- ✅ Test get_progress_visualization with data
- ✅ Test get_coverage_report

#### Group 7: File Operations (3 tests)
- ✅ Test check_and_update_coverage with no coverage.json
- ✅ Test check_and_update_coverage with coverage.json
- ✅ Test _update_pyproject_requirement success

#### Group 8: Edge Cases (3-4 tests)
- ✅ Test history trimming (max 50 entries)
- ✅ Test _calculate_trend with insufficient data
- ✅ Test _calculate_trend improving
- ✅ Test _calculate_trend declining/stable

---

## Key Testing Points

### MUST Test:
1. ✅ All four update_coverage branches (regression, improvement, maintained, initialized)
2. ✅ Tolerance margin boundary conditions
3. ✅ Milestone detection logic
4. ✅ File creation and reading

### MOCK:
1. ✅ File system operations (use Path objects with temp directories)
2. ✅ Console output (use Mock() for Console)

### SKIP (intentionally):
1. ❌ Rich console formatting details (too visual)
2. ❌ Exact progress bar characters (implementation detail)

---

## Estimated Coverage

**Target**: 65-70% of 190 statements = 124-133 statements

**Achievable via**:
- 25-30 test methods
- Testing all core logic paths
- Accepting untested visual/formatting code

**Uncovered** (~30-35%):
- Rich console formatting (progress bars, spinners)
- Some exception handling branches
- Visual output details
