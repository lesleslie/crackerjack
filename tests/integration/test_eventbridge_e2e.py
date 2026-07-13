"""End-to-end integration tests for the Crackerjack EventBridge publisher.

Verifies that publish_test_* produces envelopes with the canonical shape
the Mahavishnu Bodai subscriber consumes (topic, payload, headers.source,
headers.event_id, headers.timestamp). Uses an in-memory recording
transport (no Redis required) to simulate the round trip.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from crackerjack.core.eventbridge_publisher import (
    EVENT_VERSION,
    SOURCE,
    publish_test_completed,
    publish_test_failed,
    publish_test_started,
)


@dataclass
class RecordingTransport:
    """Records every published envelope for later inspection."""

    published: list[dict[str, Any]] = field(default_factory=list)

    async def publish(self, envelope: Any) -> Any:
        self.published.append(
            {
                "topic": envelope.topic,
                "payload": dict(envelope.payload),
                "headers": dict(envelope.headers),
            }
        )
        return envelope


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_publish_test_started_round_trips_through_transport() -> None:
    transport = RecordingTransport()
    await publish_test_started(
        "run_e2e_1", "tests/unit", total_tests=42, publisher=transport
    )
    assert len(transport.published) == 1
    record = transport.published[0]
    assert record["topic"] == "test.started"
    assert record["payload"]["run_id"] == "run_e2e_1"
    assert record["payload"]["test_suite"] == "tests/unit"
    assert record["payload"]["total_tests"] == 42
    assert record["headers"]["source"] == SOURCE
    assert record["headers"]["version"] == EVENT_VERSION
    assert record["headers"]["event_id"]


@pytest.mark.asyncio
async def test_publish_test_completed_round_trips_through_transport() -> None:
    transport = RecordingTransport()
    await publish_test_completed(
        "run_e2e_2",
        tests_completed=100,
        tests_failed=2,
        duration_seconds=12.5,
        publisher=transport,
    )
    assert len(transport.published) == 1
    record = transport.published[0]
    assert record["topic"] == "test.completed"
    assert record["payload"]["run_id"] == "run_e2e_2"
    assert record["payload"]["tests_completed"] == 100
    assert record["payload"]["tests_failed"] == 2
    assert record["payload"]["duration_seconds"] == 12.5


@pytest.mark.asyncio
async def test_publish_test_failed_round_trips_through_transport() -> None:
    transport = RecordingTransport()
    await publish_test_failed(
        "run_e2e_3",
        "test_async_patterns",
        "AssertionError: expected 1, got 2",
        "Traceback (most recent call last):\n  File ...",
        publisher=transport,
    )
    assert len(transport.published) == 1
    record = transport.published[0]
    assert record["topic"] == "test.failed"
    assert record["payload"]["run_id"] == "run_e2e_3"
    assert record["payload"]["test_name"] == "test_async_patterns"
    assert "AssertionError" in record["payload"]["error"]


@pytest.mark.asyncio
async def test_three_sequential_publishes_preserve_order_and_uniqueness() -> None:
    """Three publishes produce three distinct event_ids with payload order preserved."""
    transport = RecordingTransport()
    await publish_test_started("run_seq", "fast_hooks", total_tests=10, publisher=transport)
    await publish_test_completed(
        "run_seq",
        tests_completed=10,
        tests_failed=0,
        duration_seconds=1.0,
        publisher=transport,
    )
    await publish_test_failed("run_seq", "test_x", "boom", "tb", publisher=transport)

    assert [r["topic"] for r in transport.published] == [
        "test.started",
        "test.completed",
        "test.failed",
    ]
    event_ids = [r["headers"]["event_id"] for r in transport.published]
    assert len(set(event_ids)) == 3, "event_ids must be unique across publishes"
