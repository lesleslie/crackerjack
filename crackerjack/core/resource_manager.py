import asyncio
import contextlib
import logging
import tempfile
import threading
import time
import typing as t
import weakref
from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType


class ResourceProtocol(t.Protocol):
    async def cleanup(self) -> None: ...


class ResourceManager:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self._resources: list[ResourceProtocol] = []
        self._cleanup_callbacks: list[t.Callable[[], t.Awaitable[None]]] = []
        self._lock = threading.RLock()
        self._closed = False

    def register_resource(self, resource: ResourceProtocol) -> None:
        with self._lock:
            if self._closed:
                asyncio.create_task(resource.cleanup())
                return
            self._resources.append(resource)

    def register_cleanup_callback(
        self, callback: t.Callable[[], t.Awaitable[None]]
    ) -> None:
        with self._lock:
            if self._closed:
                coro = callback()
                if asyncio.iscoroutine(coro):
                    asyncio.ensure_future(coro)
                return
            self._cleanup_callbacks.append(callback)

    async def cleanup_all(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True

            resources = self._resources.copy()
            callbacks = self._cleanup_callbacks.copy()

        for resource in resources:
            try:
                await resource.cleanup()
            except Exception as e:
                self.logger.warning(f"Error cleaning up resource {resource}: {e}")

        for callback in callbacks:
            try:
                await callback()
            except Exception as e:
                self.logger.warning(f"Error in cleanup callback: {e}")

        with self._lock:
            self._resources.clear()
            self._cleanup_callbacks.clear()

    async def __aenter__(self) -> "ResourceManager":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.cleanup_all()


class ManagedResource(ABC):
    def __init__(self, manager: ResourceManager | None = None) -> None:
        self.manager = manager
        self._closed = False

        if manager:
            manager.register_resource(self)

    @abstractmethod
    async def cleanup(self) -> None:
        pass

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self.cleanup()

    def __del__(self) -> None:
        if not self._closed:
            with contextlib.suppress(RuntimeError):
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.cleanup())


