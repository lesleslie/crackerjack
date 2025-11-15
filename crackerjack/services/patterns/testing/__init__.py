"""Testing pattern modules.

This package contains pattern collections for parsing and analyzing
pytest test output and test error patterns.
"""

from ..core import ValidatedPattern
from .error_patterns import PATTERNS as ERROR_PATTERNS
from .pytest_output import PATTERNS as PYTEST_OUTPUT_PATTERNS

# Merge all testing patterns into a single registry
PATTERNS: dict[str, ValidatedPattern] = PYTEST_OUTPUT_PATTERNS | ERROR_PATTERNS

__all__ = [
    "PATTERNS",
    "PYTEST_OUTPUT_PATTERNS",
    "ERROR_PATTERNS",
]
