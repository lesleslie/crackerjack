"""Tests for task module."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.models.task import HookResult, SessionTracker, Task, TaskStatus, TaskStatusData


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_enum_values(self) -> None:
        """Verify all task status values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_enum_members(self) -> None:
        """Verify all task status members exist."""
        members = {member.value for member in TaskStatus}
        assert members == {"pending", "in_progress", "completed", "failed"}


class TestTask:
    """Tests for Task dataclass."""

    def test_minimal_task(self) -> None:
        """Verify minimal Task creation."""
        task = Task(
            id="task1",
            name="Test Task",
            status=TaskStatus.PENDING,
        )
        assert task.id == "task1"
        assert task.name == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.details is None

    def test_task_with_details(self) -> None:
        """Verify Task with details."""
        task = Task(
            id="task2",
            name="Complex Task",
            status=TaskStatus.IN_PROGRESS,
            details="Task is running",
        )
        assert task.details == "Task is running"

    def test_to_dict(self) -> None:
        """Verify to_dict conversion."""
        task = Task(
            id="task3",
            name="Convert Task",
            status=TaskStatus.COMPLETED,
            details="Task completed successfully",
        )
        result = task.to_dict()

        assert result == {
            "id": "task3",
            "name": "Convert Task",
            "status": "completed",
            "details": "Task completed successfully",
        }

    def test_to_dict_no_details(self) -> None:
        """Verify to_dict with None details."""
        task = Task(
            id="task4",
            name="Simple Task",
            status=TaskStatus.FAILED,
        )
        result = task.to_dict()

        assert result["details"] is None

    def test_all_statuses(self) -> None:
        """Verify Task works with all statuses."""
        for status in TaskStatus:
            task = Task(
                id=f"task-{status.value}",
                name=f"Task {status.value}",
                status=status,
            )
            assert task.status == status


class TestHookResult:
    """Tests for HookResult dataclass."""

    def test_minimal_hook_result(self) -> None:
        """Verify minimal HookResult creation."""
        result = HookResult()
        assert result.id == ""
        assert result.name == ""
        assert result.status == ""
        assert result.duration == 0.0
        assert result.files_processed == 0
        assert result.files_checked == []
        assert result.issues_found == []
        assert result.issues_count == 0

    def test_hook_result_with_name(self) -> None:
        """Verify HookResult with name."""
        result = HookResult(
            id="hook1",
            name="ruff-lint",
            status="completed",
            duration=1.5,
        )
        assert result.id == "hook1"
        assert result.name == "ruff-lint"
        assert result.status == "completed"
        assert result.duration == 1.5

    def test_post_init_hook_name_to_name(self) -> None:
        """Verify hook_name populates name if name is empty."""
        result = HookResult(hook_name="codespell")
        assert result.name == "codespell"

    def test_post_init_name_to_id(self) -> None:
        """Verify name populates id if id is empty."""
        result = HookResult(name="mypy")
        assert result.id == "mypy"

    def test_post_init_returncode_to_exit_code(self) -> None:
        """Verify returncode populates exit_code if exit_code is None."""
        result = HookResult(returncode=1)
        assert result.exit_code == 1

    def test_post_init_files_checked_to_processed(self) -> None:
        """Verify files_checked count populates files_processed if 0."""
        files = ["file1.py", "file2.py", "file3.py"]
        result = HookResult(files_checked=files)
        assert result.files_processed == 3

    def test_post_init_issues_found_initializes_empty(self) -> None:
        """Verify issues_found initializes to empty list if None."""
        result = HookResult()
        assert result.issues_found == []

    def test_post_init_issues_count_from_found(self) -> None:
        """Verify issues_count populates from issues_found length."""
        issues = ["issue1", "issue2"]
        result = HookResult(issues_found=issues)
        assert result.issues_count == 2

    def test_post_init_all_logic(self) -> None:
        """Verify all post_init logic combined."""
        files = [Path("test.py"), Path("other.py")]
        issues = ["error1", "error2", "error3"]

        result = HookResult(
            hook_name="test-hook",
            returncode=5,
            files_checked=files,
            issues_found=issues,
        )

        assert result.name == "test-hook"
        assert result.id == "test-hook"
        assert result.exit_code == 5
        assert result.files_processed == 2
        assert result.issues_count == 3


