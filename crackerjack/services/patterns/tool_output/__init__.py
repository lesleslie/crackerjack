"""Tool output parsing regex patterns.

This package provides patterns for parsing output from various development tools
including linters (ruff), type checkers (pyright, mypy), security scanners (bandit),
dead code detectors (vulture), and complexity analyzers (complexipy).
"""

from .bandit import PATTERNS as BANDIT_PATTERNS
from .other import PATTERNS as OTHER_PATTERNS
from .pyright import PATTERNS as PYRIGHT_PATTERNS
from .ruff import PATTERNS as RUFF_PATTERNS

# Merge all tool output patterns into a single registry
PATTERNS = RUFF_PATTERNS | PYRIGHT_PATTERNS | BANDIT_PATTERNS | OTHER_PATTERNS

__all__ = ["PATTERNS"]
