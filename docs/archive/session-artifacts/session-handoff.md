# Test Fixing Session - Handoff Document

## Current Status

- **Test Results**: 644 failed, 1894 passed, 33 skipped, 197 errors
- **Progress**: Structural fixes completed, now analyzing remaining 197 errors
- **Pass Rate**: 74.5% (1894/2538 tests running without errors/failures)

## Completed Work

### 1. Fixed 305 Module-Level Test Functions (29 files)

**Problem**: Test functions at module level had `(self)` parameter, causing pytest to treat them as class methods and request a `self` fixture.

**Files Fixed**:

- test_code_cleaner.py (29 functions)
- test_resource_manager.py (27)
- test_file_lifecycle.py (26)
- test_interactive.py (25)
- test_performance.py (21)
- And 24 other test files

**Fix Applied**: Removed `(self)` from module-level `def test_xxx():` functions

**Result**: Eliminated 197+ errors related to missing `self` fixture

### 2. Fixed Constructor Parameter Mismatches (4 test files)

**Problem**: Tests passing incorrect parameters to class constructors, particularly `WorkflowOrchestrator`.

**Root Cause**: `WorkflowOrchestrator` doesn't accept `console=` parameter (uses DI instead)

**Files Fixed**:

- test_legacy_settings_integration.py
- test_structured_errors.py
- test_core_modules.py
- test_executors/test_lock_integration.py

**Fix Applied**: Removed `console=` parameters, updated assertions

### 3. Fixed Syntax Errors in Source Files (3 files)

**Problem**: Missing spaces in Python keywords/operators preventing compilation

**Files Fixed**:

- crackerjack/documentation/dual_output_generator.py (lines 15, 61, 65)
- crackerjack/monitoring/metrics_collector.py (lines 15, 113, 115)
- crackerjack/monitoring/websocket_server.py (line 21)

**Patterns Fixed**:

- `import[ClassName]` → `import ClassName`
- `or[ClassName]()` → `or ClassName()`
- `parameter:Type` → `parameter: Type`

### 4. Fixed CrackerjackAPI WorkflowOrchestrator Instantiation

**Problem**: `crackerjack/api.py` line 55 was passing `console=` parameter that WorkflowOrchestrator doesn't accept

**Fix Applied**:

```python
# BEFORE
self.orchestrator = WorkflowOrchestrator(
    console=self.console,
    pkg_path=self.project_path,
    verbose=self.verbose,
)

# AFTER
self.orchestrator = WorkflowOrchestrator(
    pkg_path=self.project_path,
    verbose=self.verbose,
)
```

## Remaining Issues

### 197 Test Errors (Setup/Configuration Level)

These are NOT test logic failures but structural setup errors preventing tests from running.

**Current Investigation Point**:

- `tests/test_api_comprehensive.py::TestCrackerjackAPI::test_init` fails with Bevy (DI) injection error
- Error occurs in `crackerjack/core/workflow_orchestrator.py:2519` during `PhaseCoordinator` instantiation
- This suggests systematic Bevy/DI configuration issues

**Need to Analyze**:

1. Are these errors related to Bevy DI container setup in tests?
1. Are test fixtures properly providing required dependencies?
1. Are there missing legacy configuration in test conftest files?
1. Are there async/await issues in test fixtures?

### 644 Test Failures (Test Logic Issues)

Once errors are fixed, these failures likely represent actual test assertion/logic problems that need individual fixes.

## Next Steps (Priority Order)

### Immediate (High Priority)

1. **Analyze Bevy DI Errors**: Run failing tests with `--tb=long` to understand Bevy injection failures
1. **Check Test Conftest Files**: Review `tests/conftest.py` and related files for DI setup
1. **Identify Error Patterns**: Categorize 197 errors by type:
   - Bevy container initialization failures
   - Missing fixtures or dependency providers
   - Async/await issues in fixtures
   - Constructor parameter mismatches (similar to what we fixed)

### Secondary (After Error Analysis)

1. **Fix Systematic Error Types**: Apply fixes to all tests affected by each error pattern
1. **Run Tests by Category**: Test files in groups to verify fixes work across multiple tests
1. **Validate Fixes**: Ensure each fix reduces error count measurably

### Final

1. **Address 644 Failures**: After errors are fixed, analyze and fix test logic failures
1. **Full Test Suite**: Run complete test suite to confirm all improvements
1. **Coverage**: Verify coverage metrics remain above baseline

## Key Files Modified

**Source Files**:

- `/Users/les/Projects/crackerjack/crackerjack/api.py` (line 55-58)
- `/Users/les/Projects/crackerjack/crackerjack/documentation/dual_output_generator.py` (lines 15, 61, 65)
- `/Users/les/Projects/crackerjack/crackerjack/monitoring/metrics_collector.py` (lines 15, 113, 115)
- `/Users/les/Projects/crackerjack/crackerjack/monitoring/websocket_server.py` (line 21)

**Test Files Modified**:

- 33 test files total with structural fixes (305 function signatures)
- 4 test files with constructor fixes

## Technical Insights

### legacy/Bevy DI Pattern

WorkflowOrchestrator has TWO classes in the same file:

1. `WorkflowPipeline` (line 46) - has `@depends.inject` decorator, uses full DI
1. `WorkflowOrchestrator` (line 2477) - simpler constructor, uses `depends.get_sync()` internally

The import correctly resolves to the second one at runtime, which accepts `pkg_path`, `dry_run`, `web_job_id`, `verbose`, `debug` parameters.

### Error vs Failure Distinction

- **Errors (197)**: Setup/configuration issues - tests cannot run
- **Failures (644)**: Tests run but assertions fail - logic problems

This distinction is important: fixing the 197 errors may reduce failures since some tests can now run.

## Commands for Next Session

```bash
# Get detailed error information
timeout 60 python -m pytest tests/ -x --tb=long 2>&1 | tail -100

# Run specific error-prone test file
python -m pytest tests/test_api_comprehensive.py -v --tb=short

# Get error summary
timeout 600 python -m pytest tests/ --tb=no -q 2>&1 | tail -50

# Full test suite with timeout
timeout 600 python -m pytest tests/ --tb=no -q
```

## Questions for Next Session

1. **Bevy Configuration**: Are there any test-specific Bevy container configurations needed?
1. **Fixtures**: Do tests need specific legacy fixture providers in conftest.py?
1. **Async Setup**: Are fixture setup errors related to async/await patterns?
1. **Fallback Strategy**: If Bevy DI issues are complex, can tests use fallback manual DI setup?

______________________________________________________________________

**Session End Time**: When token limit reached
**Estimated Remaining Work**: 2-4 hours to fix 197 errors + categorize and fix 644 failures
**Recommendation**: Use pytest-hypothesis-specialist agent in next session for systematic error analysis
