"""Unit tests for SessionCoordinator.

Tests session tracking, task management, cleanup handlers,
and session lifecycle coordination.
"""

import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.core.session_coordinator import SessionCoordinator, SessionController


@pytest.mark.unit
class TestSessionCoordinatorInitialization:
    """Test SessionCoordinator initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        coordinator = SessionCoordinator()

        assert coordinator.console is not None
        assert coordinator.pkg_path == Path.cwd()
        assert coordinator.web_job_id is None
        assert coordinator.session_id is not None
        assert isinstance(coordinator.start_time, float)
        assert coordinator.cleanup_handlers == []
        assert coordinator.lock_files == set()
        assert coordinator.current_task is None

    def test_initialization_with_console(self):
        """Test initialization with provided console."""
        mock_console = Mock()

        coordinator = SessionCoordinator(console=mock_console)

        assert coordinator.console == mock_console

    def test_initialization_with_pkg_path(self, tmp_path):
        """Test initialization with provided pkg_path."""
        coordinator = SessionCoordinator(pkg_path=tmp_path)

        assert coordinator.pkg_path == tmp_path

    def test_initialization_with_web_job_id(self):
        """Test initialization with web job ID."""
        job_id = "test-job-123"
        coordinator = SessionCoordinator(web_job_id=job_id)

        assert coordinator.web_job_id == job_id
        assert coordinator.session_id == job_id

    def test_initialization_session_id_generated(self):
        """Test session ID is generated when no web_job_id."""
        coordinator = SessionCoordinator()

        assert coordinator.session_id is not None
        assert len(coordinator.session_id) == 8  # UUID hex[:8]


@pytest.mark.unit
class TestSessionCoordinatorSessionTracking:
    """Test session tracking initialization."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        return SessionCoordinator(console=mock_console)

    @pytest.fixture
    def mock_options(self):
        """Create mock options."""
        options = Mock()
        options.__dict__ = {"verbose": True, "ai_agent": False}
        return options

    def test_initialize_session_tracking(self, coordinator, mock_options):
        """Test initializing session tracking."""
        coordinator.initialize_session_tracking(mock_options)

        assert coordinator.session_tracker is not None
        assert coordinator.session_tracker.session_id == coordinator.session_id
        assert "options" in coordinator.session_tracker.metadata
        assert "pkg_path" in coordinator.session_tracker.metadata

    def test_start_session(self, coordinator):
        """Test starting a session task."""
        coordinator.start_session("test_task")

        assert coordinator.current_task == "test_task"
        assert coordinator.session_tracker is not None
        assert coordinator.session_tracker.metadata["current_session"] == "test_task"

    def test_start_session_lazy_initialization(self, coordinator):
        """Test session tracker is lazily initialized."""
        assert coordinator.session_tracker is None

        coordinator.start_session("task1")

        assert coordinator.session_tracker is not None

    def test_end_session(self, coordinator):
        """Test ending a session."""
        coordinator.start_session("test_task")

        coordinator.end_session(success=True)

        assert hasattr(coordinator, "end_time")
        assert coordinator.current_task is None
        assert coordinator.session_tracker.metadata["success"] is True


