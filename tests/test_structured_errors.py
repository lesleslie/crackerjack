import io
import typing as t
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from crackerjack.errors import (
    ErrorCode,
    ExecutionError,
    FileError,
    PublishError,
    TestError,
    check_command_result,
    check_file_exists,
    handle_error,
)


class TestErrorHandlingIntegration:
    @pytest.fixture
    def mock_command_result(self) -> t.Generator[MagicMock]:
        result = MagicMock()
        result.returncode = 0
        result.stdout = "Success"
        result.stderr = ""
        yield result

    def test_check_command_result_success(self, mock_command_result: MagicMock) -> None:
        check_command_result(
            mock_command_result,
            "test command",
            "Error executing command",
        )

    def test_check_command_result_failure(self, mock_command_result: MagicMock) -> None:
        mock_command_result.returncode = 1
        mock_command_result.stderr = "Command failed"

        with pytest.raises(ExecutionError) as excinfo:
            check_command_result(
                mock_command_result,
                "test command",
                "Error executing command",
            )

        assert excinfo.value.error_code == ErrorCode.COMMAND_EXECUTION_ERROR
        assert "Error executing command" in excinfo.value.message
        assert (
            excinfo.value.details is not None
            and "Command failed" in excinfo.value.details
        )

    def test_check_file_exists_success(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        check_file_exists(test_file, "File not found")

    def test_check_file_exists_failure(self, tmp_path: Path) -> None:
        test_file = tmp_path / "nonexistent.txt"

        with pytest.raises(FileError) as excinfo:
            check_file_exists(test_file, "File not found")

        assert excinfo.value.error_code == ErrorCode.FILE_NOT_FOUND
        assert "File not found" in excinfo.value.message
        assert (
            excinfo.value.details is not None
            and str(test_file) in excinfo.value.details
        )

    def test_error_handling_in_code_cleaner(self) -> None:
        from crackerjack.crackerjack import CodeCleaner

        console = MagicMock()

        cleaner = CodeCleaner(console=console)

        with patch("crackerjack.errors.handle_error") as mock_handle_error:
            cleaner.clean_file(Path("/nonexistent/file.py"))
            mock_handle_error.assert_called_once()
            error = mock_handle_error.call_args[0][0]
            assert isinstance(error, FileError)
            assert error.error_code == ErrorCode.FILE_NOT_FOUND

    def test_error_handling_in_publish_project(self) -> None:
        from crackerjack.crackerjack import Crackerjack

        console = MagicMock()

        runner = Crackerjack(console=console, dry_run=True)

        options = MagicMock()
        options.publish = "micro"
        options.verbose = True
        options.ai_agent = False

        with patch.object(runner, "execute_command") as mock_execute:
            mock_execute.return_value = MagicMock(
                returncode=1,
                stderr="Build failed: invalid syntax",
                stdout="",
            )

            with patch("platform.system", return_value="Linux"):
                with patch("crackerjack.errors.handle_error") as mock_handle_error:
                    runner._publish_project(options)

                    mock_handle_error.assert_called()
                    call_args = mock_handle_error.call_args
                    error = call_args.kwargs.get("error") or call_args.args[0]
                    assert isinstance(error, PublishError)
                    assert error.error_code in (
                        ErrorCode.BUILD_ERROR,
                        ErrorCode.PUBLISH_ERROR,
                    )

    def test_handle_error_output_format(self) -> None:
        error = TestError(
            message="Test failed",
            error_code=ErrorCode.TEST_FAILURE,
            details="Test details",
            recovery="Try running with --verbose",
        )

        console = Console(file=io.StringIO(), width=80)

        with patch("sys.exit"):
            handle_error(error, console, verbose=True)

        output = console.file.getvalue()  # type: ignore

        assert "❌ Error 3002: TEST_FAILURE" in output
        assert "Test failed" in output
        assert "Details:" in output
        assert "Test details" in output
        assert "Recovery suggestion:" in output
        assert "Try running with --verbose" in output

    def test_ai_agent_error_format(self) -> None:
        error = ExecutionError(
            message="Command failed",
            error_code=ErrorCode.COMMAND_EXECUTION_ERROR,
            details="Exit code 1",
            recovery="Check command syntax",
        )

        console = Console(file=io.StringIO(), width=80)

        with patch("sys.exit"):
            handle_error(error, console, verbose=True, ai_agent=True)

        output = console.file.getvalue()  # type: ignore

        assert "status" in output
        assert "error_code" in output
        assert "COMMAND_EXECUTION_ERROR" in output
        assert "Command failed" in output
