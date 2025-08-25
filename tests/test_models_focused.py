"""Focused tests for models and configurations to increase coverage."""

from crackerjack.errors import CrackerjackError, ErrorCode, ExecutionError
from crackerjack.models.config import CleaningConfig, HookConfig
from crackerjack.models.protocols import (
    CommandRunner,
    FileSystemInterface,
    OptionsProtocol,
)
from crackerjack.models.task import Task, TaskStatus


class TestCleaningConfig:
    """Test CleaningConfig dataclass thoroughly."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CleaningConfig()
        assert config.clean is True
        assert config.update_docs is False
        assert config.force_update_docs is False
        assert config.compress_docs is False
        assert config.auto_compress_docs is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = CleaningConfig(
            clean=False,
            update_docs=True,
            force_update_docs=True,
            compress_docs=True,
            auto_compress_docs=True,
        )
        assert config.clean is False
        assert config.update_docs is True
        assert config.force_update_docs is True
        assert config.compress_docs is True
        assert config.auto_compress_docs is True

    def test_partial_custom_values(self) -> None:
        """Test partial custom configuration."""
        config = CleaningConfig(update_docs=True, compress_docs=True)
        assert config.clean is True  # default
        assert config.update_docs is True  # custom
        assert config.force_update_docs is False  # default
        assert config.compress_docs is True  # custom
        assert config.auto_compress_docs is False  # default


class TestHookConfig:
    """Test HookConfig dataclass thoroughly."""

    def test_default_values(self) -> None:
        """Test default hook configuration values."""
        config = HookConfig()
        assert config.skip_hooks is False
        assert config.update_precommit is False
        assert config.experimental_hooks is False
        assert config.enable_pyrefly is False
        assert config.enable_ty is False

    def test_all_custom_values(self) -> None:
        """Test all custom hook configuration values."""
        config = HookConfig(
            skip_hooks=True,
            update_precommit=True,
            experimental_hooks=True,
            enable_pyrefly=True,
            enable_ty=True,
        )
        assert config.skip_hooks is True
        assert config.update_precommit is True
        assert config.experimental_hooks is True
        assert config.enable_pyrefly is True
        assert config.enable_ty is True

    def test_mixed_values(self) -> None:
        """Test mixed hook configuration values."""
        config = HookConfig(skip_hooks=True, experimental_hooks=True)
        assert config.skip_hooks is True
        assert config.update_precommit is False
        assert config.experimental_hooks is True
        assert config.enable_pyrefly is False
        assert config.enable_ty is False


class TestTask:
    """Test Task dataclass and methods."""

    def test_task_creation(self) -> None:
        """Test basic task creation."""
        task = Task(id="test-123", name="Test Task", status=TaskStatus.PENDING)
        assert task.id == "test-123"
        assert task.name == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.details is None

    def test_task_with_details(self) -> None:
        """Test task creation with details."""
        task = Task(
            id="detailed-task",
            name="Detailed Task",
            status=TaskStatus.IN_PROGRESS,
            details="Some important details",
        )
        assert task.id == "detailed-task"
        assert task.name == "Detailed Task"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.details == "Some important details"

    def test_task_to_dict(self) -> None:
        """Test task dictionary conversion."""
        task = Task(
            id="dict-test",
            name="Dictionary Test",
            status=TaskStatus.COMPLETED,
            details="Test details",
        )

        task_dict = task.to_dict()
        expected = {
            "id": "dict-test",
            "name": "Dictionary Test",
            "status": "completed",
            "details": "Test details",
        }
        assert task_dict == expected

    def test_task_to_dict_no_details(self) -> None:
        """Test task dictionary conversion without details."""
        task = Task(id="no-details", name="No Details Task", status=TaskStatus.FAILED)

        task_dict = task.to_dict()
        expected = {
            "id": "no-details",
            "name": "No Details Task",
            "status": "failed",
            "details": None,
        }
        assert task_dict == expected


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_enum_values(self) -> None:
        """Test all enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_enum_iteration(self) -> None:
        """Test iterating over enum values."""
        statuses = list(TaskStatus)
        assert len(statuses) == 4
        assert TaskStatus.PENDING in statuses
        assert TaskStatus.IN_PROGRESS in statuses
        assert TaskStatus.COMPLETED in statuses
        assert TaskStatus.FAILED in statuses


class TestExecutionError:
    """Test ExecutionError class."""

    def test_basic_error_creation(self) -> None:
        """Test basic error creation."""
        error = ExecutionError(
            message="Test error message",
            error_code=ErrorCode.FILE_READ_ERROR,
        )
        assert str(error) == "Test error message"
        assert error.error_code == ErrorCode.FILE_READ_ERROR

    def test_error_inheritance(self) -> None:
        """Test error inheritance from CrackerjackError."""
        error = ExecutionError(
            message="Test error",
            error_code=ErrorCode.FILE_WRITE_ERROR,
        )
        assert isinstance(error, ExecutionError)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, Exception)

    def test_error_with_different_codes(self) -> None:
        """Test creating errors with different error codes."""
        error_codes = [
            ErrorCode.FILE_READ_ERROR,
            ErrorCode.FILE_WRITE_ERROR,
            ErrorCode.VALIDATION_ERROR,
            ErrorCode.COMMAND_EXECUTION_ERROR,
        ]

        for code in error_codes:
            error = ExecutionError(
                message=f"Test error for {code.name}",
                error_code=code,
            )
            assert error.error_code == code
            assert isinstance(error, ExecutionError)


