# Crackerjack Test Suite Documentation

This document describes the test suite for the Crackerjack project, including the structure, conventions, and best practices.

## Test Structure

The test suite is organized into the following categories:

### Unit Tests (`tests/unit/`)

- Test individual units of code in isolation
- Located in `tests/unit/<module_name>/`
- Named `test_<component>.py`
- Focus on testing one class or function at a time

### Integration Tests (`tests/integration/`)

- Test how multiple components work together
- Located in `tests/integration/`
- Named `test_<integration_scenario>.py`
- Validate that different modules interact correctly

### Performance Tests (`tests/performance/`)

- Benchmark performance characteristics
- Located in `tests/performance/`
- Named `test_<component>_performance.py`
- Use pytest-benchmark for consistent measurements

### End-to-End Tests (`tests/e2e/`)

- Test complete workflows from start to finish
- Located in `tests/e2e/`
- Named `test_<workflow>.py`
- Validate complete user journeys

## Test Conventions

### Naming Conventions

- Test files: `test_<component>.py`
- Test classes: `Test<ComponentName>` (e.g., `TestClassifierAgent`)
- Test methods: `test_<behavior_under_test>` (e.g., `test_classifier_returns_correct_category`)

### Test Organization

- Each test method should test one specific behavior
- Use descriptive names that explain the expected behavior
- Follow the Arrange-Act-Assert pattern:
  - Arrange: Set up test data and mocks
  - Act: Execute the code under test
  - Assert: Verify the expected outcome

### Assertions

- Use specific assertions when possible (e.g., `assertEqual`, `assertTrue`)
- Provide meaningful error messages for complex assertions
- Test both positive and negative cases

## Testing Patterns

### Mocking Dependencies

Use `unittest.mock` or `pytest-mock` to isolate the code under test:

```python
def test_example_with_mock(mocker):
    mock_dependency = mocker.patch('module.dependency.method')
    mock_dependency.return_value = 'expected_value'

    # Test code that uses the dependency

    mock_dependency.assert_called_once()
```

### Parametrized Tests

Use `@pytest.mark.parametrize` for testing multiple inputs:

```python
@pytest.mark.parametrize("input_value,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double_value(input_value, expected):
    result = double_value(input_value)
    assert result == expected
```

### Async Testing

For async code, use `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected_value
```

## Property-Based Testing

The test suite uses Hypothesis for property-based testing to validate invariants:

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_never_fails(text):
    # This test should never fail regardless of input
    assert text is not None
```

## Performance Benchmarks

Performance tests use pytest-benchmark:

```python
def test_performance(benchmark):
    result = benchmark(function_to_test, arg1, arg2)
    assert result == expected_value
```

## Fixtures

Common test fixtures are defined in `tests/conftest.py`:

- `temp_project_path`: Temporary directory with a basic project structure
- `mock_options`: Mock options object
- `mock_console`: Mock console interface
- `session_coordinator`: Pre-configured SessionCoordinator instance
- `phase_coordinator`: Pre-configured PhaseCoordinator instance
- `workflow_pipeline`: Pre-configured WorkflowPipeline instance

## Test Categories

Tests are categorized using pytest markers:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.performance`: Performance tests
- `@pytest.mark.e2e`: End-to-end tests
- `@pytest.mark.slow`: Slow-running tests (deselect with `-m "not slow"`)

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_example.py

# Run tests with specific marker
pytest -m "unit"

# Run tests excluding slow ones
pytest -m "not slow"
```

### Coverage

```bash
# Run tests with coverage
pytest --cov=crackerjack --cov-report=html

# Generate coverage report
coverage report
```

### Performance Testing

```bash
# Run performance benchmarks
pytest tests/performance/ --benchmark-only

# Run with performance reports
pytest --benchmark-skip
```

## Best Practices

1. **Keep tests fast**: Aim for tests that run in under 100ms
1. **Make tests deterministic**: Tests should produce the same results every time
1. **Test behavior, not implementation**: Focus on what the code does, not how it does it
1. **Use descriptive names**: Test names should clearly indicate what is being tested
1. **Test edge cases**: Include tests for boundary conditions and error cases
1. **Maintain test independence**: Tests should not depend on each other's execution order
1. **Use appropriate test doubles**: Choose between mocks, stubs, and fakes appropriately

## Continuous Integration

The CI pipeline runs:

- All unit and integration tests
- Performance benchmarks
- Code coverage checks
- Linting and type checking

Tests must pass before merging pull requests.
