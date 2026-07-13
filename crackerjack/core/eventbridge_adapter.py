"""Oneiric EventBridge adapter — bridges ``publisher.publish(envelope)`` to ``bridge.emit(...)``.

The :mod:`crackerjack.core.eventbridge_publisher` module expects an
injected ``publisher`` with an async ``publish(envelope)`` method.
Oneiric's :class:`oneiric.domains.events.EventBridge` exposes an
``emit(topic, payload, headers)`` method, not ``publish``. This adapter
translates between the two.

Per the operational-safety review (Finding #2): this adapter is the
production injection point. Without it, the publisher module would
have no production-compatible publisher to wire into. Tests use a
duck-typed AsyncMock; production wires an ``EventBridgePublisher``
constructed against the running ``EventBridge``.
"""
from __future__ import annotations

from typing import Any

from oneiric.runtime.events import EventEnvelope


class EventBridgePublisher:
    """Adapter from ``publish(envelope)`` to ``EventBridge.emit(topic, payload, headers)``.

    Args:
        bridge: An instance of :class:`oneiric.domains.events.EventBridge`
            (duck-typed; the only attribute accessed is ``emit``).
    """

    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge

    async def publish(self, envelope: EventEnvelope) -> None:
        """Forward ``envelope`` to ``bridge.emit(topic, payload, headers)``."""
        await self._bridge.emit(
            envelope.topic,
            envelope.payload,
            envelope.headers,
        )


__all__ = ["EventBridgePublisher"]