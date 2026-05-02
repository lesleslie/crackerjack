from pathlib import Path

from crackerjack.agents.base import AgentContext
from crackerjack.agents.formatting_agent import FormattingAgent
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


def test_execute_fix_plan_applies_planned_change(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    file_path.write_text("value = 1\n", encoding="utf-8")

    agent = FormattingAgent(AgentContext(project_path=tmp_path))
    plan = FixPlan(
        file_path=str(file_path),
        issue_type="FORMATTING",
        changes=[
            ChangeSpec(
                line_range=(1, 1),
                old_code="value = 1",
                new_code="value = 2  # noqa: B904",
                reason="Apply targeted lint suppression",
            )
        ],
        rationale="Targeted formatting fix",
        risk_level="low",
        validated_by="PlanningAgent",
    )

    result = agent.execute_fix_plan(plan)

    import asyncio

    fix_result = asyncio.run(result)
    assert fix_result.success is True
    assert file_path.read_text(encoding="utf-8") == "value = 2  # noqa: B904\n"


def test_apply_change_spec_falls_back_to_flexible_multiline_match(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    file_path.write_text(
        "try:\n"
        "    do_work()\n"
        "except ValueError as e:\n"
        "    raise HTTPException(\n"
        "        status_code=401,\n"
        "        detail='bad',\n"
        "    )\n",
        encoding="utf-8",
    )

    agent = FormattingAgent(AgentContext(project_path=tmp_path))
    change = ChangeSpec(
        line_range=(4, 7),
        old_code="raise HTTPException(\n    status_code=401,\n    detail='bad',\n)",
        new_code="raise HTTPException(\n    status_code=401,\n    detail='bad',\n) from e",
        reason="Add chaining",
    )

    updated = agent._apply_change_spec(file_path.read_text(encoding="utf-8"), change)

    assert updated is not None
    assert "from e" in updated


def test_apply_change_spec_falls_back_for_whitespace_variation(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    file_path.write_text(
        "@app.command()\n"
        "def shell(\n"
        "    ctx: typer.Context,\n"
        "    mode: str = 'lite',\n"
        ") -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    agent = FormattingAgent(AgentContext(project_path=tmp_path))
    change = ChangeSpec(
        line_range=(2, 5),
        old_code="def shell(\nctx: typer.Context,\nmode: str = 'lite',\n) -> None:",
        new_code="def shell(\n_ctx: typer.Context,\nmode: str = 'lite',\n) -> None:",
        reason="Rename unused argument",
    )

    updated = agent._apply_change_spec(file_path.read_text(encoding="utf-8"), change)

    assert updated is not None
    assert "_ctx: typer.Context" in updated