class ManagedTemporaryFile(ManagedResource):
    def __init__(
        self,
        suffix: str = "",
        prefix: str = "crackerjack-",
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.temp_file = tempfile.NamedTemporaryFile(
            suffix=suffix,
            prefix=prefix,
            delete=False,
        )
        self.path = Path(self.temp_file.name)

    async def cleanup(self) -> None:
        if not self._closed:
            self._closed = True

            if not self.temp_file.closed:
                self.temp_file.close()

            try:
                if self.path.exists():
                    self.path.unlink()
            except OSError as e:
                logging.getLogger(__name__).warning(
                    f"Failed to remove temporary file {self.path}: {e}"
                )

    def write_text(self, content: str, encoding: str = "utf-8") -> None:
        if self._closed:
            raise RuntimeError("Cannot write to closed temporary file")
        self.path.write_text(content, encoding=encoding)

    def read_text(self, encoding: str = "utf-8") -> str:
        return self.path.read_text(encoding=encoding)


class ManagedTemporaryDirectory(ManagedResource):
    def __init__(
        self,
        suffix: str = "",
        prefix: str = "crackerjack-",
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
        self.path = Path(self.temp_dir)

    async def cleanup(self) -> None:
        if not self._closed:
            self._closed = True

            try:
                import shutil

                if self.path.exists():
                    shutil.rmtree(self.path)
            except OSError as e:
                logging.getLogger(__name__).warning(
                    f"Failed to remove temporary directory {self.path}: {e}"
                )


class ManagedProcess(ManagedResource):
    def __init__(
        self,
        process: asyncio.subprocess.Process,
        timeout: float = 30.0,
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.process = process
        self.timeout = timeout

    async def cleanup(self) -> None:
        if not self._closed and self.process.returncode is None:
            self._closed = True

            try:
                self.process.terminate()

                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except TimeoutError:
                    self.process.kill()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=2.0)
                    except TimeoutError:
                        logging.getLogger(__name__).warning(
                            f"Process {self.process.pid} did not terminate after force kill"
                        )

            except ProcessLookupError:
                pass
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Error cleaning up process {self.process.pid}: {e}"
                )


class ManagedTask(ManagedResource):
    def __init__(
        self,
        task: asyncio.Task[t.Any],
        timeout: float = 30.0,
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.task = task
        self.timeout = timeout

    async def cleanup(self) -> None:
        if not self._closed and not self.task.done():
            self._closed = True

            self.task.cancel()

            try:
                await asyncio.wait_for(self.task, timeout=self.timeout)
            except (TimeoutError, asyncio.CancelledError):
                pass
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error cleaning up task: {e}")


class ManagedFileHandle(ManagedResource):
    def __init__(
        self,
        file_handle: t.IO[t.Any],
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.file_handle = file_handle

    async def cleanup(self) -> None:
        if not self._closed and not self.file_handle.closed:
            self._closed = True

            try:
                self.file_handle.close()
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error closing file handle: {e}")


class ResourceContext:
    def __init__(self) -> None:
        self.resource_manager = ResourceManager()

    def managed_temp_file(
        self,
        suffix: str = "",
        prefix: str = "crackerjack-",
    ) -> ManagedTemporaryFile:
        return ManagedTemporaryFile(suffix, prefix, self.resource_manager)

    def managed_temp_dir(
        self,
        suffix: str = "",
        prefix: str = "crackerjack-",
    ) -> ManagedTemporaryDirectory:
        return ManagedTemporaryDirectory(suffix, prefix, self.resource_manager)

    def managed_process(
        self,
        process: asyncio.subprocess.Process,
        timeout: float = 30.0,
    ) -> ManagedProcess:
        return ManagedProcess(process, timeout, self.resource_manager)

    def managed_task(
        self,
        task: asyncio.Task[t.Any],
        timeout: float = 30.0,
    ) -> ManagedTask:
        return ManagedTask(task, timeout, self.resource_manager)

    def managed_file(
        self,
        file_handle: t.IO[t.Any],
    ) -> ManagedFileHandle:
        return ManagedFileHandle(file_handle, self.resource_manager)

    async def __aenter__(self) -> "ResourceContext":
        await self.resource_manager.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.resource_manager.__aexit__(exc_type, exc_val, exc_tb)


_global_managers: weakref.WeakSet[ResourceManager] = weakref.WeakSet()


def register_global_resource_manager(manager: ResourceManager) -> None:
    _global_managers.add(manager)


async def cleanup_all_global_resources() -> None:
    managers = list[t.Any](_global_managers)

    cleanup_tasks = [asyncio.create_task(manager.cleanup_all()) for manager in managers]

    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)


@contextlib.asynccontextmanager
async def with_resource_cleanup() -> t.AsyncIterator[ResourceContext]:
    async with ResourceContext() as ctx:
        yield ctx


@contextlib.asynccontextmanager
async def with_temp_file(
    suffix: str = "", prefix: str = "crackerjack-"
) -> t.AsyncIterator[ManagedTemporaryFile]:
    async with ResourceContext() as ctx:
        temp_file = ctx.managed_temp_file(suffix, prefix)
        try:
            yield temp_file
        finally:
            await temp_file.cleanup()


@contextlib.asynccontextmanager
async def with_temp_dir(
    suffix: str = "", prefix: str = "crackerjack-"
) -> t.AsyncIterator[ManagedTemporaryDirectory]:
    async with ResourceContext() as ctx:
        temp_dir = ctx.managed_temp_dir(suffix, prefix)
        try:
            yield temp_dir
        finally:
            await temp_dir.cleanup()


@contextlib.asynccontextmanager
async def with_managed_process(
    process: asyncio.subprocess.Process,
    timeout: float = 30.0,
) -> t.AsyncIterator[asyncio.subprocess.Process]:
    async with ResourceContext() as ctx:
        managed_proc = ctx.managed_process(process, timeout)
        try:
            yield managed_proc.process
        finally:
            await managed_proc.cleanup()


class ResourceLeakDetector:
    def __init__(self) -> None:
        self.open_files: set[str] = set()
        self.active_processes: set[int] = set()
        self.active_tasks: set[asyncio.Task[t.Any]] = set()
        self._start_time = time.time()

    def track_file(self, file_path: str) -> None:
        self.open_files.add(file_path)

    def untrack_file(self, file_path: str) -> None:
        self.open_files.discard(file_path)

    def track_process(self, pid: int) -> None:
        self.active_processes.add(pid)

    def untrack_process(self, pid: int) -> None:
        self.active_processes.discard(pid)

    def track_task(self, task: asyncio.Task[t.Any]) -> None:
        self.active_tasks.add(task)

    def untrack_task(self, task: asyncio.Task[t.Any]) -> None:
        self.active_tasks.discard(task)

    def get_leak_report(self) -> dict[str, t.Any]:
        return {
            "duration_seconds": time.time() - self._start_time,
            "open_files": list[t.Any](self.open_files),
            "active_processes": list[t.Any](self.active_processes),
            "active_tasks": len([t for t in self.active_tasks if not t.done()]),
            "total_tracked_files": len(self.open_files),
            "total_tracked_processes": len(self.active_processes),
            "total_tracked_tasks": len(self.active_tasks),
        }

    def has_potential_leaks(self) -> bool:
        return bool(
            self.open_files
            or self.active_processes
            or any(not t.done() for t in self.active_tasks)
        )


_leak_detector: ResourceLeakDetector | None = None


def enable_leak_detection() -> ResourceLeakDetector:
    global _leak_detector
    _leak_detector = ResourceLeakDetector()
    return _leak_detector


def get_leak_detector() -> ResourceLeakDetector | None:
    return _leak_detector


def disable_leak_detection() -> dict[str, t.Any] | None:
    global _leak_detector
    if _leak_detector:
        report = _leak_detector.get_leak_report()
        _leak_detector = None
        return report
    return None
