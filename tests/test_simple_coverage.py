import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

from crackerjack.errors import (
    ConfigError,
    CrackerjackError,
    ExecutionError,
    TestExecutionError,
)
from crackerjack.models.config import HookConfig, PublishConfig, TestConfig
from crackerjack.models.protocols import (
    FileSystemInterface,
)
from crackerjack.models.protocols import (
    HookManager as HookManagerProtocol,
)
from crackerjack.models.task import HookResult, SessionTracker, TaskStatus

"""
Tests for simple modules to boost coverage without complex mocking.
"""


class TestHookResult:
    def test_hook_result_creation(self) -> None:
        result = HookResult(
            id="test - hook", name="Test Hook", status="passed", duration=1.5
        )

        assert result.id == "test - hook"
        assert result.name == "Test Hook"
        assert result.status == "passed"
        assert result.duration == 1.5
        assert result.files_processed == 0
        assert result.issues_found == []
        assert result.stage == "pre - commit"

    def test_hook_result_with_issues(self) -> None:
        result = HookResult(
            id="failed - hook",
            name="Failed Hook",
            status="failed",
            duration=2.0,
            files_processed=5,
            issues_found=["Issue 1", "Issue 2"],
            stage="comprehensive",
        )

        assert result.issues_found == ["Issue 1", "Issue 2"]
        assert result.files_processed == 5
        assert result.stage == "comprehensive"


class TestTaskStatus:
    def test_task_status_creation(self) -> None:
        status = TaskStatus(id="task - 1", name="Test Task", status="running")

        assert status.id == "task - 1"
        assert status.name == "Test Task"
        assert status.status == "running"
        assert status.files_changed == []

    def test_task_status_with_timing(self) -> None:
        start_time = time.time()
        end_time = start_time + 2.5

        status = TaskStatus(
            id="timed - task",
            name="Timed Task",
            status="completed",
            start_time=start_time,
            end_time=end_time,
        )

        assert status.duration == 2.5
        assert status.start_time == start_time
        assert status.end_time == end_time


class TestSessionTracker:
    def test_session_tracker_creation(self) -> None:
        from rich.console import Console

        console = Console()
        tracker = SessionTracker(
            console=console,
            session_id="test - session",
            start_time=time.time(),
            progress_file=Path(str(Path(tempfile.gettempdir()) / "progress.md")),
        )

        assert tracker.session_id == "test - session"
        assert tracker.console == console
        assert tracker.tasks == {}
        assert tracker.current_task is None


class TestProtocols:
    def test_hook_manager_protocol(self) -> None:
        assert HookManagerProtocol is not None

        mock_manager = Mock(spec=HookManagerProtocol)
        assert hasattr(mock_manager, "run_fast_hooks")

    def test_filesystem_interface(self) -> None:
        assert FileSystemInterface is not None

        mock_fs = Mock(spec=FileSystemInterface)
        assert hasattr(mock_fs, "read_file")
        assert hasattr(mock_fs, "write_file")


class TestConfigModels:
    def test_test_config_defaults(self) -> None:
        config = TestConfig()

        assert config.test is False
        assert config.benchmark is False
        assert config.test_workers == 0
        assert config.test_timeout == 0

    def test_hook_config_defaults(self) -> None:
        config = HookConfig()

        assert config.skip_hooks is False
        assert config.update_precommit is False
        assert config.experimental_hooks is False
        assert config.enable_pyrefly is False
        assert config.enable_ty is False

    def test_publish_config_defaults(self) -> None:
        config = PublishConfig()

        assert config.publish is None
        assert config.bump is None


class TestErrors:
    def test_error_imports(self) -> None:
        assert CrackerjackError is not None
        assert ConfigError is not None
        assert ExecutionError is not None
        assert TestExecutionError is not None


class TestCrackerjackModule:
    def test_module_imports(self) -> None:
        from crackerjack.api import CrackerjackAPI
        from crackerjack.code_cleaner import CodeCleaner
        from crackerjack.models.task import HookResult

        assert CrackerjackAPI is not None
        assert CodeCleaner is not None
        assert HookResult is not None

    def test_workflow_options_import(self) -> None:
        from crackerjack.models.config import WorkflowOptions

        options = WorkflowOptions()
        assert options.cleaning is not None
        assert options.hooks is not None
        assert options.testing is not None
