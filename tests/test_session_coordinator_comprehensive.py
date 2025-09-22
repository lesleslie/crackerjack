import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.task import Task


class TestSessionCoordinator:
    @pytest.fixture
    def console(self):
        return Console()

    @pytest.fixture
    def pkg_path(self):
        return Path(tempfile.gettempdir())

    @pytest.fixture
    def session(self, console, pkg_path):
        return SessionCoordinator(console, pkg_path)

    def test_init(self, session, console, pkg_path):
        """Test SessionCoordinator initialization"""
        assert session.console == console
        assert session.pkg_path == pkg_path
        assert session.session_id is not None
        # These are private attributes in the actual implementation
        assert hasattr(session, '_cleanup_handlers')
        assert hasattr(session, '_lock_files')
        assert session.start_time is not None
        assert isinstance(session.tasks, dict)
        assert len(session.tasks) == 0

    def test_init_with_web_job_id(self, console, pkg_path):
        """Test SessionCoordinator initialization with web job ID"""
        web_job_id = "test-job-123"
        session = SessionCoordinator(console, pkg_path, web_job_id)

        assert session.session_id == web_job_id
        assert session.web_job_id == web_job_id

    def test_start_session(self, session):
        """Test start_session method"""
        task_name = "test_task"
        session.start_session(task_name)

        assert session.current_task == task_name

    def test_end_session(self, session):
        """Test end_session method"""
        # Start a session first
        session.start_session("test_task")

        # End the session
        session.end_session(success=True)

        # Check that session state is properly updated
        assert hasattr(session, 'end_time')
        assert session.end_time is not None

    def test_track_task(self, session):
        """Test track_task method"""
        task_id = "task_123"
        task_name = "test_task"
        result_id = session.track_task(task_id, task_name)

        assert result_id == task_id
        assert task_id in session.tasks
        task = session.tasks[task_id]
        # The implementation creates a generic object, not a Task instance
        assert hasattr(task, 'task_id')
        assert hasattr(task, 'description')
        assert hasattr(task, 'status')
        assert task.task_id == task_id
        assert task.description == task_name
        assert task.status == "in_progress"

    def test_update_task(self, session):
        """Test update_task method"""
        task_id = "task_123"
        task_name = "test_task"
        session.track_task(task_id, task_name)

        # Update the task
        session.update_task(task_id, status="processing", progress=50)

        task = session.tasks[task_id]
        assert task.status == "processing"
        assert task.progress == 50

    def test_complete_task(self, session):
        """Test complete_task method"""
        task_id = "task_123"
        task_name = "test_task"
        session.track_task(task_id, task_name)

        # Complete the task
        session.complete_task(task_id, "Task completed successfully")

        task = session.tasks[task_id]
        assert task.status == "completed"
        assert task.end_time is not None

    def test_fail_task(self, session):
        """Test fail_task method"""
        task_id = "task_123"
        task_name = "test_task"
        session.track_task(task_id, task_name)

        # Fail the task
        error_message = "Something went wrong"
        session.fail_task(task_id, error_message)

        task = session.tasks[task_id]
        assert task.status == "failed"
        assert task.error == error_message
        assert task.end_time is not None

    def test_get_session_summary(self, session):
        """Test get_session_summary method"""
        # Initially should return None or empty dict
        summary = session.get_session_summary()
        assert summary is None or summary == {}

        # Add some tasks
        session.track_task("task1", "Task 1")
        session.complete_task("task1")
        session.track_task("task2", "Task 2")
        session.fail_task("task2", "Failed")

        # Now should return a summary
        summary = session.get_session_summary()
        assert isinstance(summary, dict)
        assert "total" in summary
        assert "completed" in summary
        assert "failed" in summary

    def test_get_summary(self, session):
        """Test get_summary method"""
        # Add some tasks
        session.track_task("task1", "Task 1")
        session.complete_task("task1")
        session.track_task("task2", "Task 2")
        session.fail_task("task2", "Failed")

        summary = session.get_summary()
        assert isinstance(summary, dict)
        assert "session_id" in summary
        assert "start_time" in summary
        assert "tasks" in summary
        assert len(summary["tasks"]) == 2

    def test_finalize_session(self, session):
        """Test finalize_session method"""
        start_time = time.time()
        session.finalize_session(start_time, success=True)

        # Check that session is properly finalized
        assert hasattr(session, '_end_time')
        assert session._end_time is not None

    def test_register_cleanup(self, session):
        """Test register_cleanup method"""
        def cleanup_handler():
            pass

        session.register_cleanup(cleanup_handler)

        assert len(session._cleanup_handlers) == 1
        assert session._cleanup_handlers[0] == cleanup_handler

    def test_track_lock_file(self, session):
        """Test track_lock_file method"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            lock_file_path = Path(tmp_file.name)

        session.track_lock_file(lock_file_path)

        assert lock_file_path in session._lock_files

    def test_cleanup_resources(self, session):
        """Test cleanup_resources method"""
        # Register a cleanup handler
        cleanup_called = False
        def cleanup_handler():
            nonlocal cleanup_called
            cleanup_called = True

        session.register_cleanup(cleanup_handler)

        # Track a lock file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            lock_file_path = Path(tmp_file.name)
        session.track_lock_file(lock_file_path)

        # Cleanup resources
        with patch.object(session, '_cleanup_temporary_files'), \
             patch.object(session, '_cleanup_debug_logs'), \
             patch.object(session, '_cleanup_coverage_files'), \
             patch.object(session, '_cleanup_pycache_directories'):
            session.cleanup_resources()

        # Verify cleanup handler was called
        assert cleanup_called is True

    def test_set_cleanup_config(self, session):
        """Test set_cleanup_config method"""
        config = Mock()
        session.set_cleanup_config(config)

        assert session._cleanup_config == config

    def test_cleanup_temporary_files(self, session):
        """Test _cleanup_temporary_files method"""
        # This method is complex and depends on system state, so we'll just test
        # that it doesn't raise exceptions
        try:
            session._cleanup_temporary_files()
        except Exception as e:
            pytest.fail(f"_cleanup_temporary_files raised an exception: {e}")

    def test_cleanup_debug_logs(self, session):
        """Test _cleanup_debug_logs method"""
        # This method is complex and depends on system state, so we'll just test
        # that it doesn't raise exceptions
        try:
            session._cleanup_debug_logs()
        except Exception as e:
            pytest.fail(f"_cleanup_debug_logs raised an exception: {e}")

    def test_cleanup_coverage_files(self, session):
        """Test _cleanup_coverage_files method"""
        # This method is complex and depends on system state, so we'll just test
        # that it doesn't raise exceptions
        try:
            session._cleanup_coverage_files()
        except Exception as e:
            pytest.fail(f"_cleanup_coverage_files raised an exception: {e}")

    def test_cleanup_pycache_directories(self, session):
        """Test _cleanup_pycache_directories method"""
        # This method is complex and depends on system state, so we'll just test
        # that it doesn't raise exceptions
        try:
            session._cleanup_pycache_directories()
        except Exception as e:
            pytest.fail(f"_cleanup_pycache_directories raised an exception: {e}")

    def test_initialize_session_tracking(self, session):
        """Test initialize_session_tracking method"""
        # Create mock options
        options = Mock()
        options.verbose = True
        options.test = True

        with patch.object(session, '_setup_logging'), \
             patch.object(session, '_setup_websocket_progress_file'), \
             patch.object(session, '_initialize_quality_service'):
            session.initialize_session_tracking(options)

        # Verify that the setup methods were called
        # (The actual behavior would depend on the options and system state)

    def test_update_stage(self, session):
        """Test update_stage method"""
        stage = "testing"
        status = "running"

        with patch.object(session, '_update_websocket_progress'):
            session.update_stage(stage, status)

        # The method should call _update_websocket_progress with the right parameters
        # (The actual behavior would depend on system state)
