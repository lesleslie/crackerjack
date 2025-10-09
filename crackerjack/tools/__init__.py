"""Native tool implementations for crackerjack (Phase 8).

This package contains Python implementations of quality checking tools,
providing direct invocation without pre-commit wrapper overhead.

Native tools replace pre-commit-hooks utilities with equivalent functionality:
- trailing_whitespace: Remove trailing whitespace
- end_of_file_fixer: Ensure files end with newline
- check_yaml: Validate YAML syntax
- check_toml: Validate TOML syntax
- check_added_large_files: Warn on large file additions
"""

from __future__ import annotations

__all__ = [
    "trailing_whitespace",
    "end_of_file_fixer",
    "check_yaml",
    "check_toml",
    "check_added_large_files",
]
