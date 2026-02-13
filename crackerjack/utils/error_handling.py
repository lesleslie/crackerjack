import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


Logger = logging.Logger


def log_and_return_error(
    error: Exception,
    message: str,
    *,
    logger_instance: Logger | None = None,
    level: int = logging.ERROR,
    **extra_context: Any,
) -> None:
    log = logger_instance or logger

    context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    context.update(extra_context)

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


def safe_execute[T](
    func: Callable[..., T],
    *args: Any,
    error_message: str | None = None,
    default_return: T | None = None,
    logger_instance: Logger | None = None,
    **kwargs: Any,
) -> T | None:
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
    if log_before_raise:
        log_and_return_error(
            original_error,
            new_message,
            logger_instance=logger_instance,
        )

    raise type(original_error)(new_message) from original_error


def format_error_message(
    operation: str,
    resource: str | None = None,
    reason: str | None = None,
) -> str:
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
