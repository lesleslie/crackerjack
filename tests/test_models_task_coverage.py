import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.models.task import HookResult, SessionTracker, TaskStatusData


class TestHookResult:
    def test_hook_result_creation_minimal(self) -> None:
        result = HookResult(
            id="test - hook",
            name="Test Hook",
            status="passed",
            duration=1.5,
        )

        assert result.id == "test - hook"
        assert result.name == "Test Hook"
        assert result.status == "passed"
        assert result.duration == 1.5
        assert result.files_processed == 0
        assert result.issues_found == []
        assert result.stage == "fast"

    def test_hook_result_creation_full(self) -> None:
        result = HookResult(
            id="full - hook",
            name="Full Hook",
            status="failed",
            duration=2.3,
            files_processed=5,
            issues_found=["error1", "error2"],
            stage="comprehensive",
        )

        assert result.id == "full - hook"
        assert result.name == "Full Hook"
        assert result.status == "failed"
        assert result.duration == 2.3
        assert result.files_processed == 5
        assert result.issues_found == ["error1", "error2"]
        assert result.stage == "comprehensive"

    def test_hook_result_post_init_none_issues(self) -> None:
        result = HookResult(
            id="test",
            name="Test",
            status="passed",
            duration=1.0,
            issues_found=None,
        )

        assert result.issues_found == []

    def test_hook_result_post_init_existing_issues(self) -> None:
        issues = ["issue1", "issue2"]
        result = HookResult(
            id="test",
            name="Test",
            status="failed",
            duration=1.0,
            issues_found=issues,
        )

        assert result.issues_found == issues
        assert result.issues_found is issues


class TestTaskStatus:
    def test_task_status_creation_minimal(self) -> None:
        status = TaskStatusData(id="task - 1", name="Test Task", status="pending")

        assert status.id == "task - 1"
        assert status.name == "Test Task"
        assert status.status == "pending"
        assert status.start_time is None
        assert status.end_time is None
        assert status.duration is None
        assert status.details is None
        assert status.error_message is None
        assert status.files_changed == []

    def test_task_status_creation_full(self) -> None:
        start_time = time.time()
        end_time = start_time + 5.0
        files = ["file1.py", "file2.py"]

        status = TaskStatusData(
            id="full - task",
            name="Full Task",
            status="completed",
            start_time=start_time,
            end_time=end_time,
            duration=5.0,
            details="Task completed successfully",
            error_message=None,
            files_changed=files,
        )

        assert status.id == "full - task"
        assert status.name == "Full Task"
        assert status.status == "completed"
        assert status.start_time == start_time
        assert status.end_time == end_time
        assert status.duration == 5.0
        assert status.details == "Task completed successfully"
        assert status.error_message is None
        assert status.files_changed == files

    def test_task_status_post_init_none_files_changed(self) -> None:
        status = TaskStatusData(
            id="test",
            name="Test",
            status="pending",
            files_changed=None,
        )

        assert status.files_changed == []

    def test_task_status_post_init_existing_files_changed(self) -> None:
        files = ["file1.py", "file2.py"]
        status = TaskStatusData(
            id="test",
            name="Test",
            status="pending",
            files_changed=files,
        )

        assert status.files_changed == files
        assert status.files_changed is files

    def test_task_status_post_init_duration_calculation(self) -> None:
        start_time = 1000.0
        end_time = 1005.5

        status = TaskStatusData(
            id="test",
            name="Test",
            status="completed",
            start_time=start_time,
            end_time=end_time,
        )

        assert status.duration == 5.5

    def test_task_status_post_init_no_duration_calculation(self) -> None:
        status = TaskStatusData(
            id="test",
            name="Test",
            status="pending",
            start_time=None,
            end_time=None,
        )

        assert status.duration is None

        status2 = TaskStatusData(
            id="test2",
            name="Test2",
            status="in_progress",
            start_time=1000.0,
            end_time=None,
        )

        assert status2.duration is None

        status3 = TaskStatusData(
            id="test3",
            name="Test3",
            status="completed",
            start_time=None,
            end_time=1005.0,
        )

        assert status3.duration is None


