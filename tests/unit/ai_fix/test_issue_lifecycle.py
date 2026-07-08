"""Tests for the per-issue :class:`IssueLifecycle` state machine.

PR 4 of the 2026-07-07 ai-fix design moves defect-#1 (no-op detection) out of
``AutofixCoordinator`` and into a per-issue lifecycle that also owns the retry
budget and tier-escalation policy. These tests pin:

- no-op flag propagation (defect #1),
- the retry budget,
- tier-escalation logic,
- classification pass-through.
"""

from __future__ import annotations

import pytest

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority
from crackerjack.ai_fix.issue_classifier import IssueKind
from crackerjack.ai_fix.issue_lifecycle import (
    IssueLifecycle,
    is_no_op_failure,
)


def _issue() -> Issue:
    return Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.MEDIUM,
        message="x is not defined",
        file_path="/tmp/test/module.py",
        line_number=1,
    )


def _fail(*remaining: str) -> FixResult:
    return FixResult(success=False, confidence=0.0, remaining_issues=list(remaining))


def _ok() -> FixResult:
    return FixResult(success=True, confidence=1.0)


def _no_op() -> FixResult:
    return _fail("no-op fix: file content unchanged")


class TestNoOpDetectionHelper:
    """The moved ``is_no_op_failure`` helper preserves coordinator behavior."""

    def test_detects_no_op_marker_in_feedback(self) -> None:
        assert is_no_op_failure("no-op fix: file content unchanged", None) is True

    def test_detects_marker_in_plan_results(self) -> None:
        results = [
            FixResult(
                success=False,
                remaining_issues=[
                    "write_file_content returned success but file content is unchanged"
                ],
            )
        ]
        assert is_no_op_failure("Attempt 1: ...", results) is True

    def test_false_for_normal_failure(self) -> None:
        assert is_no_op_failure("E501 line too long (ruff/refurb)", None) is False


class TestClassification:
    def test_classification_returns_kind(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.NEEDS_LLM)
        assert lifecycle.classification() is IssueKind.NEEDS_LLM


class TestNoOpFlag:
    def test_no_op_result_sets_flag_and_blocks_retry(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.FIXABLE_MECHANICAL)
        lifecycle.record_attempt(1, _no_op())

        assert lifecycle.no_op is True
        assert lifecycle.should_retry() is False

    def test_no_op_blocks_escalation(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.NEEDS_LLM)
        lifecycle.record_attempt(1, _no_op())

        assert lifecycle.should_escalate_to_next_tier() is False

    def test_normal_failure_does_not_set_no_op(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.FIXABLE_MECHANICAL)
        lifecycle.record_attempt(1, _fail("E501 line too long"))

        assert lifecycle.no_op is False


class TestRetryBudget:
    def test_retry_allowed_before_any_attempt(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.FIXABLE_MECHANICAL)
        assert lifecycle.should_retry() is True

    def test_retry_allowed_within_budget(self) -> None:
        lifecycle = IssueLifecycle(
            _issue(), IssueKind.FIXABLE_MECHANICAL, max_attempts=3
        )
        lifecycle.record_attempt(1, _fail("still broken"))
        assert lifecycle.attempts == 1
        assert lifecycle.should_retry() is True

    def test_retry_blocked_on_exhaustion(self) -> None:
        lifecycle = IssueLifecycle(
            _issue(), IssueKind.FIXABLE_MECHANICAL, max_attempts=3
        )
        for _ in range(3):
            lifecycle.record_attempt(1, _fail("still broken"))
        assert lifecycle.attempts == 3
        assert lifecycle.should_retry() is False

    def test_retry_blocked_after_success(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.FIXABLE_MECHANICAL)
        lifecycle.record_attempt(1, _ok())
        assert lifecycle.succeeded is True
        assert lifecycle.should_retry() is False


class TestNonFixable:
    def test_non_fixable_never_retries(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.NON_FIXABLE)
        assert lifecycle.should_retry() is False

    def test_non_fixable_never_escalates(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.NON_FIXABLE)
        lifecycle.record_attempt(1, _fail("nope"))
        assert lifecycle.should_escalate_to_next_tier() is False


class TestEscalation:
    def test_escalate_after_failed_lower_tier(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.NEEDS_LLM, max_tier=3)
        lifecycle.record_attempt(1, _fail("mechanical fixer failed"))
        assert lifecycle.should_escalate_to_next_tier() is True

    def test_no_escalation_before_any_attempt(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.NEEDS_LLM, max_tier=3)
        assert lifecycle.should_escalate_to_next_tier() is False

    def test_no_escalation_at_max_tier(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.NEEDS_LLM, max_tier=3)
        lifecycle.record_attempt(3, _fail("llm session failed"))
        assert lifecycle.should_escalate_to_next_tier() is False

    def test_no_escalation_after_success(self) -> None:
        lifecycle = IssueLifecycle(_issue(), IssueKind.NEEDS_LLM, max_tier=3)
        lifecycle.record_attempt(1, _ok())
        assert lifecycle.should_escalate_to_next_tier() is False


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
