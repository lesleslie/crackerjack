from __future__ import annotations

from pathlib import Path

from crackerjack.agents.base import FixResult
from crackerjack.models.fix_plan import FixPlan

NO_OP_REMAINING_ISSUE = "no-op fix: file content unchanged"


NO_OP_REMAINING_ISSUE_PREFIX = "no-op fix:"


class TightenedFixer:
    async def execute(self, plan: FixPlan) -> FixResult: # pragma: no cover - protocol
        ...


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
