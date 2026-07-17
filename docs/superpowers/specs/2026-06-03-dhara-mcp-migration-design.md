---
status: draft
role: implementation
date: 2026-07-17
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
topic: lifecycle
---

# Dhara MCP Adapter Learner Migration — Design

**Date:** 2026-06-03
**Status:** Approved (brainstorming complete)  <!-- legacy status — see YAML frontmatter -->
**Author:** Claude

## Problem

`python -m crackerjack run` hangs at interpreter shutdown, requiring
Ctrl+C to escape. The hang is at `_thread_shutdown()` blocking on a
non-daemon `Thread-1 (_connection_worker_thread)` spawned by `aiosqlite`.

### Root cause

`crackerjack/integration/dhara_integration.py:509-518` (the
`DharaAdapterLearner.__post_init__` method) creates an `AsyncConnection`
via `AsyncSqliteStorage`, which under the hood calls `aiosqlite.connect()`.
Each `aiosqlite.connect()` spawns a `_connection_worker_thread` that
is only reaped when the connection's `close()` coroutine completes.

`DharaAdapterLearner.close()` does call the abort path, but **no caller
in the codebase invokes it**. The learner instance is created in
`create_adapter_learner` and stored on `PhaseCoordinator._adapter_learning`
for the lifetime of the run. When the run ends and the adapter is
garbage-collected, the connection's worker thread is orphaned.

### Why the regression started in the last day or two

