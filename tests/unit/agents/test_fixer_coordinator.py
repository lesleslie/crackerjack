from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.agents.fixer_coordinator import FixerCoordinator
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


@pytest.mark.asyncio
async def test_type_error_plan_preserves_stage_and_details() -> None:
    coordinator = FixerCoordinator(project_path="/tmp")
    fixer = coordinator.fixers["TYPE_ERROR"]
    fixer.analyze_and_fix = AsyncMock(  # type: ignore[method-assign]
        return_value=FixResult(success=True, confidence=0.9)
    )

    plan = FixPlan(
        file_path="/tmp/example.py",
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
async def test_refurb_plan_preserves_furb_code() -> None:
    coordinator = FixerCoordinator(project_path="/tmp")
    fixer = coordinator.fixers["REFURB"]
    fixer.analyze_and_fix = AsyncMock(  # type: ignore[method-assign]
        return_value=FixResult(success=True, confidence=0.9)
    )

    plan = FixPlan(
        file_path="/tmp/example.py",
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
