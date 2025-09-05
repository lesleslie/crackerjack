"""Resource lifecycle management protocols.

Defines protocols and interfaces for comprehensive resource management
patterns throughout the crackerjack codebase.
"""

import typing as t
from abc import ABC, abstractmethod
from types import TracebackType

if t.TYPE_CHECKING:
    import asyncio
    from pathlib import Path


class AsyncCleanupProtocol(t.Protocol):
    """Protocol for resources that support async cleanup."""

    async def cleanup(self) -> None:
        """Clean up the resource asynchronously."""
        ...


class SyncCleanupProtocol(t.Protocol):
    """Protocol for resources that support synchronous cleanup."""

    def cleanup(self) -> None:
        """Clean up the resource synchronously."""
        ...


class ResourceLifecycleProtocol(t.Protocol):
    """Protocol for resources with full lifecycle management."""

    async def initialize(self) -> None:
        """Initialize the resource."""
        ...

    async def cleanup(self) -> None:
        """Clean up the resource."""
        ...

    def is_initialized(self) -> bool:
        """Check if the resource is initialized."""
        ...

    def is_closed(self) -> bool:
        """Check if the resource is closed."""
        ...


class AsyncContextProtocol(t.Protocol):
    """Protocol for async context managers."""

    async def __aenter__(self) -> t.Self:
        """Enter async context."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context."""
        ...


class ResourceManagerProtocol(t.Protocol):
    """Protocol for resource managers."""

    def register_resource(self, resource: AsyncCleanupProtocol) -> None:
        """Register a resource for management."""
        ...

    def register_cleanup_callback(
        self, callback: t.Callable[[], t.Awaitable[None]]
    ) -> None:
        """Register a cleanup callback."""
        ...

    async def cleanup_all(self) -> None:
        """Clean up all managed resources."""
        ...


class FileResourceProtocol(t.Protocol):
    """Protocol for file-based resources."""

    @property
    def path(self) -> "Path":
        """Get the file path."""
        ...

    def exists(self) -> bool:
        """Check if the file exists."""
        ...

    async def cleanup(self) -> None:
        """Clean up the file resource."""
        ...


class ProcessResourceProtocol(t.Protocol):
    """Protocol for process-based resources."""

    @property
    def pid(self) -> int:
        """Get the process ID."""
        ...

    def is_running(self) -> bool:
        """Check if the process is running."""
        ...

    async def cleanup(self) -> None:
        """Clean up the process resource."""
        ...


class TaskResourceProtocol(t.Protocol):
    """Protocol for asyncio task resources."""

    @property
    def task(self) -> "asyncio.Task[t.Any]":
        """Get the asyncio task."""
        ...

    def is_done(self) -> bool:
        """Check if the task is done."""
        ...

    def is_cancelled(self) -> bool:
        """Check if the task is cancelled."""
        ...

    async def cleanup(self) -> None:
        """Clean up the task resource."""
        ...


class NetworkResourceProtocol(t.Protocol):
    """Protocol for network-based resources."""

    @property
    def is_connected(self) -> bool:
        """Check if the resource is connected."""
        ...

    async def disconnect(self) -> None:
        """Disconnect the resource."""
        ...

    async def cleanup(self) -> None:
        """Clean up the network resource."""
        ...


class CacheResourceProtocol(t.Protocol):
    """Protocol for cache-based resources."""

    def clear(self) -> None:
        """Clear the cache."""
        ...

    def get_size(self) -> int:
        """Get the cache size."""
        ...

    async def cleanup(self) -> None:
        """Clean up the cache resource."""
        ...


# Abstract base classes for resource implementations
class AbstractManagedResource(ABC):
    """Abstract base class for managed resources."""

    def __init__(self) -> None:
        self._initialized = False
        self._closed = False

    @abstractmethod
    async def _do_initialize(self) -> None:
        """Perform resource initialization. Override in subclasses."""
        pass

    @abstractmethod
    async def _do_cleanup(self) -> None:
        """Perform resource cleanup. Override in subclasses."""
        pass

    async def initialize(self) -> None:
        """Initialize the resource if not already initialized."""
        if self._initialized:
            return

        try:
            await self._do_initialize()
            self._initialized = True
        except Exception:
            self._closed = True
            raise

    async def cleanup(self) -> None:
        """Clean up the resource if not already closed."""
        if self._closed:
            return

        self._closed = True
        try:
            await self._do_cleanup()
        except Exception:
            # Log but don't re-raise during cleanup
            import logging

            logging.getLogger(__name__).warning(
                f"Error during cleanup of {self.__class__.__name__}", exc_info=True
            )

    def is_initialized(self) -> bool:
        """Check if the resource is initialized."""
        return self._initialized

    def is_closed(self) -> bool:
        """Check if the resource is closed."""
        return self._closed

    async def __aenter__(self) -> t.Self:
        """Enter async context and initialize."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context and cleanup."""
        await self.cleanup()


