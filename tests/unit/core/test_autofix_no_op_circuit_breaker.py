"""Test the _plan_signature helper and no-op circuit breaker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.ai_fix.tightened_dispatcher import NO_OP_REMAINING_ISSUE
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


def _make_plan(
    issue_type: str = "refactor_for_clarity",
    file_path: str = "crackerjack/foo.py",
    changes: tuple[ChangeSpec, ...] = (),
    rationale: str = "default rationale",
) -> FixPlan:
    return FixPlan(
        issue_type=issue_type,
        file_path=file_path,
        changes=list(changes),
        rationale=rationale,
        risk_level="low",
        validated_by="test",
        issue_message="test",
        issue_stage="test",
        issue_details=[],
    )


def test_plan_signature_is_stable_for_identical_plans() -> None:
    p1 = _make_plan()
    p2 = _make_plan()
    assert AutofixCoordinator._plan_signature(p1) == AutofixCoordinator._plan_signature(p2)


def test_plan_signature_differs_for_distinct_file_paths() -> None:
    p1 = _make_plan(file_path="crackerjack/a.py")
    p2 = _make_plan(file_path="crackerjack/b.py")
    assert AutofixCoordinator._plan_signature(p1) != AutofixCoordinator._plan_signature(p2)


def test_plan_signature_ignores_rationale() -> None:
    p1 = _make_plan(rationale="first")
    p2 = _make_plan(rationale="second")
    assert AutofixCoordinator._plan_signature(p1) == AutofixCoordinator._plan_signature(p2)


def test_plan_signature_differs_for_distinct_changes() -> None:
    p1 = _make_plan(
        changes=(
            ChangeSpec(
                line_range=(1, 1),
                old_code="x = 1",
                new_code="x = 2",
                reason="test",
            ),
        )
    )
    p2 = _make_plan(
        changes=(
            ChangeSpec(
                line_range=(1, 1),
                old_code="x = 1",
                new_code="x = 999",
                reason="test",
            ),
        )
    )
    assert AutofixCoordinator._plan_signature(p1) != AutofixCoordinator._plan_signature(p2)


@pytest.mark.asyncio
async def test_circuit_breaker_skips_after_two_no_op_results() -> None:
    """After 2 consecutive no-op attempts, the loop should break with 'stuck' reason."""
    from pathlib import Path

    from crackerjack.agents.base import FixResult

    coord = AutofixCoordinator(pkg_path=Path("."), max_iterations=3)

    # Stub _execute_plan_with_validation to always return no-op
    no_op_result = FixResult(
        success=False,
        confidence=0.0,
        fixes_applied=[],
        remaining_issues=[NO_OP_REMAINING_ISSUE],
        recommendations=[],
        files_modified=[],
        issue_specific_confidence=None,
    )
    stuck_result = FixResult(
        success=False,
        confidence=0.0,
        fixes_applied=[],
        remaining_issues=["stuck: planner producing identical plans"],
        recommendations=[],
        files_modified=[],
        issue_specific_confidence=None,
    )
    coord._execute_plan_with_validation = AsyncMock(  # type: ignore[method-assign]
        return_value=(False, [no_op_result], "no-op")
    )
    # The regenerate helper always returns the SAME plan so signature is stable
    plan = _make_plan()
    coord._regenerate_plan_with_feedback = AsyncMock(  # type: ignore[method-assign]
        return_value=plan
    )
    # _plans_equivalent returns False so the loop progresses past the
    # "No-Progress Error" early-exit; only the new breaker should fire.
    coord._plans_equivalent = MagicMock(  # type: ignore[method-assign]
        return_value=False
    )
    coord._classify_terminal_failure = MagicMock(  # type: ignore[method-assign]
        return_value=None
    )
    coord._is_global_budget_exhausted = lambda: False  # type: ignore[method-assign]
    coord._fail_plan = MagicMock(  # type: ignore[method-assign]
        return_value=stuck_result
    )
    coord._is_writable_target = MagicMock(  # type: ignore[method-assign]
        return_value=True
    )
    coord._global_attempt_count = 0
    coord.logger = MagicMock()  # type: ignore[assignment]

    fc = MagicMock()
    vc = MagicMock()
    ac = MagicMock()
    bar = MagicMock()
    plan_to_issue: dict[str, object] = {}
    plan_key = "test-key"

    result = await coord._execute_single_plan_with_retry(
        plan=plan,
        fixer_coordinator=fc,
        validation_coordinator=vc,
        analysis_coordinator=ac,
        plan_to_issue=plan_to_issue,  # type: ignore[arg-type]
        plan_key=plan_key,
        bar=bar,
    )

    # The breaker must have routed through _fail_plan with "Stuck Plan"
    assert result is stuck_result
    coord._fail_plan.assert_called_once()  # type: ignore[attr-defined]
    args, _ = coord._fail_plan.call_args  # type: ignore[attr-defined]
    assert args[0] == "Stuck Plan"
