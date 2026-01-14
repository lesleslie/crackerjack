# Sprint 8: Test Coverage Improvement Plan

**Dates**: 2026-01-14
**Status**: Planning
**Target**: 3 files (522 total statements)
**Goal**: 60-70% coverage average
**Estimated Duration**: 4-5 hours
**Estimated Tests**: ~150-170

---

## Executive Summary

Sprint 8 continues systematic test coverage improvement by targeting three high-impact adapter and CLI handler files that currently have 0% coverage:

1. **adapters/complexity/complexipy.py** (220 statements) - Complexity analysis adapter
2. **cli/handlers/analytics.py** (165 statements) - Analytics CLI commands
3. **adapters/refactor/refurb.py** (137 statements) - Refactoring suggestions adapter

**Total Scope**: 522 statements across 3 files

**Success Criteria**:
- ✅ All tests passing (100% pass rate)
- ✅ 60-70% average coverage across all files
- ✅ Zero implementation bugs introduced
- ✅ Comprehensive documentation created

---

## Target Files Selection

### Priority Matrix

| File | Statements | 0% Coverage | Complexity | Impact | Priority |
|------|------------|-------------|------------|--------|----------|
| adapters/complexity/complexipy.py | 220 | Yes | Medium | HIGH | **P1** |
| cli/handlers/analytics.py | 165 | Yes | Medium | HIGH | **P1** |
| adapters/refactor/refurb.py | 137 | Yes | Low-Medium | MEDIUM | **P1** |
| adapters/lsp/zuban.py | 242 | Yes | High | HIGH | P2 |
| adapters/utility/checks.py | 269 | Yes | Low | MEDIUM | P2 |
| agents/refactoring_helpers.py | 163 | Yes | Medium | HIGH | P2 |