class AbstractFileResource(AbstractManagedResource):
    """Abstract base class for file-based resources."""

    def __init__(self, path: "Path") -> None:
        super().__init__()
        self._path = path

    @property
    def path(self) -> "Path":
        """Get the file path."""
        return self._path

    def exists(self) -> bool:
        """Check if the file exists."""
        return self._path.exists()


class AbstractProcessResource(AbstractManagedResource):
    """Abstract base class for process-based resources."""

    def __init__(self, pid: int) -> None:
        super().__init__()
        self._pid = pid

    @property
    def pid(self) -> int:
        """Get the process ID."""
        return self._pid

    def is_running(self) -> bool:
        """Check if the process is running."""
        try:
            import os

            os.kill(self._pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class AbstractTaskResource(AbstractManagedResource):
    """Abstract base class for asyncio task resources."""

    def __init__(self, task: "asyncio.Task[t.Any]") -> None:
        super().__init__()
        self._task = task

    @property
    def task(self) -> "asyncio.Task[t.Any]":
        """Get the asyncio task."""
        return self._task

    def is_done(self) -> bool:
        """Check if the task is done."""
        return self._task.done()

    def is_cancelled(self) -> bool:
        """Check if the task is cancelled."""
        return self._task.cancelled()


class AbstractNetworkResource(AbstractManagedResource):
    """Abstract base class for network-based resources."""

    def __init__(self) -> None:
        super().__init__()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if the resource is connected."""
        return self._connected and not self._closed

    async def disconnect(self) -> None:
        """Disconnect the resource."""
        if self._connected:
            self._connected = False
            await self._do_disconnect()

    @abstractmethod
    async def _do_disconnect(self) -> None:
        """Perform disconnection. Override in subclasses."""
        pass

    async def _do_cleanup(self) -> None:
        """Cleanup includes disconnection."""
        await self.disconnect()


# Resource lifecycle decorators
def with_resource_cleanup(resource_attr: str):
    """Decorator to ensure resource cleanup on method exit."""

    def decorator(func: t.Callable[..., t.Awaitable[t.Any]]):
        async def wrapper(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
            resource = getattr(self, resource_attr, None)
            try:
                return await func(self, *args, **kwargs)
            finally:
                if resource and hasattr(resource, "cleanup"):
                    await resource.cleanup()

        return wrapper

    return decorator


def ensure_initialized(resource_attr: str):
    """Decorator to ensure resource is initialized before method execution."""

    def decorator(func: t.Callable[..., t.Awaitable[t.Any]]):
        async def wrapper(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
            resource = getattr(self, resource_attr, None)
            if resource and hasattr(resource, "initialize"):
                await resource.initialize()
            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


# Resource health monitoring protocols
class HealthCheckProtocol(t.Protocol):
    """Protocol for health checking resources."""

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check and return status."""
        ...

    def is_healthy(self) -> bool:
        """Quick health check."""
        ...


class MonitorableResourceProtocol(t.Protocol):
    """Protocol for resources that can be monitored."""

    def get_metrics(self) -> dict[str, t.Any]:
        """Get resource metrics."""
        ...

    def get_status(self) -> str:
        """Get resource status string."""
        ...

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check."""
        ...


# Resource factory protocols
class ResourceFactoryProtocol(t.Protocol):
    """Protocol for resource factories."""

    async def create_resource(self, **kwargs: t.Any) -> AsyncCleanupProtocol:
        """Create a new resource instance."""
        ...

    def get_resource_type(self) -> str:
        """Get the resource type name."""
        ...


class PooledResourceProtocol(t.Protocol):
    """Protocol for pooled resources."""

    async def acquire(self) -> AsyncCleanupProtocol:
        """Acquire a resource from the pool."""
        ...

    async def release(self, resource: AsyncCleanupProtocol) -> None:
        """Release a resource back to the pool."""
        ...

    def get_pool_size(self) -> int:
        """Get current pool size."""
        ...

    def get_active_count(self) -> int:
        """Get count of active resources."""
        ...


# Error handling protocols
class ResourceErrorProtocol(t.Protocol):
    """Protocol for resource error handling."""

    def handle_error(self, error: Exception) -> bool:
        """Handle resource error. Return True if error was handled."""
        ...

    def should_retry(self, error: Exception) -> bool:
        """Check if operation should be retried on this error."""
        ...

    def get_retry_delay(self, attempt: int) -> float:
        """Get delay before retry attempt."""
        ...


class FallbackResourceProtocol(t.Protocol):
    """Protocol for resources with fallback capabilities."""

    async def get_fallback(self) -> AsyncCleanupProtocol | None:
        """Get fallback resource if primary fails."""
        ...

    def has_fallback(self) -> bool:
        """Check if fallback is available."""
        ...
