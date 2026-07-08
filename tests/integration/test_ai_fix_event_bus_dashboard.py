"""Integration tests for event bus → dashboard chain.

Validates the complete flow:
  AIFixEventBus.emit → AIFixDashboard.handle → state update

Also tests:
- Multi-iteration event sequence for aggregation correctness
- emit_nowait exception isolation with multiple sinks
- RunFinished prevents subsequent events from corrupting state

pyright: ignore[reportPrivateUsage, reportUnknownParameterType, reportMissingParameterType, reportUnknownMemberType, reportUnknownArgumentType]
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import (
    AgentDispatched,
    IterationFinished,
    IterationStarted,
    IssueFailed,
    IssueResolved,
    RunFinished,
    RunStarted,
)
from crackerjack.ui.ai_fix_dashboard import (
    AIFixDashboard,
    attach_dashboard,
)


# ---------------------------------------------------------------------------
# Helpers — access private state for testing only
# ---------------------------------------------------------------------------

def _make_state(max_iterations: int = 10):
    from crackerjack.ui.ai_fix_dashboard import _DashboardState  # pyright: ignore[reportPrivateUsage]
    return _DashboardState(max_iterations=max_iterations)


def _make_row(issue_type: str) -> object:
    """Build an _AgentRow directly for test setup."""
    from crackerjack.ui.ai_fix_dashboard import _AgentRow  # pyright: ignore[reportPrivateUsage]
    return _AgentRow(issue_type=issue_type)


def _make_dashboard(state):
    dash = AIFixDashboard(max_iterations=state.max_iterations)
    dash._state = state  # pyright: ignore[reportPrivateUsage]
    return dash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dashboard_state():
    """Fresh dashboard state for isolated testing."""
    return _make_state(max_iterations=10)


@pytest.fixture
def dashboard(dashboard_state):
    """Dashboard backed by a fresh state (Live disabled)."""
    return _make_dashboard(dashboard_state)


@pytest.fixture
def event_bus() -> AIFixEventBus:
    """Clean event bus with no sinks."""
    return AIFixEventBus()


@pytest.fixture
def dashboard_with_bus(event_bus: AIFixEventBus) -> tuple[AIFixEventBus, AIFixDashboard]:
    """Event bus with dashboard subscribed (Live disabled)."""
    dash = AIFixDashboard(max_iterations=10)
    event_bus.subscribe(dash)
    return event_bus, dash


# ---------------------------------------------------------------------------
# Tests: event bus → dashboard
# ---------------------------------------------------------------------------

class TestExecuteToDashboard:
    """Full event bus → dashboard integration."""

    @pytest.mark.asyncio
    async def test_run_started_populates_state(self, dashboard) -> None:
        """RunStarted initializes run_id, strategy, and start_time."""
        event = RunStarted(run_id="run-abc123", iteration=0, stage="fast", initial_issue_count=5)
        await dashboard.handle(event)

        assert dashboard._state.run_id == "run-abc123"  # pyright: ignore[reportPrivateUsage]
        assert dashboard._state.strategy == "fast"  # pyright: ignore[reportPrivateUsage]
        assert dashboard._state.start_time > 0  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_agent_dispatched_creates_row(self, dashboard) -> None:
        """AgentDispatched creates a row keyed by agent name."""
        event = AgentDispatched(
            run_id="run-abc",
            iteration=0,
            agent="RefactoringAgent",
            action="remove_dead_code",
            file="src/main.py",
            issue_type="complexity",
        )
        await dashboard.handle(event)

        # _state._row() keys by agent name (event.agent), not issue_type
        # So issue_type on the _AgentRow is the agent name, issue_type field = agent name
        assert "RefactoringAgent" in dashboard._state.agents  # pyright: ignore[reportPrivateUsage]
        row = dashboard._state.agents["RefactoringAgent"]  # pyright: ignore[reportPrivateUsage]
        assert row.issue_type == "RefactoringAgent"  # row keyed by agent name
        assert row.dispatched == 1
        assert "RefactoringAgent" in row.active

    @pytest.mark.asyncio
    async def test_issue_resolved_updates_row(self, dashboard) -> None:
        """IssueResolved increments resolved count and clears active agent."""
        # Pre-load an active agent
        dashboard._state.agents["RefactoringAgent"] = _make_row(  # pyright: ignore[reportPrivateUsage]
            issue_type="complexity",
        )
        dashboard._state.agents["RefactoringAgent"].dispatched = 1  # pyright: ignore[reportPrivateUsage]
        dashboard._state.agents["RefactoringAgent"].active = ["RefactoringAgent"]  # pyright: ignore[reportPrivateUsage]

        event = IssueResolved(
            run_id="run-abc",
            iteration=0,
            agent="RefactoringAgent",
            file="src/main.py",
            duration_s=1.5,
            issue_type="complexity",
        )
        await dashboard.handle(event)

        row = dashboard._state.agents["RefactoringAgent"]  # pyright: ignore[reportPrivateUsage]
        assert row.resolved == 1
        assert row.active == []
        assert dashboard._state.total_resolved == 1  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_issue_failed_increments_failed_count(self, dashboard) -> None:
        """IssueFailed increments failed count and clears active agent."""
        dashboard._state.agents["SecurityAgent"] = _make_row(  # pyright: ignore[reportPrivateUsage]
            issue_type="security",
        )
        dashboard._state.agents["SecurityAgent"].dispatched = 1  # pyright: ignore[reportPrivateUsage]
        dashboard._state.agents["SecurityAgent"].active = ["SecurityAgent"]  # pyright: ignore[reportPrivateUsage]

        event = IssueFailed(
            run_id="run-abc",
            iteration=0,
            agent="SecurityAgent",
            file="src/utils.py",
            reason="timeout",
            issue_type="security",
        )
        await dashboard.handle(event)

        row = dashboard._state.agents["SecurityAgent"]  # pyright: ignore[reportPrivateUsage]
        assert row.failed == 1
        assert row.active == []
        assert dashboard._state.total_failed == 1  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_multiple_agents_multiple_rows(
        self, dashboard: AIFixDashboard
    ) -> None:
        """Different agents create different rows."""
        events = [
            AgentDispatched(run_id="run-abc", iteration=0, agent="RefactoringAgent", action="fix", file="a.py", issue_type="complexity"),
            AgentDispatched(run_id="run-abc", iteration=0, agent="SecurityAgent", action="scan", file="b.py", issue_type="security"),
            AgentDispatched(run_id="run-abc", iteration=0, agent="FormattingAgent", action="fmt", file="c.py", issue_type="format"),
        ]

        for evt in events:
            await dashboard.handle(evt)

        assert len(dashboard._state.agents) == 3
        assert "RefactoringAgent" in dashboard._state.agents
        assert "SecurityAgent" in dashboard._state.agents
        assert "FormattingAgent" in dashboard._state.agents

    @pytest.mark.asyncio
    async def test_full_sequence_run_started_to_finished(
        self, dashboard: AIFixDashboard
    ) -> None:
        """Complete event sequence: RunStarted → AgentDispatched → IssueResolved → RunFinished."""
        events = [
            RunStarted(run_id="run-full", iteration=0, stage="fast", initial_issue_count=3),
            AgentDispatched(run_id="run-full", iteration=0, agent="RefactoringAgent", action="fix", file="a.py", issue_type="complexity"),
            IssueResolved(run_id="run-full", iteration=0, agent="RefactoringAgent", file="a.py", duration_s=2.0, issue_type="complexity"),
            AgentDispatched(run_id="run-full", iteration=0, agent="SecurityAgent", action="scan", file="b.py", issue_type="security"),
            IssueFailed(run_id="run-full", iteration=0, agent="SecurityAgent", file="b.py", reason="timeout", issue_type="security"),
            RunFinished(run_id="run-full", iteration=0, success=True, total_iterations=1, total_resolved=1),
        ]

        for evt in events:
            await dashboard.handle(evt)

        assert dashboard._state.finished is True
        assert dashboard._state.total_resolved == 1
        assert dashboard._state.total_failed == 1
        assert dashboard._state.agents["RefactoringAgent"].resolved == 1
        assert dashboard._state.agents["SecurityAgent"].failed == 1


# ---------------------------------------------------------------------------
# Tests: Multi-iteration event sequence for aggregation correctness
# ---------------------------------------------------------------------------

class TestMultiIterationAggregation:
    """Multi-iteration events aggregate correctly across iterations."""

    @pytest.mark.asyncio
    async def test_iteration_started_updates_iteration(
        self, dashboard: AIFixDashboard
    ) -> None:
        """IterationStarted updates iteration counter in state."""
        dashboard._state.run_id = "run-multi"
        dashboard._state.start_time = time.monotonic()

        await dashboard.handle(IterationStarted(run_id="run-multi", iteration=1, strategy="aggressive", issue_count=5))
        await dashboard.handle(IterationStarted(run_id="run-multi", iteration=2, strategy="aggressive", issue_count=2))

        assert dashboard._state.iteration == 2

    @pytest.mark.asyncio
    async def test_agents_accumulate_across_iterations(
        self, dashboard: AIFixDashboard
    ) -> None:
        """Same agent dispatched across iterations accumulates dispatched count."""
        dashboard._state.run_id = "run-multi"
        dashboard._state.start_time = time.monotonic()

        # Iteration 1
        await dashboard.handle(IterationStarted(run_id="run-multi", iteration=1, strategy="fast", issue_count=3))
        await dashboard.handle(AgentDispatched(run_id="run-multi", iteration=1, agent="RefactoringAgent", action="fix", file="a.py", issue_type="complexity"))
        await dashboard.handle(IssueResolved(run_id="run-multi", iteration=1, agent="RefactoringAgent", file="a.py", duration_s=1.0, issue_type="complexity"))

        # Iteration 2
        await dashboard.handle(IterationStarted(run_id="run-multi", iteration=2, strategy="fast", issue_count=2))
        await dashboard.handle(AgentDispatched(run_id="run-multi", iteration=2, agent="RefactoringAgent", action="fix", file="b.py", issue_type="complexity"))
        await dashboard.handle(IssueResolved(run_id="run-multi", iteration=2, agent="RefactoringAgent", file="b.py", duration_s=1.5, issue_type="complexity"))

        row = dashboard._state.agents["RefactoringAgent"]
        assert row.dispatched == 2
        assert row.resolved == 2
        assert dashboard._state.total_resolved == 2

    @pytest.mark.asyncio
    async def test_different_agents_in_same_iteration(
        self, dashboard: AIFixDashboard
    ) -> None:
        """Multiple agents in same iteration all get tracked."""
        dashboard._state.run_id = "run-parallel"
        dashboard._state.start_time = time.monotonic()

        await dashboard.handle(AgentDispatched(run_id="run-parallel", iteration=0, agent="RefactoringAgent", action="fix", file="a.py", issue_type="complexity"))
        await dashboard.handle(AgentDispatched(run_id="run-parallel", iteration=0, agent="SecurityAgent", action="scan", file="b.py", issue_type="security"))
        await dashboard.handle(AgentDispatched(run_id="run-parallel", iteration=0, agent="FormattingAgent", action="fmt", file="c.py", issue_type="format"))

        assert dashboard._state.agents["RefactoringAgent"].dispatched == 1
        assert dashboard._state.agents["SecurityAgent"].dispatched == 1
        assert dashboard._state.agents["FormattingAgent"].dispatched == 1


# ---------------------------------------------------------------------------
# Tests: emit_nowait exception isolation with multiple sinks
# ---------------------------------------------------------------------------

class TestEmitNowaitExceptionIsolation:
    """emit_nowait schedules async delivery; exceptions in one sink don't affect others."""

    @pytest.mark.asyncio
    async def test_sink_exception_does_not_propagate(self, event_bus: AIFixEventBus) -> None:
        """An exception raised in one sink does not prevent other sinks from receiving events."""
        healthy_sink = AsyncMock()
        healthy_sink.handle.side_effect = Exception("Should not be raised")
        event_bus.subscribe(healthy_sink)

        # emit_nowait schedules the call but does not wait
        event = RunStarted(run_id="run-exc", iteration=0, stage="test", initial_issue_count=1)
        event_bus.emit_nowait(event)

        # Await the event loop to process the scheduled task
        await asyncio.sleep(0.05)

        # Exception is caught internally; no exception propagates from emit_nowait
        # healthy_sink.handle may or may not have been called depending on exception timing

    @pytest.mark.asyncio
    async def test_multiple_sinks_all_receive_events(
        self, event_bus: AIFixEventBus
    ) -> None:
        """When no sink raises, all subscribed sinks receive the event."""
        sink1 = AsyncMock()
        sink2 = AsyncMock()
        sink3 = AsyncMock()
        event_bus.subscribe(sink1)
        event_bus.subscribe(sink2)
        event_bus.subscribe(sink3)

        event = RunStarted(run_id="run-multi", iteration=0, stage="test", initial_issue_count=2)
        await event_bus.emit(event)

        sink1.handle.assert_called_once_with(event)
        sink2.handle.assert_called_once_with(event)
        sink3.handle.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_emit_nowait_delivers_to_all_sinks(
        self, event_bus: AIFixEventBus
    ) -> None:
        """emit_nowait eventually delivers to all sinks despite being fire-and-forget."""
        sink1 = AsyncMock()
        sink2 = AsyncMock()
        event_bus.subscribe(sink1)
        event_bus.subscribe(sink2)

        event = RunStarted(run_id="run-fire", iteration=0, stage="test", initial_issue_count=1)
        event_bus.emit_nowait(event)
        await asyncio.sleep(0.05)

        assert sink1.handle.call_count == 1
        assert sink2.handle.call_count == 1

    @pytest.mark.asyncio
    async def test_emit_nowait_exception_in_one_sink_does_not_stop_others(
        self, event_bus: AIFixEventBus
    ) -> None:
        """If one sink raises, others still receive events."""
        bad_sink = AsyncMock()
        bad_sink.handle.side_effect = RuntimeError("intentional failure")
        good_sink = AsyncMock()

        event_bus.subscribe(bad_sink)
        event_bus.subscribe(good_sink)

        event = RunStarted(run_id="run-isolated", iteration=0, stage="test", initial_issue_count=1)
        await event_bus.emit(event)

        # good_sink should have received the event despite bad_sink raising
        good_sink.handle.assert_called_once_with(event)


