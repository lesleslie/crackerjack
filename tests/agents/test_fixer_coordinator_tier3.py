"""Tests for the tier-3 wiring on ``FixerCoordinator``.

The full integration (auto-routing tier-3 diagnostics inside
``execute_plans``) is a follow-up PR. These tests pin the
minimum-viable surface:

* ``attach_iterative_agent`` registers the agent.
* ``route_tier3_plan`` calls the agent and produces a FixResult.
* Calling without an attached agent returns None (no exception).
* Existing FixerCoordinator construction is unaffected (the agent
  attribute is optional).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from crackerjack.agents.fixer_coordinator import FixerCoordinator
from crackerjack.agents.iterative_fix_agent import (
    FixOutcome,
    InMemorySkillStore,
    IterativeFixAgent,
    LocalClaudeSubprocess,
)
from crackerjack.models.fix_plan import ChangeSpec, FixPlan

# ---------------------------------------------------------------------------
# Construction regression
# ---------------------------------------------------------------------------


class TestFixerCoordinatorUnchanged:
    def test_constructs_without_iterative_agent(self) -> None:
        # Existing callers should not break.
        coord = FixerCoordinator()
        assert coord.iterative_agent is None

    def test_attach_iterative_agent_registers(self) -> None:
        coord = FixerCoordinator()
        agent = IterativeFixAgent(
            pool=LocalClaudeSubprocess(),
            skill_store=InMemorySkillStore(),
        )
        coord.attach_iterative_agent(agent)
        assert coord.iterative_agent is agent


# ---------------------------------------------------------------------------
# route_tier3_plan
# ---------------------------------------------------------------------------


class TestRouteTier3Plan:
    def _make_plan(self, tmp_path: Path) -> FixPlan:
        target = tmp_path / "foo.py"
        target.write_text("x = 1\n")
        return FixPlan(
            file_path=str(target),
            issue_type="unsupported-attribute",
            risk_level="low",
            validated_by="system",
            rationale="Attribute `lower` is not defined on `None`",
            issue_message="Attribute `lower` is not defined on `None`",
            changes=[
                ChangeSpec(
                    line_range=(10, 10),
                    old_code="name.lower()",
                    new_code="(name or '').lower()",
                    reason="None-narrow",
                ),
            ],
        )

    def test_returns_none_when_no_agent_attached(self, tmp_path: Path) -> None:
        coord = FixerCoordinator()
        plan = self._make_plan(tmp_path)
        result = asyncio.run(coord.route_tier3_plan(plan))
        assert result is None

    def test_returns_fixresult_when_agent_succeeds(self, tmp_path: Path) -> None:
        # Use a stub agent that always succeeds.
        coord = FixerCoordinator()
        agent = MagicMock()
        agent.fix_file.return_value = FixOutcome(
            success=True,
            dispatched_to_pool=True,
            skill_recorded=True,
            message="stub-success",
        )
        coord.attach_iterative_agent(agent)

        plan = self._make_plan(tmp_path)
        result = asyncio.run(coord.route_tier3_plan(plan))
        assert result is not None
        assert result.success is True
        assert result.files_modified == [str(tmp_path / "foo.py")]
        assert agent.fix_file.called

    def test_returns_fixresult_with_remaining_issues_on_failure(
        self, tmp_path: Path
    ) -> None:
        coord = FixerCoordinator()
        agent = MagicMock()
        agent.fix_file.return_value = FixOutcome(
            success=False, message="dispatch failed: boom"
        )
        coord.attach_iterative_agent(agent)

        plan = self._make_plan(tmp_path)
        result = asyncio.run(coord.route_tier3_plan(plan))
        assert result is not None
        assert result.success is False
        assert result.files_modified == []
        assert "boom" in result.remaining_issues[0]

    def test_synthesizes_diagnostic_when_plan_has_no_changes(
        self, tmp_path: Path
    ) -> None:
        # A plan with no ChangeSpecs should still produce a synthetic
        # diagnostic so the agent at least gets the metadata.
        coord = FixerCoordinator()
        agent = MagicMock()
        agent.fix_file.return_value = FixOutcome(success=True, message="ok")
        coord.attach_iterative_agent(agent)
        plan = FixPlan(
            file_path=str(tmp_path / "foo.py"),
            issue_type="unsupported-attribute",
            risk_level="low",
            validated_by="system",
            rationale="r",
            changes=[],
        )
        asyncio.run(coord.route_tier3_plan(plan))
        diagnostics = agent.fix_file.call_args[0][1]
        assert len(diagnostics) == 1

    def test_passes_tydiagnostic_list_to_agent(self, tmp_path: Path) -> None:
        coord = FixerCoordinator()
        agent = MagicMock()
        agent.fix_file.return_value = FixOutcome(success=True, message="ok")
        coord.attach_iterative_agent(agent)

        plan = self._make_plan(tmp_path)
        asyncio.run(coord.route_tier3_plan(plan))

        agent.fix_file.assert_called_once()
        call_args = agent.fix_file.call_args
        # First positional arg is the target path.
        assert call_args[0][0] == tmp_path / "foo.py"
        # Second arg is the diagnostics list.
        diagnostics = call_args[0][1]
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "unsupported-attribute"
        assert diagnostics[0].line == 10


# ---------------------------------------------------------------------------
# Auto-routing in _execute_single_plan
# ---------------------------------------------------------------------------


class TestExecuteSinglePlanTier3Fallback:
    """When regular fixers don't produce an effective result and the
    issue type is in TIER3_ISSUE_TYPES, the coordinator should
    auto-route to the attached iterative_agent.
    """

    def _make_plan(
        self, tmp_path: Path, issue_type: str = "unsupported-attribute"
    ) -> FixPlan:
        target = tmp_path / "foo.py"
        target.write_text("x = 1\n")
        return FixPlan(
            file_path=str(target),
            issue_type=issue_type,
            risk_level="low",
            validated_by="system",
            rationale="r",
            issue_message="m",
            changes=[
                ChangeSpec(
                    line_range=(10, 10),
                    old_code="a",
                    new_code="b",
                    reason="r",
                ),
            ],
        )

    def test_no_agent_attached_returns_last_result(self, tmp_path: Path) -> None:
        # Without an iterative_agent attached, we don't try tier-3.
        coord = FixerCoordinator()
        plan = self._make_plan(tmp_path)
        # TYPE_ERROR is in candidate fixers (TypeErrorSpecialistAgent),
        # but that agent won't be registered in this minimal test setup,
        # so no regular fixer matches either. Without tier-3, the result
        # is the "no fixer" failure.
        result = asyncio.run(coord._execute_single_plan(plan))
        assert result.success is False

    def test_tier3_runs_when_regular_fixer_fails_and_type_eligible(
        self, tmp_path: Path
    ) -> None:
        coord = FixerCoordinator()
        # Attach an agent that always succeeds.
        agent = MagicMock()
        agent.fix_file.return_value = FixOutcome(
            success=True, dispatched_to_pool=True, message="tier3-ok"
        )
        coord.attach_iterative_agent(agent)

        plan = self._make_plan(tmp_path, issue_type="unsupported-attribute")
        result = asyncio.run(coord._execute_single_plan(plan))
        assert result.success is True
        assert agent.fix_file.called

    def test_tier3_skipped_for_non_tier3_issue_type(self, tmp_path: Path) -> None:
        # Issue type not in TIER3_ISSUE_TYPES → don't route to tier-3
        # even if an agent is attached.
        coord = FixerCoordinator()
        agent = MagicMock()
        coord.attach_iterative_agent(agent)

        plan = self._make_plan(tmp_path, issue_type="some-other-type")
        asyncio.run(coord._execute_single_plan(plan))
        agent.fix_file.assert_not_called()

    def test_tier3_failure_returns_no_fixer_result(self, tmp_path: Path) -> None:
        # When tier-3 also fails, the user sees the regular-fixer
        # fallback (or the no-fixer message).
        coord = FixerCoordinator()
        agent = MagicMock()
        agent.fix_file.return_value = FixOutcome(
            success=False, message="dispatch failed"
        )
        coord.attach_iterative_agent(agent)

        plan = self._make_plan(tmp_path, issue_type="unsupported-attribute")
        result = asyncio.run(coord._execute_single_plan(plan))
        # Either "no fixer" or agent-reported failure — both acceptable
        # as long as we don't claim success.
        assert result.success is False
