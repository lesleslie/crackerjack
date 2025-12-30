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

Adapters are registered via constructor injection in server initialization.
"""

from .lsp._base import (
    Issue,
    RustToolAdapter,
    ToolResult,
)
from .lsp._manager import RustToolHookManager
from .lsp.skylos import DeadCodeIssue, SkylosAdapter
from .lsp.zuban import TypeIssue, ZubanAdapter

# Adapters are registered via constructor injection in server initialization
# AI adapter registration in crackerjack.adapters.ai.claude module
# QA adapters are loaded from their category subdirectories

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
