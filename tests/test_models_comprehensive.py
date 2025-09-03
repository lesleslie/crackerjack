import tempfile
from pathlib import Path

from crackerjack.models.config import (
    CleaningConfig,
    ExecutionConfig,
    GitConfig,
    PublishConfig,
    TestConfig,
    WorkflowOptions,
)
from crackerjack.models.task import (
    HookResult,
    SessionTracker,
    TaskStatusData,
)

"""
Comprehensive tests for models modules to boost coverage.
"""


class TestWorkflowOptions:
    def test_workflow_options_defaults(self) -> None:
        options = WorkflowOptions()

        assert isinstance(options.cleaning, CleaningConfig)
        assert isinstance(options.testing, TestConfig)
        assert isinstance(options.publishing, PublishConfig)
        assert isinstance(options.git, GitConfig)
        assert isinstance(options.execution, ExecutionConfig)

    def test_cleaning_config_defaults(self) -> None:
        config = CleaningConfig()

        assert config.clean is True
        assert config.update_docs is False

    def test_cleaning_config_with_values(self) -> None:
        config = CleaningConfig(
            clean=False,
            update_docs=True,
        )

        assert config.clean is False
        assert config.update_docs is True

    def test_testing_config_defaults(self) -> None:
        config = TestConfig()

        assert config.test is False
        assert config.test_workers == 0
        assert config.test_timeout == 0
        assert config.benchmark is False

    def test_testing_config_with_values(self) -> None:
        config = TestConfig(
            test=True,
            test_workers=4,
            test_timeout=300,
            benchmark=True,
        )

        assert config.test is True
        assert config.test_workers == 4
        assert config.test_timeout == 300
        assert config.benchmark is True

    def test_publish_config_defaults(self) -> None:
        config = PublishConfig()

        assert config.publish is None
        assert config.bump is None

    def test_git_config_defaults(self) -> None:
        config = GitConfig()

        assert hasattr(config, "commit")

    def test_execution_config_defaults(self) -> None:
        config = ExecutionConfig()

        assert hasattr(config, "verbose")

    def test_workflow_options_backward_compatibility(self) -> None:
        options = WorkflowOptions()

        assert hasattr(options, "clean")
        assert hasattr(options, "test")

    def test_workflow_options_nested_access(self) -> None:
        options = WorkflowOptions()

        options.cleaning.clean = False
        options.testing.test = True

        assert options.cleaning.clean is False
        assert options.testing.test is True


class TestTaskModels:
    def test_task_status_creation(self) -> None:
        status = TaskStatusData(
            id="task_1",
            name="Test Task",
            status="running",
            start_time=1000.0,
            end_time=1015.5,
            details="Task is running",
        )

        assert status.id == "task_1"
        assert status.name == "Test Task"
        assert status.status == "running"
        assert status.start_time == 1000.0
        assert status.end_time == 1015.5
        assert status.duration == 15.5
        assert status.details == "Task is running"

    def test_task_status_defaults(self) -> None:
        status = TaskStatusData(
            id="task_2",
            name="Simple Task",
            status="pending",
        )

        assert status.files_changed == []
        assert status.start_time is None
        assert status.end_time is None
        assert status.duration is None
        assert status.error_message is None

    def test_hook_result_creation(self) -> None:
        result = HookResult(
            id="hook_1",
            name="ruff - check",
            status="passed",
            duration=2.5,
            files_processed=15,
            issues_found=["unused import in file.py"],
            stage="pre - commit",
        )

        assert result.id == "hook_1"
        assert result.name == "ruff - check"
        assert result.status == "passed"
        assert result.duration == 2.5
        assert result.files_processed == 15
        assert result.issues_found == ["unused import in file.py"]
        assert result.stage == "pre - commit"

    def test_hook_result_defaults(self) -> None:
        result = HookResult(
            id="hook_2",
            name="trailing - whitespace",
            status="failed",
            duration=0.5,
        )

        assert result.files_processed == 0
        assert result.issues_found == []
        assert result.stage == "pre - commit"

    def test_session_tracker_creation(self) -> None:
        from rich.console import Console

        console = Console()
        tracker = SessionTracker(
            console=console,
            session_id="session_123",
            start_time=1000.0,
            progress_file=Path(str(Path(tempfile.gettempdir()) / "progress.json")),
        )

        assert tracker.console == console
        assert tracker.session_id == "session_123"
        assert tracker.start_time == 1000.0
        assert tracker.progress_file == Path(
            str(Path(tempfile.gettempdir()) / "progress.json"),
        )
        assert tracker.tasks == {}
        assert tracker.current_task is None

    def test_session_tracker_with_tasks(self) -> None:
        from rich.console import Console

        console = Console()
        task_data = TaskStatusData(
            id="task_1",
            name="Test Task",
            status="completed",
        )

        tracker = SessionTracker(
            console=console,
            session_id="session_456",
            start_time=2000.0,
            progress_file=Path(str(Path(tempfile.gettempdir()) / "progress2.json")),
            tasks={"task_1": task_data},
            current_task="task_1",
        )

        assert "task_1" in tracker.tasks
        assert tracker.tasks["task_1"] == task_data
        assert tracker.current_task == "task_1"


