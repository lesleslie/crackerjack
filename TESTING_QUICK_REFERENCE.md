# Crackerjack Test Coverage - Quick Reference

**Goal**: 60%+ overall coverage (from 21.6%)
**Timeline**: 6 days
**Working Dir**: `/Users/les/Projects/crackerjack`

## 🚀 Quick Start

```bash
cd /Users/les/Projects/crackerjack

# 1. Run coverage audit
./scripts/run_coverage_audit.sh

# 2. Generate test templates
python scripts/create_test_templates.py

# 3. View coverage report
open htmlcov/index.html

# 4. Run tests
pytest -v

# 5. Check coverage
pytest --cov=crackerjack --cov-report=term-missing
```

## 📋 Daily Commands

### Day 1: Audit
```bash
./scripts/run_coverage_audit.sh
python scripts/create_test_templates.py
open htmlcov/index.html
```

### Day 2-3: Adapters
```bash
pytest tests/unit/adapters/ -v --cov=crackerjack/adapters
```

### Day 4-5: Agents
```bash
pytest tests/unit/agents/ -v --cov=crackerjack/agents
```

### Day 6: CLI
```bash
pytest tests/unit/cli/ -v --cov=crackerjack/cli
pytest tests/integration/ -v
```

## 🎯 Coverage Targets

| Module | Target | Priority |
|--------|--------|----------|
| Adapters | 70% | HIGH |
| Agents | 70% | HIGH |
| CLI | 70% | HIGH |
| Orchestration | 60% | MEDIUM |
| Services | 60% | MEDIUM |

## 📝 Test Template

```python
"""Test module description."""

import pytest
from pathlib import Path
from crackerjack.module import ClassUnderTest

@pytest.mark.unit
class TestClassUnderTest:
    """Test suite for ClassUnderTest."""

    @pytest.fixture
    def setup(self):
        return ClassUnderTest()

    @pytest.mark.asyncio
    async def test_feature(self, setup):
        # Arrange
        input_data = "valid"

        # Act
        result = await setup.method(input_data)

        # Assert
        assert result.is_valid
```

## 🏗️ Using Fixtures

```python
# DI context for managers
def test_with_di_context(workflow_orchestrator_di_context):
    injection_map, pkg_path = workflow_orchestrator_di_context
    # Can now instantiate without parameters

# Mock fixtures
def test_with_mocks(mock_console, mock_filesystem):
    # Use mocks from conftest.py

# Temp directory
def test_with_temp(tmp_path):
    test_file = tmp_path / "test.py"
    test_file.write_text("content")
```

## 🧪 Test Patterns

### Async Test
```python
@pytest.mark.asyncio
async def test_async_method():
    result = await async_function()
    assert result is not None
```

### Parametrized Test
```python
@pytest.mark.parametrize("input,expected", [
    ("valid", "success"),
    ("", "error"),
])
def test_multiple_inputs(input, expected):
    assert function(input) == expected
```

### Mock Test
```python
@patch('crackerjack.module.external')
def test_with_mock(mock_external):
    mock_external.return_value = "value"
    result = function()
    assert result == "expected"
```

## 📊 Coverage Commands

```bash
# Overall coverage
pytest --cov=crackerjack --cov-report=html

# Module coverage
pytest --cov=crackerjack/adapters --cov-report=term-missing

# Coverage percentage
pytest --cov=crackerjack --cov-report=json
python -c "import json; print(json.load(open('coverage.json'))['totals']['percent_covered'])"

# Branch coverage
pytest --cov=crackerjack --cov-branch --cov-report=html
```

## 🏃 Running Tests

```bash
# All tests
pytest

# Verbose
pytest -v

# Specific file
pytest tests/unit/adapters/test_ruff_adapter.py

# Specific test
pytest tests/unit/adapters/test_ruff_adapter.py::TestRuffAdapter::test_format

# With markers
pytest -m unit
pytest -m "not slow"

# Parallel
pytest -n auto
```

## 📚 Documentation

- **Plan**: `CRACKERJACK_TEST_COVERAGE_PLAN.md`
- **Guide**: `TEST_IMPLEMENTATION_GUIDE.md`
- **Audit**: `COVERAGE_AUDIT_REPORT.md`
- **Summary**: `TEST_COVERAGE_EXPANSION_SUMMARY.md`
- **Fixtures**: `tests/conftest.py`

## ⚡ Common Tasks

### Create new test file
```bash
python scripts/create_test_templates.py
# Or manually:
touch tests/unit/path/to/test_module.py
```

### Run failing tests only
```bash
pytest --lf
```

### Run until first failure
```bash
pytest -x
```

### Show test summary
```bash
pytest -v --tb=no
```

### Debug test
```bash
pytest --pdb
```

## ✅ Success Criteria

- [ ] Overall ≥ 60%
- [ ] Adapters ≥ 70%
- [ ] Agents ≥ 70%
- [ ] CLI ≥ 70%
- [ ] Execution < 5 min
- [ ] Flaky < 1%

## 🐛 Troubleshooting

### Import errors
```bash
PYTHONPATH=/Users/les/Projects/crackerjack pytest tests/unit/
```

### Coverage not updating
```bash
rm -f .coverage htmlcov/ coverage.json
pytest --cov=crackerjack --cov-report=html
```

### Async tests not running
```bash
# Check pytest-asyncio is installed
uv add --dev pytest-asyncio

# Add marker
@pytest.mark.asyncio
async def test_async():
    ...
```

## 📈 Progress Tracking

```bash
# Daily check
pytest --cov=crackerjack --cov-report=json
python -c "import json; print(f\"{json.load(open('coverage.json'))['totals']['percent_covered']:.1f}%\")"

# Module check
pytest tests/unit/adapters/ --cov=crackerjack/adapters --cov-report=term-missing
pytest tests/unit/agents/ --cov=crackerjack/agents --cov-report=term-missing
pytest tests/unit/cli/ --cov=crackerjack/cli --cov-report=term-missing
```

## 🎯 Daily Targets

| Day | Focus | Target |
|-----|-------|--------|
| 1 | Audit | Baseline |
| 2 | Adapters | 40% |
| 3 | Adapters | 60% |
| 4 | Agents | 40% |
| 5 | Agents | 60% |
| 6 | CLI + Final | 60%+ |

---

**Quick Start**: `./scripts/run_coverage_audit.sh`
**Full Plan**: `CRACKERJACK_TEST_COVERAGE_PLAN.md`
**Guide**: `TEST_IMPLEMENTATION_GUIDE.md`
