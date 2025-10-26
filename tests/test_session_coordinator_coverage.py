import logging
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from acb.console import Console

from acb.depends import depends
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.task import SessionTracker


# Module-level DI context setup for SessionCoordinator testing
@pytest.fixture
def mock_console_di() -> MagicMock:
    """Mock Console for DI context."""
    return MagicMock(spec=Console)


@pytest.fixture
def session_coordinator_di_context(mock_console_di: MagicMock):
    """Set up DI context for SessionCoordinator testing."""
    injection_map = {Console: mock_console_di}

    original_values = {}
    try:
        # Register Console mock with DI
        try:
            original_values[Console] = depends.get_sync(Console)
        except Exception:
            original_values[Console] = None
        depends.set(Console, mock_console_di)

        yield injection_map, mock_console_di
    finally:
        # Restore original values after test
        if original_values[Console] is not None:
            depends.set(Console, original_values[Console])


class TestSessionCoordinator:
    @pytest.fixture
    def console(self, mock_console_di):
        """Provide console mock for tests."""
        return mock_console_di

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def coordinator(self, session_coordinator_di_context, mock_console_di, temp_dir):
        """Create SessionCoordinator with mocked Console via DI."""
        injection_map, mock_console = session_coordinator_di_context
        return SessionCoordinator(console=mock_console, pkg_path=temp_dir)

    @pytest.fixture
    def mock_options(self):
        options = Mock()
        options.track_progress = True
        return options

    @pytest.fixture
    def mock_options_no_tracking(self):
        options = Mock()
        options.track_progress = False
        return options

    def test_initialization(self, coordinator, console, temp_dir) -> None:
        assert coordinator.console == console
        assert coordinator.pkg_path == temp_dir
        assert coordinator.session_tracker is None
        assert coordinator._cleanup_handlers == []
        assert coordinator._thread_pool is None
        assert coordinator._lock_files == set()

    def test_initialize_session_tracking_enabled(
        self,
        coordinator,
        mock_options,
    ) -> None:
        with patch.object(uuid, "uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "test - session - id"
            mock_uuid.return_value.__str__ = lambda self: "test - session - id"
            mock_uuid.return_value.__getitem__ = (
                lambda self, idx: "test - session - id"[:idx]
            )

            coordinator.initialize_session_tracking(mock_options)

            assert coordinator.session_tracker is not None
            assert isinstance(coordinator.session_tracker, SessionTracker)
            coordinator.console.print.assert_called_with(
                "[cyan]📊[/ cyan] Session tracking enabled",
            )

    def test_initialize_session_tracking_disabled(
        self,
        coordinator,
        mock_options_no_tracking,
    ) -> None:
        coordinator.initialize_session_tracking(mock_options_no_tracking)

        assert coordinator.session_tracker is None
        coordinator.console.print.assert_not_called()

    def test_track_task_with_tracker(self, coordinator) -> None:
        mock_tracker = Mock(spec=SessionTracker)
        coordinator.session_tracker = mock_tracker

        coordinator.track_task("task_1", "Test Task")

        mock_tracker.start_task.assert_called_once_with("task_1", "Test Task")

    def test_track_task_without_tracker(self, coordinator) -> None:
        coordinator.session_tracker = None

        coordinator.track_task("task_1", "Test Task")

    def test_complete_task_with_tracker(self, coordinator) -> None:
        mock_tracker = Mock(spec=SessionTracker)
        coordinator.session_tracker = mock_tracker

        coordinator.complete_task("task_1", details="Task completed successfully")

        mock_tracker.complete_task.assert_called_once_with(
            "task_1",
            details="Task completed successfully",
        )

    def test_complete_task_without_tracker(self, coordinator) -> None:
        coordinator.session_tracker = None

        coordinator.complete_task("task_1", details="Task completed")

    def test_complete_task_no_details(self, coordinator) -> None:
        mock_tracker = Mock(spec=SessionTracker)
        coordinator.session_tracker = mock_tracker

        coordinator.complete_task("task_1")

        mock_tracker.complete_task.assert_called_once_with("task_1", details=None)

    def test_fail_task_with_tracker(self, coordinator) -> None:
        mock_tracker = Mock(spec=SessionTracker)
        coordinator.session_tracker = mock_tracker

        coordinator.fail_task("task_1", "Task failed due to error")

        mock_tracker.fail_task.assert_called_once_with(
            "task_1",
            "Task failed due to error",
        )

    def test_fail_task_without_tracker(self, coordinator) -> None:
        coordinator.session_tracker = None

        coordinator.fail_task("task_1", "Error occurred")

    def test_get_session_summary_with_tracker(self, coordinator) -> None:
        mock_tracker = Mock(spec=SessionTracker)
        mock_tracker.get_summary.return_value = {"completed": 5, "failed": 1}
        coordinator.session_tracker = mock_tracker

        result = coordinator.get_session_summary()

        assert result == {"completed": 5, "failed": 1}
        mock_tracker.get_summary.assert_called_once()

    def test_get_session_summary_without_tracker(self, coordinator) -> None:
        coordinator.session_tracker = None

        result = coordinator.get_session_summary()

        assert result is None

    def test_finalize_session_success(self, coordinator) -> None:
        start_time = time.time() - 10.0

        with patch.object(coordinator, "complete_task") as mock_complete:
            coordinator.finalize_session(start_time, success=True)

            mock_complete.assert_called_once()
            call_args = mock_complete.call_args
            assert call_args[0][0] == "workflow"
            assert "Completed successfully" in call_args[0][1]
            assert "10." in call_args[0][1]

    def test_finalize_session_failure(self, coordinator) -> None:
        start_time = time.time() - 5.0

        with patch.object(coordinator, "complete_task") as mock_complete:
            coordinator.finalize_session(start_time, success=False)

            mock_complete.assert_called_once()
            call_args = mock_complete.call_args
            assert call_args[0][0] == "workflow"
            assert "Completed with issues" in call_args[0][1]
            assert "5." in call_args[0][1]

    def test_register_cleanup(self, coordinator) -> None:
        cleanup_handler = Mock()

        coordinator.register_cleanup(cleanup_handler)

        assert cleanup_handler in coordinator._cleanup_handlers
        assert len(coordinator._cleanup_handlers) == 1

    def test_register_multiple_cleanup_handlers(self, coordinator) -> None:
        handler1 = Mock()
        handler2 = Mock()

        coordinator.register_cleanup(handler1)
        coordinator.register_cleanup(handler2)

        assert len(coordinator._cleanup_handlers) == 2
        assert handler1 in coordinator._cleanup_handlers
        assert handler2 in coordinator._cleanup_handlers

    def test_track_lock_file(self, coordinator, temp_dir) -> None:
        lock_file = temp_dir / "test.lock"

        coordinator.track_lock_file(lock_file)

        assert lock_file in coordinator._lock_files
        assert len(coordinator._lock_files) == 1

    def test_track_multiple_lock_files(self, coordinator, temp_dir) -> None:
        lock_file1 = temp_dir / "test1.lock"
        lock_file2 = temp_dir / "test2.lock"

        coordinator.track_lock_file(lock_file1)
        coordinator.track_lock_file(lock_file2)

        assert len(coordinator._lock_files) == 2
        assert lock_file1 in coordinator._lock_files
        assert lock_file2 in coordinator._lock_files

    def test_cleanup_resources_calls_handlers(self, coordinator) -> None:
        handler1 = Mock()
        handler2 = Mock()
        coordinator._cleanup_handlers = [handler1, handler2]

        with patch.object(coordinator, "_cleanup_temporary_files"):
            coordinator.cleanup_resources()

            handler1.assert_called_once()
            handler2.assert_called_once()

    def test_cleanup_resources_handles_handler_exceptions(self, coordinator) -> None:
        handler1 = Mock(side_effect=Exception("Handler failed"))
        handler2 = Mock()
        coordinator._cleanup_handlers = [handler1, handler2]

        with patch.object(coordinator, "_cleanup_temporary_files"):
            coordinator.cleanup_resources()

            handler1.assert_called_once()
            handler2.assert_called_once()

    def test_cleanup_resources_calls_temporary_file_cleanup(self, coordinator) -> None:
        with patch.object(coordinator, "_cleanup_temporary_files") as mock_cleanup:
            coordinator.cleanup_resources()

            mock_cleanup.assert_called_once()

    def test_cleanup_temporary_files_no_config(self, coordinator) -> None:
        coordinator._cleanup_config = None

        with (
            patch.object(coordinator, "_cleanup_debug_logs") as mock_debug,
            patch.object(coordinator, "_cleanup_coverage_files") as mock_coverage,
        ):
            coordinator._cleanup_temporary_files()

            mock_debug.assert_called_once_with()
            mock_coverage.assert_called_once_with()

    def test_cleanup_temporary_files_with_config_disabled(self, coordinator) -> None:
        mock_config = Mock()
        mock_config.auto_cleanup = False
        coordinator._cleanup_config = mock_config

        with (
            patch.object(coordinator, "_cleanup_debug_logs") as mock_debug,
            patch.object(coordinator, "_cleanup_coverage_files") as mock_coverage,
        ):
            coordinator._cleanup_temporary_files()

            mock_debug.assert_not_called()
            mock_coverage.assert_not_called()

    def test_cleanup_temporary_files_with_config_enabled(self, coordinator) -> None:
        mock_config = Mock()
        mock_config.auto_cleanup = True
        mock_config.keep_debug_logs = 3
        mock_config.keep_coverage_files = 7
        coordinator._cleanup_config = mock_config

        with (
            patch.object(coordinator, "_cleanup_debug_logs") as mock_debug,
            patch.object(coordinator, "_cleanup_coverage_files") as mock_coverage,
        ):
            coordinator._cleanup_temporary_files()

            mock_debug.assert_called_once_with(keep_recent=3)
            mock_coverage.assert_called_once_with(keep_recent=7)

    def test_set_cleanup_config(self, coordinator) -> None:
        mock_config = Mock()
        mock_config.auto_cleanup = True

        coordinator.set_cleanup_config(mock_config)

        assert coordinator._cleanup_config == mock_config

    def test_cleanup_debug_logs_no_files(self, coordinator, temp_dir) -> None:
        coordinator._cleanup_debug_logs(keep_recent=5)

    def test_cleanup_debug_logs_with_files(self, coordinator, temp_dir) -> None:
        debug_files = []
        for i in range(8):
            debug_file = temp_dir / f"crackerjack - debug -{i: 03d}.log"
            debug_file.write_text(f"Debug log {i}")
            debug_files.append(debug_file)

            time.sleep(0.01)

        coordinator._cleanup_debug_logs(keep_recent=3)

        remaining_files = list(temp_dir.glob("crackerjack - debug - *.log"))
        assert len(remaining_files) == 3

        for debug_file in debug_files[-3:]:
            assert debug_file.exists()

    def test_cleanup_debug_logs_handles_permission_error(
        self,
        coordinator,
        temp_dir,
    ) -> None:
        debug_file = temp_dir / "crackerjack - debug - 001.log"
        debug_file.write_text("Debug log")

        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
            coordinator._cleanup_debug_logs(keep_recent=0)

    def test_cleanup_coverage_files_no_files(self, coordinator, temp_dir) -> None:
        coordinator._cleanup_coverage_files(keep_recent=10)

    def test_cleanup_coverage_files_with_files(self, coordinator, temp_dir) -> None:
        coverage_files = []
        for i in range(15):
            coverage_file = temp_dir / f".coverage.{i: 03d}"
            coverage_file.write_text(f"Coverage data {i}")
            coverage_files.append(coverage_file)

            time.sleep(0.01)

        coordinator._cleanup_coverage_files(keep_recent=5)

        remaining_files = list(temp_dir.glob(".coverage.*"))
        assert len(remaining_files) == 5

        for coverage_file in coverage_files[-5:]:
            assert coverage_file.exists()

    def test_cleanup_coverage_files_handles_file_not_found_error(
        self,
        coordinator,
        temp_dir,
    ) -> None:
        coverage_file = temp_dir / ".coverage.001"
        coverage_file.write_text("Coverage data")

        with patch.object(
            Path,
            "unlink",
            side_effect=FileNotFoundError("File not found"),
        ):
            coordinator._cleanup_coverage_files(keep_recent=0)

    def test_setup_logging_no_existing_handlers(self, coordinator) -> None:
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_logger.handlers = []
            mock_get_logger.return_value = mock_logger

            coordinator._setup_logging()

            mock_get_logger.assert_called_with("crackerjack")
            mock_logger.addHandler.assert_called_once()
            mock_logger.setLevel.assert_called_with(logging.WARNING)

    def test_setup_logging_with_existing_handlers(self, coordinator) -> None:
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_logger.handlers = [Mock()]
            mock_get_logger.return_value = mock_logger

            coordinator._setup_logging()

            mock_get_logger.assert_called_with("crackerjack")
            mock_logger.addHandler.assert_not_called()
            mock_logger.setLevel.assert_not_called()


class TestSessionCoordinatorIntegration:
    @pytest.fixture
    def console(self):
        return Console()

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_full_session_workflow(self, console, temp_dir) -> None:
        coordinator = SessionCoordinator(console=console, pkg_path=temp_dir)

        options = Mock()
        options.track_progress = True

        coordinator.initialize_session_tracking(options)
        assert coordinator.session_tracker is not None

        coordinator.track_task("setup", "Setup Environment")
        coordinator.track_task("build", "Build Project")

        coordinator.complete_task("setup", "Environment ready")
        coordinator.complete_task("build", "Build successful")

        summary = coordinator.get_session_summary()
        assert summary is not None

        start_time = time.time() - 5.0
        coordinator.finalize_session(start_time, success=True)

    def test_cleanup_workflow_with_real_files(self, console, temp_dir) -> None:
        coordinator = SessionCoordinator(console=console, pkg_path=temp_dir)

        for i in range(10):
            debug_file = temp_dir / f"crackerjack - debug -{i: 03d}.log"
            debug_file.write_text(f"Debug log {i}")

            coverage_file = temp_dir / f".coverage.{i: 03d}"
            coverage_file.write_text(f"Coverage data {i}")

        mock_config = Mock()
        mock_config.auto_cleanup = True
        mock_config.keep_debug_logs = 3
        mock_config.keep_coverage_files = 5
        coordinator.set_cleanup_config(mock_config)

        cleanup_called = []

        def test_cleanup() -> None:
            cleanup_called.append(True)

        coordinator.register_cleanup(test_cleanup)

        coordinator.cleanup_resources()

        assert len(cleanup_called) == 1

        debug_files = list(temp_dir.glob("crackerjack - debug - *.log"))
        coverage_files = list(temp_dir.glob(".coverage.*"))

        assert len(debug_files) == 3
        assert len(coverage_files) == 5
