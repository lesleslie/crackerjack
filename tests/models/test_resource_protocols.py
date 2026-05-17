"""Tests for resource_protocols module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.models.resource_protocols import (
    AbstractFileResource,
    AbstractManagedResource,
    AbstractNetworkResource,
    AbstractProcessResource,
    AbstractTaskResource,
    AsyncCleanupProtocol,
    AsyncContextProtocol,
    CacheResourceProtocol,
    ensure_initialized,
    FileResourceProtocol,
    NetworkResourceProtocol,
    ProcessResourceProtocol,
    ResourceErrorProtocol,
    ResourceLifecycleProtocol,
    SyncCleanupProtocol,
    TaskResourceProtocol,
    with_resource_cleanup,
)


class ConcreteResource(AbstractManagedResource):
    """Concrete implementation of AbstractManagedResource for testing."""

    def __init__(self) -> None:
        super().__init__()
        self.initialize_called = False
        self.cleanup_called = False

    async def _do_initialize(self) -> None:
        self.initialize_called = True

    async def _do_cleanup(self) -> None:
        self.cleanup_called = True


class TestAbstractManagedResource:
    """Tests for AbstractManagedResource base class."""

    @pytest.mark.asyncio
    async def test_initialize(self) -> None:
        """Verify resource initialization."""
        resource = ConcreteResource()
        assert resource.is_initialized() is False
        assert resource.is_closed() is False

        await resource.initialize()

        assert resource.is_initialized() is True
        assert resource.is_closed() is False
        assert resource.initialize_called is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self) -> None:
        """Verify initialize can be called multiple times safely."""
        resource = ConcreteResource()
        await resource.initialize()
        await resource.initialize()

        # Should only initialize once
        assert resource.initialize_called is True

    @pytest.mark.asyncio
    async def test_cleanup(self) -> None:
        """Verify resource cleanup."""
        resource = ConcreteResource()
        await resource.initialize()
        assert resource.is_closed() is False

        await resource.cleanup()

        assert resource.is_closed() is True
        assert resource.cleanup_called is True

    @pytest.mark.asyncio
    async def test_cleanup_idempotent(self) -> None:
        """Verify cleanup can be called multiple times safely."""
        resource = ConcreteResource()
        await resource.initialize()
        await resource.cleanup()
        await resource.cleanup()

        # Should only cleanup once
        assert resource.cleanup_called is True

    @pytest.mark.asyncio
    async def test_initialize_sets_closed_on_error(self) -> None:
        """Verify closed flag is set if initialization fails."""

        class FailingResource(AbstractManagedResource):
            async def _do_initialize(self) -> None:
                raise RuntimeError("Init failed")

            async def _do_cleanup(self) -> None:
                pass

        resource = FailingResource()
        with pytest.raises(RuntimeError):
            await resource.initialize()

        assert resource.is_closed() is True
        assert resource.is_initialized() is False

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Verify resource as async context manager."""
        resource = ConcreteResource()

        async with resource:
            assert resource.is_initialized() is True
            assert resource.is_closed() is False

        assert resource.is_closed() is True

    @pytest.mark.asyncio
    async def test_cleanup_logs_error(self) -> None:
        """Verify cleanup logs errors without raising."""

        class FailingCleanupResource(AbstractManagedResource):
            async def _do_initialize(self) -> None:
                pass

            async def _do_cleanup(self) -> None:
                raise RuntimeError("Cleanup failed")

        resource = FailingCleanupResource()
        await resource.initialize()

        # Should not raise even though cleanup fails
        await resource.cleanup()
        assert resource.is_closed() is True


class ConcreteFileResource(AbstractFileResource):
    """Concrete file resource for testing."""

    async def _do_initialize(self) -> None:
        pass

    async def _do_cleanup(self) -> None:
        pass


class TestAbstractFileResource:
    """Tests for AbstractFileResource."""

    @pytest.mark.asyncio
    async def test_file_resource_creation(self, tmp_path: Path) -> None:
        """Verify file resource with path."""
        file_path = tmp_path / "test.txt"
        file_path.touch()

        resource = ConcreteFileResource(file_path)
        assert resource.path == file_path
        assert resource.exists() is True

    @pytest.mark.asyncio
    async def test_file_resource_nonexistent(self, tmp_path: Path) -> None:
        """Verify nonexistent file returns False."""
        file_path = tmp_path / "nonexistent.txt"
        resource = ConcreteFileResource(file_path)
        assert resource.exists() is False

    @pytest.mark.asyncio
    async def test_file_resource_initialize(self, tmp_path: Path) -> None:
        """Verify file resource initialization."""
        file_path = tmp_path / "test.txt"
        file_path.touch()

        resource = ConcreteFileResource(file_path)
        await resource.initialize()

        assert resource.is_initialized() is True


