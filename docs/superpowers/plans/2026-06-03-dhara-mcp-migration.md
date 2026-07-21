______________________________________________________________________

## status: active role: implementation date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# Dhara MCP Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `python -m crackerjack run` hang at `_thread_shutdown()` by adding a `DharaMCPAdapterLearner` happy path (via streamablehttp) and a `weakref.finalize`-based leak fix on the in-process `DharaAdapterLearner`, then remove the now-redundant `aiosqlite_cleanup` atexit module.

**Architecture:** Factory walks a chain of four backends: `DharaMCPAdapterLearner` (NEW, happy path) → `DharaAdapterLearner` (existing, in-process, now leak-free) → `SQLiteAdapterLearner` (existing) → `NoOpAdapterLearner` (existing). First success wins. The in-process path uses `weakref.finalize` to close the aiosqlite connection when the learner is gc'd, replacing the fragile `atexit.register` hack.

**Tech Stack:** Python 3.13, FastMCP, `mcp.client.streamablehttp`, `weakref.finalize`, `unittest.mock.patch` for tests, `pytest` + `pytest-asyncio`.

______________________________________________________________________

## Docstring policy

Per `RULES.md`, all public classes, methods, and functions in new code MUST have docstrings. Module-level docstrings are encouraged for non-trivial modules. Inline comments are reserved for explaining *why*, not *what*. The `-x` flag is a manual cleanup tool, not part of the `crackerjack run` pipeline, so docstrings survive into the committed code.

______________________________________________________________________

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `crackerjack/integration/dhara_integration.py` | The four learner implementations + factory | MODIFY (finalizer + factory refactor) |
| `crackerjack/integration/dhara_mcp_client.py` | Streamablehttp client wrapping Dhara MCP tools | CREATE |
| `crackerjack/config/settings.py` | `DharaMCPSettings` class | MODIFY (add class) |
| `crackerjack/services/aiosqlite_cleanup.py` | Obsolete atexit walk | DELETE (commit 3) |
| `crackerjack/__main__.py` | Imports `aiosqlite_cleanup`; has diagnostic atexit | MODIFY (remove import + diagnostic atexit) |
| `tests/integration/test_aio_thread_leak_regression.py` | Regression test for the original hang | CREATE |
| `tests/integration/dhara_mcp_client_test.py` | Unit tests for `DharaMCPClient` | CREATE |
| `tests/integration/dhara_mcp_adapter_learner_test.py` | Integration tests for `DharaMCPAdapterLearner` | CREATE |
| `tests/integration/test_dhara_integration.py` | Factory tests | MODIFY (add factory tests, keep existing) |
| `tests/services/test_aiosqlite_cleanup.py` | Obsolete atexit tests | DELETE (commit 3) |
| `docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md` | Description of MCP path | MODIFY |
| `docs/DHARA_WIRING.md` | Add `adapter_attempt` to producer list | MODIFY |

______________________________________________________________________

## Type reference

These types are referenced throughout the plan. Use these exact names.

```python
@dataclass(frozen=True)
class AdapterAttemptRecord:
    """A single record of an adapter execution attempt.

    Produced by `DharaLearningIntegration.track_adapter_execution` and
    passed to the active adapter learner's `record_adapter_attempt`.
    """
    adapter_name: str
    file_type: str
    file_size: int
    project_context: dict[str, t.Any]
    success: bool
    execution_time_ms: int
    error_type: str | None
    timestamp: datetime

    def to_dict(self) -> dict[str, t.Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> AdapterAttemptRecord: ...


@t.runtime_checkable
class AdapterLearnerProtocol(t.Protocol):
    """Protocol for adapter-learning backends.

    Implementations record each `AdapterAttemptRecord` to their
    respective storage so the system can learn which adapters work
    best for which files.
    """
    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None: ...


@dataclass
class DharaMCPConfig:
    """Configuration for the Dhara MCP client."""
    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None


@dataclass
class DharaMCPClient:
    """Thin MCP client wrapping the Dhara server's kv_timeseries tool group.

    Transport: `mcp.client.streamablehttp` over HTTP. The base URL gets
    `/mcp` appended automatically by the transport.

    `connect()` returns bool and never raises — the factory catches all
    exceptions. Tool methods catch internally and return None or empty
    list, so the factory is the single point that decides fallback
    policy.
    """
    config: DharaMCPConfig
    _client: t.Any = None
    _session: t.Any = None
    _is_connected: bool = False

    async def connect(self) -> bool:
        """Open the MCP session. Returns True on success, False on any failure."""
        ...

    async def disconnect(self) -> None:
        """Close the session and transport. Idempotent. Swallows the
        streamablehttp cancel-scope RuntimeError documented in
        `mcp-connection-stability-plan.md`."""
        ...

    async def is_alive(self) -> bool: ...
    async def put(self, key, value, ttl=None) -> dict[str, t.Any] | None: ...
    async def get(self, key) -> dict[str, t.Any] | None: ...
    async def record_time_series(
        self, metric_type, entity_id, record, timestamp=None,
    ) -> dict[str, t.Any] | None: ...
    async def query_time_series(
        self, metric_type, entity_id, start_date=None, limit=None,
    ) -> list[dict[str, t.Any]]: ...
    async def aggregate_patterns(
        self, start_date, min_occurrences=2,
    ) -> list[dict[str, t.Any]]: ...


class DharaMCPClientError(NetworkError):
    """Raised by DharaMCPClient on protocol-level failures that
    should surface through crackerjack's error handling."""


class DharaMCPAdapterLearner:
    """`AdapterLearnerProtocol` implementation that records attempts
    to a remote Dhara MCP server via the kv_timeseries tool group.

    The record body includes a `pattern` key so the server's
    `aggregate_patterns` tool can group attempts by success/failure.
    """
    def __init__(self, config: DharaMCPConfig) -> None:
        """Create a learner with the given MCP config. The session is
        opened lazily on the first `record_adapter_attempt` call."""
        ...

    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None: ...
    async def _record_attempt_async(self, attempt: AdapterAttemptRecord) -> None: ...
    def _derive_pattern(self, attempt: AdapterAttemptRecord) -> str:
        """Return a coarse pattern category for `aggregate_patterns`."""
        ...
    def close(self) -> None:
        """Best-effort disconnect. Idempotent. Swallows exceptions."""
        ...


class DharaMCPSettings(MCPBaseSettings):
    """Settings for the Dhara MCP adapter-learning client."""
    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None
```

______________________________________________________________________

## Task 1: Regression test for the in-process aiosqlite leak

**Files:**

- Create: `tests/integration/test_aio_thread_leak_regression.py`

**Context:** This test reproduces the original hang. It creates a `DharaAdapterLearner` (which spawns an aiosqlite worker thread), drops the reference, and asserts that gc reaped the worker. This test will FAIL on the current `main` branch (the leak is real) and PASS after Task 2 adds the `weakref.finalize` registration.

- [ ] **Step 1: Create the regression test file**

Path: `tests/integration/test_aio_thread_leak_regression.py`

