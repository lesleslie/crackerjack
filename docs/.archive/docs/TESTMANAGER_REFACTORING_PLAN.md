# TestManager Refactoring Plan

**Date**: 2025-02-08
**Status**: Planned (Not Started)
**Estimated Effort**: 2-3 days
**Priority**: HIGH (Highest remaining SOLID violation)

---

## Current State

**File**: `crackerjack/managers/test_manager.py`
**Lines**: 1899 (almost 1900 lines)
**Responsibilities**: 7+ distinct concerns mixed together

**Current Problems**:
1. **God Class Anti-Pattern**: Too many responsibilities in one class
2. **Difficult to Test**: Hard to test parsing logic in isolation
3. **Maintenance Burden**: Changes ripple across multiple concerns
4. **Poor Readability**: 1900 lines is a maintenance nightmare

---

## SOLID Violation: Single Responsibility Principle

**Location**: `crackerjack/managers/test_manager.py`

**Problem**: TestManager mixes 7+ distinct responsibilities:
1. Test execution orchestration
2. Test result parsing (20+ methods)
3. UI rendering (Rich tables, panels)
4. Coverage management
5. LSP diagnostics
6. Xcode test execution
7. Statistics reporting

**Impact**:
- SRP violation (HIGH priority)
- Difficult to test in isolation
- 1900 lines creates cognitive load

---

## Refactoring Strategy

### Phase 1: Extract TestResultParser (Day 1)
**Goal**: Extract all test result parsing logic into focused class

**Methods to Extract** (~20 methods):
- `_parse_test_statistics()` - Parse test statistics from output
- `_parse_summary_match()` - Parse summary section
- `_parse_test_lines_by_token()` - Token-based line parsing
- `_parse_metric_patterns()` - Parse metric patterns
- `_parse_legacy_patterns()` - Parse legacy pytest output
- `_parse_summary_failed_line()` - Parse failure from summary
- `_parse_failure_header()` - Parse failure section header
- `_parse_location_and_assertion()` - Parse file:line:assertion
- `_parse_captured_section_header()` - Parse captured output header
- `_parse_traceback_line()` - Parse traceback lines
- `_parse_captured_output()` - Parse captured output
- `_parse_short_summary()` - Parse short test summary
- `_parse_summary_failure_line()` - Parse failure details
- `_parse_failure_line()` - Parse individual failure lines

**New Class**: `crackerjack/services/testing/test_result_parser.py`
```python
class TestResultParser:
    """Parse pytest output into structured results."""

    def __init__(self, logger: Logger):
        self.logger = logger

    def parse_test_output(self, output: str) -> TestResults:
        """Parse complete pytest output."""
        stats = self._parse_test_statistics(output)
        failures = self._parse_failures(output)
        summary = self._parse_short_summary(output)
        return TestResults(stats, failures, summary)

    # ... all parsing methods extracted here
```

**Updated TestManager**:
```python
class TestManager:
    def __init__(self, ..., result_parser: TestResultParser):
        self.result_parser = result_parser

    def _run_tests(self, ...):
        # Execute tests
        output = self._execute_test_command(...)

        # Use parser instead of internal methods
        results = self.result_parser.parse_test_output(output)
        return results
```

**Impact**:
- Remove ~600 lines from TestManager
- Create testable, focused TestResultParser (~400 lines)
- Enable isolated unit testing of parsing logic

---

### Phase 2: Extract TestResultRenderer (Day 1-2)
**Goal**: Extract UI rendering logic into focused class

**Methods to Extract** (~5 methods):
- `_render_test_results_panel()` - Render Rich panel with results
- `_render_statistics_table()` - Render statistics table
- `_render_failures_table()` - Render failures table
- `_render_coverage_summary()` - Render coverage info
- `_render_progress_indicator()` - Render progress bar

**New Class**: `crackerjack/services/testing/test_result_renderer.py`
```python
class TestResultRenderer:
    """Render test results to console using Rich."""

    def __init__(self, console: Console):
        self.console = console

    def render_results(self, results: TestResults) -> None:
        """Render complete test results to console."""
        self._render_panel(results)
        self._render_stats(results)
        self._render_failures(results)
```

**Updated TestManager**:
```python
class TestManager:
    def __init__(self, ..., renderer: TestResultRenderer):
        self.renderer = renderer

    def _run_tests(self, ...):
        results = self.result_parser.parse_test_output(output)
        self.renderer.render_results(results)
```

**Impact**:
- Remove ~200 lines from TestManager
- Create testable TestResultRenderer (~150 lines)
- Enable UI changes without touching TestManager

---

### Phase 3: Extract CoverageManager (Day 2)
**Goal**: Extract coverage management into focused class

**Methods to Extract** (~5 methods):
- `_handle_coverage_extraction_result()` - Process coverage data
- `_update_coverage_badge()` - Update coverage badge
- `_handle_ratchet_result()` - Handle ratchet system results
- `_handle_coverage_improvement()` - Report improvements
- `_extract_coverage_data()` - Extract coverage from output

