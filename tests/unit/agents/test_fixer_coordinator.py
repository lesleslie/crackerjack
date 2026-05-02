from __future__ import annotations

from unittest.mock import AsyncMock

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