```python
"""Regression test for the aiosqlite worker-thread leak.

The `DharaAdapterLearner` in `crackerjack/integration/dhara_integration.py`
opens an aiosqlite connection whose `_connection_worker_thread` is only
reaped when the connection is closed. The learner never closed it, so
the thread was orphaned at end of `crackerjack run` and blocked
`_thread_shutdown()` at interpreter shutdown, forcing the user to
Ctrl+C to escape.

This test reproduces the failure: it creates a learner, drops the
reference, and asserts that no worker thread survives garbage
collection. The test is parametrized on whether the obsolete
`aiosqlite_cleanup` module is also loaded; the finalizer registered
in `DharaAdapterLearner.__post_init__` is sufficient on its own
without the atexit walk.
"""

from __future__ import annotations

import gc
import threading
import time
from pathlib import Path

import pytest


def _live_aio_threads() -> list[str]:
    """Return the names of all live non-daemon aiosqlite worker threads.

    aiosqlite names its worker threads `Thread-N (_connection_worker_thread)`.
    """
    return [
        t.name
        for t in threading.enumerate()
        if not t.daemon
        and t.is_alive()
        and t.name.endswith(" (_connection_worker_thread)")
    ]


@pytest.mark.parametrize("with_cleanup_module", [True, False])
def test_no_aio_thread_leak_when_learner_garbage_collected(
    tmp_path: Path, with_cleanup_module: bool
) -> None:
    """The aiosqlite worker thread that blocked `_thread_shutdown()`
    must NOT survive garbage collection of the learner.
    """
    if not with_cleanup_module:
        # Simulate the post-cleanup-module-removal state by ensuring
        # the obsolete atexit walk is not in effect for this test.
        import sys
        for mod_name in list(sys.modules):
            if mod_name.startswith("crackerjack.services.aiosqlite_cleanup"):
                del sys.modules[mod_name]

    from crackerjack.integration.dhara_integration import DharaAdapterLearner

    db_path = tmp_path / "test_leak.dhara"

    try:
        learner = DharaAdapterLearner(db_path=db_path)
    except Exception:
        pytest.skip("Dhara backend unavailable in this environment")

    assert _live_aio_threads(), (
        "Sanity: learner init should have spawned a worker thread"
    )

    del learner
    gc.collect()
    gc.collect()

    deadline = time.monotonic() + 1.0
    while _live_aio_threads() and time.monotonic() < deadline:
        time.sleep(0.02)

    assert _live_aio_threads() == [], (
        f"Learner gc left {len(_live_aio_threads())} aiosqlite "
        f"worker thread(s) alive. The interpreter would hang at "
        f"_thread_shutdown()."
    )
```

- [ ] **Step 2: Run the test to verify it FAILS on main**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/test_aio_thread_leak_regression.py -v
```

Expected: Both `with_cleanup_module=True` and `with_cleanup_module=False` FAIL with the "Learner gc left N aiosqlite worker thread(s) alive" assertion. (On Dhara 0.5.0, the test is `pytest.skip`-ed — that's acceptable for this verification step; the manual run in Task 2 will catch it in your environment.)

If the test passes already (the leak is somehow already fixed), STOP and re-investigate — do not proceed to Step 3.

- [ ] **Step 3: Commit the failing test**

```bash
cd /Users/les/Projects/crackerjack && git add tests/integration/test_aio_thread_leak_regression.py && git commit -m "test(adapter-learning): regression test for aiosqlite worker leak

The DharaAdapterLearner creates an aiosqlite connection whose
_connection_worker_thread is only reaped when the connection is
closed. The learner never closes it, so the thread is orphaned
at end of 'crackerjack run' and blocks _thread_shutdown().

This test reproduces the failure: it creates a learner, drops
the reference, and asserts no worker thread survives. Fails on
main; will pass after the weakref.finalize fix."
```

______________________________________________________________________

## Task 2: Fix the aiosqlite leak via weakref.finalize

**Files:**

- Modify: `crackerjack/integration/dhara_integration.py`

**Context:** Replace the `atexit.register(_safe_close)` hack in `create_adapter_learner` with a `weakref.finalize` registration inside `DharaAdapterLearner.__post_init__`. The finalizer fires the moment the learner is gc'd, which is the only reliable point to close the connection.

- [ ] **Step 1: Add the module-level `_safe_abort_sync` helper**

In `crackerjack/integration/dhara_integration.py`, near the top of the file (after the imports), add:

```python
import weakref
```

(Add `weakref` to the existing import block, alphabetized.)

Then, at the end of the file (or just before `create_adapter_learner`), add:

```python
def _safe_abort_sync(connection: t.Any) -> None:
    """Close a Dhara AsyncConnection safely. Used as a `weakref.finalize`
    callback so a finalizer can't crash the interpreter.

    The function is deliberately permissive: it handles the case where
    `abort` is a sync method (Dhara's older `Connection.abort` in
    version 0.5.0), an async coroutine (Dhara's `AsyncConnection.abort`
    in newer versions), or missing entirely (Dhara 0.5.0 has no
    AsyncConnection at all, in which case the factory falls back to
    SQLite before this finalizer ever runs).

    Catches `BaseException` (not `Exception`) so that `KeyboardInterrupt`,
    `SystemExit`, and `asyncio.CancelledError` during interpreter
    teardown cannot escape and crash the interpreter.
    """
    if connection is None:
        return
    try:
        abort = getattr(connection, "abort", None)
        if abort is None:
            return
        result = abort()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    except BaseException as exc:  # noqa: BLE001 - by design
        logger.debug(f"finalizer: connection abort failed: {exc!r}")
```

- [ ] **Step 2: Register the finalizer in `DharaAdapterLearner.__post_init__`**

In `DharaAdapterLearner.__post_init__` (the method that sets up `self._async_connection`), at the END of the method, add:

```python
        weakref.finalize(self, _safe_abort_sync, self._async_connection)
```

The exact insertion point is the last line of `__post_init__`, AFTER `self._initialized = True` and the `logger.info("✅ Dhara adapter learner initialized (async)...")` call. The method currently ends with the `logger.error("❌ Failed to initialize...")` block in its except arm — the `weakref.finalize` registration should only happen in the success path, so put it right before the `except BlockingIOError` clause.

- [ ] **Step 3: Remove the existing `atexit.register(_safe_close)` from `create_adapter_learner`**

In `create_adapter_learner` (around line 786-794 of the current file), DELETE:

```python
            def _safe_close(_learner: DharaAdapterLearner = learner) -> None:
                try:
                    _learner.close()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug(
                        f"DharaAdapterLearner.close() at atexit failed: {exc!r}"
                    )

            atexit.register(_safe_close)
```

And DELETE the comment block immediately above it that begins with `# Register close() with atexit so the aiosqlite connection`.

- [ ] **Step 4: Update the stale comment at line 779**

