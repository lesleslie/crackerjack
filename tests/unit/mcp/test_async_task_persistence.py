"""Unit tests for the SQLite-backed AsyncTaskStore (C-WIRE Task 6).

Coverage:
- ``register`` persists via SQLite.
- ``register`` upserts the same ``task_id`` with a new status (no
  release/re-register dance needed).
- ``update_status`` is the explicit status-change path.
- ``get`` returns ``None`` for unknown tasks.
- ``list_keys`` filters by prefix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.mcp.persistence import AsyncTaskStore


@pytest.mark.unit
async def test_register_persists_via_sqlite(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = AsyncTaskStore(db)
    await store.init_schema()
    record = await store.register("task-1", "running")
    fetched = await store.get("task-1")
    assert fetched is not None
    assert fetched.task_id == "task-1"
    assert fetched.status == "running"
    assert record.registered_at == fetched.registered_at


@pytest.mark.unit
async def test_register_upserts_with_new_status(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = AsyncTaskStore(db)
    await store.init_schema()
    await store.register("task-1", "running")
    await store.register("task-1", "completed")
    fetched = await store.get("task-1")
    assert fetched is not None
    assert fetched.status == "completed"


@pytest.mark.unit
async def test_status_update_via_explicit_path(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = AsyncTaskStore(db)
    await store.init_schema()
    await store.register("task-1", "running")
    await store.update_status("task-1", "failed")
    fetched = await store.get("task-1")
    assert fetched is not None
    assert fetched.status == "failed"


@pytest.mark.unit
async def test_get_returns_none_for_unknown_task(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = AsyncTaskStore(db)
    await store.init_schema()
    fetched = await store.get("nonexistent")
    assert fetched is None


@pytest.mark.unit
async def test_list_keys_with_prefix(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    store = AsyncTaskStore(db)
    await store.init_schema()
    await store.register("async:1", "running")
    await store.register("async:2", "running")
    await store.register("other:1", "running")

    async_keys = await store.list_keys("async:")
    assert sorted(async_keys) == ["async:1", "async:2"]

    other_keys = await store.list_keys("other:")
    assert other_keys == ["other:1"]

    no_match = await store.list_keys("nope:")
    assert no_match == []
