# Crackerjack EventBridge Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Crackerjack-side publisher that adapts the existing `broadcast_test_*` WebSocket methods into the canonical Oneiric `EventEnvelope` (msgspec) and emits them through Oneiric EventBridge so the Mahavishnu Bodai subscriber (Phase 6A) surfaces `[crackerjack] test.started/completed/failed` alongside the existing `[mahavishnu]` and (eventually) `[akosha]` lines.

**Architecture:** A new `crackerjack.core.eventbridge_publisher` module exposes three `publish_test_*` async functions that mirror `mahavishnu.core.events.mahavishnu_publisher`. Each function builds a canonical Oneiric `EventEnvelope` via `oneiric.runtime.events.create_event_envelope` (msgspec.Struct) and dispatches it through an injected `publisher: Any | None` parameter (duck-typed; `None` is a no-op). The functions never raise — they log at WARNING on transport failure. Wire-up happens at the four `PhaseCoordinator.run_*_phase` entry/exit points (the production orchestrator currently has zero callers for `broadcast_test_*`, so we add them in parallel with the publisher). Settings gain an optional `eventbridge:` block; the MCP server gains a `publish_to_eventbridge` tool for ad-hoc emission.

**Tech Stack:** Python 3.13, oneiric 0.13.6 (already a dep — `pyproject.toml:49`), `oneiric.runtime.events.EventEnvelope` (msgspec), `pytest`, `pytest-asyncio`. No new dependencies required.

**Mirror reference:** `mahavishnu/core/events/mahavishnu_publisher.py` and `tests/unit/test_mahavishnu_publisher.py` (read both before starting).

## Global Constraints

- Crackerjack project conventions per `CLAUDE.md` Crackerjack-Compliant Code: `from __future__ import annotations` first non-comment line; imports sorted within each section (stdlib → third-party → first-party with `force-sort-within-sections = true` and `known-first-party = ["crackerjack"]`); modern syntax `X | None` (not `Optional[X]`); function args with default `None` typed `X | None = None`; no `assert` in production code; `logger.exception` (not `logger.error(..., exc_info=True)`) in `except` blocks; oneiric logger (`oneiric.logging`) preferred over stdlib `logging`.
- Hard limits: line length 100, max 10 function args, max 15 branches, max 6 returns, max 55 statements per function.
- Async tests don't need `@pytest.mark.asyncio` (crackerjack's `pyproject.toml` sets `asyncio_mode = "auto"`).
- The publisher's `publisher` parameter is `Any | None` (NOT `EventPublisherProtocol` — that lives in `mahavishnu.core.events.contract` and is type-mismatched with Oneiric's msgspec envelope; do not import it from Mahavishnu).

______________________________________________________________________

## File Structure

| Path | Purpose |
|---|---|
| `crackerjack/core/eventbridge_publisher.py` | New. Three `publish_test_*` functions + `_make_envelope` + `_publish` helpers. ~120 lines. |
| `crackerjack/core/phase_coordinator.py` | Modified. Adds 6 calls (4 entry, 2 success-path exit) to `publish_test_*` at the four `run_*_phase` methods. +30 lines. |
| `settings/crackerjack.yaml` | Modified. Adds `eventbridge:` block. +10 lines. |
| `crackerjack/mcp/tools/eventbridge_tools.py` | New. `register_eventbridge_tools(mcp_app)` with `publish_to_eventbridge` tool. ~70 lines. |
| `crackerjack/mcp/tools/__init__.py` | Modified. Adds `eventbridge_tools` to the tool group registry. +1 line. |
| `crackerjack/mcp/server_core.py` | Modified. Calls `register_eventbridge_tools(mcp_app)` in `create_mcp_server()`. +1 line. |
| `tests/unit/test_eventbridge_publisher.py` | New. ~200 lines. Mirrors `test_mahavishnu_publisher.py`. |
| `tests/integration/test_eventbridge_e2e.py` | New. End-to-end: spin up the publisher against a fake transport, assert the envelope round-trips. ~120 lines. |

Files changing together: `phase_coordinator.py` (the wire-up) depends on `eventbridge_publisher.py`; `mcp/tools/__init__.py` and `mcp/server_core.py` depend on `eventbridge_tools.py`; both `mcp_tools` paths are independent of the publisher. Tests are organized unit-then-integration per project convention.

______________________________________________________________________

## Task 1: Verify oneiric dependency is sufficient

**Files:**

- Read-only: `pyproject.toml` (line 49)

**Step 1.1: Read pyproject.toml line 49**

Run: `grep -n 'oneiric' /Users/les/Projects/crackerjack/pyproject.toml`
Expected: `49:    "oneiric>=0.13.3",` (confirmed by scout)

**Step 1.2: Confirm oneiric.runtime.events is importable**

