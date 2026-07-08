"""PR 8 (self-improving loop): promotion pipeline + supporting types.

The pipeline turns a *cached skill* (a diff that a Tier-3 LLM session
produced to fix an issue) into a *mechanical fixer* (a Python file that
fixes the same issue class without needing the LLM again). When the
mechanical fixer's test suite passes, the pipeline submits a PR so a
human can review and merge.

Three collaborators are injected:

* :class:`LLMCodegen` — turns the skill's diff + the original error
  signature into a Python fixer module. The LLM is mocked in tests;
  a real :class:`ClaudeLLMCodegen` is gated behind
  ``promotion_enabled=True``.
* :class:`SandboxRunner` — imports the generated fixer and runs the
  skill's original test cases against it. Must pass for promotion.
* :class:`AutoFixerPRCreator` — opens the GitHub PR with the generated
  fixer, the skill's diff, and a "promoted from skill" header.

The whole pipeline is **flag-gated**. With ``promotion_enabled=False``
(the default, and the only safe setting for unaudited CI), the
pipeline is a no-op. The user opts in by passing
``--ai-fix-auto-promote``. This is the explicit-consent gate the
safety review required: nothing happens until a human runs the
crackerjack binary with that flag.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# Default evidence threshold: a skill must have been replayed and
# validated this many times before we trust it enough to ask an LLM
# to derive a mechanical fixer from it. 3 is the design default; can
# be overridden per-pipeline via __init__.
DEFAULT_EVIDENCE_THRESHOLD: int = 3


@dataclass(frozen=True)
class PromotionResult:
    """Outcome of :meth:`PromotionPipeline.maybe_promote`.

    ``promoted`` is True only when the full chain succeeded: skill had
    enough evidence, LLM produced a fixer, sandbox validated it, PR
    was created. Any failure flips ``promoted`` to False and ``reason``
    names the gate that failed.
    """

    promoted: bool
    reason: str
    pr_url: str | None = None
    fixer_path: Path | None = None
    duration_s: float = 0.0


@dataclass(frozen=True)
class SkillSnapshot:
    """A point-in-time view of a cached skill, used by the LLM codegen.

    The pipeline constructs one of these from the SkillStore so the
    LLM gets the diff and the original error together. Storing the
    snapshot (rather than a live reference) means the LLM call is
    independent of subsequent skill updates.
    """

    signature: str
    diff: str
    original_error: str
    recorded_count: int


@runtime_checkable
class LLMCodegen(Protocol):
    """Anything that can turn a skill snapshot into a Python fixer module.

    The contract is deliberately small: input is the skill's signature,
    original error, and recorded diff; output is the full Python
    source of a fixer module (a single .py file's contents).
    """

    async def generate_fixer(
        self,
        *,
        signature: str,
        original_error: str,
        skill_diff: str,
    ) -> str: ...


@runtime_checkable
class SandboxRunner(Protocol):
    """Anything that can validate a generated fixer against test cases.

    The runner imports the generated module, replays the original
    error message, and returns a pass/fail result. The exact contract
    is intentionally loose: the runner has access to the skill's
    test cases, the project root, and the issue signature; how it
    validates is up to the implementation.
    """

    def run_tests(
        self,
        *,
        fixer_source: str,
        signature: str,
        project_root: Path,
    ) -> SandboxResult: ...


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of a :class:`SandboxRunner` invocation.

    ``passed`` is True iff the generated fixer reproduced the skill's
    behaviour against the skill's recorded test cases. ``stderr`` and
    ``stdout`` are captured for the PR body and the run log.
    """

    passed: bool
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0


@runtime_checkable
class AutoFixerPRCreator(Protocol):
    """Anything that can submit a GitHub PR for a generated fixer.

    Implementations should be side-effect-only: write the file to
    ``auto_fixers/`` (or the implementation-defined target dir),
    open a PR, return the PR URL. No retries, no fallback.
    """

    def create_pr(
        self,
        *,
        fixer_source: str,
        signature: str,
        skill_diff: str,
    ) -> str: ...


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PromotionPipeline:
    """End-to-end skill-to-mechanical-fixer pipeline.

    Lifecycle of a promotion:

    1. Caller invokes :meth:`maybe_promote(signature)`.
    2. Pipeline checks :attr:`promotion_enabled`. If False, return
       ``PromotionResult(promoted=False, reason="promotion_disabled")``
       — no LLM call, no PR, no side effects.
    3. Pipeline asks the injected ``skill_reader`` (a callable) for
       the skill snapshot. If absent or below ``evidence_threshold``,
       return ``reason="insufficient_evidence"``.
    4. Pipeline calls ``await llm_codegen.generate_fixer(...)``.
       On exception, return ``reason="llm_error"``.
    5. Pipeline calls ``sandbox_runner.run_tests(...)``. If the
       sandbox reports failure, return ``reason="sandbox_failed"``.
    6. Pipeline calls ``pr_creator.create_pr(...)``. If the creator
       raises, return ``reason="pr_creation_failed"``; the generated
       fixer is left in a temp dir for human pickup.
    7. Return ``PromotionResult(promoted=True, pr_url=..., ...)``.
    """

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
        """Promote the skill ``signature`` to a mechanical fixer, if eligible.

        Returns a :class:`PromotionResult` describing the outcome.
        ``result.promoted`` is True only when the full chain succeeded.
        Every short-circuit path returns ``promoted=False`` with a
        ``reason`` naming the gate that fired.
        """
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

        # Gate 1: skill must exist with enough evidence.
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

        # Gate 2: LLM produces a fixer.
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

        # Gate 3: sandbox validates the fixer.
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

        # Gate 4: PR creation. If this fails we still wrote the
        # generated source to a temp path (the PR creator owns that);
        # the human can pick it up manually.
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
