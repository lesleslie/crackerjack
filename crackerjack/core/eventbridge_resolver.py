"""Production wiring entry point for the EventBridge publisher.

The ``crackerjack.core.eventbridge_publisher`` module expects an injected
``publisher`` argument. ``WorkflowPipeline.__init__`` calls
``resolve_event_publisher(settings, bridge=...)`` to construct one when
the operator has opted in via ``settings.eventbridge.enabled=True``.

Wiring is opt-in:
- ``settings.eventbridge.enabled=False`` (default) -> returns None
- ``settings.eventbridge.dry_run=True`` (default) -> returns None
- both ``enabled=True`` AND ``dry_run=False`` AND ``bridge`` provided
  -> returns ``EventBridgePublisher(bridge)``

When ``bridge`` is not provided (the production pre-Oneiric-runtime case),
the resolver returns None. The full Oneiric runtime initialization is
deferred; this resolver is the seam where production code will pass
the live bridge once that wiring exists.
"""

from __future__ import annotations

from typing import Any

from crackerjack.config import CrackerjackSettings
from crackerjack.core.eventbridge_adapter import EventBridgePublisher


def resolve_event_publisher(
    settings: CrackerjackSettings,
    *,
    bridge: Any | None = None,
) -> EventBridgePublisher | None:
    """Return an ``EventBridgePublisher`` when the operator has opted in.

    Args:
        settings: Loaded Crackerjack settings. The ``eventbridge`` block
            controls whether wiring happens.
        bridge: Pre-constructed Oneiric EventBridge instance. If None
            (default), the resolver returns None -- this is the
            pre-Oneiric-runtime case. Production wiring will pass a
            real bridge once the runtime initialization is available.

    Returns:
        ``EventBridgePublisher(bridge)`` when enabled, not dry-run, and
        a bridge is available. ``None`` otherwise.
    """
    eb = settings.eventbridge
    if not eb.enabled:
        return None
    if eb.dry_run:
        return None
    if bridge is None:
        return None
    return EventBridgePublisher(bridge)


__all__ = ["resolve_event_publisher"]
