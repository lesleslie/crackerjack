# Crackerjack Test Implementation Guide

**Purpose**: Practical guide for implementing comprehensive test coverage for Crackerjack
**Target Coverage**: 60%+ overall
**Timeline**: 6 days
**Working Directory**: `/Users/les/Projects/crackerjack`

## Quick Start

### Day 1: Setup & Audit

```bash
cd /Users/les/Projects/crackerjack

# 1. Run coverage audit
chmod +x scripts/run_coverage_audit.sh
./scripts/run_coverage_audit.sh

# 2. Generate test templates
python scripts/create_test_templates.py

# 3. Review coverage report
open htmlcov/index.html
```

### Day 2-3: Quality Check Tests

```bash
# Focus on adapter tests
pytest tests/unit/adapters/ -v --cov=crackerjack/adapters --cov-report=term-missing

# Target specific adapters
pytest tests/unit/adapters/format/test_ruff_adapter.py -v
pytest tests/unit/adapters/security/test_bandit_adapter.py -v
pytest tests/unit/adapters/complexity/test_complexipy_adapter.py -v
```

### Day 4-5: Agent Skills Tests

```bash
# Focus on agent tests
pytest tests/unit/agents/ -v --cov=crackerjack/agents --cov-report=term-missing

# Target specific agents
pytest tests/unit/agents/test_security_agent.py -v
pytest tests/unit/agents/test_refactoring_agent.py -v
pytest tests/unit/agents/test_performance_agent.py -v
```

### Day 6: CLI Tests

```bash
# Focus on CLI tests
pytest tests/unit/cli/ -v --cov=crackerjack/cli --cov-report=term-missing

# Integration tests
pytest tests/integration/test_cli_workflow.py -v
```

## Test Implementation Workflow

### 1. Coverage-Driven Development

**Step 1: Identify Low-Coverage Module**

```bash
# Check coverage report
grep -A 5 "crackerjack/module_name" htmlcov/index.html
```

**Step 2: Create Test File**

```bash
# Use template generator or create manually
touch tests/unit/path/to/test_module.py
```

**Step 3: Write Tests**

- Follow test structure below
- Use existing fixtures from `conftest.py`
- Mark tests appropriately (`@pytest.mark.unit`, etc.)

**Step 4: Verify Coverage**

```bash
# Run tests for module
pytest tests/unit/path/to/test_module.py -v --cov=crackerjack/module_name --cov-report=term-missing
```

**Step 5: Iterate**

- Add tests for uncovered lines
- Refactor complex functions
- Improve assertion clarity

### 2. Test Structure Template

```python
"""Test module description."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from crackerjack.module import ClassUnderTest


@pytest.mark.unit
class TestClassUnderTest:
    """Test suite for ClassUnderTest."""

    @pytest.fixture
    def setup(self):
        """Create test fixture with default configuration."""
        return ClassUnderTest(param1="value1", param2="value2")

    @pytest.mark.asyncio
    async def test_feature_positive_case(self, setup):
        """Test feature with valid input."""
        # Arrange
        input_data = "valid_input"

        # Act
        result = await setup.method(input_data)

        # Assert
        assert result.is_valid
        assert result.value == "expected"

    def test_feature_negative_case(self, setup):
        """Test feature with invalid input."""
        # Arrange
        input_data = None

        # Act & Assert
        with pytest.raises(ValueError, match="expected message"):
            setup.method(input_data)

    def test_feature_edge_case(self, setup):
        """Test feature with edge case input."""
        # Arrange
        input_data = ""

        # Act
        result = setup.method(input_data)

        # Assert
        assert result == "default_value"
```

### 3. Async Test Pattern

```python
"""Async test pattern for adapters and agents."""


@pytest.mark.asyncio
async def test_async_method_with_timeout():
    """Test async method with timeout."""
    # Arrange
    adapter = AdapterUnderTest()
    test_file = Path("/tmp/test.py")
    test_file.write_text("def hello(): pass")

    # Act
    result = await adapter.check([test_file], config)

    # Assert
    assert result.passed is True
```

### 4. Mock Pattern

```python
"""Mock pattern for external dependencies."""

from unittest.mock import Mock, patch


@pytest.mark.unit
class TestWithMocks:
    """Test suite using mocks."""

    @patch("crackerjack.module.external_dependency")
    def test_with_mock(self, mock_dep):
        """Test with mocked external dependency."""
        # Arrange
        mock_dep.return_value = "mocked_value"

        # Act
        result = function_under_test()

        # Assert
        assert result == "expected"
        mock_dep.assert_called_once()

    def test_with_mock_fixture(self, mock_filesystem):
        """Test with mock fixture from conftest.py."""
        # Arrange
        mock_filesystem.exists.return_value = True

        # Act
        result = function_under_test()

        # Assert
        assert result is not None
        mock_filesystem.exists.assert_called()
```

