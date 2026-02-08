"""Error handling utilities for crackerjack.

This module provides standardized error handling patterns to ensure:
- All errors are logged with full context
- Stack traces are preserved
- Errors are never silently swallowed
- Consistent error message formatting
"""

import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, TypeVar

from crackerjack.models.protocols import Logger

logger = logging.getLogger(__name__)

T = TypeVar("T")


def log_and_return_error(
    error: Exception,
    message: str,
    *,
    logger_instance: Logger | None = None,
    level: int = logging.ERROR,
    **extra_context: Any,
) -> None:
    """Log an exception with full context and stack trace.

    This is the preferred error logging method for crackerjack.

    Args:
        error: The exception that occurred
        message: Descriptive message explaining what operation failed
        logger_instance: Logger to use (defaults to module logger)
        level: Logging level (ERROR, WARNING, etc.)
        **extra_context: Additional context (file_path, function_name, etc.)

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     log_and_return_error(
        ...         e,
        ...         "Failed to process file",
        ...         file_path=str(path),
        ...         function="process_file"
        ...     )
    """
    log = logger_instance or logger

    # Build extra context with standard fields
    context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    context.update(extra_context)

    # Log with full exception info
    log.log(
        level,
        f"{message}: {error}",
        exc_info=True,
        extra=context,
    )


def log_exception(
    message: str,
    *,
    logger_instance: Logger | None = None,
    level: int = logging.ERROR,
    include_traceback: bool = True,
    **extra_context: Any,
) -> None:
    """Log an exception with context.

    Use this in exception handlers to log with full stack trace.

    Args:
        message: Descriptive message
        logger_instance: Logger to use (defaults to module logger)
        level: Logging level
        include_traceback: Whether to include stack trace
        **extra_context: Additional context

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception:
        ...     log_exception(
        ...         "Failed to load configuration",
        ...         config_path=str(path)
        ...     )
    """
    log = logger_instance or logger

    context = {
        **extra_context,
    }

    log.log(
        level,
        message,
        exc_info=include_traceback,
        extra=context,
    )


def safe_execute(
    func: Callable[..., T],
    *args: Any,
    error_message: str | None = None,
    default_return: T | None = None,
    logger_instance: Logger | None = None,
    **kwargs: Any,
) -> T | None:
    """Execute a function safely with comprehensive error logging.

    This wrapper ensures all exceptions are logged with full context
    before returning a default value.

    Args:
        func: Function to execute
        *args: Positional arguments for func
        error_message: Custom error message (auto-generated if None)
        default_return: Value to return on error (None if not specified)
        logger_instance: Logger to use
        **kwargs: Keyword arguments for func

    Returns:
        Function result on success, default_return on error

    Example:
        >>> result = safe_execute(
        ...     parse_json,
        ...     json_content,
        ...     error_message="Failed to parse configuration",
        ...     default_return={},
        ...     file_path=str(path)
        ... )
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        func_name = getattr(func, "__name__", "unknown_function")

        if error_message is None:
            error_message = f"Function '{func_name}' failed"

        log_and_return_error(
            e,
            error_message,
            logger_instance=logger_instance,
            function=func_name,
            **kwargs,
        )

        return default_return


def get_error_context(
    *,
    file_path: Path | str | None = None,
    function_name: str | None = None,
    line_number: int | None = None,
    **additional_context: Any,
) -> dict[str, Any]:
    """Build standardized error context dictionary.

    Args:
        file_path: Path to file being processed
        function_name: Function where error occurred
        line_number: Line number where error occurred
        **additional_context: Any additional context

    Returns:
        Dictionary with all non-None context values

    Example:
        >>> context = get_error_context(
        ...     file_path=Path("config.yaml"),
        ...     function_name="load_config",
        ...     operation="parse_yaml"
        ... )
    """
    context: dict[str, Any] = {}

    if file_path is not None:
        context["file_path"] = str(file_path)
    if function_name is not None:
        context["function"] = function_name
    if line_number is not None:
        context["line_number"] = line_number

    context.update(additional_context)
    return context


def raise_with_context(
    original_error: Exception,
    new_message: str,
    *,
    logger_instance: Logger | None = None,
    log_before_raise: bool = True,
) -> None:
    """Raise a new exception while preserving the original context.

    This ensures the original stack trace is not lost.

    Args:
        original_error: The original exception
        new_message: New error message with additional context
        logger_instance: Logger to use
        log_before_raise: Whether to log before raising

    Raises:
        Always raises the original exception type with new message

    Example:
        >>> try:
        ...     config.load()
        ... except ValueError as e:
        ...     raise_with_context(
        ...         e,
        ...         f"Failed to load config from {config_path}",
        ...         config_path=str(config_path)
        ...     )
    """
    if log_before_raise:
        log_and_return_error(
            original_error,
            new_message,
            logger_instance=logger_instance,
        )

    # Preserve original exception type and stack trace
    raise type(original_error)(new_message) from original_error


def format_error_message(
    operation: str,
    resource: str | None = None,
    reason: str | None = None,
) -> str:
    """Format a consistent error message.

    Args:
        operation: What was being attempted (e.g., "read file", "parse JSON")
        resource: What resource was being operated on (e.g., file path)
        reason: Why the operation failed (e.g., "file not found")

    Returns:
        Formatted error message

    Examples:
        >>> format_error_message("read file", "config.yaml")
        'Failed to read file: config.yaml'
        >>> format_error_message("read file", "config.yaml", "not found")
        'Failed to read file config.yaml: not found'
    """
    if resource and reason:
        return f"Failed to {operation} {resource}: {reason}"
    if resource:
        return f"Failed to {operation}: {resource}"
    return f"Failed to {operation}"


def handle_file_operation_error(
    error: Exception,
    file_path: Path | str,
    operation: str,
    *,
    logger_instance: Logger | None = None,
    reraise: bool = False,
) -> None:
    """Handle file operation errors with consistent logging.

    Args:
        error: The exception that occurred
        file_path: Path to file
        operation: Operation being performed (e.g., "read", "write")
        logger_instance: Logger to use
        reraise: Whether to re-raise the exception

    Example:
        >>> try:
        ...     content = Path(file_path).read_text()
        ... except OSError as e:
        ...     handle_file_operation_error(e, file_path, "read", reraise=True)
    """
    message = format_error_message(operation, str(file_path), str(error))

    log_and_return_error(
        error,
        message,
        logger_instance=logger_instance,
        file_path=str(file_path),
        operation=operation,
    )

    if reraise:
        raise
