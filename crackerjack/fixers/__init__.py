"""Framework-free deterministic fixers extracted from crackerjack.agents.

Each module here holds plain functions (no SubAgent/coordinator dependency)
that perform real AST/regex-based source transformations. This package is
populated incrementally as agents/*.py files are extracted; see
docs/superpowers/plans/2026-08-06-ai-fix-removal-extraction.md for the plan.
"""

from __future__ import annotations
