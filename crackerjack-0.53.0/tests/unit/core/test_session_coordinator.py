"""Unit tests for session coordinator components."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.task import SessionTracker


class TestSessionCoordinatorInitialization:
    """Test SessionCoordinator initialization."""

    def test_initialization_defaults(self) -> None:
        """Test SessionCoordinator initialization with defaults."""
        coordinator = SessionCoordinator()

        assert isinstance(coordinator.console, CrackerjackConsole)
        assert coordinator.pkg_path == Path.cwd()
        assert coordinator.session_id is not None
        assert len(coordinator.session_id) >= 8
        assert isinstance(coordinator.start_time, float)
        assert coordinator.cleanup_handlers == []
        assert coordinator.lock_files == set()
        assert coordinator.current_task is None
        assert coordinator.session_tracker is None
        assert coordinator.tasks == {}

    def test_initialization_with_parameters(self) -> None:
        """Test SessionCoordinator initialization with parameters."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")
        web_job_id = "test-job-123"

        coordinator = SessionCoordinator(
            console=console,
            pkg_path=pkg_path,
            web_job_id=web_job_id,
        )

        assert coordinator.console is console
        assert coordinator.pkg_path == pkg_path
        assert coordinator.web_job_id == web_job_id
        assert coordinator.session_id == web_job_id


class TestSessionCoordinatorSessionTracking:
    """Test session tracking functionality."""

    def test_initialize_session_tracking_without_tracking(self) -> None:
        """Test initialize_session_tracking when tracking is disabled."""
        coordinator = SessionCoordinator()
        options = MagicMock()
        options.track_progress = False

        coordinator.initialize_session_tracking(options)

        # Session tracker should remain None when tracking is disabled
        assert coordinator.session_tracker is None

    def test_initialize_session_tracking_with_tracking(self) -> None:
        """Test initialize_session_tracking when tracking is enabled."""
        coordinator = SessionCoordinator()
        options = MagicMock()
        options.track_progress = True

        coordinator.initialize_session_tracking(options)

        # Session tracker should be initialized when tracking is enabled
        assert coordinator.session_tracker is not None
        assert isinstance(coordinator.session_tracker, SessionTracker)
        assert coordinator.session_tracker.session_id == coordinator.session_id
        assert coordinator.session_tracker.start_time == coordinator.start_time

    def test_start_session(self) -> None:
        """Test start_session method."""
        coordinator = SessionCoordinator()
        task_name = "test_task"

        coordinator.start_session(task_name)

        assert coordinator.current_task == task_name
        assert coordinator.session_tracker is not None
        assert coordinator.session_tracker.metadata["current_session"] == task_name

    def test_start_session_creates_tracker_if_none(self) -> None:
        """Test start_session creates tracker if none exists."""
        coordinator = SessionCoordinator()
        coordinator.session_tracker = None
        task_name = "test_task"

        coordinator.start_session(task_name)

        assert coordinator.session_tracker is not None
        assert coordinator.session_tracker.metadata["current_session"] == task_name

    def test_end_session(self) -> None:
        """Test end_session method."""
        coordinator = SessionCoordinator()
        success = True

        coordinator.end_session(success)

        # Check that end_time is set and metadata is updated
        assert hasattr(coordinator, 'end_time')
        assert isinstance(coordinator.end_time, float)
        if coordinator.session_tracker:
            assert coordinator.session_tracker.metadata["completed_at"] == coordinator.end_time
            assert coordinator.session_tracker.metadata["success"] == success

    def test_end_session_with_tracker(self) -> None:
        """Test end_session method with existing tracker."""
        coordinator = SessionCoordinator()
        coordinator.session_tracker = SessionTracker(
            session_id=coordinator.session_id,
            start_time=coordinator.start_time,
        )
        success = False

        coordinator.end_session(success)

        assert coordinator.session_tracker.metadata["success"] == success
        assert coordinator.current_task is None


