import typing as t

from .api import (
    CrackerjackAPI,
    PublishResult,
    QualityCheckResult,
    TestResult,
    clean_code,
    publish_package,
    run_quality_checks,
    run_tests,
)
from .errors import (
    CleaningError,
    ConfigError,
    CrackerjackError,
    DependencyError,
    ErrorCode,
    ExecutionError,
    FileError,
    GitError,
    NetworkError,
    PublishError,
    ResourceError,
    SecurityError,
    TestExecutionError,
    TimeoutError,
    ValidationError,
    check_command_result,
    check_file_exists,
    handle_error,
)
from .interactive import WorkflowOptions

try:
    from importlib.metadata import version

    __version__ = version("crackerjack")
except (ImportError, ModuleNotFoundError):
    __version__ = "0.19.8"
__all__: t.Sequence[str] = [
    "CrackerjackAPI",
    "QualityCheckResult",
    "TestResult",
    "PublishResult",
    "WorkflowOptions",
    "run_quality_checks",
    "clean_code",
    "run_tests",
    "publish_package",
    "__version__",
    "CrackerjackError",
    "ConfigError",
    "DependencyError",
    "ExecutionError",
    "TestExecutionError",
    "PublishError",
    "GitError",
    "FileError",
    "CleaningError",
    "NetworkError",
    "ResourceError",
    "SecurityError",
    "TimeoutError",
    "ValidationError",
    "ErrorCode",
    "handle_error",
    "check_file_exists",
    "check_command_result",
]
