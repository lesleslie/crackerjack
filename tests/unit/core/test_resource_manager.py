"""Unit tests for resource_manager.

Tests resource management, cleanup, temporary resources,
process/task management, and leak detection.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.core.resource_manager import (
    ManagedFileHandle,
    ManagedProcess,
    ManagedTask,
    ManagedTemporaryDirectory,
    ManagedTemporaryFile,
    ResourceContext,
    ResourceLeakDetector,
    ResourceManager,
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


@pytest.mark.unit
class TestResourceManagerInitialization:
    """Test ResourceManager initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        manager = ResourceManager()

        assert manager._resources == []
        assert manager._cleanup_callbacks == []
        assert manager._closed is False

    def test_initialization_with_logger(self):
        """Test initialization with custom logger."""
        mock_logger = Mock()

        manager = ResourceManager(logger=mock_logger)

        assert manager.logger == mock_logger


@pytest.mark.unit
class TestResourceManagerRegistration:
    """Test resource registration."""

    def test_register_resource(self):
        """Test registering a resource."""
        manager = ResourceManager()
        resource = Mock()
        resource.cleanup = AsyncMock()

        manager.register_resource(resource)

        assert resource in manager._resources

    def test_register_resource_when_closed(self):
        """Test registering resource when manager is closed."""
        manager = ResourceManager()
        manager._closed = True

        resource = Mock()
        resource.cleanup = AsyncMock()

        with patch("asyncio.create_task") as mock_create_task:
            manager.register_resource(resource)

            # Should cleanup immediately
            mock_create_task.assert_called_once()

    def test_register_cleanup_callback(self):
        """Test registering cleanup callback."""
        manager = ResourceManager()

        async def cleanup_callback():
            pass

        manager.register_cleanup_callback(cleanup_callback)

        assert cleanup_callback in manager._cleanup_callbacks

    @pytest.mark.asyncio
    async def test_register_cleanup_callback_when_closed(self):
        """Test registering callback when manager is closed."""
        manager = ResourceManager()
        manager._closed = True

        callback_executed = False

        async def cleanup_callback():
            nonlocal callback_executed
            callback_executed = True

        with patch("asyncio.ensure_future") as mock_ensure:
            manager.register_cleanup_callback(cleanup_callback)

            # Should execute immediately
            mock_ensure.assert_called_once()


