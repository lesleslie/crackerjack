"""Timeout enforcement decorator."""

import asyncio
import signal
import typing as t
from functools import wraps

from ..errors import TimeoutError as CrackerjackTimeoutError
from .utils import is_async_function


def with_timeout(
    seconds: float,
    error_message: str | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Enforce a timeout on function execution.

    Args:
        seconds: Timeout duration in seconds
        error_message: Optional custom error message (default: auto-generated)

    Returns:
        Decorated function with timeout enforcement

    Raises:
        CrackerjackTimeoutError: If function execution exceeds timeout

    Example:
        >>> @with_timeout(seconds=30)
        >>> async def slow_operation() -> dict:
        ...     # Must complete within 30 seconds
        ...     return await fetch_large_data()

        >>> @with_timeout(seconds=5, error_message="Database query too slow")
        >>> def query_database() -> list:
        ...     return db.execute_query()

    Notes:
        - Async functions use asyncio.wait_for for clean cancellation
        - Sync functions use signal.alarm on Unix systems (not supported on Windows)
        - Raises CrackerjackTimeoutError from crackerjack.errors
        - For cross-platform sync timeout, consider using multiprocessing
    """

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    return await asyncio.wait_for(
                        func(*args, **kwargs), timeout=seconds
                    )
                except TimeoutError as e:
                    msg = (
                        error_message
                        or f"Function {func.__name__} timed out after {seconds}s"
                    )
                    raise CrackerjackTimeoutError(
                        message=msg,
                        details=f"Timeout: {seconds}s",
                        recovery="Consider increasing timeout or optimizing the operation",
                    ) from e

            return async_wrapper

        else:

            @wraps(func)
            def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                # Sync timeout using signal (Unix only)
                def timeout_handler(signum: int, frame: t.Any) -> None:
                    msg = (
                        error_message
                        or f"Function {func.__name__} timed out after {seconds}s"
                    )
                    raise CrackerjackTimeoutError(
                        message=msg,
                        details=f"Timeout: {seconds}s",
                        recovery="Consider increasing timeout or optimizing the operation",
                    )

                # Set up signal handler
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(seconds))

                try:
                    result = func(*args, **kwargs)
                finally:
                    # Cancel alarm and restore handler
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

                return result

            return sync_wrapper

    return decorator
