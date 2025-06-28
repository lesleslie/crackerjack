import typing as t
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from crackerjack.errors import (
    CleaningError,
    ConfigError,
    CrackerjackError,
    ErrorCode,
    ExecutionError,
    FileError,
    GitError,
    PublishError,
    TestError,
    handle_error,
)


class TestErrorClasses:
    def test_base_error_class(self) -> None:
        error = CrackerjackError(
            message="Test error",
            error_code=ErrorCode.UNKNOWN_ERROR,
            details="Test details",
            recovery="Test recovery",
            exit_code=2,
        )
        assert error.message == "Test error"
        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert error.details == "Test details"
        assert error.recovery == "Test recovery"
        assert error.exit_code == 2
        assert str(error) == "Test error"

    def test_specialized_error_classes(self) -> None:
        error_classes = [
            ConfigError,
            ExecutionError,
            TestError,
            PublishError,
            GitError,
            FileError,
            CleaningError,
        ]
        for error_class in error_classes:
            error = error_class(
                message="Test error", error_code=ErrorCode.UNKNOWN_ERROR
            )
            assert isinstance(error, CrackerjackError)
            assert error.message == "Test error"
            assert error.error_code == ErrorCode.UNKNOWN_ERROR


class TestErrorHandling:
    @pytest.fixture
    def console_mock(self) -> t.Generator[MagicMock]:
        with patch.object(Console, "print") as mock:
            yield mock

    @pytest.fixture
    def mock_sys_exit(self) -> t.Generator[MagicMock]:
        with patch("sys.exit") as mock:
            yield mock

    def test_handle_error_console_output(
        self, console_mock: MagicMock, mock_sys_exit: MagicMock
    ) -> None:
        error = TestError(
            message="Test failed",
            error_code=ErrorCode.TEST_FAILURE,
            details="Test details",
            recovery="Fix the test",
        )
        console = Console()
        handle_error(error, console, verbose=True)
        console_mock.assert_called_once()
        mock_sys_exit.assert_called_once_with(1)

    def test_handle_error_without_exit(
        self, console_mock: MagicMock, mock_sys_exit: MagicMock
    ) -> None:
        error = TestError(message="Test failed", error_code=ErrorCode.TEST_FAILURE)
        console = Console()
        handle_error(error, console, exit_on_error=False)
        console_mock.assert_called_once()
        mock_sys_exit.assert_not_called()

    def test_handle_error_ai_agent_mode(
        self, console_mock: MagicMock, mock_sys_exit: MagicMock
    ) -> None:
        error = TestError(
            message="Test failed",
            error_code=ErrorCode.TEST_FAILURE,
            details="Test details",
            recovery="Fix the test",
        )
        console = Console()
        handle_error(error, console, verbose=True, ai_agent=True)
        console_mock.assert_called_once()
        call_args = console_mock.call_args[0][0]
        assert "[json]" in str(call_args)
        assert "error_code" in str(call_args)
        assert "TEST_FAILURE" in str(call_args)

    def test_handle_error_without_details_or_recovery(
        self, console_mock: MagicMock
    ) -> None:
        error = TestError(message="Test failed", error_code=ErrorCode.TEST_FAILURE)
        console = Console()
        handle_error(error, console, verbose=True, exit_on_error=False)
        console_mock.assert_called_once()


class TestErrorCodes:
    def test_error_codes_unique(self) -> None:
        code_values = [code.value for code in ErrorCode]
        assert len(code_values) == len(set(code_values)), (
            "Duplicate error code values found"
        )

    def test_error_codes_categories(self) -> None:
        for code in ErrorCode:
            value = code.value
            if 1000 <= value < 2000:
                assert "CONFIG" in code.name
            elif 2000 <= value < 3000:
                assert any(
                    prefix in code.name
                    for prefix in ("COMMAND", "EXTERNAL", "PDM", "PRE_COMMIT")
                )
            elif 3000 <= value < 4000:
                assert "TEST" in code.name or "BENCHMARK" in code.name
            elif 4000 <= value < 5000:
                assert any(
                    prefix in code.name
                    for prefix in ("BUILD", "PUBLISH", "VERSION", "AUTHENTICATION")
                )
            elif 5000 <= value < 6000:
                assert (
                    "GIT" in code.name
                    or "PULL_REQUEST" in code.name
                    or "COMMIT" in code.name
                )
            elif 6000 <= value < 7000:
                assert "FILE" in code.name or "PERMISSION" in code.name
            elif 7000 <= value < 8000:
                assert "CODE" in code.name or "FORMATTING" in code.name
            elif 9000 <= value < 10000:
                assert any(
                    prefix in code.name
                    for prefix in ("UNKNOWN", "NOT_IMPLEMENTED", "UNEXPECTED")
                )