Per `git log --since="2 days ago"`, commit `c6acf211` ("build(deps):
declare aiosqlite in adapter-learning extra") added `aiosqlite` to
crackerjack's declared dependencies. Before that, `DharaAdapterLearner`
could not import `AsyncConnection` (the class didn't exist in the
installed Dhara 0.5.0), so the constructor raised and the factory
silently fell back to `SQLiteAdapterLearner` (sync, no thread leak).
After the dependency was declared, the import succeeds in environments
where Dhara is at a compatible version, and the leak becomes visible.

The user's clarification: "we should only be connecting to dhara
through mcp". The in-process `DharaAdapterLearner` is the wrong
abstraction — adapter learning should be a client of the Dhara MCP
server, not an in-process import of Dhara's internal classes.

## Goal

Replace the in-process `DharaAdapterLearner` with an MCP client that
talks to the Dhara MCP server. Keep the in-process path as a fallback
for users who don't run a Dhara MCP server. Fix the aiosqlite thread
leak in the in-process fallback independently, so users on either
path get a clean exit.

## Non-goals

- Changing the `AdapterLearnerProtocol` interface
- Changing the `phase_coordinator.py` call sites
- Adding new adapter-learning features (analytics dashboards, etc.)
- Touching the Dhara MCP server itself (separate repo)
- Replacing `SQLiteAdapterLearner` (sync sqlite3 has no thread issue)

## Architecture

Four components, each with one clear responsibility:

```
crackerjack (call sites)
    │
    ▼
create_adapter_learner (factory, refactored)
    │
    ├─→ [NEW] DharaMCPAdapterLearner  ──→  DharaMCPClient
    │         (happy path: talks to          (streamablehttp
    │          remote Dhara MCP server)       transport)
    │
    ├─→ DharaAdapterLearner  ──→  AsyncConnection + AsyncSqliteStorage
    │         (in-process fallback,            │
    │          now leak-free via               ▼
    │          weakref.finalize)          aiosqlite (with leak fix)
    │
    ├─→ SQLiteAdapterLearner  ──→  sync sqlite3 (unchanged)
    │
    └─→ NoOpAdapterLearner (last resort, unchanged)
```

**Why a chain, not a single backend:**
The user has a Dhara MCP server running in their environment. The
factory should prefer it. But operators without a Dhara MCP server
should still get adapter learning via the in-process path, and
even that path must not hang at exit.

**Why weakref.finalize, not atexit.register:**
`atexit` handlers run in LIFO order at interpreter shutdown — too late
to be useful when the adapter is gc'd at end of `crackerjack run`.
`weakref.finalize` fires the moment the learner's last reference is
released, which is much earlier. It also doesn't keep the learner
alive (it holds a weakref, not a strong ref).

**Dhara 0.5.0 compatibility note:**
The installed Dhara 0.5.0 does NOT have `AsyncConnection` or
`AsyncSqliteStorage`. The leak fix in commit 1 is environment-dependent:
it works when Dhara is at a version that exposes `AsyncConnection.abort()`.
On Dhara 0.5.0, the in-process path raises in `__post_init__` and the
factory falls through to SQLite. The factory chain handles both cases.

## Components

### 1. `crackerjack/integration/dhara_mcp_client.py` (NEW)

`DharaMCPConfig` dataclass:

- `url: str = "http://localhost:8683"` — base URL of the Dhara MCP server.
  The streamablehttp transport appends `/mcp` automatically.
- `timeout_seconds: int = 5`
- `enabled: bool = True` — feature flag (kill switch)
- `token: str | None = None` — bearer token for the Dhara server's
  `auth=auth("write")` gating on `put`/`record_time_series`. None means
  no auth header (server in unauthenticated mode).

`DharaMCPClientError(NetworkError)` — uses crackerjack's existing error
hierarchy (`crackerjack/errors.py:191`) so it surfaces correctly through
`handle_error()` and the `ErrorCode` system.

`DharaMCPClient` — `@dataclass` (matches `SessionBuddyMCPClient`):

- `config: DharaMCPConfig` — config dataclass
- `_client: Any | None` — `streamablehttp_client` instance, set on connect
- `_session: Any | None` — `ClientSession`, set on connect
- `_is_connected: bool` — connection state
- `connect() -> bool` — opens transport, runs MCP initialize handshake.
  Returns True on success, False on any failure (NEVER raises; the
  factory's `except Exception` is the catch-all). Catches `httpx.ConnectError`,
  `httpx.TimeoutException`, MCP handshake errors, AND the
  `"cancel scope"` RuntimeError documented in
  `mcp-connection-stability-plan.md`.
- `disconnect() -> None` — closes session and transport. Wraps `aclose()`
  in `try/except` for the cancel-scope RuntimeError. Idempotent.
- `is_alive() -> bool` — calls a health-check tool, returns True/False
- `put(key, value, ttl=None) -> dict | None` — wraps the `put` tool.
  Returns None on any error (logged at DEBUG).
- `get(key) -> dict | None` — wraps the `get` tool
- `record_time_series(metric_type, entity_id, record, timestamp=None) -> dict | None`
- `query_time_series(metric_type, entity_id, start_date=None, limit=None) -> list[dict]`
- `aggregate_patterns(start_date, min_occurrences=2) -> list[dict]`

All tool methods are async. They do NOT raise — they catch and log,
returning None or empty list. The factory is the only place that
makes fallback decisions.

**Auth header:** If `config.token` is set, every tool call includes
`Authorization: Bearer {token}`. The token is read once at connect
time; rotation requires reconnect.

### 2. `DharaMCPAdapterLearner` (NEW, in `dhara_integration.py`)

Implements `AdapterLearnerProtocol` (the `record_adapter_attempt` method).
Owns a `DharaMCPClient`. The record body includes the `pattern` key
that Dhara's `aggregate_patterns` tool looks for:

```python
def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None:
    asyncio.run(self._record_attempt_async(attempt))

async def _record_attempt_async(self, attempt: AdapterAttemptRecord) -> None:
    try:
        record = {
            **attempt.to_dict(),
            "pattern": self._derive_pattern(attempt),
        }
        await self._client.record_time_series(
            metric_type="adapter_attempt",
            entity_id=attempt.name,
            record=record,
            timestamp=datetime.now(UTC).isoformat(),
        )
    except Exception as exc:
        logger.debug(f"DharaMCPAdapterLearner.record_adapter_attempt failed: {exc!r}")

def _derive_pattern(self, attempt: AdapterAttemptRecord) -> str:
    # "success:{name}", "error:{error_class}", etc. — a coarse
    # category that aggregate_patterns can group on.
    if attempt.success:
        return f"success:{attempt.name}"
    return f"error:{type(attempt.error).__name__ if attempt.error else 'unknown'}"
```

`close()` is best-effort and idempotent. No leak risk — there's no
aiosqlite connection to manage.

### 3. `DharaAdapterLearner` leak fix (MODIFY, in `dhara_integration.py`)

Add a `weakref.finalize` registration inside `__post_init__`:

```python
def __post_init__(self) -> None:
    # ... existing setup that creates self._async_connection ...

    # When the learner is gc'd, run the abort path. weakref.finalize
    # holds a weakref to self, so it doesn't extend the learner's
    # lifetime. The finalizer fires earlier than atexit (which is
    # too late) and is the only reliable way to close the
    # aiosqlite connection at end of `crackerjack run`.
    #
    # The connection is bound to the event loop it was created in.
    # The factory created it via `asyncio.run(_init_connection())`,
    # so the loop is long-gone. We must run abort() in a fresh
    # loop. If `AsyncConnection` or its `abort` method don't exist
    # (e.g., Dhara 0.5.0), the finalizer is a no-op — the factory
    # falls back to SQLite in that case anyway.
    weakref.finalize(self, _safe_abort_sync, self._async_connection)
```

Module-level helper (NEVER raises — see error handling):

```python
def _safe_abort_sync(connection: Any) -> None:
    """Module-level finalizer helper. Must NEVER raise.

    `BaseException` (not `Exception`) so we also catch
    `KeyboardInterrupt`, `SystemExit`, and `asyncio.CancelledError`
    during interpreter teardown — a raising finalizer is an
    interpreter crash. In Dhara 0.5.0 (no AsyncConnection), this
    is effectively a no-op.
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

The existing `atexit.register` in `create_adapter_learner` is REMOVED
(along with the `_safe_close` def helper it references) — the finalizer
subsumes it and fires earlier.

### 4. `create_adapter_learner` refactor (MODIFY)

Walk the chain in order; first success wins; log which path was chosen.

```python
def create_adapter_learner(
    enabled: bool = True,
    db_path: Path | None = None,
    min_attempts: int = 5,
    backend: str = "auto",
) -> AdapterLearnerProtocol:
    if not enabled:
        return NoOpAdapterLearner()

    db_path = db_path or Path(".crackerjack/adapter_learning.db")
    mcp_config = _build_dhara_mcp_config()  # reads from settings

    # 1. Dhara MCP server (happy path)
    if backend in ("auto", "dhara") and mcp_config.enabled:
        try:
            learner = DharaMCPAdapterLearner(mcp_config)
            logger.info(f"adapter_learning: using Dhara MCP at {mcp_config.url}")
            return learner
        except Exception as exc:
            logger.info(
                f"Dhara MCP unavailable "
                f"({type(exc).__name__}: {exc}); "
                f"falling back to in-process Dhara"
            )

    # 2. In-process Dhara (leak-free via weakref.finalize)
    if backend in ("auto", "dhara"):
        for candidate in _dhara_adapter_learning_db_candidates(db_path):
            try:
                learner = DharaAdapterLearner(
                    db_path=candidate, min_attempts=min_attempts,
                )
                logger.info(f"adapter_learning: using in-process Dhara at {candidate}")
                return learner
            except Exception as exc:
                logger.warning(
                    f"Dhara in-process unavailable at {candidate}: {exc}"
                )
                continue
        if backend == "dhara":
            logger.warning("Dhara backend unavailable, using NoOp as requested")
            return NoOpAdapterLearner()

    # 3. Synchronous SQLite
    for candidate in _sqlite_candidate_paths(db_path):
        try:
            learner = SQLiteAdapterLearner(
                db_path=candidate, min_attempts=min_attempts,
            )
            logger.info(f"adapter_learning: using SQLite at {candidate}")
            return learner
        except Exception as exc:
            logger.warning(f"SQLite adapter learner unavailable: {exc}")

    # 4. Last resort
    logger.info("adapter_learning: using NoOp (all backends failed)")
    return NoOpAdapterLearner()
```

`_build_dhara_mcp_config` is a module-level helper that reads from
`crackerjack_settings()` (the same loader other code uses), NOT a
`from_settings()` classmethod on the config (which doesn't exist on
`MCPBaseSettings`).

### 5. `crackerjack/config/settings.py` (MODIFY)

Add a new top-level settings class (matches the pattern of `MCPServerSettings`,
`LearningSettings` — no nested groups):

```python
class DharaMCPSettings(MCPBaseSettings):
    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None
```

`crackerjack_settings()` is the loader that exposes the singleton. Other
code accesses the values through that loader. No nesting required.

## Data flow

When a `crackerjack run` finishes a hook check:

1. The autofix coordinator calls `self._adapter_learner_integration.track_adapter_execution(adapter_name, success, duration, error, metadata)` (existing call site, unchanged)
1. `DharaLearningIntegration.track_adapter_execution` builds an `AdapterAttemptRecord` and calls `self.adapter_learner.record_adapter_attempt(attempt)` (existing, unchanged)
1. Depending on which learner the factory returned, one of:
   - **DharaMCPAdapterLearner** (preferred): translates to a `record_time_series` MCP tool call over HTTP, async via `asyncio.run()`. The Dhara MCP server stores the record.
   - **DharaAdapterLearner** (fallback): writes via the existing 4-call path to the in-process AsyncConnection. **The finalizer will close the connection when the learner is gc'd.**
   - **SQLiteAdapterLearner**: sync sqlite3, no thread issue.
   - **NoOpAdapterLearner**: logs at debug, returns immediately.

When the run ends and `phase_coordinator` releases its reference to the
adapter:

- **DharaMCPAdapterLearner**: nothing to clean up; the HTTP connection closes on its own
- **DharaAdapterLearner**: `weakref.finalize` fires, calls `_safe_abort_sync`, which runs `asyncio.run(connection.abort())` (or skips if the method doesn't exist), which sends the stop sentinel to the aiosqlite worker queue. The thread exits.
- **SQLiteAdapterLearner**: nothing to clean up
- **NoOpAdapterLearner**: nothing to clean up

Result: `_thread_shutdown()` finds no orphaned non-daemon threads. Clean exit.

## Error handling

### Factory level

| Failure | Detection | Response |
|---|---|---|
| Dhara MCP server unreachable | `connect()` returns False | Log INFO, fall through to in-process |
| In-process Dhara init fails (Dhara 0.5.0 missing `AsyncConnection`) | `ImportError` or `RuntimeError` in `DharaAdapterLearner.__post_init__` | Log INFO, fall through to SQLite |
| SQLite init fails (db locked, permission) | `OSError`, `PermissionError` in `SQLiteAdapterLearner.__init__` | Log WARNING, fall through to NoOp |
| All backends fail | reaches the bottom | Return `NoOpAdapterLearner` (current behavior) |

The factory only catches exceptions during **construction**. Once a
learner is returned, it must not raise on subsequent calls — that
guarantees a failed write never breaks the run.

### Per-learner policy

- `record_adapter_attempt` in all three learners wraps its work in `try/except Exception` with `logger.debug(...)` and returns `None`
- `close()` is best-effort, wrapped in `try/except Exception` at every layer
- The interpreter must not crash on teardown

### The finalizer helper — critical safety net

The finalizer must NEVER raise. A raising finalizer is a Python
interpreter crash. The helper uses `except BaseException` (not
`Exception`) so it catches `KeyboardInterrupt`, `SystemExit`, and
`asyncio.CancelledError` too — all of which can fire during teardown
and would otherwise hang or crash the interpreter.

```python
def _safe_abort_sync(connection: Any) -> None:
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

### Streamablehttp cancel-scope RuntimeError

`mcp-connection-stability-plan.md` documents a known issue where
`streamablehttp_client.aclose()` can raise `RuntimeError: Attempted to exit cancel scope in a different task` when called from a different
task context (e.g., during gc from a finalizer). The `disconnect()`
method wraps the close in `try/except` for this specific error:

```python
def disconnect(self) -> None:
    if self._session is not None:
        try:
            await self._session.__aexit__(None, None, None)
        except RuntimeError as exc:
            if "cancel scope" not in str(exc):
                raise
            logger.debug(f"DharaMCPClient.disconnect: cancel-scope error ignored: {exc!r}")
        self._session = None
    if self._client is not None:
        try:
            await self._client.__aexit__(None, None, None)
        except RuntimeError as exc:
            if "cancel scope" not in str(exc):
                raise
            logger.debug(f"DharaMCPClient.disconnect: cancel-scope error ignored: {exc!r}")
        self._client = None
    self._is_connected = False
```

## Settings

```python
# config/settings.py
class DharaMCPSettings(MCPBaseSettings):
    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None
```

Backwards compatibility:

- `adapter_learning_enabled`, `adapter_learning_db`, `adapter_learning_backend` are unchanged
- New `dhara_mcp_url`, `dhara_mcp_timeout_seconds`, `dhara_mcp_enabled`, `dhara_mcp_token` settings are additive (MCPBaseSettings flattens fields with env var prefix `MAHAVISHNU_DHARA_MCP_*`)
- Existing `crackerjack/settings/local.yaml` files need no changes

## Testing

### Unit tests

`tests/integration/dhara_mcp_client_test.py`:

- `test_record_time_series_calls_correct_tool` — mock ClientSession, assert the right tool name and args
- `test_put_get_round_trip` — fake session that returns canned responses
- `test_connect_returns_false_on_connection_error` — `httpx.ConnectError` causes `connect()` to return False
- `test_disconnect_closes_session_and_client`
- `test_disconnect_swallows_cancel_scope_runtime_error` — `aclose()` raising the documented RuntimeError must not propagate
- `test_query_time_series_returns_empty_list_on_tool_error`
- `test_aggregate_patterns_passes_through_args`
- `test_auth_token_added_to_tool_calls` — when config.token is set, every tool call includes the bearer header

### Integration tests

`tests/integration/dhara_mcp_adapter_learner_test.py`:

- Use a `FastMCPTransport` in-process test fixture (`fastmcp/client/transports/memory.py:19`) — does NOT bind a port, exercises the actual MCP framing. This is the canonical pattern for FastMCP integration tests.
- `test_dhara_mcp_learner_records_attempt` — record an attempt, query the server, assert the record arrived with the `pattern` key
- `test_dhara_mcp_learner_close_is_idempotent`
- `test_dhara_mcp_learner_close_swallows_exceptions` — close() must not raise even if the server is down
- `test_dhara_mcp_learner_record_includes_pattern_key` — assert the record body has `pattern` populated (for `aggregate_patterns` compatibility)

### Factory tests (in `tests/integration/test_dhara_integration.py`)

- `test_factory_prefers_mcp_when_server_reachable` — mock MCP connect to return True, assert `DharaMCPAdapterLearner` is returned
- `test_factory_falls_back_to_inprocess_when_mcp_unreachable` — mock MCP connect to return False, assert we get the in-process or SQLite path (not NoOp)
- `test_factory_falls_back_to_noop_when_everything_fails` — mock all backends to fail, assert NoOp
- `test_factory_respects_dhara_mcp_disabled_flag` — set enabled=False, assert MCP is skipped
- `test_factory_handles_dhara_import_success_but_init_runtime_error` — mock `DharaAdapterLearner.__post_init__` to raise `RuntimeError("AsyncConnection.new failed")`, assert fallback to SQLite
- `test_factory_handles_mcp_server_rejecting_call` — MCP connect returns True, but a subsequent tool call returns 4xx. Learner should still record the call (we don't re-raise in tool methods).
- `test_factory_logging_at_each_step` — assert INFO logs are emitted for the path chosen, INFO for fallbacks, WARNING for last-resort fallback to NoOp

Mocking style: use `unittest.mock.patch` (with `with patch(...)` context
managers) to match the existing test file's conventions.

### Regression test (the one that proves the hang is fixed)

`tests/integration/test_aio_thread_leak_regression.py`:

```python
import asyncio
import gc
import threading
import time
from pathlib import Path

import pytest


def _live_aio_threads() -> list[str]:
    return [
        t.name
        for t in threading.enumerate()
        if not t.daemon
        and t.is_alive()
        and t.name.endswith(" (_connection_worker_thread)")
    ]


def test_no_aio_thread_leak_when_learner_garbage_collected(tmp_path):
    """The aiosqlite _connection_worker_thread that blocked
    _thread_shutdown() must NOT survive garbage collection of
    the learner.

    Regression test for the hang observed in June 2026 where
    'python -m crackerjack run' would hang at interpreter
    shutdown because aiosqlite's worker thread was orphaned.
    """
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

    # Poll for up to 1 second for the worker to exit.
    deadline = time.monotonic() + 1.0
    while _live_aio_threads() and time.monotonic() < deadline:
        time.sleep(0.02)

    assert _live_aio_threads() == [], (
        f"Learner gc left {len(_live_aio_threads())} aiosqlite "
        f"worker thread(s) alive. The interpreter would hang at "
        f"_thread_shutdown()."
    )
    # tmp_path is auto-cleaned by pytest
```

### Tests to delete (after the leak fix is verified in commit 3)

- `tests/services/test_aiosqlite_cleanup.py` — the `atexit` walk in `aiosqlite_cleanup.py` becomes redundant once the finalizer is in place. Delete the module and the test.

### Commit 3 — the missing failing test

Per TDD discipline, commit 3 (deletion) needs a test that proves the
deletion is safe. That test is the same regression test from commit 1
re-run after the deletion. To make the TDD discipline explicit, the
regression test in commit 1 is *parameterized* to also work after
deletion:

```python
@pytest.mark.parametrize("with_cleanup_module", [True, False])
def test_no_aio_thread_leak_when_learner_garbage_collected(
    tmp_path, with_cleanup_module
):
    """Works whether or not the aiosqlite_cleanup module is imported.

    Without the finalizer (commit 1), this test fails on Dhara with
    AsyncConnection. With the finalizer, it always passes — regardless
    of whether aiosqlite_cleanup.py is also imported.
    """
    if not with_cleanup_module:
        # Simulate the post-commit-3 state by ensuring the module
        # is NOT imported during this test.
        import sys
        for mod in list(sys.modules):
            if mod.startswith("crackerjack.services.aiosqlite_cleanup"):
                del sys.modules[mod]
    # ... rest of test ...
```

The `with_cleanup_module=True` case is the new test in commit 1.
The `with_cleanup_module=False` case is the new test in commit 3 —
it proves the finalizer alone is sufficient, so the cleanup module
is safe to delete.

## Rollout

Three commits, each independently shippable.

### Commit 1: `fix(adapter-learning): reap aiosqlite worker on learner collection`

Files modified:

- `crackerjack/integration/dhara_integration.py` — add `_safe_abort_sync` module-level helper, add `weakref.finalize` registration in `DharaAdapterLearner.__post_init__`, REMOVE the existing `atexit.register(_safe_close)` from `create_adapter_learner` AND the `_safe_close` def helper (which was only used by that atexit handler)
- `crackerjack/integration/dhara_integration.py:779` — REMOVE the stale comment referencing the `aiosqlite_cleanup` module (this is the comment that says "we run before the aiosqlite_cleanup module's atexit handler")

Files created:

- `tests/integration/test_aio_thread_leak_regression.py`

Verify:

- `pytest tests/integration/test_aio_thread_leak_regression.py -v` PASSES
- `pytest tests/integration/test_dhara_integration.py` PASSES (existing tests still work)
- **Manual with timeout:** `timeout 60 python -m crackerjack run -v -f --ai-debug; echo "EXIT: $?"`. The `timeout` is critical — the original bug was a HANG, not a non-zero exit. Assert exit code 0 AND the run completed within 60 seconds.
- On Dhara 0.5.0 (no AsyncConnection): the test skips, but the manual run still proves the run completes (because the factory falls back to SQLite).

Risk: low. Adds a finalizer; no other code paths change.

### Commit 2: `feat(adapter-learning): add DharaMCPAdapterLearner via streamablehttp`

Files created:

- `crackerjack/integration/dhara_mcp_client.py` — `DharaMCPConfig`, `DharaMCPClient`, `DharaMCPClientError`
- `tests/integration/dhara_mcp_client_test.py`
- `tests/integration/dhara_mcp_adapter_learner_test.py`

Files modified:

- `crackerjack/integration/dhara_integration.py` — add `DharaMCPAdapterLearner`, refactor `create_adapter_learner` to walk the chain
- `crackerjack/config/settings.py` — add `DharaMCPSettings`
- `tests/integration/test_dhara_integration.py` — add factory tests

Verify:

- Full integration test suite passes
- **Manual with timeout, no Dhara server running:** `timeout 60 python -m crackerjack run -v -f --ai-debug; echo "EXIT: $?"` — should fall back to in-process / SQLite, no hang
- **Manual with timeout, with real Dhara MCP server running:** `timeout 60 python -m crackerjack run -v -f --ai-debug; echo "EXIT: $?"` — should connect via MCP, log "using Dhara MCP at http://...", record adapter attempts via the MCP server
- **Concrete MCP verification:** after a run, query the Dhara MCP server's `query_time_series` tool with `metric_type="adapter_attempt"` and assert at least one record exists

Risk: medium. New code path; factory logic changes. Mitigated by the catch-all `except Exception` at the factory — the worst case is "we always fall back to NoOp", which is the current behavior.

### Commit 3: `chore(adapter-learning): remove now-unused aiosqlite cleanup module`

Files deleted:

- `crackerjack/services/aiosqlite_cleanup.py`
- `tests/services/test_aiosqlite_cleanup.py`

Files modified:

- `crackerjack/__main__.py` — remove the `from crackerjack.services.aiosqlite_cleanup import ...` import and the `atexit.register(_log_live_non_daemon_threads)` registration. Rename `_log_live_non_daemon_threads` to `crackerjack_diag` (kept for future regression detection).

Verify:

- Full test suite passes
- **Manual with timeout:** `timeout 60 python -m crackerjack run -v -f --ai-debug; echo "EXIT: $?"` — still exits 0, no hang
- Re-run the commit 1 regression test (parameterized with `with_cleanup_module=False`) to prove the finalizer alone is sufficient

Risk: low. Pure deletion. If something in commit 1 was missed, the regression test will catch it.

## Backwards compatibility

- `DharaAdapterLearner` class is preserved (in-process fallback)
- `create_adapter_learner(backend="dhara")` semantics are preserved: if all Dhara backends fail, fall through to SQLite then NoOp
- `adapter_learning_db`, `adapter_learning_enabled`, `adapter_learning_backend` settings are unchanged
- The new `DharaMCPSettings` is additive — no existing config breaks
- Callers of `create_adapter_learner` (currently just `phase_coordinator.py`) need no changes
- The `aiosqlite` dependency stays declared (commit 1 is what makes the in-process path actually work)

## Documentation

- `docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md` — update to describe the new MCP path
- `docs/features/SKILLS_INTEGRATION.md` — update references to the in-process Dhara path
- New: `docs/ADAPTER_LEARNING_BACKENDS.md` — fallback chain, when to use which, how to disable
- `docs/DHARA_WIRING.md` — add `adapter_attempt` to the list of metric types Crackerjack writes (it's the new producer)
- `CHANGELOG.md` — entry under the next version

## Open questions

None. The design is complete and approved.
