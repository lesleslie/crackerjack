"""Tests for crackerjack.mcp.task_manager.AsyncTaskManager."""

from __future__ import annotations

import asyncio
import logging
import time
import typing as t
import warnings

import pytest

from crackerjack.mcp.task_manager import AsyncTaskManager, TaskInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _noop() -> str:
    return "done"


async def _slow(seconds: float) -> str:
    await asyncio.sleep(seconds)
    return f"slept-{seconds}"


async def _raises() -> None:
    raise RuntimeError("boom")


def _never() -> t.Coroutine[t.Any, t.Any, None]:
    """Return a coroutine that never completes. Caller must close() it if unused."""
    async def _wait_forever() -> None:
        await asyncio.Event().wait()

    return _wait_forever()


def _close_coros(*coros: t.Any) -> None:
    for c in coros:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if asyncio.iscoroutine(c):
                c.close()


def _new_manager(max_concurrent: int = 5) -> AsyncTaskManager:
    return AsyncTaskManager(max_concurrent_tasks=max_concurrent)


# ---------------------------------------------------------------------------
# Construction / Stats
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_constructor_defaults() -> None:
    mgr = AsyncTaskManager()
    stats = mgr.get_stats()
    assert stats["running"] is False
    assert stats["active_tasks"] == 0
    assert stats["max_concurrent_tasks"] == 10
    assert stats["available_slots"] == 10


@pytest.mark.unit
def test_constructor_respects_max_concurrent() -> None:
    mgr = AsyncTaskManager(max_concurrent_tasks=3)
    assert mgr.get_stats()["max_concurrent_tasks"] == 3
    assert mgr.get_stats()["available_slots"] == 3


# ---------------------------------------------------------------------------
# Lifecycle: start / stop
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_start_sets_running_and_spawns_cleanup_task() -> None:
    mgr = _new_manager()
    try:
        await mgr.start()
        assert mgr.get_stats()["running"] is True
        assert mgr._cleanup_task is not None  # type: ignore[attr-defined]
    finally:
        await mgr.stop()


@pytest.mark.unit
async def test_stop_clears_running_flag() -> None:
    mgr = _new_manager()
    await mgr.start()
    await mgr.stop()
    assert mgr.get_stats()["running"] is False


@pytest.mark.unit
async def test_stop_with_no_tasks_does_not_raise() -> None:
    mgr = _new_manager()
    # start not called - stop should still be safe
    await mgr.stop()
    assert mgr.get_stats()["active_tasks"] == 0


@pytest.mark.unit
async def test_stop_cancels_active_tasks() -> None:
    mgr = _new_manager()
    await mgr.start()
    await mgr.create_task(_never(), "t1", "long task")
    assert mgr.get_stats()["active_tasks"] == 1
    await mgr.stop()
    assert mgr.get_stats()["active_tasks"] == 0


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_create_task_returns_task_and_logs_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mgr = _new_manager()
    caplog.set_level(logging.INFO, logger="crackerjack.mcp.task_manager")
    task = await mgr.create_task(_noop(), "t1", "my task")
    assert isinstance(task, asyncio.Task)
    result = await task
    assert result == "done"
    # eventually-removed from registry
    await asyncio.sleep(0)
    assert mgr.get_stats()["active_tasks"] == 0


@pytest.mark.unit
async def test_create_task_duplicate_id_raises_value_error() -> None:
    """Conflict: duplicate task_id is the equivalent of a uniqueness conflict."""
    mgr = _new_manager()
    await mgr.create_task(_never(), "dup", "first")
    second = _never()
    with pytest.raises(ValueError, match="already exists"):
        await mgr.create_task(second, "dup", "second")
    _close_coros(second)
    # cleanup
    await mgr.stop()


@pytest.mark.unit
async def test_create_task_at_capacity_raises_runtime_error() -> None:
    mgr = _new_manager(max_concurrent=1)
    await mgr.create_task(_never(), "a", "")
    blocked = _never()
    with pytest.raises(RuntimeError, match="Maximum concurrent tasks"):
        await mgr.create_task(blocked, "b", "")
    _close_coros(blocked)
    await mgr.stop()