class TestSessionTracker:
    @pytest.fixture
    def console(self):
        return Mock(spec=Console)

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def session_tracker(self, console, temp_dir):
        return SessionTracker(
            console=console,
            session_id="test - session",
            start_time=time.time(),
            progress_file=temp_dir / "progress.json",
        )

    def test_session_tracker_creation(self, console, temp_dir) -> None:
        start_time = time.time()
        progress_file = temp_dir / "progress.json"

        tracker = SessionTracker(
            console=console,
            session_id="test - session",
            start_time=start_time,
            progress_file=progress_file,
        )

        assert tracker.console == console
        assert tracker.session_id == "test - session"
        assert tracker.start_time == start_time
        assert tracker.progress_file == progress_file
        assert tracker.tasks == {}
        assert tracker.current_task is None
        assert tracker.metadata == {}

    def test_session_tracker_init_with_existing_data(self, console, temp_dir) -> None:
        existing_tasks = {"task1": TaskStatusData("task1", "Task 1", "completed")}
        existing_metadata = {"key": "value"}

        tracker = SessionTracker(
            console=console,
            session_id="test - session",
            start_time=time.time(),
            progress_file=temp_dir / "progress.json",
            tasks=existing_tasks,
            metadata=existing_metadata,
        )

        assert tracker.tasks == existing_tasks
        assert tracker.metadata == existing_metadata

    def test_session_tracker_init_empty_collections(self, console, temp_dir) -> None:
        tracker = SessionTracker(
            console=console,
            session_id="test - session",
            start_time=time.time(),
            progress_file=temp_dir / "progress.json",
        )

        assert tracker.tasks == {}
        assert tracker.metadata == {}

    def test_start_task_basic(self, session_tracker) -> None:
        session_tracker.start_task("task1", "Test Task")

        assert "task1" in session_tracker.tasks
        task = session_tracker.tasks["task1"]
        assert task.id == "task1"
        assert task.name == "Test Task"
        assert task.status == "in_progress"
        assert task.start_time is not None
        assert task.details is None
        assert session_tracker.current_task == "task1"

        session_tracker.console.print.assert_called_with(
            "[yellow]⏳[/ yellow] Started: Test Task",
        )

    def test_start_task_with_details(self, session_tracker) -> None:
        session_tracker.start_task("task2", "Detailed Task", details="Task details")

        task = session_tracker.tasks["task2"]
        assert task.details == "Task details"

    def test_complete_task_existing(self, session_tracker) -> None:
        session_tracker.start_task("task1", "Test Task")
        start_time = session_tracker.tasks["task1"].start_time

        session_tracker.complete_task("task1", details="Completed successfully")

        task = session_tracker.tasks["task1"]
        assert task.status == "completed"
        assert task.end_time is not None
        assert task.duration is not None
        assert task.duration == task.end_time - start_time
        assert task.details == "Completed successfully"
        assert session_tracker.current_task is None

        session_tracker.console.print.assert_called_with(
            "[green]✅[/ green] Completed: Test Task",
        )

    def test_complete_task_with_files_changed(self, session_tracker) -> None:
        session_tracker.start_task("task1", "Test Task")
        files_changed = ["file1.py", "file2.py"]

        session_tracker.complete_task("task1", files_changed=files_changed)

        task = session_tracker.tasks["task1"]
        assert task.files_changed == files_changed

    def test_complete_task_nonexistent(self, session_tracker) -> None:
        session_tracker.complete_task("nonexistent", details="Details")

        assert "nonexistent" not in session_tracker.tasks
        session_tracker.console.print.assert_not_called()

    def test_complete_task_different_current_task(self, session_tracker) -> None:
        session_tracker.start_task("task1", "Task 1")
        session_tracker.start_task("task2", "Task 2")

        session_tracker.complete_task("task1")

        assert session_tracker.tasks["task1"].status == "completed"
        assert session_tracker.current_task == "task2"

    def test_fail_task_existing(self, session_tracker) -> None:
        session_tracker.start_task("task1", "Test Task")
        start_time = session_tracker.tasks["task1"].start_time

        session_tracker.fail_task("task1", "Task failed", details="Error details")

        task = session_tracker.tasks["task1"]
        assert task.status == "failed"
        assert task.end_time is not None
        assert task.duration is not None
        assert task.duration == task.end_time - start_time
        assert task.error_message == "Task failed"
        assert task.details == "Error details"
        assert session_tracker.current_task is None

        session_tracker.console.print.assert_called_with(
            "[red]❌[/ red] Failed: Test Task - Task failed",
        )

    def test_fail_task_nonexistent(self, session_tracker) -> None:
        session_tracker.fail_task("nonexistent", "Error message")

        assert "nonexistent" not in session_tracker.tasks
        session_tracker.console.print.assert_not_called()

    def test_fail_task_different_current_task(self, session_tracker) -> None:
        session_tracker.start_task("task1", "Task 1")
        session_tracker.start_task("task2", "Task 2")

        session_tracker.fail_task("task1", "Error occurred")

        assert session_tracker.tasks["task1"].status == "failed"
        assert session_tracker.current_task == "task2"

    def test_update_progress_file(self, session_tracker) -> None:
        session_tracker._update_progress_file()

    def test_get_summary_empty(self, session_tracker) -> None:
        summary = session_tracker.get_summary()

        assert summary["session_id"] == "test - session"
        assert summary["duration"] >= 0
        assert summary["total_tasks"] == 0
        assert summary["completed"] == 0
        assert summary["failed"] == 0
        assert summary["in_progress"] == 0
        assert summary["current_task"] is None

    def test_get_summary_with_tasks(self, session_tracker) -> None:
        session_tracker.start_task("task1", "Task 1")
        session_tracker.complete_task("task1")

        session_tracker.start_task("task2", "Task 2")
        session_tracker.fail_task("task2", "Error")

        session_tracker.start_task("task3", "Task 3")

        summary = session_tracker.get_summary()

        assert summary["session_id"] == "test - session"
        assert summary["total_tasks"] == 3
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["in_progress"] == 1
        assert summary["current_task"] == "task3"

    def test_get_summary_duration_calculation(self, session_tracker) -> None:
        start_time = session_tracker.start_time

        summary = session_tracker.get_summary()

        expected_duration = time.time() - start_time
        assert abs(summary["duration"] - expected_duration) < 1.0


