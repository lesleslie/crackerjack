"""Tests for ai_fix_event_bus module."""

import asyncio
from typing import Protocol
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.ai_fix_event_bus import AIFixEventBus, Sink
from crackerjack.core.ai_fix_events import (
    AIFixEvent,
    RunStarted,
    IterationStarted,
    RunFinished,
)


class SinkImpl(Protocol):
    """Protocol for sink testing."""
    async def handle(self, event: AIFixEvent) -> None: ...


class TestAIFixEventBus:
    """Tests for AIFixEventBus class."""

    def test_init(self) -> None:
        """Test bus initialization."""
        bus = AIFixEventBus()
        assert bus._sinks == []

    def test_subscribe(self) -> None:
        """Test subscribing a sink to the bus."""
        bus = AIFixEventBus()
        mock_sink = MagicMock(spec=Sink)
        bus.subscribe(mock_sink)
        assert mock_sink in bus._sinks

    def test_unsubscribe(self) -> None:
        """Test unsubscribing a sink from the bus."""
        bus = AIFixEventBus()
        mock_sink = MagicMock(spec=Sink)
        bus.subscribe(mock_sink)
        bus.unsubscribe(mock_sink)
        assert mock_sink not in bus._sinks

    def test_unsubscribe_not_subscribed(self) -> None:
        """Test unsubscribing a sink that was never subscribed."""
        bus = AIFixEventBus()
        mock_sink = MagicMock(spec=Sink)
        # Should not raise
        bus.unsubscribe(mock_sink)

    @pytest.mark.asyncio
    async def test_emit_calls_handle_on_all_sinks(self) -> None:
        """Test that emit calls handle on all subscribed sinks."""
        bus = AIFixEventBus()
        mock_sink1 = AsyncMock(spec=Sink)
        mock_sink2 = AsyncMock(spec=Sink)
        bus.subscribe(mock_sink1)
        bus.subscribe(mock_sink2)

        event = RunStarted(run_id="test-123", iteration=1, stage="test", initial_issue_count=5)
        await bus.emit(event)

        mock_sink1.handle.assert_called_once_with(event)
        mock_sink2.handle.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_emit_handles_sink_exception(self) -> None:
        """Test that emit continues even if a sink raises an exception."""
        bus = AIFixEventBus()
        mock_sink1 = AsyncMock(spec=Sink)
        mock_sink2 = AsyncMock(spec=Sink)
        mock_sink2.handle.side_effect = Exception("Sink error")
        bus.subscribe(mock_sink1)
        bus.subscribe(mock_sink2)

        event = RunStarted(run_id="test-123", iteration=1)
        # Should not raise
        await bus.emit(event)

        mock_sink1.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_empty_sinks(self) -> None:
        """Test emit with no sinks subscribed."""
        bus = AIFixEventBus()
        event = RunStarted(run_id="test-123", iteration=1)
        # Should not raise
        await bus.emit(event)

    def test_emit_nowait_no_loop(self) -> None:
        """Test emit_nowait when there's no running event loop."""
        bus = AIFixEventBus()
        event = RunStarted(run_id="test-123", iteration=1)
        # Should silently no-op
        bus.emit_nowait(event)

    def test_emit_nowait_with_loop(self) -> None:
        """Test emit_nowait schedules task in running event loop."""
        bus = AIFixEventBus()
        mock_sink = AsyncMock(spec=Sink)
        bus.subscribe(mock_sink)
        event = RunStarted(run_id="test-123", iteration=1)

        async def run_test():
            bus.emit_nowait(event)
            await asyncio.sleep(0.01)  # Give task time to run

        asyncio.run(run_test())

        # Sink should have been called
        assert mock_sink.handle.called

    @pytest.mark.asyncio
    async def test_emit_nowait_concurrent(self) -> None:
        """Test emit_nowait with multiple concurrent calls."""
        bus = AIFixEventBus()
        mock_sink = AsyncMock(spec=Sink)
        bus.subscribe(mock_sink)

        async def run_test():
            for i in range(5):
                event = RunStarted(run_id=f"test-{i}", iteration=1)
                bus.emit_nowait(event)
            await asyncio.sleep(0.05)  # Give all tasks time to complete

        asyncio.run(run_test())
        # All 5 events should have been handled
        assert mock_sink.handle.call_count == 5

    def test_new_run_id_format(self) -> None:
        """Test that new_run_id returns properly formatted string."""
        run_id = AIFixEventBus.new_run_id()

        # Should contain timestamp
        assert "-" in run_id
        parts = run_id.split("-")
        assert len(parts) >= 2  # At least timestamp and uuid part

    def test_new_run_id_unique(self) -> None:
        """Test that new_run_id generates unique IDs."""
        ids = set()
        for _ in range(10):
            run_id = AIFixEventBus.new_run_id()
            assert run_id not in ids
            ids.add(run_id)

    def test_multiple_subscriptions(self) -> None:
        """Test subscribing same sink multiple times."""
        bus = AIFixEventBus()
        mock_sink = MagicMock(spec=Sink)
        bus.subscribe(mock_sink)
        bus.subscribe(mock_sink)
        assert bus._sinks.count(mock_sink) == 2

    def test_unsubscribe_only_removes_one(self) -> None:
        """Test that unsubscribe only removes first occurrence."""
        bus = AIFixEventBus()
        mock_sink = MagicMock(spec=Sink)
        bus.subscribe(mock_sink)
        bus.subscribe(mock_sink)
        bus.unsubscribe(mock_sink)
        assert mock_sink in bus._sinks


class TestSinkProtocol:
    """Tests for Sink protocol compliance."""

    def test_sink_protocol_can_be_implemented(self) -> None:
        """Test that Sink protocol can be implemented."""
        class MySink:
            async def handle(self, event: AIFixEvent) -> None:
                pass

        sink = MySink()
        # Should satisfy Sink protocol
        assert isinstance(sink, Sink)