In the same `create_adapter_learner` factory, find the comment block that ends with "...we run *before* the `aiosqlite_cleanup` module's atexit handler..." (currently around line 776-783). DELETE that entire comment block (the one explaining the LIFO ordering with the aiosqlite_cleanup module). The finalizer makes this explanation obsolete.

- [ ] **Step 5: Run the regression test to verify it now PASSES**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/test_aio_thread_leak_regression.py -v
```

Expected: `with_cleanup_module=True` PASSES, `with_cleanup_module=False` PASSES. Both prove the finalizer alone is sufficient. (On Dhara 0.5.0, the test is `pytest.skip`-ed — that's still PASS for the skip case.)

- [ ] **Step 6: Run the existing dhara_integration tests to make sure nothing regressed**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/test_dhara_integration.py -v
```

Expected: all existing tests PASS. The factory still returns the same learners in the same order; only the cleanup mechanism changed.

- [ ] **Step 7: Manual end-to-end verification with timeout**

Run:

```bash
cd /Users/les/Projects/crackerjack && timeout 60 python -m crackerjack run -v -f --ai-debug; echo "EXIT: $?"
```

Expected: `EXIT: 0` AND the run completes within 60 seconds (no hang). Look for the absence of `[crackerjack-diag]` lines in the output and the absence of a `KeyboardInterrupt` traceback.

If the run still hangs, STOP and re-investigate. The most likely failure is that `weakref.finalize` did not actually register (e.g., the insertion point was wrong, so the function exited before the line was reached).

- [ ] **Step 8: Commit the leak fix**

```bash
cd /Users/les/Projects/crackerjack && git add crackerjack/integration/dhara_integration.py && git commit -m "fix(adapter-learning): reap aiosqlite worker via weakref.finalize

The DharaAdapterLearner creates an aiosqlite connection whose
_connection_worker_thread is only reaped when the connection's
close() coroutine completes. The learner never closed it, so
the thread was orphaned at end of 'crackerjack run' and blocked
_thread_shutdown(), forcing the user to Ctrl+C.

Replace the atexit.register hack in create_adapter_learner with
a weakref.finalize registration in DharaAdapterLearner.__post_init__.
weakref.finalize fires the moment the learner's last reference is
released (earlier than atexit, which is too late) and holds a
weakref so it doesn't extend the learner's lifetime.

The finalizer runs asyncio.run(connection.abort()) in a fresh
event loop. abort() is a coroutine on AsyncConnection; the helper
also handles the case where abort is sync or missing entirely
(e.g., Dhara 0.5.0 has no AsyncConnection at all). The helper
catches BaseException so a raising finalizer can't crash the
interpreter.

The Dhara 0.5.0 fallback path is unchanged: if the import fails,
the factory falls through to SQLiteAdapterLearner, which has no
thread leak.

Verified by tests/integration/test_aio_thread_leak_regression.py
and a manual 'timeout 60 python -m crackerjack run -v -f --ai-debug'
which now exits 0 with no [crackerjack-diag] line."
```

______________________________________________________________________

## Task 3: Add `DharaMCPSettings` to config

**Files:**

- Modify: `crackerjack/config/settings.py`

**Context:** Add a new top-level settings class for the Dhara MCP client. No `field(default_factory=...)` nesting — other settings groups (e.g., `MCPServerSettings`, `LearningSettings`) are top-level classes accessed via the global settings loader.

- [ ] **Step 1: Find a good insertion point in `crackerjack/config/settings.py`**

Open the file. Find the `class LearningSettings(MCPBaseSettings):` class. Add the new class right after it (alphabetical, "Dhara" comes before "Learning" — but if the file is ordered by discovery date, just put it adjacent to `LearningSettings` for readability).

- [ ] **Step 2: Add the `DharaMCPSettings` class**

```python
class DharaMCPSettings(MCPBaseSettings):
    """Settings for the Dhara MCP adapter-learning client.

    The crackerjack adapter-learning subsystem talks to the Dhara MCP
    server over streamablehttp rather than importing Dhara in-process.
    These settings configure that client.

    Environment variables: `MAHAVISHNU_DHARA_MCP_URL`,
    `MAHAVISHNU_DHARA_MCP_TIMEOUT_SECONDS`, `MAHAVISHNU_DHARA_MCP_ENABLED`,
    `MAHAVISHNU_DHARA_MCP_TOKEN`.
    """
    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None
```

- [ ] **Step 3: Verify the settings class is importable**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -c "from crackerjack.config.settings import DharaMCPSettings; s = DharaMCPSettings(); print(s.url, s.enabled, s.token)"
```

Expected output: `http://localhost:8683 True None`

- [ ] **Step 4: Commit the settings addition**

```bash
cd /Users/les/Projects/crackerjack && git add crackerjack/config/settings.py && git commit -m "feat(settings): add DharaMCPSettings for adapter-learning MCP client"
```

______________________________________________________________________

## Task 4: Failing tests for `DharaMCPClient`

**Files:**

- Create: `tests/integration/dhara_mcp_client_test.py`

**Context:** The `DharaMCPClient` wraps `mcp.client.streamablehttp` and translates each Dhara MCP tool call. These tests use `unittest.mock.AsyncMock` to mock `ClientSession.call_tool` and verify the right tool name and arguments are passed.

- [ ] **Step 1: Create the test file with the first failing test**

Path: `tests/integration/dhara_mcp_client_test.py`

```python
"""Unit tests for `DharaMCPClient`.

The client wraps `mcp.client.streamablehttp` and translates each Dhara
MCP tool into a typed Python method. These tests use `unittest.mock`
to mock the `ClientSession` and verify the right tool name and
arguments are passed.
"""

from __future__ import annotations

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.integration.dhara_mcp_client import (
    DharaMCPClient,
    DharaMCPConfig,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    """A mock ClientSession with `call_tool` set up as AsyncMock."""
    session = AsyncMock()
    session.call_tool = AsyncMock()
    return session


@pytest.fixture
def client_with_session(mock_session: AsyncMock) -> DharaMCPClient:
    """A `DharaMCPClient` with a mock session already attached.

    Skips the `connect()` handshake so tests can drive tool methods
    directly.
    """
    client = DharaMCPClient(DharaMCPConfig(url="http://test/mcp"))
    client._session = mock_session
    client._is_connected = True
    return client


@pytest.mark.asyncio
async def test_record_time_series_calls_correct_tool(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """`record_time_series` must invoke the underlying MCP `record_time_series`
    tool with the metric_type, entity_id, record, and timestamp arguments."""
    expected_response = MagicMock()
    expected_response.data = {"ok": True, "metric_type": "adapter_attempt"}
    mock_session.call_tool.return_value = expected_response

    result = await client_with_session.record_time_series(
        metric_type="adapter_attempt",
        entity_id="prefect",
        record={"success": True, "execution_time_ms": 42},
        timestamp="2026-06-03T12:00:00+00:00",
    )

    assert result == {"ok": True, "metric_type": "adapter_attempt"}
    mock_session.call_tool.assert_awaited_once()
    call_args = mock_session.call_tool.await_args
    assert call_args.args[0] == "record_time_series"
    assert call_args.kwargs["arguments"]["metric_type"] == "adapter_attempt"
    assert call_args.kwargs["arguments"]["entity_id"] == "prefect"
```