class TestTaskStatusData:
    """Tests for TaskStatusData dataclass."""

    def test_minimal_status_data(self) -> None:
        """Verify minimal TaskStatusData creation."""
        data = TaskStatusData(
            id="task1",
            name="Test Task",
            status="pending",
        )
        assert data.id == "task1"
        assert data.name == "Test Task"
        assert data.status == "pending"
        assert data.files_changed == []
        assert data.hook_results == []

    def test_post_init_lists_initialized(self) -> None:
        """Verify post_init initializes empty lists."""
        data = TaskStatusData(
            id="task2",
            name="Task 2",
            status="in_progress",
        )
        assert isinstance(data.files_changed, list)
        assert isinstance(data.hook_results, list)
        assert data.files_changed == []
        assert data.hook_results == []

    def test_post_init_duration_calculated(self) -> None:
        """Verify post_init calculates duration from times."""
        start = time.time()
        end = start + 5.0

        data = TaskStatusData(
            id="task3",
            name="Task 3",
            status="completed",
            start_time=start,
            end_time=end,
        )

        assert data.duration == 5.0

    def test_post_init_no_duration_without_end_time(self) -> None:
        """Verify duration is None if end_time is missing."""
        data = TaskStatusData(
            id="task4",
            name="Task 4",
            status="in_progress",
            start_time=time.time(),
        )
        assert data.duration is None

    def test_task_id_property_getter(self) -> None:
        """Verify task_id property returns id."""
        data = TaskStatusData(
            id="task5",
            name="Task 5",
            status="pending",
        )
        assert data.task_id == "task5"

    def test_task_id_property_setter(self) -> None:
        """Verify task_id property setter updates id."""
        data = TaskStatusData(
            id="task6",
            name="Task 6",
            status="pending",
        )
        data.task_id = "new_id"
        assert data.id == "new_id"

    def test_description_property_getter(self) -> None:
        """Verify description property returns name."""
        data = TaskStatusData(
            id="task7",
            name="Test Description",
            status="pending",
        )
        assert data.description == "Test Description"

    def test_description_property_setter(self) -> None:
        """Verify description property setter updates name."""
        data = TaskStatusData(
            id="task8",
            name="Original Name",
            status="pending",
        )
        data.description = "New Name"
        assert data.name == "New Name"

    def test_error_property_getter(self) -> None:
        """Verify error property returns error_message."""
        data = TaskStatusData(
            id="task9",
            name="Task 9",
            status="failed",
            error_message="Test error",
        )
        assert data.error == "Test error"

    def test_error_property_setter(self) -> None:
        """Verify error property setter updates error_message."""
        data = TaskStatusData(
            id="task10",
            name="Task 10",
            status="pending",
        )
        data.error = "New error"
        assert data.error_message == "New error"


