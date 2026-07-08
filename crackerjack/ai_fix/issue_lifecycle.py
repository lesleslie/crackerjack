"""Per-issue lifecycle: retry budget, tier escalation, and no-op detection.

PR 4 of the 2026-07-07 ai-fix design. This module owns three concerns that were
previously scattered across ``AutofixCoordinator``:

1. **No-op detection (defect #1).** A fixer can report ``success=True`` while
   leaving the file byte-identical. The moved :func:`is_no_op_failure` helper
   recognizes the marker strings such fixers (and the tightened dispatcher)
   emit; a recorded no-op sets a sticky flag that makes the issue
   non-retryable. ``AutofixCoordinator._is_no_op_failure`` now delegates here.
2. **Retry budget.** How many attempts an issue is granted before the loop
   gives up.
3. **Tier escalation.** Whether a failed lower-tier attempt should hand off to
   the next (higher) tier.

The lifecycle also carries the issue's :class:`IssueKind` classification so the
router can make routing decisions without re-classifying.

PR 7 adds :func:`signature_for_issue` — the router's default signature for
``SkillStore.find`` lookups. It is the ``Issue`` analog of
:func:`crackerjack.agents.iterative_fix_agent.signature_for`, reusing that
module's backtick-normalization helper so a defect pattern keeps the same key
whether it is classified as a ``TyDiagnostic`` or a generic ``Issue``.
"""

from __future__ import annotations

import hashlib

from crackerjack.agents.base import FixResult, Issue
from crackerjack.agents.iterative_fix_agent import (
    _normalize_message,
)
from crackerjack.ai_fix.issue_classifier import IssueKind

# Default attempts before the retry budget is exhausted. Matches the historical
# "3 attempts" ceiling of the FixerCoordinator retry loop.
DEFAULT_MAX_ATTEMPTS = 3

# Highest tier the router escalates to (Tier-3 = LLM session). Escalation stops
# once an attempt at this tier has been recorded.
DEFAULT_MAX_TIER = 3

# Substrings that mark a "the fixer changed nothing" outcome. Moved verbatim
# from ``AutofixCoordinator._is_no_op_failure`` to preserve behavior.
NO_OP_MARKERS = (
    "no-op fix",
    "file content unchanged",
    "file content is unchanged",
    "no changes applied",
    "no meaningful change",
)


def is_no_op_failure(
    feedback: str,
    plan_results: list[FixResult] | None = None,
) -> bool:
    """Return ``True`` when ``feedback``/``plan_results`` describe a no-op fix.

    This is defect-#1's detection logic, moved out of ``AutofixCoordinator`` so
    the lifecycle (and the coordinator, via delegation) share one definition.
    """
    text_parts = [feedback.lower()]
    if plan_results:
        for result in plan_results:
            text_parts.extend(issue.lower() for issue in result.remaining_issues)

    text = " ".join(text_parts)
    return any(marker in text for marker in NO_OP_MARKERS)


class IssueLifecycle:
    """State machine for a single issue's journey through the fix tiers."""

    def __init__(
        self,
        issue: Issue,
        kind: IssueKind,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        max_tier: int = DEFAULT_MAX_TIER,
    ) -> None:
        self._issue = issue
        self._kind = kind
        self._max_attempts = max_attempts
        self._max_tier = max_tier
        self._attempts: list[tuple[int, FixResult]] = []
        self._no_op = False

    @property
    def issue(self) -> Issue:
        return self._issue

    @property
    def attempts(self) -> int:
        """Number of recorded fix attempts."""
        return len(self._attempts)

    @property
    def no_op(self) -> bool:
        """Sticky flag: set once a recorded attempt was a no-op fix."""
        return self._no_op

    @property
    def succeeded(self) -> bool:
        """Whether the most recent attempt reported success."""
        return bool(self._attempts) and self._attempts[-1][1].success

    @property
    def highest_tier_attempted(self) -> int:
        """Highest tier number seen across attempts (0 if none yet)."""
        if not self._attempts:
            return 0
        return max(tier for tier, _ in self._attempts)

    def record_attempt(self, tier: int, result: FixResult) -> None:
        """Record the outcome of a fix attempt at ``tier``.

        A no-op result flips the sticky :attr:`no_op` flag, which permanently
        disables retries and escalation for this issue.
        """
        self._attempts.append((tier, result))
        if is_no_op_failure("", [result]):
            self._no_op = True

    def should_retry(self) -> bool:
        """Whether the same tier should be attempted again.

        ``False`` when the issue is ``NON_FIXABLE``, a no-op was detected, the
        last attempt succeeded, or the retry budget is exhausted.
        """
        if self._kind is IssueKind.NON_FIXABLE:
            return False
        if self._no_op:
            return False
        if self.succeeded:
            return False
        return self.attempts < self._max_attempts

    def should_escalate_to_next_tier(self) -> bool:
        """Whether a failed attempt should hand off to the next higher tier.

        ``False`` when the issue is ``NON_FIXABLE``, a no-op was detected, no
        attempt has been made yet, the last attempt succeeded, or the highest
        tier has already been reached.
        """
        if self._kind is IssueKind.NON_FIXABLE:
            return False
        if self._no_op:
            return False
        if not self._attempts:
            return False
        if self.succeeded:
            return False
        return self.highest_tier_attempted < self._max_tier

    def classification(self) -> IssueKind:
        return self._kind


def signature_for_issue(issue: Issue) -> str:
    """Compute a stable, normalized signature for ``issue``.

    Mirrors the shape produced by
    :func:`crackerjack.agents.iterative_fix_agent.signature_for` for
    ``TyDiagnostic``: hash of the normalized ``issue.type`` (the
    equivalent of a "code") joined with the normalized ``issue.message``.

    The same backtick-normalization rules apply so two issues with the
    same defect pattern but different identifiers (``x is None`` vs
    ``y is None``) collapse to the same signature — that is how
    pattern-level replay keys work.

    PR 7: the router uses this as its default signature for
    ``SkillStore.find`` lookups so a successful Tier-3 dispatch and the
    next Tier-3 dispatch that hits the same defect share the same key.
    """
    code = getattr(issue.type, "value", str(issue.type))
    shape = f"{code}:{_normalize_message(issue.message)}"
    return hashlib.sha256(shape.encode()).hexdigest()[:16]


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_MAX_TIER",
    "NO_OP_MARKERS",
    "IssueLifecycle",
    "is_no_op_failure",
    "signature_for_issue",
]
