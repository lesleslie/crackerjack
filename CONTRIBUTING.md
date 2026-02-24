# Contributing to Crackerjack

Thank you for your interest in contributing to Crackerjack! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Workflow](#workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Review Process](#review-process)

## Code of Conduct

Be respectful, inclusive, and collaborative. We aim to maintain a welcoming environment for all contributors.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- Familiarity with quality tools (pytest, ruff, etc.)

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/your-username/crackerjack.git
cd crackerjack

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run initial tests
pytest
```

## Development Setup

### Project Structure

```
crackerjack/
├── crackerjack/          # Main package
│   ├── cli/             # CLI commands
│   ├── checks/          # Quality check implementations
│   ├── gates/           # Quality gate management
│   ├── config/          # Configuration management
│   ├── managers/        # Test and check managers
│   ├── ai/              # AI auto-fix engine
│   ├── reporting/       # Result reporting
│   └── mcp/             # MCP server
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── e2e/            # End-to-end tests
├── docs/               # Documentation
│   ├── guides/         # User guides
│   ├── reference/      # Reference documentation
│   └── adr/            # Architecture Decision Records
└── scripts/            # Utility scripts
```

### Development Tools

```bash
# Format code
ruff format crackerjack/

# Lint code
ruff check crackerjack/

# Type check
mypy crackerjack/

# Run security checks
bandit -r crackerjack/

# Check for unused dependencies
creosote .
```

## Workflow

### 1. Create an Issue

Before starting work, create an issue or claim an existing one to discuss your plans.

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 3. Make Changes

- Write code following [Coding Standards](#coding-standards)
- Add tests for new functionality
- Update documentation as needed

### 4. Test Your Changes

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_config.py

# Run with coverage
pytest --cov=crackerjack --cov-report=html

# Run integration tests
pytest tests/integration/
```

### 5. Commit Changes

```bash
# Stage changes
git add .

# Commit with clear message
git commit -m "feat: add support for custom quality gates

- Implement custom quality gate configuration
- Add validation for gate definitions
- Update documentation

Fixes #123"
```

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
```

## Coding Standards

### Python Style

- Follow **PEP 8** style guide
- Use **ruff** for formatting and linting
- Maximum line length: 100 characters
- Use type hints for all public functions
- Write docstrings for all modules, classes, and public functions

### Example

```python
"""Quality check implementation."""

from typing import List, Optional
from crackerjack.checks.base import Check, CheckResult, CheckStatus


class CustomCheck(Check):
    """Custom quality check for specific requirements.

    Args:
        config: Check configuration dictionary
        timeout: Maximum execution time in seconds

    Attributes:
        name: Check name
        description: Check description
    """

    name = "custom-check"
    description = "Custom quality check"

    def __init__(self, config: dict, timeout: int = 300) -> None:
        """Initialize the custom check.

        Args:
            config: Configuration dictionary
            timeout: Maximum execution time
        """
        super().__init__(config, timeout)
        self.timeout = timeout

    def run(self, context: CheckContext) -> CheckResult:
        """Execute the quality check.

        Args:
            context: Check execution context

        Returns:
            CheckResult with status and details
        """
        issues: List[str] = []

        # Implementation here

        return CheckResult(
            status=CheckStatus.PASS if not issues else CheckStatus.FAIL,
            message=f"Found {len(issues)} issues",
            details=issues,
        )
```

### Error Handling

- Use custom exceptions from `crackerjack.exceptions`
- Provide clear error messages
- Log errors appropriately
- Handle edge cases gracefully

```python
from crackerjack.exceptions import CheckError, ConfigurationError

try:
    result = self._execute_check()
except subprocess.TimeoutExpired:
    raise CheckError(f"Check {self.name} timed out after {self.timeout}s")
except KeyError as e:
    raise ConfigurationError(f"Missing required configuration: {e}")
```

### Logging

Use Python's logging module:

```python
import logging

logger = logging.getLogger(__name__)


def execute_check(self) -> CheckResult:
    """Execute check with logging."""
    logger.info(f"Executing check: {self.name}")
    try:
        result = self._run()
        logger.debug(f"Check result: {result.status}")
        return result
    except Exception as e:
        logger.error(f"Check failed: {e}", exc_info=True)
        raise
```

## Testing

### Test Structure

```python
"""Tests for custom check module."""

import pytest
from crackerjack.checks.custom import CustomCheck
from crackerjack.checks.base import CheckContext, CheckStatus


class TestCustomCheck:
    """Test suite for CustomCheck."""

    def test_init(self) -> None:
        """Test check initialization."""
        check = CustomCheck(config={}, timeout=300)
        assert check.name == "custom-check"
        assert check.timeout == 300

    def test_run_success(self, check_context: CheckContext) -> None:
        """Test successful check execution."""
        check = CustomCheck(config={})
        result = check.run(check_context)
        assert result.status == CheckStatus.PASS

    def test_run_failure(self, check_context: CheckContext) -> None:
        """Test failed check execution."""
        check = CustomCheck(config={}, timeout=1)
        result = check.run(check_context)
        assert result.status == CheckStatus.FAIL
        assert len(result.details) > 0

    @pytest.mark.parametrize(
        "config,expected_status",
        [
            ({"strict": True}, CheckStatus.FAIL),
            ({"strict": False}, CheckStatus.PASS),
        ],
    )
    def test_config_variations(
        self,
        config: dict,
        expected_status: CheckStatus,
        check_context: CheckContext,
    ) -> None:
        """Test different configuration options."""
        check = CustomCheck(config=config)
        result = check.run(check_context)
        assert result.status == expected_status
```

### Test Markers

Use pytest markers for categorization:

```python
@pytest.mark.unit
def test_unit_function():
    """Unit test - fast and isolated."""
    pass


@pytest.mark.integration
@pytest.mark.slow
def test_integration():
    """Integration test - slower, uses external tools."""
    pass


@pytest.mark.e2e
@pytest.mark.slow
def test_end_to_end():
    """End-to-end test - full workflow."""
    pass
```

### Running Tests

```bash
# Run all tests
pytest

# Run by marker
pytest -m unit
pytest -m "not slow"

# Run with coverage
pytest --cov=crackerjack --cov-report=html --cov-report=term

# Run specific test file
pytest tests/unit/test_checks.py

# Run with verbose output
pytest -v

# Stop on first failure
pytest -x

# Run failed tests only
pytest --lf
```

### Coverage Requirements

- **Minimum coverage**: 80%
- **Target coverage**: 90%+
- **New code**: 100% coverage expected

## Documentation

### Docstring Style

Use Google-style docstrings:

```python
def execute_check(config: dict, timeout: int = 300) -> CheckResult:
    """Execute a quality check with given configuration.

    This method runs the check and returns results including
    status, message, and detailed findings.

    Args:
        config: Configuration dictionary with check parameters
        timeout: Maximum execution time in seconds

    Returns:
        CheckResult object containing execution results

    Raises:
        CheckError: If check execution fails
        TimeoutError: If check exceeds timeout

    Example:
        >>> check = CustomCheck(config={"strict": True})
        >>> result = check.execute_check()
        >>> print(result.status)
        CheckStatus.PASS
    """
```

### Documentation Updates

- Update **QUICKSTART.md** for user-facing features
- Add ADRs for significant design decisions in `docs/adr/`
- Update **CHANGELOG.md** for version changes

### ADR Template

```markdown
# ADR-XXX: Title

## Status
Proposed | Accepted | Deprecated | Superseded

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?
```

## Submitting Changes

### Pull Request Checklist

Before submitting, ensure:

- [ ] Code follows [Coding Standards](#coding-standards)
- [ ] Tests pass locally: `pytest`
- [ ] Coverage meets minimum: `pytest --cov=crackerjack`
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commit messages follow conventional commits format
- [ ] PR description clearly explains changes

### Commit Message Format

Use conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: feat, fix, docs, style, refactor, test, chore

**Examples**:

```
feat(checks): add support for mypy type checking

- Implement mypy check wrapper
- Add configuration options
- Update documentation

Closes #123
```

```
fix(cli): resolve timeout argument parsing issue

The timeout argument was not being properly parsed from
command-line arguments, causing all checks to use default
timeout values.

Fixes #456
```

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Coverage maintained
- [ ] Documentation updated
- [ ] CHANGELOG.md updated

## Related Issues
Fixes #123, Related to #456
```

## Review Process

### Review Criteria

- **Code Quality**: Follows coding standards, well-structured
- **Test Coverage**: Adequate tests, good coverage
- **Documentation**: Clear, complete documentation
- **Functionality**: Works as intended, no regressions

### Review Timeline

- **Initial review**: Within 2-3 days
- **Follow-up**: Within 1 day of response
- **Merge**: After approval and CI passes

### After Review

- Address feedback comments
- Update code as needed
- Request re-review when ready
- CI must pass before merge

## Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and ideas
- **Discord/Slack**: Real-time discussion (if available)

### Resources

- **[QUICKSTART.md](QUICKSTART.md)** - Get started
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Architecture overview
- **[docs/guides/](docs/guides/)** - Detailed guides
- **[docs/reference/](docs/reference/)** - Reference documentation

## Recognition

Contributors are recognized in:

- **CONTRIBUTORS.md** - List of all contributors
- **Release notes** - Credits for each release
- **Documentation** - Specific contributions acknowledged

Thank you for contributing to Crackerjack! 🎉
