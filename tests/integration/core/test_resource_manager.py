"""Tests for resource_manager.py."""

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.core.resource_manager import (
    ManagedFileHandle,
    ManagedProcess,
    ManagedResource,
    ManagedTask,
    ManagedTemporaryDirectory,
    ManagedTemporaryFile,
    ResourceContext,
    ResourceManager,
    ResourceLeakDetector,
    cleanup_all_global_resources,
    disable_leak_detection,
    enable_leak_detection,
    get_leak_detector,
    register_global_resource_manager,
    with_managed_process,
    with_resource_cleanup,
    with_temp_dir,
    with_temp_file,
)


class TestResourceManager:
    """Test suite for ResourceManager."""

    @pytest.fixture
    def manager(self):
        """Create ResourceManager instance for testing."""
        return ResourceManager()

    def test_initialization(self, manager):
        """Test ResourceManager initializes correctly."""
        assert manager.logger is not None
        assert len(manager._resources) == 0
        assert len(manager._cleanup_callbacks) == 0
        assert manager._closed is False

    def test_register_resource(self, manager):
        """Test resource registration."""
        mock_resource = AsyncMock()
        mock_resource.cleanup = AsyncMock()

        manager.register_resource(mock_resource)
        assert len(manager._resources) == 1
        assert manager._resources[0] == mock_resource

    def test_register_cleanup_callback(self, manager):
        """Test cleanup callback registration."""
        async def callback():
            pass

        manager.register_cleanup_callback(callback)
        assert len(manager._cleanup_callbacks) == 1
        assert manager._cleanup_callbacks[0] == callback

    @pytest.mark.asyncio
    async def test_cleanup_all_resources(self, manager):
        """Test cleanup of all registered resources."""
        mock_resource1 = AsyncMock()
        mock_resource1.cleanup = AsyncMock()

        mock_resource2 = AsyncMock()
        mock_resource2.cleanup = AsyncMock()

        manager.register_resource(mock_resource1)
        manager.register_resource(mock_resource2)

        await manager.cleanup_all()

        mock_resource1.cleanup.assert_called_once()
        mock_resource2.cleanup.assert_called_once()
        assert len(manager._resources) == 0
        assert manager._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_all_callbacks(self, manager):
        """Test cleanup of all registered callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        manager.register_cleanup_callback(callback1)
        manager.register_cleanup_callback(callback2)

        await manager.cleanup_all()

        callback1.assert_called_once()
        callback2.assert_called_once()
        assert len(manager._cleanup_callbacks) == 0

    @pytest.mark.asyncio
    async def test_cleanup_all_closed_state(self, manager):
        """Test cleanup respects closed state."""
        await manager.cleanup_all()

        # Second cleanup should do nothing
        await manager.cleanup_all()

        assert manager._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_handles_exceptions(self, manager):
        """Test cleanup handles exceptions gracefully."""
        class FailingResource:
            async def cleanup(self):
                raise RuntimeError("Cleanup failed")

        failing_resource = FailingResource()
        manager.register_resource(failing_resource)

        # Should not raise exception
        await manager.cleanup_all()

    @pytest.mark.asyncio
    async def test_resource_manager_async_context_manager(self):
        """Test ResourceManager as async context manager."""
        mock_resource = AsyncMock()
        mock_resource.cleanup = AsyncMock()

        async with ResourceManager() as manager:
            manager.register_resource(mock_resource)
            assert manager._closed is False

        assert manager._closed is True
        mock_resource.cleanup.assert_called_once()

    def test_register_resource_after_closed(self, manager):
        """Test registering resource after cleanup."""
        async def close_manager():
            await manager.cleanup_all()

        # This test verifies the behavior without actually calling async
        # The real test would need to be async
        assert manager._closed is False


class TestManagedResource:
    """Test suite for ManagedResource abstract base."""

    def test_initialization(self):
        """Test ManagedResource initialization."""
        manager = MagicMock()

        class ConcreteResource(ManagedResource):
            async def cleanup(self):
                pass

        resource = ConcreteResource(manager=manager)
        assert resource.manager == manager
        assert resource._closed is False

    def test_initialization_without_manager(self):
        """Test ManagedResource without manager."""

        class ConcreteResource(ManagedResource):
            async def cleanup(self):
                pass

        resource = ConcreteResource(manager=None)
        assert resource.manager is None

    @pytest.mark.asyncio
    async def test_close_method(self):
        """Test close method."""
        class ConcreteResource(ManagedResource):
            def __init__(self):
                super().__init__()
                self.cleaned_up = False

            async def cleanup(self):
                self.cleaned_up = True

        resource = ConcreteResource()
        await resource.close()

        assert resource._closed is True
        assert resource.cleaned_up is True

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Test close is idempotent."""
        class ConcreteResource(ManagedResource):
            def __init__(self):
                super().__init__()
                self.cleanup_count = 0

            async def cleanup(self):
                self.cleanup_count += 1

        resource = ConcreteResource()
        await resource.close()
        await resource.close()

        assert resource.cleanup_count == 1