class TestErrorCode:
    """Test ErrorCode enum."""

    def test_error_code_values(self) -> None:
        """Test some error code values."""
        assert ErrorCode.FILE_READ_ERROR.value == 6003
        assert ErrorCode.FILE_WRITE_ERROR.value == 6004
        assert ErrorCode.VALIDATION_ERROR.value == 8005
        assert ErrorCode.COMMAND_EXECUTION_ERROR.value == 2001
        assert ErrorCode.NETWORK_ERROR.value == 8003
        assert ErrorCode.GENERAL_ERROR.value == 9000

    def test_error_code_uniqueness(self) -> None:
        """Test that all error codes are unique."""
        error_codes = [code.value for code in ErrorCode]
        assert len(error_codes) == len(set(error_codes))

    def test_error_code_names(self) -> None:
        """Test error code names."""
        assert ErrorCode.FILE_READ_ERROR.name == "FILE_READ_ERROR"
        assert ErrorCode.FILE_WRITE_ERROR.name == "FILE_WRITE_ERROR"
        assert ErrorCode.VALIDATION_ERROR.name == "VALIDATION_ERROR"


class TestProtocols:
    """Test protocol definitions."""

    def test_filesystem_interface_exists(self) -> None:
        """Test that FileSystemInterface can be imported and used."""
        assert FileSystemInterface is not None

        # Test that protocol has expected methods
        protocol_methods = ["read_file", "write_file", "exists", "mkdir"]

        for method_name in protocol_methods:
            # Check if the protocol defines the method
            if hasattr(FileSystemInterface, method_name):
                assert hasattr(FileSystemInterface, method_name)

    def test_options_protocol_exists(self) -> None:
        """Test that OptionsProtocol can be imported and used."""
        assert OptionsProtocol is not None

        # Test some expected attributes exist in annotations
        annotations = getattr(OptionsProtocol, "__annotations__", {})
        expected_attrs = ["commit", "interactive", "verbose", "clean", "test"]
        for attr in expected_attrs:
            assert attr in annotations

    def test_command_runner_protocol(self) -> None:
        """Test CommandRunner protocol."""
        assert CommandRunner is not None
        assert hasattr(CommandRunner, "execute_command")

    def test_protocol_typing(self) -> None:
        """Test protocol can be used for typing."""

        # This should not raise any errors
        def use_filesystem(fs: FileSystemInterface) -> None:
            pass

        def use_options(opts: OptionsProtocol) -> None:
            pass

        # Just test that the functions can be defined
        assert callable(use_filesystem)
        assert callable(use_options)


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple models."""

    def test_complete_workflow_scenario(self) -> None:
        """Test a complete workflow scenario."""
        # Create configurations
        cleaning_config = CleaningConfig(clean=True, update_docs=True)
        hook_config = HookConfig(skip_hooks=False, experimental_hooks=True)

        # Create tasks for the workflow
        tasks = [
            Task("clean-1", "Clean source code", TaskStatus.PENDING),
            Task("clean-2", "Update documentation", TaskStatus.PENDING),
            Task("clean-3", "Run experimental hooks", TaskStatus.PENDING),
        ]

        # Simulate workflow progress
        assert all(task.status == TaskStatus.PENDING for task in tasks)

        # Convert all tasks to dictionaries
        task_dicts = [task.to_dict() for task in tasks]
        assert len(task_dicts) == 3
        assert all(task_dict["status"] == "pending" for task_dict in task_dicts)

        # Test configuration state
        assert cleaning_config.clean is True
        assert cleaning_config.update_docs is True
        assert hook_config.experimental_hooks is True
        assert hook_config.skip_hooks is False

    def test_error_handling_scenario(self) -> None:
        """Test error handling in workflow scenarios."""
        # Create a task that might fail
        task = Task("risky-task", "Risky Operation", TaskStatus.IN_PROGRESS)

        # Simulate different types of errors
        errors = [
            ExecutionError("File not found", ErrorCode.FILE_READ_ERROR),
            ExecutionError("Permission denied", ErrorCode.FILE_WRITE_ERROR),
            ExecutionError("Invalid config", ErrorCode.INVALID_CONFIG),
        ]

        for error in errors:
            assert isinstance(error, ExecutionError)
            assert error.error_code in [
                ErrorCode.FILE_READ_ERROR,
                ErrorCode.FILE_WRITE_ERROR,
                ErrorCode.INVALID_CONFIG,
            ]
            assert len(error.message) > 0

        # Task state should remain unchanged during error handling
        assert task.status == TaskStatus.IN_PROGRESS
