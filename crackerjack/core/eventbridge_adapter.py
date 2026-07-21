from __future__ import annotations

from typing import Any

from oneiric.runtime.events import EventEnvelope


class EventBridgePublisher:
    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge

    async def publish(self, envelope: EventEnvelope) -> None:
        await self._bridge.emit(
            envelope.topic,
            envelope.payload,
            envelope.headers,
        )


__all__ = ["EventBridgePublisher"]