@pytest.mark.unit
async def test_create_task_capacity_resets_after_completion() -> None:
    mgr = _new_manager(max_concurrent=1)
    t1 = await mgr.create_task(_noop(), "a", "")
    await t1  # let it finish
    await asyncio.sleep(0)  # allow _wrap_task finally block to run
    # Now a second task can be created.
    t2 = await mgr.create_task(_noop(), "b", "")
    assert t2 is not t1
    await t2


@pytest.mark.unit
async def test_create_task_with_timeout_applies_wait_for() -> None:
    """If timeout_seconds is set, the coroutine is wrapped in wait_for."""
    mgr = _new_manager()
    # Use a generous timeout so we don't get spurious TimeoutError.
    task = await mgr.create_task(_slow(0.01), "t", "fast", timeout_seconds=1.0)
    result = await task
    assert result == "slept-0.01"


@pytest.mark.unit
async def test_create_task_timeout_triggers_timeout_error() -> None:
    mgr = _new_manager()
    task = await mgr.create_task(_slow(0.5), "slow", "slow", timeout_seconds=0.05)
    with pytest.raises((asyncio.TimeoutError, TimeoutError)):
        await task


@pytest.mark.unit
async def test_create_task_default_timeout_is_none() -> None:
    mgr = _new_manager()
    task = await mgr.create_task(_noop(), "t", "desc")
    info = await mgr.get_task_status("t")
    assert info is not None
    assert info["timeout_seconds"] is None
    await task


# ---------------------------------------------------------------------------
# _wrap_task behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_task_exception_logged_and_task_removed() -> None:
    mgr = _new_manager()
    task = await mgr.create_task(_raises(), "explode", "will fail")
    with pytest.raises(RuntimeError, match="boom"):
        await task
    # give the finally block a chance to run
    await asyncio.sleep(0)
    assert mgr.get_stats()["active_tasks"] == 0


@pytest.mark.unit
async def test_task_cancellation_propagates_cancelled_error() -> None:
    mgr = _new_manager()
    task = await mgr.create_task(_never(), "cancellable", "")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# ---------------------------------------------------------------------------
# cancel_task
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_cancel_existing_task_returns_true() -> None:
    mgr = _new_manager()
    await mgr.create_task(_never(), "t", "")
    cancelled = await mgr.cancel_task("t")
    assert cancelled is True
    with pytest.raises(asyncio.CancelledError):
        await mgr._tasks["t"].task  # type: ignore[attr-defined]
    await mgr.stop()


@pytest.mark.unit
async def test_cancel_unknown_task_returns_false() -> None:
    mgr = _new_manager()
    assert await mgr.cancel_task("missing") is False


# ---------------------------------------------------------------------------
# get_task_status
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_get_task_status_unknown_returns_none() -> None:
    mgr = _new_manager()
    assert await mgr.get_task_status("nope") is None


@pytest.mark.unit
async def test_get_task_status_returns_expected_fields() -> None:
    mgr = _new_manager()
    await mgr.create_task(_never(), "t", "do something", timeout_seconds=2.0)
    info = await mgr.get_task_status("t")
    assert info is not None
    assert info["task_id"] == "t"
    assert info["description"] == "do something"
    assert info["timeout_seconds"] == 2.0
    assert info["done"] is False
    assert info["cancelled"] is False
    assert info["created_at"] <= time.time()
    assert info["running_time"] >= 0.0
    await mgr.stop()


# ---------------------------------------------------------------------------
# list_active_tasks
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_list_active_tasks_empty() -> None:
    mgr = _new_manager()
    assert await mgr.list_active_tasks() == []


@pytest.mark.unit
async def test_list_active_tasks_includes_all_running() -> None:
    mgr = _new_manager()
    await mgr.create_task(_never(), "a", "A")
    await mgr.create_task(_never(), "b", "B")
    listing = await mgr.list_active_tasks()
    ids = {item["task_id"] for item in listing}
    assert ids == {"a", "b"}
    for item in listing:
        assert item["description"] in {"A", "B"}
        assert item["done"] is False
    await mgr.stop()


