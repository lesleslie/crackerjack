import pytest

import crackerjack.services.connection_pool as connection_pool


class DummyConnector:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


class DummySession:
    def __init__(self, connector, timeout, raise_for_status) -> None:
        self.connector = connector
        self.timeout = timeout
        self.raise_for_status = raise_for_status
        self.closed = False
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True


@pytest.fixture(autouse=True)
def reset_global_pool():
    original_pool = connection_pool._global_pool
    connection_pool._global_pool = None
    yield
    if original_pool is not None:
        connection_pool._global_pool = original_pool
    else:
        connection_pool._global_pool = None


@pytest.mark.asyncio
async def test_get_session_creates_and_reuses_session(monkeypatch):
    connector_calls: list[DummyConnector] = []
    session_calls: list[DummySession] = []

    def fake_connector(*args, **kwargs):
        connector = DummyConnector(*args, **kwargs)
        connector_calls.append(connector)
        return connector

    def fake_session(*args, **kwargs):
        session = DummySession(*args, **kwargs)
        session_calls.append(session)
        return session

    monkeypatch.setattr(connection_pool.aiohttp, "TCPConnector", fake_connector)
    monkeypatch.setattr(connection_pool, "ClientSession", fake_session)

    pool = connection_pool.HTTPConnectionPool(
        timeout=12.5,
        connect_timeout=4.0,
        max_connections=20,
        max_per_host=7,
    )

    session = await pool.get_session()
    assert session is session_calls[0]
    assert connector_calls[0].kwargs == {
        "limit": 20,
        "limit_per_host": 7,
        "enable_cleanup_closed": True,
    }
    assert session.timeout.total == 12.5
    assert session.raise_for_status is False
    assert pool._initialized is True
    assert pool.is_closed() is False

    reused = await pool.get_session()
    assert reused is session
    assert len(session_calls) == 1


@pytest.mark.asyncio
async def test_session_context_and_close(monkeypatch):
    monkeypatch.setattr(connection_pool.aiohttp, "TCPConnector", lambda *args, **kwargs: DummyConnector(*args, **kwargs))
    monkeypatch.setattr(connection_pool, "ClientSession", lambda *args, **kwargs: DummySession(*args, **kwargs))

    pool = connection_pool.HTTPConnectionPool()

    with pytest.raises(RuntimeError, match="boom"):
        async with pool.get_session_context():
            raise RuntimeError("boom")

    assert pool._session is not None
    assert pool._initialized is True

    await pool.close()
    assert pool._session is None
    assert pool._initialized is False
    assert pool.is_closed() is True


@pytest.mark.asyncio
async def test_aenter_aexit_and_global_pool(monkeypatch):
    monkeypatch.setattr(connection_pool.aiohttp, "TCPConnector", lambda *args, **kwargs: DummyConnector(*args, **kwargs))
    monkeypatch.setattr(connection_pool, "ClientSession", lambda *args, **kwargs: DummySession(*args, **kwargs))

    async with connection_pool.HTTPConnectionPool() as pool:
        assert await pool.get_session()

    assert pool.is_closed() is True

    first = await connection_pool.get_http_pool(
        timeout=9.0,
        connect_timeout=1.5,
        max_connections=11,
        max_per_host=4,
    )
    second = await connection_pool.get_http_pool()
    assert first is second
    assert first.timeout.total == 9.0
    assert first.max_connections == 11
    assert first.max_per_host == 4

    await connection_pool.close_http_pool()
    assert connection_pool._global_pool is None


@pytest.mark.asyncio
async def test_close_noop_for_missing_or_closed_session(monkeypatch):
    monkeypatch.setattr(connection_pool.aiohttp, "TCPConnector", lambda *args, **kwargs: DummyConnector(*args, **kwargs))
    monkeypatch.setattr(connection_pool, "ClientSession", lambda *args, **kwargs: DummySession(*args, **kwargs))

    pool = connection_pool.HTTPConnectionPool()
    await pool.close()

    session = await pool.get_session()
    session.closed = True
    await pool.close()

    assert session.close_calls == 0
    assert pool._session is session
    assert pool._initialized is True

    await connection_pool.close_http_pool()
    assert connection_pool._global_pool is None