Run: `cd /Users/les/Projects/crackerjack && python -c "from oneiric.runtime.events import EventEnvelope, create_event_envelope; print(EventEnvelope, create_event_envelope)"`
Expected: Both print. If either import fails, STOP — oneiric version is wrong; do not proceed.

**Step 1.3: Confirm installed oneiric version**

Run: `cd /Users/les/Projects/crackerjack && python -c "import importlib.metadata; print(importlib.metadata.version('oneiric'))"`
Expected: `0.13.6` (or higher; 0.13.x is required for the `create_event_envelope` factory).

**Commit:** No commit for this task — it's a verification step, not a code change.

______________________________________________________________________

## Task 1.5: Oneiric EventBridge adapter — `EventBridgePublisher`

**Files:**

- Create: `crackerjack/core/eventbridge_adapter.py`
- Test: `tests/unit/test_eventbridge_adapter.py`

**Why this task exists (per operational-safety Finding #2):** The publisher functions call `publisher.publish(envelope)`, but Oneiric's `EventBridge` exposes `emit(topic, payload, headers)`. The plan needs an adapter that bridges the two APIs so production wiring has a real publisher to inject. The `RecordingTransport` in integration tests still works because it's the test-time injection point; this adapter is the production injection point.

**Interfaces:**

- Consumes: `oneiric.domains.events.EventBridge` (an instance with an `emit(topic, payload, headers)` method — confirmed at `oneiric/domains/events.py:58-73`)

- Produces: `class EventBridgePublisher` with `async def publish(self, envelope: EventEnvelope) -> None` that delegates to `bridge.emit(envelope.topic, envelope.payload, envelope.headers)`

- [x] **Step 1: Write the failing test**

Write `tests/unit/test_eventbridge_adapter.py`:

```python
"""Unit tests for ``crackerjack.core.eventbridge_adapter``.

The adapter bridges ``publisher.publish(envelope)`` (the API the
publisher module expects) and ``EventBridge.emit(topic, payload, headers)``
(the API Oneiric's EventBridge exposes).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from oneiric.runtime.events import EventEnvelope
import pytest

from crackerjack.core.eventbridge_adapter import EventBridgePublisher


def test_adaptor_publish_calls_emit_with_envelope_fields() -> None:
    """publish() unpacks the envelope and forwards to bridge.emit()."""
    bridge = MagicMock()
    bridge.emit = AsyncMock()
    adapter = EventBridgePublisher(bridge)
    envelope = EventEnvelope(
        topic="test.started",
        payload={"run_id": "r", "total_tests": 5},
        headers={"source": "crackerjack", "event_id": "abc-123"},
    )

    # Async -- run via asyncio
    import asyncio
    asyncio.run(adapter.publish(envelope))

    bridge.emit.assert_awaited_once_with(
        "test.started",
        {"run_id": "r", "total_tests": 5},
        {"source": "crackerjack", "event_id": "abc-123"},
    )


def test_adaptor_constructor_stores_bridge() -> None:
    """The bridge reference is stored for later emit() calls."""
    bridge = MagicMock()
    adapter = EventBridgePublisher(bridge)
    assert adapter._bridge is bridge
```

- [x] **Step 2: Run the test to verify it fails (RED)**

Run: `cd /Users/les/Projects/crackerjack && pytest tests/unit/test_eventbridge_adapter.py -v`
Expected: `ModuleNotFoundError: No module named 'crackerjack.core.eventbridge_adapter'`

- [x] **Step 3: Implement the adapter**

Write `crackerjack/core/eventbridge_adapter.py`:

```python
"""Oneiric EventBridge adapter — bridges ``publisher.publish(envelope)`` to ``bridge.emit(...)``.

The :mod:`crackerjack.core.eventbridge_publisher` module expects an
injected ``publisher`` with an async ``publish(envelope)`` method.
Oneiric's :class:`oneiric.domains.events.EventBridge` exposes an
``emit(topic, payload, headers)`` method, not ``publish``. This adapter
translates between the two.

Per the operational-safety review (Finding #2): this adapter is the
production injection point. Without it, the publisher module would
have no production-compatible publisher to wire into. Tests use a
duck-typed AsyncMock; production wires an ``EventBridgePublisher``
constructed against the running ``EventBridge``.
"""
from __future__ import annotations

from typing import Any

from oneiric.runtime.events import EventEnvelope


class EventBridgePublisher:
    """Adapter from ``publish(envelope)`` to ``EventBridge.emit(topic, payload, headers)``.

    Args:
        bridge: An instance of :class:`oneiric.domains.events.EventBridge`
            (duck-typed; the only attribute accessed is ``emit``).
    """

    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge

    async def publish(self, envelope: EventEnvelope) -> None:
        """Forward ``envelope`` to ``bridge.emit(topic, payload, headers)``."""
        await self._bridge.emit(
            envelope.topic,
            envelope.payload,
            envelope.headers,
        )


__all__ = ["EventBridgePublisher"]
```

- [x] **Step 4: Run the test to verify it passes (GREEN)**

Run: `cd /Users/les/Projects/crackerjack && pytest tests/unit/test_eventbridge_adapter.py -v`
Expected: All 2 tests pass.

- [x] **Step 5: Verify ruff is clean**

Run: `cd /Users/les/Projects/crackerjack && ruff check crackerjack/core/eventbridge_adapter.py tests/unit/test_eventbridge_adapter.py`
Expected: `All checks passed!`

- [x] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/core/eventbridge_adapter.py tests/unit/test_eventbridge_adapter.py
git commit -m "feat(eventbridge): add EventBridgePublisher adapter

Bridges publisher.publish(envelope) (publisher module's expected API)
to EventBridge.emit(topic, payload, headers) (Oneiric's actual API).
Production wiring now has a real publisher to inject; tests still use
duck-typed AsyncMock via the publisher: Any | None parameter."
```

______________________________________________________________________

## Task 2: Failing test — `_make_envelope` produces canonical Oneiric envelope

**Files:**

- Create: `tests/unit/test_eventbridge_publisher.py`

**Interfaces:**

- Consumes: `oneiric.runtime.events.EventEnvelope` (msgspec.Struct with `topic`, `payload`, `headers`)

- Produces: `crackerjack.core.eventbridge_publisher._make_envelope(topic, source, payload) -> EventEnvelope`

- [x] **Step 1: Create the test file**

Write `tests/unit/test_eventbridge_publisher.py`:

```python
"""Unit tests for ``crackerjack.core.eventbridge_publisher``.

Mirrors the test pattern from
``mahavishnu/tests/unit/test_mahavishnu_publisher.py`` — same shape,
same envelope-shape assertions, same never-raises guarantee.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, Mock
import uuid

from oneiric.runtime.events import EventEnvelope
import pytest

from crackerjack.core.eventbridge_publisher import (
    EVENT_VERSION,
    SOURCE,
    TOPIC_TEST_COMPLETED,
    TOPIC_TEST_FAILED,
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
    assert parsed.astimezone(UTC).utcoffset().total_seconds() == 0
```

- [x] **Step 2: Run the test to verify it fails (RED)**

Run: `cd /Users/les/Projects/crackerjack && pytest tests/unit/test_eventbridge_publisher.py -v`
Expected: `ModuleNotFoundError: No module named 'crackerjack.core.eventbridge_publisher'` (or `ImportError`).

- [x] **Step 3: Stop. Move to Task 3 — implement the publisher module.**

Do NOT commit yet. Tasks 2 and 3 are one TDD cycle.

______________________________________________________________________

## Task 3: Implement `crackerjack/core/eventbridge_publisher.py` (GREEN)

**Files:**

- Create: `crackerjack/core/eventbridge_publisher.py`
- Modify: `tests/unit/test_eventbridge_publisher.py` (extend with the 7 additional tests below)

**Interfaces:**

- Consumes: `oneiric.runtime.events.EventEnvelope`, `oneiric.runtime.events.create_event_envelope`

- Produces: `publish_test_started(run_id, test_suite, total_tests, *, publisher=None)`, `publish_test_completed(run_id, tests_completed, tests_failed, duration_seconds, *, publisher=None)`, `publish_test_failed(run_id, test_name, error, traceback, *, publisher=None)`

- [x] **Step 1: Implement the publisher module**

Write `crackerjack/core/eventbridge_publisher.py`:

```python
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

from datetime import UTC, datetime
import inspect
import logging
from typing import Any
import uuid

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
            "crackerjack.publisher: failed to publish test.started event "
            "run_id=%s",
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
            "crackerjack.publisher: failed to publish test.completed event "
            "run_id=%s",
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
```

- [x] **Step 2: Extend the test file with the publish\_* tests*\*

Append the following tests to `tests/unit/test_eventbridge_publisher.py` (after the three tests from Task 2):

```python
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
        "run_done", tests_completed=42, tests_failed=0, duration_seconds=12.5,
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
        "run_boom", "test_async_patterns", "AssertionError", "Traceback...",
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
        rec for rec in caplog.records
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
    """A coroutine returned by ``publish`` that raises mid-execution is swallowed."""
    publisher = AsyncMock()

    async def boom(_envelope: object) -> None:
        raise ConnectionError("lost mid-flight")

    publisher.publish.return_value = boom()

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
            lambda pub: publish_test_completed("run_z", 0, 0, 0.0, publisher=pub),
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
    await call(publisher)  # type: ignore[operator]
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
```

Also add to the imports at the top of the file:

```python
import logging
```

- [x] **Step 3: Run all tests in the file**

Run: `cd /Users/les/Projects/crackerjack && pytest tests/unit/test_eventbridge_publisher.py -v`
Expected: All 17 tests pass (3 from Task 2, 5 basic publish\_\* tests from Step 2.1, 5 parametrized exception types + CancelledError + sync publisher + coroutine raising + boundary cases + UUID4 format = 9 from Step 2.2).

- [x] **Step 4: Verify ruff is clean**

Run: `cd /Users/les/Projects/crackerjack && ruff check crackerjack/core/eventbridge_publisher.py tests/unit/test_eventbridge_publisher.py`
Expected: `All checks passed!`

- [x] **Step 5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/core/eventbridge_publisher.py tests/unit/test_eventbridge_publisher.py
git commit -m "feat(eventbridge): add Crackerjack test-lifecycle publisher

Wraps broadcast_test_started/completed/failed into the canonical Oneiric
EventEnvelope so the Mahavishnu Bodai subscriber surfaces
[crackerjack] test.started/completed/failed lines. Mirrors
mahavishnu.core.events.mahavishnu_publisher; never-raises contract
preserved; publisher=None is a no-op."
```

______________________________________________________________________

## Task 4: Settings — add `eventbridge:` block

**Files:**

- Modify: `settings/crackerjack.yaml` (append at end)

**Interfaces:**

- Consumes: Existing settings structure (top-level keys: `crackerjack`, `websocket`, `dashboard`, etc.)

- Produces: New top-level `eventbridge:` block; nothing else reads it yet (Task 6 wires the MCP tool)

- [x] **Step 1: Read the existing tail of the settings file**

Run: `tail -20 /Users/les/Projects/crackerjack/settings/crackerjack.yaml`
Expected: YAML tail with the last section (e.g. `self_improvement:` or similar).

- [x] **Step 2: Append the eventbridge block**

Append the following to `settings/crackerjack.yaml` (preserve trailing newline if present):

```yaml
# EventBridge publisher (Phase 6 cross-repo publisher).
# When enabled=true, Crackerjack emits test lifecycle events to the
# unified Bodai EventBridge stream consumed by Mahavishnu's Bodai
# subscriber. Default disabled-by-default per operator-facing toggle
# convention.
eventbridge:
  enabled: false
  default_topic: "test.default"
  default_source: "crackerjack"
  endpoint: null  # Optional: external EventBridge ingestion URL (not used yet)
  max_concurrency: 5
  timeout_seconds: 5.0
  dry_run: true   # When true, envelopes are logged but not transmitted
```

- [x] **Step 3: Validate YAML syntax**

Run: `cd /Users/les/Projects/crackerjack && python -c "import yaml; yaml.safe_load(open('settings/crackerjack.yaml'))" && echo OK`
Expected: `OK`. If `yaml.YAMLError`, fix the indentation (must be 2-space).

- [x] **Step 4: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add settings/crackerjack.yaml
git commit -m "feat(eventbridge): add eventbridge settings block (disabled by default)"
```

______________________________________________________________________

## Task 5: Wire publish calls into `PhaseCoordinator`

**Files:**

- Modify: `crackerjack/core/phase_coordinator.py`
  - Imports: add `from crackerjack.core.eventbridge_publisher import publish_test_started, publish_test_completed, publish_test_failed`
  - Constructor: add `event_publisher: Any | None = None` parameter and `self._event_publisher = event_publisher` field
  - Method 1: `run_hooks_phase` (line 320) — emit `test.started` at entry, `test.completed` at success return
  - Method 2: `run_fast_hooks_only` (line 329) — emit `test.started` at entry (after the skip guard), `test.completed` at success return
  - Method 3: `run_snob_tests_phase` (line 808) — emit `test.started` at entry (after the skip guard), `test.completed` at success return
  - Method 4: `run_comprehensive_hooks_only` (line 901) — emit `test.started` at entry, `test.completed` at success return

**Interfaces:**

- Consumes: `publish_test_started(run_id, test_suite, total_tests, *, publisher)`, `publish_test_completed(run_id, tests_completed, tests_failed, duration_seconds, *, publisher)`

- Produces: 4 entry emits (one per phase method) + 4 success-path emits

- [x] **Step 1: Read the constructor and the four phase methods**

Run: `cd /Users/les/Projects/crackerjack && sed -n '50,90p;320,330p;808,815p;895,905p' crackerjack/core/phase_coordinator.py`
Expected: You see the constructor signature and the entry of each phase method. Confirm the constructor's existing parameter list (it likely has `console`, `session`, `options`, etc.).

- [x] **Step 2: Add the import**

Find the imports block at the top of `phase_coordinator.py` (after the `from __future__ import annotations` and standard-library imports, before any first-party imports). Add:

```python
from typing import Any  # if not already imported

from crackerjack.core.eventbridge_publisher import (
    publish_test_completed,
    publish_test_failed,
    publish_test_started,
)
```

If `from typing import Any` is already present, omit that line.

- [x] **Step 3: Add the constructor parameter and field**

Find the `__init__` method (around line 100-150). Add `event_publisher: Any | None = None` to the parameter list and `self._event_publisher = event_publisher` as the first line of the body. The exact location depends on the existing constructor — find the line `def __init__(` and add the new parameter at the end of the parameter list with the same indentation level. Add the field assignment after `self.console = ...` (or whichever field comes first).

- [x] **Step 4: Wire `run_hooks_phase` (line 320)**

Replace the body of `run_hooks_phase` with:

```python
    @handle_errors
    async def run_hooks_phase(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            return True

        run_id = getattr(options, "run_id", "unknown")
        await publish_test_started(
            run_id, "hooks", total_tests=0, publisher=self._event_publisher
        )

        if not await self.run_fast_hooks_only(options):
            return False

        result = await self.run_comprehensive_hooks_only(options)
        if result:
            await publish_test_completed(
                run_id, tests_completed=0, tests_failed=0, duration_seconds=0.0,
                publisher=self._event_publisher,
            )
        return result
```

(The exact `total_tests` value is `0` because the hooks phase doesn't count tests; downstream consumers should not interpret this as "zero tests run.")

- [x] **Step 5: Wire `run_fast_hooks_only` (line 329)**

Replace the body of `run_fast_hooks_only` with:

```python
    async def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            self.console.print("[yellow]⚠️[/yellow] Skipping fast hooks (--skip-hooks)")
            return True

        if getattr(self, "_fast_hooks_started", False):
            self.logger.debug("Duplicate fast hooks invocation detected; skipping")
            return True

        self._fast_hooks_started = True
        self.session.track_task("hooks_fast", "Fast quality checks")

        run_id = getattr(options, "run_id", "unknown")
        await publish_test_started(
            run_id, "fast_hooks", total_tests=0,
            publisher=self._event_publisher,
        )

        success = self._run_fast_hooks_with_retry(options)

        if not success and getattr(options, "ai_fix", False):
            success = await self._apply_ai_fix_for_fast_hooks(options, success)

        self._complete_fast_hooks_task(success)

        if success:
            await publish_test_completed(
                run_id, tests_completed=0, tests_failed=0, duration_seconds=0.0,
                publisher=self._event_publisher,
            )

        return success
```

- [x] **Step 6: Wire `run_snob_tests_phase` (line 808)**

Replace the body of `run_snob_tests_phase` with (preserving the existing return logic):

```python
    async def run_snob_tests_phase(self, options: OptionsProtocol) -> bool:
        if getattr(options, "no_snob", False):
            return True

        affected = self._get_snob_affected_tests()
        if not affected:
            return True

        self.console.print(
            f"[cyan]🔍 SNOB[/cyan] Running {len(affected)} affected test(s)"
        )

        run_id = getattr(options, "run_id", "unknown")
        await publish_test_started(
            run_id, "snob_tests", total_tests=len(affected),
            publisher=self._event_publisher,
        )

        passed = self._run_pytest_subset(affected)

        if passed:
            await publish_test_completed(
                run_id, tests_completed=len(affected), tests_failed=0,
                duration_seconds=0.0,
                publisher=self._event_publisher,
            )
            return True

        # ... existing failure-handling logic below, unchanged ...
        failures = (
            self.test_manager.get_test_failures()
            if hasattr(self, "test_manager")
            else []
        )
        safe = self._classify_safe_test_failures(failures)

        if not safe:
            self.console.print("[yellow]⚠️[/yellow] Snob failures require manual review")
            await publish_test_failed(
                run_id, "snob_tests", "snob test failures detected", "",
                publisher=self._event_publisher,
            )
            return False

        # ... rest unchanged
```

(Adjust: read the rest of the method first — the plan preserves any additional return logic the existing code has after the `safe` check. Do not delete logic.)

- [x] **Step 7: Wire `run_comprehensive_hooks_only` (line 901)**

Replace the entry of `run_comprehensive_hooks_only` with (preserving the rest):

```python
    async def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            return True

        run_id = getattr(options, "run_id", "unknown")
        await publish_test_started(
            run_id, "comprehensive_hooks", total_tests=0,
            publisher=self._event_publisher,
        )

        # ... rest of method unchanged ...
```

At the success path (before any `return True` at the end of the method), add:

```python
        await publish_test_completed(
            run_id, tests_completed=0, tests_failed=0, duration_seconds=0.0,
            publisher=self._event_publisher,
        )
```

- [x] **Step 8: Run the existing tests**

Run: `cd /Users/les/Projects/crackerjack && pytest tests/unit/ -x -q --timeout=120`
Expected: All existing tests pass (your changes are additive — no logic should have been removed).

- [x] **Step 9: Verify ruff is clean**

Run: `cd /Users/les/Projects/crackerjack && ruff check crackerjack/core/phase_coordinator.py`
Expected: `All checks passed!`

- [x] **Step 10: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/core/phase_coordinator.py
git commit -m "feat(eventbridge): wire publish_test_* into PhaseCoordinator

Adds event_publisher constructor parameter and emits test.started /
test.completed / test.failed envelopes at the entry/exit of the four
run_*_phase methods (run_hooks_phase, run_fast_hooks_only,
run_snob_tests_phase, run_comprehensive_hooks_only). publish calls are
no-ops when event_publisher is None, preserving existing behavior for
callers that don't construct the publisher."
```

______________________________________________________________________

## Task 6: MCP tool — `publish_to_eventbridge`

**Files:**

- Create: `crackerjack/mcp/tools/eventbridge_tools.py`
- Modify: `crackerjack/mcp/tools/__init__.py` (add `eventbridge_tools` to the registry)
- Modify: `crackerjack/mcp/server_core.py` (call `register_eventbridge_tools(mcp_app)` in `create_mcp_server()`)

**Interfaces:**

- Consumes: `publish_test_started`, `publish_test_completed`, `publish_test_failed` from `crackerjack.core.eventbridge_publisher`

- Produces: One MCP tool `publish_to_eventbridge(topic, payload, *, async_callback=False) -> dict`

- [x] **Step 1: Read existing tool patterns**

Run: `cd /Users/les/Projects/crackerjack && sed -n '270,310p' crackerjack/mcp/tools/monitoring_tools.py`
Expected: `register_monitoring_tools` and an example tool registration pattern.

- [x] **Step 2: Create `crackerjack/mcp/tools/eventbridge_tools.py`**

```python
"""MCP tools for the Crackerjack-side EventBridge publisher.

Exposes a single ``publish_to_eventbridge`` MCP tool that wraps the
underlying ``publish_test_*`` async functions into a sync-callable
interface for Claude Code and other MCP clients.

Mirrors the dispatch_to_pool pattern from
``mahavishnu/mcp/tools/pool_tools.py``: optional ``async_callback`` flag
returns a workflow_id immediately and runs the publish in the background.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
import uuid

from crackerjack.core.eventbridge_publisher import (
    publish_test_completed,
    publish_test_failed,
    publish_test_started,
)

if TYPE_CHECKING:
    from mcp_common.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Module-level publisher handle. Defaults to None (no-op). Set via
# register_eventbridge_tools(publisher=...) at app startup.
_publisher: Any | None = None


def set_eventbridge_publisher(publisher: Any | None) -> None:
    """Configure the publisher handle used by ``publish_to_eventbridge``."""
    global _publisher
    _publisher = publisher


async def _dispatch_topic(topic: str, payload: dict[str, Any]) -> None:
    """Route a (topic, payload) pair to the matching ``publish_test_*`` function."""
    if topic == "test.started":
        await publish_test_started(
            run_id=payload["run_id"],
            test_suite=payload["test_suite"],
            total_tests=payload["total_tests"],
            publisher=_publisher,
        )
    elif topic == "test.completed":
        await publish_test_completed(
            run_id=payload["run_id"],
            tests_completed=payload["tests_completed"],
            tests_failed=payload["tests_failed"],
            duration_seconds=payload["duration_seconds"],
            publisher=_publisher,
        )
    elif topic == "test.failed":
        await publish_test_failed(
            run_id=payload["run_id"],
            test_name=payload["test_name"],
            error=payload["error"],
            traceback=payload["traceback"],
            publisher=_publisher,
        )
    else:
        logger.warning(
            "crackerjack.eventbridge_tools: unknown topic=%s; ignoring", topic
        )


def register_eventbridge_tools(
    mcp_app: "FastMCP",
    publisher: Any | None = None,
    enabled: bool = False,
) -> None:
    """Register the EventBridge publisher MCP tool.

    Args:
        mcp_app: FastMCP application instance.
        publisher: Optional injected publisher. Stored at module level via
            :func:`set_eventbridge_publisher` so the tool callable can
            reach it without closure-over-app-state.
        enabled: Master toggle for the tool. When False (default), the
            tool is registered but rejects every call with
            ``{"status": "disabled"}``. Per operational-safety
            Finding #8: the operator-facing YAML toggle
            (``eventbridge.enabled``) MUST gate this call. The MCP
            server wiring must pass ``enabled=cfg.eventbridge.enabled``
            from the loaded config.

    Behavior:
        - When ``enabled=False`` (default), the tool is a no-op that
          returns ``{"status": "disabled"}`` for every call. The
          module-level ``_publisher`` is NOT set, so even direct
          calls to :func:`publish_test_*` from the same process are
          no-ops.
        - When ``enabled=True`` and ``publisher=None``, the tool
          queues/publishes through the publisher module's no-op
          early-return path. This is acceptable: the operator enabled
          the toggle but the publisher is not wired (e.g. EventBridge
          adapter not yet constructed). Output is
          ``{"status": "published"}`` for sync and
          ``{"status": "queued", "workflow_id": "..."}`` for async.
    """
    if not enabled:
        # Per the contract above, do NOT inject the publisher when
        # disabled. This prevents accidental activation from a
        # pre-loaded publisher reference.
        return

    if publisher is not None:
        set_eventbridge_publisher(publisher)

    @mcp_app.tool()
    async def publish_to_eventbridge(
        topic: str,
        payload: dict[str, Any],
        async_callback: bool = False,
    ) -> dict[str, Any]:
        """Publish an event to the Crackerjack EventBridge stream.

        Args:
            topic: One of ``test.started``, ``test.completed``, ``test.failed``.
            payload: Event payload dict (must match the topic's schema).
            async_callback: If true, return immediately with a workflow_id
                and run the publish in the background.

        Returns:
            Dict with one of:
            - ``{"status": "published"}`` (sync, enabled)
            - ``{"workflow_id": "<uuid>", "status": "queued"}`` (async, enabled)
            - ``{"status": "disabled"}`` (when ``enabled=False`` at registration;
              tool is not registered and direct calls bypass the gate, so
              this branch is only reachable if registered-disabled behavior
              is added later).
        """
        if async_callback:
            import asyncio

            workflow_id = f"pub_{uuid.uuid4().hex[:12]}"
            asyncio.create_task(_dispatch_topic(topic, payload))
            return {"workflow_id": workflow_id, "status": "queued"}

        await _dispatch_topic(topic, payload)
        return {"status": "published"}


__all__ = ["register_eventbridge_tools", "set_eventbridge_publisher"]
```

- [x] **Step 3: Update `crackerjack/mcp/tools/__init__.py`**

Read the file first. Add an export for the new module. The convention is one line per tool group. Insert:

```python
from crackerjack.mcp.tools.eventbridge_tools import register_eventbridge_tools
```

If the file uses a different style (e.g. `__all__` listing), match that style.

- [x] **Step 4: Update `crackerjack/mcp/server_core.py`**

Find the `create_mcp_server` function (around line 157) and the block where tool groups are registered (lines 227-244 according to the scout). Add a call to `register_eventbridge_tools` at the appropriate place — typically after the existing `register_*_tools(mcp_app)` calls. **The call MUST pass `enabled=cfg.eventbridge.enabled`** from the loaded `CrackerjackSettings` (per operational-safety Finding #8). If a publisher is wired through app config, also pass it as `publisher=app.event_publisher`.

```python
def create_mcp_server(config):
    # ...existing registrations...
    from crackerjack.config import CrackerjackSettings
    settings = CrackerjackSettings()
    register_eventbridge_tools(
        mcp_app,
        publisher=getattr(app, "event_publisher", None),
        enabled=settings.eventbridge.enabled,
    )
    # ...more registrations...
```

If `create_mcp_server` already takes a settings object, read `eventbridge.enabled` from it directly. The default when no config is loaded is `enabled=False` (per the `CrackerjackSettings` defaults), so the tool is a no-op until the operator explicitly enables it.

- [x] **Step 5: Run the existing tests**

Run: `cd /Users/les/Projects/crackerjack && pytest tests/unit/ -x -q --timeout=120`
Expected: All existing tests pass.

- [x] **Step 6: Verify ruff is clean**

Run: `cd /Users/les/Projects/crackerjack && ruff check crackerjack/mcp/tools/eventbridge_tools.py crackerjack/mcp/tools/__init__.py crackerjack/mcp/server_core.py`
Expected: `All checks passed!`

- [x] **Step 7: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/mcp/tools/eventbridge_tools.py crackerjack/mcp/tools/__init__.py crackerjack/mcp/server_core.py
git commit -m "feat(mcp): expose publish_to_eventbridge MCP tool

Allows Claude Code and other MCP clients to publish test lifecycle
events to the unified Bodai EventBridge. Supports sync and async
(async_callback=true) modes mirroring mahavishnu.dispatch_to_pool."
```

______________________________________________________________________

## Task 7: Integration test — end-to-end envelope round-trip

**Files:**

- Create: `tests/integration/test_eventbridge_e2e.py`

**Interfaces:**

- Consumes: `publish_test_started`, `publish_test_completed`, `publish_test_failed`

- Produces: 4 integration tests verifying that envelopes flow from publish call through a fake transport and back as a parsed dict.

- [x] **Step 1: Create the integration test file**

Write `tests/integration/test_eventbridge_e2e.py`:

```python
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
        "run_seq", tests_completed=10, tests_failed=0, duration_seconds=1.0,
        publisher=transport,
    )
    await publish_test_failed(
        "run_seq", "test_x", "boom", "tb", publisher=transport
    )

    assert [r["topic"] for r in transport.published] == [
        "test.started",
        "test.completed",
        "test.failed",
    ]
    event_ids = [r["headers"]["event_id"] for r in transport.published]
    assert len(set(event_ids)) == 3, "event_ids must be unique across publishes"
```

- [x] **Step 2: Run the integration tests**

Run: `cd /Users/les/Projects/crackerjack && pytest tests/integration/test_eventbridge_e2e.py -v --timeout=120`
Expected: All 4 tests pass.

- [x] **Step 3: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add tests/integration/test_eventbridge_e2e.py
git commit -m "test(eventbridge): add end-to-end round-trip integration tests

Verifies canonical envelope shape survives transport. Uses an in-memory
RecordingTransport; no Redis required. Covers started/completed/failed
plus a sequential-publish uniqueness check."
```

______________________________________________________________________

## Task 8: Cross-repo smoke test (manual verification)

**Files:**

- None. This task is a manual verification step against a running Mahavishnu subscriber.

**Step 8.1: Run the Mahavishnu subscriber in one terminal**

Open a terminal in `/Users/les/Projects/mahavishnu` and start the Bodai subscriber:

```bash
cd /Users/les/Projects/mahavishnu
python -m crackerjack  # or whatever the local invocation is
```

In another terminal, manually invoke `publish_test_started`:

```bash
cd /Users/les/Projects/crackerjack
python -c "
import asyncio
from crackerjack.core.eventbridge_publisher import publish_test_started

async def main():
    await publish_test_started(
        'run_smoke', 'tests/unit', total_tests=42, publisher=None  # no-op since publisher=None
    )

asyncio.run(main())
print('OK')
"
```

Expected: `OK` prints, no errors.

(This is a smoke test, not a real e2e against a live EventBridge — that requires Mahavishnu running in the same Redis. The full e2e verification is a separate task, not in scope here.)

- [x] **Step 1: Confirm the smoke test passes**

Run: `cd /Users/les/Projects/crackerjack && python -c "import asyncio; from crackerjack.core.eventbridge_publisher import publish_test_started; asyncio.run(publish_test_started('run_smoke', 'tests/unit', total_tests=42)); print('OK')"`
Expected: `OK`

- [x] **Step 2: Final commit (if any cleanup needed)**

If any documentation updates are needed (e.g. adding a note to `CLAUDE.md` about the publisher), commit them here. Otherwise skip — this is the close-out task.

______________________________________________________________________

## Integration Contract

- **Triggered from:** `PhaseCoordinator.run_hooks_phase / run_fast_hooks_only / run_snob_tests_phase / run_comprehensive_hooks_only` (Task 5) AND `publish_to_eventbridge` MCP tool (Task 6).
- **Returns to / updates:** None directly. Envelopes flow into Oneiric EventBridge → Mahavishnu Bodai subscriber → `~/.mahavishnu/bodai-event-queue.json` → Claude Code `/bodai-status` and PostToolUse hook.
- **Demonstrable by:** Run `pytest tests/unit/test_eventbridge_publisher.py tests/unit/test_eventbridge_adapter.py tests/integration/test_eventbridge_e2e.py -v` from Crackerjack; all 23 tests pass (2 adapter + 17 publisher unit + 4 integration). Plus a manual smoke test invoking `publish_test_started` from a Python REPL.
- **Rollback signal:** None — the publisher is non-destructive. Disable by passing `event_publisher=None` at `PhaseCoordinator` construction (the default), or set `eventbridge.enabled=false` in settings (the YAML toggle is checked by future wiring, not by this plan).
- **Observability added:** `crackerjack.publisher` logger emits WARNING-or-higher records on publish failure (test introspection via `caplog`).

## References

- `mahavishnu/core/events/mahavishnu_publisher.py` — pattern mirrored 1:1
- `tests/unit/test_mahavishnu_publisher.py` — test pattern mirrored
- `mahavishnu/core/events/bodai_subscriber.py` — consumer-side; the wire format this publisher emits
- `oneiric.runtime.events.EventEnvelope` / `create_event_envelope` — canonical envelope (msgspec.Struct, three fields: `topic`, `payload`, `headers`)
- `.claude/decisions/bodai-observability-pattern.md` (in mahavishnu repo) — the convergence rule this publisher implements
- `docs/plans/2026-07-11-phase-6-bodai-observability.md` — Phase 6 close-out context