class TestTaskStatusEdgeCases:
    def test_task_status_duration_calculation_zero_start_time(self) -> None:
        status = TaskStatusData(
            id="test",
            name="Test",
            status="completed",
            start_time=0.0,
            end_time=5.0,
        )

        assert status.duration == 5.0

    def test_task_status_negative_duration(self) -> None:
        status = TaskStatusData(
            id="test",
            name="Test",
            status="completed",
            start_time=10.0,
            end_time=5.0,
        )

        assert status.duration == -5.0


class TestSessionTrackerIntegration:
    def test_full_task_lifecycle(self) -> None:
        console = Mock(spec=Console)
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = SessionTracker(
                console=console,
                session_id="integration - test",
                start_time=time.time(),
                progress_file=Path(temp_dir) / "progress.json",
            )

            tracker.start_task("lifecycle", "Lifecycle Task", details="Starting task")

            assert tracker.current_task == "lifecycle"
            task = tracker.tasks["lifecycle"]
            assert task.status == "in_progress"
            assert task.details == "Starting task"

            tracker.complete_task(
                "lifecycle",
                details="Task finished",
                files_changed=["test.py"],
            )

            assert tracker.current_task is None
            assert task.status == "completed"
            assert task.details == "Task finished"
            assert task.files_changed == ["test.py"]

            summary = tracker.get_summary()
            assert summary["total_tasks"] == 1
            assert summary["completed"] == 1
            assert summary["failed"] == 0
            assert summary["in_progress"] == 0

    def test_multiple_tasks_workflow(self) -> None:
        console = Mock(spec=Console)
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = SessionTracker(
                console=console,
                session_id="multi - test",
                start_time=time.time(),
                progress_file=Path(temp_dir) / "progress.json",
            )

            tracker.start_task("task1", "Task 1")
            tracker.start_task("task2", "Task 2")
            tracker.start_task("task3", "Task 3")

            tracker.complete_task("task1")
            tracker.fail_task("task2", "Task 2 failed")

            summary = tracker.get_summary()
            assert summary["total_tasks"] == 3
            assert summary["completed"] == 1
            assert summary["failed"] == 1
            assert summary["in_progress"] == 1
            assert summary["current_task"] == "task3"
