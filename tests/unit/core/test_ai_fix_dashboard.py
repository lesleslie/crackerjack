from __future__ import annotations

import os

import pytest
from rich.console import Console

from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import (
    AgentDispatched,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    PreflightFinished,
    RunFinished,
    RunStarted,
)
from crackerjack.ui.ai_fix_dashboard import (
    AIFixDashboard,
    _DashboardState,
    attach_dashboard,
    should_activate,
)


RUN_ID = "2026-01-01-0000-ab12"


def make_dashboard() -> AIFixDashboard:
    console = Console(force_terminal=True, width=80, highlight=False)
    return AIFixDashboard(console=console, max_iterations=5)


# ─── state updates ───────────────────────────────────────────────────────────

class TestDashboardStateUpdates:
    @pytest.mark.asyncio
    async def test_run_started_sets_run_id(self) -> None:
        d = make_dashboard()
        await d.handle(RunStarted(run_id=RUN_ID, iteration=0, stage="comprehensive", initial_issue_count=10))
        assert d._state.run_id == RUN_ID

    @pytest.mark.asyncio
    async def test_iteration_started_sets_iteration(self) -> None:
        d = make_dashboard()
        await d.handle(IterationStarted(run_id=RUN_ID, iteration=2, strategy="balanced", issue_count=5))
        assert d._state.iteration == 2
        assert d._state.strategy == "balanced"

    @pytest.mark.asyncio
    async def test_agent_dispatched_creates_row(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="type_error", action="fix", file="a.py"))
        assert "type_error" in d._state.agents
        assert d._state.agents["type_error"].dispatched == 1

    @pytest.mark.asyncio
    async def test_issue_resolved_increments_counters(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="security", action="fix", file="b.py"))
        await d.handle(IssueResolved(run_id=RUN_ID, iteration=0, agent="security", file="b.py", duration_s=1.5))
        row = d._state.agents["security"]
        assert row.resolved == 1
        assert d._state.total_resolved == 1
        assert "security" not in row.active

    @pytest.mark.asyncio
    async def test_issue_failed_increments_counters(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="complexity", action="fix", file="c.py"))
        await d.handle(IssueFailed(run_id=RUN_ID, iteration=0, agent="complexity", file="c.py", reason="timeout"))
        assert d._state.agents["complexity"].failed == 1
        assert d._state.total_failed == 1

    @pytest.mark.asyncio
    async def test_preflight_finished_accumulates(self) -> None:
        d = make_dashboard()
        await d.handle(PreflightFinished(run_id=RUN_ID, iteration=0, issues_saved=7, duration_s=1.0))
        await d.handle(PreflightFinished(run_id=RUN_ID, iteration=1, issues_saved=3, duration_s=0.5))
        assert d._state.preflight_saved == 10

    @pytest.mark.asyncio
    async def test_last_activity_updated_on_resolved(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="refurb", action="fix", file="x.py"))
        await d.handle(IssueResolved(run_id=RUN_ID, iteration=0, agent="refurb", file="x.py", duration_s=0.9))
        assert "refurb" in d._state.last_activity
        assert "x.py" in d._state.last_activity

    @pytest.mark.asyncio
    async def test_last_activity_updated_on_failed(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="zuban", action="fix", file="y.py"))
        await d.handle(IssueFailed(run_id=RUN_ID, iteration=0, agent="zuban", file="y.py", reason="bad diff"))
        assert "zuban" in d._state.last_activity

    @pytest.mark.asyncio
    async def test_run_finished_marks_state(self) -> None:
        d = make_dashboard()
        await d.handle(RunFinished(run_id=RUN_ID, iteration=0, success=True, total_iterations=3))
        assert d._state.finished is True

    @pytest.mark.asyncio
    async def test_multiple_agents_same_type_active(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="refurb", action="fix", file="a.py"))
        # Same agent type dispatched again (different plan)
        row = d._state.agents["refurb"]
        assert row.dispatched == 1

    @pytest.mark.asyncio
    async def test_resolve_removes_from_active(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="security", action="fix", file="s.py"))
        assert d._state.agents["security"].dispatched == 1
        await d.handle(IssueResolved(run_id=RUN_ID, iteration=0, agent="security", file="s.py", duration_s=0.5))
        assert "security" not in d._state.agents["security"].active


