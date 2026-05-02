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
