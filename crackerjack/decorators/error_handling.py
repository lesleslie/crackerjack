"""Core error handling decorators."""

from __future__ import annotations

import asyncio
import errno
import inspect
import sys
import time
import typing as t
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import suppress
from functools import wraps

from acb.console import Console
from acb.depends import depends

from ..errors import (
    CrackerjackError,
    ValidationError,
)
from ..errors import (
    TimeoutError as CrackerjackTimeoutError,
)
from .utils import format_exception_chain, get_function_context, is_async_function


def _safe_console_print(
    console: Console,
    message: str,
    *,
    include_traceback: bool = False,
    retries: int = 3,
    retry_delay: float = 0.05,
) -> None:
    """Safely print to a Rich Console, tolerating non-blocking streams.

    Some environments set stdout/stderr to non-blocking (e.g., PTY pipes),
    which can raise BlockingIOError (EWOULDBLOCK/EAGAIN). This helper retries
    briefly and then degrades silently if output still cannot be written.
    """
    for attempt in range(retries + 1):
        try:
            console.print(message)
            if include_traceback:
                console.print_exception()
            return
        except (BlockingIOError, BrokenPipeError, OSError) as e:  # pragma: no cover
            # Only retry on would-block conditions; otherwise degrade silently
            err_no = getattr(e, "errno", None)
            would_block = (
                err_no in {errno.EAGAIN, errno.EWOULDBLOCK}
                if err_no is not None
                else isinstance(e, BlockingIOError)
            )
            if would_block and attempt < retries:
                time.sleep(retry_delay)
                continue
            # Final fallback: try bare stderr write; ignore all errors
            with suppress(Exception):
                err = sys.__stderr__
                if err is not None:
                    err.write(message + "\n")
                    if include_traceback:
                        # Avoid rich rendering here to prevent further issues
                        err.write("(traceback suppressed due to I/O constraints)\n")
                    err.flush()
            return


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
    _safe_console_print(
        console,
        f"[red]❌ Error in {context['function_name']}: {type(e).__name__}: {e}[/red]",
    )

    # Transform to CrackerjackError if requested
    if transform_to:
        transformed = transform_to(  # type: ignore[call-arg]
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
    func: t.Callable[..., t.Any] | None = None,
    *,
    error_types: list[type[Exception]] | None = None,
    fallback: t.Any = None,
    transform_to: type[CrackerjackError] | None = None,
    console: Console | None = None,
    suppress: bool = False,
) -> (
    t.Callable[..., t.Any]
    | t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]
):
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
    _console = console or depends.get_sync(Console)
    _error_types = tuple(error_types) if error_types else (Exception,)

    def decorator(inner_func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        target = inner_func
        if is_async_function(inner_func):

            @wraps(inner_func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return await target(*args, **kwargs)
                except _error_types as e:
                    return _handle_exception(
                        e, target, transform_to, fallback, suppress, _console
                    )

            return async_wrapper

        else:

            @wraps(inner_func)
            def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return target(*args, **kwargs)
                except _error_types as e:
                    return _handle_exception(
                        e, target, transform_to, fallback, suppress, _console
                    )

            return sync_wrapper

    if func is not None and callable(func):
        return decorator(func)

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
    _console = console or depends.get_sync(Console)

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
                        _safe_console_print(
                            _console,
                            f"[red]Error in {context['function_name']}: "
                            f"{type(e).__name__}: {e}[/red]",
                            include_traceback=include_traceback,
                        )

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
                        _safe_console_print(
                            _console,
                            f"[red]Error in {context['function_name']}: "
                            f"{type(e).__name__}: {e}[/red]",
                            include_traceback=include_traceback,
                        )

                    raise

            return sync_wrapper

    return decorator


def retry(
    *,
    max_attempts: int = 3,
    exceptions: t.Iterable[type[Exception]] | None = None,
    backoff: float = 0.0,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Retry decorator supporting sync and async callables.

    Args:
        max_attempts: Maximum number of attempts (>=1)
        exceptions: Iterable of exception types to retry on (default: Exception)
        backoff: Base delay in seconds applied after each failed attempt.
                 Delay grows linearly with attempt number.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    retry_exceptions = tuple(exceptions) if exceptions else (Exception,)

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                attempt = 0
                while True:
                    try:
                        return await func(*args, **kwargs)
                    except retry_exceptions:
                        attempt += 1
                        if attempt >= max_attempts:
                            raise
                        delay = backoff * attempt if backoff > 0 else 0.0
                        if delay > 0:
                            await asyncio.sleep(delay)
                        continue

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except retry_exceptions:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    delay = backoff * attempt if backoff > 0 else 0.0
                    if delay > 0:
                        time.sleep(delay)
                    continue

        return sync_wrapper

    return decorator


def with_timeout(
    *,
    seconds: float,
    error_message: str | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Timeout enforcement decorator.

    Args:
        seconds: Maximum execution time in seconds.
        error_message: Optional custom error message for timeout.
    """

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return await asyncio.wait_for(
                        func(*args, **kwargs), timeout=seconds
                    )
                except TimeoutError as exc:
                    message = error_message or f"Operation timed out after {seconds}s"
                    raise CrackerjackTimeoutError(message=message) from exc

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=seconds)
                except FutureTimeoutError as exc:
                    message = error_message or f"Operation timed out after {seconds}s"
                    raise CrackerjackTimeoutError(message=message) from exc

        return sync_wrapper

    return decorator


def _execute_single_validator(
    validate: t.Callable[[t.Any], bool], param: str, value: t.Any
) -> None:
    """Execute a single validator and raise ValidationError if it fails."""
    try:
        result = validate(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValidationError(
            message=f"Validator for '{param}' raised {type(exc).__name__}: {exc}",
        ) from exc
    if not result:
        raise ValidationError(
            message=f"Validation failed for parameter '{param}'",
        )


def _check_type_annotation_against_signature(
    name: str, value: t.Any, signature: inspect.Signature
) -> None:
    """Check if value matches parameter type annotation."""
    parameter = signature.parameters.get(name)
    if not parameter or parameter.annotation is inspect.Signature.empty:
        return
    if not isinstance(value, parameter.annotation):  # type: ignore[arg-type]
        raise ValidationError(
            message=(
                f"Parameter '{name}' expected "
                f"{parameter.annotation!r}, got {type(value)!r}"
            ),
        )


def _create_async_validation_wrapper(
    func: t.Callable[..., t.Any],
    signature: inspect.Signature,
    validate_fn: t.Callable[[inspect.BoundArguments], None],
) -> t.Callable[..., t.Any]:
    """Create async wrapper with validation."""

    @wraps(func)
    async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        validate_fn(bound)
        return await func(*args, **kwargs)

    return async_wrapper


def _create_sync_validation_wrapper(
    func: t.Callable[..., t.Any],
    signature: inspect.Signature,
    validate_fn: t.Callable[[inspect.BoundArguments], None],
) -> t.Callable[..., t.Any]:
    """Create sync wrapper with validation."""

    @wraps(func)
    def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        validate_fn(bound)
        return func(*args, **kwargs)

    return sync_wrapper


def validate_args(
    *,
    validators: dict[
        str, t.Callable[[t.Any], bool] | t.Iterable[t.Callable[[t.Any], bool]]
    ]
    | None = None,
    type_check: bool = False,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Validate function arguments using provided callables and optional type checks.

    Args:
        validators: Mapping of argument names to validator callable(s).
        type_check: If True, enforce annotations via isinstance checks.
    """

    validator_map = validators or {}

    def _run_validators(param: str, value: t.Any) -> None:
        funcs = validator_map.get(param)
        if not funcs:
            return
        if not isinstance(funcs, (list, tuple, set)):
            funcs = [funcs]  # type: ignore[list-item]
        for validate in funcs:
            _execute_single_validator(validate, param, value)

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        signature = inspect.signature(func)

        def _validate(bound: inspect.BoundArguments) -> None:
            if type_check:
                for name, value in bound.arguments.items():
                    _check_type_annotation_against_signature(name, value, signature)

            for name, value in bound.arguments.items():
                _run_validators(name, value)

        if is_async_function(func):
            return _create_async_validation_wrapper(func, signature, _validate)

        return _create_sync_validation_wrapper(func, signature, _validate)

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
    _console = console or depends.get_sync(Console)

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if warn:
                        context = get_function_context(func)
                        _safe_console_print(
                            _console,
                            f"[yellow]⚠️  {context['function_name']} failed, using fallback: "
                            f"{type(e).__name__}[/yellow]",
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
                        _safe_console_print(
                            _console,
                            f"[yellow]⚠️  {context['function_name']} failed, using fallback: "
                            f"{type(e).__name__}[/yellow]",
                        )

                    if callable(fallback_value):
                        return fallback_value()
                    return fallback_value

            return sync_wrapper

    return decorator
