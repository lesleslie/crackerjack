from ..core import ValidatedPattern
from .error_patterns import PATTERNS as ERROR_PATTERNS
from .pytest_output import PATTERNS as PYTEST_OUTPUT_PATTERNS

PATTERNS: dict[str, ValidatedPattern] = PYTEST_OUTPUT_PATTERNS | ERROR_PATTERNS

__all__ = [
    "PATTERNS",
    "PYTEST_OUTPUT_PATTERNS",
    "ERROR_PATTERNS",
]
