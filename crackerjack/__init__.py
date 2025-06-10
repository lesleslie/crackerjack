import typing as t

from .crackerjack import Crackerjack, create_crackerjack_runner
from .errors import (
    CleaningError,
    ConfigError,
    CrackerjackError,
    ErrorCode,
    ExecutionError,
    FileError,
    GitError,
    PublishError,
    TestError,
    check_command_result,
    check_file_exists,
    handle_error,
)

try:
    from importlib.metadata import version

    __version__ = version("crackerjack")
except (ImportError, ModuleNotFoundError):
    __version__ = "0.19.8"
__all__: t.Sequence[str] = [
    "create_crackerjack_runner",
    "Crackerjack",
    "__version__",
    "CrackerjackError",
    "ConfigError",
    "ExecutionError",
    "TestError",
    "PublishError",
    "GitError",
    "FileError",
    "CleaningError",
    "ErrorCode",
    "handle_error",
    "check_file_exists",
    "check_command_result",
]
