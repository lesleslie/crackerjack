"""Tests for ``crackerjack.mcp.tools.eventbridge_tools``.

The module exposes two top-level functions:
- ``set_eventbridge_publisher(publisher)`` sets module-level singleton
- ``register_eventbridge_tools(mcp_app, publisher, enabled)`` registers
  an MCP tool that dispatches to the appropriate publisher function

Tests use a fake FastMCP that captures the registered tool function so
we can invoke it directly without spawning a real MCP server.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from crackerjack.mcp.tools import eventbridge_tools
from crackerjack.mcp.tools.eventbridge_tools import (
    register_eventbridge_tools,
    set_eventbridge_publisher,
)


class _FakeFastMCP:
    """Captures tool decorator registrations for direct invocation."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self) -> Any:
        def decorator(fn: Any) -> Any:
            # Use the function name as the tool key.
            self.tools[fn.__name__] = fn
            return fn

        return decorator


@pytest.fixture(autouse=True)
def _reset_publisher() -> None:
    """Reset module-level _publisher between tests."""
    eventbridge_tools._publisher = None  # type: ignore[attr-defined]
    yield
    eventbridge_tools._publisher = None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# set_eventbridge_publisher
# ---------------------------------------------------------------------------


def test_set_eventbridge_publisher_stores_global() -> None:
    sentinel = object()
    set_eventbridge_publisher(sentinel)
    assert eventbridge_tools._publisher is sentinel  # type: ignore[attr-defined]


def test_set_eventbridge_publisher_to_none() -> None:
    set_eventbridge_publisher("something")
    set_eventbridge_publisher(None)
    assert eventbridge_tools._publisher is None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# register_eventbridge_tools — disabled / enabled paths
# ---------------------------------------------------------------------------


def test_register_disabled_returns_early() -> None:
    """When ``enabled=False``, no tool is registered."""
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, publisher=object(), enabled=False)
    assert mcp.tools == {}


def test_register_enabled_with_no_publisher() -> None:
    """``enabled=True`` + publisher=None still registers the tool.

    The tool function reports ``no_publisher`` at call time.
    """
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, publisher=None, enabled=True)
    assert "publish_to_eventbridge" in mcp.tools


def test_register_enabled_with_publisher_sets_global() -> None:
    mcp = _FakeFastMCP()
    sentinel = object()
    register_eventbridge_tools(mcp, publisher=sentinel, enabled=True)
    assert eventbridge_tools._publisher is sentinel  # type: ignore[attr-defined]


def test_register_enabled_publisher_already_set() -> None:
    """If global publisher is already set, passing publisher=None doesn't clobber it."""
    mcp = _FakeFastMCP()
    sentinel = object()
    set_eventbridge_publisher(sentinel)
    register_eventbridge_tools(mcp, publisher=None, enabled=True)
    assert eventbridge_tools._publisher is sentinel  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# publish_to_eventbridge — no publisher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_no_publisher_returns_warning() -> None:
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, publisher=None, enabled=True)
    tool = mcp.tools["publish_to_eventbridge"]
    out = await tool(topic="test.started", payload={})
    assert out["status"] == "no_publisher"
    assert "publisher not wired" in out["warning"]


# ---------------------------------------------------------------------------
# publish_to_eventbridge — dispatch by topic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_test_started(monkeypatch: pytest.MonkeyPatch) -> None:
    """topic='test.started' → publish_test_started is awaited."""
    set_eventbridge_publisher("p")
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, enabled=True)
    tool = mcp.tools["publish_to_eventbridge"]

    called: dict[str, Any] = {}

    async def fake_started(run_id: str, test_suite: str, total_tests: int, publisher: Any) -> None:
        called["started"] = (run_id, test_suite, total_tests, publisher)

    monkeypatch.setattr(
        eventbridge_tools, "publish_test_started", fake_started
    )
    out = await tool(
        topic="test.started",
        payload={
            "run_id": "r1",
            "test_suite": "unit",
            "total_tests": 10,
        },
    )
    assert out["status"] == "published"
    assert called["started"] == ("r1", "unit", 10, "p")


