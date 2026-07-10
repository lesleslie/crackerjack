"""Tests for ai-fix stage thrash reduction in the retry loop.

Observed in a real ``crackerjack run --ai-fix`` session: the FixerCoordinator
retry loop (``_execute_single_plan_with_retry``) burned all 3 attempts on
outcomes that could never succeed on retry:

Defect #1 — No-op fix loop:
    A fixer returns ``success=True`` but leaves the file byte-identical. The
    coordinator detects the no-op, rolls back, and returns a failure whose
    feedback is ``"no-op fix: file content unchanged"``. ``_regenerate_plan_
    with_feedback`` re-runs *deterministic* analysis and produces the identical
    plan, so the same no-op recurs 3x → ``Max retries exceeded``. A deterministic
    no-op cannot be repaired by retry.

Defect #3 — No-progress validation-rejection loop:
    A generated fix repeatedly fails the *same* validation (e.g. ruff E501 on
    the same line) because regeneration keeps producing the identical plan.

Both are "no-progress" patterns. The fix:
    (a) ``_is_no_op_failure`` classifies a no-op result as non-retryable, so the
        loop stops after one attempt instead of retrying an unchangeable outcome.
    (b) ``_plans_equivalent`` detects when a regenerated plan equals the plan we
        just tried, so the loop stops instead of re-running an identical plan.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


def _make_plan(
    new_code: str = "x = 1\n", file_path: str = "/tmp/test/module.py"
) -> FixPlan:
    return FixPlan(
        file_path=file_path,
        issue_type="TYPE_ERROR",
        risk_level="low",
        validated_by="system",
        rationale="test",
        changes=[
            ChangeSpec(
                line_range=(1, 1),
                old_code="x=1\n",
                new_code=new_code,
                reason="test",
            )
        ],
    )


class TestNoOpFailureNonRetryable:
    """Defect #1: a detected no-op fix must be treated as non-retryable."""

    @pytest.fixture
    def coordinator(self):
        return AutofixCoordinator(console=None, pkg_path=Path("/tmp/test"))

    def test_is_no_op_failure_detects_no_op_marker(self, coordinator) -> None:
        """The coordinator-level no-op message must be classified as a no-op."""
        assert (
            coordinator._is_no_op_failure("no-op fix: file content unchanged", None)
            is True
        )

    def test_is_no_op_failure_detects_agent_marker_in_results(
        self, coordinator
    ) -> None:
        """A no-op reported via FixResult.remaining_issues must be detected."""
        results = [
            FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    "write_file_content returned success but file content is unchanged"
                ],
            )
        ]
        assert coordinator._is_no_op_failure("Attempt 1: ...", results) is True

    def test_is_no_op_failure_false_for_normal_failure(self, coordinator) -> None:
        """A genuine validation failure is NOT a no-op — it may be retryable."""
        assert (
            coordinator._is_no_op_failure(
                "Quality validation failed (ruff/refurb): E501 line too long",
                None,
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_no_op_stops_after_single_attempt(
        self, coordinator, tmp_path
    ) -> None:
        """A no-op failure must NOT trigger the 2 extra retries. The loop
        should stop after the first attempt without regenerating the plan."""
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        plan = _make_plan(file_path=str(target))
        coordinator._execute_plan_with_validation = AsyncMock(  # type: ignore[method-assign]
            return_value=(False, [], "no-op fix: file content unchanged")
        )
        coordinator._regenerate_plan_with_feedback = AsyncMock(  # type: ignore[method-assign]
            return_value=plan
        )

        result = await coordinator._execute_single_plan_with_retry(
            plan=plan,
            fixer_coordinator=AsyncMock(),
            validation_coordinator=AsyncMock(),
            analysis_coordinator=AsyncMock(),
            plan_to_issue={},
            plan_key="module.py:1:TYPE_ERROR",
            bar=None,
        )

        assert result.success is False
        assert coordinator._execute_plan_with_validation.await_count == 1, (
            "A deterministic no-op must not be retried — the loop should stop "
            "after the first attempt, not burn all 3."
        )
        assert coordinator._regenerate_plan_with_feedback.await_count == 0, (
            "No-op is non-retryable, so plan regeneration must not run."
        )


class TestNoProgressPlanRegeneration:
    """Defect #3: an identical regenerated plan must stop the retry loop."""

    @pytest.fixture
    def coordinator(self):
        return AutofixCoordinator(console=None, pkg_path=Path("/tmp/test"))

    def test_plans_equivalent_true_for_identical_plans(self, coordinator) -> None:
        assert coordinator._plans_equivalent(_make_plan(), _make_plan()) is True

    def test_plans_equivalent_false_for_different_changes(self, coordinator) -> None:
        assert (
            coordinator._plans_equivalent(
                _make_plan(new_code="x = 1\n"),
                _make_plan(new_code="x = 2\n"),
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_identical_regenerated_plan_stops_retry(
        self, coordinator, tmp_path
    ) -> None:
        """When regeneration yields a plan identical to the one just tried,
        the loop must stop rather than re-running the same failing plan."""
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        plan = _make_plan(file_path=str(target))
        coordinator._execute_plan_with_validation = AsyncMock(  # type: ignore[method-assign]
            return_value=(
                False,
                [],
                "Quality validation failed (ruff/refurb): E501 line too long",
            )
        )
        # Regeneration returns an equivalent (identical) plan every time.
        coordinator._regenerate_plan_with_feedback = AsyncMock(  # type: ignore[method-assign]
            return_value=_make_plan(file_path=str(target))
        )

        result = await coordinator._execute_single_plan_with_retry(
            plan=plan,
            fixer_coordinator=AsyncMock(),
            validation_coordinator=AsyncMock(),
            analysis_coordinator=AsyncMock(),
            plan_to_issue={},
            plan_key="module.py:1:TYPE_ERROR",
            bar=None,
        )

        assert result.success is False
        assert coordinator._execute_plan_with_validation.await_count == 1, (
            "After regeneration produces an identical plan, the loop must "
            "stop — not execute the same plan a second and third time."
        )
        assert coordinator._regenerate_plan_with_feedback.await_count == 1, (
            "Exactly one regeneration attempt should occur before the "
            "no-progress guard trips."
        )
