"""
Crackerjack Sensible Defaults

This module defines production-ready default values for Crackerjack settings.
These defaults are designed to work well for 80% of Python projects while
being easily overrideable via configuration files or CLI arguments.

Design Principles:
1. **Conservative**: Err on the side of safety and quality
2. **Performant**: Balance thoroughness with speed
3. **Standard**: Follow industry best practices
4. **Overrideable**: All defaults can be overridden
5. **Documented**: Rationale provided for each default

Author: Crackerjack UX Team
Version: 1.0.0
"""

from pathlib import Path
from typing import Final

# =============================================================================
# Quality Threshold Defaults
# =============================================================================

#: Minimum test coverage percentage (industry standard: 80%)
#: Rationale: 80% is widely accepted as the balance between quality and practicality
#: Source: Python Testing Best Practices, Google SRE Book
DEFAULT_COVERAGE_THRESHOLD: Final[int] = 80

#: Maximum cyclomatic complexity per function
#: Rationale: Complexity > 15 indicates hard-to-maintain code (McCabe 1976)
#: Source: "A Complexity Measure", IEEE Transactions on Software Engineering
DEFAULT_COMPLEXITY_THRESHOLD: Final[int] = 15

#: Maximum function line count
#: Rationale: Functions > 50 lines are harder to test and understand
#: Source: Clean Code by Robert C. Martin
DEFAULT_MAX_FUNCTION_LENGTH: Final[int] = 50


# =============================================================================
# Execution Defaults
# =============================================================================

#: Default test timeout in seconds (5 minutes)
#: Rationale: Most unit tests should complete in seconds, 5min accommodates integration tests
#: Reference: pytest-timeout documentation
DEFAULT_TEST_TIMEOUT: Final[int] = 300

#: Default command timeout in seconds (10 minutes)
#: Rationale: Allows for slow operations but prevents indefinite hangs
DEFAULT_COMMAND_TIMEOUT: Final[int] = 600

#: Enable parallel test execution by default
#: Rationale: Modern CI/CD has multiple cores, parallelization speeds up feedback
DEFAULT_PARALLEL_EXECUTION: Final[bool] = True

#: Auto-detect number of workers for parallel execution
#: Rationale: Optimal worker count depends on CPU cores and memory
DEFAULT_AUTO_DETECT_WORKERS: Final[bool] = True

#: Maximum parallel workers (safety limit)
#: Rationale: Prevents resource exhaustion on machines with many cores
DEFAULT_MAX_WORKERS: Final[int] = 8

#: Minimum parallel workers
#: Rationale: Ensures some parallelism even on small machines
DEFAULT_MIN_WORKERS: Final[int] = 2


# =============================================================================
# Tool-Specific Defaults
# =============================================================================

#: Ruff checks to run by default
#: Rationale: Balance between thoroughness and false positives
#: Categories: Error-prone code, style, complexity, imports
DEFAULT_RUFF_SELECT: Final[list[str]] = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # Pyflakes
    "I",  # isort
    "N",  # pep8-naming
    "UP",  # pyupgrade
    "B",  # flake8-bugbear
    "C4",  # flake8-comprehensions
    "SIM",  # flake8-simplify
    "RUF",  # Ruff-specific rules
]

#: Ruff checks to ignore by default
#: Rationale: These rules tend to have high false positive rates
DEFAULT_RUFF_IGNORE: Final[list[str]] = [
    "E502",  # Line too long (handled by formatter)
]

#: Enable coverage tracking by default
#: Rationale: Coverage is essential for quality assurance
DEFAULT_ENABLE_COVERAGE: Final[bool] = True

#: Coverage report formats
#: Rationale: HTML for detailed review, terminal for quick summary
DEFAULT_COVERAGE_REPORTS: Final[list[str]] = [
    "term",
    "html",
]

#: Run security checks by default
#: Rationale: Security is critical for production code
DEFAULT_ENABLE_SECURITY: Final[bool] = True