@pytest.mark.unit
class TestResourceManagerCleanup:
    """Test resource cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_all_resources(self):
        """Test cleanup all resources."""
        manager = ResourceManager()

        resource1 = Mock()
        resource1.cleanup = AsyncMock()
        resource2 = Mock()
        resource2.cleanup = AsyncMock()

        manager.register_resource(resource1)
        manager.register_resource(resource2)

        await manager.cleanup_all()

        resource1.cleanup.assert_called_once()
        resource2.cleanup.assert_called_once()
        assert manager._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_all_callbacks(self):
        """Test cleanup all callbacks."""
        manager = ResourceManager()

        callback1_executed = False
        callback2_executed = False

        async def callback1():
            nonlocal callback1_executed
            callback1_executed = True

        async def callback2():
            nonlocal callback2_executed
            callback2_executed = True

        manager.register_cleanup_callback(callback1)
        manager.register_cleanup_callback(callback2)

        await manager.cleanup_all()

        assert callback1_executed is True
        assert callback2_executed is True

    @pytest.mark.asyncio
    async def test_cleanup_handles_errors(self):
        """Test cleanup handles resource errors gracefully."""
        manager = ResourceManager()

        resource1 = Mock()
        resource1.cleanup = AsyncMock(side_effect=Exception("Cleanup error"))
        resource2 = Mock()
        resource2.cleanup = AsyncMock()

        manager.register_resource(resource1)
        manager.register_resource(resource2)

        # Should not raise exception
        await manager.cleanup_all()

        # Both should be attempted
        resource1.cleanup.assert_called_once()
        resource2.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_already_closed(self):
        """Test cleanup when already closed."""
        manager = ResourceManager()
        manager._closed = True

        # Should return early without error
        await manager.cleanup_all()

    @pytest.mark.asyncio
    async def test_cleanup_clears_resources(self):
        """Test cleanup clears resource lists."""
        manager = ResourceManager()

        resource = Mock()
        resource.cleanup = AsyncMock()
        manager.register_resource(resource)

        await manager.cleanup_all()

        assert manager._resources == []
        assert manager._cleanup_callbacks == []


@pytest.mark.unit
class TestResourceManagerContextManager:
    """Test ResourceManager as context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test ResourceManager as async context manager."""
        async with ResourceManager() as manager:
            resource = Mock()
            resource.cleanup = AsyncMock()
            manager.register_resource(resource)

        # Resource should be cleaned up
        resource.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_with_exception(self):
        """Test context manager cleanup on exception."""
        resource = Mock()
        resource.cleanup = AsyncMock()

        try:
            async with ResourceManager() as manager:
                manager.register_resource(resource)
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # Resource should still be cleaned up
        resource.cleanup.assert_called_once()


@pytest.mark.unit
class TestManagedTemporaryFile:
    """Test ManagedTemporaryFile."""

    def test_initialization_default(self):
        """Test default initialization."""
        temp_file = ManagedTemporaryFile()

        assert temp_file.path.exists()
        assert temp_file._closed is False

    def test_initialization_with_suffix(self):
        """Test initialization with custom suffix."""
        temp_file = ManagedTemporaryFile(suffix=".txt")

        assert str(temp_file.path).endswith(".txt")

    def test_initialization_with_prefix(self):
        """Test initialization with custom prefix."""
        temp_file = ManagedTemporaryFile(prefix="test-")

        assert "test-" in temp_file.path.name

    def test_initialization_with_manager(self):
        """Test initialization with resource manager."""
        manager = ResourceManager()

        temp_file = ManagedTemporaryFile(manager=manager)

        assert temp_file in manager._resources

    @pytest.mark.asyncio
    async def test_cleanup_removes_file(self):
        """Test cleanup removes temporary file."""
        temp_file = ManagedTemporaryFile()
        file_path = temp_file.path

        await temp_file.cleanup()

        assert not file_path.exists()
        assert temp_file._closed is True

    def test_write_text(self):
        """Test writing text to temporary file."""
        temp_file = ManagedTemporaryFile()

        temp_file.write_text("test content")

        assert temp_file.read_text() == "test content"

    def test_write_text_when_closed_raises_error(self):
        """Test writing to closed file raises error."""
        temp_file = ManagedTemporaryFile()
        temp_file._closed = True

        with pytest.raises(RuntimeError, match="Cannot write to closed"):
            temp_file.write_text("content")

    def test_read_text(self):
        """Test reading text from temporary file."""
        temp_file = ManagedTemporaryFile()
        temp_file.write_text("test content")

        content = temp_file.read_text()

        assert content == "test content"


@pytest.mark.unit
class TestManagedTemporaryDirectory:
    """Test ManagedTemporaryDirectory."""

    def test_initialization_default(self):
        """Test default initialization."""
        temp_dir = ManagedTemporaryDirectory()

        assert temp_dir.path.exists()
        assert temp_dir.path.is_dir()
        assert temp_dir._closed is False

    def test_initialization_with_suffix(self):
        """Test initialization with custom suffix."""
        temp_dir = ManagedTemporaryDirectory(suffix="-test")

        assert temp_dir.path.name.endswith("-test")

    def test_initialization_with_prefix(self):
        """Test initialization with custom prefix."""
        temp_dir = ManagedTemporaryDirectory(prefix="test-")

        assert "test-" in temp_dir.path.name

    @pytest.mark.asyncio
    async def test_cleanup_removes_directory(self):
        """Test cleanup removes temporary directory."""
        temp_dir = ManagedTemporaryDirectory()
        dir_path = temp_dir.path

        # Create some files
        (dir_path / "file1.txt").write_text("content1")
        (dir_path / "file2.txt").write_text("content2")

        await temp_dir.cleanup()

        assert not dir_path.exists()
        assert temp_dir._closed is True


@pytest.mark.unit
class TestManagedProcess:
    """Test ManagedProcess."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test initialization with process."""
        mock_process = Mock()
        mock_process.returncode = None

        managed = ManagedProcess(mock_process)

        assert managed.process == mock_process
        assert managed.timeout == 30.0

    @pytest.mark.asyncio
    async def test_initialization_custom_timeout(self):
        """Test initialization with custom timeout."""
        mock_process = Mock()
        mock_process.returncode = None

        managed = ManagedProcess(mock_process, timeout=60.0)

        assert managed.timeout == 60.0

    @pytest.mark.asyncio
    async def test_cleanup_terminates_process(self):
        """Test cleanup terminates process."""
        mock_process = Mock()
        mock_process.returncode = None
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        managed = ManagedProcess(mock_process)

        await managed.cleanup()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_kills_process_on_timeout(self):
        """Test cleanup kills process if terminate times out."""
        mock_process = Mock()
        mock_process.returncode = None
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock(side_effect=TimeoutError)
        mock_process.kill = Mock()

        managed = ManagedProcess(mock_process)

        await managed.cleanup()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_skips_already_finished_process(self):
        """Test cleanup skips already finished process."""
        mock_process = Mock()
        mock_process.returncode = 0  # Already finished

        managed = ManagedProcess(mock_process)

        # Should not raise error
        await managed.cleanup()


