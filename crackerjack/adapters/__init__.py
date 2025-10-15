"""Rust tool adapters for unified integration.

QA Framework Adapters:
The QA framework adapters are organized by check type in subdirectories:
- format/: Code formatting (ruff, mdformat)
- lint/: Code linting (codespell)
- security/: Security scanning (bandit, gitleaks)
- type/: Type checking (zuban)
- refactor/: Refactoring suggestions (refurb, creosote)
- complexity/: Complexity analysis (complexipy)
- utility/: Utility checks (text patterns, EOF, syntax, size, deps)
- shared/: Base classes for all QA adapters

ACB 0.19.0+ auto-discovers adapters via depends.set() at module level.
"""

from .lsp._base import (
    Issue,
    RustToolAdapter,
    ToolResult,
)
from .lsp._manager import RustToolHookManager
from .lsp.skylos import DeadCodeIssue, SkylosAdapter
from .lsp.zuban import TypeIssue, ZubanAdapter

# NOTE: ACB 0.19.0+ uses depends.set() for adapter registration at module level
# AI adapter registration moved to crackerjack.adapters.ai.claude module
# QA adapters are auto-discovered from their category subdirectories

__all__ = [
    "RustToolAdapter",
    "ToolResult",
    "Issue",
    "SkylosAdapter",
    "DeadCodeIssue",
    "ZubanAdapter",
    "TypeIssue",
    "RustToolHookManager",
]