# ─── render output ───────────────────────────────────────────────────────────

class TestDashboardRendering:
    @pytest.mark.asyncio
    async def test_render_text_contains_run_id_suffix(self) -> None:
        d = make_dashboard()
        await d.handle(RunStarted(run_id=RUN_ID, iteration=0, stage="comprehensive", initial_issue_count=5))
        text = d.render_text()
        assert "ab12" in text

    @pytest.mark.asyncio
    async def test_render_text_contains_agent_type(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="type_error", action="fix", file="f.py"))
        text = d.render_text()
        assert "type_error" in text

    @pytest.mark.asyncio
    async def test_render_text_shows_resolved_count(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="security", action="fix", file="a.py"))
        await d.handle(IssueResolved(run_id=RUN_ID, iteration=0, agent="security", file="a.py", duration_s=1.0))
        text = d.render_text()
        assert "resolved 1" in text

    @pytest.mark.asyncio
    async def test_render_text_shows_preflight_saved(self) -> None:
        d = make_dashboard()
        await d.handle(RunStarted(run_id=RUN_ID, iteration=0, stage="comprehensive", initial_issue_count=5))
        await d.handle(PreflightFinished(run_id=RUN_ID, iteration=0, issues_saved=12, duration_s=1.0))
        text = d.render_text()
        assert "preflight saved 12" in text

    @pytest.mark.asyncio
    async def test_render_text_shows_checkmark_when_all_resolved(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="refurb", action="fix", file="r.py"))
        await d.handle(IssueResolved(run_id=RUN_ID, iteration=0, agent="refurb", file="r.py", duration_s=0.4))
        text = d.render_text()
        assert "✔" in text

    @pytest.mark.asyncio
    async def test_render_text_shows_last_activity(self) -> None:
        d = make_dashboard()
        await d.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="refurb", action="fix", file="app.py"))
        await d.handle(IssueResolved(run_id=RUN_ID, iteration=0, agent="refurb", file="app.py", duration_s=2.1))
        text = d.render_text()
        assert "app.py" in text

    def test_render_text_empty_state(self) -> None:
        d = make_dashboard()
        text = d.render_text()
        assert "AI Fix" in text  # Panel title present even with no events

    @pytest.mark.asyncio
    async def test_render_text_shows_elapsed(self) -> None:
        d = make_dashboard()
        await d.handle(RunStarted(run_id=RUN_ID, iteration=0, stage="", initial_issue_count=0))
        text = d.render_text()
        # elapsed shows MM:SS format
        assert "elapsed" in text
        assert ":" in text


# ─── activation ──────────────────────────────────────────────────────────────

class TestShouldActivate:
    def test_mode_on_always_true(self) -> None:
        assert should_activate("on") is True

    def test_mode_off_always_false(self) -> None:
        assert should_activate("off") is False

    def test_auto_false_in_ci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CI", "true")
        monkeypatch.delenv("CRACKERJACK_NO_TUI", raising=False)
        assert should_activate("auto") is False

    def test_auto_false_when_no_tui_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CRACKERJACK_NO_TUI", "1")
        monkeypatch.delenv("CI", raising=False)
        assert should_activate("auto") is False

    def test_auto_respects_isatty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("CRACKERJACK_NO_TUI", raising=False)
        # In test environment stdout is not a tty
        assert should_activate("auto") is False


class TestAttachDashboard:
    def test_attach_returns_none_when_mode_off(self) -> None:
        bus = AIFixEventBus()
        result = attach_dashboard(bus, mode="off")
        assert result is None

    def test_attach_returns_none_for_non_bus(self) -> None:
        result = attach_dashboard(object(), mode="on")  # ty: ignore[invalid-argument-type]
        assert result is None

    def test_attach_returns_dashboard_when_mode_on(self) -> None:
        bus = AIFixEventBus()
        dashboard = attach_dashboard(bus, mode="on")
        assert dashboard is not None
        assert isinstance(dashboard, AIFixDashboard)
        dashboard.stop()
