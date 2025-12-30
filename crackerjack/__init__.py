"""Crackerjack - Opinionated Python project management tool."""

import logging
import sys
import typing as t

# CRITICAL: Suppress logger startup messages for clean UX
# This must be the FIRST thing we do to prevent verbose logging
_EARLY_DEBUG_MODE = any(
    arg in ("--debug", "-d", "--ai-debug") or arg.startswith("--debug=")
    for arg in sys.argv[1:]
)

if not _EARLY_DEBUG_MODE:
    # Suppress verbose logging for clean default UX
    crackerjack_logger = logging.getLogger("crackerjack")
    crackerjack_logger.setLevel(logging.WARNING)

    # Suppress other framework loggers that might be verbose
    for logger_name in (
        "uvicorn",
        "fastapi",
        "httpx",
        "httpcore",
        "oneiric",
        "Oneiric",
        "oneiric.core",
        "oneiric.runtime",
    ):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.propagate = False

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
