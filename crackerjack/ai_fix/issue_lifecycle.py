
from __future__ import annotations

import hashlib

from crackerjack.agents.base import FixResult, Issue
from crackerjack.agents.iterative_fix_agent import (
    signature_shape,
)
from crackerjack.ai_fix.issue_classifier import IssueKind


DEFAULT_MAX_ATTEMPTS = 3


DEFAULT_MAX_TIER = 3


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
    text_parts = [feedback.lower()]
    if plan_results:
        for result in plan_results:
            text_parts.extend(issue.lower() for issue in result.remaining_issues)

    text = " ".join(text_parts)
    return any(marker in text for marker in NO_OP_MARKERS)


class IssueLifecycle:

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
        return len(self._attempts)

    @property
    def no_op(self) -> bool:
        return self._no_op

    @property
    def succeeded(self) -> bool:
        return bool(self._attempts) and self._attempts[-1][1].success

    @property
    def highest_tier_attempted(self) -> int:
        if not self._attempts:
            return 0
        return max(tier for tier, _ in self._attempts)

    def record_attempt(self, tier: int, result: FixResult) -> None:
        self._attempts.append((tier, result))
        if is_no_op_failure("", [result]):
            self._no_op = True

    def should_retry(self) -> bool:
        if self._kind is IssueKind.NON_FIXABLE:
            return False
        if self._no_op:
            return False
        if self.succeeded:
            return False
        return self.attempts < self._max_attempts

    def should_escalate_to_next_tier(self) -> bool:
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
    code = getattr(issue.type, "value", str(issue.type))
    return hashlib.sha256(signature_shape(code, issue.message).encode()).hexdigest()[
        :16
    ]


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_MAX_TIER",
    "NO_OP_MARKERS",
    "IssueLifecycle",
    "is_no_op_failure",
    "signature_for_issue",
]
