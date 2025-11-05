import sys
import typing as t
from enum import Enum
from pathlib import Path

from acb.console import Console
from rich.panel import Panel


class ErrorCode(Enum):
    CONFIG_FILE_NOT_FOUND = 1001
    CONFIG_PARSE_ERROR = 1002
    INVALID_CONFIG = 1003
    MISSING_CONFIG_FIELD = 1004
    COMMAND_EXECUTION_ERROR = 2001
    COMMAND_TIMEOUT = 2002
    EXTERNAL_TOOL_ERROR = 2003
    PDM_INSTALL_ERROR = 2004
    PRE_COMMIT_ERROR = 2005
    TEST_EXECUTION_ERROR = 3001
    TEST_FAILURE = 3002
    BENCHMARK_REGRESSION = 3003
    BUILD_ERROR = 4001
    PUBLISH_ERROR = 4002
    VERSION_BUMP_ERROR = 4003
    AUTHENTICATION_ERROR = 4004
    GIT_COMMAND_ERROR = 5001
    PULL_REQUEST_ERROR = 5002
    COMMIT_ERROR = 5003
    FILE_NOT_FOUND = 6001
    PERMISSION_ERROR = 6002
    FILE_READ_ERROR = 6003
    FILE_WRITE_ERROR = 6004
    FILE_TOO_LARGE = 6005
    CODE_CLEANING_ERROR = 7001
    FORMATTING_ERROR = 7002
    RESOURCE_ERROR = 8001
    TIMEOUT_ERROR = 8002
    NETWORK_ERROR = 8003
    DEPENDENCY_ERROR = 8004
    VALIDATION_ERROR = 8005
    SECURITY_ERROR = 8006
    GENERAL_ERROR = 9000
    UNKNOWN_ERROR = 9001
    NOT_IMPLEMENTED = 9002
    UNEXPECTED_ERROR = 9999


class CrackerjackError(Exception):
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details
        self.recovery = recovery
        self.exit_code = exit_code
        super().__init__(message)


class ConfigError(CrackerjackError):
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.CONFIG_PARSE_ERROR,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class ExecutionError(CrackerjackError):
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.COMMAND_EXECUTION_ERROR,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class TestExecutionError(CrackerjackError):
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.TEST_EXECUTION_ERROR,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class PublishError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.PUBLISH_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class GitError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.GIT_COMMAND_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class FileError(CrackerjackError):
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.FILE_NOT_FOUND,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class CleaningError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.EXTERNAL_TOOL_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class NetworkError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.NETWORK_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class DependencyError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.DEPENDENCY_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class ResourceError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | dict[str, t.Any] | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class ValidationError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class TimeoutError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


class SecurityError(CrackerjackError):
    def __init__(
        self,
        message: str,
        details: str | None = None,
        recovery: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(
            message=message,
            error_code=ErrorCode.SECURITY_ERROR,
            details=details,
            recovery=recovery,
            exit_code=exit_code,
        )


def _format_error_for_ai_agent(error: CrackerjackError, verbose: bool) -> str:
    import json

    error_data = {
        "status": "error",
        "error_code": error.error_code.name,
        "code": error.error_code.value,
        "message": error.message,
    }
    if verbose and error.details:
        error_data["details"] = (
            json.dumps(error.details)
            if isinstance(error.details, dict)
            else error.details
        )
    if error.recovery:
        error_data["recovery"] = error.recovery

    return json.dumps(error_data)


def _format_error_for_console(error: CrackerjackError, verbose: bool) -> Panel:
    title = f"Error {error.error_code.value}: {error.error_code.name}"
    content = [error.message]

    if verbose and error.details:
        content.extend(("\n[white]Details: [/ white]", str(error.details)))
    if error.recovery:
        content.extend(("\n[green]Recovery suggestion: [/ green]", str(error.recovery)))

    return Panel(
        "\n".join(content),
        title=title,
        border_style="red",
        title_align="left",
        expand=False,
    )


def handle_error(
    error: CrackerjackError,
    console: Console,
    verbose: bool = False,
    ai_agent: bool = False,
    exit_on_error: bool = True,
) -> None:
    if ai_agent:
        formatted_json = _format_error_for_ai_agent(error, verbose)
        console.print(f"[json]{formatted_json}[/ json]")
    else:
        panel = _format_error_for_console(error, verbose)
        console.print(panel)

    if exit_on_error:
        sys.exit(error.exit_code)


def check_file_exists(path: Path, error_message: str) -> None:
    if not path.exists():
        raise FileError(
            message=error_message,
            details=f"The file at {path} does not exist.",
            recovery="Check the file path and ensure the file exists.",
        )


def check_command_result(
    result: t.Any,
    command: str,
    error_message: str,
    error_code: ErrorCode = ErrorCode.COMMAND_EXECUTION_ERROR,
    recovery: str | None = None,
) -> None:
    if getattr(result, "returncode", 0) != 0:
        stderr = getattr(result, "stderr", "")
        details = f"Command '{command}' failed with return code {result.returncode}."
        if stderr:
            details += f"\nStandard error output: \n{stderr}"
        raise ExecutionError(
            message=error_message,
            error_code=error_code,
            details=details,
            recovery=recovery,
        )


def format_error_report(error: CrackerjackError) -> str:
    return f"Error {error.error_code.value}: {error.message}"
