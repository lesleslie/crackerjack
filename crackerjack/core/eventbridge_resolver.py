from __future__ import annotations

from typing import Any

from crackerjack.config import CrackerjackSettings
from crackerjack.core.eventbridge_adapter import EventBridgePublisher


def resolve_event_publisher(
    settings: CrackerjackSettings,
    *,
    bridge: Any | None = None,
) -> EventBridgePublisher | None:
    eb = settings.eventbridge
    if not eb.enabled:
        return None
    if eb.dry_run:
        return None
    if bridge is None:
        return None
    return EventBridgePublisher(bridge)


__all__ = ["resolve_event_publisher"]