@pytest.mark.unit
class TestSessionCoordinatorTaskTracking:
    """Test task tracking functionality."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        return SessionCoordinator(console=mock_console)

    def test_track_task(self, coordinator):
        """Test tracking a task."""
        task_id = coordinator.track_task("task1", "Test Task", "Details")

        assert task_id == "task1"
        assert coordinator.session_tracker is not None
        assert "task1" in coordinator.tasks

    def test_track_task_lazy_initialization(self, coordinator):
        """Test task tracking initializes session tracker."""
        assert coordinator.session_tracker is None

        coordinator.track_task("task1", "Task")

        assert coordinator.session_tracker is not None

    def test_complete_task(self, coordinator):
        """Test completing a task."""
        coordinator.track_task("task1", "Test Task")

        coordinator.complete_task("task1", "Completed successfully", ["file1.py"])

        task = coordinator.tasks["task1"]
        assert task.status == "completed"

    def test_complete_task_without_session_tracker(self, coordinator):
        """Test completing task when session tracker is None."""
        coordinator.session_tracker = None

        # Should not raise error
        coordinator.complete_task("task1", "Done")

    def test_fail_task(self, coordinator):
        """Test failing a task."""
        coordinator.track_task("task1", "Test Task")

        coordinator.fail_task("task1", "Error occurred", "Error details")

        task = coordinator.tasks["task1"]
        assert task.status == "failed"

    def test_fail_task_without_session_tracker(self, coordinator):
        """Test failing task when session tracker is None."""
        coordinator.session_tracker = None

        # Should not raise error
        coordinator.fail_task("task1", "Error")

    def test_update_task_completed(self, coordinator):
        """Test updating task to completed status."""
        coordinator.track_task("task1", "Test Task")

        coordinator.update_task("task1", "completed", details="Done")

        task = coordinator.tasks["task1"]
        assert task.status == "completed"

    def test_update_task_failed(self, coordinator):
        """Test updating task to failed status."""
        coordinator.track_task("task1", "Test Task")

        coordinator.update_task("task1", "failed", error_message="Error")

        task = coordinator.tasks["task1"]
        assert task.status == "failed"

    def test_update_task_in_progress(self, coordinator):
        """Test updating task to in_progress status."""
        coordinator.track_task("task1", "Test Task")

        coordinator.update_task("task1", "in_progress", details="Working")

        task = coordinator.tasks["task1"]
        assert task.status == "in_progress"

    def test_update_task_in_progress_creates_task(self, coordinator):
        """Test updating non-existent task to in_progress creates it."""
        coordinator.update_task("new_task", "in_progress", details="Creating")

        assert "new_task" in coordinator.tasks

    def test_update_task_arbitrary_status(self, coordinator):
        """Test updating task with arbitrary status."""
        coordinator.track_task("task1", "Test Task")

        coordinator.update_task("task1", "custom_status", details="Custom")

        task = coordinator.tasks["task1"]
        assert task.status == "custom_status"

    def test_update_task_lazy_initialization(self, coordinator):
        """Test update_task initializes session tracker."""
        assert coordinator.session_tracker is None

        coordinator.update_task("task1", "in_progress")

        assert coordinator.session_tracker is not None


@pytest.mark.unit
class TestSessionCoordinatorCleanup:
    """Test cleanup and resource management."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        return SessionCoordinator(console=mock_console)

    def test_register_cleanup(self, coordinator):
        """Test registering cleanup handler."""
        handler = Mock()

        coordinator.register_cleanup(handler)

        assert handler in coordinator.cleanup_handlers

    def test_cleanup_resources_executes_handlers(self, coordinator):
        """Test cleanup executes all handlers."""
        handler1 = Mock()
        handler2 = Mock()

        coordinator.register_cleanup(handler1)
        coordinator.register_cleanup(handler2)

        coordinator.cleanup_resources()

        handler1.assert_called_once()
        handler2.assert_called_once()

    def test_cleanup_resources_handles_errors(self, coordinator):
        """Test cleanup handles handler errors gracefully."""
        failing_handler = Mock(side_effect=Exception("Handler error"))
        successful_handler = Mock()

        coordinator.register_cleanup(failing_handler)
        coordinator.register_cleanup(successful_handler)

        # Should not raise exception
        coordinator.cleanup_resources()

        # Successful handler should still be called
        successful_handler.assert_called_once()

    def test_track_lock_file(self, coordinator, tmp_path):
        """Test tracking lock files."""
        lock_file = tmp_path / "test.lock"

        coordinator.track_lock_file(lock_file)

        assert lock_file in coordinator.lock_files

    def test_cleanup_removes_lock_files(self, coordinator, tmp_path):
        """Test cleanup removes tracked lock files."""
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("lock")

        coordinator.track_lock_file(lock_file)
        coordinator.cleanup_resources()

        assert not lock_file.exists()
        assert lock_file not in coordinator.lock_files

    def test_cleanup_handles_missing_lock_files(self, coordinator, tmp_path):
        """Test cleanup handles non-existent lock files."""
        lock_file = tmp_path / "nonexistent.lock"

        coordinator.track_lock_file(lock_file)

        # Should not raise error
        coordinator.cleanup_resources()

        assert lock_file not in coordinator.lock_files

    def test_set_cleanup_config(self, coordinator):
        """Test setting cleanup configuration."""
        config = {"preserve_files": True, "verbose": False}

        coordinator.set_cleanup_config(config)

        assert coordinator.cleanup_config == config


@pytest.mark.unit
class TestSessionCoordinatorFinalization:
    """Test session finalization."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        return SessionCoordinator(console=mock_console)

    def test_finalize_session_success(self, coordinator):
        """Test finalizing successful session."""
        coordinator.start_session("test_task")
        start_time = time.time()

        coordinator.finalize_session(start_time, success=True)

        assert "duration" in coordinator.session_tracker.metadata
        assert coordinator.session_tracker.metadata["success"] is True
        assert coordinator.current_task is None

    def test_finalize_session_failure(self, coordinator):
        """Test finalizing failed session."""
        coordinator.start_session("test_task")
        start_time = time.time()

        coordinator.finalize_session(start_time, success=False)

        assert coordinator.session_tracker.metadata["success"] is False

    def test_finalize_session_without_tracker(self, coordinator):
        """Test finalizing session without tracker."""
        coordinator.session_tracker = None
        start_time = time.time()

        # Should not raise error
        coordinator.finalize_session(start_time, success=True)


@pytest.mark.unit
class TestSessionCoordinatorSummary:
    """Test session summary generation."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator instance."""
        mock_console = Mock()
        return SessionCoordinator(console=mock_console)

    def test_get_session_summary_with_tracker(self, coordinator):
        """Test getting session summary with tracker."""
        coordinator.start_session("test_task")
        coordinator.track_task("task1", "Task 1")
        coordinator.complete_task("task1")

        summary = coordinator.get_session_summary()

        assert "session_id" in summary
        assert summary["session_id"] == coordinator.session_id

    def test_get_session_summary_without_tracker(self, coordinator):
        """Test getting session summary without tracker."""
        coordinator.session_tracker = None

        summary = coordinator.get_session_summary()

        assert summary["session_id"] == coordinator.session_id
        assert summary["tasks"] == {}
        assert summary["tasks_count"] == 0

    def test_get_summary_alias(self, coordinator):
        """Test get_summary is alias for get_session_summary."""
        coordinator.start_session("test")

        summary1 = coordinator.get_session_summary()
        summary2 = coordinator.get_summary()

        # Compare all fields except duration which changes with each call
        assert summary1["session_id"] == summary2["session_id"]
        assert summary1["total_tasks"] == summary2["total_tasks"]
        assert summary1["tasks_count"] == summary2["tasks_count"]
        assert summary1["completed"] == summary2["completed"]
        assert summary1["failed"] == summary2["failed"]
        assert summary1["in_progress"] == summary2["in_progress"]
        assert summary1["current_task"] == summary2["current_task"]

    def test_get_session_summary_backward_compatible(self, coordinator):
        """Test session summary includes backward compatible tasks_count."""
        coordinator.start_session("test")
        coordinator.track_task("task1", "Task 1")

        summary = coordinator.get_session_summary()

        assert "tasks_count" in summary


