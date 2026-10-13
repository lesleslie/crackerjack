from __future__ import annotations

import asyncio
import logging
import time
import typing as t
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rich.console import Console

from .persistence import AsyncTaskRecord, AsyncTaskStore

console = Console()

logger = logging.getLogger(__name__)


@dataclass
class TaskInfo:
    task_id: str
    task: asyncio.Task[t.Any]
    created_at: float
    description: str = ""
    timeout_seconds: float | None = None


class AsyncTaskManager:
    def __init__(
        self,
        max_concurrent_tasks: int = 10,
        *,
        store: AsyncTaskStore | None = None,
        settings: t.Any | None = None,
    ) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks
        self._tasks: dict[str, TaskInfo] = {}
        self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._cleanup_task: asyncio.Task[t.Any] | None = None
        self._reaper_task: asyncio.Task[t.Any] | None = None
        self._running = False
        self._lock = asyncio.Lock()
        self._store = store
        self._settings = settings

    @property
    def store(self) -> AsyncTaskStore | None:
        return self._store

    async def start(self) -> None:
        self._running = True
        if self._store is not None:
            await self._store.init_schema()
            self._reaper_task = asyncio.create_task(self._reap_zombies_loop())
            logger.info("crackerjack_async_task_manager_started")
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        try:
            console.print(
                f"[green]🎯 Task Manager started (max {self.max_concurrent_tasks} concurrent)[ / green]",
            )
        except ValueError, OSError:
            logger.info(
                f"Task Manager started (max {self.max_concurrent_tasks} concurrent) ",
            )

    async def stop(self) -> None:
        self._running = False

        if self._reaper_task:
            self._reaper_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reaper_task
            self._reaper_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cleanup_task

        await self._cancel_all_tasks()
        logger.info("crackerjack_async_task_manager_stopped")
        try:
            console.print("[yellow]🎯 Task Manager stopped[ / yellow]")
        except ValueError, OSError:
            logger.info("Task Manager stopped")

    async def create_task(
        self,
        coro: t.Coroutine[t.Any, t.Any, t.Any],
        task_id: str,
        description: str = "",
        timeout_seconds: float | None = None,
    ) -> asyncio.Task[t.Any]:
        async with self._lock:
            if task_id in self._tasks:
                msg = f"Task {task_id} already exists"
                raise ValueError(msg)

            if len(self._tasks) >= self.max_concurrent_tasks:
                msg = f"Maximum concurrent tasks ({self.max_concurrent_tasks}) reached"
                raise RuntimeError(
                    msg,
                )

        if timeout_seconds:
            coro = asyncio.wait_for(coro, timeout=timeout_seconds)

        task = asyncio.create_task(self._wrap_task(coro, task_id))

        task_info = TaskInfo(
            task_id=task_id,
            task=task,
            created_at=time.time(),
            description=description,
            timeout_seconds=timeout_seconds,
        )

        async with self._lock:
            self._tasks[task_id] = task_info

        logger.info(f"Created task {task_id}: {description}")
        from contextlib import suppress

        with suppress(ValueError, OSError):
            console.print(f"[blue]🚀 Task {task_id} created: {description}[ / blue]")
        return task

    async def _wrap_task(
        self,
        coro: t.Coroutine[t.Any, t.Any, t.Any],
        task_id: str,
    ) -> t.Any:
        try:
            async with self._task_semaphore:
                result = await coro
                logger.info(f"Task {task_id} completed successfully")
                return result
        except asyncio.CancelledError:
            logger.info(f"Task {task_id} was cancelled")
            raise
        except Exception as e:
            logger.exception(f"Task {task_id} failed: {e}")
            from contextlib import suppress

            with suppress(ValueError, OSError):
                console.print(f"[red]❌ Task {task_id} failed: {e}[ / red]")
            raise
        finally:
            async with self._lock:
                if task_id in self._tasks:
                    del self._tasks[task_id]

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return False

            task_info.task.cancel()
            logger.info(f"Cancelled task {task_id}")
            from contextlib import suppress

            with suppress(ValueError, OSError):
                console.print(f"[yellow]🚫 Task {task_id} cancelled[ / yellow]")
            return True

    async def get_task_status(self, task_id: str) -> dict[str, t.Any] | None:
        async with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return None

            return {
                "task_id": task_id,
                "description": task_info.description,
                "created_at": task_info.created_at,
                "running_time": time.time() - task_info.created_at,
                "done": task_info.task.done(),
                "cancelled": task_info.task.cancelled(),
                "timeout_seconds": task_info.timeout_seconds,
            }

    async def list_active_tasks(self) -> list[dict[str, t.Any]]:
        async with self._lock:
            tasks = []
            for task_id, task_info in self._tasks.items():
                task_status = {
                    "task_id": task_id,
                    "description": task_info.description,
                    "created_at": task_info.created_at,
                    "running_time": time.time() - task_info.created_at,
                    "done": task_info.task.done(),
                    "cancelled": task_info.task.cancelled(),
                    "timeout_seconds": task_info.timeout_seconds,
                }
                tasks.append(task_status)
            return tasks

    async def wait_for_task(self, task_id: str, timeout: float | None = None) -> t.Any:
        async with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                msg = f"Task {task_id} not found"
                raise ValueError(msg)

        try:
            if timeout:
                return await asyncio.wait_for(task_info.task, timeout=timeout)
            return await task_info.task
        except TimeoutError:
            logger.warning(f"Timeout waiting for task {task_id}")
            raise

    @asynccontextmanager
    async def managed_task(
        self,
        coro: t.Coroutine[t.Any, t.Any, t.Any],
        task_id: str,
        description: str = "",
        timeout_seconds: float | None = None,
    ) -> t.AsyncGenerator[asyncio.Task[t.Any]]:
        task = await self.create_task(coro, task_id, description, timeout_seconds)
        try:
            yield task
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def _cancel_all_tasks(self) -> None:
        async with self._lock:
            tasks_to_cancel = list[t.Any](self._tasks.values())

        if not tasks_to_cancel:
            return

        try:
            console.print(
                f"[yellow]🧹 Cancelling {len(tasks_to_cancel)} running tasks[ / yellow]",
            )
        except ValueError, OSError:
            logger.info(f"Cancelling {len(tasks_to_cancel)} running tasks")

        for task_info in tasks_to_cancel:
            task_info.task.cancel()

        await asyncio.gather(
            *[task_info.task for task_info in tasks_to_cancel],
            return_exceptions=True,
        )

        async with self._lock:
            self._tasks.clear()

    async def _cleanup_loop(self) -> None:
        while self._running:
            try:
                await self._cleanup_completed_tasks()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in task cleanup loop: {e}")
                await asyncio.sleep(5)

    async def _cleanup_completed_tasks(self) -> None:
        async with self._lock:
            completed_tasks = []
            for task_id, task_info in list[t.Any](self._tasks.items()):
                if task_info.task.done():
                    completed_tasks.append(task_id)
                    del self._tasks[task_id]

        if completed_tasks:
            logger.info(f"Cleaned up {len(completed_tasks)} completed tasks")

    # ------------------------------------------------------------------
    # Persistent task records (C-WIRE Task 6: SQLite-backed)
    #
    # These methods operate on a separate persistence layer (AsyncTaskStore)
    # from the in-memory ``self._tasks`` dict. The in-memory dict tracks
    # *running* asyncio.Task objects (so they can be cancelled), while the
    # store tracks *durable* status records that survive process restart.
    # Both layers coexist; nothing in the existing in-memory method surface
    # was changed.
    # ------------------------------------------------------------------

    async def register_task(
        self,
        task_id: str,
        status: str,
        metadata: dict[str, t.Any] | None = None,
    ) -> AsyncTaskRecord | None:
        """Register (or upsert) a durable task record.

        Returns the persisted record, or ``None`` if no store is wired.
        """
        if self._store is None:
            logger.debug(
                "register_task called without a wired store; task_id=%s",
                task_id,
            )
            return None
        return await self._store.register(task_id, status, metadata)

    async def update_task_status(self, task_id: str, new_status: str) -> None:
        """Update the status of a persisted task record."""
        if self._store is None:
            logger.debug(
                "update_task_status called without a wired store; task_id=%s",
                task_id,
            )
            return
        await self._store.update_status(task_id, new_status)

    async def get_task(self, task_id: str) -> AsyncTaskRecord | None:
        """Look up a persisted task record by id. ``None`` on miss or when
        no store is wired."""
        if self._store is None:
            return None
        return await self._store.get(task_id)

    async def _reap_zombies(self) -> int:
        """Delete zombie entries (pending/running older than ``zombie_age_seconds``).

        Returns the count of deleted entries.
        """
        if self._store is None or self._settings is None:
            return 0
        zombie_age = int(
            getattr(
                getattr(self._settings, "async_task", None),
                "zombie_age_seconds",
                604800,
            ),
        )
        keys = await self._store.list_keys()
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=zombie_age)
        deleted = 0
        candidates = 0
        for key in keys:
            record = await self._store.get(key)
            if record is None:
                continue
            if record.status not in {"pending", "running"}:
                continue
            candidates += 1
            if record.registered_at < threshold:
                removed = await self._store.delete(key)
                if removed:
                    deleted += 1
                    logger.warning(
                        "crackerjack_async_task_zombie_reaped task_id=%s "
                        "registered_at=%s",
                        key,
                        record.registered_at.isoformat(),
                    )
        logger.info(
            "crackerjack_async_task_reaper_status candidates=%d reaped=%d",
            candidates,
            deleted,
        )
        return deleted

    async def _reap_zombies_loop(self) -> None:
        interval = int(
            getattr(
                getattr(self._settings, "async_task", None),
                "reap_zombies_interval_seconds",
                3600,
            ),
        )
        while self._running:
            try:
                await self._reap_zombies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in reap_zombies: {e}")
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    def get_stats(self) -> dict[str, t.Any]:
        return {
            "running": self._running,
            "active_tasks": len(self._tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "available_slots": self._task_semaphore._value,
        }
