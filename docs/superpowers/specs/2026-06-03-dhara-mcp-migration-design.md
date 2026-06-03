# Dhara MCP Adapter Learner Migration — Design

**Date:** 2026-06-03
**Status:** Approved (brainstorming complete)
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

## Components

### 1. `crackerjack/integration/dhara_mcp_client.py` (NEW)

`DharaMCPConfig` dataclass:
- `url: str = "http://localhost:8683"` — base URL of the Dhara MCP server
- `timeout_seconds: int = 5`
- `enabled: bool = True` — feature flag (kill switch)

`DharaMCPClient` class:
- `async connect() -> None` — opens the streamablehttp transport, runs the MCP initialize handshake. Raises `DharaMCPClientError` on any transport or protocol error.
- `async disconnect() -> None` — closes the session and transport
- `async is_alive() -> bool` — calls a health-check tool, returns True/False
- `async put(key, value, ttl=None) -> dict` — wraps the `put` tool
- `async get(key) -> dict` — wraps the `get` tool
- `async record_time_series(metric_type, entity_id, record, timestamp=None) -> dict` — wraps `record_time_series`
- `async query_time_series(metric_type, entity_id, start_date=None, limit=None) -> list[dict]` — wraps `query_time_series`
- `async aggregate_patterns(start_date, min_occurrences=2) -> list[dict]` — wraps `aggregate_patterns`

`DharaMCPClientError(Exception)` for protocol-level failures.

Transport: `mcp.client.streamablehttp.streamablehttp_client` + `mcp.ClientSession`,
mirroring `crackerjack/integration/session_buddy_mcp.py`.

### 2. `DharaMCPAdapterLearner` (NEW, in `dhara_integration.py`)

Implements `AdapterLearnerProtocol` (the `record_adapter_attempt` method).
Owns a `DharaMCPClient`. Translation:

```python
def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None:
    asyncio.run(self._record_attempt_async(attempt))

async def _record_attempt_async(self, attempt: AdapterAttemptRecord) -> None:
    try:
        await self._client.record_time_series(
            metric_type="adapter_attempt",
            entity_id=attempt.name,
            record=attempt.to_dict(),
            timestamp=datetime.now(UTC).isoformat(),
        )
    except Exception as exc:
        logger.debug(f"DharaMCPAdapterLearner.record_adapter_attempt failed: {exc!r}")
```

`close()` is best-effort and idempotent. No leak risk — there's no
aiosqlite connection to manage.

### 3. `DharaAdapterLearner` leak fix (MODIFY, in `dhara_integration.py`)

Add a `weakref.finalize` registration inside `__post_init__`:

```python
def __post_init__(self) -> None:
    # ... existing setup that creates self._async_connection ...

    weakref.finalize(
        self,
        _safe_abort_sync,           # module-level helper
        self._async_connection,
    )
```

Module-level helper (NEVER raises — see error handling):

```python
def _safe_abort_sync(connection: AsyncConnection | None) -> None:
    if connection is None:
        return
    try:
        asyncio.run(connection.abort())
    except BaseException as exc:  # noqa: BLE001 - by design
        logger.debug(f"finalizer: connection.abort failed: {exc!r}")
```

The existing `atexit.register` in `create_adapter_learner` is REMOVED
— the finalizer subsumes it and fires earlier.

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

    # 1. Dhara MCP server (happy path)
    if backend in ("auto", "dhara"):
        mcp_config = DharaMCPConfig.from_settings()
        if mcp_config.enabled:
            try:
                return DharaMCPAdapterLearner(mcp_config)
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
                return DharaAdapterLearner(
                    db_path=candidate, min_attempts=min_attempts,
                )
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
            return SQLiteAdapterLearner(
                db_path=candidate, min_attempts=min_attempts,
            )
        except Exception as exc:
            logger.warning(f"SQLite adapter learner unavailable: {exc}")

    # 4. Last resort
    return NoOpAdapterLearner()
```

### 5. `crackerjack/config/settings.py` (MODIFY)

Add a new settings group:

```python
class DharaMCPSettings(MCPBaseSettings):
    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
