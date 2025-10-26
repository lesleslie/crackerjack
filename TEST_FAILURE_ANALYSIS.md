# Test Failure Pattern Analysis - Crackerjack Project

## Summary
- **Total Failed Tests**: 467
- **Top 10 Test Files by Failure Count**: 206 failures (44% of total)
- **Primary Patterns**: 3 main categories
- **Highest Impact Pattern**: DI Constructor Signature Mismatch (affects ~120+ tests)

---

## Top 10 Test Files with Most Failures

### 1. tests/test_publish_manager_coverage.py
- **Failures**: 54
- **Primary Pattern**: DI Constructor Signature Mismatch
- **Example Error**:
  ```
  TypeError: PublishManagerImpl.__init__() got an unexpected keyword argument 'console'
  TypeError: PublishManagerImpl.__init__() got an unexpected keyword argument 'pkg_path'
  ```
- **Root Cause**: Tests pass positional args `(console, pkg_path)` but ACB DI requires `@depends.inject` with `Inject[T]` parameters
- **Test Code**: `PublishManagerImpl(mock_console, temp_pkg_path, dry_run=False)`
- **Expected**: `PublishManagerImpl(console=console, pkg_path=pkg_path, dry_run=False)` with proper DI setup

### 2. tests/test_session_coordinator_coverage.py
- **Failures**: 33
- **Primary Pattern**: DI Constructor Signature Mismatch + Console Type Mismatch
- **Example Error**:
  ```
  AssertionError: assert <console width=80 None> == <Mock spec='Console' id='4740319952'>
  ```
- **Root Cause**: Tests pass `Mock(spec=Console)` but actual code uses `acb.console.Console` from DI
- **Test Code**: `SessionCoordinator(console=console, pkg_path=temp_dir)`
- **Issue**: Console fixture is Mock, but DI creates real Console instance

### 3. tests/test_global_lock_config.py
- **Failures**: 25
- **Primary Pattern**: Constructor Parameter Name Mismatch
- **Example Error**:
  ```
  TypeError: GlobalLockConfig.__init__() got an unexpected keyword argument 'lock_directory'
  ```
- **Root Cause**: Tests use old parameter names; actual class has different parameter names
- **Test Code**: `GlobalLockConfig(lock_directory=temp_path)`
- **Expected**: Need to check actual GlobalLockConfig parameters

### 4. tests/test_managers_consolidated.py
- **Failures**: 23
- **Primary Pattern**: DI Constructor Signature Mismatch
- **Example Error**:
  ```
  TypeError: HookManagerImpl.__init__() got an unexpected keyword argument 'console'
  ```
- **Root Cause**: Tests use old-style positional constructor parameters
- **Test Code**: `HookManagerImpl(console=console, pkg_path=temp_project)`
- **Issue**: HookManagerImpl doesn't accept `console` parameter directly

### 5. tests/managers/test_hook_manager_orchestration.py
- **Failures**: 20
- **Primary Pattern**: DI Constructor Signature Mismatch
- **Example Error**:
  ```
  TypeError: HookManagerImpl.__init__() got an unexpected keyword argument 'console'
  ```
- **Root Cause**: HookManagerImpl constructor changed
- **Test Code**: `HookManagerImpl(console=console, pkg_path=pkg_path)`
- **Expected**: Needs DI-based initialization

### 6. tests/test_hook_lock_manager.py
- **Failures**: 19
- **Primary Pattern**: Constructor Parameter Name Mismatch
- **Example Error**:
  ```
  TypeError: GlobalLockConfig.__init__() got an unexpected keyword argument 'lock_directory'
  ```
- **Root Cause**: Parameter name mismatch with GlobalLockConfig

### 7. tests/test_session_coordinator_comprehensive.py
- **Failures**: 18
- **Primary Pattern**: DI Constructor Signature Mismatch + Object Type Mismatch
- **Example Error**: Similar to test_session_coordinator_coverage.py

### 8. tests/test_models_task_coverage.py
- **Failures**: 17
- **Primary Pattern**: String Value Mismatch (Hyphenation)
- **Example Error**:
  ```
  AssertionError: assert 'pre-commit' == 'pre - commit'
  - pre - commit
  ?    - -
  ```
