"""Core error handling decorators."""

import typing as t
from functools import wraps

from rich.console import Console

from ..errors import CrackerjackError
from .utils import format_exception_chain, get_function_context, is_async_function


def _handle_exception(
    e: Exception,
    func: t.Callable[..., t.Any],
    transform_to: type[CrackerjackError] | None,
    fallback: t.Any,
    suppress: bool,
    console: Console,
) -> t.Any:
    """Helper to handle exception with transformation and fallback logic."""
    context = get_function_context(func)

    # Log error with context
    console.print(
        f"[red]❌ Error in {context['function_name']}: {type(e).__name__}: {e}[/red]"
    )

    # Transform to CrackerjackError if requested
    if transform_to:
        transformed = transform_to(
            message=str(e),
            details={
                "original_error": type(e).__name__,
                "function": context["function_name"],
                "module": context["module"],
            },
        )
        if not suppress:
            raise transformed from e

    # Use fallback if provided
    if fallback is not None:
        return fallback() if callable(fallback) else fallback

    # Re-raise if not suppressed and no transform
    if not suppress:
        raise

    return None


def handle_errors(
    error_types: list[type[Exception]] | None = None,
    fallback: t.Any = None,
    transform_to: type[CrackerjackError] | None = None,
    console: Console | None = None,
    suppress: bool = False,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Centralized error handling with transformation and fallback support.

    Args:
        error_types: List of exception types to handle (None = all exceptions)
        fallback: Fallback value or callable to return on error
        transform_to: Transform caught exceptions to this CrackerjackError type
        console: Optional Rich Console for error output
        suppress: If True, suppress errors and use fallback (no re-raise)

    Returns:
        Decorated function with error handling

    Example:
        >>> from crackerjack.errors import FileError, ExecutionError
        >>>
        >>> @handle_errors(
        ...     error_types=[FileNotFoundError, PermissionError],
        ...     transform_to=FileError,
        ...     fallback={}
        ... )
        >>> def load_config(path: str) -> dict:
        ...     with open(path) as f:
        ...         return json.load(f)

        >>> @handle_errors(fallback=lambda: [], suppress=True)
        >>> def get_optional_data() -> list[str]:
        ...     # Errors suppressed, returns []
        ...     return fetch_data()

    Notes:
        - If transform_to is set, exceptions are wrapped in CrackerjackError
        - Fallback can be a value or callable
        - With suppress=True, errors are logged but not raised
        - Integrates with Rich console for beautiful output
    """
    _console = console or Console()
    _error_types = tuple(error_types) if error_types else (Exception,)

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return await func(*args, **kwargs)
                except _error_types as e:
                    return _handle_exception(
                        e, func, transform_to, fallback, suppress, _console
                    )

            return async_wrapper

        else:

            @wraps(func)
            def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return func(*args, **kwargs)
                except _error_types as e:
                    return _handle_exception(
                        e, func, transform_to, fallback, suppress, _console
                    )

            return sync_wrapper

    return decorator


def log_errors(
    logger: t.Any | None = None,
    level: str = "error",
    include_traceback: bool = True,
    console: Console | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Log errors with context before re-raising.

    Args:
        logger: Logger instance (uses print if None)
        level: Log level (error, warning, info, debug)
        include_traceback: Include full exception traceback
        console: Optional Rich Console

    Returns:
        Decorated function with error logging

    Example:
        >>> import logging
        >>> logger = logging.getLogger(__name__)
        >>>
        >>> @log_errors(logger=logger, level="error")
        >>> async def critical_operation() -> bool:
        ...     # Errors are logged before re-raising
        ...     return await perform_operation()

    Notes:
        - Does not suppress errors, only logs them
        - Includes function context in logs
        - Supports structured logging if logger supports it
    """
    _console = console or Console()

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    context = get_function_context(func)
                    error_chain = format_exception_chain(e)

                    # Log error with context
                    if logger:
                        log_method = getattr(logger, level, logger.error)
                        log_method(
                            f"Error in {context['function_name']}",
                            exc_info=include_traceback,
                            extra={
                                "function": context["function_name"],
                                "module": context["module"],
                                "error_type": type(e).__name__,
                                "error_chain": error_chain,
                            },
                        )
                    else:
                        _console.print(
                            f"[red]Error in {context['function_name']}: "
                            f"{type(e).__name__}: {e}[/red]"
                        )
                        if include_traceback:
                            _console.print_exception()

                    raise

            return async_wrapper

        else:

            @wraps(func)
            def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    context = get_function_context(func)
                    error_chain = format_exception_chain(e)

                    if logger:
                        log_method = getattr(logger, level, logger.error)
                        log_method(
                            f"Error in {context['function_name']}",
                            exc_info=include_traceback,
                            extra={
                                "function": context["function_name"],
                                "module": context["module"],
                                "error_type": type(e).__name__,
                                "error_chain": error_chain,
                            },
                        )
                    else:
                        _console.print(
                            f"[red]Error in {context['function_name']}: "
                            f"{type(e).__name__}: {e}[/red]"
                        )
                        if include_traceback:
                            _console.print_exception()

                    raise

            return sync_wrapper

    return decorator


def graceful_degradation(
    fallback_value: t.Any = None,
    warn: bool = True,
    console: Console | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Gracefully degrade on errors with optional warnings.

    Args:
        fallback_value: Value to return on error (can be callable)
        warn: Show warning message when falling back
        console: Optional Rich Console

    Returns:
        Decorated function with graceful degradation

    Example:
        >>> @graceful_degradation(fallback_value=[], warn=True)
        >>> def get_optional_features() -> list[str]:
        ...     # Returns [] on error with warning
        ...     return fetch_features()

        >>> @graceful_degradation(fallback_value=lambda: {})
        >>> async def load_cache() -> dict:
        ...     # Returns {} on error
        ...     return await load_cache_file()

    Notes:
        - Suppresses all exceptions
        - Logs/warns about failures if warn=True
        - Useful for optional features that shouldn't break the app
    """
    _console = console or Console()

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if warn:
                        context = get_function_context(func)
                        _console.print(
                            f"[yellow]⚠️  {context['function_name']} failed, using fallback: "
                            f"{type(e).__name__}[/yellow]"
                        )

                    if callable(fallback_value):
                        return fallback_value()
                    return fallback_value

            return async_wrapper

        else:

            @wraps(func)
            def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if warn:
                        context = get_function_context(func)
                        _console.print(
                            f"[yellow]⚠️  {context['function_name']} failed, using fallback: "
                            f"{type(e).__name__}[/yellow]"
                        )

                    if callable(fallback_value):
                        return fallback_value()
                    return fallback_value

            return sync_wrapper

    return decorator
