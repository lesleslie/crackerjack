"""Dispatch a fixer plan with a tightened "bytes-differ" success gate.

The current ``Fixer.execute`` contract reports success when the underlying
operation does not raise, not when bytes on disk actually changed. That gap is
defect #1 in the 2026-07-07 design — fixers can lie about success and drive the
loop into 1,000+ no-op retries.

This module wraps a fixer with a "read before / execute / read after" check.
When ``fixer.execute`` reports ``success=True`` but the target file's bytes are
identical, the wrapper downgrades the result to a no-op failure instead of
letting the lie propagate.
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.agents.base import FixResult
from crackerjack.models.fix_plan import FixPlan

NO_OP_REMAINING_ISSUE = "no-op fix: file content unchanged"

# Public escape hatch so callers can distinguish a synthesized no-op from a
# genuine fixer-reported failure (e.g. for logging dashboards or routing).
NO_OP_REMAINING_ISSUE_PREFIX = "no-op fix:"


class TightenedFixer:
    """Structural protocol for objects this dispatcher can call.

    Kept as a ``Protocol`` so callers can swap in any class exposing
    ``async def execute(plan) -> FixResult`` without inheritance.
    """

    async def execute(self, plan: FixPlan) -> FixResult:  # pragma: no cover - protocol
        ...


async def dispatch_with_bytes_check(
    fixer: TightenedFixer, plan: FixPlan, target: Path
) -> FixResult:
    """Invoke ``fixer.execute(plan)`` and downgrade success when bytes unchanged.

    The ``target`` parameter is explicit (rather than read from
    ``plan.file_path``) so the caller can pin the file under inspection — that
    lets the dispatcher cope with relative paths, symlinks, or rewrites that
    happen to change ``plan.file_path`` mid-dispatch.

    On ``success=True`` but unchanged bytes, returns a fresh ``FixResult`` with:

    - ``success=False``
    - ``remaining_issues=[NO_OP_REMAINING_ISSUE]``
    - ``confidence=0.0``
    - The original ``fixes_applied``, ``files_modified``, ``recommendations``,
      and ``issue_specific_confidence`` preserved so downstream stages still
      see what the fixer claimed to do.
    """
    before = target.read_bytes()
    result = await fixer.execute(plan)
    after = target.read_bytes()

    if result.success and before == after:
        return FixResult(
            success=False,
            confidence=0.0,
            fixes_applied=list(result.fixes_applied),
            remaining_issues=[NO_OP_REMAINING_ISSUE],
            recommendations=list(result.recommendations),
            files_modified=list(result.files_modified),
            issue_specific_confidence=result.issue_specific_confidence,
        )

    return result


__all__ = [
    "NO_OP_REMAINING_ISSUE",
    "NO_OP_REMAINING_ISSUE_PREFIX",
    "TightenedFixer",
    "dispatch_with_bytes_check",
]