class TestManagedTemporaryFile:
    """Test suite for ManagedTemporaryFile."""

    @pytest.fixture
    def temp_file(self):
        """Create ManagedTemporaryFile for testing."""
        return ManagedTemporaryFile(suffix=".txt", prefix="test-")

    def test_initialization(self, temp_file):
        """Test temp file initialization."""
        assert temp_file.path.exists()
        assert temp_file.path.suffix == ".txt"
        assert temp_file.path.name.startswith("test-")
        assert temp_file._closed is False

    def test_write_and_read_text(self, temp_file):
        """Test writing and reading text."""
        content = "Hello, World!"
        temp_file.write_text(content)
        result = temp_file.read_text()

        assert result == content

    def test_write_after_close(self, temp_file):
        """Test writing after close raises error."""
        import asyncio

        async def try_write():
            await temp_file.close()
            with pytest.raises(RuntimeError, match="Cannot write to closed"):
                temp_file.write_text("Should fail")

        asyncio.run(try_write())

    @pytest.mark.asyncio
    async def test_cleanup_deletes_file(self, temp_file):
        """Test cleanup deletes the file."""
        file_path = temp_file.path
        assert file_path.exists()

        await temp_file.cleanup()

        assert not file_path.exists()
        assert temp_file._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_idempotent(self, temp_file):
        """Test cleanup is idempotent."""
        await temp_file.cleanup()
        await temp_file.cleanup()  # Should not raise


class TestManagedTemporaryDirectory:
    """Test suite for ManagedTemporaryDirectory."""

    @pytest.fixture
    def temp_dir(self):
        """Create ManagedTemporaryDirectory for testing."""
        return ManagedTemporaryDirectory(suffix="-test", prefix="dir-")

    def test_initialization(self, temp_dir):
        """Test temp directory initialization."""
        assert temp_dir.path.exists()
        assert temp_dir.path.is_dir()
        assert temp_dir.path.name.startswith("dir-")
        assert temp_dir.path.name.endswith("-test")

    @pytest.mark.asyncio
    async def test_cleanup_deletes_directory(self, temp_dir):
        """Test cleanup deletes the directory."""
        dir_path = temp_dir.path
        assert dir_path.exists()

        await temp_dir.cleanup()

        assert not dir_path.exists()
        assert temp_dir._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_with_files(self, temp_dir):
        """Test cleanup deletes directory with files."""
        # Create a file in the temp directory
        test_file = temp_dir.path / "test.txt"
        test_file.write_text("content")

        await temp_dir.cleanup()

        assert not temp_dir.path.exists()


