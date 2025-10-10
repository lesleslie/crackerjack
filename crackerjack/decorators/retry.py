"""Retry logic decorator with exponential backoff."""

import asyncio
import time
import typing as t
from functools import wraps

from rich.console import Console

from .utils import is_async_function


def _calculate_delay(attempt: int, backoff: float, max_delay: float) -> float:
    """Calculate delay with exponential backoff."""
    return min(backoff**attempt, max_delay)


def _show_retry_message(
    func_name: str,
    attempt: int,
    max_attempts: int,
    delay: float,
    error_type: str,
    console: Console,
) -> None:
    """Show retry attempt message."""
    console.print(
        f"[yellow]⟳ Retry {attempt}/{max_attempts - 1} for {func_name} "
        f"after {delay:.1f}s (error: {error_type})[/yellow]"
    )


def _show_failure_message(func_name: str, max_attempts: int, console: Console) -> None:
    """Show final failure message."""
    console.print(f"[red]❌ {func_name} failed after {max_attempts} attempts[/red]")


def retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] | list[type[Exception]] | None = None,
    on_retry: t.Callable[[Exception, int], None] | None = None,
    console: Console | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Retry a function with exponential backoff on failure.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        backoff: Exponential backoff multiplier (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        exceptions: Specific exception types to retry. If None, retries all exceptions.
        on_retry: Optional callback function called on each retry with (exception, attempt_number)
        console: Optional Rich Console for output (creates default if None)

    Returns:
        Decorated function with retry logic

    Example:
        >>> from crackerjack.errors import NetworkError
        >>>
        >>> @retry(max_attempts=5, backoff=2.0, exceptions=[NetworkError])
        >>> async def fetch_data(url: str) -> dict:
        ...     # May raise NetworkError
        ...     return await client.get(url)

        >>> @retry(max_attempts=3)
        >>> def unreliable_operation() -> bool:
        ...     # Retries on any exception
        ...     return perform_operation()

    Notes:
        - Supports both sync and async functions
        - Uses exponential backoff: delay = min(backoff ** attempt, max_delay)
        - Shows progress indication via Rich console
        - Preserves original exception on final failure
    """
    retry_exceptions = (
        (Exception,)
        if exceptions is None
        else (tuple(exceptions) if isinstance(exceptions, list) else exceptions)
    )
    _console = console or Console()

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except retry_exceptions as e:
                        if attempt == max_attempts:
                            _show_failure_message(func.__name__, max_attempts, _console)
                            raise

                        delay = _calculate_delay(attempt, backoff, max_delay)
                        _show_retry_message(
                            func.__name__,
                            attempt,
                            max_attempts,
                            delay,
                            type(e).__name__,
                            _console,
                        )

                        if on_retry:
                            on_retry(e, attempt)

                        await asyncio.sleep(delay)

                raise RuntimeError("Retry logic error")

            return async_wrapper

        else:

            @wraps(func)
            def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                for attempt in range(1, max_attempts + 1):
                    try:
                        return func(*args, **kwargs)
                    except retry_exceptions as e:
                        if attempt == max_attempts:
                            _show_failure_message(func.__name__, max_attempts, _console)
                            raise

                        delay = _calculate_delay(attempt, backoff, max_delay)
                        _show_retry_message(
                            func.__name__,
                            attempt,
                            max_attempts,
                            delay,
                            type(e).__name__,
                            _console,
                        )

                        if on_retry:
                            on_retry(e, attempt)

                        time.sleep(delay)

                raise RuntimeError("Retry logic error")

            return sync_wrapper

    return decorator
