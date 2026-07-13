"""Tests for the production wiring of EventBridgePublisher in WorkflowPipeline.

The wiring happens inside ``run_complete_workflow`` (after the Oneiric
runtime is built) and uses ``PhaseCoordinator.set_event_publisher``.

Tests verify the wiring is opt-in and never wires when the operator
has not enabled it.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from crackerjack.config import CrackerjackSettings, EventBridgeSettings
from crackerjack.core.eventbridge_adapter import EventBridgePublisher
from crackerjack.core.workflow_orchestrator import WorkflowPipeline


def _settings_with_eventbridge(*, enabled: bool, dry_run: bool = False) -> CrackerjackSettings:
    return CrackerjackSettings(
        eventbridge=EventBridgeSettings(enabled=enabled, dry_run=dry_run)
    )


def _make_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.emit = AsyncMock()
    return bridge


def _build_pipeline(
    settings: CrackerjackSettings, *, bridge: object | None = None
) -> WorkflowPipeline:
    """Construct a WorkflowPipeline without running it.

    Uses the ``phases`` and ``session`` injection points to avoid
    spinning up the real Oneiric runtime. ``bridge_resolver`` is
    wired so production-style bridge resolution works in tests.
    """
    from crackerjack.core.console import CrackerjackConsole

    phases = MagicMock()
    session = MagicMock()
    return WorkflowPipeline(
        console=CrackerjackConsole(),
        pkg_path=None,
        settings=settings,
        session=session,
        phases=phases,
        bridge_resolver=lambda _settings, _runtime: bridge,
    )


def test_run_complete_workflow_does_not_set_publisher_when_disabled() -> None:
    """settings.eventbridge.enabled=False -> no set_event_publisher call."""
    settings = _settings_with_eventbridge(enabled=False)
    pipeline = _build_pipeline(settings, bridge=_make_bridge())

    async def _run_no_phase_returns_true() -> bool:
        return True

    pipeline.phases.run_configuration_phase = _run_no_phase_returns_true
    pipeline._initialize_workflow_session = MagicMock()
    pipeline._clear_oneiric_cache = MagicMock()
    pipeline.session.finalize_session = MagicMock()

    import asyncio
    asyncio.run(pipeline.run_complete_workflow(options=MagicMock()))

    pipeline.phases.set_event_publisher.assert_not_called()


def test_run_complete_workflow_does_not_set_publisher_when_dry_run() -> None:
    """settings.eventbridge.dry_run=True -> safety override; no wiring."""
    settings = _settings_with_eventbridge(enabled=True, dry_run=True)
    pipeline = _build_pipeline(settings, bridge=_make_bridge())

    async def _run() -> bool:
        return True

    pipeline.phases.run_configuration_phase = _run
    pipeline._initialize_workflow_session = MagicMock()
    pipeline._clear_oneiric_cache = MagicMock()
    pipeline.session.finalize_session = MagicMock()

    import asyncio
    asyncio.run(pipeline.run_complete_workflow(options=MagicMock()))

    pipeline.phases.set_event_publisher.assert_not_called()


def test_run_complete_workflow_sets_publisher_when_enabled_and_bridge_provided() -> None:
    """Enabled + dry_run=False + bridge -> set_event_publisher called."""
    settings = _settings_with_eventbridge(enabled=True, dry_run=False)
    bridge = _make_bridge()
    pipeline = _build_pipeline(settings, bridge=bridge)

    async def _run() -> bool:
        return True

    pipeline.phases.run_configuration_phase = _run
    pipeline._initialize_workflow_session = MagicMock()
    pipeline._clear_oneiric_cache = MagicMock()
    pipeline.session.finalize_session = MagicMock()

    import asyncio
    asyncio.run(pipeline.run_complete_workflow(options=MagicMock()))

    pipeline.phases.set_event_publisher.assert_called_once()
    publisher_arg = pipeline.phases.set_event_publisher.call_args.args[0]
    assert isinstance(publisher_arg, EventBridgePublisher)


def test_run_complete_workflow_does_not_set_publisher_when_bridge_resolver_returns_none() -> None:
    """When the bridge_resolver returns None (e.g. Oneiric runtime down),
    the wiring is a no-op even if settings say enabled=True."""
    settings = _settings_with_eventbridge(enabled=True, dry_run=False)
    pipeline = _build_pipeline(settings, bridge=None)  # resolver returns None

    async def _run() -> bool:
        return True

    pipeline.phases.run_configuration_phase = _run
    pipeline._initialize_workflow_session = MagicMock()
    pipeline._clear_oneiric_cache = MagicMock()
    pipeline.session.finalize_session = MagicMock()

    import asyncio
    asyncio.run(pipeline.run_complete_workflow(options=MagicMock()))

    pipeline.phases.set_event_publisher.assert_not_called()