### 5. Parameterized Test Pattern

```python
"""Parameterized test pattern for multiple inputs."""


@pytest.mark.parametrize(
    "input_data,expected_output",
    [
        ("valid", "success"),
        ("", "default"),
        (None, "error"),
    ],
)
def test_with_multiple_inputs(input_data, expected_output):
    """Test with multiple input-output pairs."""
    result = function_under_test(input_data)
    assert result == expected_output
```

### 6. Fixture Usage

```python
"""Using fixtures from conftest.py."""


def test_with_di_context(workflow_orchestrator_di_context):
    """Test with DI context from conftest.py."""
    # Arrange
    injection_map, pkg_path = workflow_orchestrator_di_context

    # Act - Can now instantiate without parameters
    from crackerjack.orchestration.workflow_orchestrator import WorkflowOrchestrator

    orchestrator = WorkflowOrchestrator(pkg_path=pkg_path)

    # Assert
    assert orchestrator is not None
```

## Module-Specific Guidelines

### Adapter Tests

**Location**: `tests/unit/adapters/{category}/test_{adapter_name}.py`

**Key Test Areas**:

1. Valid files processing
1. Empty file list handling
1. Invalid/error file handling
1. Configuration loading
1. Async execution
1. Cache integration

**Example**:

```python
@pytest.mark.asyncio
async def test_adapter_with_valid_files(adapter, config, tmp_path):
    """Test adapter processes valid files correctly."""
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello(): pass")
    result = await adapter.check([test_file], config)
    assert result.passed is True
```

### Agent Tests

**Location**: `tests/unit/agents/test_{agent_name}.py`

**Key Test Areas**:

1. Issue type matching
1. File modification
1. Agent coordination
1. Confidence scoring
1. Batch processing

**Example**:

```python
@pytest.mark.asyncio
async def test_agent_fixes_security_issue(agent, agent_context, tmp_path):
    """Test agent fixes security vulnerability."""
    test_file = tmp_path / "test.py"
    test_file.write_text('subprocess.run("ls", shell=True)')
    agent_context.files = [test_file]

    result = await agent.fix_issue(
        context=agent_context, issue_type="B602", message="shell injection detected"
    )

    assert result.success is True
    assert "shell=True" not in test_file.read_text()
```

### CLI Tests

**Location**: `tests/unit/cli/test_cli_{command}.py`

**Key Test Areas**:

1. Command invocation
1. Flag combinations
1. Error handling
1. Output formatting
1. Exit codes

**Example**:

```python
def test_run_command_with_flags(tmp_path):
    """Test CLI command with multiple flags."""
    (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")
    result = runner.invoke(app, ["run", "--fast", "--verbose"])
    assert result.exit_code == 0
    assert "crackerjack" in result.stdout.lower()
```

## Common Test Scenarios

### Scenario 1: Testing File Operations

```python
def test_file_operations(tmp_path):
    """Test operations on temporary files."""
    # Create test file
    test_file = tmp_path / "test.py"
    test_file.write_text("original content")

    # Perform operation
    result = process_file(test_file)

    # Verify changes
    assert test_file.exists()
    assert "modified" in test_file.read_text()
```

### Scenario 2: Testing Error Handling

```python
def test_error_handling():
    """Test proper error handling."""
    with pytest.raises(SpecificError) as exc_info:
        function_that_raises()

    assert "expected message" in str(exc_info.value)
    assert exc_info.value.code == "ERROR_CODE"
```

### Scenario 3: Testing Async Operations

```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operation completes successfully."""
    result = await async_function()
    assert result is not None
    assert await result.is_ready()
```

### Scenario 4: Testing with Mocks

```python
@patch("crackerjack.module.external_service")
def test_with_external_service(mock_service):
    """Test with mocked external service."""
    mock_service.fetch.return_value = {"data": "value"}
    result = function_using_service()
    assert result == "expected"
    mock_service.fetch.assert_called_once()
```

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/adapters/test_ruff_adapter.py

# Run specific test class
pytest tests/unit/adapters/test_ruff_adapter.py::TestRuffAdapter

# Run specific test
pytest tests/unit/adapters/test_ruff_adapter.py::TestRuffAdapter::test_format

# Run with markers
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
pytest -m "not slow"    # Skip slow tests
```

### Coverage Commands

```bash
# Run with coverage
pytest --cov=crackerjack --cov-report=html

# Coverage for specific module
pytest --cov=crackerjack/adapters --cov-report=term-missing

# Coverage with branch coverage
pytest --cov=crackerjack --cov-branch --cov-report=html

# Generate coverage report
pytest --cov=crackerjack --cov-report=json
python -c "import json; print(json.load(open('coverage.json'))['totals']['percent_covered'])"
```

### Parallel Execution

```bash
# Run tests in parallel
pytest -n auto

