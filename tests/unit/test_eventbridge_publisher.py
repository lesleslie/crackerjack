"""Unit tests for ``crackerjack.core.eventbridge_publisher``.

Mirrors the test pattern from
``mahavishnu/tests/unit/test_mahavishnu_publisher.py`` — same shape,
same envelope-shape assertions, same never-raises guarantee.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from oneiric.runtime.events import EventEnvelope

from crackerjack.core.eventbridge_publisher import (
    EVENT_VERSION,
    SOURCE,
    TOPIC_TEST_COMPLETED,
    TOPIC_TEST_STARTED,
    _make_envelope,
    publish_test_completed,
    publish_test_failed,
    publish_test_started,
)

pytestmark = pytest.mark.unit


def _headers_of(envelope: EventEnvelope) -> dict[str, Any]:
    return dict(envelope.headers) if isinstance(envelope.headers, dict) else {}


def _payload_of(envelope: EventEnvelope) -> dict[str, Any]:
    return dict(envelope.payload) if isinstance(envelope.payload, dict) else {}


def test_make_envelope_builds_canonical_shape() -> None:
    """_make_envelope produces a Oneiric msgspec envelope with required headers."""
    envelope = _make_envelope(
        TOPIC_TEST_STARTED, SOURCE, {"run_id": "run_1", "total_tests": 42}
    )
    assert envelope.topic == "test.started"
    headers = _headers_of(envelope)
    assert headers.get("source") == "crackerjack"
    assert headers.get("version") == "1.0.0"
    assert isinstance(headers.get("event_id"), str) and headers.get("event_id")
    assert isinstance(headers.get("timestamp"), str) and headers.get("timestamp")
    payload = _payload_of(envelope)
    assert payload.get("run_id") == "run_1"
    assert payload.get("total_tests") == 42


def test_envelope_event_ids_are_unique_across_calls() -> None:
    """Each call produces a different event_id (UUID4)."""
    env_a = _make_envelope(TOPIC_TEST_STARTED, SOURCE, {"run_id": "run_1"})
    env_b = _make_envelope(TOPIC_TEST_STARTED, SOURCE, {"run_id": "run_1"})
    id_a = _headers_of(env_a).get("event_id")
    id_b = _headers_of(env_b).get("event_id")
    assert isinstance(id_a, str) and id_a
    assert isinstance(id_b, str) and id_b
    assert id_a != id_b


def test_envelope_timestamp_is_iso_utc() -> None:
    """Timestamp header parses as ISO 8601 in UTC."""
    envelope = _make_envelope(TOPIC_TEST_COMPLETED, SOURCE, {"run_id": "run_t"})
    timestamp = _headers_of(envelope).get("timestamp")
    assert isinstance(timestamp, str)
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None
    offset = parsed.astimezone(UTC).utcoffset()
    assert offset is not None and offset == timedelta(0)


@pytest.mark.asyncio
async def test_publish_test_started_invokes_injected_publisher() -> None:
    """publish_test_started calls publisher.publish with the right envelope."""
    publisher = AsyncMock()
    publisher.publish.return_value = None

    await publish_test_started(
        "run_xyz", "tests/unit", 42, publisher=publisher
    )

    publisher.publish.assert_awaited_once()
    envelope = publisher.publish.await_args.args[0]
    assert isinstance(envelope, EventEnvelope)
    assert envelope.topic == "test.started"
    payload = _payload_of(envelope)
    assert payload.get("run_id") == "run_xyz"
    assert payload.get("test_suite") == "tests/unit"
    assert payload.get("total_tests") == 42
    assert _headers_of(envelope).get("source") == "crackerjack"


@pytest.mark.asyncio
async def test_publish_test_completed_builds_canonical_envelope() -> None:
    """publish_test_completed emits topic=test.completed with the right payload."""
    publisher = AsyncMock()
    publisher.publish.return_value = None

    await publish_test_completed(
        "run_done",
        tests_completed=42,
        tests_failed=0,
        duration_seconds=12.5,
        publisher=publisher,
    )

    publisher.publish.assert_awaited_once()
    envelope = publisher.publish.await_args.args[0]
    assert envelope.topic == "test.completed"
    payload = _payload_of(envelope)
    assert payload.get("run_id") == "run_done"
    assert payload.get("tests_completed") == 42
    assert payload.get("tests_failed") == 0
    assert payload.get("duration_seconds") == 12.5
    assert _headers_of(envelope).get("source") == "crackerjack"
    assert _headers_of(envelope).get("version") == EVENT_VERSION


@pytest.mark.asyncio
async def test_publish_test_failed_builds_canonical_envelope() -> None:
    """publish_test_failed emits topic=test.failed with the right payload."""
    publisher = AsyncMock()
    publisher.publish.return_value = None

    await publish_test_failed(
        "run_boom",
        "test_async_patterns",
        "AssertionError",
        "Traceback...",
        publisher=publisher,
    )

    publisher.publish.assert_awaited_once()
    envelope = publisher.publish.await_args.args[0]
    assert envelope.topic == "test.failed"
    payload = _payload_of(envelope)
    assert payload.get("run_id") == "run_boom"
    assert payload.get("test_name") == "test_async_patterns"
    assert payload.get("error") == "AssertionError"
    assert payload.get("traceback") == "Traceback..."
    assert _headers_of(envelope).get("source") == "crackerjack"


@pytest.mark.asyncio
async def test_publisher_with_none_is_a_noop() -> None:
    """publisher=None is silently accepted and emits nothing."""
    # Must not raise
    await publish_test_started("run_n", "tests/unit", 10)
    await publish_test_completed("run_n", 10, 0, 1.0)
    await publish_test_failed("run_n", "t", "e", "tb")


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("transport is down"),
        ConnectionError("broker unreachable"),
        TimeoutError("publish timed out"),
        TypeError("malformed envelope"),
        OSError("network unreachable"),
    ],
)
@pytest.mark.asyncio
async def test_publisher_swallows_exception_types(
    exc: BaseException, caplog: pytest.LogCaptureFixture
) -> None:
    """Each ``Exception`` subclass is logged exactly once and never propagates.

    Parametrized over 5 exception subclasses to ensure the ``except Exception``
    in the ``publish_*`` functions catches the full set of common transport
    failures (RuntimeError, ConnectionError, TimeoutError, TypeError, OSError).
    """
    publisher = AsyncMock()
    publisher.publish.side_effect = exc

    with caplog.at_level(
        logging.WARNING, logger="crackerjack.core.eventbridge_publisher"
    ):
        # Must NOT raise out of publish_test_started
        await publish_test_started(
            "run_x", "tests/unit", 10, publisher=publisher
        )

    # Exactly one log per call (not aggregate count -- aggregate allows
    # silent bugs where one call logs 3 times and another logs 0).
    error_logs = [
        rec
        for rec in caplog.records
        if rec.levelno >= logging.WARNING
        and rec.name == "crackerjack.core.eventbridge_publisher"
    ]
    assert len(error_logs) == 1, (
        f"expected exactly 1 log per call, got {len(error_logs)}: {error_logs}"
    )
    assert "test.started" in error_logs[0].getMessage()


@pytest.mark.asyncio
async def test_publisher_does_not_swallow_cancelled_error() -> None:
    """``asyncio.CancelledError`` is ``BaseException`` and propagates.

    ``except Exception`` does not catch ``BaseException`` subclasses; this is
    correct asyncio semantics. The publisher must let cancellation bubble up
    so Ctrl-C interrupts long-running test runs.
    """
    publisher = AsyncMock()
    publisher.publish.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await publish_test_started(
            "run_x", "tests/unit", 10, publisher=publisher
        )


@pytest.mark.asyncio
async def test_publisher_supports_sync_publish_returning_none() -> None:
    """Sync publisher returning ``None`` (non-awaitable) is supported.

    Exercises the ``inspect.isawaitable(result) == False`` branch in
    ``_publish``. A real class with a sync ``def publish`` (not ``async def``)
    is required -- ``Mock`` is used instead of ``AsyncMock`` because
    ``Mock`` does not auto-create ``__await__``.
    """
    sync_publisher = Mock()  # noqa: S3776  -- deliberately Mock, not AsyncMock
    sync_publisher.publish.return_value = None

    await publish_test_started(
        "run_sync", "tests/unit", 5, publisher=sync_publisher
    )
    sync_publisher.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publisher_swallows_coroutine_raising_after_await() -> None:
    """A coroutine returned by ``publish`` that raises mid-execution is swallowed.

    Uses ``side_effect`` with an ``async def`` so each ``publisher.publish``
    call returns a real coroutine that raises when awaited. AsyncMock with
    ``side_effect`` invokes the function on each call and awaits the returned
    coroutine when the mock itself is awaited -- which mirrors the real
    ``async def publish(...)`` path that production wiring uses.
    """
    publisher = AsyncMock()

    async def boom(_envelope: object) -> None:
        raise ConnectionError("lost mid-flight")

    publisher.publish.side_effect = boom

    # Must NOT raise out of publish_test_started
    await publish_test_started(
        "run_x", "tests/unit", 10, publisher=publisher
    )


@pytest.mark.parametrize(
    "call, expected_topic",
    [
        (
            lambda pub: publish_test_started("run_z", "ts", 0, publisher=pub),
            "test.started",
        ),
        (
            lambda pub: publish_test_completed(
                "run_z", 0, 0, 0.0, publisher=pub
            ),
            "test.completed",
        ),
        (
            lambda pub: publish_test_failed("run_z", "t", "", "", publisher=pub),
            "test.failed",
        ),
    ],
)
@pytest.mark.asyncio
async def test_publisher_handles_zero_and_empty_values(
    call: object, expected_topic: str
) -> None:
    """Boundary values (``0``, ``""``, ``0.0``) flow through without dropping fields."""
    publisher = AsyncMock()
    publisher.publish.return_value = None
    await call(publisher)  # ty: ignore[call-non-callable]
    envelope = publisher.publish.await_args.args[0]
    assert envelope.topic == expected_topic
    payload = _payload_of(envelope)
    assert payload, "payload must be a non-empty dict, not None"


@pytest.mark.asyncio
async def test_event_id_is_valid_uuid4_format() -> None:
    """The event_id header parses as a UUID4 (not just truthy)."""
    envelope = _make_envelope(TOPIC_TEST_STARTED, SOURCE, {"run_id": "r"})
    event_id = _headers_of(envelope).get("event_id")
    assert isinstance(event_id, str) and event_id
    parsed = uuid.UUID(event_id)
    assert parsed.version == 4, "event_id must be UUID4 (random)"