@pytest.mark.unit
class TestManagedTask:
    """Test ManagedTask."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test initialization with task."""

        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())

        managed = ManagedTask(task)

        assert managed.task == task
        assert managed.timeout == 30.0

        task.cancel()

    @pytest.mark.asyncio
    async def test_initialization_custom_timeout(self):
        """Test initialization with custom timeout."""

        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())

        managed = ManagedTask(task, timeout=60.0)

        assert managed.timeout == 60.0

        task.cancel()

    @pytest.mark.asyncio
    async def test_cleanup_cancels_task(self):
        """Test cleanup cancels task."""

        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())

        managed = ManagedTask(task)

        await managed.cleanup()

        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_cleanup_skips_done_task(self):
        """Test cleanup skips already done task."""

        async def dummy_task():
            return "done"

        task = asyncio.create_task(dummy_task())
        await task  # Wait for completion

        managed = ManagedTask(task)

        # Should not raise error
        await managed.cleanup()


@pytest.mark.unit
class TestManagedFileHandle:
    """Test ManagedFileHandle."""

    def test_initialization(self, tmp_path):
        """Test initialization with file handle."""
        file_path = tmp_path / "test.txt"
        file_handle = file_path.open("w")

        managed = ManagedFileHandle(file_handle)

        assert managed.file_handle == file_handle

        file_handle.close()

    @pytest.mark.asyncio
    async def test_cleanup_closes_handle(self, tmp_path):
        """Test cleanup closes file handle."""
        file_path = tmp_path / "test.txt"
        file_handle = file_path.open("w")

        managed = ManagedFileHandle(file_handle)

        await managed.cleanup()

        assert file_handle.closed
        assert managed._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_skips_closed_handle(self, tmp_path):
        """Test cleanup skips already closed handle."""
        file_path = tmp_path / "test.txt"
        file_handle = file_path.open("w")
        file_handle.close()

        managed = ManagedFileHandle(file_handle)

        # Should not raise error
        await managed.cleanup()