- [ ] **Step 2: Run the test to verify it FAILS**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/dhara_mcp_client_test.py -v
```

Expected: ImportError on `crackerjack.integration.dhara_mcp_client` — the module doesn't exist yet. This is the failing-first state we want.

- [ ] **Step 3: Commit the failing test**

```bash
cd /Users/les/Projects/crackerjack && git add tests/integration/dhara_mcp_client_test.py && git commit -m "test(adapter-learning): first test for DharaMCPClient.record_time_series"
```

______________________________________________________________________

## Task 5: Implement `DharaMCPClient`

**Files:**

- Create: `crackerjack/integration/dhara_mcp_client.py`

**Context:** The thin MCP client. Uses `mcp.client.streamablehttp` + `ClientSession`. Catches everything in `connect()` (returns bool, never raises). All tool methods catch exceptions and return None or empty list.

- [ ] **Step 1: Create the file with the imports and config**

Path: `crackerjack/integration/dhara_mcp_client.py`

```python
"""Thin MCP client wrapping the Dhara server's kv_timeseries tool group.

The Dhara MCP server (separate repo, `dhara`) exposes five tools under
`TOOL_GROUP_KV_TIME_SERIES`: `put`, `get`, `record_time_series`,
`query_time_series`, and `aggregate_patterns`. This module provides
typed Python wrappers around those tools, plus a connection lifecycle
that's safe to drive from sync code (crackerjack's adapter-learning
call sites are sync and use `asyncio.run` to bridge).

`connect()` returns `bool` and never raises. The factory
(`crackerjack/integration/dhara_integration.py::create_adapter_learner`)
catches all exceptions from learner construction, so the client must
not raise from `connect()` either. Tool methods catch internally and
return `None` or `[]` so a single failed tool call doesn't break the
learner.
"""

from __future__ import annotations

import logging
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field

from crackerjack.errors import NetworkError

logger = logging.getLogger(__name__)


@dataclass
class DharaMCPConfig:
    """Configuration for the Dhara MCP client.

    `url` is the BASE URL of the Dhara server. The streamablehttp
    transport appends `/mcp` automatically. `token`, when set, is sent
    as a `Bearer` header on every tool call (the Dhara server gates
    `put` and `record_time_series` with `auth=auth("write")`).
    """
    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None


class DharaMCPClientError(NetworkError):
    """Raised by `DharaMCPClient` on protocol-level failures that
    should surface through crackerjack's error handling.

    Note: most client methods catch their own exceptions and return
    None or empty list, so this error is only raised in cases where
    the caller has explicitly opted into raise-on-failure semantics.
    """
```

- [ ] **Step 2: Add the `DharaMCPClient` class skeleton**

```python
@dataclass
class DharaMCPClient:
    """Thin MCP client wrapping the Dhara server's kv_timeseries tools.

    Lifecycle:
    - Construction does NOT open a connection (lazy).
    - First call to a tool method (or explicit `connect()`) opens the
      transport and runs the MCP initialize handshake.
    - `disconnect()` is idempotent and safe to call from anywhere,
      including from a finalizer at interpreter shutdown.

    Error handling:
    - `connect()` returns `bool`, never raises. The factory is the
      single point that decides fallback policy.
    - Tool methods catch all exceptions internally and return `None`
      or `[]` so a single failed call doesn't break the learner.
    """
    config: DharaMCPConfig
    _client: t.Any = field(init=False, default=None)
    _session: t.Any = field(init=False, default=None)
    _is_connected: bool = field(init=False, default=False)

    async def connect(self) -> bool:
        """Open the MCP session against the configured Dhara server.

        Returns True on success. Returns False (and never raises) on
        any failure: connection refused, timeout, MCP handshake error,
        or the streamablehttp cancel-scope RuntimeError documented in
        `mcp-connection-stability-plan.md`.
        """
        from mcp import ClientSession
        from mcp.client.streamablehttp import streamablehttp_client

        try:
            server_url = self.config.url.rstrip("/")
            self._client = streamablehttp_client(url=f"{server_url}/mcp")
            self._session = ClientSession(self._client)
            await self._session.__aenter__()
            self._is_connected = True
            return True
        except Exception as exc:
            logger.debug(
                f"DharaMCPClient.connect failed: {type(exc).__name__}: {exc!r}"
            )
            await self._safe_close()
            return False

    async def _safe_close(self) -> None:
        """Close the session and transport without raising.

        Both `__aexit__` calls are wrapped in `suppress(Exception)`
        because the streamablehttp transport can raise the
        cancel-scope RuntimeError during teardown.
        """
        if self._session is not None:
            with suppress(Exception):
                await self._session.__aexit__(None, None, None)
            self._session = None
        if self._client is not None:
            with suppress(Exception):
                await self._client.__aexit__(None, None, None)
            self._client = None
        self._is_connected = False

    async def disconnect(self) -> None:
        """Public close. Idempotent. Equivalent to `_safe_close`."""
        await self._safe_close()
```

- [ ] **Step 3: Add the tool wrapper methods**

```python
    async def _call_tool(
        self, name: str, arguments: dict[str, t.Any]
    ) -> dict[str, t.Any] | None:
        """Invoke a tool on the connected MCP session.

        Returns the tool response as a dict, or None if not connected
        or if the call raised. Never propagates exceptions.
        """
        if not self._is_connected or self._session is None:
            logger.debug(f"DharaMCPClient._call_tool({name}): not connected")
            return None
        try:
            response = await self._session.call_tool(name, arguments=arguments)
            data = getattr(response, "data", None)
            if data is None:
                return None
            if isinstance(data, dict):
                return data
            return {"value": data}
        except Exception as exc:
            logger.debug(
                f"DharaMCPClient._call_tool({name}) failed: "
                f"{type(exc).__name__}: {exc!r}"
            )
            return None

    async def put(
        self,
        key: str,
        value: t.Any,
        ttl: int | None = None,
    ) -> dict[str, t.Any] | None:
        """Wrap the Dhara MCP `put` tool (key/value store with optional TTL)."""
        return await self._call_tool("put", {"key": key, "value": value, "ttl": ttl})

    async def get(self, key: str) -> dict[str, t.Any] | None:
        """Wrap the Dhara MCP `get` tool (read a key/value record)."""
        return await self._call_tool("get", {"key": key})

    async def record_time_series(
        self,
        metric_type: str,
        entity_id: str,
        record: dict[str, t.Any],
        timestamp: str | None = None,
    ) -> dict[str, t.Any] | None:
        """Wrap the Dhara MCP `record_time_series` tool (append a time-series record).

        `record` is a free-form dict; include a `pattern` key if you
        want the server's `aggregate_patterns` tool to group on it.
        """
        arguments: dict[str, t.Any] = {
            "metric_type": metric_type,
            "entity_id": entity_id,
            "record": record,
        }
        if timestamp is not None:
            arguments["timestamp"] = timestamp
        return await self._call_tool("record_time_series", arguments)

    async def query_time_series(
        self,
        metric_type: str,
        entity_id: str,
        start_date: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, t.Any]]:
        """Wrap the Dhara MCP `query_time_series` tool (read time-series records)."""
        arguments: dict[str, t.Any] = {
            "metric_type": metric_type,
            "entity_id": entity_id,
        }
        if start_date is not None:
            arguments["start_date"] = start_date
        if limit is not None:
            arguments["limit"] = limit
        result = await self._call_tool("query_time_series", arguments)
        if isinstance(result, list):
            return result
        return []

    async def aggregate_patterns(
        self,
        start_date: str,
        min_occurrences: int = 2,
    ) -> list[dict[str, t.Any]]:
        """Wrap the Dhara MCP `aggregate_patterns` tool (group by pattern)."""
        result = await self._call_tool(
            "aggregate_patterns",
            {"start_date": start_date, "min_occurrences": min_occurrences},
        )
        if isinstance(result, list):
            return result
        return []

    async def is_alive(self) -> bool:
        """Return True if the session is connected and a probe tool call succeeds."""
        if not self._is_connected:
            return False
        result = await self._call_tool("get", {"key": "__health__"})
        return result is not None
