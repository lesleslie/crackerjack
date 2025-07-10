import io
import typing as t
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

if t.TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
from crackerjack.errors import (
    ErrorCode,
    ExecutionError,
    FileError,
    TestError,
    check_command_result,
    check_file_exists,
    handle_error,
)


class OptionsProtocol(t.Protocol):
    publish: bool
    verbose: bool
    ai_agent: bool
    commit: bool
    interactive: bool
    doc: bool
    no_config_updates: bool
    update_precommit: bool
    clean: bool
    test: bool


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
            mock_command_result, "test command", "Error executing command"
        )

    def test_check_command_result_failure(self, mock_command_result: MagicMock) -> None:
        mock_command_result.returncode = 1
        mock_command_result.stderr = "Command failed"
        with pytest.raises(ExecutionError) as excinfo:
            check_command_result(
                mock_command_result, "test command", "Error executing command"
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

    def test_error_handling_in_code_cleaner(
        self, capsys: "CaptureFixture[str]"
    ) -> None:
        from crackerjack.crackerjack import CodeCleaner

        console = Console(force_terminal=False)
        cleaner = CodeCleaner(console=console)
        test_path = Path("/nonexistent/file.py")
        with patch("pathlib.Path.read_text") as mock_read:
            mock_read.side_effect = FileNotFoundError(
                f"[Errno 2] No such file or directory: '{test_path}'"
            )
            cleaner.clean_file(test_path)
            captured = capsys.readouterr()
            output = captured.out.strip()
            assert "FILE_WRITE_ERROR" in output
            assert str(test_path) in output
            assert "File system error while cleaning" in output

    def test_error_handling_in_publish_project(self) -> None:
        from crackerjack.crackerjack import Crackerjack

        console = Console(file=io.StringIO(), force_terminal=False)
        with patch(
            "crackerjack.crackerjack.Crackerjack.execute_command"
        ) as mock_execute:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Build failed: invalid syntax"
            mock_result.stdout = ""
            mock_execute.return_value = mock_result
            with (
                patch("crackerjack.crackerjack.CodeCleaner"),
                patch("crackerjack.crackerjack.ConfigManager"),
                patch("crackerjack.crackerjack.ProjectManager"),
            ):
                runner = Crackerjack(console=console, dry_run=True)

                class Options(OptionsProtocol):
                    publish = True
                    verbose = True
                    ai_agent = False
                    commit = False
                    interactive = False
                    doc = False
                    no_config_updates = False
                    update_precommit = False
                    clean = False
                    test = False
                    benchmark = False
                    benchmark_regression = False
                    benchmark_regression_threshold = 0.0
                    test_workers = 1
                    test_timeout = 0
                    bump = False
                    all = False
                    create_pr = False
                    skip_hooks = False

                options = Options()
                with patch("platform.system", return_value="Linux"):
                    with pytest.raises(SystemExit) as exc_info:
                        runner._publish_project(options)
                    assert exc_info.value.code == 1
                    mock_execute.assert_called_once_with(
                        ["pdm", "build"], capture_output=True, text=True
                    )

    def test_handle_error_output_format(self) -> None:
        error = TestError(
            message="Test failed",
            error_code=ErrorCode.TEST_FAILURE,
            details="Test details",
            recovery="Try running with --verbose",
        )
        output_io = io.StringIO()
        console = Console(file=output_io, width=80)
        with patch("sys.exit"):
            handle_error(error, console, verbose=True)
        output = output_io.getvalue()
        assert "Error 3002: TEST_FAILURE" in output
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
        output_io = io.StringIO()
        console = Console(file=output_io, width=80)
        with patch("sys.exit"):
            handle_error(error, console, verbose=True, ai_agent=True)
        output = output_io.getvalue()
        assert "status" in output
        assert "error_code" in output
        assert "COMMAND_EXECUTION_ERROR" in output
        assert "Command failed" in output
