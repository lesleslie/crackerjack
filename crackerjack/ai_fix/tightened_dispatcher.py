from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from crackerjack.agents.base import FixResult
from crackerjack.models.fix_plan import FixPlan

NO_OP_REMAINING_ISSUE = "no-op fix: file content unchanged"


NO_OP_REMAINING_ISSUE_PREFIX = "no-op fix:"


@runtime_checkable
class TightenedFixer(Protocol):
    async def execute(self, plan: FixPlan) -> FixResult: ...


async def dispatch_with_bytes_check(
    fixer: TightenedFixer, plan: FixPlan, target: Path
) -> FixResult:
    before = target.read_bytes()
    result = await fixer.execute(plan)
    after = target.read_bytes()

    if result.success and before == after:
        return FixResult(
            success=False,
            confidence=0.0,
            fixes_applied=result.fixes_applied.copy(),
            remaining_issues=[NO_OP_REMAINING_ISSUE],
            recommendations=result.recommendations.copy(),
            files_modified=result.files_modified.copy(),
            issue_specific_confidence=result.issue_specific_confidence,
        )

    return result


__all__ = [
    "NO_OP_REMAINING_ISSUE",
    "NO_OP_REMAINING_ISSUE_PREFIX",
    "TightenedFixer",
    "dispatch_with_bytes_check",
]
