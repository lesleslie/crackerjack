import typing as t

from acb import register_pkg

register_pkg("crackerjack")

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
from .interactive import InteractiveWorkflowOptions as WorkflowOptions

try:
    from importlib.metadata import version

    __version__ = version("crackerjack")
except (ImportError, ModuleNotFoundError):
    __version__ = "0.19.8"
__all__: t.Sequence[str] = [
    "CleaningError",
    "ConfigError",
    "CrackerjackAPI",
    "CrackerjackError",
    "DependencyError",
    "ErrorCode",
    "ExecutionError",
    "FileError",
    "GitError",
    "NetworkError",
    "PublishError",
    "PublishResult",
    "QualityCheckResult",
    "ResourceError",
    "SecurityError",
    "TestExecutionError",
    "TestResult",
    "TimeoutError",
    "ValidationError",
    "WorkflowOptions",
    "__version__",
    "check_command_result",
    "check_file_exists",
    "clean_code",
    "handle_error",
    "publish_package",
    "run_quality_checks",
    "run_tests",
]
