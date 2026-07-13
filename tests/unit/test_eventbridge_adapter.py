"""Unit tests for ``crackerjack.core.eventbridge_adapter``.

The adapter bridges ``publisher.publish(envelope)`` (the API the
publisher module expects) and ``EventBridge.emit(topic, payload, headers)``
(the API Oneiric's EventBridge exposes).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from oneiric.runtime.events import EventEnvelope

from crackerjack.core.eventbridge_adapter import EventBridgePublisher


def test_adaptor_publish_calls_emit_with_envelope_fields() -> None:
    """publish() unpacks the envelope and forwards to bridge.emit()."""
    bridge = MagicMock()
    bridge.emit = AsyncMock()
    adapter = EventBridgePublisher(bridge)
    envelope = EventEnvelope(
        topic="test.started",
        payload={"run_id": "r", "total_tests": 5},
        headers={"source": "crackerjack", "event_id": "abc-123"},
    )

    # Async -- run via asyncio
    import asyncio

    asyncio.run(adapter.publish(envelope))

    bridge.emit.assert_awaited_once_with(
        "test.started",
        {"run_id": "r", "total_tests": 5},
        {"source": "crackerjack", "event_id": "abc-123"},
    )


def test_adaptor_constructor_stores_bridge() -> None:
    """The bridge reference is stored for later emit() calls."""
    bridge = MagicMock()
    adapter = EventBridgePublisher(bridge)
    assert adapter._bridge is bridge