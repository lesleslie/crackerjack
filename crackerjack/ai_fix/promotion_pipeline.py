from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


DEFAULT_EVIDENCE_THRESHOLD: int = 3


@dataclass(frozen=True)
class PromotionResult:
    promoted: bool
    reason: str
    pr_url: str | None = None
    fixer_path: Path | None = None
    duration_s: float = 0.0


@dataclass(frozen=True)
class SkillSnapshot:
    signature: str
    diff: str
    original_error: str
    recorded_count: int


@runtime_checkable
class LLMCodegen(Protocol):
    async def generate_fixer(
        self,
        *,
        signature: str,
        original_error: str,
        skill_diff: str,
    ) -> str: ...


@runtime_checkable
class SandboxRunner(Protocol):
    def run_tests(
        self,
        *,
        fixer_source: str,
        signature: str,
        project_root: Path,
    ) -> SandboxResult: ...


@dataclass(frozen=True)
class SandboxResult:
    passed: bool
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0


@runtime_checkable
class AutoFixerPRCreator(Protocol):
    def create_pr(
        self,
        *,
        fixer_source: str,
        signature: str,
        skill_diff: str,
    ) -> str: ...


class PromotionPipeline:
    def __init__(
        self,
        *,
        skill_reader: Any,
        llm_codegen: LLMCodegen,
        sandbox_runner: SandboxRunner,
        pr_creator: AutoFixerPRCreator,
        promotion_enabled: bool = False,
        evidence_threshold: int = DEFAULT_EVIDENCE_THRESHOLD,
        project_root: Path | None = None,
    ) -> None:
        self._skill_reader = skill_reader
        self._llm = llm_codegen
        self._sandbox = sandbox_runner
        self._pr = pr_creator
        self.promotion_enabled = promotion_enabled
        self.evidence_threshold = evidence_threshold
        self._project_root = project_root or Path.cwd()

    async def maybe_promote(self, signature: str) -> PromotionResult:
        import time

        if not self.promotion_enabled:
            logger.debug(
                "PromotionPipeline.maybe_promote(%s) skipped: promotion disabled",
                signature,
            )
            return PromotionResult(
                promoted=False,
                reason="promotion_disabled",
            )

        t0 = time.monotonic()

        snapshot = self._skill_reader(signature)
        if snapshot is None:
            return PromotionResult(
                promoted=False,
                reason="skill_not_found",
            )
        if snapshot.recorded_count < self.evidence_threshold:
            return PromotionResult(
                promoted=False,
                reason="insufficient_evidence",
            )

        try:
            fixer_source = await self._llm.generate_fixer(
                signature=signature,
                original_error=snapshot.original_error,
                skill_diff=snapshot.diff,
            )
        except Exception as exc:  # noqa: BLE001 - any LLM error is a single fail-mode
            logger.warning(
                "PromotionPipeline: LLM codegen failed for %s: %s",
                signature,
                exc,
            )
            return PromotionResult(
                promoted=False,
                reason=f"llm_error:{type(exc).__name__}",
                duration_s=time.monotonic() - t0,
            )

        if not fixer_source or not fixer_source.strip():
            return PromotionResult(
                promoted=False,
                reason="llm_returned_empty",
                duration_s=time.monotonic() - t0,
            )

        sandbox = self._sandbox.run_tests(
            fixer_source=fixer_source,
            signature=signature,
            project_root=self._project_root,
        )
        if not sandbox.passed:
            logger.info(
                "PromotionPipeline: sandbox rejected fixer for %s: %s",
                signature,
                sandbox.stderr[:500],
            )
            return PromotionResult(
                promoted=False,
                reason="sandbox_failed",
                duration_s=time.monotonic() - t0,
            )

        try:
            pr_url = self._pr.create_pr(
                fixer_source=fixer_source,
                signature=signature,
                skill_diff=snapshot.diff,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "PromotionPipeline: PR creation failed for %s: %s",
                signature,
                exc,
            )
            return PromotionResult(
                promoted=False,
                reason=f"pr_creation_failed:{type(exc).__name__}",
                duration_s=time.monotonic() - t0,
            )

        return PromotionResult(
            promoted=True,
            reason="success",
            pr_url=pr_url,
            duration_s=time.monotonic() - t0,
        )


__all__ = [
    "DEFAULT_EVIDENCE_THRESHOLD",
    "AutoFixerPRCreator",
    "LLMCodegen",
    "PromotionPipeline",
    "PromotionResult",
    "SandboxResult",
    "SandboxRunner",
    "SkillSnapshot",
]