class TestSessionCoordinatorTaskTracking:
    """Test task tracking functionality."""

    def test_track_task(self) -> None:
        """Test track_task method."""
        coordinator = SessionCoordinator()
        task_id = "task-123"
        task_name = "test-task"
        details = "Test task details"

        result_id = coordinator.track_task(task_id, task_name, details)

        assert result_id == task_id
        assert coordinator.session_tracker is not None
        assert task_id in coordinator.session_tracker.tasks

    def test_track_task_creates_tracker_if_none(self) -> None:
        """Test track_task creates tracker if none exists."""
        coordinator = SessionCoordinator()
        coordinator.session_tracker = None

        coordinator.track_task("task-123", "test-task", "details")

        assert coordinator.session_tracker is not None

    def test_complete_task(self) -> None:
        """Test complete_task method."""
        coordinator = SessionCoordinator()
        task_id = "task-456"
        details = "Completion details"
        files_changed = ["file1.py", "file2.py"]

        # First track the task
        coordinator.track_task(task_id, "test-task", "initial details")

        # Then complete it
        coordinator.complete_task(task_id, details, files_changed)

        # Verify the task was completed
        if coordinator.session_tracker:
            task = coordinator.session_tracker.tasks[task_id]
            assert task.completed_at is not None
            assert task.details == details

    def test_complete_task_with_none_tracker(self) -> None:
        """Test complete_task when session tracker is None."""
        coordinator = SessionCoordinator()
        coordinator.session_tracker = None

        # Should not raise an exception
        coordinator.complete_task("task-123", "details", ["file.py"])

    def test_update_task_completed(self) -> None:
        """Test update_task with 'completed' status."""
        coordinator = SessionCoordinator()
        task_id = "task-789"

        coordinator.track_task(task_id, "test-task", "initial details")
        coordinator.update_task(task_id, "completed", details="Updated details")

        # Verify the task was completed
        if coordinator.session_tracker:
            task = coordinator.session_tracker.tasks[task_id]
            assert task.status == "completed"
            assert task.details == "Updated details"

    def test_update_task_failed(self) -> None:
        """Test update_task with 'failed' status."""
        coordinator = SessionCoordinator()
        task_id = "task-999"

        coordinator.track_task(task_id, "test-task", "initial details")
        coordinator.update_task(task_id, "failed", error_message="Test error")

        # Verify the task was marked as failed
        if coordinator.session_tracker:
            task = coordinator.session_tracker.tasks[task_id]
            assert task.status == "failed"
            assert task.error_message == "Test error"

    def test_update_task_in_progress(self) -> None:
        """Test update_task with 'in_progress' status."""
        coordinator = SessionCoordinator()
        task_id = "task-888"

        coordinator.track_task(task_id, "test-task", "initial details")
        coordinator.update_task(task_id, "in_progress", details="In progress", progress=50)

        # Verify the task was updated
        if coordinator.session_tracker:
            task = coordinator.session_tracker.tasks[task_id]
            assert task.status == "in_progress"
            assert task.details == "In progress"
            assert task.progress == 50

    def test_update_task_generic(self) -> None:
        """Test update_task with generic status."""
        coordinator = SessionCoordinator()
        task_id = "task-777"

        coordinator.track_task(task_id, "test-task", "initial details")
        coordinator.update_task(task_id, "custom_status", details="Custom details", progress=75)

        # Verify the task was updated
        if coordinator.session_tracker:
            task = coordinator.session_tracker.tasks[task_id]
            assert task.status == "custom_status"
            assert task.details == "Custom details"
            assert task.progress == 75

    def test_fail_task(self) -> None:
        """Test fail_task method."""
        coordinator = SessionCoordinator()
        task_id = "task-fail"
        error_message = "Something went wrong"
        details = "Failure details"

        coordinator.track_task(task_id, "test-task", "initial details")
        coordinator.fail_task(task_id, error_message, details)

        # Verify the task was marked as failed
        if coordinator.session_tracker:
            task = coordinator.session_tracker.tasks[task_id]
            assert task.status == "failed"
            assert task.error_message == error_message
            assert task.details == details

    def test_fail_task_none_tracker(self) -> None:
        """Test fail_task when session tracker is None."""
        coordinator = SessionCoordinator()
        coordinator.session_tracker = None

        # Should not raise an exception
        coordinator.fail_task("task-123", "error message", "details")


