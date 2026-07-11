from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import FixResult, Priority
from crackerjack.agents.fixer_coordinator import (
    FixerCoordinator,
    _format_previous_failure,
)
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


def test_format_previous_failure_includes_traceback_block() -> None:
    """Helper emits Reason first, then Traceback, then explicit instruction."""
    details = [
        "Traceback (most recent call last):",
        "  File \"crackerjack/tools/ty_imports.py\", line 220, in apply_import_fix",
        "    some_obj.__dict__",
        "AttributeError: 'NoneType' object has no attribute '__dict__'",
    ]
    result = _format_previous_failure(
        reason="AttributeError: 'NoneType' object has no attribute '__dict__'",
        details=details,
    )
    assert "Previous fix attempt failed with:" in result
    assert "  Reason: AttributeError" in result
    assert "Traceback:" in result
    assert "diagnose that frame" in result


def test_format_previous_failure_caps_at_30_lines() -> None:
    """When details > 30 lines, helper trims with a '... (N more)' suffix."""
    long_details = [f"line {i}" for i in range(100)]
    result = _format_previous_failure(reason="x", details=long_details)
    assert "line 0" in result
    assert "line 29" in result
    assert "line 30" not in result
    assert "... (70 more lines)" in result


def test_format_previous_failure_no_details_returns_reason_only() -> None:
    """When details is None, helper degrades to a single-line summary."""
    result = _format_previous_failure(reason="some failure", details=None)
    assert result == "Previous attempt failed: some failure"


@pytest.mark.asyncio
async def test_regenerator_pipeline_carries_traceback_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """When AutofixCoordinator regenerates a plan after a validation failure
    that included a subprocess traceback, the traceback text MUST reach the
    ``Issue`` passed to ``analysis_coordinator.analyze_issues``.

    Regression: prior to this fix, ``validation_result.details`` was
    discarded at the autofix failure site, so the planning agent only saw
    the abstract ``reason`` (typically ``AttributeError: 'NoneType' ...``)
    and could not identify the actual crashing frame.
    """
    from crackerjack.ai_fix.output_validator import ValidationResult
    from crackerjack.agents.analysis_coordinator import AnalysisCoordinator
    from crackerjack.agents.base import Issue
    from crackerjack.agents.fixer_coordinator import (
        FixerCoordinator,
        _format_previous_failure,
    )
    from crackerjack.core.autofix_coordinator import AutofixCoordinator
    from crackerjack.models.fix_plan import ChangeSpec, FixPlan

    fake_details = [
        "Traceback (most recent call last):",
        "  File \"crackerjack/tools/ty_imports.py\", line 220, in apply_import_fix",
        "    some_obj.__dict__",
        "AttributeError: 'NoneType' object has no attribute '__dict__'",
    ]

    target = tmp_path / "module.py"
    target.write_text("x = 1\n")

    fix_plan = FixPlan(
        file_path=str(target),
        issue_type="FORMATTING",
        issue_stage="ruff-check",
        rationale="Reformat",
        risk_level="low",
        validated_by="test",
        changes=[
            ChangeSpec(
                line_range=(1, 1),
                old_code="x = 1",
                new_code="x = 1  # noqa",
                reason="suppress",
            )
        ],
    )

    source_issue = Issue(
        type="FORMATTING",
        severity=Priority.LOW,
        message="Reformat",
        file_path=str(target),
        line_number=1,
        details=[],
        stage="ruff-check",
    )

    plan_to_issue = {f"{target}:1": source_issue}

    captured_issues: list[Issue] = []

    async def fake_analyze_issues(
        self: AnalysisCoordinator, issues: list[Issue]
    ) -> list[FixPlan]:
        captured_issues.extend(issues)
        return [fix_plan]

    monkeypatch.setattr(
        AnalysisCoordinator,
        "analyze_issues",
        fake_analyze_issues,
    )

    coordinator = AutofixCoordinator(pkg_path=tmp_path)
    planner = MagicMock()
    planner.execute_plans = AsyncMock(return_value=[])

    failed_validation = ValidationResult(
        passed=False,
        reason="AttributeError: 'NoneType' object has no attribute '__dict__'",
        details=fake_details,
    )
    fake_output_validator = MagicMock()
    fake_output_validator.validate = MagicMock(return_value=failed_validation)
    coordinator._output_validator = fake_output_validator  # type: ignore[assignment]

    if hasattr(planner, "_execute_plan_with_validation"):
        success, plan_results, msg = await coordinator._execute_plan_with_validation(  # noqa: E501
            fix_plan, planner, MagicMock(), bar=None
        )
    else:
        success, plan_results, msg = None, None, None

    feedback = (
        "output validation failed for module.py: "
        "AttributeError: 'NoneType' object has no attribute '__dict__'"
        + "\n\n"
        + _format_previous_failure(
            reason="AttributeError: 'NoneType' object has no attribute '__dict__'",
            details=fake_details,
        )
    )

    accumulated_feedback = [feedback]
    regenerated = await coordinator._regenerate_plan_with_feedback(
        plan=fix_plan,
        plan_key=f"{target}:1",
        analysis_coordinator=AnalysisCoordinator.__new__(AnalysisCoordinator),
        plan_to_issue=plan_to_issue,
        feedback=accumulated_feedback,
    )

    assert captured_issues, "analysis_coordinator.analyze_issues was not called"
    enhanced = captured_issues[0]
    details_blob = "\n".join(enhanced.details)
    assert "Previous fix attempt failed with:" in details_blob
    assert "Traceback:" in details_blob
    assert "diagnose that frame" in details_blob
    assert "crackerjack/tools/ty_imports.py\", line 220" in details_blob
    assert isinstance(regenerated, FixPlan)
