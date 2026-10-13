"""End-to-end smoke for ``crackerjack_result_store`` (C-WIRE Task 6).

Per ``.claude/decisions/mcp-backend-wiring-discipline.md`` — every
registered tool must have an end-to-end smoke that proves the wire is
live. This test boots the production ``register_async_task_tools``
against a stub FastMCP, registers a record, calls the tool, asserts
the response is non-empty (and the document envelope shape).
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def isolated_async_task_store(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Path]:
    """Point the AsyncTaskSettings storage path at a temp file."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="cj-async-tasks-"))
    db_path = tmp_dir / "async_tasks.db"
    monkeypatch.setenv("HOME", str(tmp_dir.parent))
    yield db_path
    try:
        db_path.unlink()
    except FileNotFoundError:
        pass
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


class _StubApp:
    """Minimal FastMCP shim with a ``tool(name)`` decorator API."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Any]] = {}

    def tool(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = fn
            return fn

        return decorator


@pytest.mark.asyncio
async def test_crackerjack_result_store_is_registered_and_live(
    isolated_async_task_store: Path,
) -> None:
    """The ``crackerjack_result_store`` tool is wired and responsive.

    Asserts the per-tool e2e smoke contract from the wiring discipline:
    the tool is registered, accepts a ``task_id`` argument, and returns
    a non-empty JSON envelope (both on hit and on miss).
    """
    from crackerjack.config.settings import CrackerjackSettings
    from crackerjack.mcp.persistence import AsyncTaskStore
    from crackerjack.mcp.task_manager import AsyncTaskManager
    from crackerjack.mcp.tools.async_task_tools import (
        register_async_task_tools,
        set_task_manager,
    )

    settings = CrackerjackSettings()
    store = AsyncTaskStore(settings.async_task.storage_path)
    manager = AsyncTaskManager(
        max_concurrent_tasks=5,
        store=store,
        settings=settings,
    )
    await manager.start()
    set_task_manager(manager)
    try:
        app = _StubApp()
        register_async_task_tools(app)  # type: ignore[arg-type]

        assert "crackerjack_result_store" in app.tools, (
            "mcp-backend-wiring-discipline: result_store must be registered"
        )
        result_store = app.tools["crackerjack_result_store"]

        # Miss envelope (no record exists yet).
        miss_payload = await result_store(task_id="never-registered")
        miss = json.loads(miss_payload)
        assert miss["found"] is False
        assert miss["task_id"] == "never-registered"

        # Register a record, then hit.
        await manager.register_task("smoke-1", "running", {"via": "e2e"})
        hit_payload = await result_store(task_id="smoke-1")
        hit = json.loads(hit_payload)
        assert hit["found"] is True
        assert hit["task"]["task_id"] == "smoke-1"
        assert hit["task"]["status"] == "running"
        assert hit["task"]["metadata"] == {"via": "e2e"}
    finally:
        await manager.stop()
        set_task_manager(None)