```

Add to `LearningSettings`:

```python
dhara_mcp: DharaMCPSettings = field(default_factory=DharaMCPSettings)
```

## Data flow

When a `crackerjack run` finishes a hook check:

1. The autofix coordinator calls `self._adapter_learner_integration.track_adapter_execution(adapter_name, success, duration, error, metadata)` (existing call site, unchanged)
2. `DharaLearningIntegration.track_adapter_execution` builds an `AdapterAttemptRecord` and calls `self.adapter_learner.record_adapter_attempt(attempt)` (existing, unchanged)
3. Depending on which learner the factory returned, one of:
   - **DharaMCPAdapterLearner** (preferred): translates to a `record_time_series` MCP tool call over HTTP, async via `asyncio.run()`. The Dhara MCP server stores the record.
   - **DharaAdapterLearner** (fallback): writes via the existing 4-call path to the in-process AsyncConnection. **The finalizer will close the connection when the learner is gc'd.**
   - **SQLiteAdapterLearner**: sync sqlite3, no thread issue.
   - **NoOpAdapterLearner**: logs at debug, returns immediately.

When the run ends and `phase_coordinator` releases its reference to the
adapter:

- **DharaMCPAdapterLearner**: nothing to clean up; the HTTP connection closes on its own
- **DharaAdapterLearner**: `weakref.finalize` fires, calls `_safe_abort_sync`, which runs `asyncio.run(connection.abort())`, which sends the stop sentinel to the aiosqlite worker queue. The thread exits.
- **SQLiteAdapterLearner**: nothing to clean up
- **NoOpAdapterLearner**: nothing to clean up

Result: `_thread_shutdown()` finds no orphaned non-daemon threads. Clean exit.

## Error handling

### Factory level

| Failure | Detection | Response |
|---|---|---|
| Dhara MCP server unreachable | `httpx.ConnectError`, `httpx.TimeoutException`, MCP handshake error | Log INFO, fall through to in-process |
| MCP server reachable but rejects the call | Tool returns 4xx/5xx | Log DEBUG, return None from the tool wrapper. Don't re-raise. |
| In-process Dhara init fails | `ImportError`, `RuntimeError` in `__post_init__` | Log INFO, fall through to SQLite |
| SQLite init fails | `OSError`, `PermissionError` | Log WARNING, fall through to NoOp |
| All backends fail | reaches the bottom | Return `NoOpAdapterLearner` |

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
def _safe_abort_sync(connection: AsyncConnection | None) -> None:
    if connection is None:
        return
    try:
        asyncio.run(connection.abort())
    except BaseException as exc:  # noqa: BLE001 - by design
        logger.debug(f"finalizer: connection.abort failed: {exc!r}")
```

## Settings

```python
# config/settings.py
class DharaMCPSettings(MCPBaseSettings):
    """Dhara MCP client configuration.

    When enabled and reachable, the DharaMCPAdapterLearner is used
    instead of the in-process Dhara path. Set enabled=False in
    settings/local.yaml to force the in-process fallback.
    """
    url: str = "http://localhost:8683"
    timeout_seconds: int = 5
    enabled: bool = True
```

Backwards compatibility:
- `adapter_learning_enabled`, `adapter_learning_db`, `adapter_learning_backend` are unchanged
- New `dhara_mcp` group is additive
- Existing `crackerjack/settings/local.yaml` files need no changes

## Testing

### Unit tests

`tests/integration/dhara_mcp_client_test.py`:
- `test_record_time_series_calls_correct_tool` — mock ClientSession, assert the right tool name and args
- `test_put_get_round_trip` — fake session that returns canned responses
- `test_connect_returns_false_on_connection_error` — `httpx.ConnectError` causes `DharaMCPClientError`
- `test_disconnect_closes_session_and_client`
- `test_query_time_series_returns_empty_list_on_tool_error`
- `test_aggregate_patterns_passes_through_args`

### Integration tests

`tests/integration/dhara_mcp_adapter_learner_test.py`:
- Use an in-process FastMCP server fixture exposing the kv_timeseries tools
- `test_dhara_mcp_learner_records_attempt` — record an attempt, query the server, assert the record arrived
- `test_dhara_mcp_learner_close_is_idempotent`
- `test_dhara_mcp_learner_close_swallows_exceptions` — close() must not raise even if the server is down

### Factory tests (in `tests/integration/test_dhara_integration.py`)

- `test_factory_prefers_mcp_when_server_reachable` — mock MCP connect to succeed, assert `DharaMCPAdapterLearner` is returned
- `test_factory_falls_back_to_inprocess_when_mcp_unreachable` — mock MCP connect to raise, assert we get the in-process or SQLite path (not NoOp)
- `test_factory_falls_back_to_noop_when_everything_fails` — mock all backends to fail, assert NoOp
- `test_factory_respects_dhara_mcp_disabled_flag` — set enabled=False, assert MCP is skipped

### Regression test (the one that proves the hang is fixed)

`tests/integration/test_aio_thread_leak_regression.py`:

