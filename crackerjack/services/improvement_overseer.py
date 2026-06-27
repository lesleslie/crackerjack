from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from oneiric.core.logging import get_logger

if TYPE_CHECKING:
    from crackerjack.services.improvement_generator import ImprovementProposal

logger = get_logger(__name__)


@dataclass
class OverseerVerdict:
    approved: bool
    concerns: list[str]
    model_used: str


class ImprovementOverseer:
    """Independent second-opinion LLM review between diff generation and application.

    Uses a DIFFERENT model from ImprovementGenerator (C-NEW-24). Same-model evaluation
    is the primary failure mode in self-modifying AI systems (SICA ICLR 2025).

    The overseer evaluates every proposal against the constitutional invariants.
    Any concern (even minor) escalates to PR-only — never auto-apply.
    """

    DEFAULT_OVERSEER_MODEL = "MiniMax-M3-highspeed"

    def __init__(self, model: str = DEFAULT_OVERSEER_MODEL) -> None:
        self._model = model

    async def review_diff(
        self,
        diff: str,
        constitution: str,
        failure_context: str,
    ) -> OverseerVerdict:
        """Review a proposed diff against the constitution.

        Returns OverseerVerdict with approved=False and populated concerns
        if any invariant is potentially violated. Even a single concern
        prevents auto-apply — human PR review is required.

        This is a stub implementation. Production wires to an actual LLM
        call via Mahavishnu cloud_worker using self._model.
        """
        concerns: list[str] = []

        # Structural checks that don't need LLM (fast path)
        if "Any" in diff and "# type: ignore" not in diff:
            concerns.append("Diff may introduce untyped `Any` usage")

        if "import logging" in diff:
            concerns.append("Diff uses stdlib logging instead of oneiric logger")

        if "assert " in diff:
            concerns.append(
                "Diff contains assert statement (banned in production code)"
            )

        logger.info(
            "ImprovementOverseer (%s): %d concerns for diff (%d chars)",
            self._model,
            len(concerns),
            len(diff),
        )

        return OverseerVerdict(
            approved=len(concerns) == 0,
            concerns=concerns,
            model_used=self._model,
        )

    def build_review_context(
        self,
        proposal: ImprovementProposal,
        constitution: str,
        failure_context: str,
    ) -> dict[str, Any]:
        return {
            "model": self._model,
            "constitution": constitution,
            "diff": proposal.diff,
            "rationale": proposal.rationale,
            "improvement_type": proposal.improvement_type,
            "failure_context": failure_context,
        }