@pytest.mark.asyncio
async def test_publish_test_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    set_eventbridge_publisher("p")
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, enabled=True)
    tool = mcp.tools["publish_to_eventbridge"]

    called: dict[str, Any] = {}

    async def fake_completed(
        run_id: str,
        tests_completed: int,
        tests_failed: int,
        duration_seconds: float,
        publisher: Any,
    ) -> None:
        called["completed"] = (
            run_id, tests_completed, tests_failed, duration_seconds, publisher
        )

    monkeypatch.setattr(
        eventbridge_tools, "publish_test_completed", fake_completed
    )
    out = await tool(
        topic="test.completed",
        payload={
            "run_id": "r2",
            "tests_completed": 9,
            "tests_failed": 1,
            "duration_seconds": 12.5,
        },
    )
    assert out["status"] == "published"
    assert called["completed"] == ("r2", 9, 1, 12.5, "p")


@pytest.mark.asyncio
async def test_publish_test_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    set_eventbridge_publisher("p")
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, enabled=True)
    tool = mcp.tools["publish_to_eventbridge"]

    called: dict[str, Any] = {}

    async def fake_failed(
        run_id: str,
        test_name: str,
        error: str,
        traceback: str,
        publisher: Any,
    ) -> None:
        called["failed"] = (run_id, test_name, error, traceback, publisher)

    monkeypatch.setattr(
        eventbridge_tools, "publish_test_failed", fake_failed
    )
    out = await tool(
        topic="test.failed",
        payload={
            "run_id": "r3",
            "test_name": "test_x",
            "error": "boom",
            "traceback": "Traceback...",
        },
    )
    assert out["status"] == "published"
    assert called["failed"] == ("r3", "test_x", "boom", "Traceback...", "p")


@pytest.mark.asyncio
async def test_publish_unknown_topic_logs_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown topic → logger.warning is called, returns 'published'."""
    set_eventbridge_publisher("p")
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, enabled=True)
    tool = mcp.tools["publish_to_eventbridge"]

    with patch.object(eventbridge_tools, "logger") as mock_logger:
        out = await tool(topic="weird.topic", payload={})
    assert out["status"] == "published"
    mock_logger.warning.assert_called_once()
    args = mock_logger.warning.call_args.args
    assert "unknown topic" in args[0]
    assert "weird.topic" in args


# ---------------------------------------------------------------------------
# publish_to_eventbridge — async_callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_async_callback_returns_queued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """async_callback=True → returns workflow_id + 'queued' without awaiting."""
    set_eventbridge_publisher("p")
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, enabled=True)
    tool = mcp.tools["publish_to_eventbridge"]

    dispatched: list[str] = []

    async def fake_started(run_id: str, **kw: Any) -> None:
        dispatched.append(run_id)

    monkeypatch.setattr(
        eventbridge_tools, "publish_test_started", fake_started
    )
    out = await tool(
        topic="test.started",
        payload={"run_id": "r1", "test_suite": "unit", "total_tests": 5},
        async_callback=True,
    )
    assert out["status"] == "queued"
    assert out["workflow_id"].startswith("pub_")
    assert len(out["workflow_id"]) == 4 + 12  # "pub_" + 12 hex
    # Dispatch happens via create_task, but we did not await long enough
    # for the task to complete — that's fine; the wrapper returns immediately.


@pytest.mark.asyncio
async def test_publish_async_callback_dispatches_eventually(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When async_callback=True, the dispatch task actually runs."""
    import asyncio

    set_eventbridge_publisher("p")
    mcp = _FakeFastMCP()
    register_eventbridge_tools(mcp, enabled=True)
    tool = mcp.tools["publish_to_eventbridge"]

    called: dict[str, Any] = {}

    async def fake_started(run_id: str, **kw: Any) -> None:
        called["run_id"] = run_id

    monkeypatch.setattr(
        eventbridge_tools, "publish_test_started", fake_started
    )
    await tool(
        topic="test.started",
        payload={"run_id": "r9", "test_suite": "x", "total_tests": 1},
        async_callback=True,
    )
    # Let the create_task-scheduled coroutine complete.
    await asyncio.sleep(0.05)
    assert called.get("run_id") == "r9"


# ---------------------------------------------------------------------------
# __all__ surface
# ---------------------------------------------------------------------------


def test_module_dunder_all() -> None:
    assert eventbridge_tools.__all__ == [
        "register_eventbridge_tools",
        "set_eventbridge_publisher",
    ]
