from __future__ import annotations

import pytest
from rich.console import Console

from crackerjack.core.ai_fix_events import (
    FixSessionFinished,
    FixSessionStarted,
    TierTransitioned,
)
from crackerjack.ui.ai_fix_dashboard import AIFixDashboard


RUN_ID = "2026-07-07-1200-abcd"


def make_dashboard() -> AIFixDashboard:
    console = Console(force_terminal=True, width=80, highlight=False)
    return AIFixDashboard(console=console, max_iterations=5)


class TestFixSessionStartedRendering:
    @pytest.mark.asyncio
    async def test_session_started_increments_session_count(self) -> None:
        d = make_dashboard()
        await d.handle(
            FixSessionStarted(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
            )
        )
        assert d._state.session_started_count == 1

    @pytest.mark.asyncio
    async def test_session_started_accumulates(self) -> None:
        d = make_dashboard()
        for i in range(3):
            await d.handle(
                FixSessionStarted(
                    run_id=RUN_ID,
                    iteration=0,
                    issue_signature=f"sig-{i}",
                    file=f"f{i}.py",
                )
            )
        assert d._state.session_started_count == 3


class TestFixSessionFinishedRendering:
    @pytest.mark.asyncio
    async def test_session_finished_increments_finished_count(self) -> None:
        d = make_dashboard()
        await d.handle(
            FixSessionFinished(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
                success=True,
            )
        )
        assert d._state.session_finished_count == 1

    @pytest.mark.asyncio
    async def test_session_finished_counts_no_ops(self) -> None:
        d = make_dashboard()
        await d.handle(
            FixSessionFinished(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
                success=False,
                no_op_count=2,
            )
        )
        await d.handle(
            FixSessionFinished(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-2",
                file="b.py",
                success=True,
                no_op_count=0,
            )
        )
        assert d._state.total_no_op_count == 2


class TestTierTransitionedRendering:
    @pytest.mark.asyncio
    async def test_tier_transition_does_not_crash(self) -> None:
        d = make_dashboard()
        # TierTransitioned is rendered but doesn't change state; it must
        # not raise when the dashboard receives it.
        await d.handle(
            TierTransitioned(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                from_tier=1,
                to_tier=2,
                reason="escalate",
                file="a.py",
            )
        )
        # Should not raise


class TestRenderWithNewEvents:
    @pytest.mark.asyncio
    async def test_render_text_includes_session_started_count(self) -> None:
        d = make_dashboard()
        for i in range(2):
            await d.handle(
                FixSessionStarted(
                    run_id=RUN_ID,
                    iteration=0,
                    issue_signature=f"sig-{i}",
                    file=f"f{i}.py",
                )
            )
        text = d.render_text()
        # The dashboard should expose the session count somewhere
        assert "2" in text

    @pytest.mark.asyncio
    async def test_render_text_includes_no_op_count(self) -> None:
        d = make_dashboard()
        await d.handle(
            FixSessionFinished(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
                success=False,
                no_op_count=7,
            )
        )
        text = d.render_text()
        assert "no-op" in text.lower() or "7" in text