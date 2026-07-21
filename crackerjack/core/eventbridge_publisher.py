from __future__ import annotations

import inspect
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from oneiric.runtime.events import EventEnvelope, create_event_envelope

logger = logging.getLogger(__name__)

SOURCE = "crackerjack"
EVENT_VERSION = "1.0.0"

TOPIC_TEST_STARTED = "test.started"
TOPIC_TEST_COMPLETED = "test.completed"
TOPIC_TEST_FAILED = "test.failed"


def _make_envelope(topic: str, source: str, payload: dict[str, Any]) -> EventEnvelope:
    event_id = uuid.uuid4()
    timestamp = datetime.now(UTC).isoformat()
    return create_event_envelope(
        topic=topic,
        payload=payload,
        source=source,
        version=EVENT_VERSION,
        headers={
            "source": source,
            "event_id": str(event_id),
            "timestamp": timestamp,
            "version": EVENT_VERSION,
        },
    )


async def _publish(envelope: EventEnvelope, publisher: Any | None) -> None:
    if publisher is None:
        return
    try:
        result = publisher.publish(envelope)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.exception(
            "crackerjack.publisher: failed to publish topic=%s event_id=%s",
            envelope.topic,
            envelope.headers.get("event_id", "<unknown>"),
        )


async def publish_test_started(
    run_id: str,
    test_suite: str,
    total_tests: int,
    *,
    publisher: Any | None = None,
) -> None:

    if publisher is None:
        return
    try:
        payload: dict[str, Any] = {
            "run_id": run_id,
            "test_suite": test_suite,
            "total_tests": total_tests,
        }
        envelope = _make_envelope(TOPIC_TEST_STARTED, SOURCE, payload)
        await _publish(envelope, publisher)
    except Exception:
        logger.exception(
            "crackerjack.publisher: failed to publish test.started event run_id=%s",
            run_id,
        )


async def publish_test_completed(
    run_id: str,
    tests_completed: int,
    tests_failed: int,
    duration_seconds: float,
    *,
    publisher: Any | None = None,
) -> None:

    if publisher is None:
        return
    try:
        payload: dict[str, Any] = {
            "run_id": run_id,
            "tests_completed": tests_completed,
            "tests_failed": tests_failed,
            "duration_seconds": duration_seconds,
        }
        envelope = _make_envelope(TOPIC_TEST_COMPLETED, SOURCE, payload)
        await _publish(envelope, publisher)
    except Exception:
        logger.exception(
            "crackerjack.publisher: failed to publish test.completed event run_id=%s",
            run_id,
        )


async def publish_test_failed(
    run_id: str,
    test_name: str,
    error: str,
    traceback: str,
    *,
    publisher: Any | None = None,
) -> None:

    if publisher is None:
        return
    try:
        payload: dict[str, Any] = {
            "run_id": run_id,
            "test_name": test_name,
            "error": error,
            "traceback": traceback,
        }
        envelope = _make_envelope(TOPIC_TEST_FAILED, SOURCE, payload)
        await _publish(envelope, publisher)
    except Exception:
        logger.exception(
            "crackerjack.publisher: failed to publish test.failed event "
            "run_id=%s test_name=%s",
            run_id,
            test_name,
        )


__all__ = [
    "EVENT_VERSION",
    "SOURCE",
    "TOPIC_TEST_COMPLETED",
    "TOPIC_TEST_FAILED",
    "TOPIC_TEST_STARTED",
    "_make_envelope",
    "publish_test_completed",
    "publish_test_failed",
    "publish_test_started",
]