```python
def test_no_aio_thread_leak_when_learner_garbage_collected():
    """The aiosqlite _connection_worker_thread that blocked
    _thread_shutdown() must NOT survive garbage collection of
    the learner.
    """
    import gc
    import threading

    from crackerjack.integration.dhara_integration import DharaAdapterLearner

    def _live_aio_threads() -> list[str]:
        return [
            t.name
            for t in threading.enumerate()
            if not t.daemon
            and t.is_alive()
            and t.name.endswith(" (_connection_worker_thread)")
        ]

    try:
        learner = DharaAdapterLearner(
            db_path=Path(".crackerjack/test_leak.dhara")
        )
    except Exception:
        pytest.skip("Dhara backend unavailable in this environment")

    assert _live_aio_threads(), "Sanity: learner init should spawn a worker"

    del learner
    gc.collect()
    gc.collect()

    for _ in range(50):
        if not _live_aio_threads():
            break
        time.sleep(0.02)

    assert _live_aio_threads() == [], (
        f"Learner gc left {len(_live_aio_threads())} aiosqlite "
        f"worker thread(s) alive. The interpreter would hang at "
        f"_thread_shutdown()."
    )
```

### Tests to delete (after the leak fix is verified)

- `tests/services/test_aiosqlite_cleanup.py` — the `atexit` walk in `aiosqlite_cleanup.py` becomes redundant once the finalizer is in place. Delete the module and the test.

### Tests to update

- `tests/integration/test_dhara_integration.py` — replace the `sys.modules` patches (which simulate Dhara absence) with explicit factory tests. The new tests are more precise about which backend is selected.

## Rollout

Three commits, each independently shippable.

### Commit 1: `fix(adapter-learning): reap aiosqlite worker on learner collection`

Files modified:
- `crackerjack/integration/dhara_integration.py` — add `_safe_abort_sync` module-level helper, add `weakref.finalize` registration in `DharaAdapterLearner.__post_init__`, REMOVE the existing `atexit.register(_safe_close)` from `create_adapter_learner` AND the `_safe_close` def helper (which was only used by that atexit handler)

Files created:
- `tests/integration/test_aio_thread_leak_regression.py`

Verify:
- `pytest tests/integration/test_aio_thread_leak_regression.py` PASSES
- `pytest tests/integration/test_dhara_integration.py` PASSES (existing tests still work)
- Manual: `python -m crackerjack run -v -f --ai-debug` exits with code 0, no `[crackerjack-diag]` line, no KeyboardInterrupt

Risk: low. Adds a finalizer; no other code paths change.

### Commit 2: `feat(adapter-learning): add DharaMCPAdapterLearner via streamablehttp`

Files created:
- `crackerjack/integration/dhara_mcp_client.py` — `DharaMCPConfig`, `DharaMCPClient`, `DharaMCPClientError`
- `crackerjack/integration/dhara_mcp_adapter_learner.py` (or in `dhara_integration.py`) — `DharaMCPAdapterLearner`
- `tests/integration/dhara_mcp_client_test.py`
- `tests/integration/dhara_mcp_adapter_learner_test.py`

Files modified:
- `crackerjack/integration/dhara_integration.py` — add `DharaMCPAdapterLearner`, refactor `create_adapter_learner` to walk the chain
- `crackerjack/config/settings.py` — add `DharaMCPSettings`
- `tests/integration/test_dhara_integration.py` — add factory tests

Verify:
- Full integration test suite passes
- Manual with real Dhara MCP server: `crackerjack run` records adapter attempts via MCP
- Manual without Dhara MCP server: factory falls back to in-process (which now has the leak fix from commit 1)

Risk: medium. New code path; factory logic changes. Mitigated by the catch-all `except Exception` at the factory — the worst case is "we always fall back to NoOp", which is the current behavior.

### Commit 3: `chore(adapter-learning): remove now-unused aiosqlite cleanup module`

Files deleted:
- `crackerjack/services/aiosqlite_cleanup.py`
- `tests/services/test_aiosqlite_cleanup.py`

Files modified:
- `crackerjack/__main__.py` — remove the `from crackerjack.services.aiosqlite_cleanup import ...` import and the diagnostic `_log_live_non_daemon_threads` (or keep just the diagnostic, renamed to `crackerjack_diag`)

Verify:
- Full test suite passes
- Manual: `python -m crackerjack run -v -f --ai-debug` exits with code 0

Risk: low. Pure deletion. If something in commit 1 was missed, the regression test will catch it.

## Backwards compatibility

- `DharaAdapterLearner` class is preserved (in-process fallback)
- `create_adapter_learner(backend="dhara")` semantics are preserved: if all Dhara backends fail, fall through to SQLite then NoOp
- `adapter_learning_db`, `adapter_learning_enabled`, `adapter_learning_backend` settings are unchanged
- The new `dhara_mcp` settings group is additive — no existing config breaks
- Callers of `create_adapter_learner` (currently just `phase_coordinator.py`) need no changes
- The `aiosqlite` dependency stays declared (commit 1 is what makes the in-process path actually work)

## Documentation

- `docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md` — update to describe the new MCP path
- `docs/features/SKILLS_INTEGRATION.md` — update references to the in-process Dhara path
- New: `docs/ADAPTER_LEARNING_BACKENDS.md` — fallback chain, when to use which, how to disable
- `CHANGELOG.md` — entry under the next version

## Open questions

None. The design is complete and approved.
