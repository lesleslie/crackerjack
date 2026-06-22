from __future__ import annotations

import asyncio
import re

import pytest

from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import (
    AIFixEvent,
    AgentDispatched,
    RunStarted,
    RunFinished,
)


class CaptureSink:
    def __init__(self) -> None:
        self.received: list[AIFixEvent] = []

    async def handle(self, event: AIFixEvent) -> None:
        self.received.append(event)


class ErrorSink:
    async def handle(self, event: AIFixEvent) -> None:
        raise ValueError("sink exploded")


class TestAIFixEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self) -> None:
        bus = AIFixEventBus()
        sink = CaptureSink()
        bus.subscribe(sink)
        event = RunStarted(run_id="r", iteration=0)
        await bus.emit(event)
        assert sink.received == [event]

    @pytest.mark.asyncio
    async def test_multiple_sinks_all_receive(self) -> None:
        bus = AIFixEventBus()
        sinks = [CaptureSink(), CaptureSink()]
        for s in sinks:
            bus.subscribe(s)
        event = RunStarted(run_id="r", iteration=0)
        await bus.emit(event)
        for s in sinks:
            assert len(s.received) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        bus = AIFixEventBus()
        sink = CaptureSink()
        bus.subscribe(sink)
        bus.unsubscribe(sink)
        await bus.emit(RunStarted(run_id="r", iteration=0))
        assert sink.received == []

    @pytest.mark.asyncio
    async def test_faulty_sink_does_not_stop_others(self) -> None:
        bus = AIFixEventBus()
        bad = ErrorSink()
        good = CaptureSink()
        bus.subscribe(bad)
        bus.subscribe(good)
        event = RunStarted(run_id="r", iteration=0)
        await bus.emit(event)
        assert good.received == [event]

    @pytest.mark.asyncio
    async def test_emit_nowait_delivers_event(self) -> None:
        bus = AIFixEventBus()
        sink = CaptureSink()
        bus.subscribe(sink)
        event = RunStarted(run_id="r", iteration=0)
        bus.emit_nowait(event)
        await asyncio.sleep(0)
        assert sink.received == [event]

    def test_emit_nowait_noop_outside_event_loop(self) -> None:
        bus = AIFixEventBus()
        sink = CaptureSink()
        bus.subscribe(sink)
        # Should not raise even when no loop is running
        bus.emit_nowait(RunStarted(run_id="r", iteration=0))

    def test_new_run_id_format(self) -> None:
        run_id = AIFixEventBus.new_run_id()
        pattern = r"^\d{4}-\d{2}-\d{2}-\d{4}-[0-9a-f]{4}$"
        assert re.match(pattern, run_id), f"Unexpected run_id format: {run_id!r}"

    def test_new_run_id_unique(self) -> None:
        ids = {AIFixEventBus.new_run_id() for _ in range(20)}
        # UUIDs ensure uniqueness; at minimum all 20 should differ
        assert len(ids) == 20

    @pytest.mark.asyncio
    async def test_emit_order_preserved(self) -> None:
        bus = AIFixEventBus()
        sink = CaptureSink()
        bus.subscribe(sink)
        events = [
            RunStarted(run_id="r", iteration=0),
            RunFinished(run_id="r", iteration=0),
        ]
        for e in events:
            await bus.emit(e)
        assert sink.received == events


@pytest.mark.unit
class TestTask11EventFields:
    def test_run_started_includes_model_name(self) -> None:
        """RunStarted must have model_name and provider fields."""
        event = RunStarted(
            run_id="r",
            iteration=0,
            model_name="MiniMax-M3",
            provider="minimax",
        )
        assert event.model_name == "MiniMax-M3"
        assert event.provider == "minimax"

    def test_next_fix_task_id_increments_sequentially(self) -> None:
        """next_fix_task_id() returns fix-0000, fix-0001, fix-0002 sequentially."""
        bus = AIFixEventBus()
        ids = [bus.next_fix_task_id() for _ in range(3)]
        assert ids == ["fix-0000", "fix-0001", "fix-0002"]

    def test_next_fix_task_id_resets_per_instance(self) -> None:
        """Each AIFixEventBus instance starts its own counter at 0."""
        bus1 = AIFixEventBus()
        bus2 = AIFixEventBus()
        assert bus1.next_fix_task_id() == "fix-0000"
        assert bus2.next_fix_task_id() == "fix-0000"

    def test_agent_dispatched_includes_fix_task_id(self) -> None:
        """AgentDispatched must carry fix_task_id, phase, attempt, max_attempts."""
        event = AgentDispatched(
            run_id="r",
            iteration=0,
            fix_task_id="fix-0003",
            phase="applying",
            attempt=1,
            max_attempts=3,
        )
        assert event.fix_task_id == "fix-0003"
        assert event.phase == "applying"
        assert event.attempt == 1
        assert event.max_attempts == 3

    def test_phase_changed_event_exists(self) -> None:
        """PhaseChanged dataclass must exist in ai_fix_events."""
        from crackerjack.core.ai_fix_events import PhaseChanged

        event = PhaseChanged(
            run_id="r",
            iteration=0,
            fix_task_id="fix-0001",
            old_phase="applying",
            new_phase="validating",
        )
        assert event.old_phase == "applying"
        assert event.new_phase == "validating"