**New Class**: `crackerjack/services/testing/coverage_manager.py`
```python
class CoverageManager:
    """Manage test coverage data and reporting."""

    def __init__(self, console: Console, logger: Logger):
        self.console = console
        self.logger = logger

    def process_coverage(self, output: str) -> CoverageData:
        """Extract and process coverage from test output."""
        return self._extract_coverage_data(output)

    def update_badge(self, ratchet_result: dict) -> None:
        """Update coverage badge."""
        ...
```

**Impact**:
- Remove ~150 lines from TestManager
- Create focused CoverageManager (~100 lines)
- Isolate coverage logic

---

### Phase 4: Extract XcodeTestRunner (Day 2-3)
**Goal**: Extract Xcode-specific test logic into focused class

**Methods to Extract** (~10 methods):
- `_run_xcode_tests()` - Run Xcode tests
- `_build_xcode_command()` - Build xcodebuild command
- `_parse_xcode_output()` - Parse Xcode test output
- `_handle_xcode_result()` - Process Xcode test results
- Other Xcode-specific methods

**New Class**: `crackerjack/services/testing/xcode_test_runner.py`
```python
class XcodeTestRunner:
    """Run and parse Xcode test results."""

    def __init__(self, console: Console, logger: Logger):
        self.console = console
        self.logger = logger

    def run_tests(self, project: str, scheme: str) -> XcodeTestResults:
        """Run Xcode tests and return results."""
        cmd = self._build_command(project, scheme)
        output = self._execute_xcodebuild(cmd)
        return self._parse_output(output)
```

**Impact**:
- Remove ~200 lines from TestManager
- Create focused XcodeTestRunner (~150 lines)
- Isolate platform-specific logic

---

### Phase 5: Simplify TestManager (Day 3)
**Goal**: Keep TestManager focused on orchestration only

**Remaining TestManager** (~400 lines, down from 1900):
- Test execution orchestration
- Result aggregation
- Integration with extracted services
- Lifecycle management

**Updated TestManager**:
```python
class TestManager:
    """Orchestrate test execution and result processing."""

    def __init__(
        self,
        console: Console,
        result_parser: TestResultParser,
        renderer: TestResultRenderer,
        coverage_manager: CoverageManager,
        xcode_runner: XcodeTestRunner | None,
    ):
        self.console = console
        self.result_parser = result_parser
        self.renderer = renderer
        self.coverage_manager = coverage_manager
        self.xcode_runner = xcode_runner

    def run_tests(self, options: OptionsProtocol) -> TestResults:
        """Run tests and return results (orchestration only)."""
        # Execute tests
        if options.xcode_tests and self.xcode_runner:
            results = self.xcode_runner.run_tests(...)
        else:
            output = self._execute_pytest(...)
            results = self.result_parser.parse_test_output(output)

        # Process coverage
        coverage = self.coverage_manager.process_coverage(output)

        # Render results
        self.renderer.render_results(results, coverage)

        return results
```

**Impact**:
- **78% reduction**: 1900 lines → 400 lines
- **SRP compliance**: Single responsibility (orchestration)
- **Testability**: Each component testable in isolation
- **Maintainability**: Changes localized to specific components

---

## Implementation Plan

### Day 1: Extract TestResultParser
- [ ] Create `TestResultParser` class skeleton
- [ ] Move 20 parsing methods to TestResultParser
- [ ] Update TestManager to use TestResultParser
- [ ] Run test suite to verify
- [ ] Fix any broken imports/dependencies

### Day 2: Extract Renderer & Coverage
- [ ] Create `TestResultRenderer` class
- [ ] Move rendering methods from TestManager
- [ ] Create `CoverageManager` class
- [ ] Move coverage methods from TestManager
- [ ] Update TestManager to use both
- [ ] Run tests, fix issues

### Day 3: Extract Xcode & Simplify
- [ ] Create `XcodeTestRunner` class
- [ ] Move Xcode methods from TestManager
- [ ] Simplify TestManager (remove extracted code)
- [ ] Update all imports/dependencies
- [ ] Run full test suite
- [ ] Performance verification

---

## Success Criteria

**Before**:
- TestManager: 1900 lines, 7 responsibilities
- Testing: Monolithic, hard to test in isolation
- Maintenance: Changes affect multiple concerns

**After**:
- TestManager: 400 lines (78% reduction), 1 responsibility
- Testing: Each component testable independently
- Maintenance: Changes localized to specific components
- **SRP Compliance**: ✅ Achieved

---

## Risk Assessment

**Risks**:
1. **Breaking Changes**: Extracting classes may break imports
   - **Mitigation**: Update all imports systematically
   - **Verification**: Run full test suite after each phase

2. **Performance**: Multiple class instantiations
   - **Mitigation**: Profile before/after
   - **Expected**: Minimal impact (same operations, different organization)

3. **Test Coverage**: May temporarily decrease during refactor
   - **Mitigation**: Write tests for new classes
   - **Goal**: Maintain or improve coverage

**Risk Level**: MEDIUM (manageable with systematic approach)

---

## Next Steps

**Immediate**: Get user approval to proceed with TestManager refactoring

**After Approval**:
1. Start Phase 1: Extract TestResultParser (Day 1)
2. Continue through all 5 phases
3. Verify with full test suite after each phase
4. Commit after each major milestone

---

**Status**: READY TO BEGIN (pending user approval)
**Estimated Timeline**: 2-3 days
**Impact**: 78% complexity reduction, SRP compliance