**Selection Rationale**:
- **complexipy.py**: Core complexity analysis adapter, critical for quality checks
- **analytics.py**: CLI analytics commands, important for user insights
- **refurb.py**: Refactoring suggestions, valuable for code improvement
- **Total**: 522 statements (similar scope to Sprint 7's 532)

**Not Selected** (high complexity/dependencies):
- `adapters/lsp/zuban.py` (242 statements) - LSP client complexity
- `adapters/utility/checks.py` (269 statements) - Lower immediate impact

---

## File 1: adapters/complexity/complexipy.py

**File**: `crackerjack/adapters/complexity/complexipy.py`
**Lines**: 455
**Statements**: 220
**Current Coverage**: 0%
**Target Coverage**: 60-65%
**Estimated Tests**: ~60-70

### Functionality

ComplexipyAdapter provides complexity analysis using the complexipy tool:

1. **Complexity Calculation**: Calculate cyclomatic complexity for Python files
2. **File Analysis**: Analyze individual files or directories
3. **Threshold Checking**: Check complexity against configurable thresholds
4. **Result Reporting**: Generate complexity reports with file/function-level details
5. **Integration**: QA adapter interface for pre-commit hooks

### Key Classes/Functions

- `ComplexipyAdapter`: Main adapter class
- `analyze()`: Run complexity analysis
- `parse_output()`: Parse complexipy output
- `check_thresholds()`: Verify complexity thresholds
- Private helpers: file filtering, result formatting

### Testing Challenges

- **External tool dependency**: complexipy must be installed
- **Output parsing**: Complex JSON/text parsing logic
- **File system operations**: Temp file handling for test code
- **Threshold logic**: Multiple complexity thresholds (A, B, C ratings)

### Test Strategy

- Mock complexipy execution (don't require actual tool)
- Test output parsing with mock data
- Test threshold checking logic
- Test file filtering and result formatting
- Module-level import pattern to avoid pytest conflicts

---

## File 2: cli/handlers/analytics.py

**File**: `crackerjack/cli/handlers/analytics.py`
**Lines**: ~300 (estimated)
**Statements**: 165
**Current Coverage**: 0%
**Target Coverage**: 60-65%
**Estimated Tests**: ~45-55

### Functionality

Analytics CLI handlers provide analytics and reporting commands:

1. **Analytics Display**: Show test analytics, coverage trends
2. **Report Generation**: Generate various reports (HTML, JSON, text)
3. **Data Aggregation**: Aggregate metrics from multiple sources
4. **Trend Analysis**: Calculate trends over time
5. **CLI Integration**: Register analytics commands with CLI

### Key Classes/Functions

- `register_analytics_commands()`: CLI command registration
- `show_analytics()`: Display analytics dashboard
- `generate_report()`: Generate formatted reports
- `calculate_trends()`: Compute trend metrics
- Private helpers: data formatting, output generation

### Testing Challenges

- **CLI dependency**: Requires CLI infrastructure setup
- **Rich console output**: Complex output formatting
- **Data aggregation**: Multiple data sources
- **File output**: Report file generation

### Test Strategy

- Mock CLI dependencies (console, config)
- Test command registration logic
- Test analytics calculation with mock data
- Test report generation with temp files
- Mock rich console output

---

## File 3: adapters/refactor/refurb.py

**File**: `crackerjack/adapters/refactor/refurb.py`
**Lines**: ~240 (estimated)
**Statements**: 137
**Current Coverage**: 0%
**Target Coverage**: 65-70%
**Estimated Tests**: ~40-50

### Functionality

RefurbAdapter provides refactoring suggestions using the refurb tool:

1. **Refurb Analysis**: Run refurb to find Python code improvements
2. **Result Parsing**: Parse refurb output into structured format
3. **Suggestion Filtering**: Filter suggestions by type/severity
4. **Auto-fixing**: Apply automatic fixes where possible
5. **Integration**: QA adapter interface for pre-commit hooks

### Key Classes/Functions

- `RefurbAdapter`: Main adapter class
- `analyze()`: Run refurb analysis
- `parse_output()`: Parse refurb output
- `apply_fixes()`: Apply automatic fixes
- Private helpers: result filtering, fix application

### Testing Challenges

- **External tool dependency**: refurb must be installed
- **Output parsing**: JSON/text parsing from refurb
- **Fix application**: File modification logic
- **Suggestion categorization**: Different refactor types

### Test Strategy

- Mock refurb execution
- Test output parsing with mock data
- Test fix application with temp files
- Test suggestion filtering logic
- Verify adapter protocol compliance

---

## Testing Approach

### Sprint 8 Strategy: Adapter & CLI Focus

**Key Differences from Sprint 7**:
- Focus on **adapters** (external tool integrations)
- Focus on **CLI handlers** (user-facing commands)
- More **external dependencies** to mock
- More **file I/O** operations

**Success Factors from Sprint 7** (to continue):
1. ✅ Read implementation thoroughly FIRST
2. ✅ Use module-level import pattern
3. ✅ Mock external dependencies aggressively
4. ✅ Test file I/O with temp directories
5. ✅ Create comprehensive analysis documents

### Testing Techniques

1. **Adapter Testing Pattern**:
   ```python
   # Mock external tool execution
   @patch("subprocess.run")
   def test_analyze_with_mocked_tool(self, mock_run: Mock) -> None:
       mock_run.return_value = CompletedProcess(
           args=["complexipy"],
           returncode=0,
           stdout='{"files": [...]}',
           stderr=""
       )
       adapter = ComplexipyAdapter()
       result = adapter.analyze(Path("test.py"))
   ```

2. **CLI Handler Testing Pattern**:
   ```python
   # Mock CLI dependencies
   @patch("rich.console.Console")
   def test_show_analytics(self, mock_console: Mock) -> None:
       handler = AnalyticsHandler(console=mock_console)
       handler.show_analytics(mock_data)
       mock_console.print.assert_called()
   ```

3. **File I/O Testing Pattern**:
   ```python
   def test_apply_fixes_with_temp_file(self, tmp_path: Path) -> None:
       test_file = tmp_path / "test.py"
       test_file.write_text("original code")
       adapter.apply_fixes(test_file)
       assert "fixed code" in test_file.read_text()
   ```

---

## Timeline & Phases

### Phase 1: complexipy.py (~1.5 hours)
- [ ] Read implementation (455 lines) - 30 min
- [ ] Create analysis document - 15 min
- [ ] Write tests (~60-70 tests) - 45 min
- [ ] Run and fix failures - 15 min

### Phase 2: analytics.py (~1.5 hours)
- [ ] Read implementation (~300 lines) - 30 min
- [ ] Create analysis document - 15 min
- [ ] Write tests (~45-55 tests) - 45 min
- [ ] Run and fix failures - 15 min

### Phase 3: refurb.py (~1.5 hours)
- [ ] Read implementation (~240 lines) - 30 min
- [ ] Create analysis document - 15 min
- [ ] Write tests (~40-50 tests) - 45 min
- [ ] Run and fix failures - 15 min

**Total Estimated Duration**: 4.5 hours

---

## Risk Assessment

### Low Risk ✅
- **refurb.py**: Simple adapter pattern, clear output format
- File I/O testing pattern established from Sprint 7

### Medium Risk ⚠️
- **analytics.py**: CLI dependency complexity
- Rich console output mocking
- Multiple data source aggregation

### Higher Risk ⚠️⚠️
- **complexipy.py**: Complex JSON parsing logic
- Multiple complexity thresholds
- External tool behavior nuances

**Mitigation Strategies**:
1. Read implementation more thoroughly for complexipy.py
2. Create comprehensive mock data for all edge cases
3. Test parsing logic in isolation first
4. Use Sprint 7 patterns for file I/O and mocking

---

## Success Metrics

### Coverage Targets

| File | Statements | Target | Minimum Acceptable |
|------|------------|--------|-------------------|
| complexipy.py | 220 | 60-65% | 55% |
| analytics.py | 165 | 60-65% | 55% |
| refurb.py | 137 | 65-70% | 60% |
| **AVERAGE** | **522** | **60-70%** | **57%** |

### Quality Gates

- ✅ 100% test pass rate (no skipping tests)
- ✅ Zero implementation bugs introduced
- ✅ All public API methods tested
- ✅ Core logic paths covered
- ✅ Error handling tested
- ✅ Edge cases covered

### Documentation Deliverables

1. **SPRINT8_COMPLEXIPY_ANALYSIS.md** - Implementation analysis
2. **SPRINT8_COMPLEXIPY_COMPLETE.md** - Phase 1 completion
3. **SPRINT8_ANALYTICS_ANALYSIS.md** - Implementation analysis
4. **SPRINT8_ANALYTICS_COMPLETE.md** - Phase 2 completion
5. **SPRINT8_REFURB_ANALYSIS.md** - Implementation analysis
6. **SPRINT8_REFURB_COMPLETE.md** - Phase 3 completion
7. **SPRINT8_COMPLETE.md** - Overall sprint completion

---

## Comparison to Sprint 7

| Metric | Sprint 7 | Sprint 8 | Change |
|--------|----------|----------|--------|
| Files tested | 3 | 3 | Same |
| Total statements | 532 | 522 | -2% |
| Domain focus | Services | Adapters/CLI | **Different** |
| External deps | 2 (numpy, regex) | 3 (complexipy, refurb, rich) | +1 |
| File I/O | Low | **High** | **Increase** |
| Estimated tests | 161 | ~150-170 | Similar |
| Target coverage | 65-70% | 60-70% | Same |

**Key Differences**:
- Sprint 7: Service layer (business logic)
- Sprint 8: Adapter + CLI layer (integration and user interface)

**Similarities**:
- Same file count (3)
- Similar statement count (~520-530)
- Same testing patterns (mock external deps)
- Same success criteria

---

## Lessons from Sprint 7 to Apply

### What Worked Well ✅

1. **Reading implementation first** - Prevented 95% of test failures
2. **Module-level import pattern** - Zero pytest conflicts
3. **Comprehensive analysis docs** - 200+ lines before writing tests
4. **Mock external dependencies** - Isolated code under test
5. **File I/O with /tmp/** - Clean test setup/teardown

### Improvements for Sprint 8 🚀

1. **More focus on adapter patterns** - Understand QA adapter protocol
2. **Better CLI mocking** - Rich console and CLI infrastructure
3. **Comprehensive tool output mocking** - Realistic external tool data
4. **Temp file management** - Consistent cleanup patterns

---

## Next Steps

1. ✅ Start Phase 1: Read complexipy.py implementation
2. ✅ Create SPRINT8_COMPLEXIPY_ANALYSIS.md
3. ✅ Write comprehensive tests for complexipy.py
4. ✅ Run tests and fix failures
5. ✅ Document Phase 1 completion
6. ✅ Continue to Phase 2 (analytics.py)
7. ✅ Continue to Phase 3 (refurb.py)
8. ✅ Create overall Sprint 8 completion documentation

---

**Sprint 8 Status**: 📋 **PLANNED**
**Start Date**: 2026-01-14
**Expected Completion**: 2026-01-14
**Overall Goal**: Add 60-70% coverage to 522 statements (3 files)