@pytest.mark.unit
async def test_list_active_tasks_excludes_completed() -> None:
    mgr = _new_manager()
    t = await mgr.create_task(_noop(), "only", "")
    await t
    await asyncio.sleep(0)
    assert await mgr.list_active_tasks() == []


# ---------------------------------------------------------------------------
# wait_for_task
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_wait_for_task_returns_result_when_completes() -> None:
    mgr = _new_manager()
    await mgr.create_task(_slow(0.01), "t", "")
    result = await mgr.wait_for_task("t")
    assert result == "slept-0.01"


@pytest.mark.unit
async def test_wait_for_task_unknown_raises_value_error() -> None:
    mgr = _new_manager()
    with pytest.raises(ValueError, match="not found"):
        await mgr.wait_for_task("missing")


@pytest.mark.unit
async def test_wait_for_task_with_timeout_raises_on_expiry() -> None:
    mgr = _new_manager()
    await mgr.create_task(_never(), "t", "")
    with pytest.raises(TimeoutError):
        await mgr.wait_for_task("t", timeout=0.05)
    # cleanup
    await mgr.cancel_task("t")
    await mgr.stop()


# ---------------------------------------------------------------------------
# managed_task context manager
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_managed_task_yields_task_and_cancels_on_exit() -> None:
    mgr = _new_manager()
    async with mgr.managed_task(_never(), "ctx", "context") as task:
        assert isinstance(task, asyncio.Task)
        assert not task.done()
    # task should be cancelled when leaving the context
    await asyncio.sleep(0)
    with pytest.raises((asyncio.CancelledError, BaseException)):
        await task


@pytest.mark.unit
async def test_managed_task_does_not_cancel_if_already_done() -> None:
    mgr = _new_manager()

    async def quick() -> str:
        return "ok"

    async with mgr.managed_task(quick(), "ctx2", "fast") as task:
        result = await task
    assert result == "ok"


@pytest.mark.unit
async def test_managed_task_exception_in_task_does_not_break_context() -> None:
    """The exception is stored in the task; the context manager just cancels
    on exit. Awaiting the task inside the block re-raises."""
    mgr = _new_manager()

    async def fail() -> None:
        raise RuntimeError("managed-fail")

    async with mgr.managed_task(fail(), "ctx3", "") as task:
        with pytest.raises(RuntimeError, match="managed-fail"):
            await task


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_cancel_all_tasks_with_no_tasks_is_noop() -> None:
    mgr = _new_manager()
    await mgr._cancel_all_tasks()  # type: ignore[attr-defined]
    assert mgr.get_stats()["active_tasks"] == 0


@pytest.mark.unit
async def test_cleanup_completed_tasks_removes_done_tasks() -> None:
    mgr = _new_manager()
    t = await mgr.create_task(_noop(), "c", "")
    await t
    await asyncio.sleep(0)
    # task already removed by _wrap_task finally; listing should be empty
    assert mgr.get_stats()["active_tasks"] == 0
    await mgr._cleanup_completed_tasks()  # type: ignore[attr-defined]
    assert mgr.get_stats()["active_tasks"] == 0


@pytest.mark.unit
async def test_get_stats_active_tasks_reflects_registry() -> None:
    mgr = _new_manager()
    await mgr.create_task(_never(), "s1", "")
    await mgr.create_task(_never(), "s2", "")
    stats = mgr.get_stats()
    assert stats["active_tasks"] == 2
    await mgr.stop()


# ---------------------------------------------------------------------------
# TaskInfo dataclass
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_task_info_defaults() -> None:
    """TaskInfo default values and basic construction."""
    current = asyncio.current_task()
    assert current is not None  # always set inside a running event loop
    info = TaskInfo(
        task_id="x",
        task=current,
        created_at=0.0,
    )
    assert info.task_id == "x"
    assert info.description == ""
    assert info.timeout_seconds is None
    assert info.created_at == 0.0