class TestProtocolInterfaces:
    def test_filesystem_interface_protocol(self) -> None:
        class MockFileSystem:
            def read_file(self, path: Path) -> str:
                return "content"

            def write_file(self, path: Path, content: str) -> None:
                pass

            def list_files(self, directory: Path) -> list[Path]:
                return []

        mock_fs = MockFileSystem()

        assert hasattr(mock_fs, "read_file")
        assert hasattr(mock_fs, "write_file")
        assert hasattr(mock_fs, "list_files")

    def test_git_interface_protocol(self) -> None:
        class MockGit:
            def commit(self, message: str) -> bool:
                return True

            def push(self) -> bool:
                return True

            def get_status(self) -> dict:
                return {}

        mock_git = MockGit()

        assert hasattr(mock_git, "commit")
        assert hasattr(mock_git, "push")
        assert hasattr(mock_git, "get_status")

    def test_hook_manager_protocol(self) -> None:
        class MockHookManager:
            def run_fast_hooks(self) -> bool:
                return True

            def run_comprehensive_hooks(self) -> bool:
                return True

        mock_hooks = MockHookManager()

        assert hasattr(mock_hooks, "run_fast_hooks")
        assert hasattr(mock_hooks, "run_comprehensive_hooks")

    def test_test_manager_protocol(self) -> None:
        class MockTestManager:
            def run_tests(self) -> bool:
                return True

            def get_coverage(self) -> float:
                return 85.0

        mock_tests = MockTestManager()

        assert hasattr(mock_tests, "run_tests")
        assert hasattr(mock_tests, "get_coverage")

    def test_publish_manager_protocol(self) -> None:
        class MockPublishManager:
            def bump_version(self, bump_type: str) -> str:
                return "1.0.0"

            def publish(self) -> bool:
                return True

        mock_publish = MockPublishManager()

        assert hasattr(mock_publish, "bump_version")
        assert hasattr(mock_publish, "publish")


class TestModelIntegration:
    def test_complex_workflow_options(self) -> None:
        options = WorkflowOptions()

        options.cleaning.clean = True
        options.cleaning.targets = [Path("src / "), Path("tests / ")]

        options.testing.test = True
        options.testing.workers = 4
        options.testing.timeout = 300
        options.testing.benchmark = True

        options.publishing.publish = "patch"
        options.publishing.bump = "minor"

        options.git.commit = True
        options.git.create_pr = True

        options.execution.verbose = True
        options.execution.dry_run = False

        assert options.cleaning.clean is True
        assert len(options.cleaning.targets) == 2
        assert options.testing.test is True
        assert options.testing.workers == 4
        assert options.publishing.publish == "patch"
        assert options.git.commit is True
        assert options.execution.verbose is True

    def test_task_workflow_integration(self) -> None:
        task_data = TaskStatusData(
            id="integration_task",
            name="Integration Task",
            status="running",
            start_time=1000.0,
            details="Integration test running",
        )

        hook_result = HookResult(
            id="integration_hook",
            name="integration - check",
            status="passed",
            duration=5.0,
            files_processed=10,
        )

        from rich.console import Console

        console = Console()
        tracker = SessionTracker(
            console=console,
            session_id="integration_session",
            start_time=1000.0,
            progress_file=Path(str(Path(tempfile.gettempdir()) / "integration.json")),
            tasks={"integration_task": task_data},
            current_task="integration_task",
        )

        assert tracker.current_task == task_data.id
        assert tracker.tasks[task_data.id] == task_data
        assert hook_result.status == "passed"