- **Root Cause**: Tests expect 'pre - commit' (with spaces) but code returns 'pre-commit' (hyphenated)
- **Test Code**: `assert result.stage == "pre - commit"`

### 9. tests/test_cli/test_global_lock_options.py
- **Failures**: 15
- **Primary Pattern**: Constructor Parameter Name Mismatch + DI Issues

### 10. tests/test_unified_config.py
- **Failures**: 14
- **Primary Pattern**: Constructor Parameter Name Mismatch

---

## Pattern Analysis: Top 3 Failure Patterns by Impact

### PATTERN 1: DI Constructor Signature Mismatch (Affects ~120+ tests)
**Impact Level**: CRITICAL (44% of failures)

**Description**: Tests call constructors with `console=` and `pkg_path=` keyword arguments, but classes refactored to use ACB dependency injection with `@depends.inject` decorator.

**Affected Files**:
- PublishManagerImpl (54 tests)
- HookManagerImpl (23+20 = 43 tests)
- SessionCoordinator (33+18 = 51 tests)
- TestManagementImpl (implied from consolidated tests)
- WorkflowOrchestrator (multiple tests)

**Example**:
```python
# TEST CODE (OLD PATTERN)
manager = PublishManagerImpl(mock_console, temp_pkg_path, dry_run=False)

# ACTUAL CLASS (NEW ACB PATTERN)
class PublishManagerImpl:
    @depends.inject
    def __init__(
        self,
        git_service: Inject[GitServiceProtocol],
        version_analyzer: Inject[VersionAnalyzerProtocol],
        changelog_generator: Inject[ChangelogGeneratorProtocol],
        filesystem: Inject[FileSystemInterface],
        security: Inject[SecurityServiceProtocol],
        regex_patterns: Inject[RegexPatternsProtocol],
        console: Console = depends(),
        pkg_path: Path = depends(),
        dry_run: bool = False,
    ) -> None:
```

**Root Cause**: Phase 4 refactoring converted core managers to use ACB DI, but test fixtures and calls were not updated.

**Fix Strategy**: 
1. Update all test fixtures to work with DI-based initialization
2. For tests that need specific instances, either:
   - Use real DI container with proper setup
   - Create wrapper functions that handle DI injection
   - Mock at service level instead of constructor level

---

### PATTERN 2: Constructor Parameter Name/Type Mismatch (Affects ~40+ tests)
**Impact Level**: HIGH (9% of failures)

**Description**: Tests use parameter names or types that don't match the actual class constructor.

**Affected Files**:
- GlobalLockConfig (25+19 = 44 tests)
- Config-related classes (14 tests)

**Examples**:
```python
# TEST CODE (WRONG)
GlobalLockConfig(lock_directory=temp_path)

# ACTUAL CLASS (DIFFERENT PARAMETER NAME)
class GlobalLockConfig:
    def __init__(self, ...):
        # Uses different parameter name, not 'lock_directory'
```

**Root Cause**: 
1. Class constructor was renamed/refactored
2. Tests were written for old API and not updated
3. Parameter names changed during refactoring

**Fix Strategy**:
1. Check actual parameter names in GlobalLockConfig
2. Update test calls to match
3. May need to check if parameters were renamed in requirements

---

### PATTERN 3: String Value/Constant Mismatch (Affects ~17+ tests)
**Impact Level**: MEDIUM (4% of failures)

**Description**: Tests expect specific string values (often with specific formatting) but code returns slightly different formats.

**Affected Files**:
- test_models_task_coverage.py (HookResult, TaskStatus tests)

**Example**:
```python
# TEST EXPECTATION
assert result.stage == "pre - commit"  # With spaces

# ACTUAL VALUE
result.stage = "pre-commit"  # Hyphenated

# TEST CODE
def test_hook_result_creation_minimal(self):
    result = HookResult(stage="pre - commit", ...)
    assert result.stage == "pre - commit"
```

**Root Cause**:
1. String formatting changed during refactoring
2. Tests hardcoded expected values
3. Possible conversion happening in HookResult class

**Fix Strategy**:
1. Check HookResult.__post_init__ for string normalization
2. Update test expectations to match actual output
3. Or remove string normalization if it's causing issues