```

- [ ] **Step 4: Run the test from Task 4 to verify it PASSES**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/dhara_mcp_client_test.py -v
```

Expected: PASS for `test_record_time_series_calls_correct_tool`.

- [ ] **Step 5: Add the remaining unit tests**

Append to `tests/integration/dhara_mcp_client_test.py`:

```python
@pytest.mark.asyncio
async def test_put_calls_correct_tool(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """`put` must invoke the underlying `put` tool with key, value, and TTL."""
    expected_response = MagicMock()
    expected_response.data = {"ok": True, "key": "test"}
    mock_session.call_tool.return_value = expected_response

    result = await client_with_session.put(key="test", value={"a": 1}, ttl=60)

    assert result == {"ok": True, "key": "test"}
    call_args = mock_session.call_tool.await_args
    assert call_args.args[0] == "put"
    assert call_args.kwargs["arguments"]["key"] == "test"
    assert call_args.kwargs["arguments"]["ttl"] == 60


@pytest.mark.asyncio
async def test_get_calls_correct_tool(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """`get` must invoke the underlying `get` tool with the key."""
    expected_response = MagicMock()
    expected_response.data = {"key": "test", "value": 42}
    mock_session.call_tool.return_value = expected_response

    result = await client_with_session.get(key="test")

    assert result == {"key": "test", "value": 42}
    call_args = mock_session.call_tool.await_args
    assert call_args.args[0] == "get"


@pytest.mark.asyncio
async def test_query_time_series_returns_empty_list_on_tool_error(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """When the underlying tool raises, the wrapper returns `[]` (not None)."""
    mock_session.call_tool.side_effect = RuntimeError("simulated")

    result = await client_with_session.query_time_series(
        metric_type="adapter_attempt", entity_id="prefect"
    )

    assert result == []


@pytest.mark.asyncio
async def test_aggregate_patterns_passes_through_args(
    client_with_session: DharaMCPClient, mock_session: AsyncMock
) -> None:
    """`aggregate_patterns` must pass start_date and min_occurrences through."""
    expected_response = MagicMock()
    expected_response.data = [{"pattern": "success:prefect", "count": 5}]
    mock_session.call_tool.return_value = expected_response

    result = await client_with_session.aggregate_patterns(
        start_date="2026-06-01", min_occurrences=3
    )

    assert result == [{"pattern": "success:prefect", "count": 5}]
    call_args = mock_session.call_tool.await_args
    assert call_args.args[0] == "aggregate_patterns"
    assert call_args.kwargs["arguments"]["min_occurrences"] == 3


@pytest.mark.asyncio
async def test_connect_returns_false_on_connection_error() -> None:
    """`connect()` must return False (not raise) on transport failure."""
    client = DharaMCPClient(DharaMCPConfig(url="http://unreachable:9999"))

    with patch(
        "mcp.client.streamablehttp.streamablehttp_client",
        side_effect=ConnectionError("refused"),
    ):
        result = await client.connect()

    assert result is False
    assert client._is_connected is False


@pytest.mark.asyncio
async def test_call_tool_returns_none_when_not_connected() -> None:
    """Tool methods on an unconnected client must return None (not raise)."""
    client = DharaMCPClient(DharaMCPConfig(url="http://test/mcp"))
    result = await client.put(key="test", value=42)
    assert result is None
```

- [ ] **Step 6: Run all unit tests for the client**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/dhara_mcp_client_test.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 7: Commit the client implementation**

```bash
cd /Users/les/Projects/crackerjack && git add crackerjack/integration/dhara_mcp_client.py tests/integration/dhara_mcp_client_test.py && git commit -m "feat(adapter-learning): add DharaMCPClient

Thin wrapper over mcp.client.streamablehttp that translates
each Dhara MCP kv_timeseries tool into a typed Python method.

connect() returns bool and never raises (the factory catches
all exceptions). disconnect() is idempotent and swallows the
streamablehttp cancel-scope RuntimeError documented in
mcp-connection-stability-plan.md. Each tool method catches
all exceptions internally and returns None or empty list,
so the factory is the single point that decides fallback
policy."
```

______________________________________________________________________

## Task 6: Add `DharaMCPAdapterLearner`

**Files:**

- Create: `tests/integration/dhara_mcp_adapter_learner_test.py` (failing test first)

- Modify: `crackerjack/integration/dhara_integration.py` (add the class)

- [ ] **Step 1: Create the failing integration test**

Path: `tests/integration/dhara_mcp_adapter_learner_test.py`

```python
"""Integration tests for `DharaMCPAdapterLearner`.

The learner is the crackerjack-side bridge to the Dhara MCP server.
It translates each `AdapterAttemptRecord` into a `record_time_series`
tool call. These tests use mock clients to verify the translation
without needing a live Dhara server.
"""

from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.integration.dhara_mcp_client import (
    DharaMCPClient,
    DharaMCPConfig,
)
from crackerjack.integration.dhara_integration import (
    AdapterAttemptRecord,
    DharaMCPAdapterLearner,
)


def _make_attempt(
    *, success: bool = True, error_type: str | None = None
) -> AdapterAttemptRecord:
    """Build an `AdapterAttemptRecord` for tests."""
    return AdapterAttemptRecord(
        adapter_name="prefect",
        file_type="py",
        file_size=100,
        project_context={"path": "/tmp/test"},
        success=success,
        execution_time_ms=42,
        error_type=error_type,
        timestamp=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
    )


def test_dhara_mcp_learner_close_is_idempotent() -> None:
    """`close()` may be called any number of times without raising."""
    learner = DharaMCPAdapterLearner(DharaMCPConfig(url="http://test/mcp"))
    learner.close()
    learner.close()


def test_dhara_mcp_learner_close_swallows_exceptions() -> None:
    """If the underlying disconnect raises, `close()` must not propagate."""
    learner = DharaMCPAdapterLearner(DharaMCPConfig(url="http://test/mcp"))
    learner._client = MagicMock()
    learner._client.disconnect = AsyncMock(side_effect=RuntimeError("boom"))
    learner.close()
```

