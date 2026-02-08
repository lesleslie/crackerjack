# Manager Layer Test Implementation Plan

## Overview
Add comprehensive test coverage for crackerjack's manager layer modules to achieve 75%+ coverage across all managers.

## Target Modules

### 1. HookManager (`crackerjack/managers/hook_manager.py`)
**Status**: Partial tests exist in `tests/unit/managers/test_hook_manager.py`

**Coverage Gaps**:
- Hook discovery and registration edge cases
- Progress callback functionality
- Error handling and retry logic
- Parallel hook execution
- Orchestration stats retrieval

**Tests to Add**:
- Test hook discovery with missing hooks
- Test progress callbacks during execution
- Test error handling in orchestration mode
- Test parallel vs sequential execution
- Test get_execution_info edge cases
- Test get_hook_summary with various result states

### 2. TestManager (`crackerjack/managers/test_manager.py`)
**Status**: Partial tests exist in `tests/unit/managers/test_test_manager.py`

**Coverage Gaps**:
- Coverage extraction from file
- Test statistics parsing edge cases
- Coverage ratchet handling
- LSP diagnostics integration
- Xcode test execution
- Failure line extraction

**Tests to Add**:
- Test coverage extraction from coverage.json
- Test coverage extraction fallback mechanisms
- Test statistics parsing with various formats
- Test coverage ratchet success/failure paths
- Test LSP diagnostics pre-check
- Test Xcode test execution on macOS
- Test failure extraction from short summary
- Test failure extraction from test paths
- Test structured failure parsing

### 3. TestExecutor (`crackerjack/managers/test_executor.py`)
**Status**: No dedicated test file

**Tests to Create** (`tests/unit/managers/test_test_executor.py`):
- Test project directory detection
- Test pytest index finding
- Test project path from test args
- Test progress initialization
- Test environment setup for coverage
- Test xdist fallback logic
- Test xdist timeout detection
- Test xdist removal from command
- Test thread cleanup
- Test stdout/stderr reading
- Test process completion waiting
- Test AI progress emission
- Test test output parsing (collection, execution, session events)

### 4. PublishManager (`crackerjack/managers/publish_manager.py`)
**Status**: Partial tests exist in `tests/unit/managers/test_publish_manager.py`

**Coverage Gaps**:
- Version bumping with AI recommendations
- Changelog updates
- Authentication validation
- Build execution
- Publish workflow
- Git tag creation
- Package info extraction

**Tests to Add**:
- Test version calculation (major, minor, patch)
- Test version recommendation integration
- Test interactive version prompting
- Test changelog generation calls
- Test auth validation with env var
- Test auth validation with keyring
- Test build dry-run vs actual
- Test publish success indicators
- Test git tag creation and push
- Test package info parsing
- Test fallback TOML parsing

### 5. TestProgress (`crackerjack/managers/test_progress.py`)
**Status**: No dedicated test file

**Tests to Create** (`tests/unit/managers/test_test_progress.py`):
- Test initialization and defaults
- Test completed property calculation
- Test elapsed_time property
- Test eta_seconds calculation
- Test tests_per_second property
- Test overall_status_color property
- Test update method with various fields
- Test stdout/stderr append and retrieval
- Test progress bar creation
- Test ETA formatting
- Test test rate formatting
- Test collection progress formatting
- Test execution progress formatting
- Test progress counters formatting

## Implementation Strategy

### Phase 1: TestExecutor Tests (Highest Priority)
- **Why**: Core process execution, complex logic
- **Effort**: 300-400 lines of tests
- **Coverage Target**: 70%+

### Phase 2: TestProgress Tests (High Priority, Simple)
- **Why**: Simple, focused, high value
- **Effort**: 150-200 lines of tests
- **Coverage Target**: 80%+

### Phase 3: TestManager Tests (Expand Existing)
- **Why**: Expand existing tests for missing coverage
- **Effort**: 200-300 lines of additional tests
- **Coverage Target**: 80%+

### Phase 4: HookManager Tests (Expand Existing)
- **Why**: Expand existing tests for orchestration coverage
- **Effort**: 150-200 lines of additional tests
- **Coverage Target**: 75%+

### Phase 5: PublishManager Tests (Expand Existing)
- **Why**: Expand existing tests for workflow coverage
- **Effort**: 200-250 lines of additional tests
- **Coverage Target**: 70%+

## Testing Patterns

### Mock Usage
- Use `unittest.mock.Mock` for simple mocks
- Use `unittest.mock.AsyncMock` for async methods
- Use `unittest.mock.patch` for dependency injection
- Use `pytest.fixture` for reusable test setup

### Test Structure
```python
@pytest.mark.unit
class TestFeature:
    """Test feature description."""

    @pytest.fixture
    def setup(self):
        """Create test fixtures."""
        # Setup code
        yield
        # Teardown code

    def test_specific_behavior(self, setup) -> None:
        """Test description."""
        # Arrange
        # Act
        # Assert
```

### Coverage Goals
- **TestExecutor**: 70%+ (complex process management)
- **TestProgress**: 80%+ (simpler, focused)
- **TestManager**: 80%+ (core functionality)
- **HookManager**: 75%+ (orchestration complexity)
- **PublishManager**: 70%+ (workflow complexity)

## Verification

```bash
# Run all manager tests
python -m pytest tests/unit/managers/ -v

# Check coverage for managers
python -m pytest tests/unit/managers/ --cov=crackerjack.managers --cov-report=term-missing

# Run specific test file
python -m pytest tests/unit/managers/test_test_executor.py -v

# Coverage report HTML
python -m pytest tests/unit/managers/ --cov=crackerjack.managers --cov-report=html
```

## Dependencies

All tests should use existing fixtures from `tests/conftest.py`:
- `mock_console`
- `temp_pkg_path`
- Various protocol mocks

## Notes

- Follow existing test patterns in the codebase
- Use type hints for all test functions
- Add docstrings for all test classes and methods
- Mark tests with `@pytest.mark.unit`
- Keep tests focused and independent
- Avoid async tests where possible (use sync alternatives)
