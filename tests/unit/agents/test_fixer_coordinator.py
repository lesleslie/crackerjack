from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.agents.fixer_coordinator import FixerCoordinator
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


@pytest.mark.asyncio
async def test_type_error_plan_preserves_stage_and_details(tmp_path) -> None:
    file_path = tmp_path / "example.py"
    file_path.write_text(
        "\n".join(
            [
                "def example():",
                "    return thing()",
            ]
            + [f"# line {i}" for i in range(3, 20)]
        )
        + "\n"
    )

    coordinator = FixerCoordinator(project_path=str(tmp_path))
    fixer = coordinator.fixers["TYPE_ERROR"]
    fixer.analyze_and_fix = AsyncMock(  # type: ignore[method-assign]
        return_value=FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["mock type fix"],
            files_modified=[str(file_path)],
        )
    )

    plan = FixPlan(
        file_path=str(file_path),
        issue_type="TYPE_ERROR",
        changes=[
            ChangeSpec(
                line_range=(12, 12),
                old_code="value = thing()",
                new_code="value = thing()",
                reason="type fix",
            )
        ],
        rationale="Fix type mismatch",
        risk_level="low",
        validated_by="test",
        issue_message="Type annotation mismatch from zuban",
        issue_stage="zuban",
        issue_details=["code: attr-defined", "severity: error"],
    )

    result = await coordinator.execute_plans([plan])

    assert result[0].success is True
    assert fixer.analyze_and_fix.await_count == 1

    issue = fixer.analyze_and_fix.await_args.args[0]
    assert issue.message == "Type annotation mismatch from zuban"
    assert issue.stage == "zuban"
    assert issue.details == ["code: attr-defined", "severity: error"]


@pytest.mark.asyncio
async def test_refurb_plan_preserves_furb_code(tmp_path) -> None:
    file_path = tmp_path / "example.py"
    file_path.write_text(
        "\n".join(
            [
                "def example():",
                "    return True",
            ]
            + [f"# line {i}" for i in range(3, 25)]
        )
        + "\n"
    )

    coordinator = FixerCoordinator(project_path=str(tmp_path))
    fixer = coordinator.fixers["REFURB"]
    fixer.analyze_and_fix = AsyncMock(  # type: ignore[method-assign]
        return_value=FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["mock refurb fix"],
            files_modified=[str(file_path)],
        )
    )

    plan = FixPlan(
        file_path=str(file_path),
        issue_type="REFURB",
        changes=[
            ChangeSpec(
                line_range=(20, 20),
                old_code="if value == True:",
                new_code="if value:",
                reason="refurb fix",
            )
        ],
        rationale="Refurb FURB136 suggestion",
        risk_level="low",
        validated_by="test",
        issue_message="FURB136: Replace boolean comparison",
        issue_stage="refurb",
        issue_details=["refurb_code: FURB136"],
    )

    result = await coordinator.execute_plans([plan])

    assert result[0].success is True
    assert fixer.analyze_and_fix.await_count == 1

    issue = fixer.analyze_and_fix.await_args.args[0]
    assert issue.message == "FURB136: Replace boolean comparison"
    assert issue.stage == "refurb"
    assert issue.details == ["refurb_code: FURB136"]


@pytest.mark.asyncio
async def test_type_error_plan_falls_back_to_architect_when_primary_noops(
    tmp_path,
) -> None:
    file_path = tmp_path / "example.py"
    file_path.write_text(
        "\n".join(
            [
                "def example():",
                "    return thing()",
            ]
            + [f"# line {i}" for i in range(3, 20)]
        )
        + "\n"
    )

    coordinator = FixerCoordinator(project_path=str(tmp_path))
    primary = coordinator.fixers["TYPE_ERROR"]
    fallback = coordinator.fixers["ARCHITECT"]

    primary.analyze_and_fix = AsyncMock(  # type: ignore[method-assign]
        return_value=FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No changes applied"],
        )
    )
    fallback.execute_fix_plan = AsyncMock(  # type: ignore[method-assign]
        return_value=FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["Applied planned type fix"],
            files_modified=["/tmp/example.py"],
        )
    )

    plan = FixPlan(
        file_path=str(file_path),
        issue_type="TYPE_ERROR",
        changes=[
            ChangeSpec(
                line_range=(1, 1),
                old_code="def example():",
                new_code="def example() -> None:",
                reason="Add return annotation",
            )
        ],
        rationale="Missing return type annotation",
        risk_level="low",
        validated_by="test",
        issue_message="Missing return type annotation",
        issue_stage="ruff-check",
        issue_details=["code: ANN201"],
    )

    result = await coordinator.execute_plans([plan])

    assert result[0].success is True
    assert primary.analyze_and_fix.await_count == 1
    assert fallback.execute_fix_plan.await_count == 1


@pytest.mark.asyncio
async def test_execute_plans_serializes_same_file_plans(tmp_path) -> None:
    file_path = tmp_path / "example.py"
    file_path.write_text("value = 1\n", encoding="utf-8")

    coordinator = FixerCoordinator(project_path=str(tmp_path))
    first_complete = False
    call_order: list[str] = []

    plan1 = FixPlan(
        file_path=str(file_path),
        issue_type="FORMATTING",
        changes=[
            ChangeSpec(
                line_range=(1, 1),
                old_code="value = 1",
                new_code="value = 2",
                reason="first change",
            )
        ],
        rationale="first",
        risk_level="low",
        validated_by="test",
        issue_message="first",
        issue_stage="ruff-check",
    )
    plan2 = FixPlan(
        file_path=str(file_path),
        issue_type="FORMATTING",
        changes=[
            ChangeSpec(
                line_range=(1, 1),
                old_code="value = 2",
                new_code="value = 3",
                reason="second change",
            )
        ],
        rationale="second",
        risk_level="low",
        validated_by="test",
        issue_message="second",
        issue_stage="ruff-check",
    )

    async def fake_execute_single_plan(plan: FixPlan) -> FixResult:
        nonlocal first_complete
        call_order.append(plan.issue_message or "")
        if plan.issue_message == "second":
            assert first_complete is True
        if plan.issue_message == "first":
            await asyncio.sleep(0)
            first_complete = True
        return FixResult(
            success=True,
            confidence=1.0,
            fixes_applied=[plan.issue_message or ""],
            files_modified=[str(file_path)],
        )

    with patch.object(
        coordinator,
        "_execute_single_plan",
        side_effect=fake_execute_single_plan,
    ):
        results = await coordinator.execute_plans([plan1, plan2])

    assert call_order == ["first", "second"]
    assert [result.success for result in results] == [True, True]