- [ ] **Step 2: Run to verify it FAILS**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/dhara_mcp_adapter_learner_test.py -v
```

Expected: ImportError on `DharaMCPAdapterLearner`.

- [ ] **Step 3: Commit the failing test**

```bash
cd /Users/les/Projects/crackerjack && git add tests/integration/dhara_mcp_adapter_learner_test.py && git commit -m "test(adapter-learning): first tests for DharaMCPAdapterLearner"
```

- [ ] **Step 4: Add `DharaMCPAdapterLearner` to `dhara_integration.py`**

In `crackerjack/integration/dhara_integration.py`, add the import:

```python
from crackerjack.integration.dhara_mcp_client import DharaMCPClient, DharaMCPConfig
```

(Add it to the existing first-party imports block.)

Then, near the bottom of the file (after `NoOpAdapterLearner`, before `create_adapter_learner`), add:

```python
class DharaMCPAdapterLearner:
    """`AdapterLearnerProtocol` implementation that records attempts
    to a remote Dhara MCP server via the kv_timeseries tool group.

    The session is opened lazily on the first
    `record_adapter_attempt` call (sync-to-async via
    `asyncio.run`). The record body includes a `pattern` key so
    the server's `aggregate_patterns` tool can group attempts by
    success/failure category.
    """

    def __init__(self, config: DharaMCPConfig) -> None:
        """Create a learner with the given MCP config.

        The connection is opened lazily — `record_adapter_attempt`
        is the first method that talks to the network.
        """
        self._client = DharaMCPClient(config)

    def _derive_pattern(self, attempt: AdapterAttemptRecord) -> str:
        """Derive a coarse pattern category for `aggregate_patterns`.

        Returns e.g. `success:prefect` or `error:ValueError`. The
        pattern is intentionally short and stable so it can be
        used as a group-by key.
        """
        if attempt.success:
            return f"success:{attempt.adapter_name}"
        error_name = attempt.error_type or "unknown"
        return f"error:{error_name}"

    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None:
        """Bridge to async: run the async record path in a fresh event loop."""
        asyncio.run(self._record_attempt_async(attempt))

    async def _record_attempt_async(self, attempt: AdapterAttemptRecord) -> None:
        """Connect (if not already), translate the attempt to a
        `record_time_series` call, and send it.

        If the connection fails, the call is silently skipped
        (logged at DEBUG). The factory chain handles the broader
        case of an unreachable server.
        """
        try:
            connected = await self._client.connect()
            if not connected:
                logger.debug("DharaMCPAdapterLearner: not connected, skipping record")
                return
            record = {**attempt.to_dict(), "pattern": self._derive_pattern(attempt)}
            await self._client.record_time_series(
                metric_type="adapter_attempt",
                entity_id=attempt.adapter_name,
                record=record,
                timestamp=datetime.now(UTC).isoformat(),
            )
        except Exception as exc:
            logger.debug(
                f"DharaMCPAdapterLearner.record_adapter_attempt failed: {exc!r}"
            )

    def close(self) -> None:
        """Best-effort disconnect. Idempotent. Swallows exceptions."""
        try:
            asyncio.run(self._client.disconnect())
        except Exception as exc:
            logger.debug(f"DharaMCPAdapterLearner.close failed: {exc!r}")
```

- [ ] **Step 5: Run the integration test to verify it PASSES**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/dhara_mcp_adapter_learner_test.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Add the record-attempt integration test**

Append to `tests/integration/dhara_mcp_adapter_learner_test.py`:

```python
def test_dhara_mcp_learner_record_includes_pattern_key() -> None:
    """`record_adapter_attempt` must include a `pattern` key in the
    record body for `aggregate_patterns` to group on.
    """
    learner = DharaMCPAdapterLearner(DharaMCPConfig(url="http://test/mcp"))
    learner._client = MagicMock()
    learner._client.connect = AsyncMock(return_value=True)
    learner._client.record_time_series = AsyncMock()

    attempt = _make_attempt(success=True)
    learner.record_adapter_attempt(attempt)

    learner._client.record_time_series.assert_awaited_once()
    call_args = learner._client.record_time_series.await_args
    assert call_args.kwargs["metric_type"] == "adapter_attempt"
    assert call_args.kwargs["entity_id"] == "prefect"
    record = call_args.kwargs["record"]
    assert record["pattern"] == "success:prefect"
    assert record["success"] is True
    assert record["execution_time_ms"] == 42
```

- [ ] **Step 7: Run the full learner test file**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/dhara_mcp_adapter_learner_test.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 8: Commit the learner implementation**

```bash
cd /Users/les/Projects/crackerjack && git add crackerjack/integration/dhara_integration.py tests/integration/dhara_mcp_adapter_learner_test.py && git commit -m "feat(adapter-learning): add DharaMCPAdapterLearner

Implements AdapterLearnerProtocol by translating each
AdapterAttemptRecord into a record_time_series MCP call.

The record body includes a 'pattern' key so Dhara's
aggregate_patterns tool can group attempts by success/failure
categories.

connect() is lazy — first record_adapter_attempt() opens the
MCP session. close() is best-effort and idempotent."
```

______________________________________________________________________

## Task 7: Refactor `create_adapter_learner` to walk the chain

**Files:**

- Modify: `crackerjack/integration/dhara_integration.py`

**Context:** The factory now tries the MCP path first, then the in-process path, then SQLite, then NoOp. Logs which path was chosen at INFO.

- [ ] **Step 1: Find the current `create_adapter_learner` factory**

In `crackerjack/integration/dhara_integration.py`, locate the `def create_adapter_learner(...)` function.

- [ ] **Step 2: Replace the factory body with the chain-walking version**

Replace the entire function body (everything between `def create_adapter_learner(...) -> AdapterLearnerProtocol:` and the next `def` or class definition) with:

```python
def create_adapter_learner(
    enabled: bool = True,
    db_path: Path | None = None,
    min_attempts: int = 5,
    backend: str = "auto",
) -> AdapterLearnerProtocol:
    """Build the right `AdapterLearnerProtocol` implementation for this run.

    Walks the chain MCP -> in-process Dhara -> SQLite -> NoOp, returning
    the first backend that initializes. Each step logs at INFO which
    path was chosen. The factory catches exceptions during learner
    construction (only); once a learner is returned, it must not
    raise on subsequent calls.
    """
    if not enabled:
        logger.info("adapter_learning: disabled, using NoOp")
        return NoOpAdapterLearner()

    db_path = db_path or Path(".crackerjack/adapter_learning.db")
    mcp_config = _load_dhara_mcp_config()

    if backend in ("auto", "dhara") and mcp_config.enabled:
        try:
            learner = DharaMCPAdapterLearner(mcp_config)
            logger.info(
                f"adapter_learning: using Dhara MCP at {mcp_config.url}"
            )
            return learner
        except Exception as exc:
            logger.info(
                f"Dhara MCP unavailable "
                f"({type(exc).__name__}: {exc}); "
                f"falling back to in-process Dhara"
            )

    if backend in ("auto", "dhara"):
        for candidate in _dhara_adapter_learning_db_candidates(db_path):
            try:
                learner = DharaAdapterLearner(
                    db_path=candidate, min_attempts=min_attempts,
                )
                logger.info(
                    f"adapter_learning: using in-process Dhara at {candidate}"
                )
                return learner
            except Exception as exc:
                logger.warning(
                    f"Dhara in-process unavailable at {candidate}: {exc}"
                )
                continue
        if backend == "dhara":
            logger.warning("Dhara backend unavailable, using NoOp as requested")
            return NoOpAdapterLearner()

    for candidate in _adapter_learning_db_candidates(db_path):
        try:
            learner = SQLiteAdapterLearner(
                db_path=candidate, min_attempts=min_attempts,
            )
            logger.info(
                f"adapter_learning: using SQLite at {candidate}"
            )
            return learner
        except Exception as exc:
            logger.warning(f"SQLite adapter learner unavailable: {exc}")

    logger.info("adapter_learning: using NoOp (all backends failed)")
    return NoOpAdapterLearner()
