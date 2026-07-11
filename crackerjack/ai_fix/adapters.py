from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from crackerjack.agents.base import FixResult, Issue

if TYPE_CHECKING:
    from crackerjack.agents.fixer_coordinator import FixerCoordinator

logger = logging.getLogger(__name__)


class _Tier3Adapter:
    def __init__(self, iterative_agent: Any) -> None:
        self._agent = iterative_agent

    async def fix(self, issue: Issue) -> FixResult:
        if self._agent is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["tier-3 not attached"],
            )
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["tier-3 requires a file_path"],
            )

        from crackerjack.agents.iterative_fix_agent import TyDiagnostic

        target = Path(issue.file_path)
        diagnostics = [
            TyDiagnostic(
                file=target,
                line=issue.line_number or 0,
                col=0,
                code=issue.type.value,
                message=issue.message,
            )
        ]
        try:
            outcome = self._agent.fix_file(target, diagnostics)
        except Exception as exc:
            logger.debug("Tier-3 dispatch raised for %s: %s", issue.file_path, exc)
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"tier-3 exception: {exc}"],
            )

        actually_modified = bool(outcome.success) and bool(
            getattr(outcome, "dispatched_to_pool", False)
        )

        if outcome.success and actually_modified:
            return FixResult(
                success=True,
                confidence=0.5,
                fixes_applied=[
                    f"{'skill-replay' if outcome.path_was_skill_replay else 'worker-dispatch'}: {outcome.message}"  # noqa: E501
                ],
                files_modified=[issue.file_path],
            )
        if outcome.success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"tier-3 reported success but did not write bytes: {outcome.message}"  # noqa: E501
                ],
            )
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[outcome.message],
        )


class _Tier2Adapter:
    def __init__(self, fixer_coordinator: FixerCoordinator) -> None:
        self._fixer_coordinator = fixer_coordinator

    async def fix(self, issue: Issue) -> FixResult:

        for candidate in ("TYPE_ERROR", "ARCHITECT", "REFURB"):
            fixer = self._fixer_coordinator.fixers.get(candidate)
            if fixer is None:
                continue
            if hasattr(fixer, "analyze_and_fix"):
                try:
                    return await fixer.analyze_and_fix(issue)
                except Exception as exc:
                    logger.debug(
                        "Tier-2 dispatcher %s raised for %s: %s",
                        type(fixer).__name__,
                        issue.file_path,
                        exc,
                    )
                    return FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[
                            f"tier-2 {type(fixer).__name__} exception: {exc}"
                        ],
                    )
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["tier-2: no eligible dispatcher"],
        )


__all__ = ["_Tier2Adapter", "_Tier3Adapter"]