class TestSessionTracker:
    """Tests for SessionTracker model."""

    def test_minimal_session_tracker(self) -> None:
        """Verify minimal SessionTracker creation."""
        tracker = SessionTracker(
            session_id="session1",
            start_time=time.time(),
        )
        assert tracker.session_id == "session1"
        assert isinstance(tracker.start_time, float)
        assert tracker.tasks == {}
        assert tracker.metadata == {}
        assert tracker.current_task is None

    def test_session_tracker_with_console(self) -> None:
        """Verify SessionTracker accepts custom console."""
        mock_console = MagicMock()
        tracker = SessionTracker(
            session_id="session2",
            start_time=time.time(),
            console=mock_console,
        )
        assert tracker.console is mock_console

    @patch("crackerjack.models.task.Console")
    def test_session_tracker_default_console(self, mock_console_class: MagicMock) -> None:
        """Verify SessionTracker creates default console if not provided."""
        mock_console_instance = MagicMock()
        mock_console_class.return_value = mock_console_instance

        tracker = SessionTracker(
            session_id="session3",
            start_time=time.time(),
            console=None,
        )

        assert tracker.console is not None

    def test_start_task(self) -> None:
        """Verify start_task creates and tracks task."""
        tracker = SessionTracker(
            session_id="session4",
            start_time=time.time(),
            console=MagicMock(),
        )

        tracker.start_task("task1", "Test Task", "Details here")

        assert "task1" in tracker.tasks
        task = tracker.tasks["task1"]
        assert task.id == "task1"
        assert task.name == "Test Task"
        assert task.status == "in_progress"
        assert task.details == "Details here"
        assert tracker.current_task == "task1"

    def test_complete_task(self) -> None:
        """Verify complete_task updates task status."""
        start_time = time.time()
        tracker = SessionTracker(
            session_id="session5",
            start_time=start_time,
            console=MagicMock(),
        )

        tracker.start_task("task1", "Test Task")
        tracker.complete_task("task1", "Task completed", ["file1.py"])

        task = tracker.tasks["task1"]
        assert task.status == "completed"
        assert task.details == "Task completed"
        assert task.files_changed == ["file1.py"]
        assert task.end_time is not None
        assert task.duration is not None
        assert tracker.current_task is None

    def test_complete_nonexistent_task(self) -> None:
        """Verify complete_task handles nonexistent task gracefully."""
        tracker = SessionTracker(
            session_id="session6",
            start_time=time.time(),
            console=MagicMock(),
        )

        # Should not raise error
        tracker.complete_task("nonexistent", "Details")
        assert "nonexistent" not in tracker.tasks

    def test_fail_task(self) -> None:
        """Verify fail_task updates task with error."""
        tracker = SessionTracker(
            session_id="session7",
            start_time=time.time(),
            console=MagicMock(),
        )

        tracker.start_task("task1", "Test Task")
        tracker.fail_task("task1", "Task failed due to error", "Error details")

        task = tracker.tasks["task1"]
        assert task.status == "failed"
        assert task.error_message == "Task failed due to error"
        assert task.details == "Error details"
        assert task.end_time is not None
        assert tracker.current_task is None

    def test_get_summary_empty(self) -> None:
        """Verify get_summary with no tasks."""
        start_time = time.time()
        tracker = SessionTracker(
            session_id="session8",
            start_time=start_time,
            console=MagicMock(),
        )

        summary = tracker.get_summary()

        assert summary["session_id"] == "session8"
        assert summary["total_tasks"] == 0
        assert summary["tasks_count"] == 0
        assert summary["completed"] == 0
        assert summary["failed"] == 0
        assert summary["in_progress"] == 0

    def test_get_summary_mixed_statuses(self) -> None:
        """Verify get_summary with various task statuses."""
        start_time = time.time()
        tracker = SessionTracker(
            session_id="session9",
            start_time=start_time,
            console=MagicMock(),
        )

        # Create tasks with different statuses
        tracker.start_task("task1", "Task 1")
        tracker.start_task("task2", "Task 2")
        tracker.complete_task("task2")
        tracker.start_task("task3", "Task 3")
        tracker.fail_task("task3", "Error")

        summary = tracker.get_summary()

        assert summary["total_tasks"] == 3
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["in_progress"] == 1
        assert summary["current_task"] is None

    def test_update_progress_file_no_file(self) -> None:
        """Verify _update_progress_file handles missing file path."""
        tracker = SessionTracker(
            session_id="session10",
            start_time=time.time(),
            console=MagicMock(),
            progress_file=None,
        )

        # Should not raise error
        tracker._update_progress_file()

    def test_update_progress_file_writes_json(self, tmp_path: Path) -> None:
        """Verify _update_progress_file writes progress to file."""
        progress_file = tmp_path / "progress.json"

        tracker = SessionTracker(
            session_id="session11",
            start_time=time.time(),
            console=MagicMock(),
            progress_file=str(progress_file),
        )

        tracker.start_task("task1", "Test Task")
        tracker.metadata["key"] = "value"
        tracker._update_progress_file()

        assert progress_file.exists()
        content = json.loads(progress_file.read_text())
        assert content["session_id"] == "session11"
        assert content["current_task"] == "task1"
        assert content["metadata"]["key"] == "value"

    def test_update_progress_file_handles_os_error(self) -> None:
        """Verify _update_progress_file handles write errors."""
        tracker = SessionTracker(
            session_id="session12",
            start_time=time.time(),
            console=MagicMock(),
            progress_file="/invalid/nonexistent/path/progress.json",
        )

        # Should not raise error
        tracker._update_progress_file()