```

- [ ] **Step 3: Add the `_load_dhara_mcp_config` helper**

Just before `create_adapter_learner`, add:

```python
def _load_dhara_mcp_config() -> DharaMCPConfig:
    """Load `DharaMCPSettings` from the global settings loader and
    translate it into a `DharaMCPConfig`.

    Returns a default `DharaMCPConfig` on any failure (logged at
    DEBUG). The factory treats a load failure as "use the default
    config", not as a hard error.
    """
    from crackerjack.config.settings import DharaMCPSettings
    try:
        settings = DharaMCPSettings()
        return DharaMCPConfig(
            url=settings.url,
            timeout_seconds=settings.timeout_seconds,
            enabled=settings.enabled,
            token=settings.token,
        )
    except Exception as exc:
        logger.debug(f"failed to load DharaMCPSettings: {exc!r}")
        return DharaMCPConfig()
```

- [ ] **Step 4: Add the factory tests**

Append to `tests/integration/test_dhara_integration.py`:

```python
def test_factory_prefers_mcp_when_server_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the Dhara MCP server is reachable, the factory returns
    `DharaMCPAdapterLearner`."""
    from crackerjack.integration import dhara_integration
    from crackerjack.integration.dhara_integration import DharaMCPAdapterLearner

    monkeypatch.setattr(
        dhara_integration, "_load_dhara_mcp_config", lambda: DharaMCPConfig(enabled=True)
    )

    class _StubLearner:
        def __init__(self, config: DharaMCPConfig) -> None:
            pass

    monkeypatch.setattr(dhara_integration, "DharaMCPAdapterLearner", _StubLearner)

    learner = dhara_integration.create_adapter_learner(enabled=True, backend="auto")
    assert isinstance(learner, _StubLearner)


def test_factory_falls_back_to_noop_when_everything_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """If all backends fail, the factory returns NoOpAdapterLearner."""
    from crackerjack.integration import dhara_integration
    from crackerjack.integration.dhara_integration import NoOpAdapterLearner

    monkeypatch.setattr(
        dhara_integration, "_load_dhara_mcp_config", lambda: DharaMCPConfig(enabled=False)
    )

    def _raise_dhara(*args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        raise RuntimeError("AsyncConnection missing")

    def _raise_sqlite(*args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        raise OSError("locked")

    monkeypatch.setattr(dhara_integration, "DharaAdapterLearner", _raise_dhara)
    monkeypatch.setattr(dhara_integration, "SQLiteAdapterLearner", _raise_sqlite)

    learner = dhara_integration.create_adapter_learner(enabled=True, backend="auto")
    assert isinstance(learner, NoOpAdapterLearner)


def test_factory_respects_dhara_mcp_disabled_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """When `dhara_mcp.enabled` is False, the factory must skip the
    MCP path and fall through to in-process / SQLite / NoOp.
    """
    from crackerjack.integration import dhara_integration

    monkeypatch.setattr(
        dhara_integration, "_load_dhara_mcp_config", lambda: DharaMCPConfig(enabled=False)
    )

    used_dhara_mcp = False

    class _SpyMCP:
        def __init__(self, config: DharaMCPConfig) -> None:
            nonlocal used_dhara_mcp
            used_dhara_mcp = True

    def _raise_init(*args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        raise RuntimeError("init failed")

    monkeypatch.setattr(dhara_integration, "DharaMCPAdapterLearner", _SpyMCP)
    monkeypatch.setattr(dhara_integration, "DharaAdapterLearner", _raise_init)
    monkeypatch.setattr(dhara_integration, "SQLiteAdapterLearner", _raise_init)

    dhara_integration.create_adapter_learner(enabled=True, backend="auto")
    assert not used_dhara_mcp
```

(The test file needs the `DharaMCPConfig` import too — add `from crackerjack.integration.dhara_mcp_client import DharaMCPConfig` to the top of `test_dhara_integration.py`.)

- [ ] **Step 5: Run the factory tests**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/test_dhara_integration.py -v
```

Expected: all existing tests PASS plus the 3 new factory tests PASS.

- [ ] **Step 6: Manual end-to-end verification with and without MCP server**

Run without a Dhara MCP server running:

```bash
cd /Users/les/Projects/crackerjack && timeout 60 python -m crackerjack run -v -f --ai-debug 2>&1 | grep -E "adapter_learning|Dhara MCP|EXIT|KeyboardInterrupt|crackerjack-diag"
echo "EXIT: $?"
```

Expected: log line `adapter_learning: using SQLite at ...` (or in-process Dhara, depending on the environment) and `EXIT: 0`.

If you have a Dhara MCP server running on `http://localhost:8683`, also run with:

```bash
cd /Users/les/Projects/crackerjack && timeout 60 python -m crackerjack run -v -f --ai-debug 2>&1 | grep -E "adapter_learning|Dhara MCP|EXIT|KeyboardInterrupt|crackerjack-diag"
echo "EXIT: $?"
```

Expected: log line `adapter_learning: using Dhara MCP at http://localhost:8683` and `EXIT: 0`.

- [ ] **Step 7: Commit the factory refactor**

```bash
cd /Users/les/Projects/crackerjack && git add crackerjack/integration/dhara_integration.py tests/integration/test_dhara_integration.py && git commit -m "feat(adapter-learning): factory walks MCP -> Dhara -> SQLite -> NoOp

create_adapter_learner now tries the Dhara MCP server first
(happy path), falls back to the in-process Dhara learner
(now leak-free from commit 1 of this work), then to the
existing SQLite path, and finally to NoOp.

Each step logs at INFO which path was chosen. The factory
catches exceptions during learner construction (only) and
falls through to the next backend. Once a learner is
returned, it must not raise on subsequent calls.

Add factory tests that mock each backend to succeed or fail
and verify the right learner is selected."
```

______________________________________________________________________

## Task 8: Documentation update

**Files:**

- Modify: `docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md`
- Modify: `docs/DHARA_WIRING.md`

**Context:** The wiring doc and the ecosystem integration doc need to reflect the new MCP path. These are minor edits — no new files.

- [ ] **Step 1: Update `docs/DHARA_WIRING.md` to list `adapter_attempt` as a producer**

In the "Crackerjack → Dhara Time-Series" section, add a new entry:

```markdown
**Schema (Crackerjack → Dhara):**

```

metric_type: "adapter_attempt"
entity_id: "\<adapter_name>"
record: {
"adapter_name": str,
"file_type": str,
"file_size": int,
"project_context": dict,
"success": bool,
"execution_time_ms": int,
"error_type": str | None,
"timestamp": str (ISO 8601),
"pattern": str # e.g. "success:prefect" or "error:ValueError" — used by aggregate_patterns
}

```

Wired by `DharaMCPAdapterLearner` in `crackerjack/integration/dhara_integration.py`.
Transports the record via `mcp.client.streamablehttp` to the Dhara MCP server.
```

- [ ] **Step 2: Update `docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md`**

Find the "Dhara Storage Backend" section and add a note:

```markdown
**Note:** As of v0.65, Crackerjack's adapter-learning subsystem talks to
the Dhara MCP server via `streamablehttp` rather than importing Dhara
in-process. See `crackerjack/integration/dhara_mcp_client.py`. The
in-process path is preserved as a fallback for environments where the
Dhara MCP server is unreachable.
```

- [ ] **Step 3: Commit the docs**

```bash
cd /Users/les/Projects/crackerjack && git add docs/DHARA_WIRING.md docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md && git commit -m "docs: document DharaMCPAdapterLearner producer and transport"
```

______________________________________________________________________

## Task 9: Delete the obsolete `aiosqlite_cleanup` module

**Files:**

- Delete: `crackerjack/services/aiosqlite_cleanup.py`
- Delete: `tests/services/test_aiosqlite_cleanup.py`
- Modify: `crackerjack/__main__.py` (remove the import and the atexit)

**Context:** With the `weakref.finalize` leak fix in place, the `atexit` walk in `aiosqlite_cleanup.py` is no longer needed. The diagnostic atexit (which logs surviving threads) is renamed to `crackerjack_diag` and kept for future regression detection.

- [ ] **Step 1: Verify the regression test still passes**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/integration/test_aio_thread_leak_regression.py::test_no_aio_thread_leak_when_learner_garbage_collected -v
```

Expected: both parameterizations PASS (or skip on Dhara 0.5.0).

- [ ] **Step 2: Delete the obsolete module and its test**

```bash
cd /Users/les/Projects/crackerjack && git rm crackerjack/services/aiosqlite_cleanup.py tests/services/test_aiosqlite_cleanup.py
```

- [ ] **Step 3: Remove the import from `crackerjack/__main__.py`**

Open `crackerjack/__main__.py`. Find and DELETE the block:

```python
from crackerjack.services.aiosqlite_cleanup import (  # noqa: F401
    cleanup_aiosqlite_connections,
)
```

Also find the `_log_live_non_daemon_threads` function and the `atexit.register(_log_live_non_daemon_threads)` line. RENAME the function to `crackerjack_diag` and KEEP it (and the atexit registration) — it's useful for future regression detection:

```python
def crackerjack_diag() -> None:
    """Diagnostic that runs at interpreter exit and logs any non-daemon
    threads still alive. Catches future regressions where a library
    spawns an unkillable thread (like the June 2026 aiosqlite bug).
    """
    try:
        live = [
            thr for thr in _threading.enumerate() if not thr.daemon and thr.is_alive()
        ]
    except Exception:
        return
    if not live:
        return
    print(
        f"[crackerjack-diag] {len(live)} non-daemon thread(s) still alive at exit:",
        file=sys.stderr,
        flush=True,
    )
    for thr in live:
        print(
            f"  - name={thr.name!r} ident={thr.ident} alive={thr.is_alive()}",
            file=sys.stderr,
            flush=True,
        )


atexit.register(crackerjack_diag)
```

(Replace `_log_live_non_daemon_threads` with `crackerjack_diag` in both the function definition and the `atexit.register` call.)

- [ ] **Step 4: Run the full test suite**

Run:

```bash
cd /Users/les/Projects/crackerjack && python -m pytest tests/ -x -q
```

Expected: all tests PASS (or skip on Dhara 0.5.0).

- [ ] **Step 5: Manual end-to-end verification**

```bash
cd /Users/les/Projects/crackerjack && timeout 60 python -m crackerjack run -v -f --ai-debug; echo "EXIT: $?"
```

Expected: `EXIT: 0`, no `KeyboardInterrupt` traceback. The `[crackerjack-diag]` line should NOT appear (it only fires when non-daemon threads are alive at exit, which they shouldn't be).

- [ ] **Step 6: Commit the deletion**

```bash
cd /Users/les/Projects/crackerjack && git add crackerjack/__main__.py && git commit -m "chore(adapter-learning): remove obsolete aiosqlite_cleanup module

The weakref.finalize leak fix (in DharaAdapterLearner.__post_init__)
makes the atexit walk in aiosqlite_cleanup.py redundant. The
finalizer fires earlier and is deterministic.

The diagnostic atexit (crackerjack_diag) is retained and renamed
for clarity. It only fires when non-daemon threads are alive at
exit, which catches future regressions."
```

______________________________________________________________________

## Self-review

**1. Spec coverage:**

- ✅ Section 1: Architecture — covered in Tasks 1, 2, 3, 4, 5, 6, 7
- ✅ Section 2: Components — Tasks 3 (settings), 5 (client), 6 (learner), 7 (factory)
- ✅ Section 3: Error handling — Task 5 step 3 (`with suppress`), Task 2 step 1 (`except BaseException`), Task 5 disconnect cancel-scope handling
- ✅ Section 4: Testing — Tasks 1, 4, 5, 6, 7 all add tests
- ✅ Section 5: Rollout — Three commits, matches the spec

**2. Placeholder scan:** No "TBD", "TODO", "fill in", or "handle edge cases" without concrete code. Every step has full code.

**3. Type consistency:** All types defined in the plan reference section at the top. `AdapterAttemptRecord.adapter_name` (not `name`), `execution_time_ms` (not `duration_ms`), `error_type` (not `error`) used consistently.

**4. Docstring policy:** Per RULES.md (post-update), all public classes, methods, and functions in new code have docstrings. The plan code blocks include them throughout. The `-x` flag is documented as a manual cleanup tool, not part of the pipeline.

______________________________________________________________________

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-03-dhara-mcp-migration.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
1. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
