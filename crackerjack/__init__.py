"""Crackerjack - Opinionated Python project management tool."""

import logging
import sys
import typing as t

# CRITICAL: Suppress ACB logger startup messages BEFORE any ACB imports
# This must be the FIRST thing we do, even before acb.register_pkg()
# ACB's logger initializes at import time and emits "Application started" messages.
_EARLY_DEBUG_MODE = any(
    arg in ("--debug", "-d", "--ai-debug") or arg.startswith("--debug=")
    for arg in sys.argv[1:]
)

if not _EARLY_DEBUG_MODE:
    # Suppress ACB startup logging for clean default UX
    acb_logger = logging.getLogger("acb")
    acb_logger.setLevel(logging.CRITICAL)
    acb_logger.propagate = False

    # Suppress crackerjack orchestration INFO logging (show only warnings/errors)
    # This prevents "Executing hook strategy", "Wave X complete", etc. from
    # appearing during progress bar updates
    crackerjack_logger = logging.getLogger("crackerjack")
    crackerjack_logger.setLevel(logging.WARNING)

# NOW safe to import ACB
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
