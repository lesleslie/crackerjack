from __future__ import annotations

import asyncio
import logging

import pytest

import crackerjack.services.connection_pool as connection_pool


# ---------------------------------------------------------------------------
# Local fakes mirroring aiohttp's TCPConnector + ClientSession surface so we
# never touch real network state. They are intentionally tiny: the production
# code only touches the constructor kwargs and `close()`.
# ---------------------------------------------------------------------------


class FakeConnector:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs


class FakeSession:
    def __init__(
        self,
        connector: object | None = None,
        timeout: object | None = None,
        raise_for_status: bool = False,
        **kwargs: object,
    ) -> None:
        self.connector = connector
        self.timeout = timeout
        self.raise_for_status = raise_for_status
        self.closed = False
        self.close_calls = 0
        self.kwargs = kwargs

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True


@pytest.fixture(autouse=True)
def _patch_aiohttp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace aiohttp.TCPConnector + ClientSession with fakes for every test."""
    monkeypatch.setattr(
        connection_pool.aiohttp,
        "TCPConnector",
        lambda *a, **kw: FakeConnector(*a, **kw),
    )
    monkeypatch.setattr(
        connection_pool,
        "ClientSession",
        lambda *a, **kw: FakeSession(*a, **kw),
    )


@pytest.fixture(autouse=True)
def _reset_global_pool() -> None:
    """Snapshot & restore the module-level singleton between tests."""
    original = connection_pool._global_pool
    connection_pool._global_pool = None
    try:
        yield
    finally:
        connection_pool._global_pool = original


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_stores_timeouts_on_client_timeout(self) -> None:
        pool = connection_pool.HTTPConnectionPool(
            timeout=12.5, connect_timeout=4.0
        )

        assert isinstance(pool.timeout, connection_pool.ClientTimeout)
        assert pool.timeout.total == 12.5
        assert pool.timeout.connect == 4.0

    def test_stores_pool_size_config(self) -> None:
        pool = connection_pool.HTTPConnectionPool(
            max_connections=42, max_per_host=7
        )

        assert pool.max_connections == 42
        assert pool.max_per_host == 7

    def test_starts_in_uninitialized_state(self) -> None:
        pool = connection_pool.HTTPConnectionPool()

        assert pool._session is None
        assert pool._initialized is False
        # asyncio.Lock created lazily here, so the attribute may not exist
        # until first use; instantiate to confirm.
        assert isinstance(pool._lock, asyncio.Lock)

    def test_default_config_matches_module_defaults(self) -> None:
        pool = connection_pool.HTTPConnectionPool()

        assert pool.timeout.total == 30.0
        assert pool.timeout.connect == 10.0
        assert pool.max_connections == 100
        assert pool.max_per_host == 30


# ---------------------------------------------------------------------------
# get_session — first call creates the session
# ---------------------------------------------------------------------------


class TestGetSessionFirstCall:
    async def test_creates_tcp_connector_with_expected_kwargs(self) -> None:
        captured: list[FakeConnector] = []
        original = connection_pool.aiohttp.TCPConnector

        def capturing_connector(*args: object, **kwargs: object) -> FakeConnector:
            connector = original(*args, **kwargs)
            captured.append(connector)
            return connector

        connection_pool.aiohttp.TCPConnector = capturing_connector
        try:
            pool = connection_pool.HTTPConnectionPool(
                max_connections=55, max_per_host=11
            )
            await pool.get_session()
        finally:
            connection_pool.aiohttp.TCPConnector = original

        assert len(captured) == 1
        assert captured[0].kwargs == {
            "limit": 55,
            "limit_per_host": 11,
            "enable_cleanup_closed": True,
        }

    async def test_session_receives_connector_and_timeout(self) -> None:
        captured: list[FakeSession] = []
        original = connection_pool.ClientSession

        def capturing_session(*args: object, **kwargs: object) -> FakeSession:
            session = original(*args, **kwargs)
            captured.append(session)
            return session

        connection_pool.ClientSession = capturing_session
        try:
            pool = connection_pool.HTTPConnectionPool(
                timeout=9.0, connect_timeout=3.0
            )
            await pool.get_session()
        finally:
            connection_pool.ClientSession = original

        assert len(captured) == 1
        session = captured[0]
        assert session.connector is not None
        assert session.timeout is pool.timeout
        assert session.raise_for_status is False

    async def test_marks_initialized_and_caches_session(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        assert pool._initialized is False

        session = await pool.get_session()

        assert pool._session is session
        assert pool._initialized is True
        assert pool.is_closed() is False

    async def test_logs_debug_on_initialization(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        pool = connection_pool.HTTPConnectionPool(
            timeout=20.0, max_connections=33, max_per_host=4
        )

        with caplog.at_level(logging.DEBUG, logger="crackerjack.services.connection_pool"):
            await pool.get_session()

        assert any(
            "HTTP connection pool initialized" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# get_session — subsequent calls
# ---------------------------------------------------------------------------


class TestGetSessionReuse:
    async def test_returns_cached_session_on_second_call(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        first = await pool.get_session()

        second = await pool.get_session()

        assert second is first
        assert pool._session is first

    async def test_does_not_create_extra_sessions_across_calls(self) -> None:
        capture: list[FakeSession] = []
        original = connection_pool.ClientSession

        def tracking_session(*args: object, **kwargs: object) -> FakeSession:
            session = original(*args, **kwargs)
            capture.append(session)
            return session

        connection_pool.ClientSession = tracking_session
        try:
            pool = connection_pool.HTTPConnectionPool()
            await pool.get_session()
            await pool.get_session()
            await pool.get_session()
        finally:
            connection_pool.ClientSession = original

        assert len(capture) == 1

    async def test_concurrent_coroutines_share_single_session(self) -> None:
        capture: list[FakeSession] = []
        original = connection_pool.ClientSession

        def tracking_session(*args: object, **kwargs: object) -> FakeSession:
            session = original(*args, **kwargs)
            capture.append(session)
            return session

        connection_pool.ClientSession = tracking_session
        try:
            pool = connection_pool.HTTPConnectionPool()
            results = await asyncio.gather(
                pool.get_session(),
                pool.get_session(),
                pool.get_session(),
                pool.get_session(),
            )
        finally:
            connection_pool.ClientSession = original

        assert len(capture) == 1
        # All concurrent callers see the same session instance.
        assert len({id(r) for r in results}) == 1

    async def test_locked_caller_reuses_already_initialized_session(self) -> None:
        """The double-checked lock path inside the `async with self._lock`."""
        pool = connection_pool.HTTPConnectionPool()

        # Manually mark the pool as initialized under the lock so that the
        # second check inside the `async with` block reuses the cached value.
        async with pool._lock:
            preseed = FakeSession(FakeConnector(), pool.timeout, False)
            pool._session = preseed
            pool._initialized = True

        session = await pool.get_session()

        assert session is preseed

    async def test_inner_lock_check_returns_cached_session(self) -> None:
        """While `pool._lock` is held externally, the slow-path check fires."""
        pool = connection_pool.HTTPConnectionPool()

        # Acquire (not via `async with`, so the lock is still held below).
        await pool._lock.acquire()
        try:
            task = asyncio.create_task(pool.get_session())
            # Let the task start and block on the lock acquire.
            await asyncio.sleep(0)

            preseed = FakeSession(FakeConnector(), pool.timeout, False)
            pool._session = preseed
            pool._initialized = True
        finally:
            pool._lock.release()

        session = await task

        assert session is preseed


# ---------------------------------------------------------------------------
# get_session_context
# ---------------------------------------------------------------------------


class TestGetSessionContext:
    async def test_yields_session_and_returns_normally(self) -> None:
        pool = connection_pool.HTTPConnectionPool()

        async with pool.get_session_context() as session:
            inner_session = session

        assert inner_session is pool._session
        assert pool._initialized is True

    async def test_reraises_exception_from_body(self) -> None:
        pool = connection_pool.HTTPConnectionPool()

        with pytest.raises(RuntimeError, match="boom"):
            async with pool.get_session_context():
                raise RuntimeError("boom")

        # Session should still be cached after the failure.
        assert pool._session is not None
        assert pool._initialized is True

    async def test_logs_debug_when_body_raises(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        pool = connection_pool.HTTPConnectionPool()

        with caplog.at_level(logging.DEBUG, logger="crackerjack.services.connection_pool"):
            with pytest.raises(ValueError):
                async with pool.get_session_context():
                    raise ValueError("nope")

        assert any(
            "HTTP request error" in record.message for record in caplog.records
        )


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    async def test_closes_open_session_and_resets_state(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        session = await pool.get_session()
        assert session.closed is False

        await pool.close()

        assert session.close_calls == 1
        assert session.closed is True
        assert pool._session is None
        assert pool._initialized is False

    async def test_is_noop_when_session_already_none(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        assert pool._session is None

        await pool.close()  # should not raise

        assert pool._session is None
        assert pool._initialized is False

    async def test_is_noop_when_session_already_closed(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        session = await pool.get_session()
        session.closed = True  # mark externally closed

        await pool.close()

        assert session.close_calls == 0
        # State remains because production only resets after a successful close.
        assert pool._session is session
        assert pool._initialized is True

    async def test_second_close_call_is_noop(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        session = await pool.get_session()

        await pool.close()
        await pool.close()

        assert session.close_calls == 1
        assert pool._session is None

    async def test_close_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        pool = connection_pool.HTTPConnectionPool()
        await pool.get_session()

        with caplog.at_level(logging.DEBUG, logger="crackerjack.services.connection_pool"):
            await pool.close()

        assert any(
            "HTTP connection pool closed" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# Async context manager protocol
# ---------------------------------------------------------------------------


class TestAsyncContextManager:
    async def test_aenter_returns_self(self) -> None:
        pool = connection_pool.HTTPConnectionPool()

        result = await pool.__aenter__()

        assert result is pool

    async def test_aexit_closes_session(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        session = await pool.get_session()

        await pool.__aexit__(None, None, None)

        assert session.closed is True
        assert pool.is_closed() is True

    async def test_full_async_with_block(self) -> None:
        async with connection_pool.HTTPConnectionPool() as pool:
            session = await pool.get_session()
            assert session is pool._session

        assert pool.is_closed() is True


# ---------------------------------------------------------------------------
# is_closed
# ---------------------------------------------------------------------------


class TestIsClosed:
    async def test_initially_closed(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        assert pool.is_closed() is True

    async def test_open_after_session_created(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        await pool.get_session()

        assert pool.is_closed() is False

    async def test_closed_after_explicit_close(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        await pool.get_session()

        await pool.close()

        assert pool.is_closed() is True

    async def test_closed_when_session_flag_indicates_closed(self) -> None:
        pool = connection_pool.HTTPConnectionPool()
        session = await pool.get_session()
        session.closed = True  # mark without going through pool.close()

        assert pool.is_closed() is True


# ---------------------------------------------------------------------------
# get_http_pool (module-level singleton)
# ---------------------------------------------------------------------------


class TestGetHttpPool:
    async def test_first_call_creates_pool(self) -> None:
        pool = await connection_pool.get_http_pool(
            timeout=15.0,
            connect_timeout=2.5,
            max_connections=88,
            max_per_host=12,
        )

        assert isinstance(pool, connection_pool.HTTPConnectionPool)
        assert pool.timeout.total == 15.0
        assert pool.timeout.connect == 2.5
        assert pool.max_connections == 88
        assert pool.max_per_host == 12
        assert connection_pool._global_pool is pool

    async def test_subsequent_calls_return_same_instance(self) -> None:
        first = await connection_pool.get_http_pool()
        second = await connection_pool.get_http_pool()
        third = await connection_pool.get_http_pool()

        assert first is second is third
        assert connection_pool._global_pool is first

    async def test_kwargs_ignored_when_pool_already_exists(self) -> None:
        first = await connection_pool.get_http_pool(
            timeout=5.0, max_connections=10, max_per_host=2
        )

        # Different kwargs must NOT replace the existing pool.
        second = await connection_pool.get_http_pool(
            timeout=99.0, max_connections=999, max_per_host=999
        )

        assert second is first
        assert first.timeout.total == 5.0
        assert first.max_connections == 10
        assert first.max_per_host == 2

    async def test_double_checked_lock_reuses_existing_pool(self) -> None:
        """The slow-path inside `async with _pool_lock` must reuse, not recreate."""
        # Seed a pool under the lock so the second check fires.
        async with connection_pool._pool_lock:
            existing = connection_pool.HTTPConnectionPool()
            connection_pool._global_pool = existing

        result = await connection_pool.get_http_pool()

        assert result is existing

    async def test_inner_lock_check_returns_cached_global_pool(self) -> None:
        """While `_pool_lock` is held externally, the slow-path check fires."""
        await connection_pool._pool_lock.acquire()
        try:
            task = asyncio.create_task(connection_pool.get_http_pool())
            await asyncio.sleep(0)

            existing = connection_pool.HTTPConnectionPool()
            connection_pool._global_pool = existing
        finally:
            connection_pool._pool_lock.release()

        result = await task

        assert result is existing

    async def test_logs_info_on_creation(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="crackerjack.services.connection_pool"):
            await connection_pool.get_http_pool()

        assert any(
            "HTTP connection pool singleton created" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# close_http_pool
# ---------------------------------------------------------------------------


class TestCloseHttpPool:
    async def test_closes_and_clears_global_pool(self) -> None:
        pool = await connection_pool.get_http_pool()
        session = await pool.get_session()

        await connection_pool.close_http_pool()

        assert session.closed is True
        assert connection_pool._global_pool is None

    async def test_second_call_is_noop(self) -> None:
        await connection_pool.get_http_pool()
        await connection_pool.close_http_pool()

        # Must not raise even though the global pool is now None.
        await connection_pool.close_http_pool()

        assert connection_pool._global_pool is None

    async def test_call_is_noop_when_no_pool_exists(self) -> None:
        assert connection_pool._global_pool is None

        await connection_pool.close_http_pool()

        assert connection_pool._global_pool is None

    async def test_logs_info_on_close(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        await connection_pool.get_http_pool()

        with caplog.at_level(logging.INFO, logger="crackerjack.services.connection_pool"):
            await connection_pool.close_http_pool()

        assert any(
            "HTTP connection pool singleton destroyed" in record.message
            for record in caplog.records
        )
