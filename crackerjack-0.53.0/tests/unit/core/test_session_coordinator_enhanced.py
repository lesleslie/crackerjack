"""Enhanced tests for session coordinator with more scenarios."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.task import SessionTracker


class TestSessionCoordinatorEnhanced:
    """Enhanced tests for SessionCoordinator covering more scenarios."""

    def test_session_coordinator_with_real_session_tracker(self) -> None:
        """Test SessionCoordinator with actual SessionTracker operations."""
        coordinator = SessionCoordinator()

        # Initialize session tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Verify session tracker was created
        assert coordinator.session_tracker is not None

        # Test tracking a task
        task_id = "test_task_1"
        coordinator.track_task(task_id, "Test Task", "Test task description")

        # Verify task was added to tracker
        assert task_id in coordinator.session_tracker.tasks

        # Update task status
        coordinator.update_task(task_id, "in_progress", details="Task in progress", progress=50)

        # Verify task was updated
        task = coordinator.session_tracker.tasks[task_id]
        assert task.status == "in_progress"
        assert task.progress == 50

        # Complete the task
        coordinator.complete_task(task_id, "Task completed", ["file1.py", "file2.py"])

        # Verify task was completed
        task = coordinator.session_tracker.tasks[task_id]
        assert task.status == "completed"
        assert task.completed_at is not None

    def test_session_coordinator_task_failure_scenarios(self) -> None:
        """Test SessionCoordinator task failure scenarios."""
        coordinator = SessionCoordinator()

        # Initialize session tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Test failing a task
        task_id = "failing_task"
        coordinator.track_task(task_id, "Failing Task", "Task that will fail")

        error_message = "Something went wrong"
        coordinator.fail_task(task_id, error_message, "Detailed error info")

        # Verify task was marked as failed
        task = coordinator.session_tracker.tasks[task_id]
        assert task.status == "failed"
        assert task.error_message == error_message

    def test_session_coordinator_multiple_tasks(self) -> None:
        """Test SessionCoordinator with multiple concurrent tasks."""
        coordinator = SessionCoordinator()

        # Initialize session tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Track multiple tasks
        tasks = [
            ("task_1", "Task 1", "First task"),
            ("task_2", "Task 2", "Second task"),
            ("task_3", "Task 3", "Third task"),
        ]

        for task_id, name, desc in tasks:
            coordinator.track_task(task_id, name, desc)

        # Verify all tasks were tracked
        for task_id, _, _ in tasks:
            assert task_id in coordinator.session_tracker.tasks

        # Update different tasks with different statuses
        coordinator.update_task("task_1", "completed", details="Task 1 completed")
        coordinator.update_task("task_2", "in_progress", details="Task 2 in progress", progress=75)
        coordinator.update_task("task_3", "failed", error_message="Task 3 failed")

        # Verify updates were applied
        assert coordinator.session_tracker.tasks["task_1"].status == "completed"
        assert coordinator.session_tracker.tasks["task_2"].status == "in_progress"
        assert coordinator.session_tracker.tasks["task_3"].status == "failed"

    def test_session_coordinator_session_lifecycle(self) -> None:
        """Test complete session lifecycle."""
        coordinator = SessionCoordinator()

        # Start a session
        coordinator.start_session("main_workflow")
        assert coordinator.current_task == "main_workflow"

        # Initialize tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Track some work
        coordinator.track_task("work_task", "Work Task", "Doing some work")
        coordinator.update_task("work_task", "in_progress")

        # End the session
        start_time = time.time() - 10  # Started 10 seconds ago
        coordinator.finalize_session(start_time, success=True)

        # Verify session was finalized properly
        if coordinator.session_tracker:
            assert coordinator.session_tracker.metadata["success"] is True
            assert abs(coordinator.session_tracker.metadata["duration"] - 10.0) < 1.0

    def test_session_coordinator_cleanup_scenarios(self) -> None:
        """Test SessionCoordinator cleanup in various scenarios."""
        coordinator = SessionCoordinator()

        # Register a cleanup handler
        cleanup_handler = MagicMock()
        coordinator.register_cleanup(cleanup_handler)

        # Add a lock file
        lock_file = Path("/tmp/test_lock.lock")
        coordinator.track_lock_file(lock_file)

        # Create the lock file temporarily
        lock_file.touch()

        try:
            # Perform cleanup
            coordinator.cleanup_resources()

            # Verify cleanup handler was called
            cleanup_handler.assert_called_once()

            # Verify lock file was removed
            assert not lock_file.exists()

            # Verify lock file was removed from tracking
            assert lock_file not in coordinator._lock_files
        finally:
            # Clean up in case it wasn't removed
            if lock_file.exists():
                lock_file.unlink()

    def test_session_coordinator_with_different_console_implementations(self) -> None:
        """Test SessionCoordinator with different console implementations."""
        console = CrackerjackConsole()
        pkg_path = Path("/tmp/test")

        coordinator = SessionCoordinator(console=console, pkg_path=pkg_path)

        # Initialize session tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Verify it works with the real console
        coordinator.track_task("console_test", "Console Test", "Testing with real console")
        assert "console_test" in coordinator.session_tracker.tasks

    def test_session_coordinator_summary_methods(self) -> None:
        """Test SessionCoordinator summary methods in various states."""
        coordinator = SessionCoordinator()

        # Test summary when no tracker exists
        summary = coordinator.get_session_summary()
        assert summary["tasks_count"] == 0

        # Initialize tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Add some tasks
        coordinator.track_task("task1", "Task 1", "Description 1")
        coordinator.track_task("task2", "Task 2", "Description 2")

        # Test summary when tracker exists
        summary = coordinator.get_session_summary()
        assert summary["tasks_count"] == 2

        # Test full summary
        full_summary = coordinator.get_summary()
        assert "session_id" in full_summary
        assert "start_time" in full_summary
        assert "tasks" in full_summary
        assert "metadata" in full_summary

    def test_session_coordinator_error_recovery_scenarios(self) -> None:
        """Test SessionCoordinator behavior in error recovery scenarios."""
        coordinator = SessionCoordinator()

        # Test operations when session tracker is None initially
        # These should not crash
        coordinator.complete_task("nonexistent", "details", ["file.py"])
        coordinator.fail_task("nonexistent", "error", "details")
        coordinator.update_task("nonexistent", "status", details="details")

        # Now initialize tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Operations should work normally now
        coordinator.track_task("new_task", "New Task", "Description")
        coordinator.update_task("new_task", "in_progress")
        coordinator.complete_task("new_task", "Completed", ["file.py"])

        # Verify the new task was tracked properly
        assert "new_task" in coordinator.session_tracker.tasks
        assert coordinator.session_tracker.tasks["new_task"].status == "completed"

    def test_session_coordinator_with_custom_web_job_id(self) -> None:
        """Test SessionCoordinator with custom web job ID."""
        web_job_id = "custom-job-123"
        coordinator = SessionCoordinator(web_job_id=web_job_id)

        # Verify the custom ID was used
        assert coordinator.session_id == web_job_id
        assert coordinator.web_job_id == web_job_id

        # Initialize tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Verify the custom ID is reflected in the session tracker
        if coordinator.session_tracker:
            assert coordinator.session_tracker.session_id == web_job_id

    def test_session_coordinator_task_progress_updates(self) -> None:
        """Test SessionCoordinator task progress updates."""
        coordinator = SessionCoordinator()

        # Initialize tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        task_id = "progress_task"
        coordinator.track_task(task_id, "Progress Task", "Task with progress updates")

        # Update progress multiple times
        progress_updates = [10, 25, 50, 75, 100]
        for progress in progress_updates:
            coordinator.update_task(task_id, "in_progress", progress=progress)
            if coordinator.session_tracker:
                task = coordinator.session_tracker.tasks[task_id]
                assert task.progress == progress

        # Complete the task
        coordinator.update_task(task_id, "completed", progress=100)
        if coordinator.session_tracker:
            task = coordinator.session_tracker.tasks[task_id]
            assert task.status == "completed"
            assert task.progress == 100

    def test_session_coordinator_metadata_storage(self) -> None:
        """Test SessionCoordinator metadata storage and retrieval."""
        coordinator = SessionCoordinator()

        # Initialize tracking
        options = MagicMock()
        options.track_progress = True
        coordinator.initialize_session_tracking(options)

        # Verify initial metadata
        if coordinator.session_tracker:
            assert "pkg_path" in coordinator.session_tracker.metadata
            assert str(coordinator.pkg_path) in str(coordinator.session_tracker.metadata["pkg_path"])

        # Add custom metadata through session operations
        coordinator.start_session("test_session")
        if coordinator.session_tracker:
            assert coordinator.session_tracker.metadata["current_session"] == "test_session"
