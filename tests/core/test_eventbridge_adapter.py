"""Tests for ``crackerjack.core.eventbridge_adapter``.

Covers the lightweight ``EventBridgePublisher`` async wrapper around a
``oneiric.runtime.events.EventEnvelope`` producer. The publisher
delegates to whatever bridge object is passed in, forwarding topic,
payload, and headers.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from oneiric.runtime.events import EventEnvelope

from crackerjack.core.eventbridge_adapter import EventBridgePublisher


def _make_envelope(
    topic: str = "crackerjack.test",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        topic=topic,
        payload=payload or {"k": "v"},
        headers=headers or {"trace_id": "abc"},
    )


@pytest.mark.asyncio
async def test_publish_forwards_envelope_to_bridge() -> None:
    bridge = AsyncMock()
    publisher = EventBridgePublisher(bridge)

    envelope = _make_envelope()
    await publisher.publish(envelope)

    bridge.emit.assert_awaited_once_with(
        envelope.topic,
        envelope.payload,
        envelope.headers,
    )


@pytest.mark.asyncio
async def test_publish_handles_minimal_envelope() -> None:
    """An envelope with literal topic + empty payload/headers flows through."""
    bridge = AsyncMock()
    envelope = EventEnvelope(topic="only_topic", payload={}, headers={})
    publisher = EventBridgePublisher(bridge)

    await publisher.publish(envelope)

    bridge.emit.assert_awaited_once_with("only_topic", {}, {})


@pytest.mark.asyncio
async def test_publish_propagates_bridge_exceptions() -> None:
    """If the underlying bridge raises, the publisher does not swallow it."""
    bridge = AsyncMock()
    bridge.emit.side_effect = RuntimeError("bridge offline")
    publisher = EventBridgePublisher(bridge)

    with pytest.raises(RuntimeError, match="bridge offline"):
        await publisher.publish(_make_envelope())


def test_publisher_accepts_any_bridge_object() -> None:
    """The bridge type is ``Any`` — accept any object with ``emit``."""

    class _FakeBridge:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any], dict[str, str]]] = []

        async def emit(
            self,
            topic: str,
            payload: dict[str, Any],
            headers: dict[str, str],
        ) -> None:
            self.calls.append((topic, payload, headers))

    publisher = EventBridgePublisher(_FakeBridge())
    assert publisher._bridge is not None  # type: ignore[attr-defined]