@pytest.mark.unit
class TestResourceContext:
    """Test ResourceContext."""

    def test_initialization(self):
        """Test initialization."""
        context = ResourceContext()

        assert isinstance(context.resource_manager, ResourceManager)

    def test_managed_temp_file(self):
        """Test creating managed temp file."""
        context = ResourceContext()

        temp_file = context.managed_temp_file(suffix=".txt", prefix="test-")

        assert isinstance(temp_file, ManagedTemporaryFile)
        assert temp_file in context.resource_manager._resources

    def test_managed_temp_dir(self):
        """Test creating managed temp directory."""
        context = ResourceContext()

        temp_dir = context.managed_temp_dir(suffix="-test", prefix="test-")

        assert isinstance(temp_dir, ManagedTemporaryDirectory)
        assert temp_dir in context.resource_manager._resources

    @pytest.mark.asyncio
    async def test_managed_process(self):
        """Test creating managed process."""
        context = ResourceContext()
        mock_process = Mock()
        mock_process.returncode = None

        managed_proc = context.managed_process(mock_process, timeout=60.0)

        assert isinstance(managed_proc, ManagedProcess)
        assert managed_proc.timeout == 60.0

    @pytest.mark.asyncio
    async def test_managed_task(self):
        """Test creating managed task."""
        context = ResourceContext()

        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())

        managed_task = context.managed_task(task, timeout=60.0)

        assert isinstance(managed_task, ManagedTask)
        assert managed_task.timeout == 60.0

        task.cancel()

    def test_managed_file(self, tmp_path):
        """Test creating managed file handle."""
        context = ResourceContext()
        file_path = tmp_path / "test.txt"
        file_handle = file_path.open("w")

        managed_file = context.managed_file(file_handle)

        assert isinstance(managed_file, ManagedFileHandle)

        file_handle.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test ResourceContext as context manager."""
        temp_file = None

        async with ResourceContext() as context:
            temp_file = context.managed_temp_file()
            file_path = temp_file.path
            assert file_path.exists()

        # File should be cleaned up
        assert not file_path.exists()


@pytest.mark.unit
class TestContextManagers:
    """Test context manager functions."""

    @pytest.mark.asyncio
    async def test_with_resource_cleanup(self):
        """Test with_resource_cleanup context manager."""
        async with with_resource_cleanup() as context:
            temp_file = context.managed_temp_file()
            file_path = temp_file.path
            assert file_path.exists()

        # File should be cleaned up
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_with_temp_file(self):
        """Test with_temp_file context manager."""
        async with with_temp_file(suffix=".txt", prefix="test-") as temp_file:
            assert temp_file.path.exists()
            assert str(temp_file.path).endswith(".txt")
            file_path = temp_file.path

        # File should be cleaned up
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_with_temp_dir(self):
        """Test with_temp_dir context manager."""
        async with with_temp_dir(suffix="-test", prefix="test-") as temp_dir:
            assert temp_dir.path.exists()
            assert temp_dir.path.is_dir()
            dir_path = temp_dir.path

        # Directory should be cleaned up
        assert not dir_path.exists()

    @pytest.mark.asyncio
    async def test_with_managed_process(self):
        """Test with_managed_process context manager."""
        mock_process = Mock()
        mock_process.returncode = None
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        async with with_managed_process(mock_process, timeout=60.0) as process:
            assert process == mock_process

        # Process should be terminated
        mock_process.terminate.assert_called_once()


@pytest.mark.unit
class TestResourceLeakDetector:
    """Test ResourceLeakDetector."""

    def test_initialization(self):
        """Test initialization."""
        detector = ResourceLeakDetector()

        assert detector.open_files == set()
        assert detector.active_processes == set()
        assert detector.active_tasks == set()
        assert detector._start_time > 0

    def test_track_file(self):
        """Test tracking file."""
        detector = ResourceLeakDetector()

        detector.track_file("/path/to/file.txt")

        assert "/path/to/file.txt" in detector.open_files

    def test_untrack_file(self):
        """Test untracking file."""
        detector = ResourceLeakDetector()
        detector.track_file("/path/to/file.txt")

        detector.untrack_file("/path/to/file.txt")

        assert "/path/to/file.txt" not in detector.open_files

    def test_track_process(self):
        """Test tracking process."""
        detector = ResourceLeakDetector()

        detector.track_process(12345)

        assert 12345 in detector.active_processes

    def test_untrack_process(self):
        """Test untracking process."""
        detector = ResourceLeakDetector()
        detector.track_process(12345)

        detector.untrack_process(12345)

        assert 12345 not in detector.active_processes

    @pytest.mark.asyncio
    async def test_track_task(self):
        """Test tracking task."""
        detector = ResourceLeakDetector()

        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())

        detector.track_task(task)

        assert task in detector.active_tasks

        await task

    @pytest.mark.asyncio
    async def test_untrack_task(self):
        """Test untracking task."""
        detector = ResourceLeakDetector()

        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())
        detector.track_task(task)

        detector.untrack_task(task)

        assert task not in detector.active_tasks

        await task

    def test_get_leak_report_empty(self):
        """Test leak report with no leaks."""
        detector = ResourceLeakDetector()

        report = detector.get_leak_report()

        assert report["total_tracked_files"] == 0
        assert report["total_tracked_processes"] == 0
        assert report["total_tracked_tasks"] == 0
        assert "duration_seconds" in report

    def test_get_leak_report_with_leaks(self):
        """Test leak report with tracked resources."""
        detector = ResourceLeakDetector()
        detector.track_file("/path/to/file.txt")
        detector.track_process(12345)

        report = detector.get_leak_report()

        assert report["total_tracked_files"] == 1
        assert report["total_tracked_processes"] == 1
        assert "/path/to/file.txt" in report["open_files"]
        assert 12345 in report["active_processes"]

    def test_has_potential_leaks_false(self):
        """Test has_potential_leaks with no leaks."""
        detector = ResourceLeakDetector()

        assert detector.has_potential_leaks() is False

    def test_has_potential_leaks_true_files(self):
        """Test has_potential_leaks with open files."""
        detector = ResourceLeakDetector()
        detector.track_file("/path/to/file.txt")

        assert detector.has_potential_leaks() is True

    def test_has_potential_leaks_true_processes(self):
        """Test has_potential_leaks with active processes."""
        detector = ResourceLeakDetector()
        detector.track_process(12345)

        assert detector.has_potential_leaks() is True


@pytest.mark.unit
class TestLeakDetectionGlobalFunctions:
    """Test global leak detection functions."""

    def teardown_method(self):
        """Clean up global state after each test."""
        disable_leak_detection()

    def test_enable_leak_detection(self):
        """Test enabling leak detection."""
        detector = enable_leak_detection()

        assert detector is not None
        assert isinstance(detector, ResourceLeakDetector)
        assert get_leak_detector() == detector

    def test_get_leak_detector_when_disabled(self):
        """Test getting leak detector when disabled."""
        assert get_leak_detector() is None

    def test_disable_leak_detection_returns_report(self):
        """Test disabling leak detection returns report."""
        enable_leak_detection()
        detector = get_leak_detector()
        detector.track_file("/path/to/file.txt")

        report = disable_leak_detection()

        assert report is not None
        assert "total_tracked_files" in report
        assert report["total_tracked_files"] == 1

    def test_disable_leak_detection_when_not_enabled(self):
        """Test disabling when not enabled."""
        report = disable_leak_detection()

        assert report is None


@pytest.mark.unit
class TestGlobalResourceManagement:
    """Test global resource management."""

    @pytest.mark.asyncio
    async def test_register_global_resource_manager(self):
        """Test registering global resource manager."""
        manager = ResourceManager()

        register_global_resource_manager(manager)

        # Manager should be registered (hard to test weak references directly)

    @pytest.mark.asyncio
    async def test_cleanup_all_global_resources(self):
        """Test cleaning up all global resources."""
        manager1 = ResourceManager()
        manager2 = ResourceManager()

        resource1 = Mock()
        resource1.cleanup = AsyncMock()
        resource2 = Mock()
        resource2.cleanup = AsyncMock()

        manager1.register_resource(resource1)
        manager2.register_resource(resource2)

        register_global_resource_manager(manager1)
        register_global_resource_manager(manager2)

        await cleanup_all_global_resources()

        # Resources should be cleaned up
        resource1.cleanup.assert_called_once()
        resource2.cleanup.assert_called_once()
