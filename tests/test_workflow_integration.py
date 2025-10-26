from pathlib import Path

import pytest
from rich.console import Console

from crackerjack.core.session_coordinator import SessionTracker
from crackerjack.models.task import HookResult, TaskStatusData


class TestHookResult:
    def test_hook_result_initialization(self) -> None:
        hook = HookResult(
            id="test - hook",
            name="Test Hook",
            status="passed",
            duration=1.5,
            files_processed=10,
        )
        assert hook.id == "test - hook"
        assert hook.name == "Test Hook"
        assert hook.status == "passed"
        assert hook.duration == 1.5
        assert hook.files_processed == 10
        assert hook.issues_found == []
        assert hook.stage == "pre-commit"

    def test_hook_result_post_init_issues(self) -> None:
        hook = HookResult(
            id="test - hook",
            name="Test Hook",
            status="failed",
            duration=2.0,
            issues_found=None,
        )
        assert hook.issues_found == []

    def test_hook_result_with_issues(self) -> None:
        issues = ["Issue 1", "Issue 2"]
        hook = HookResult(
            id="test - hook",
            name="Test Hook",
            status="failed",
            duration=2.0,
            issues_found=issues,
        )
        assert hook.issues_found == issues


class TestTaskStatus:
    def test_task_status_initialization(self) -> None:
        task = TaskStatusData(
            id="test - task",
            name="Test Task",
            status="pending",
        )
        assert task.id == "test - task"
        assert task.name == "Test Task"
        assert task.status == "pending"
        assert task.start_time is None
        assert task.end_time is None
        assert task.duration is None
        assert task.details is None
        assert task.error_message is None
        assert task.files_changed == []

    def test_task_status_post_init_files_changed(self) -> None:
        task = TaskStatusData(
            id="test - task",
            name="Test Task",
            status="pending",
            files_changed=None,
        )
        assert task.files_changed == []

    def test_task_status_duration_calculation(self) -> None:
        task = TaskStatusData(
            id="test - task",
            name="Test Task",
            status="completed",
            start_time=100.0,
            end_time=103.5,
        )
        assert task.duration == 3.5

    def test_task_status_with_details(self) -> None:
        files = ["file1.py", "file2.py"]
        task = TaskStatusData(
            id="test - task",
            name="Test Task",
            status="completed",
            details="Task completed successfully",
            files_changed=files,
        )
        assert task.details == "Task completed successfully"
        assert task.files_changed == files


class TestSessionTracker:
    @pytest.fixture
    def temp_progress_file(self, tmp_path: Path) -> Path:
        return tmp_path / "test - session.md"

    @pytest.fixture
    def session_tracker(self, temp_progress_file: Path) -> SessionTracker:
        console = Console()
        return SessionTracker(
            console=console,
            session_id="test - session - 123",
            start_time=1000.0,
            progress_file=temp_progress_file,
        )

    def test_session_tracker_initialization(
        self,
        session_tracker: SessionTracker,
    ) -> None:
        assert session_tracker.session_id == "test - session - 123"
        assert session_tracker.start_time == 1000.0
        assert not session_tracker.tasks
        assert session_tracker.current_task is None
        assert not session_tracker.metadata

    def test_session_tracker_start_task(self, session_tracker: SessionTracker) -> None:
        session_tracker.start_task("task1", "Test Task", "Task details")
        assert "task1" in session_tracker.tasks
        task = session_tracker.tasks["task1"]
        assert task.id == "task1"
        assert task.name == "Test Task"
        assert task.status == "in_progress"
        assert task.details == "Task details"
        assert task.start_time is not None
        assert session_tracker.current_task == "task1"

    def test_session_tracker_complete_task(
        self,
        session_tracker: SessionTracker,
    ) -> None:
        session_tracker.start_task("task1", "Test Task")
        session_tracker.complete_task(
            "task1",
            "Completed successfully",
            ["file1.py", "file2.py"],
        )

        task = session_tracker.tasks["task1"]
        assert task.status == "completed"
        assert task.end_time is not None
        assert task.duration is not None
        assert task.details == "Completed successfully"
        assert task.files_changed == ["file1.py", "file2.py"]

    def test_session_tracker_fail_task(self, session_tracker: SessionTracker) -> None:
        session_tracker.start_task("task1", "Test Task")
        session_tracker.fail_task("task1", "Error details", "Task failed")
        task = session_tracker.tasks["task1"]
        assert task.status == "failed"
        assert task.end_time is not None
        assert task.duration is not None
        assert task.error_message == "Error details"

    def test_session_tracker_nonexistent_task_operations(
        self,
        session_tracker: SessionTracker,
    ) -> None:
        session_tracker.complete_task("nonexistent", "Complete")
        session_tracker.fail_task("nonexistent", "Error", "Fail")


class TestWorkflowIntegration:
    def test_hook_result_task_status_compatibility(self) -> None:
        hook = HookResult(
            id="test - hook",
            name="Test Hook",
            status="passed",
            duration=1.5,
            files_processed=5,
        )
        task = TaskStatusData(
            id="hook - task",
            name="Run Hook",
            status="completed",
            start_time=100.0,
            end_time=101.5,
            details=f"Hook {hook.name} processed {hook.files_processed} files",
        )
        assert task.duration == hook.duration
        assert task.details is not None
        assert hook.name in task.details
        assert task.details is not None
        assert str(hook.files_processed) in task.details

    def test_session_tracker_with_multiple_tasks(self, tmp_path: Path) -> None:
        progress_file = tmp_path / "session.md"
        console = Console()
        tracker = SessionTracker(
            console=console,
            session_id="multi - task - session",
            start_time=1000.0,
            progress_file=progress_file,
        )
        tracker.start_task("setup", "Setup Environment")
        tracker.complete_task("setup", "Environment ready")
        tracker.start_task("test", "Run Tests")
        tracker.complete_task(
            "test",
            "All tests passed",
            ["test1.py", "test2.py"],
        )
        tracker.start_task("deploy", "Deploy Package")
        tracker.fail_task("deploy", "Network timeout", "Deployment failed")
        assert len(tracker.tasks) == 3
        assert tracker.tasks["setup"].status == "completed"
        assert tracker.tasks["test"].status == "completed"
        assert tracker.tasks["test"].files_changed == ["test1.py", "test2.py"]
        assert tracker.tasks["deploy"].status == "failed"
        assert tracker.tasks["deploy"].error_message == "Network timeout"