#: Security check tools to run
#: Rationale: Bandit for static analysis, Safety for dependencies
DEFAULT_SECURITY_TOOLS: Final[list[str]] = [
    "bandit",
    "safety",
]


# =============================================================================
# File and Directory Defaults
# =============================================================================

#: Default project root directory
#: Rationale: Use current working directory if not specified
DEFAULT_PROJECT_ROOT: Final[Path] = Path.cwd()

#: Default package name for coverage
#: Rationale: Will be auto-detected from pyproject.toml
DEFAULT_PACKAGE_NAME: Final[str] = None  # Auto-detect

#: Directories to exclude from analysis
#: Rationale: Standard Python project structure
DEFAULT_EXCLUDE_DIRS: Final[list[str]] = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
    "build",
    "dist",
    "*.egg-info",
]


# =============================================================================
# Output and Reporting Defaults
# =============================================================================

#: Default output format for reports
#: Rationale: Human-readable console output with color
DEFAULT_OUTPUT_FORMAT: Final[str] = "console"

#: Verbose output disabled by default
#: Rationale: Keep output clean, users can enable for debugging
DEFAULT_VERBOSE: Final[bool] = False

#: Show progress indicators
#: Rationale: Provide feedback during long-running operations
DEFAULT_SHOW_PROGRESS: Final[bool] = True

#: Color output enabled
#: Rationale: Improves readability and usability
DEFAULT_COLOR_OUTPUT: Final[bool] = True


# =============================================================================
# Quality Gate Defaults
# =============================================================================

#: Fail on test errors
#: Rationale: Tests should pass before committing/publishing
DEFAULT_FAIL_ON_TEST_ERRORS: Final[bool] = True

#: Fail on coverage below threshold
#: Rationale: Enforce minimum coverage standards
DEFAULT_FAIL_ON_COVERAGE: Final[bool] = True

#: Fail on complexity violations
#: Rationale: Prevent overly complex code from entering codebase
DEFAULT_FAIL_ON_COMPLEXITY: Final[bool] = True

#: Fail on security issues
#: Rationale: Security vulnerabilities must be addressed
DEFAULT_FAIL_ON_SECURITY: Final[bool] = True


# =============================================================================
# Cache and Performance Defaults
# =============================================================================

#: Enable caching for tool results
#: Rationale: Speeds up repeated runs during development
DEFAULT_ENABLE_CACHING: Final[bool] = True

#: Cache TTL in seconds (1 hour)
#: Rationale: Balance between freshness and performance
DEFAULT_CACHE_TTL: Final[int] = 3600

#: Maximum cache entries
#: Rationale: Prevent unbounded cache growth
DEFAULT_CACHE_MAX_ENTRIES: Final[int] = 1000


# =============================================================================
# AI and Auto-Fix Defaults
# =============================================================================

#: AI auto-fix disabled by default
#: Rationale: Requires API keys, opt-in for experimental features
DEFAULT_AI_FIX_ENABLED: Final[bool] = False

#: Default AI provider
#: Rationale: Claude has good Python understanding, but user can choose
DEFAULT_AI_PROVIDER: Final[str] = "claude"

#: Max iterations for AI auto-fix
#: Rationale: Prevent infinite loops, most issues fix in 1-3 attempts
DEFAULT_AI_MAX_ITERATIONS: Final[int] = 5


# =============================================================================
# Documentation Defaults
# =============================================================================

#: Documentation cleanup enabled
#: Rationale: Keep documentation organized and up-to-date
DEFAULT_DOCS_CLEANUP_ENABLED: Final[bool] = True

#: Backup before documentation cleanup
#: Rationale: Safety net in case of unintended deletions
DEFAULT_DOCS_BACKUP_BEFORE_CLEANUP: Final[bool] = True


# =============================================================================
# Git Integration Defaults
# =============================================================================

#: Create git commit by default
#: Rationale: False - let user control commit behavior
DEFAULT_GIT_COMMIT: Final[bool] = False

#: Create pull request by default
#: Rationale: False - requires remote repository configuration
DEFAULT_GIT_CREATE_PR: Final[bool] = False

