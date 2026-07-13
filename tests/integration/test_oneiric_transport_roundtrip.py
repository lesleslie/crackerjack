"""Real Oneiric EventBridge transport integration tests.

These tests exercise the full ``publish_* -> EventBridgePublisher -> emit``
path against a real ``oneiric.domains.events.EventBridge`` instance.
They use a custom dispatcher to capture emitted envelopes, so no Redis
or external broker is required -- the test stays self-contained.

Mirrors the Akosha and Mahavishnu integration tests. The companion
``test_eventbridge_e2e.py`` covers the AsyncMock component path; this
file covers the Oneiric transport round-trip.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from oneiric.core.config import LayerSettings
from oneiric.core.lifecycle import LifecycleManager
from oneiric.core.resolution import Resolver
from oneiric.domains.events import EventBridge
from oneiric.runtime.events import EventEnvelope, EventHandler, HandlerResult

from crackerjack.core.eventbridge_adapter import EventBridgePublisher
from crackerjack.core.eventbridge_publisher import (
    publish_test_completed,
    publish_test_failed,
    publish_test_started,
)


pytestmark = [pytest.mark.integration, pytest.mark.timeout(30)]


class _CapturingDispatcher:
    """Drop-in EventDispatcher replacement that captures and dispatches envelopes.

    Mirrors the real EventDispatcher:
    - ``dispatch`` is async and invokes registered handlers that accept
      the envelope (matching topic and filters).
    - ``register`` adds a handler to the dispatch pool.
    - The ``captured`` list accumulates every envelope that flows through.

    Used to verify that envelopes produced by the publisher module
    actually reach the Oneiric EventBridge dispatch pipeline without
    requiring a real Redis or external broker.
    """

    def __init__(self) -> None:
        self.captured: list[EventEnvelope] = []
        self._handlers: list[EventHandler] = []

    async def dispatch(self, envelope: EventEnvelope) -> list[HandlerResult]:
        self.captured.append(envelope)
        results: list[HandlerResult] = []
        for handler in self._handlers:
            if not handler.accepts(envelope):
                continue
            try:
                value = handler.callback(envelope)
                if inspect.isawaitable(value):
                    await value
                results.append(
                    HandlerResult(
                        handler=handler.name,
                        success=True,
                        duration=0.0,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    HandlerResult(
                        handler=handler.name,
                        success=False,
                        duration=0.0,
                        error=str(exc),
                    )
                )
        return results

    def register(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def handlers(self) -> list[EventHandler]:
        return list(self._handlers)


def _build_real_eventbridge() -> tuple[EventBridge, _CapturingDispatcher]:
    """Construct a real ``EventBridge`` with a capturing dispatcher.

    Returns:
        (bridge, dispatcher): the bridge to publish through and the
        dispatcher instance whose ``captured`` list accumulates emitted
        envelopes.
    """
    resolver = Resolver()
    lifecycle = LifecycleManager(resolver)
    settings = LayerSettings()
    bridge = EventBridge(resolver, lifecycle, settings)
    dispatcher = _CapturingDispatcher()
    bridge._dispatcher = dispatcher  # noqa: SLF001 -- test-only
    return bridge, dispatcher


def test_eventbridge_constructed_with_real_oneiric_runtime() -> None:
    """Sanity check: EventBridge(resolver, lifecycle, settings) constructs."""
    bridge, dispatcher = _build_real_eventbridge()
    assert isinstance(bridge, EventBridge)
    assert dispatcher.captured == []


@pytest.mark.asyncio
async def test_publish_test_started_round_trips_through_real_eventbridge() -> None:
    """publish_test_started envelope arrives at the Oneiric dispatcher."""
    bridge, dispatcher = _build_real_eventbridge()
    publisher = EventBridgePublisher(bridge)

    await publish_test_started(
        "run_rt_001", "tests/unit", 42, publisher=publisher
    )

    assert len(dispatcher.captured) == 1
    envelope = dispatcher.captured[0]
    assert isinstance(envelope, EventEnvelope)
    assert envelope.topic == "test.started"
    assert envelope.headers.get("source") == "crackerjack"
    assert envelope.payload.get("run_id") == "run_rt_001"
    assert envelope.payload.get("total_tests") == 42


@pytest.mark.asyncio
async def test_publish_test_completed_round_trips() -> None:
    bridge, dispatcher = _build_real_eventbridge()
    publisher = EventBridgePublisher(bridge)

    await publish_test_completed(
        "run_rt_002",
        tests_completed=10,
        tests_failed=2,
        duration_seconds=1.5,
        publisher=publisher,
    )

    envelope = dispatcher.captured[0]
    assert envelope.topic == "test.completed"
    assert envelope.payload.get("tests_failed") == 2
    assert envelope.payload.get("duration_seconds") == 1.5


@pytest.mark.asyncio
async def test_publish_test_failed_round_trips() -> None:
    bridge, dispatcher = _build_real_eventbridge()
    publisher = EventBridgePublisher(bridge)

    await publish_test_failed(
        "run_rt_003",
        "test_async_patterns",
        "AssertionError",
        "Traceback: ...",
        publisher=publisher,
    )

    envelope = dispatcher.captured[0]
    assert envelope.topic == "test.failed"
    assert envelope.payload.get("error") == "AssertionError"
    assert envelope.payload.get("traceback") == "Traceback: ..."


@pytest.mark.asyncio
async def test_eventbridge_emit_returns_handler_results() -> None:
    """bridge.emit() returns HandlerResult list (verifies EventBridge protocol)."""
    bridge, dispatcher = _build_real_eventbridge()

    envelope = EventEnvelope(
        topic="test.started",
        payload={"run_id": "run_emit"},
        headers={"source": "crackerjack", "event_id": "e1"},
    )
    results = await bridge.emit(
        envelope.topic,
        envelope.payload,
        envelope.headers,
    )
    assert isinstance(results, list)
    assert len(dispatcher.captured) == 1
    assert dispatcher.captured[0].payload["run_id"] == "run_emit"


@pytest.mark.asyncio
async def test_publisher_with_none_does_not_invoke_bridge() -> None:
    """publisher=None: the publisher module short-circuits before touching the bridge."""
    bridge, dispatcher = _build_real_eventbridge()
    # No publisher injection; the module-level publisher is None (fixture reset).
    await publish_test_started("run_none", "ts", 0)
    assert dispatcher.captured == []  # bridge was never called


@pytest.mark.asyncio
async def test_eventhandler_callback_dispatches_through_real_eventbridge() -> None:
    """Verify a real EventHandler registered on the bridge receives envelopes.

    The default EventBridge constructed by ``_build_real_eventbridge``
    has zero handlers (the resolver has no candidates). We register
    a custom EventHandler directly on the dispatcher to confirm the
    bridge's dispatch mechanism actually fires handlers.
    """
    bridge, _dispatcher = _build_real_eventbridge()

    seen: list[EventEnvelope] = []

    async def _callback(envelope: EventEnvelope) -> Any:
        seen.append(envelope)
        return None

    bridge._dispatcher.register(  # noqa: SLF001 -- test-only
        EventHandler(
            name="rt-handler",
            callback=_callback,
            topics=("test.started",),
        )
    )

    results = await bridge.emit(
        "test.started",
        {"run_id": "rt"},
        {"source": "crackerjack"},
    )
    assert len(seen) == 1
    assert seen[0].topic == "test.started"
    assert len(results) >= 1
    assert any(r.success for r in results)
