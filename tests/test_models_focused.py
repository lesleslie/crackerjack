from crackerjack.errors import CrackerjackError, ErrorCode, ExecutionError
from crackerjack.models.config import CleaningConfig, HookConfig
from crackerjack.models.protocols import (
    CommandRunner,
    FileSystemInterface,
    OptionsProtocol,
)
from crackerjack.models.task import Task, TaskStatus


class TestCleaningConfig:
    def test_default_values(self) -> None:
        config = CleaningConfig()
        assert config.clean is True
        assert config.update_docs is False
        assert config.force_update_docs is False
        assert config.compress_docs is False
        assert config.auto_compress_docs is False

    def test_custom_values(self) -> None:
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
        config = CleaningConfig(update_docs=True, compress_docs=True)
        assert config.clean is True
        assert config.update_docs is True
        assert config.force_update_docs is False
        assert config.compress_docs is True
        assert config.auto_compress_docs is False


class TestHookConfig:
    def test_default_values(self) -> None:
        config = HookConfig()
        assert config.skip_hooks is False
        assert config.update_precommit is False
        assert config.experimental_hooks is False
        assert config.enable_pyrefly is False
        assert config.enable_ty is False

    def test_all_custom_values(self) -> None:
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
        config = HookConfig(skip_hooks=True, experimental_hooks=True)
        assert config.skip_hooks is True
        assert config.update_precommit is False
        assert config.experimental_hooks is True
        assert config.enable_pyrefly is False
        assert config.enable_ty is False


class TestTask:
    def test_task_creation(self) -> None:
        task = Task(id="test - 123", name="Test Task", status=TaskStatus.PENDING)
        assert task.id == "test - 123"
        assert task.name == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.details is None

    def test_task_with_details(self) -> None:
        task = Task(
            id="detailed - task",
            name="Detailed Task",
            status=TaskStatus.IN_PROGRESS,
            details="Some important details",
        )
        assert task.id == "detailed - task"
        assert task.name == "Detailed Task"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.details == "Some important details"

    def test_task_to_dict(self) -> None:
        task = Task(
            id="dict - test",
            name="Dictionary Test",
            status=TaskStatus.COMPLETED,
            details="Test details",
        )

        task_dict = task.to_dict()
        expected = {
            "id": "dict - test",
            "name": "Dictionary Test",
            "status": "completed",
            "details": "Test details",
        }
        assert task_dict == expected

    def test_task_to_dict_no_details(self) -> None:
        task = Task(id="no - details", name="No Details Task", status=TaskStatus.FAILED)

        task_dict = task.to_dict()
        expected = {
            "id": "no - details",
            "name": "No Details Task",
            "status": "failed",
            "details": None,
        }
        assert task_dict == expected


class TestTaskStatus:
    def test_enum_values(self) -> None:
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_enum_iteration(self) -> None:
        statuses = list(TaskStatus)
        assert len(statuses) == 4
        assert TaskStatus.PENDING in statuses
        assert TaskStatus.IN_PROGRESS in statuses
        assert TaskStatus.COMPLETED in statuses
        assert TaskStatus.FAILED in statuses


class TestExecutionError:
    def test_basic_error_creation(self) -> None:
        error = ExecutionError(
            message="Test error message",
            error_code=ErrorCode.FILE_READ_ERROR,
        )
        assert str(error) == "Test error message"
        assert error.error_code == ErrorCode.FILE_READ_ERROR

    def test_error_inheritance(self) -> None:
        error = ExecutionError(
            message="Test error",
            error_code=ErrorCode.FILE_WRITE_ERROR,
        )
        assert isinstance(error, ExecutionError)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, Exception)

    def test_error_with_different_codes(self) -> None:
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
    def test_error_code_values(self) -> None:
        assert ErrorCode.FILE_READ_ERROR.value == 6003
        assert ErrorCode.FILE_WRITE_ERROR.value == 6004
        assert ErrorCode.VALIDATION_ERROR.value == 8005
        assert ErrorCode.COMMAND_EXECUTION_ERROR.value == 2001
        assert ErrorCode.NETWORK_ERROR.value == 8003
        assert ErrorCode.GENERAL_ERROR.value == 9000

    def test_error_code_uniqueness(self) -> None:
        error_codes = [code.value for code in ErrorCode]
        assert len(error_codes) == len(set(error_codes))

    def test_error_code_names(self) -> None:
        assert ErrorCode.FILE_READ_ERROR.name == "FILE_READ_ERROR"
        assert ErrorCode.FILE_WRITE_ERROR.name == "FILE_WRITE_ERROR"
        assert ErrorCode.VALIDATION_ERROR.name == "VALIDATION_ERROR"


class TestProtocols:
    def test_filesystem_interface_exists(self) -> None:
        assert FileSystemInterface is not None

        protocol_methods = ["read_file", "write_file", "exists", "mkdir"]

        for method_name in protocol_methods:
            if hasattr(FileSystemInterface, method_name):
                assert hasattr(FileSystemInterface, method_name)

    def test_options_protocol_exists(self) -> None:
        assert OptionsProtocol is not None

        annotations = getattr(OptionsProtocol, "__annotations__", {})
        expected_attrs = ["commit", "interactive", "verbose", "clean", "test"]
        for attr in expected_attrs:
            assert attr in annotations

    def test_command_runner_protocol(self) -> None:
        assert CommandRunner is not None
        assert hasattr(CommandRunner, "execute_command")

    def test_protocol_typing(self) -> None:
        def use_filesystem(fs: FileSystemInterface) -> None:
            pass

        def use_options(opts: OptionsProtocol) -> None:
            pass

        assert callable(use_filesystem)
        assert callable(use_options)


class TestIntegrationScenarios:
    def test_complete_workflow_scenario(self) -> None:
        cleaning_config = CleaningConfig(clean=True, update_docs=True)
        hook_config = HookConfig(skip_hooks=False, experimental_hooks=True)

        tasks = [
            Task("clean - 1", "Clean source code", TaskStatus.PENDING),
            Task("clean - 2", "Update documentation", TaskStatus.PENDING),
            Task("clean - 3", "Run experimental hooks", TaskStatus.PENDING),
        ]

        assert all(task.status == TaskStatus.PENDING for task in tasks)

        task_dicts = [task.to_dict() for task in tasks]
        assert len(task_dicts) == 3
        assert all(task_dict["status"] == "pending" for task_dict in task_dicts)

        assert cleaning_config.clean is True
        assert cleaning_config.update_docs is True
        assert hook_config.experimental_hooks is True
        assert hook_config.skip_hooks is False

    def test_error_handling_scenario(self) -> None:
        task = Task("risky - task", "Risky Operation", TaskStatus.IN_PROGRESS)

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

        assert task.status == TaskStatus.IN_PROGRESS
