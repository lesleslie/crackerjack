"""Crackerjack-side publisher for test lifecycle events.

Wraps existing ``CrackerjackWebSocketServer.broadcast_test_started`` /
``broadcast_test_completed`` / ``broadcast_test_failed`` broadcasts into
the canonical :class:`oneiric.runtime.events.EventEnvelope` (msgspec.Struct)
and publishes them via an injected duck-typed ``publisher`` object.

The result: events appear in the unified Bodai queue
(``~/.mahavishnu/bodai-event-queue.json``) for consumption by Claude Code's
``/bodai-status`` and the PostToolUse hook, alongside the existing
WebSocket broadcasts (which are kept for non-Claude consumers like
Grafana dashboards).

Public API
----------
- :func:`publish_test_started` -- topic ``test.started``
- :func:`publish_test_completed` -- topic ``test.completed``
- :func:`publish_test_failed` -- topic ``test.failed``

All three functions never raise under normal failure modes -- they log
at ERROR (via ``logger.exception``, which attaches a traceback) on
``Exception`` subclasses. ``asyncio.CancelledError`` propagates so
Ctrl-C interrupts long-running test runs. The canonical envelope carries
``source='crackerjack'`` in the ``headers`` dict, matching what
``mahavishnu.core.events.bodai_subscriber`` consumes.

Note: ``publisher`` is typed ``Any | None`` (NOT ``EventPublisherProtocol``
from Mahavishnu) because (a) that Protocol lives in the Mahavishnu repo
and Crackerjack does not depend on Mahavishnu, and (b) the Protocol is
typed against a Pydantic envelope, not Oneiric's msgspec envelope.
Duck-typing is intentional; AsyncMock and the Oneiric EventBridge
publisher both satisfy ``publisher.publish(envelope)``.
"""

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
    """Build the canonical Oneiric ``EventEnvelope`` for a Crackerjack event.

    Args:
        topic: Event topic (e.g. ``test.started``).
        source: Producer identifier (always ``crackerjack``).
        payload: Event-specific payload (must be JSON-serializable).

    Returns:
        A canonical :class:`oneiric.runtime.events.EventEnvelope` with
        ``source``, ``event_id``, ``timestamp``, and ``version`` set in
        the ``headers`` dict.
    """
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
    """Publish an envelope via the injected publisher.

    Swallows any exception (logs at WARNING) so a misbehaving publisher
    can never abort the broadcast path. Handles both sync and async
    ``publish`` results -- some implementations are coroutine-only, others
    return a future-like object.
    """
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
    """Publish a ``test.started`` event to the Bodai queue.

    Never raises: ``_make_envelope`` construction failures (e.g., non-JSON-
    serializable payloads) and ``publisher.publish`` failures are both
    caught and logged. ``asyncio.CancelledError`` propagates (it is
    ``BaseException``, not ``Exception`` -- this is correct asyncio
    semantics and lets Ctrl-C interrupt long-running test runs).

    Args:
        run_id: Crackerjack run identifier (e.g. ``run_2026_07_12_xyz``).
        test_suite: Name of the test suite being executed.
        total_tests: Total number of tests in the suite.
        publisher: Injected event publisher (typically an Oneiric
            ``EventBridge`` instance). ``None`` is a no-op.
    """
    # Early-return when no publisher is configured. Saves envelope
    # construction (and any incidental allocation / uuid4 / datetime.now
    # cost) when the publisher is a documented no-op.
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
    """Publish a ``test.completed`` event to the Bodai queue.

    Never raises -- see :func:`publish_test_started` for the contract.

    Args:
        run_id: Crackerjack run identifier.
        tests_completed: Number of tests that completed (passed).
        tests_failed: Number of tests that failed.
        duration_seconds: Wall-clock duration of the run.
        publisher: Injected event publisher. ``None`` is a no-op.
    """
    # Early-return when no publisher is configured (see publish_test_started).
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
    """Publish a ``test.failed`` event to the Bodai queue.

    Never raises -- see :func:`publish_test_started` for the contract.

    Args:
        run_id: Crackerjack run identifier.
        test_name: Name of the failing test (e.g. ``test_async_patterns``).
        error: Error message string.
        traceback: Python traceback for the failure.
        publisher: Injected event publisher. ``None`` is a no-op.
    """
    # Early-return when no publisher is configured (see publish_test_started).
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