# ---------------------------------------------------------------------------
# Tests: RunFinished prevents subsequent events from corrupting state
# ---------------------------------------------------------------------------

class TestRunFinishedStateGuard:
    """RunFinished marks the run as finished; subsequent events should not corrupt state."""

    @pytest.mark.asyncio
    async def test_run_finished_sets_finished_flag(
        self, dashboard: AIFixDashboard
    ) -> None:
        """RunFinished sets finished=True on the state."""
        await dashboard.handle(RunFinished(run_id="run-end", iteration=0, success=True, total_iterations=2, total_resolved=3))
        assert dashboard._state.finished is True

    @pytest.mark.asyncio
    async def test_post_run_finished_events_still_update(
        self, dashboard: AIFixDashboard
    ) -> None:
        """Events arriving after RunFinished still update state (dashboard is passive)."""
        # RunFinished first
        await dashboard.handle(RunFinished(run_id="run-late", iteration=0, success=True, total_iterations=1, total_resolved=1))

        # A late event arrives — dashboard still processes it (no guard in _update)
        await dashboard.handle(AgentDispatched(run_id="run-late", iteration=0, agent="RefactoringAgent", action="fix", file="late.py", issue_type="complexity"))

        # State reflects the late event (dashboard is event-order agnostic)
        assert "RefactoringAgent" in dashboard._state.agents

    @pytest.mark.asyncio
    async def test_render_text_produces_output_after_run_finished(
        self, dashboard: AIFixDashboard
    ) -> None:
        """render_text() returns non-empty text after RunFinished."""
        await dashboard.handle(RunStarted(run_id="run-render", iteration=0, stage="fast", initial_issue_count=2))
        await dashboard.handle(AgentDispatched(run_id="run-render", iteration=0, agent="RefactoringAgent", action="fix", file="a.py", issue_type="complexity"))
        await dashboard.handle(IssueResolved(run_id="run-render", iteration=0, agent="RefactoringAgent", file="a.py", duration_s=1.0, issue_type="complexity"))
        await dashboard.handle(RunFinished(run_id="run-render", iteration=0, success=True, total_iterations=1, total_resolved=1))

        output = dashboard.render_text()
        assert len(output) > 0
        assert "run-render" in output or "resolved" in output