class TestSessionCoordinatorSummaryAndFinalize:
    """Test summary and finalization functionality."""

    def test_get_session_summary(self) -> None:
        """Test get_session_summary method."""
        coordinator = SessionCoordinator()

        summary = coordinator.get_session_summary()

        # When no tracker exists, should return basic info
        assert "tasks_count" in summary
        assert summary["tasks_count"] == 0

        # When tracker exists
        coordinator.session_tracker = SessionTracker(
            session_id=coordinator.session_id,
            start_time=coordinator.start_time,
        )
        coordinator.track_task("task-1", "test-task", "details")
        summary = coordinator.get_session_summary()

        assert "tasks_count" in summary

    def test_get_summary(self) -> None:
        """Test get_summary method."""
        coordinator = SessionCoordinator()

        summary = coordinator.get_summary()

        assert "session_id" in summary
        assert "start_time" in summary
        assert "tasks" in summary
        assert "metadata" in summary

        # Verify the values
        assert summary["session_id"] == coordinator.session_id
        assert summary["start_time"] == coordinator.start_time

    def test_finalize_session_success(self) -> None:
        """Test finalize_session with success."""
        coordinator = SessionCoordinator()
        start_time = time.time() - 10  # 10 seconds ago
        success = True

        coordinator.session_tracker = SessionTracker(
            session_id=coordinator.session_id,
            start_time=start_time,
        )
        coordinator.current_task = "workflow"

        coordinator.finalize_session(start_time, success)

        # Verify metadata was updated
        if coordinator.session_tracker:
            assert coordinator.session_tracker.metadata["success"] == success
            assert "duration" in coordinator.session_tracker.metadata

    def test_finalize_session_failure(self) -> None:
        """Test finalize_session with failure."""
        coordinator = SessionCoordinator()
        start_time = time.time() - 5  # 5 seconds ago
        success = False

        coordinator.session_tracker = SessionTracker(
            session_id=coordinator.session_id,
            start_time=start_time,
        )
        coordinator.current_task = "workflow"

        coordinator.finalize_session(start_time, success)

        # Verify metadata was updated
        if coordinator.session_tracker:
            assert coordinator.session_tracker.metadata["success"] == success


class TestSessionCoordinatorCleanup:
    """Test cleanup functionality."""

    def test_register_cleanup(self) -> None:
        """Test register_cleanup method."""
        coordinator = SessionCoordinator()
        handler = MagicMock()

        coordinator.register_cleanup(handler)

        assert handler in coordinator._cleanup_handlers

    def test_track_lock_file(self) -> None:
        """Test track_lock_file method."""
        coordinator = SessionCoordinator()
        lock_path = Path("/tmp/lockfile")

        coordinator.track_lock_file(lock_path)

        assert lock_path in coordinator._lock_files

    def test_set_cleanup_config(self) -> None:
        """Test set_cleanup_config method."""
        coordinator = SessionCoordinator()
        config = MagicMock()

        coordinator.set_cleanup_config(config)

        assert coordinator._cleanup_config is config

    def test_cleanup_resources(self) -> None:
        """Test cleanup_resources method."""
        coordinator = SessionCoordinator()
        handler = MagicMock()
        lock_path = Path("/tmp/test_lock")

        coordinator.register_cleanup(handler)
        coordinator.track_lock_file(lock_path)

        # Create the lock file temporarily
        lock_path.touch()

        coordinator.cleanup_resources()

        # Verify the handler was called
        handler.assert_called_once()

        # Verify the lock file was removed
        assert not lock_path.exists()

        # Verify the lock file was removed from the set
        assert lock_path not in coordinator._lock_files

    def test_cleanup_resources_with_exceptions(self) -> None:
        """Test cleanup_resources handles exceptions gracefully."""
        coordinator = SessionCoordinator()

        def failing_handler():
            raise Exception("Handler failed")

        coordinator.register_cleanup(failing_handler)

        # Should not raise an exception even if handler fails
        coordinator.cleanup_resources()


class TestSessionCoordinatorPrivateMethods:
    """Test private methods of SessionCoordinator."""

    def test_cleanup_debug_logs(self) -> None:
        """Test _cleanup_debug_logs method."""
        coordinator = SessionCoordinator()

        # This method should not raise an exception
        coordinator._cleanup_debug_logs()

    def test_cleanup_coverage_files(self) -> None:
        """Test _cleanup_coverage_files method."""
        coordinator = SessionCoordinator()

        # This method should not raise an exception
        coordinator._cleanup_coverage_files()

    def test_cleanup_pycache_directories(self) -> None:
        """Test _cleanup_pycache_directories method."""
        coordinator = SessionCoordinator()

        # This method should not raise an exception
        coordinator._cleanup_pycache_directories()

    def test_setup_methods(self) -> None:
        """Test setup methods."""
        coordinator = SessionCoordinator()
        options = MagicMock()

        # These methods should not raise exceptions
        coordinator._setup_logging(options)
        coordinator._setup_websocket_progress_file()
        coordinator._initialize_quality_service()

    def test_update_websocket_progress(self) -> None:
        """Test _update_websocket_progress method."""
        coordinator = SessionCoordinator()

        # This method should not raise an exception
        coordinator._update_websocket_progress("stage", "status")

    def test_update_stage(self) -> None:
        """Test update_stage method."""
        coordinator = SessionCoordinator()

        # This method should not raise an exception
        coordinator.update_stage("stage", "status")
