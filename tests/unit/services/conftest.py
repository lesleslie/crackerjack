"""Shared fixtures for tests/unit/services/.

Resets the ``_global_pool`` singleton and ``_pool_lock`` between tests so
the asyncio event loop from the previous test doesn't leak into the next.
pytest-asyncio creates a fresh loop per test by default, but module-level
``asyncio.Lock()`` instances are bound to the loop that was current when the
module was first imported — without resetting the lock, a test that runs
after a previous test that touched the lock will see ``RuntimeError:
<Lock> is bound to a different event loop``.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _reset_connection_pool_state() -> None:
    """Snapshot and restore connection-pool singletons/locks for each test."""
    from crackerjack.services import connection_pool

    original_pool = connection_pool._global_pool
    original_lock = connection_pool._pool_lock
    connection_pool._global_pool = None
    connection_pool._pool_lock = asyncio.Lock()
    try:
        yield
    finally:
        connection_pool._global_pool = original_pool
        connection_pool._pool_lock = original_lock
