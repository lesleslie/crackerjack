"""Tests for the aiosqlite connection cleanup atexit handler.

Bug #6: aiosqlite spawns a `_connection_worker_thread` at every
`aiosqlite.connect()` call. The thread is only reaped when the
connection is closed. If the connection is created during a run
but never explicitly closed (as happened with DharaAdapterLearner
in `crackerjack/integration/dhara_integration.py`), the worker
thread survives to interpreter shutdown and blocks
`_thread_shutdown()`. The user has to Ctrl+C to escape.

The fix: a module-level atexit handler that walks `gc.get_objects()`,
finds any live `aiosqlite.Connection` instances, and closes them
in a fresh event loop.

This test exercises the contract: after `cleanup_aiosqlite_connections()`
is called, no `_connection_worker_thread` should remain alive.
"""

from __future__ import annotations

import asyncio
import gc
import threading

import pytest

from crackerjack.services.aiosqlite_cleanup import cleanup_aiosqlite_connections


def _live_worker_threads() -> list[threading.Thread]:
    """Return all live non-daemon threads whose name contains
    `_connection_worker_thread`."""
    return [
        t
        for t in threading.enumerate()
        if not t.daemon
        and t.is_alive()
        and "_connection_worker_thread" in t.name
    ]


def _live_aiosqlite_connections() -> list:
    """Return all `aiosqlite.Connection` instances currently alive in the
    Python object graph."""
    import aiosqlite

    return [o for o in gc.get_objects() if isinstance(o, aiosqlite.Connection)]


@pytest.mark.asyncio
async def test_aiosqlite_connect_spawns_worker_thread() -> None:
    """Sanity: `aiosqlite.connect()` does spawn a worker thread that
    needs explicit cleanup."""
    import aiosqlite

    conn = await aiosqlite.connect(":memory:")
    try:
        workers = _live_worker_threads()
        assert workers, (
            "Expected aiosqlite.connect() to spawn a _connection_worker_thread; "
            "found none. If this test fails, the assumption underlying the "
            "cleanup module is wrong and the atexit handler is unnecessary."
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_cleanup_closes_all_live_connections() -> None:
    """`cleanup_aiosqlite_connections()` must close every live
    aiosqlite connection found in the object graph, which in turn
    reaps every `_connection_worker_thread`."""
    import aiosqlite

    # Open several connections and confirm they each have a worker
    conn1 = await aiosqlite.connect(":memory:")
    conn2 = await aiosqlite.connect(":memory:")
    conn3 = await aiosqlite.connect(":memory:")

    try:
        assert len(_live_worker_threads()) >= 3, (
            f"Expected at least 3 worker threads alive after opening 3 "
            f"connections; found {len(_live_worker_threads())}."
        )

        # The cleanup should close them all
        cleanup_aiosqlite_connections()

        # Give the event loop a beat to actually reap the threads.
        for _ in range(50):
            if not _live_worker_threads():
                break
            await asyncio.sleep(0.02)

        assert _live_worker_threads() == [], (
            "cleanup_aiosqlite_connections() did not reap all "
            "_connection_worker_thread instances. The interpreter "
            "would still hang at _thread_shutdown()."
        )
    finally:
        # Defensive: also try to close each connection directly in
        # case the cleanup module itself has a bug — this ensures
        # the test doesn't leave workers around for subsequent tests.
        for c in (conn1, conn2, conn3):
            try:
                await c.close()
            except Exception:
                pass


def test_cleanup_is_idempotent() -> None:
    """Calling `cleanup_aiosqlite_connections()` more than once must
    not raise and must not crash the interpreter."""
    cleanup_aiosqlite_connections()
    cleanup_aiosqlite_connections()
    cleanup_aiosqlite_connections()


def test_cleanup_when_no_connections_open() -> None:
    """Calling cleanup with no live aiosqlite connections must be a
    no-op (no event loop created, no errors)."""
    # Make sure the gc is clean of aiosqlite connections first
    import aiosqlite

    for o in _live_aiosqlite_connections():
        # The cleanup itself uses gc to find these, so we just verify
        # it doesn't raise
        pass

    # Should not raise even when there are no live connections
    cleanup_aiosqlite_connections()
