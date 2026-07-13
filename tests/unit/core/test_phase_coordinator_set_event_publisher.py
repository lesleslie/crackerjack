"""Tests for PhaseCoordinator.set_event_publisher.

The setter is the production wiring seam: WorkflowPipeline.run_complete_workflow
constructs an EventBridgePublisher after the Oneiric runtime is built and
calls this setter on PhaseCoordinator. Before the setter exists, the
publisher had to be passed at construction time only -- which made
runtime-aware wiring impossible.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

from crackerjack.core.phase_coordinator import PhaseCoordinator


def _make_coordinator() -> PhaseCoordinator:
    return PhaseCoordinator.__new__(PhaseCoordinator)


def test_set_event_publisher_replaces_stored_publisher() -> None:
    """set_event_publisher stores the publisher for later emit calls."""
    coord = _make_coordinator()
    publisher = AsyncMock()
    coord.set_event_publisher(publisher)
    assert coord._event_publisher is publisher


def test_set_event_publisher_to_none_disables_emission() -> None:
    """set_event_publisher(None) clears the stored publisher (no-op)."""
    coord = _make_coordinator()
    coord.set_event_publisher(AsyncMock())
    coord.set_event_publisher(None)
    assert coord._event_publisher is None


def test_set_event_publisher_can_be_called_multiple_times() -> None:
    """Each set_event_publisher call replaces the previous publisher."""
    coord = _make_coordinator()
    pub_a = AsyncMock()
    pub_b = AsyncMock()

    coord.set_event_publisher(pub_a)
    assert coord._event_publisher is pub_a

    coord.set_event_publisher(pub_b)
    assert coord._event_publisher is pub_b
