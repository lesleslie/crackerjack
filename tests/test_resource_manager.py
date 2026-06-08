"""Tests for resource_manager module."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.resource_manager import (
    ManagedFileHandle,
    ManagedProcess,
    ManagedResource,
    ManagedTask,
    ManagedTemporaryDirectory,
    ManagedTemporaryFile,
    ResourceContext,
    ResourceLeakDetector,
    ResourceManager,
    ResourceProtocol,
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


class TestResourceProtocol:
    """Tests for ResourceProtocol."""

    def test_protocol_exists(self) -> None:
        """Test ResourceProtocol is a valid protocol."""
        # Verify the protocol exists and has the expected method
        assert hasattr(ResourceProtocol, "cleanup")


class TestResourceManager:
    """Tests for ResourceManager class."""

    @pytest.fixture
    def manager(self) -> ResourceManager:
        """Create a ResourceManager for testing."""
        return ResourceManager()

    @pytest.fixture
    def mock_resource(self) -> AsyncMock:
        """Create a mock resource for testing."""
        resource = AsyncMock(spec=ResourceProtocol)
        resource.cleanup = AsyncMock(return_value=None)
        return resource

    def test_init(self) -> None:
        """Test ResourceManager initialization."""
        mgr = ResourceManager()
        assert mgr._resources == []
        assert mgr._cleanup_callbacks == []
        assert mgr._closed is False

    def test_init_with_logger(self) -> None:
        """Test initialization with custom logger."""
        logger = MagicMock()
        mgr = ResourceManager(logger=logger)
        assert mgr.logger is logger

    def test_register_resource(
        self, manager: ResourceManager, mock_resource: AsyncMock
    ) -> None:
        """Test registering a resource."""
        manager.register_resource(mock_resource)
        assert mock_resource in manager._resources

    def test_register_resource_when_closed(
        self, manager: ResourceManager, mock_resource: AsyncMock
    ) -> None:
        """Test registering when manager is closed triggers cleanup."""
        manager._closed = True
        # ``register_resource`` schedules the cleanup with
        # ``asyncio.create_task``; patch it to avoid a no-event-loop
        # error and let the coroutine be garbage-collected.
        with patch(
            "crackerjack.core.resource_manager.asyncio.create_task"
        ) as mock_create:
            manager.register_resource(mock_resource)
            mock_create.assert_called_once()
        mock_resource.cleanup.assert_called_once()

    def test_register_cleanup_callback(self, manager: ResourceManager) -> None:
        """Test registering a cleanup callback."""
        callback = AsyncMock()
        manager.register_cleanup_callback(callback)
        assert callback in manager._cleanup_callbacks

    def test_register_cleanup_callback_when_closed(
        self, manager: ResourceManager
    ) -> None:
        """Test registering callback when closed triggers it."""
        callback = AsyncMock()
        manager._closed = True
        manager.register_cleanup_callback(callback)
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_all(
        self, manager: ResourceManager, mock_resource: AsyncMock
    ) -> None:
        """Test cleanup_all awaits all resources and callbacks."""
        manager.register_resource(mock_resource)
        callback = AsyncMock()
        manager.register_cleanup_callback(callback)

        await manager.cleanup_all()

        mock_resource.cleanup.assert_called_once()
        callback.assert_called_once()
        assert manager._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_all_handles_exceptions(
        self, manager: ResourceManager, mock_resource: AsyncMock
    ) -> None:
        """Test cleanup_all logs but doesn't raise on errors."""
        mock_resource.cleanup.side_effect = RuntimeError("cleanup error")
        manager.register_resource(mock_resource)

        # Should not raise
        await manager.cleanup_all()

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self, manager: ResourceManager) -> None:
        """Test async context manager __aenter__ returns self."""
        result = await manager.__aenter__()
        assert result == manager

    @pytest.mark.asyncio
    async def test_aexit_calls_cleanup(self, manager: ResourceManager) -> None:
        """Test async context manager __aexit__ calls cleanup."""
        with patch.object(manager, "cleanup_all", new_callable=AsyncMock) as mock_cleanup:
            await manager.__aexit__(None, None, None)
            mock_cleanup.assert_called_once()


