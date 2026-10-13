"""Unit tests for the reap_zombies cron (C-WIRE Task 6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from sqlite3 import connect
from types import SimpleNamespace

import pytest

from crackerjack.mcp.persistence import AsyncTaskStore
from crackerjack.mcp.task_manager import AsyncTaskManager


def _fake_settings(zombie_age_seconds: int = 604800) -> SimpleNamespace:
    return SimpleNamespace(
        async_task=SimpleNamespace(
            zombie_age_seconds=zombie_age_seconds,
            reap_zombies_interval_seconds=3600,
            storage_path=Path("/tmp/nope.db"),
        ),
    )


def _build_manager(store: AsyncTaskStore, settings: SimpleNamespace) -> AsyncTaskManager:
    return AsyncTaskManager(
        max_concurrent_tasks=5,
        store=store,
        settings=settings,
    )


@pytest.mark.unit
async def test_reap_zombies_removes_old_pending_entries(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = AsyncTaskStore(db)
    await store.init_schema()
    await store.register("task-1", "pending")

    eight_days_ago = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    conn = connect(str(db))
    try:
        conn.execute(
            "UPDATE async_tasks SET registered_at = ? WHERE task_id = ?",
            (eight_days_ago, "task-1"),
        )
        conn.commit()
    finally:
        conn.close()

    mgr = _build_manager(store, _fake_settings())
    deleted = await mgr._reap_zombies()
    assert deleted == 1
    assert await store.get("task-1") is None


@pytest.mark.unit
async def test_reap_zombies_preserves_recent_entries(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = AsyncTaskStore(db)
    await store.init_schema()
    await store.register("task-1", "running")

    mgr = _build_manager(store, _fake_settings())
    deleted = await mgr._reap_zombies()
    assert deleted == 0
    record = await store.get("task-1")
    assert record is not None
    assert record.status == "running"


@pytest.mark.unit
async def test_reap_zombies_preserves_completed_entries(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = AsyncTaskStore(db)
    await store.init_schema()

    eight_days_ago = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    conn = connect(str(db))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO async_tasks "
            "(task_id, status, registered_at, metadata_json) "
            "VALUES (?, ?, ?, ?)",
            ("task-1", "completed", eight_days_ago, "{}"),
        )
        conn.commit()
    finally:
        conn.close()

    mgr = _build_manager(store, _fake_settings())
    deleted = await mgr._reap_zombies()
    assert deleted == 0
    record = await store.get("task-1")
    assert record is not None
    assert record.status == "completed"
