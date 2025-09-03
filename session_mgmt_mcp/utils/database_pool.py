#!/usr/bin/env python3
"""Database connection pooling for DuckDB.

This module provides efficient connection pooling and management for DuckDB operations.
"""

import asyncio
import atexit
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    duckdb = None

from .logging import get_session_logger

logger = get_session_logger()


class DatabaseConnectionPool:
    """Thread-safe connection pool for DuckDB."""

    def __init__(self, db_path: str, max_connections: int = 5) -> None:
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool: list = []
        self._pool_lock = threading.Lock()
        self._active_connections: dict[int, Any] = {}
        self._executor = None
        self._closed = False

        # Ensure database directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Register cleanup on exit
        atexit.register(self.close_all)

    def _create_connection(self):
        """Create a new DuckDB connection."""
        if not DUCKDB_AVAILABLE:
            msg = "DuckDB not available"
            raise ImportError(msg)

        try:
            conn = duckdb.connect(self.db_path)
            # Set optimal pragmas for performance
            conn.execute("PRAGMA threads=4")
            conn.execute("PRAGMA memory_limit='1GB'")
            conn.execute("PRAGMA temp_directory='/tmp'")
            return conn
        except Exception as e:
            logger.exception(f"Failed to create database connection: {e}")
            raise

    def get_connection(self):
        """Get a connection from the pool or create a new one."""
        if self._closed:
            msg = "Connection pool is closed"
            raise RuntimeError(msg)

        with self._pool_lock:
            if self._pool:
                conn = self._pool.pop()
                self._active_connections[id(conn)] = conn
                return conn
            if len(self._active_connections) < self.max_connections:
                conn = self._create_connection()
                self._active_connections[id(conn)] = conn
                return conn
            msg = f"Maximum connections ({self.max_connections}) reached"
            raise RuntimeError(
                msg,
            )

    def return_connection(self, conn) -> None:
        """Return a connection to the pool."""
        if self._closed or not conn:
            return

        with self._pool_lock:
            conn_id = id(conn)
            if conn_id in self._active_connections:
                del self._active_connections[conn_id]
                if len(self._pool) < self.max_connections:
                    self._pool.append(conn)
                else:
                    try:
                        conn.close()
                    except Exception as e:
                        logger.warning(f"Error closing excess connection: {e}")

    @asynccontextmanager
    async def get_async_connection(self):
        """Async context manager for getting database connections."""
        conn = None
        try:
            # Get connection in executor to avoid blocking
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(self._get_executor(), self.get_connection)
            yield conn
        except Exception as e:
            logger.exception(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                # Return connection in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self._get_executor(),
                    self.return_connection,
                    conn,
                )

    def _get_executor(self):
        """Get or create thread pool executor."""
        if self._executor is None:
            self._executor = asyncio.ThreadPoolExecutor(max_workers=2)
        return self._executor

    async def execute_query(self, query: str, parameters: tuple | None = None):
        """Execute a query using a pooled connection."""
        async with self.get_async_connection() as conn:
            loop = asyncio.get_event_loop()

            def _execute():
                try:
                    if parameters:
                        return conn.execute(query, parameters).fetchall()
                    return conn.execute(query).fetchall()
                except Exception as e:
                    logger.exception(
                        f"Query execution error: {e}",
                        extra={"query": query[:100]},
                    )
                    raise

            return await loop.run_in_executor(self._get_executor(), _execute)

    async def execute_many(self, query: str, parameter_list: list):
        """Execute a query multiple times with different parameters."""
        async with self.get_async_connection() as conn:
            loop = asyncio.get_event_loop()

            def _execute_many():
                try:
                    results = []
                    for params in parameter_list:
                        result = conn.execute(query, params).fetchall()
                        results.append(result)
                    return results
                except Exception as e:
                    logger.exception(f"Batch query execution error: {e}")
                    raise

            return await loop.run_in_executor(self._get_executor(), _execute_many)

    def get_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        with self._pool_lock:
            return {
                "total_connections": len(self._active_connections) + len(self._pool),
                "active_connections": len(self._active_connections),
                "pooled_connections": len(self._pool),
                "max_connections": self.max_connections,
                "pool_utilization": len(self._active_connections)
                / self.max_connections,
                "db_path": self.db_path,
            }

    def close_all(self) -> None:
        """Close all connections and clean up."""
        if self._closed:
            return

        self._closed = True

        with self._pool_lock:
            # Close pooled connections
            for conn in self._pool:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing pooled connection: {e}")

            # Close active connections
            for conn in self._active_connections.values():
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing active connection: {e}")

            self._pool.clear()
            self._active_connections.clear()

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

        logger.info("Database connection pool closed")


# Global connection pool instance
_connection_pools: dict[str, DatabaseConnectionPool] = {}
_pools_lock = threading.Lock()


def get_database_pool(db_path: str, max_connections: int = 5) -> DatabaseConnectionPool:
    """Get or create a database connection pool for the given path."""
    with _pools_lock:
        if db_path not in _connection_pools:
            _connection_pools[db_path] = DatabaseConnectionPool(
                db_path,
                max_connections,
            )
        return _connection_pools[db_path]


def close_all_pools() -> None:
    """Close all database connection pools."""
    with _pools_lock:
        for pool in _connection_pools.values():
            pool.close_all()
        _connection_pools.clear()


# Register cleanup on module exit
atexit.register(close_all_pools)