class ConcreteProcessResource(AbstractProcessResource):
    """Concrete process resource for testing."""

    async def _do_initialize(self) -> None:
        pass

    async def _do_cleanup(self) -> None:
        pass


class TestAbstractProcessResource:
    """Tests for AbstractProcessResource."""

    @pytest.mark.asyncio
    async def test_process_resource_creation(self) -> None:
        """Verify process resource with PID."""
        resource = ConcreteProcessResource(1)
        assert resource.pid == 1

    @pytest.mark.asyncio
    async def test_is_running_current_process(self) -> None:
        """Verify current process reports as running."""
        import os

        resource = ConcreteProcessResource(os.getpid())
        assert resource.is_running() is True

    @pytest.mark.asyncio
    async def test_is_running_nonexistent_process(self) -> None:
        """Verify nonexistent process reports as not running."""
        # Use a very high PID that's unlikely to exist
        resource = ConcreteProcessResource(999999)
        assert resource.is_running() is False

    @pytest.mark.asyncio
    async def test_process_resource_initialize(self) -> None:
        """Verify process resource initialization."""
        import os

        resource = ConcreteProcessResource(os.getpid())
        await resource.initialize()
        assert resource.is_initialized() is True


class ConcreteTaskResource(AbstractTaskResource):
    """Concrete task resource for testing."""

    async def _do_initialize(self) -> None:
        pass

    async def _do_cleanup(self) -> None:
        pass


class TestAbstractTaskResource:
    """Tests for AbstractTaskResource."""

    @pytest.mark.asyncio
    async def test_task_resource_creation(self) -> None:
        """Verify task resource wrapping asyncio task."""

        async def dummy_coro() -> None:
            await asyncio.sleep(0)

        task = asyncio.create_task(dummy_coro())
        resource = ConcreteTaskResource(task)

        assert resource.task is task
        assert resource.is_done() is False
        assert resource.is_cancelled() is False

        await task
        assert resource.is_done() is True

    @pytest.mark.asyncio
    async def test_task_resource_cancelled(self) -> None:
        """Verify cancelled task status."""

        async def dummy_coro() -> None:
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy_coro())
        resource = ConcreteTaskResource(task)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert resource.is_cancelled() is True

    @pytest.mark.asyncio
    async def test_task_resource_initialize(self) -> None:
        """Verify task resource initialization."""

        async def dummy_coro() -> None:
            pass

        task = asyncio.create_task(dummy_coro())
        resource = ConcreteTaskResource(task)

        await resource.initialize()
        assert resource.is_initialized() is True

        await task


class TestAbstractNetworkResource:
    """Tests for AbstractNetworkResource."""

    class ConcreteNetworkResource(AbstractNetworkResource):
        """Concrete network resource for testing."""

        async def _do_initialize(self) -> None:
            self._connected = True

        async def _do_disconnect(self) -> None:
            pass

    @pytest.mark.asyncio
    async def test_network_resource_creation(self) -> None:
        """Verify network resource creation."""
        resource = self.ConcreteNetworkResource()
        assert resource.is_connected is False

    @pytest.mark.asyncio
    async def test_network_resource_initialize_connects(self) -> None:
        """Verify initialization sets connected state."""
        resource = self.ConcreteNetworkResource()
        await resource.initialize()

        assert resource.is_connected is True

    @pytest.mark.asyncio
    async def test_network_resource_disconnect(self) -> None:
        """Verify disconnect clears connected state."""
        resource = self.ConcreteNetworkResource()
        await resource.initialize()
        assert resource.is_connected is True

        await resource.disconnect()
        assert resource.is_connected is False

    @pytest.mark.asyncio
    async def test_network_resource_cleanup_disconnects(self) -> None:
        """Verify cleanup calls disconnect."""
        resource = self.ConcreteNetworkResource()
        await resource.initialize()
        await resource.cleanup()

        assert resource.is_connected is False
        assert resource.is_closed() is True


