import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from aiohttp import ClientSession, ClientTimeout

logger = logging.getLogger(__name__)


class HTTPConnectionPool:
    def __init__(
        self,
        timeout: float = 30.0,
        connect_timeout: float = 10.0,
        max_connections: int = 100,
        max_per_host: int = 30,
    ) -> None:
        self.timeout = ClientTimeout(
            total=timeout,
            connect=connect_timeout,
        )
        self.max_connections = max_connections
        self.max_per_host = max_per_host
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def get_session(self) -> ClientSession:
        if self._initialized and self._session is not None:
            return self._session

        async with self._lock:
            if self._initialized and self._session is not None:
                return self._session

            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_per_host,
                enable_cleanup_closed=True,
            )

            self._session = ClientSession(
                connector=connector,
                timeout=self.timeout,
                raise_for_status=False,
            )

            self._initialized = True
            logger.debug(
                "HTTP connection pool initialized",
                extra={
                    "max_connections": self.max_connections,
                    "max_per_host": self.max_per_host,
                    "timeout": self.timeout.total,
                },
            )

            return self._session

    @asynccontextmanager
    async def get_session_context(self):
        session = await self.get_session()
        try:
            yield session
        except Exception as e:
            logger.debug(f"HTTP request error: {e}")
            raise

    async def close(self) -> None:
        async with self._lock:
            if self._session is not None and not self._session.closed:
                await self._session.close()
                self._session = None
                self._initialized = False
                logger.debug("HTTP connection pool closed")

    async def __aenter__(self) -> "HTTPConnectionPool":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def is_closed(self) -> bool:
        return self._session is None or self._session.closed


_global_pool: HTTPConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def get_http_pool(
    timeout: float = 30.0,
    connect_timeout: float = 10.0,
    max_connections: int = 100,
    max_per_host: int = 30,
) -> HTTPConnectionPool:
    global _global_pool

    if _global_pool is not None:
        return _global_pool

    async with _pool_lock:
        if _global_pool is not None:
            return _global_pool

        _global_pool = HTTPConnectionPool(
            timeout=timeout,
            connect_timeout=connect_timeout,
            max_connections=max_connections,
            max_per_host=max_per_host,
        )

        logger.info("HTTP connection pool singleton created")
        return _global_pool


async def close_http_pool() -> None:
    global _global_pool

    if _global_pool is not None:
        await _global_pool.close()
        _global_pool = None
        logger.info("HTTP connection pool singleton destroyed")
