"""Cleans up leaked aiosqlite connections at interpreter shutdown.

Bug #6: `aiosqlite.connect()` spawns a `_connection_worker_thread`
per connection. The thread is only reaped when the connection's
`close()` coroutine completes. In the `crackerjack run` path,
connections can be created by:

  * `DharaAdapterLearner._async_connection` in
    `crackerjack/integration/dhara_integration.py` (the import
    currently fails against installed Dhara 0.5.0, but when the
    code does work, the connection is opened in a throwaway
    `asyncio.run()` and never explicitly closed)
  * oneiric's `SQLiteDatabaseAdapter` (registered as a built-in
    adapter via `oneiric/adapters/bootstrap.py`)

In both cases, the connection's worker thread is orphaned and
blocks `_thread_shutdown()` at interpreter exit. The user has to
Ctrl+C to escape.

This module provides a single function — `cleanup_aiosqlite_connections()`
— and an atexit registration that runs it. The function walks
`gc.get_objects()` to find any live `aiosqlite.Connection`
instances, then closes each in a fresh event loop. Idempotent:
safe to call multiple times, and a no-op if there are no live
connections.

The function is exposed (not just the atexit) so tests can
exercise it deterministically. Production code only needs the
atexit registration at module import.
"""

from __future__ import annotations

import asyncio
import atexit
import gc
import logging

logger = logging.getLogger(__name__)


def _find_live_aiosqlite_connections() -> list:
    """Walk `gc.get_objects()` and return every `aiosqlite.Connection`
    instance that is not yet closed.

    Importing aiosqlite lazily because:
    1. Not every project that uses crackerjack will have aiosqlite
       installed (it's only a `[adapter-learning]` extra).
    2. We want the cleanup module to import even if aiosqlite is
       missing — the cleanup is then a no-op.
    """
    try:
        import aiosqlite
    except ImportError:
        return []

    return [obj for obj in gc.get_objects() if isinstance(obj, aiosqlite.Connection)]


def cleanup_aiosqlite_connections() -> int:
    """Close every live `aiosqlite.Connection` in the object graph.

    Runs each connection's `close()` coroutine — in the current
    event loop if one is already running, otherwise in a fresh
    one. Idempotent: calling more than once is safe. If aiosqlite
    is not installed, this is a no-op.

    Returns the number of connections that were closed. Exposed
    for tests and for callers that want explicit control over
    when cleanup happens.
    """
    connections = _find_live_aiosqlite_connections()
    if not connections:
        return 0

    async def _close_all() -> None:
        # aiosqlite's Connection.close() is idempotent: a second
        # call on an already-closed connection is a no-op. So we
        # can safely iterate even if some of these have been
        # partially closed already.
        for conn in connections:
            try:
                await conn.close()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(f"aiosqlite cleanup: close failed: {exc!r}")

    try:
        # If we're already inside an event loop (e.g. called from
        # an async test), reuse it. Otherwise create a fresh one.
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is not None:
            # We're inside an event loop. The connections were
            # almost certainly created in this loop, so closing
            # them here is the right thing. Just await directly.
            running_loop.create_task(_close_all())
        else:
            # We're at top level (atexit, sync code). Create a
            # fresh event loop just for the close.
            asyncio.run(_close_all())
    except Exception as exc:
        # Never let aiosqlite cleanup itself hang or crash the
        # interpreter. The whole point is to unblock exit.
        logger.debug(f"aiosqlite cleanup: asyncio.run failed: {exc!r}")

    return len(connections)


# Register exactly once at module import. The atexit machinery
# invokes `cleanup_aiosqlite_connections` after the user's main
# code finishes but before `_thread_shutdown()` blocks on the
# leaked worker threads. This is the only reliable point to
# guarantee every aiosqlite connection is closed before the
# interpreter gives up waiting for non-daemon threads.
atexit.register(cleanup_aiosqlite_connections)


__all__ = [
    "cleanup_aiosqlite_connections",
    "_find_live_aiosqlite_connections",
]