class TestWithResourceCleanupDecorator:
    """Tests for with_resource_cleanup decorator."""

    @pytest.mark.asyncio
    async def test_cleanup_on_success(self) -> None:
        """Verify resource cleanup called after successful function."""

        class ResourceHolder:
            def __init__(self) -> None:
                self.resource = AsyncMock(spec=AsyncCleanupProtocol)

            @with_resource_cleanup("resource")
            async def do_work(self) -> str:
                return "success"

        holder = ResourceHolder()
        result = await holder.do_work()

        assert result == "success"
        holder.resource.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self) -> None:
        """Verify resource cleanup called even on exception."""

        class ResourceHolder:
            def __init__(self) -> None:
                self.resource = AsyncMock(spec=AsyncCleanupProtocol)

            @with_resource_cleanup("resource")
            async def do_work(self) -> None:
                raise RuntimeError("Work failed")

        holder = ResourceHolder()
        with pytest.raises(RuntimeError):
            await holder.do_work()

        holder.resource.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_missing_resource_attr(self) -> None:
        """Verify decorator handles missing resource attribute."""

        class ResourceHolder:
            @with_resource_cleanup("missing_resource")
            async def do_work(self) -> str:
                return "success"

        holder = ResourceHolder()
        result = await holder.do_work()

        # Should still work, just no cleanup
        assert result == "success"

    @pytest.mark.asyncio
    async def test_cleanup_missing_cleanup_method(self) -> None:
        """Verify decorator handles resource without cleanup method."""

        class ResourceHolder:
            def __init__(self) -> None:
                # Create object that explicitly doesn't have cleanup method
                self.resource = object()

            @with_resource_cleanup("resource")
            async def do_work(self) -> str:
                return "success"

        holder = ResourceHolder()
        result = await holder.do_work()

        # Should still work
        assert result == "success"


class TestEnsureInitializedDecorator:
    """Tests for ensure_initialized decorator."""

    @pytest.mark.asyncio
    async def test_initialize_before_execution(self) -> None:
        """Verify resource initialized before function execution."""

        class ResourceHolder:
            def __init__(self) -> None:
                self.resource = AsyncMock(spec=ResourceLifecycleProtocol)
                self.resource.initialize = AsyncMock()

            @ensure_initialized("resource")
            async def do_work(self) -> str:
                return "success"

        holder = ResourceHolder()
        result = await holder.do_work()

        assert result == "success"
        holder.resource.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_missing_resource_attr(self) -> None:
        """Verify decorator handles missing resource attribute."""

        class ResourceHolder:
            @ensure_initialized("missing_resource")
            async def do_work(self) -> str:
                return "success"

        holder = ResourceHolder()
        result = await holder.do_work()

        # Should still work, just no initialization
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_missing_initialize_method(self) -> None:
        """Verify decorator handles resource without initialize method."""

        class ResourceHolder:
            def __init__(self) -> None:
                # Create object that explicitly doesn't have initialize method
                self.resource = object()

            @ensure_initialized("resource")
            async def do_work(self) -> str:
                return "success"

        holder = ResourceHolder()
        result = await holder.do_work()

        # Should still work
        assert result == "success"

    @pytest.mark.asyncio
    async def test_initialize_propagates_exceptions(self) -> None:
        """Verify decorator propagates initialization errors."""

        class ResourceHolder:
            def __init__(self) -> None:
                self.resource = AsyncMock(spec=ResourceLifecycleProtocol)
                self.resource.initialize = AsyncMock(
                    side_effect=RuntimeError("Init failed")
                )

            @ensure_initialized("resource")
            async def do_work(self) -> str:
                return "success"

        holder = ResourceHolder()
        with pytest.raises(RuntimeError, match="Init failed"):
            await holder.do_work()


class TestResourceProtocolImplementation:
    """Tests for protocol implementations."""

    def test_sync_cleanup_protocol(self) -> None:
        """Verify SyncCleanupProtocol implementation."""

        class SyncResource:
            def cleanup(self) -> None:
                pass

        obj = SyncResource()
        # Should be compatible with protocol
        assert hasattr(obj, "cleanup")

    @pytest.mark.asyncio
    async def test_async_cleanup_protocol(self) -> None:
        """Verify AsyncCleanupProtocol implementation."""

        class AsyncResource:
            async def cleanup(self) -> None:
                pass

        obj = AsyncResource()
        # Should be compatible with protocol
        assert hasattr(obj, "cleanup")
        await obj.cleanup()

    def test_process_resource_protocol_impl(self) -> None:
        """Verify ProcessResourceProtocol implementation."""

        class ProcessResource:
            @property
            def pid(self) -> int:
                return 1234

            def is_running(self) -> bool:
                return True

            async def cleanup(self) -> None:
                pass

        obj = ProcessResource()
        # Should be compatible with protocol
        assert hasattr(obj, "pid")
        assert hasattr(obj, "is_running")
        assert hasattr(obj, "cleanup")

    def test_cache_resource_protocol_impl(self) -> None:
        """Verify CacheResourceProtocol implementation."""

        class CacheResource:
            def clear(self) -> None:
                pass

            def get_size(self) -> int:
                return 0

            async def cleanup(self) -> None:
                pass

        obj = CacheResource()
        assert hasattr(obj, "clear")
        assert hasattr(obj, "get_size")
        assert hasattr(obj, "cleanup")