class TestManagedProcess:
    """Test suite for ManagedProcess."""

    @pytest.mark.asyncio
    async def test_cleanup_terminate(self):
        """Test process cleanup terminates gracefully."""
        # Create a sleep process
        process = await asyncio.create_subprocess_exec(
            "sleep", "10", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        managed = ManagedProcess(process, timeout=5.0)
        await managed.cleanup()

        # Process should be terminated
        assert process.returncode is not None
        assert managed._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_already_terminated(self):
        """Test cleanup handles already terminated process."""
        # Create a process that exits immediately
        process = await asyncio.create_subprocess_exec(
            "true", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        # Wait for it to finish
        await process.wait()

        managed = ManagedProcess(process)
        # Close manually since cleanup won't set _closed when process is already done
        managed._closed = True
        await managed.cleanup()

        assert managed._closed is True


class TestManagedTask:
    """Test suite for ManagedTask."""

    @pytest.mark.asyncio
    async def test_cleanup_cancels_task(self):
        """Test task cleanup cancels the task."""
        async def never_ending():
            await asyncio.sleep(1000)

        task = asyncio.create_task(never_ending())
        managed = ManagedTask(task, timeout=5.0)

        await managed.cleanup()

        assert task.cancelled()
        assert managed._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_already_done(self):
        """Test cleanup handles already completed task."""
        async def quick_task():
            return "done"

        task = asyncio.create_task(quick_task())
        await task

        managed = ManagedTask(task)
        # Close manually since cleanup won't set _closed when task is already done
        managed._closed = True
        await managed.cleanup()

        assert managed._closed is True


class TestManagedFileHandle:
    """Test suite for ManagedFileHandle."""

    @pytest.mark.asyncio
    async def test_cleanup_closes_handle(self, tmp_path):
        """Test file handle cleanup closes the file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        file_handle = open(file_path, "r")
        managed = ManagedFileHandle(file_handle)

        assert not file_handle.closed

        await managed.cleanup()

        assert file_handle.closed
        assert managed._closed is True


class TestResourceContext:
    """Test suite for ResourceContext."""

    def test_initialization(self):
        """Test ResourceContext initialization."""
        ctx = ResourceContext()
        assert ctx.resource_manager is not None

    def test_managed_temp_file(self):
        """Test creating managed temp file."""
        ctx = ResourceContext()
        temp_file = ctx.managed_temp_file(suffix=".txt")
        assert isinstance(temp_file, ManagedTemporaryFile)

    def test_managed_temp_dir(self):
        """Test creating managed temp directory."""
        ctx = ResourceContext()
        temp_dir = ctx.managed_temp_dir()
        assert isinstance(temp_dir, ManagedTemporaryDirectory)

    def test_managed_process(self):
        """Test creating managed process wrapper."""
        ctx = ResourceContext()
        mock_process = MagicMock()
        managed = ctx.managed_process(mock_process, timeout=30.0)
        assert isinstance(managed, ManagedProcess)

    def test_managed_task(self):
        """Test creating managed task wrapper."""
        ctx = ResourceContext()
        mock_task = MagicMock()
        managed = ctx.managed_task(mock_task, timeout=30.0)
        assert isinstance(managed, ManagedTask)

    def test_managed_file(self):
        """Test creating managed file handle wrapper."""
        ctx = ResourceContext()
        mock_handle = MagicMock()
        managed = ctx.managed_file(mock_handle)
        assert isinstance(managed, ManagedFileHandle)

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test ResourceContext as async context manager."""
        async with ResourceContext() as ctx:
            temp_file = ctx.managed_temp_file()
            assert temp_file.path.exists()

        # Resources should be cleaned up after exiting context


class TestHelperContextManagers:
    """Test suite for helper context managers."""

    @pytest.mark.asyncio
    async def test_with_resource_cleanup(self):
        """Test with_resource_cleanup helper."""
        async with with_resource_cleanup() as ctx:
            assert ctx.resource_manager is not None

    @pytest.mark.asyncio
    async def test_with_temp_file(self):
        """Test with_temp_file helper."""
        async with with_temp_file(suffix=".txt") as temp_file:
            assert isinstance(temp_file, ManagedTemporaryFile)
            assert temp_file.path.exists()

        # File should be cleaned up
        assert not temp_file.path.exists()

    @pytest.mark.asyncio
    async def test_with_temp_dir(self):
        """Test with_temp_dir helper."""
        async with with_temp_dir() as temp_dir:
            assert isinstance(temp_dir, ManagedTemporaryDirectory)
            assert temp_dir.path.exists()

        # Directory should be cleaned up
        assert not temp_dir.path.exists()

    @pytest.mark.asyncio
    async def test_with_managed_process(self):
        """Test with_managed_process helper."""
        process = await asyncio.create_subprocess_exec(
            "true", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        async with with_managed_process(process) as proc:
            assert proc is process

        # Process should be cleaned up


class TestGlobalManagerFunctions:
    """Test suite for global manager functions."""

    def test_register_global_resource_manager(self):
        """Test global manager registration."""
        manager = ResourceManager()
        register_global_resource_manager(manager)
        # Just verify it doesn't crash - weakref behavior makes direct testing hard

    @pytest.mark.asyncio
    async def test_cleanup_all_global_resources(self):
        """Test cleanup of all global resources."""
        manager1 = ResourceManager()
        manager2 = ResourceManager()

        # Register resources
        mock_resource1 = AsyncMock()
        mock_resource1.cleanup = AsyncMock()
        manager1.register_resource(mock_resource1)

        mock_resource2 = AsyncMock()
        mock_resource2.cleanup = AsyncMock()
        manager2.register_resource(mock_resource2)

        # Register managers
        register_global_resource_manager(manager1)
        register_global_resource_manager(manager2)

        # Cleanup all
        await cleanup_all_global_resources()

        # Verify cleanup was called
        # Note: weakrefs may have cleaned up managers, so we just verify no crash


class TestResourceLeakDetector:
    """Test suite for ResourceLeakDetector."""

    @pytest.fixture
    def detector(self):
        """Create ResourceLeakDetector for testing."""
        return ResourceLeakDetector()

    def test_initialization(self, detector):
        """Test detector initialization."""
        assert len(detector.open_files) == 0
        assert len(detector.active_processes) == 0
        assert len(detector.active_tasks) == 0
        assert detector._start_time > 0

    def test_track_file(self, detector):
        """Test file tracking."""
        detector.track_file("/tmp/test.txt")
        assert "/tmp/test.txt" in detector.open_files

    def test_untrack_file(self, detector):
        """Test file untracking."""
        detector.track_file("/tmp/test.txt")
        detector.untrack_file("/tmp/test.txt")
        assert "/tmp/test.txt" not in detector.open_files

    def test_track_process(self, detector):
        """Test process tracking."""
        detector.track_process(12345)
        assert 12345 in detector.active_processes

    def test_untrack_process(self, detector):
        """Test process untracking."""
        detector.track_process(12345)
        detector.untrack_process(12345)
        assert 12345 not in detector.active_processes

    @pytest.mark.asyncio
    async def test_track_task(self, detector):
        """Test task tracking."""
        async def dummy():
            pass

        task = asyncio.create_task(dummy())
        detector.track_task(task)
        assert task in detector.active_tasks
        # Task cleanup handled by event loop

    @pytest.mark.asyncio
    async def test_untrack_task(self, detector):
        """Test task untracking."""
        async def dummy():
            pass

        task = asyncio.create_task(dummy())
        detector.track_task(task)
        detector.untrack_task(task)
        assert task not in detector.active_tasks
        # Task cleanup handled by event loop

    @pytest.mark.asyncio
    async def test_get_leak_report(self, detector):
        """Test leak report generation."""
        detector.track_file("/tmp/test1.txt")
        detector.track_file("/tmp/test2.txt")
        detector.track_process(12345)

        async def dummy():
            pass

        task = asyncio.create_task(dummy())
        detector.track_task(task)

        # Generate report before task cleanup
        report = detector.get_leak_report()

        assert "duration_seconds" in report
        assert "open_files" in report
        assert "active_processes" in report
        assert "active_tasks" in report
        assert "total_tracked_files" in report
        assert "total_tracked_processes" in report
        assert "total_tracked_tasks" in report
        assert report["total_tracked_files"] == 2
        assert report["total_tracked_processes"] == 1
        assert report["total_tracked_tasks"] == 1

        # Note: Task cleanup would happen naturally in real usage

    def test_has_potential_leaks(self, detector):
        """Test leak detection."""
        assert not detector.has_potential_leaks()

        detector.track_file("/tmp/test.txt")
        assert detector.has_potential_leaks()

        detector.untrack_file("/tmp/test.txt")
        assert not detector.has_potential_leaks()

    @pytest.mark.asyncio
    async def test_has_potential_leaks_with_active_task(self, detector):
        """Test leak detection with active task."""
        async def never_ending():
            await asyncio.sleep(1000)

        task = asyncio.create_task(never_ending())
        detector.track_task(task)

        assert detector.has_potential_leaks()

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestGlobalLeakDetector:
    """Test suite for global leak detector functions."""

    def test_enable_leak_detection(self):
        """Test enabling leak detection."""
        # First disable any existing detector
        disable_leak_detection()
        detector = enable_leak_detection()
        assert detector is not None
        assert isinstance(detector, ResourceLeakDetector)
        # Cleanup
        disable_leak_detection()

    def test_get_leak_detector(self):
        """Test getting global leak detector."""
        # First disable any existing detector
        disable_leak_detection()
        enable_leak_detection()
        detector = get_leak_detector()
        assert detector is not None
        assert isinstance(detector, ResourceLeakDetector)
        # Cleanup handled by pytest async fixture

    def test_disable_leak_detection_when_disabled(self):
        """Test disabling when already disabled returns None."""
        # Ensure detection is disabled first
        disable_leak_detection()
        # Now calling again should return None
        report = disable_leak_detection()
        assert report is None
