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
    DEFAULT_OVERSEER_MODEL = "MiniMax-M3-highspeed"

    def __init__(self, model: str = DEFAULT_OVERSEER_MODEL) -> None:
        self._model = model

    async def review_diff(
        self,
        diff: str,
        constitution: str,
        failure_context: str,
    ) -> OverseerVerdict:
        concerns: list[str] = []

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