#: Update pre-commit hooks by default
#: Rationale: False - explicit opt-in for hook modifications
DEFAULT_UPDATE_PRECOMMIT: Final[bool] = False


# =============================================================================
# Convenience Function
# =============================================================================


def get_all_defaults() -> dict[str, any]:
    """
    Get all default values as a dictionary.

    Returns:
        Dictionary mapping default names to their values

    Example:
        >>> defaults = get_all_defaults()
        >>> defaults['DEFAULT_COVERAGE_THRESHOLD']
        80
    """
    import inspect
    import sys

    # Get all module-level constants
    defaults = {}
    module = sys.modules[__name__]

    for name, value in inspect.getmembers(module):
        # Only include DEFAULT_ constants
        if not name.startswith("DEFAULT_"):
            continue
        # Skip functions
        if callable(value):
            continue
        # Skip modules
        if inspect.ismodule(value):
            continue
        # Skip the __all__ list
        if name == "__all__":
            continue

        defaults[name] = value

    return defaults


def get_default(name: str) -> any:
    """
    Get a specific default value by name.

    Args:
        name: Name of the default (with or without DEFAULT_ prefix)

    Returns:
        The default value

    Raises:
        AttributeError: If the default doesn't exist

    Example:
        >>> get_default('COVERAGE_THRESHOLD')
        80
        >>> get_default('DEFAULT_COVERAGE_THRESHOLD')
        80
    """
    # Add DEFAULT_ prefix if not present
    if not name.startswith("DEFAULT_"):
        name = f"DEFAULT_{name}"

    if name not in globals():
        raise AttributeError(f"Default '{name}' does not exist")

    return globals()[name]


__all__ = [
    # Quality thresholds
    "DEFAULT_COVERAGE_THRESHOLD",
    "DEFAULT_COMPLEXITY_THRESHOLD",
    "DEFAULT_MAX_FUNCTION_LENGTH",
    # Execution
    "DEFAULT_TEST_TIMEOUT",
    "DEFAULT_COMMAND_TIMEOUT",
    "DEFAULT_PARALLEL_EXECUTION",
    "DEFAULT_AUTO_DETECT_WORKERS",
    "DEFAULT_MAX_WORKERS",
    "DEFAULT_MIN_WORKERS",
    # Tool-specific
    "DEFAULT_RUFF_SELECT",
    "DEFAULT_RUFF_IGNORE",
    "DEFAULT_ENABLE_COVERAGE",
    "DEFAULT_COVERAGE_REPORTS",
    "DEFAULT_ENABLE_SECURITY",
    "DEFAULT_SECURITY_TOOLS",
    # Files and directories
    "DEFAULT_PROJECT_ROOT",
    "DEFAULT_EXCLUDE_DIRS",
    # Output
    "DEFAULT_OUTPUT_FORMAT",
    "DEFAULT_VERBOSE",
    "DEFAULT_SHOW_PROGRESS",
    "DEFAULT_COLOR_OUTPUT",
    # Quality gates
    "DEFAULT_FAIL_ON_TEST_ERRORS",
    "DEFAULT_FAIL_ON_COVERAGE",
    "DEFAULT_FAIL_ON_COMPLEXITY",
    "DEFAULT_FAIL_ON_SECURITY",
    # Cache and performance
    "DEFAULT_ENABLE_CACHING",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_CACHE_MAX_ENTRIES",
    # AI and auto-fix
    "DEFAULT_AI_FIX_ENABLED",
    "DEFAULT_AI_PROVIDER",
    "DEFAULT_AI_MAX_ITERATIONS",
    # Documentation
    "DEFAULT_DOCS_CLEANUP_ENABLED",
    "DEFAULT_DOCS_BACKUP_BEFORE_CLEANUP",
    # Git
    "DEFAULT_GIT_COMMIT",
    "DEFAULT_GIT_CREATE_PR",
    "DEFAULT_UPDATE_PRECOMMIT",
    # Utilities
    "get_all_defaults",
    "get_default",
]
