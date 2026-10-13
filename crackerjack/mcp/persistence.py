"""SQLite-backed persistence for AsyncTaskManager (C-WIRE Task 6).

This module provides ``AsyncTaskStore``: a process-shared SQLite-backed
durable state for the ``AsyncTaskManager`` class. Task records survive
crackerjack process restarts, enabling the "kill-restart-query" smoke
test and the ``crackerjack_result_store`` MCP tool.

Why SQLite (not the substrate lock sentinel):
``mahavishnu/core/_lock_sentinel.py`` is explicitly an in-process dict
primitive for the HypothesisLock use case. Its docstring defers
cross-process persistence ("If cross-process persistence is required
in the future, this sentinel would need a SQL/DuckDB backend; that's
a larger refactor and out of scope here."). This module IS that larger
refactor — but at the AsyncTaskStore level, not the sentinel level.
The sentinel stays as-is.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import typing as t
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


_VALID_STATUSES: frozenset[str] = frozenset(
    {"pending", "running", "completed", "failed", "timeout"},
)


class AsyncTaskRecord(BaseModel):
    """A single persisted async task record.

    Stored in the SQLite table ``async_tasks`` keyed by ``task_id``.
    ``metadata_json`` deserializes to ``metadata`` on read.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    status: str
    registered_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS async_tasks ("
    "task_id TEXT PRIMARY KEY,"
    "status TEXT NOT NULL CHECK (status IN "
    "('pending', 'running', 'completed', 'failed', 'timeout')),"
    "registered_at TEXT NOT NULL,"
    "metadata_json TEXT NOT NULL DEFAULT '{}'"
    ");"
    "CREATE INDEX IF NOT EXISTS idx_async_tasks_status "
    "ON async_tasks(status);"
    "CREATE INDEX IF NOT EXISTS idx_async_tasks_registered_at "
    "ON async_tasks(registered_at);"
)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_schema_sync(db_path: Path) -> None:
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


class AsyncTaskStore:
    """SQLite-backed persistence for AsyncTaskManager task records.

    All DB access goes through ``loop.run_in_executor`` so async callers
    can ``await`` without blocking the event loop.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    async def _run_in_executor(
        self,
        fn: t.Callable[..., t.Any],
        *args: t.Any,
    ) -> t.Any:
        loop = self._ensure_loop()
        return await loop.run_in_executor(None, fn, *args)

    async def init_schema(self) -> None:
        await self._run_in_executor(_init_schema_sync, self._db_path)

    @staticmethod
    def _register_sync(
        db_path: Path,
        task_id: str,
        status: str,
        metadata_json: str,
        registered_at_iso: str,
    ) -> None:
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO async_tasks "
                "(task_id, status, registered_at, metadata_json) "
                "VALUES (?, ?, ?, ?)",
                (task_id, status, registered_at_iso, metadata_json),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _get_sync(db_path: Path, task_id: str) -> AsyncTaskRecord | None:
        conn = _connect(db_path)
        try:
            cursor = conn.execute(
                "SELECT task_id, status, registered_at, metadata_json "
                "FROM async_tasks WHERE task_id = ?",
                (task_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return AsyncTaskRecord(
                task_id=row[0],
                status=row[1],
                registered_at=datetime.fromisoformat(row[2]),
                metadata=json.loads(row[3]),
            )
        finally:
            conn.close()

    @staticmethod
    def _list_keys_sync(db_path: Path, prefix: str) -> list[str]:
        conn = _connect(db_path)
        try:
            cursor = conn.execute(
                "SELECT task_id FROM async_tasks WHERE task_id LIKE ? "
                "ORDER BY task_id",
                (f"{prefix}%",),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _update_status_sync(
        db_path: Path,
        task_id: str,
        new_status: str,
    ) -> None:
        if new_status not in _VALID_STATUSES:
            msg = f"Invalid status: {new_status!r}"
            raise ValueError(msg)
        conn = _connect(db_path)
        try:
            cursor = conn.execute(
                "UPDATE async_tasks SET status = ? WHERE task_id = ?",
                (new_status, task_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                msg = f"Unknown task_id: {task_id!r}"
                raise KeyError(msg)
        finally:
            conn.close()

    @staticmethod
    def _delete_sync(db_path: Path, task_id: str) -> bool:
        conn = _connect(db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM async_tasks WHERE task_id = ?",
                (task_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    async def register(
        self,
        task_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncTaskRecord:
        if status not in _VALID_STATUSES:
            msg = f"Invalid status: {status!r}"
            raise ValueError(msg)
        metadata_dict = metadata or {}
        record = AsyncTaskRecord(
            task_id=task_id,
            status=status,
            registered_at=datetime.now(UTC),
            metadata=metadata_dict,
        )
        await self._run_in_executor(
            self._register_sync,
            self._db_path,
            task_id,
            status,
            json.dumps(metadata_dict),
            record.registered_at.isoformat(),
        )
        logger.info(
            "crackerjack_async_task_registered task_id=%s status=%s",
            task_id,
            status,
        )
        return record

    async def get(self, task_id: str) -> AsyncTaskRecord | None:
        record = await self._run_in_executor(
            self._get_sync,
            self._db_path,
            task_id,
        )
        if record is None:
            logger.debug(
                "crackerjack_async_task_lookup_miss task_id=%s",
                task_id,
            )
        return record

    async def list_keys(self, prefix: str = "") -> list[str]:
        return await self._run_in_executor(
            self._list_keys_sync,
            self._db_path,
            prefix,
        )

    async def update_status(self, task_id: str, new_status: str) -> None:
        await self._run_in_executor(
            self._update_status_sync,
            self._db_path,
            task_id,
            new_status,
        )
        logger.info(
            "crackerjack_async_task_status_updated task_id=%s status=%s",
            task_id,
            new_status,
        )

    async def delete(self, task_id: str) -> bool:
        return await self._run_in_executor(
            self._delete_sync,
            self._db_path,
            task_id,
        )


__all__ = ["AsyncTaskRecord", "AsyncTaskStore"]
