from __future__ import annotations

import asyncio
import re

import pytest

from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import AIFixEvent, RunStarted, RunFinished


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
