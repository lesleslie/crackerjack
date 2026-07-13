"""Unit tests for ``crackerjack.core.eventbridge_resolver``.

The resolver is the production wiring entry point: given a
``CrackerjackSettings`` instance, it returns an ``EventBridgePublisher``
(or ``None`` when the operator has not opted in). The wiring is opt-in
via ``settings.eventbridge.enabled=True`` AND ``dry_run=False``.

Tests cover:
- disabled -> None (no-op)
- enabled + dry_run -> None (safety: don't wire a real bridge)
- enabled + dry_run=False -> EventBridgePublisher wrapping the bridge
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from crackerjack.config import CrackerjackSettings, EventBridgeSettings
from crackerjack.core.eventbridge_adapter import EventBridgePublisher
from crackerjack.core.eventbridge_resolver import resolve_event_publisher
from oneiric.runtime.events import EventEnvelope


def _settings_with_eventbridge(
    *, enabled: bool, dry_run: bool = False, endpoint: str = ""
) -> CrackerjackSettings:
    return CrackerjackSettings(
        eventbridge=EventBridgeSettings(
            enabled=enabled, dry_run=dry_run, endpoint=endpoint
        )
    )


def test_resolve_returns_none_when_disabled() -> None:
    """Disabled (default) -> no publisher."""
    settings = _settings_with_eventbridge(enabled=False)
    assert resolve_event_publisher(settings, bridge=MagicMock()) is None


def test_resolve_returns_none_when_dry_run() -> None:
    """dry_run=True is a safety override; never wire a real bridge."""
    settings = _settings_with_eventbridge(enabled=True, dry_run=True)
    assert resolve_event_publisher(settings, bridge=MagicMock()) is None


def test_resolve_returns_publisher_when_enabled_and_live() -> None:
    """Enabled + dry_run=False + bridge provided -> EventBridgePublisher."""
    bridge = MagicMock()
    settings = _settings_with_eventbridge(enabled=True, dry_run=False)
    publisher = resolve_event_publisher(settings, bridge=bridge)
    assert isinstance(publisher, EventBridgePublisher)


def test_resolved_publisher_forwards_to_bridge_emit() -> None:
    """The publisher produced by the resolver actually publishes."""
    bridge = MagicMock()
    bridge.emit = AsyncMock()

    settings = _settings_with_eventbridge(enabled=True, dry_run=False)
    publisher = resolve_event_publisher(settings, bridge=bridge)
    assert publisher is not None

    envelope = EventEnvelope(
        topic="test.started",
        payload={"run_id": "r1"},
        headers={"source": "crackerjack"},
    )
    asyncio.run(publisher.publish(envelope))

    bridge.emit.assert_awaited_once_with(
        "test.started", {"run_id": "r1"}, {"source": "crackerjack"}
    )


def test_resolve_returns_none_when_enabled_but_no_bridge() -> None:
    """When bridge is None (default arg) the resolver returns None.

    This is the production wiring entry point before the Oneiric
    runtime initialization is wired in -- production callers supply a
    bridge; tests do too. The no-bridge path keeps the resolver safe
    to call at startup when the Oneiric runtime is unavailable.
    """
    settings = _settings_with_eventbridge(enabled=True, dry_run=False)
    assert resolve_event_publisher(settings) is None