---

## Detailed Pattern Breakdown

| Pattern | Files Affected | Test Count | Error Type | Severity |
|---------|---|---|---|---|
| DI Constructor Signature Mismatch | 6 major | ~120 | TypeError: unexpected keyword argument | CRITICAL |
| Constructor Parameter Name Mismatch | 3 major | ~40 | TypeError: unexpected keyword argument | HIGH |
| String Value/Formatting Mismatch | 1 major | ~17 | AssertionError: string equality | MEDIUM |
| Object Type Mismatch (Mock vs Real) | 2 major | ~15 | AssertionError/AttributeError | MEDIUM |
| Coroutine Awaiting Issues | Multiple | ~10 | RuntimeWarning/AttributeError | LOW |

---

## High-Impact Fix Order

### Phase 1: DI Constructor Mismatch (120+ tests) - 2-3 hours
**Target Files**:
1. `tests/test_publish_manager_coverage.py` (54 failures) - PublishManagerImpl
2. `tests/test_session_coordinator_coverage.py` (33 failures) - SessionCoordinator  
3. `tests/test_session_coordinator_comprehensive.py` (18 failures) - SessionCoordinator
4. `tests/managers/test_hook_manager_orchestration.py` (20 failures) - HookManagerImpl
5. `tests/test_managers_consolidated.py` (23 failures) - Multiple managers

**Strategy**: Create DI-aware test fixtures or mocking helpers

### Phase 2: GlobalLockConfig Parameter Mismatch (40+ tests) - 1-2 hours
**Target Files**:
1. `tests/test_global_lock_config.py` (25 failures)
2. `tests/test_hook_lock_manager.py` (19 failures)

**Strategy**: Fix parameter names to match actual class

### Phase 3: String Value Mismatches (17+ tests) - 30 minutes
**Target Files**:
1. `tests/test_models_task_coverage.py` (17 failures)

**Strategy**: Update test expectations or fix string normalization

---

## Error Message Examples by Pattern

### Pattern 1: DI Constructor Mismatch
```
TypeError: PublishManagerImpl.__init__() got an unexpected keyword argument 'console'
TypeError: SessionCoordinator.__init__() got an unexpected keyword argument 'console'
TypeError: HookManagerImpl.__init__() got an unexpected keyword argument 'console'
```

### Pattern 2: Parameter Name Mismatch
```
TypeError: GlobalLockConfig.__init__() got an unexpected keyword argument 'lock_directory'
```

### Pattern 3: String Value Mismatch
```
AssertionError: assert 'pre-commit' == 'pre - commit'
  - pre - commit
  ?    - -
```

### Pattern 4: Type Mismatch
```
AssertionError: assert <console width=80 None> == <Mock spec='Console' id='4740319952'>
AttributeError: 'coroutine' object has no attribute 'model_copy'
```

---

## Recommendations

### Immediate (High Priority)
1. Fix DI constructor signature mismatches - affects 120+ tests
2. Fix GlobalLockConfig parameter names - affects 40+ tests
3. These 2 patterns account for 160+ failures (34% of all failures)

### Short Term
1. Fix string value/formatting mismatches - 17 tests
2. Fix type mismatches in mocks - 15 tests

### Investigation Needed
1. Check if GlobalLockConfig actually exists or was renamed
2. Check if HookManagerImpl/PublishManagerImpl constructors support console parameter
3. Verify string normalization logic in HookResult class

---

## Testing Recommendation

After fixing high-impact patterns:
```bash
# Run each file group to verify fixes
python -m pytest tests/test_publish_manager_coverage.py -v
python -m pytest tests/test_session_coordinator_coverage.py -v
python -m pytest tests/test_global_lock_config.py -v
python -m pytest tests/test_managers_consolidated.py -v

# Then run all tests
python -m pytest tests/ --tb=short
```

Expected improvement:
- Phase 1 fix: ~120 tests pass (26% reduction in failures)
- Phase 2 fix: ~40 additional tests pass (35% total reduction)
- Phase 3 fix: ~17 additional tests pass (38% total reduction)
- Total potential: ~177 tests fixed (38% of 467 failures)
