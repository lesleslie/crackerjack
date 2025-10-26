from pathlib import Path
from unittest.mock import MagicMock

import pytest

from acb.console import Console
from acb.depends import depends
from crackerjack.core.session_coordinator import SessionCoordinator


@pytest.fixture
def mock_console():
    """Fixture providing a mock console for tests."""
    return MagicMock(spec=Console)


@pytest.fixture
def pkg_path():
    """Fixture providing a test package path."""
    return Path("/tmp/test_crackerjack")


def test_session_coordinator_initialization(mock_console, pkg_path) -> None:
    """Test basic SessionCoordinator initialization."""
    # Set up dependency injection by registering mock console with ACB depends system
    original_console = depends.get_sync(Console)
    try:
        depends.set(Console, mock_console)
        coordinator = SessionCoordinator(console=mock_console, pkg_path=pkg_path)

        assert coordinator.session_id is not None
        assert coordinator.pkg_path == pkg_path
        assert coordinator.console == mock_console
        assert coordinator.start_time > 0
        assert isinstance(coordinator.tasks, dict)
        assert len(coordinator.tasks) == 0
    finally:
        # Restore original console
        depends.set(Console, original_console)


def test_session_coordinator_with_web_job_id(mock_console, pkg_path) -> None:
    """Test SessionCoordinator with web job ID."""
    web_job_id = "test-job-123"
    original_console = depends.get_sync(Console)
    try:
        depends.set(Console, mock_console)
        coordinator = SessionCoordinator(
            console=mock_console, pkg_path=pkg_path, web_job_id=web_job_id
        )

        assert coordinator.session_id == web_job_id
        assert coordinator.web_job_id == web_job_id
    finally:
        depends.set(Console, original_console)


def test_session_coordinator_start_session(mock_console, pkg_path) -> None:
    """Test starting a session task."""
    original_console = depends.get_sync(Console)
    try:
        depends.set(Console, mock_console)
        coordinator = SessionCoordinator(console=mock_console, pkg_path=pkg_path)

        task_name = "test_task"
        coordinator.start_session(task_name)

        assert coordinator.current_task == task_name
    finally:
        depends.set(Console, original_console)


def test_session_coordinator_track_task(mock_console, pkg_path) -> None:
    """Test tracking a task within a session."""
    original_console = depends.get_sync(Console)
    try:
        depends.set(Console, mock_console)
        coordinator = SessionCoordinator(console=mock_console, pkg_path=pkg_path)

        task_id = "task_123"
        task_name = "test_task"
        result_id = coordinator.track_task(task_id, task_name)

        assert result_id == task_id
        assert task_id in coordinator.tasks
        task = coordinator.tasks[task_id]
        assert task.id == task_id
        assert task.name == task_name
        assert task.status == "in_progress"
        assert task.start_time is not None and task.start_time > 0
    finally:
        depends.set(Console, original_console)