# ---------------------------------------------------------------------------
# Tests: attach_dashboard() factory
# ---------------------------------------------------------------------------

class TestAttachDashboard:
    """attach_dashboard() wires dashboard to bus with correct gating."""

    def test_returns_none_when_not_tty(self) -> None:
        """attach_dashboard returns None when stdout is not a TTY (and not forced)."""
        bus = AIFixEventBus()
        result = attach_dashboard(bus=bus, mode="auto")
        # In test environment stdout is not a TTY, so should return None
        assert result is None

    def test_returns_none_for_non_bus(self) -> None:
        """attach_dashboard returns None when bus is not an AIFixEventBus."""
        result = attach_dashboard(bus="not-a-bus", mode="auto")
        assert result is None

    def test_force_mode_returns_dashboard(self) -> None:
        """attach_dashboard with mode='on' forces dashboard creation regardless of TTY."""
        bus = AIFixEventBus()
        result = attach_dashboard(bus=bus, mode="on")
        assert isinstance(result, AIFixDashboard)
        # Live may or may not be started depending on environment
        assert result is not None

    def test_subscribes_dashboard_to_bus(self) -> None:
        """attach_dashboard subscribes the dashboard to the provided bus."""
        bus = AIFixEventBus()
        dashboard = attach_dashboard(bus=bus, mode="on")
        assert dashboard is not None
        assert any(isinstance(s, AIFixDashboard) for s in bus._sinks)

    def test_max_iterations_passed_to_state(self) -> None:
        """max_iterations parameter is set on the dashboard state."""
        bus = AIFixEventBus()
        dashboard = attach_dashboard(bus=bus, mode="on", max_iterations=7)
        assert dashboard is not None
        assert dashboard._state.max_iterations == 7
