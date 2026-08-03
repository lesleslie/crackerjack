"""Pre-commit and quality hooks for the Crackerjack workflow.

This package hosts the two-stage hook execution model: fast hooks
(formatters, basic checks) and comprehensive hooks (type checkers,
security scanners, complexity analysis). Each hook module exposes a
single async entry point that returns 0 (pass), 1 (warn), or 2 (block).
"""

from __future__ import annotations
