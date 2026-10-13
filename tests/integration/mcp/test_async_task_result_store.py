"""Integration tests for the AsyncTaskManager -> result_store wire (C-WIRE Task 6).

These exercise the live ``crackerjack_result_store`` MCP tool path end-to-end:
the manager is constructed via the same hook ``create_mcp_server`` uses, then
the tool closure reads from the module-level holder to look up records.
"""

from __future__ import annotations

import json
import typing as t
from pathlib import Path

import pytest

from crackerjack.config.settings import CrackerjackSettings
from crackerjack.mcp.persistence import AsyncTaskStore
from crackerjack.mcp.task_manager import AsyncTaskManager
from crackerjack.mcp.tools.async_task_tools import (
    register_async_task_tools,
    set_task_manager,
)


class _FakeFastMCP:
    """Minimal stand-in for a ``FastMCP`` instance; captures registered tools."""

    def __init__(self) -> None:
        self.tools: dict[str, t.Any] = {}

    def tool(self, name: str | None = None) -> t.Callable[[t.Any], t.Any]:
        def decorator(fn: t.Any) -> t.Any:
            self.tools[name or fn.__name__] = fn
            return fn

        return decorator


@pytest.fixture
async def wired_manager(tmp_path: Path) -> AsyncTaskManager:
    db = tmp_path / "tasks.db"
    store = AsyncTaskStore(db)
    manager = AsyncTaskManager(
        max_concurrent_tasks=5,
        store=store,
        settings=CrackerjackSettings(),
    )
    await manager.start()
    set_task_manager(manager)
    try:
        yield manager
    finally:
        await manager.stop()
        set_task_manager(None)


@pytest.mark.integration
async def test_result_store_returns_envelope_on_hit(
    wired_manager: AsyncTaskManager,
) -> None:
    app = _FakeFastMCP()
    register_async_task_tools(app)
    assert "crackerjack_result_store" in app.tools

    await wired_manager.register_task("hit-task", "running", {"k": "v"})
    result_fn = app.tools["crackerjack_result_store"]
    payload = await result_fn(task_id="hit-task")
    envelope = json.loads(payload)
    assert envelope["found"] is True
    assert envelope["task"]["task_id"] == "hit-task"
    assert envelope["task"]["status"] == "running"
    assert envelope["task"]["metadata"] == {"k": "v"}


@pytest.mark.integration
async def test_result_store_returns_envelope_on_miss(
    wired_manager: AsyncTaskManager,
) -> None:
    app = _FakeFastMCP()
    register_async_task_tools(app)
    result_fn = app.tools["crackerjack_result_store"]
    payload = await result_fn(task_id="unknown")
    envelope = json.loads(payload)
    assert envelope == {"found": False, "task_id": "unknown"}


@pytest.mark.integration
async def test_async_task_persistence_survives_cross_restart(
    tmp_path: Path,
) -> None:
    """Per C-WIRE Task 6 spec: "kill-restart-query" durability test.

    Register a task through one ``AsyncTaskStore`` instance at one
    db_path, drop the in-memory state, instantiate a new store at the
    same path, and assert the record survives.
    """
    db = tmp_path / "durable.db"
    store = AsyncTaskStore(db)
    await store.init_schema()
    await store.register("durable-task", "running", {"persistent": True})

    # Drop the in-memory store object, replacing it with a fresh one at
    # the same path. (this is the persistence proof)
    del store
    store2 = AsyncTaskStore(db)
    await store2.init_schema()
    fetched = await store2.get("durable-task")
    assert fetched is not None
    assert fetched.status == "running"
    assert fetched.metadata == {"persistent": True}