# Run with specific number of workers
pytest -n 4

# Run tests in parallel with coverage
pytest -n auto --cov=crackerjack --cov-context=test
```

## Troubleshooting

### Issue: Tests Failing Due to Missing Fixtures

**Solution**:

```python
# Add fixture to conftest.py
@pytest.fixture
def my_fixture():
    return MyObject()


# Or use local fixture
@pytest.fixture
def local_fixture():
    return MyObject()
```

### Issue: Async Tests Not Running

**Solution**:

```python
# Ensure pytest-asyncio is installed
uv add --dev pytest-asyncio

# Add marker
@pytest.mark.asyncio
async def test_async_function():
    await async_operation()
```

### Issue: Coverage Not Updating

**Solution**:

```bash
# Clear coverage data
rm -f .coverage
rm -rf htmlcov/
rm coverage.json

# Re-run tests
pytest --cov=crackerjack --cov-report=html
```

### Issue: Import Errors in Tests

**Solution**:

```python
# Add project root to Python path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Or use PYTHONPATH
PYTHONPATH=/Users/les/Projects/crackerjack pytest tests/unit/
```

## Best Practices

### DO:

1. **Use descriptive test names** - `test_format_python_file_removes_trailing_spaces`
1. **Follow AAA pattern** - Arrange, Act, Assert
1. **Use fixtures** - Reuse setup code from `conftest.py`
1. **Mock external dependencies** - Don't depend on external services
1. **Test edge cases** - None, empty strings, negative numbers
1. **Use appropriate markers** - `@pytest.mark.unit`, `@pytest.mark.slow`
1. **Keep tests independent** - Each test should run in isolation
1. **Use parameterization** - Test multiple inputs with one test function

### DON'T:

1. **Don't test implementation details** - Test behavior, not internals
1. **Don't write monolithic tests** - One test should verify one thing
1. **Don't ignore flaky tests** - Fix them or remove them
1. **Don't hardcode paths** - Use `tmp_path` fixture
1. **Don't sleep in tests** - Use proper async/await
1. **Don't use global state** - Tests should be isolated
1. **Don't test third-party code** - Assume libraries work
1. **Don't skip tests without documentation** - Explain why

## Coverage Targets by Module

| Module | Target | Priority |
|--------|--------|----------|
| `crackerjack/adapters/` | 70% | HIGH |
| `crackerjack/agents/` | 70% | HIGH |
| `crackerjack/cli.py` | 70% | HIGH |
| `crackerjack/api.py` | 60% | MEDIUM |
| `crackerjack/orchestration/` | 60% | MEDIUM |
| `crackerjack/services/` | 60% | MEDIUM |
| `crackerjack/models/` | 50% | LOW |
| `crackerjack/config.py` | 50% | LOW |

## Progress Tracking

### Daily Check-in Commands

```bash
# Check overall coverage
pytest --cov=crackerjack --cov-report=json
python -c "import json; print(f\"Coverage: {json.load(open('coverage.json'))['totals']['percent_covered']:.1f}%\")"

# Check adapter coverage
pytest tests/unit/adapters/ --cov=crackerjack/adapters --cov-report=term-missing

# Check agent coverage
pytest tests/unit/agents/ --cov=crackerjack/agents --cov-report=term-missing

# Check CLI coverage
pytest tests/unit/cli/ --cov=crackerjack/cli --cov-report=term-missing

# Count tests
pytest --collect-only | grep "test session starts" -A 1
```

### Daily Targets

- **Day 1**: Coverage audit + test infrastructure
- **Day 2**: Adapters coverage ≥ 40%
- **Day 3**: Adapters coverage ≥ 60%
- **Day 4**: Agents coverage ≥ 40%
- **Day 5**: Agents coverage ≥ 60%
- **Day 6**: CLI coverage ≥ 60%, overall ≥ 60%

## Resources

### Documentation

- `CRACKERJACK_TEST_COVERAGE_PLAN.md` - Comprehensive test plan
- `COVERAGE_AUDIT_REPORT.md` - Coverage analysis
- `tests/conftest.py` - Available fixtures
- `pyproject.toml` - pytest configuration

### Scripts

- `scripts/run_coverage_audit.sh` - Coverage audit script
- `scripts/create_test_templates.py` - Test template generator

### Quick Reference

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=crackerjack --cov-report=html

# Run specific module
pytest tests/unit/adapters/ -v

# Run with markers
pytest -m unit

# Parallel execution
pytest -n auto

# View coverage report
open htmlcov/index.html
```

______________________________________________________________________

**Status**: Ready for implementation
**Next Action**: Run `./scripts/run_coverage_audit.sh` to establish baseline
**Questions**: Refer to `CRACKERJACK_TEST_COVERAGE_PLAN.md` for detailed test specifications
