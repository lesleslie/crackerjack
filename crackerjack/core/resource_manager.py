"""Comprehensive resource management with automatic cleanup patterns.

This module provides RAII (Resource Acquisition Is Initialization) patterns
and comprehensive resource lifecycle management to prevent resource leaks
even in error scenarios.
"""

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
    """Protocol for resources that can be cleaned up."""

    async def cleanup(self) -> None:
        """Clean up the resource."""
        ...


class ResourceManager:
    """Centralized resource management with automatic cleanup on error scenarios."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self._resources: list[ResourceProtocol] = []
        self._cleanup_callbacks: list[t.Callable[[], t.Awaitable[None]]] = []
        self._lock = threading.RLock()
        self._closed = False

    def register_resource(self, resource: ResourceProtocol) -> None:
        """Register a resource for automatic cleanup."""
        with self._lock:
            if self._closed:
                # If already closed, immediately clean up the resource
                asyncio.create_task(resource.cleanup())
                return
            self._resources.append(resource)

    def register_cleanup_callback(
        self, callback: t.Callable[[], t.Awaitable[None]]
    ) -> None:
        """Register a cleanup callback to be called during shutdown."""
        with self._lock:
            if self._closed:
                # If already closed, immediately call the callback
                coro = callback()
                if asyncio.iscoroutine(coro):
                    asyncio.ensure_future(coro)
                return
            self._cleanup_callbacks.append(callback)

    async def cleanup_all(self) -> None:
        """Clean up all registered resources."""
        with self._lock:
            if self._closed:
                return
            self._closed = True

            resources = self._resources.copy()
            callbacks = self._cleanup_callbacks.copy()

        # Clean up resources
        for resource in resources:
            try:
                await resource.cleanup()
            except Exception as e:
                self.logger.warning(f"Error cleaning up resource {resource}: {e}")

        # Call cleanup callbacks
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
    """Base class for managed resources with automatic cleanup."""

    def __init__(self, manager: ResourceManager | None = None) -> None:
        self.manager = manager
        self._closed = False

        if manager:
            manager.register_resource(self)

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up the resource. Must be implemented by subclasses."""
        pass

    async def close(self) -> None:
        """Manually close the resource."""
        if not self._closed:
            self._closed = True
            await self.cleanup()

    def __del__(self) -> None:
        """Ensure cleanup is called even if explicitly forgotten."""
        if not self._closed:
            # Create cleanup task if event loop is available
            with contextlib.suppress(RuntimeError):
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.cleanup())


class ManagedTemporaryFile(ManagedResource):
    """Temporary file with automatic cleanup on error scenarios."""

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
            delete=False,  # We'll handle deletion ourselves
        )
        self.path = Path(self.temp_file.name)

    async def cleanup(self) -> None:
        """Clean up temporary file."""
        if not self._closed:
            self._closed = True

            # Close file handle
            if not self.temp_file.closed:
                self.temp_file.close()

            # Remove file if it exists
            try:
                if self.path.exists():
                    self.path.unlink()
            except OSError as e:
                # Log but don't raise - cleanup should be best effort
                logging.getLogger(__name__).warning(
                    f"Failed to remove temporary file {self.path}: {e}"
                )

    def write_text(self, content: str, encoding: str = "utf-8") -> None:
        """Write text content to the temporary file."""
        if self._closed:
            raise RuntimeError("Cannot write to closed temporary file")
        self.path.write_text(content, encoding=encoding)

    def read_text(self, encoding: str = "utf-8") -> str:
        """Read text content from the temporary file."""
        return self.path.read_text(encoding=encoding)


class ManagedTemporaryDirectory(ManagedResource):
    """Temporary directory with automatic cleanup on error scenarios."""

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
        """Clean up temporary directory and all contents."""
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
    """Process with automatic cleanup on error scenarios."""

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
        """Clean up process with graceful termination."""
        if not self._closed and self.process.returncode is None:
            self._closed = True

            try:
                # Try graceful termination first
                self.process.terminate()

                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except TimeoutError:
                    # Force kill if graceful termination fails
                    self.process.kill()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=2.0)
                    except TimeoutError:
                        logging.getLogger(__name__).warning(
                            f"Process {self.process.pid} did not terminate after force kill"
                        )

            except ProcessLookupError:
                # Process already terminated
                pass
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Error cleaning up process {self.process.pid}: {e}"
                )


class ManagedTask(ManagedResource):
    """Asyncio task with automatic cancellation on error scenarios."""

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
        """Clean up task with cancellation."""
        if not self._closed and not self.task.done():
            self._closed = True

            self.task.cancel()

            try:
                await asyncio.wait_for(self.task, timeout=self.timeout)
            except (TimeoutError, asyncio.CancelledError):
                # Expected when cancelling or timing out
                pass
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error cleaning up task: {e}")


class ManagedFileHandle(ManagedResource):
    """File handle with automatic closing on error scenarios."""

    def __init__(
        self,
        file_handle: t.IO[t.Any],
        manager: ResourceManager | None = None,
    ) -> None:
        super().__init__(manager)
        self.file_handle = file_handle

    async def cleanup(self) -> None:
        """Clean up file handle."""
        if not self._closed and not self.file_handle.closed:
            self._closed = True

            try:
                self.file_handle.close()
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error closing file handle: {e}")


