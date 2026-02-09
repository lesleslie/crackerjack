# Crackerjack Test Coverage Expansion

**Goal**: Increase test coverage from 21.6% to 60%+
**Timeline**: 6 days
**Status**: ✅ Ready to start

## Quick Start

```bash
cd /Users/les/Projects/crackerjack

# 1. Run coverage audit
chmod +x scripts/run_coverage_audit.sh
./scripts/run_coverage_audit.sh

# 2. Generate test templates
python scripts/create_test_templates.py

# 3. View coverage report
open htmlcov/index.html
```

## Documentation

| Document | Purpose |
|----------|---------|
| **TESTING_QUICK_REFERENCE.md** | One-page cheat sheet (START HERE) |
| **TEST_IMPLEMENTATION_GUIDE.md** | Step-by-step implementation guide |
| **CRACKERJACK_TEST_COVERAGE_PLAN.md** | Comprehensive 4-phase plan |
| **COVERAGE_AUDIT_REPORT.md** | Coverage analysis framework |
| **TEST_COVERAGE_EXPANSION_SUMMARY.md** | Executive summary |
| **TEST_COVERAGE_INIT_COMPLETE.md** | Initialization status |

## Daily Workflow

**Day 1**: Coverage audit and setup
```bash
./scripts/run_coverage_audit.sh
python scripts/create_test_templates.py
```

**Day 2-3**: Adapter tests
```bash
pytest tests/unit/adapters/ -v --cov=crackerjack/adapters
```

**Day 4-5**: Agent tests
```bash
pytest tests/unit/agents/ -v --cov=crackerjack/agents
```

**Day 6**: CLI tests + final review
```bash
pytest tests/unit/cli/ -v --cov=crackerjack/cli
pytest --cov=crackerjack --cov-report=html
```

## Coverage Targets

| Module | Target | Priority |
|--------|--------|----------|
| Adapters | 70% | HIGH |
| Agents | 70% | HIGH |
| CLI | 70% | HIGH |
| Overall | 60%+ | - |

## Success Criteria

- ✅ Overall coverage ≥ 60%
- ✅ Critical modules ≥ 70%
- ✅ Test execution < 5 minutes
- ✅ Flaky test rate < 1%

## Commands

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=crackerjack --cov-report=html

# Run specific module
pytest tests/unit/adapters/ -v

# Parallel execution
pytest -n auto

# Check coverage percentage
pytest --cov=crackerjack --cov-report=json
python -c "import json; print(json.load(open('coverage.json'))['totals']['percent_covered'])"
```

## Test Template

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

## Automation Scripts

- **`scripts/run_coverage_audit.sh`** - Automated coverage analysis
- **`scripts/create_test_templates.py`** - Test file generator

## Progress

Current: **21.6%**
Target: **60%+**
Timeline: **6 days**

---

**Start here**: `TESTING_QUICK_REFERENCE.md`
**Full plan**: `CRACKERJACK_TEST_COVERAGE_PLAN.md`