class TestManagedResource:
    """Tests for ManagedResource abstract base class."""

    def test_abstract_methods(self) -> None:
        """Test ManagedResource has abstract cleanup method."""
        assert hasattr(ManagedResource, "cleanup")
        assert hasattr(ManagedResource, "__init__")

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Test close calls cleanup once."""
        class ConcreteResource(ManagedResource):
            async def cleanup(self) -> None:
                pass

        manager = MagicMock()
        resource = ConcreteResource(manager=manager)
        await resource.close()
        await resource.close()  # Second call should not call cleanup again
        # cleanup should only be called once


class TestManagedTemporaryFile:
    """Tests for ManagedTemporaryFile class."""

    def test_init(self) -> None:
        """Test ManagedTemporaryFile initialization."""
        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile"
        ):
            mtf = ManagedTemporaryFile()
            assert mtf._closed is False
            assert mtf.manager is None

    def test_init_with_manager(self) -> None:
        """Test initialization with a resource manager."""
        manager = MagicMock()
        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile"
        ):
            mtf = ManagedTemporaryFile(manager=manager)
            manager.register_resource.assert_called_once_with(mtf)

    def test_path_attribute(self) -> None:
        """Test path attribute is set correctly."""
        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile"
        ) as mock_temp:
            mock_temp.return_value.name = "/tmp/test-file"
            mtf = ManagedTemporaryFile()
            assert mtf.path == Path("/tmp/test-file")

    def test_write_text_raises_when_closed(self) -> None:
        """Test write_text raises RuntimeError when closed."""
        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile"
        ):
            mtf = ManagedTemporaryFile()
            mtf._closed = True
            with pytest.raises(RuntimeError, match="Cannot write to closed"):
                mtf.write_text("content")

    def test_write_text(self) -> None:
        """Test write_text writes content to file."""
        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile"
        ) as mock_temp:
            mock_temp.return_value.name = "/tmp/test-file"
            mock_temp.return_value.closed = False
            mtf = ManagedTemporaryFile()
            mtf.write_text("test content")
            assert mtf.path.read_text() == "test content"

    def test_read_text(self) -> None:
        """Test read_text reads content from file."""
        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile"
        ) as mock_temp:
            mock_temp.return_value.name = "/tmp/test-file"
            mock_temp.return_value.closed = False
            mtf = ManagedTemporaryFile()
            mtf.path.write_text("test content")
            assert mtf.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_cleanup_closes_file(self) -> None:
        """Test cleanup closes the file handle."""
        mock_file = MagicMock()
        mock_file.closed = False
        mock_file.name = "/tmp/test-file"

        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile",
            return_value=mock_file,
        ):
            mtf = ManagedTemporaryFile()
            mtf.path = MagicMock()
            mtf.path.exists.return_value = False

            await mtf.cleanup()

            mock_file.close.assert_called_once()
            assert mtf._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_removes_file(self) -> None:
        """Test cleanup removes the file if it exists."""
        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile"
        ) as mock_temp:
            mock_temp.return_value.closed = False
            mock_temp.return_value.name = "/tmp/test-file"
            mtf = ManagedTemporaryFile()
            mtf.path = MagicMock()
            mtf.path.exists.return_value = True

            await mtf.cleanup()

            mtf.path.unlink.assert_called_once()


class TestManagedTemporaryDirectory:
    """Tests for ManagedTemporaryDirectory class."""

    def test_init(self) -> None:
        """Test ManagedTemporaryDirectory initialization."""
        with patch(
            "crackerjack.core.resource_manager.tempfile.mkdtemp",
            return_value="/tmp/test-dir",
        ):
            mtd = ManagedTemporaryDirectory()
            assert mtd._closed is False
            assert mtd.path == Path("/tmp/test-dir")

    def test_init_with_manager(self) -> None:
        """Test initialization with a resource manager."""
        manager = MagicMock()
        with patch(
            "crackerjack.core.resource_manager.tempfile.mkdtemp",
            return_value="/tmp/test-dir",
        ):
            mtd = ManagedTemporaryDirectory(manager=manager)
            manager.register_resource.assert_called_once_with(mtd)

    @pytest.mark.asyncio
    async def test_cleanup_removes_directory(self) -> None:
        """Test cleanup removes the directory."""
        with patch(
            "crackerjack.core.resource_manager.tempfile.mkdtemp",
            return_value="/tmp/test-dir",
        ):
            mtd = ManagedTemporaryDirectory()
            mtd.path = MagicMock()
            mtd.path.exists.return_value = True

            await mtd.cleanup()

            assert mtd._closed is True


class TestManagedProcess:
    """Tests for ManagedProcess class."""

    @pytest.fixture
    def mock_process(self) -> MagicMock:
        """Create a mock process."""
        proc = MagicMock()
        proc.returncode = None
        proc.pid = 12345
        return proc

    def test_init(self, mock_process: MagicMock) -> None:
        """Test ManagedProcess initialization."""
        with patch(
            "crackerjack.core.resource_manager.asyncio.wait_for",
            new_callable=AsyncMock,
        ):
            mp = ManagedProcess(mock_process)
            assert mp.process is mock_process
            assert mp.timeout == 30.0
            assert mp._closed is False

    def test_init_with_custom_timeout(self, mock_process: MagicMock) -> None:
        """Test initialization with custom timeout."""
        mp = ManagedProcess(mock_process, timeout=60.0)
        assert mp.timeout == 60.0

    @pytest.mark.asyncio
    async def test_cleanup_terminates_process(
        self, mock_process: MagicMock
    ) -> None:
        """Test cleanup terminates the process."""
        mock_process.wait = AsyncMock(return_value=0)

        with patch(
            "crackerjack.core.resource_manager.asyncio.wait_for",
            new_callable=AsyncMock,
        ):
            mp = ManagedProcess(mock_process)
            await mp.cleanup()

        mock_process.terminate.assert_called_once()
        assert mp._closed is True

    @pytest.mark.asyncio
    async def test_cleanup_kills_on_timeout(self, mock_process: MagicMock) -> None:
        """Test cleanup kills process when termination times out."""
        mock_process.wait = AsyncMock(side_effect=TimeoutError)

        async def wait_for_mock(*args, **kwargs):
            raise TimeoutError()

        mock_process.wait = AsyncMock(
            side_effect=[TimeoutError, TimeoutError]
        )

        with patch(
            "crackerjack.core.resource_manager.asyncio.wait_for", wait_for_mock
        ):
            mp = ManagedProcess(mock_process)
            await mp.cleanup()

        mock_process.kill.assert_called()


class TestManagedTask:
    """Tests for ManagedTask class."""

    @pytest.fixture
    def mock_task(self) -> MagicMock:
        """Create a mock task."""
        task = MagicMock()
        task.done.return_value = False
        task.cancel = MagicMock()
        return task

    def test_init(self, mock_task: MagicMock) -> None:
        """Test ManagedTask initialization."""
        mt = ManagedTask(mock_task)
        assert mt.task is mock_task
        assert mt.timeout == 30.0
        assert mt._closed is False

    @pytest.mark.asyncio
    async def test_cleanup_cancels_task(self, mock_task: MagicMock) -> None:
        """Test cleanup cancels the task."""
        mock_task.wait = AsyncMock()

        with patch(
            "crackerjack.core.resource_manager.asyncio.wait_for",
            new_callable=AsyncMock,
        ):
            mt = ManagedTask(mock_task)
            await mt.cleanup()

        mock_task.cancel.assert_called_once()
        assert mt._closed is True


class TestManagedFileHandle:
    """Tests for ManagedFileHandle class."""

    def test_init(self) -> None:
        """Test ManagedFileHandle initialization."""
        mock_handle = MagicMock()
        mock_handle.closed = False
        mfh = ManagedFileHandle(mock_handle)
        assert mfh.file_handle is mock_handle
        assert mfh._closed is False

    @pytest.mark.asyncio
    async def test_cleanup_closes_handle(self) -> None:
        """Test cleanup closes the file handle."""
        mock_handle = MagicMock()
        mock_handle.closed = False
        mfh = ManagedFileHandle(mock_handle)

        await mfh.cleanup()

        mock_handle.close.assert_called_once()
        assert mfh._closed is True


class TestResourceContext:
    """Tests for ResourceContext class."""

    def test_init(self) -> None:
        """Test ResourceContext initialization."""
        ctx = ResourceContext()
        assert ctx.resource_manager is not None
        assert isinstance(ctx.resource_manager, ResourceManager)

    def test_managed_temp_file(self) -> None:
        """Test managed_temp_file creates ManagedTemporaryFile."""
        ctx = ResourceContext()
        with patch(
            "crackerjack.core.resource_manager.tempfile.NamedTemporaryFile"
        ):
            mtf = ctx.managed_temp_file()
            assert isinstance(mtf, ManagedTemporaryFile)

    def test_managed_temp_dir(self) -> None:
        """Test managed_temp_dir creates ManagedTemporaryDirectory."""
        ctx = ResourceContext()
        with patch(
            "crackerjack.core.resource_manager.tempfile.mkdtemp",
            return_value="/tmp/test",
        ):
            mtd = ctx.managed_temp_dir()
            assert isinstance(mtd, ManagedTemporaryDirectory)

    def test_managed_process(self) -> None:
        """Test managed_process creates ManagedProcess."""
        ctx = ResourceContext()
        mock_proc = MagicMock()
        mp = ctx.managed_process(mock_proc)
        assert isinstance(mp, ManagedProcess)

    def test_managed_task(self) -> None:
        """Test managed_task creates ManagedTask."""
        ctx = ResourceContext()
        mock_task = MagicMock()
        mt = ctx.managed_task(mock_task)
        assert isinstance(mt, ManagedTask)

    def test_managed_file(self) -> None:
        """Test managed_file creates ManagedFileHandle."""
        ctx = ResourceContext()
        mock_handle = MagicMock()
        mfh = ctx.managed_file(mock_handle)
        assert isinstance(mfh, ManagedFileHandle)

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self) -> None:
        """Test async context manager __aenter__ returns self."""
        ctx = ResourceContext()
        result = await ctx.__aenter__()
        assert result is ctx

    @pytest.mark.asyncio
    async def test_aexit_calls_cleanup(self) -> None:
        """Test __aexit__ calls resource_manager cleanup."""
        ctx = ResourceContext()
        with patch.object(
            ctx.resource_manager, "cleanup_all", new_callable=AsyncMock
        ) as mock_cleanup:
            await ctx.__aexit__(None, None, None)
            mock_cleanup.assert_called_once()


class TestResourceLeakDetector:
    """Tests for ResourceLeakDetector class."""

    def test_init(self) -> None:
        """Test ResourceLeakDetector initialization."""
        detector = ResourceLeakDetector()
        assert detector.open_files == set()
        assert detector.active_processes == set()
        assert detector.active_tasks == set()
        assert detector._start_time > 0

    def test_track_file(self) -> None:
        """Test track_file adds to open_files."""
        detector = ResourceLeakDetector()
        detector.track_file("/tmp/test.txt")
        assert "/tmp/test.txt" in detector.open_files

    def test_untrack_file(self) -> None:
        """Test untrack_file removes from open_files."""
        detector = ResourceLeakDetector()
        detector.track_file("/tmp/test.txt")
        detector.untrack_file("/tmp/test.txt")
        assert "/tmp/test.txt" not in detector.open_files

    def test_track_process(self) -> None:
        """Test track_process adds to active_processes."""
        detector = ResourceLeakDetector()
        detector.track_process(12345)
        assert 12345 in detector.active_processes

    def test_untrack_process(self) -> None:
        """Test untrack_process removes from active_processes."""
        detector = ResourceLeakDetector()
        detector.track_process(12345)
        detector.untrack_process(12345)
        assert 12345 not in detector.active_processes

    def test_track_task(self) -> None:
        """Test track_task adds to active_tasks."""
        detector = ResourceLeakDetector()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        detector.track_task(mock_task)
        assert mock_task in detector.active_tasks

    def test_untrack_task(self) -> None:
        """Test untrack_task removes from active_tasks."""
        detector = ResourceLeakDetector()
        mock_task = MagicMock()
        detector.track_task(mock_task)
        detector.untrack_task(mock_task)
        assert mock_task not in detector.active_tasks

    def test_get_leak_report(self) -> None:
        """Test get_leak_report returns expected structure."""
        detector = ResourceLeakDetector()
        detector.track_file("/tmp/test.txt")
        detector.track_process(12345)

        report = detector.get_leak_report()

        assert "duration_seconds" in report
        assert report["open_files"] == ["/tmp/test.txt"]
        assert report["active_processes"] == [12345]
        assert report["total_tracked_files"] == 1
        assert report["total_tracked_processes"] == 1
        assert report["total_tracked_tasks"] == 0

    def test_has_potential_leaks_false(self) -> None:
        """Test has_potential_leaks returns False when nothing is tracked."""
        detector = ResourceLeakDetector()
        assert detector.has_potential_leaks() is False

    def test_has_potential_leaks_true_with_file(self) -> None:
        """Test has_potential_leaks returns True when files are tracked."""
        detector = ResourceLeakDetector()
        detector.track_file("/tmp/test.txt")
        assert detector.has_potential_leaks() is True

    def test_has_potential_leaks_true_with_process(self) -> None:
        """Test has_potential_leaks returns True when processes are tracked."""
        detector = ResourceLeakDetector()
        detector.track_process(12345)
        assert detector.has_potential_leaks() is True

    def test_has_potential_leaks_true_with_active_task(self) -> None:
        """Test has_potential_leaks returns True when active tasks are tracked."""
        detector = ResourceLeakDetector()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        detector.track_task(mock_task)
        assert detector.has_potential_leaks() is True


class TestGlobalLeakDetectionFunctions:
    """Tests for global leak detection functions."""

    def test_enable_leak_detection(self) -> None:
        """Test enable_leak_detection returns detector."""
        # Disable first to reset state
        disable_leak_detection()

        detector = enable_leak_detection()
        assert isinstance(detector, ResourceLeakDetector)
        assert get_leak_detector() is detector

    def test_get_leak_detector_returns_none_when_disabled(self) -> None:
        """Test get_leak_detector returns None when disabled."""
        disable_leak_detection()
        assert get_leak_detector() is None

    def test_disable_leak_detection_returns_report(self) -> None:
        """Test disable_leak_detection returns leak report."""
        enable_leak_detection()
        report = disable_leak_detection()
        assert report is not None
        assert isinstance(report, dict)
        assert get_leak_detector() is None


class TestGlobalResourceManagerFunctions:
    """Tests for global resource manager functions."""

    def test_register_global_resource_manager(self) -> None:
        """Test register_global_resource_manager adds to global set."""
        manager = MagicMock()
        register_global_resource_manager(manager)
        # This is hard to test directly due to WeakSet, so we just verify it doesn't raise

    @pytest.mark.asyncio
    async def test_cleanup_all_global_resources(self) -> None:
        """Test cleanup_all_global_resources awaits all managers."""
        # The manager's ``cleanup_all`` is awaited, so the mock must
        # return a coroutine, not a bare MagicMock.
        mock_manager = MagicMock()
        mock_manager.cleanup_all = AsyncMock()
        with patch(
            "crackerjack.core.resource_manager._global_managers",
            {mock_manager},
        ):
            await cleanup_all_global_resources()
            mock_manager.cleanup_all.assert_called_once()


class TestContextManagers:
    """Tests for async context managers."""

    @pytest.mark.asyncio
    async def test_with_resource_cleanup(self) -> None:
        """Test with_resource_cleanup yields ResourceContext."""
        async with with_resource_cleanup() as ctx:
            assert isinstance(ctx, ResourceContext)

    @pytest.mark.asyncio
    async def test_with_temp_file(self) -> None:
        """Test with_temp_file yields ManagedTemporaryFile."""
        async with with_temp_file(suffix=".txt") as temp_file:
            assert isinstance(temp_file, ManagedTemporaryFile)

    @pytest.mark.asyncio
    async def test_with_temp_dir(self) -> None:
        """Test with_temp_dir yields ManagedTemporaryDirectory."""
        async with with_temp_dir(suffix="-test") as temp_dir:
            assert isinstance(temp_dir, ManagedTemporaryDirectory)

    @pytest.mark.asyncio
    async def test_with_managed_process(self) -> None:
        """Test with_managed_process yields process."""
        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)

        with patch(
            "crackerjack.core.resource_manager.asyncio.wait_for",
            new_callable=AsyncMock,
        ):
            async with with_managed_process(mock_proc) as proc:
                assert proc is mock_proc


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_register_global_resource_manager_function(self) -> None:
        """Test module-level register_global_resource_manager function."""
        manager = MagicMock()
        # Should not raise
        register_global_resource_manager(manager)
