from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crackerjack.errors import (
    CrackerjackError,
    ErrorCode,
    ExecutionError,
    FileError,
    check_command_result,
    check_file_exists,
    format_error_report,
    handle_error,
)


def test_handle_error_no_exit():
    console = MagicMock()
    error = CrackerjackError(message="boom", error_code=ErrorCode.UNKNOWN_ERROR)
    handle_error(error, console=console, exit_on_error=False)
    console.print.assert_called()


def test_check_file_exists_raises(tmp_path):
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileError):
        check_file_exists(missing, "missing file")


def test_check_command_result_raises():
    result = SimpleNamespace(returncode=1, stderr="nope")
    with pytest.raises(ExecutionError):
        check_command_result(result, "cmd", "failed")


def test_format_error_report():
    error = CrackerjackError(message="oops", error_code=ErrorCode.UNKNOWN_ERROR)
    assert format_error_report(error) == "Error 9001: oops"
