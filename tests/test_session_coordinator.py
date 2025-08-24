"""Tests for SessionCoordinator class."""

from pathlib import Path

from rich.console import Console

from crackerjack.core.session_coordinator import SessionCoordinator


def test_session_coordinator_initialization() -> None:
    """Test SessionCoordinator initialization."""
    console = Console()
    pkg_path = Path("/tmp/test")
    coordinator = SessionCoordinator(console, pkg_path)

    assert coordinator.session_id is not None
    assert coordinator.pkg_path == pkg_path
    assert coordinator.console is console
    assert coordinator.start_time > 0
    assert isinstance(coordinator.tasks, dict)
    assert len(coordinator.tasks) == 0


def test_session_coordinator_with_web_job_id() -> None:
    """Test SessionCoordinator with web job ID."""
    console = Console()
    pkg_path = Path("/tmp/test")
    web_job_id = "test-job-123"
    coordinator = SessionCoordinator(console, pkg_path, web_job_id)

    assert coordinator.session_id == web_job_id
    assert coordinator.web_job_id == web_job_id


def test_session_coordinator_start_session() -> None:
    """Test starting a session task."""
    console = Console()
    pkg_path = Path("/tmp/test")
    coordinator = SessionCoordinator(console, pkg_path)

    task_name = "test_task"
    coordinator.start_session(task_name)

    # start_session only sets current_task, not tasks dict
    assert coordinator.current_task == task_name


def test_session_coordinator_track_task() -> None:
    """Test tracking a task."""
    console = Console()
    pkg_path = Path("/tmp/test")
    coordinator = SessionCoordinator(console, pkg_path)

    task_id = "task_123"
    task_name = "test_task"
    result_id = coordinator.track_task(task_id, task_name)

    assert result_id == task_id
    assert task_id in coordinator.tasks
    task = coordinator.tasks[task_id]
    assert task.task_id == task_id
    assert task.description == task_name
    assert task.status == "in_progress"
    assert task.start_time > 0
