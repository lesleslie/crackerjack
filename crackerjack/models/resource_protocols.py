import typing as t
from abc import ABC, abstractmethod
from types import TracebackType

if t.TYPE_CHECKING:
    import asyncio
    from pathlib import Path


class AsyncCleanupProtocol(t.Protocol):
    async def cleanup(self) -> None: ...


class SyncCleanupProtocol(t.Protocol):
    def cleanup(self) -> None: ...


class ResourceLifecycleProtocol(t.Protocol):
    async def initialize(self) -> None: ...

    async def cleanup(self) -> None: ...

    def is_initialized(self) -> bool: ...

    def is_closed(self) -> bool: ...


class AsyncContextProtocol(t.Protocol):
    async def __aenter__(self) -> t.Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...


class ResourceManagerProtocol(t.Protocol):
    def register_resource(self, resource: AsyncCleanupProtocol) -> None: ...

    def register_cleanup_callback(
        self, callback: t.Callable[[], t.Awaitable[None]]
    ) -> None: ...

    async def cleanup_all(self) -> None: ...


class FileResourceProtocol(t.Protocol):
    @property
    def path(self) -> "Path": ...

    def exists(self) -> bool: ...

    async def cleanup(self) -> None: ...


class ProcessResourceProtocol(t.Protocol):
    @property
    def pid(self) -> int: ...

    def is_running(self) -> bool: ...

    async def cleanup(self) -> None: ...


class TaskResourceProtocol(t.Protocol):
    @property
    def task(self) -> "asyncio.Task[t.Any]": ...

    def is_done(self) -> bool: ...

    def is_cancelled(self) -> bool: ...

    async def cleanup(self) -> None: ...


class NetworkResourceProtocol(t.Protocol):
    @property
    def is_connected(self) -> bool: ...

    async def disconnect(self) -> None: ...

    async def cleanup(self) -> None: ...


class CacheResourceProtocol(t.Protocol):
    def clear(self) -> None: ...

    def get_size(self) -> int: ...

    async def cleanup(self) -> None: ...


class AbstractManagedResource(ABC):
    def __init__(self) -> None:
        self._initialized = False
        self._closed = False

    @abstractmethod
    async def _do_initialize(self) -> None:
        pass

    @abstractmethod
    async def _do_cleanup(self) -> None:
        pass

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            await self._do_initialize()
            self._initialized = True
        except Exception:
            self._closed = True
            raise

    async def cleanup(self) -> None:
        if self._closed:
            return

        self._closed = True
        try:
            await self._do_cleanup()
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                f"Error during cleanup of {self.__class__.__name__}", exc_info=True
            )

    def is_initialized(self) -> bool:
        return self._initialized

    def is_closed(self) -> bool:
        return self._closed

    async def __aenter__(self) -> t.Self:
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.cleanup()


class AbstractFileResource(AbstractManagedResource):
    def __init__(self, path: "Path") -> None:
        super().__init__()
        self._path = path

    @property
    def path(self) -> "Path":
        return self._path

    def exists(self) -> bool:
        return self._path.exists()


class AbstractProcessResource(AbstractManagedResource):
    def __init__(self, pid: int) -> None:
        super().__init__()
        self._pid = pid

    @property
    def pid(self) -> int:
        return self._pid

    def is_running(self) -> bool:
        try:
            import os

            os.kill(self._pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class AbstractTaskResource(AbstractManagedResource):
    def __init__(self, task: "asyncio.Task[t.Any]") -> None:
        super().__init__()
        self._task = task

    @property
    def task(self) -> "asyncio.Task[t.Any]":
        return self._task

    def is_done(self) -> bool:
        return self._task.done()

    def is_cancelled(self) -> bool:
        return self._task.cancelled()


class AbstractNetworkResource(AbstractManagedResource):
    def __init__(self) -> None:
        super().__init__()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and not self._closed

    async def disconnect(self) -> None:
        if self._connected:
            self._connected = False
            await self._do_disconnect()

    @abstractmethod
    async def _do_disconnect(self) -> None:
        pass

    async def _do_cleanup(self) -> None:
        await self.disconnect()


def with_resource_cleanup(
    resource_attr: str,
) -> t.Callable[..., t.Callable[..., t.Awaitable[t.Any]]]:
    def decorator(
        func: t.Callable[..., t.Awaitable[t.Any]],
    ) -> t.Callable[..., t.Awaitable[t.Any]]:
        async def wrapper(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
            resource = getattr(self, resource_attr, None)
            try:
                return await func(self, *args, **kwargs)
            finally:
                if resource and hasattr(resource, "cleanup"):
                    await resource.cleanup()

        return wrapper

    return decorator


def ensure_initialized(
    resource_attr: str,
) -> t.Callable[..., t.Callable[..., t.Awaitable[t.Any]]]:
    def decorator(
        func: t.Callable[..., t.Awaitable[t.Any]],
    ) -> t.Callable[..., t.Awaitable[t.Any]]:
        async def wrapper(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
            resource = getattr(self, resource_attr, None)
            if resource and hasattr(resource, "initialize"):
                await resource.initialize()
            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


class HealthCheckProtocol(t.Protocol):
    async def health_check(self) -> dict[str, t.Any]: ...

    def is_healthy(self) -> bool: ...


class MonitorableResourceProtocol(t.Protocol):
    def get_metrics(self) -> dict[str, t.Any]: ...

    def get_status(self) -> str: ...

    async def health_check(self) -> dict[str, t.Any]: ...


class ResourceFactoryProtocol(t.Protocol):
    async def create_resource(self, **kwargs: t.Any) -> AsyncCleanupProtocol: ...

    def get_resource_type(self) -> str: ...


class PooledResourceProtocol(t.Protocol):
    async def acquire(self) -> AsyncCleanupProtocol: ...

    async def release(self, resource: AsyncCleanupProtocol) -> None: ...

    def get_pool_size(self) -> int: ...

    def get_active_count(self) -> int: ...


class ResourceErrorProtocol(t.Protocol):
    def handle_error(self, error: Exception) -> bool: ...

    def should_retry(self, error: Exception) -> bool: ...

    def get_retry_delay(self, attempt: int) -> float: ...


class FallbackResourceProtocol(t.Protocol):
    async def get_fallback(self) -> AsyncCleanupProtocol | None: ...

    def has_fallback(self) -> bool: ...