@pytest.mark.unit
class TestSessionController:
    """Test SessionController class."""

    @pytest.fixture
    def mock_pipeline(self):
        """Create mock pipeline."""
        pipeline = Mock()
        pipeline.session = Mock(spec=SessionCoordinator)
        return pipeline

    def test_initialization(self, mock_pipeline):
        """Test SessionController initialization."""
        controller = SessionController(mock_pipeline)

        assert controller._pipeline == mock_pipeline

    def test_initialize(self, mock_pipeline):
        """Test initializing session."""
        controller = SessionController(mock_pipeline)
        options = Mock()

        controller.initialize(options)

        # Should call all initialization methods
        mock_pipeline.session.initialize_session_tracking.assert_called_once_with(
            options
        )
        mock_pipeline._configure_session_cleanup.assert_called_once_with(options)
        mock_pipeline._initialize_zuban_lsp.assert_called_once_with(options)
        mock_pipeline._configure_hook_manager_lsp.assert_called_once_with(options)
        mock_pipeline._register_lsp_cleanup_handler.assert_called_once_with(options)
        mock_pipeline._log_workflow_startup_info.assert_called_once_with(options)


@pytest.mark.unit
class TestSessionCoordinatorIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def coordinator(self, tmp_path):
        """Create coordinator with temp path."""
        mock_console = Mock()
        return SessionCoordinator(console=mock_console, pkg_path=tmp_path)

    def test_complete_session_lifecycle(self, coordinator):
        """Test complete session lifecycle."""
        # Start session
        coordinator.start_session("main_workflow")

        # Track tasks
        coordinator.track_task("task1", "Task 1", "Details 1")
        coordinator.track_task("task2", "Task 2", "Details 2")

        # Complete tasks
        coordinator.complete_task("task1", "Done", ["file1.py"])
        coordinator.fail_task("task2", "Error occurred")

        # End session
        coordinator.end_session(success=False)

        # Get summary
        summary = coordinator.get_session_summary()

        assert summary["session_id"] == coordinator.session_id
        assert len(coordinator.tasks) == 2

    def test_cleanup_with_handlers_and_locks(self, coordinator, tmp_path):
        """Test cleanup with both handlers and lock files."""
        # Register handlers
        handler1 = Mock()
        handler2 = Mock()
        coordinator.register_cleanup(handler1)
        coordinator.register_cleanup(handler2)

        # Track lock files
        lock1 = tmp_path / "lock1.lock"
        lock2 = tmp_path / "lock2.lock"
        lock1.write_text("lock")
        lock2.write_text("lock")
        coordinator.track_lock_file(lock1)
        coordinator.track_lock_file(lock2)

        # Cleanup
        coordinator.cleanup_resources()

        # Verify handlers called
        handler1.assert_called_once()
        handler2.assert_called_once()

        # Verify lock files removed
        assert not lock1.exists()
        assert not lock2.exists()
        assert len(coordinator.lock_files) == 0

    def test_session_with_web_job_id(self):
        """Test session with web job ID."""
        mock_console = Mock()
        job_id = "web-job-456"

        coordinator = SessionCoordinator(console=mock_console, web_job_id=job_id)

        coordinator.start_session("web_task")
        coordinator.track_task("task1", "Web Task")

        summary = coordinator.get_session_summary()

        assert summary["session_id"] == job_id

    def test_multiple_task_updates(self, coordinator):
        """Test multiple updates to same task."""
        coordinator.track_task("task1", "Task 1")

        coordinator.update_task("task1", "in_progress", details="Starting")
        assert coordinator.tasks["task1"].status == "in_progress"

        coordinator.update_task("task1", "in_progress", details="Continuing")
        assert coordinator.tasks["task1"].details == "Continuing"

        coordinator.update_task("task1", "completed", details="Finished")
        assert coordinator.tasks["task1"].status == "completed"