class ResourceContext:
    """Context manager for automatic resource management."""

    def __init__(self) -> None:
        self.resource_manager = ResourceManager()

    def managed_temp_file(
        self,
        suffix: str = "",
        prefix: str = "crackerjack-",
    ) -> ManagedTemporaryFile:
        """Create a managed temporary file."""
        return ManagedTemporaryFile(suffix, prefix, self.resource_manager)

    def managed_temp_dir(
        self,
        suffix: str = "",
        prefix: str = "crackerjack-",
    ) -> ManagedTemporaryDirectory:
        """Create a managed temporary directory."""
        return ManagedTemporaryDirectory(suffix, prefix, self.resource_manager)

    def managed_process(
        self,
        process: asyncio.subprocess.Process,
        timeout: float = 30.0,
    ) -> ManagedProcess:
        """Create a managed process."""
        return ManagedProcess(process, timeout, self.resource_manager)

    def managed_task(
        self,
        task: asyncio.Task[t.Any],
        timeout: float = 30.0,
    ) -> ManagedTask:
        """Create a managed task."""
        return ManagedTask(task, timeout, self.resource_manager)

    def managed_file(
        self,
        file_handle: t.IO[t.Any],
    ) -> ManagedFileHandle:
        """Create a managed file handle."""
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


# Global resource manager registry
_global_managers: weakref.WeakSet[ResourceManager] = weakref.WeakSet()


def register_global_resource_manager(manager: ResourceManager) -> None:
    """Register a resource manager for global cleanup."""
    _global_managers.add(manager)


async def cleanup_all_global_resources() -> None:
    """Clean up all globally registered resource managers."""
    managers = list(_global_managers)

    cleanup_tasks = [asyncio.create_task(manager.cleanup_all()) for manager in managers]

    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)


# Cleanup helper context managers
@contextlib.asynccontextmanager
async def with_resource_cleanup():
    """Context manager that ensures resource cleanup on any exit."""
    async with ResourceContext() as ctx:
        yield ctx


@contextlib.asynccontextmanager
async def with_temp_file(suffix: str = "", prefix: str = "crackerjack-"):
    """Context manager for temporary file with automatic cleanup."""
    async with ResourceContext() as ctx:
        temp_file = ctx.managed_temp_file(suffix, prefix)
        try:
            yield temp_file
        finally:
            await temp_file.cleanup()


@contextlib.asynccontextmanager
async def with_temp_dir(suffix: str = "", prefix: str = "crackerjack-"):
    """Context manager for temporary directory with automatic cleanup."""
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
):
    """Context manager for process with automatic cleanup."""
    async with ResourceContext() as ctx:
        managed_proc = ctx.managed_process(process, timeout)
        try:
            yield managed_proc
        finally:
            await managed_proc.cleanup()


# Enhanced error handling utilities
class ResourceLeakDetector:
    """Detector for potential resource leaks during development."""

    def __init__(self) -> None:
        self.open_files: set[str] = set()
        self.active_processes: set[int] = set()
        self.active_tasks: set[asyncio.Task[t.Any]] = set()
        self._start_time = time.time()

    def track_file(self, file_path: str) -> None:
        """Track an opened file."""
        self.open_files.add(file_path)

    def untrack_file(self, file_path: str) -> None:
        """Untrack a closed file."""
        self.open_files.discard(file_path)

    def track_process(self, pid: int) -> None:
        """Track a spawned process."""
        self.active_processes.add(pid)

    def untrack_process(self, pid: int) -> None:
        """Untrack a terminated process."""
        self.active_processes.discard(pid)

    def track_task(self, task: asyncio.Task[t.Any]) -> None:
        """Track an active task."""
        self.active_tasks.add(task)

    def untrack_task(self, task: asyncio.Task[t.Any]) -> None:
        """Untrack a completed task."""
        self.active_tasks.discard(task)

    def get_leak_report(self) -> dict[str, t.Any]:
        """Get a report of potential resource leaks."""
        return {
            "duration_seconds": time.time() - self._start_time,
            "open_files": list(self.open_files),
            "active_processes": list(self.active_processes),
            "active_tasks": len([t for t in self.active_tasks if not t.done()]),
            "total_tracked_files": len(self.open_files),
            "total_tracked_processes": len(self.active_processes),
            "total_tracked_tasks": len(self.active_tasks),
        }

    def has_potential_leaks(self) -> bool:
        """Check if there are potential resource leaks."""
        return bool(
            self.open_files
            or self.active_processes
            or any(not t.done() for t in self.active_tasks)
        )


# Development-time resource leak detection
_leak_detector: ResourceLeakDetector | None = None


def enable_leak_detection() -> ResourceLeakDetector:
    """Enable resource leak detection for development."""
    global _leak_detector
    _leak_detector = ResourceLeakDetector()
    return _leak_detector


def get_leak_detector() -> ResourceLeakDetector | None:
    """Get the current resource leak detector, if enabled."""
    return _leak_detector


def disable_leak_detection() -> dict[str, t.Any] | None:
    """Disable resource leak detection and return final report."""
    global _leak_detector
    if _leak_detector:
        report = _leak_detector.get_leak_report()
        _leak_detector = None
        return report
    return None
