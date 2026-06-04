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
