"""Adapters that wrap the existing tier-2 / tier-3 dispatchers for :class:`FixRouter`.

The :class:`crackerjack.ai_fix.fix_router.FixRouter` calls ``async fix(issue)
-> FixResult`` on its Tier-2 and Tier-3 collaborators. The historical
dispatchers expose different shapes:

- Tier-3: ``IterativeFixAgent.fix_file(path, diagnostics) -> FixOutcome``
- Tier-2: ``TypeErrorSpecialistAgent.analyze_and_fix(issue) -> FixResult``
  (or no such agent at all — Tier-2 is a thin pass-through).

This module ships thin ``TierDispatcher``-shaped adapters that the
``AutofixCoordinator`` builds when wiring the router. Keeping the adapters
here (next to the router) avoids polluting :class:`IterativeFixAgent` and
:class:`FixerCoordinator` with router-internal types.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from crackerjack.agents.base import FixResult, Issue

if TYPE_CHECKING:
    from crackerjack.agents.fixer_coordinator import FixerCoordinator

logger = logging.getLogger(__name__)


class _Tier3Adapter:
    """Adapt :class:`IterativeFixAgent` to the router's TierDispatcher shape.

    The router calls ``await tier3.fix(issue) -> FixResult``. The
    IterativeFixAgent takes a path + diagnostics, not an Issue — so the
    adapter synthesizes a single :class:`TyDiagnostic` from the Issue's
    line number / type / message and forwards the call.
    """

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
        # Local import — :class:`TyDiagnostic` lives in the agent module to
        # keep this adapter free of a hard dependency on the agent module
        # at import time (avoids cycles when tests stub the agent).
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
        # Mirror ``FixerCoordinator.route_tier3_plan_sync`` — only claim
        # the file was modified when the worker actually wrote bytes.
        actually_modified = bool(outcome.success) and bool(
            getattr(outcome, "dispatched_to_pool", False)
        )
        return FixResult(
            success=bool(outcome.success),
            confidence=0.5 if outcome.success else 0.0,
            fixes_applied=[
                f"{'skill-replay' if outcome.path_was_skill_replay else 'worker-dispatch'}: {outcome.message}"
            ]
            if outcome.success
            else [],
            files_modified=[issue.file_path] if actually_modified else [],
            remaining_issues=[] if outcome.success else [outcome.message],
        )


class _Tier2Adapter:
    """Adapt the existing Tier-2 fixer-set to the router's TierDispatcher shape.

    Tier-2 in the legacy coordinator is "the next built-in fixer in the
    candidate-fixer chain." The router instead delegates Tier-2 to a single
    dedicated dispatcher — for now we wrap ``FixerCoordinator._execute_single_plan``
    with the ``analyze_and_fix`` semantics, so any registered
    ``TypeErrorSpecialistAgent`` (or the next fallback) is treated as
    Tier-2.

    The implementation is deliberately conservative: it calls
    ``fixer.analyze_and_fix(issue)`` on the registered ``TYPE_ERROR`` fixer
    and forwards the result. If no Type-Error fixer is registered, Tier-2
    returns a failure.
    """

    def __init__(self, fixer_coordinator: FixerCoordinator) -> None:
        self._fixer_coordinator = fixer_coordinator

    async def fix(self, issue: Issue) -> FixResult:
        # Prefer TYPE_ERROR — the historical Tier-2 entry point — but
        # fall back to any other registered fixer if TYPE_ERROR is
        # missing.
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
