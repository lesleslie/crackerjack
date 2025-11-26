"""Retry utilities for handling API connection errors and other transient failures.

This module provides a general-purpose retry decorator that can be used across
the Crackerjack codebase to handle API connection errors and other transient failures.
"""

import asyncio
import functools
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast

from loguru import logger

T = TypeVar("T")


def _calculate_delay(current_delay: float, jitter: bool, backoff: float) -> float:
    """Calculate the delay for the next retry attempt."""
    if jitter:
        return current_delay * (0.5 + random.random() * 0.5)  # nosec B311 # Not used for cryptographic purposes
    return current_delay * backoff


def _prepare_next_attempt(
    current_delay: float,
    max_delay: float | None,
    backoff: float,
    jitter: bool,
    attempt: int,
    max_attempts: int,
    e: BaseException,
    logger_func: Callable[[str], None] | None,
) -> float:
    """Prepare for the next retry attempt by calculating delay and logging."""
    current_delay = _calculate_delay(current_delay, jitter, backoff)

    if max_delay:
        current_delay = min(current_delay, max_delay)

    log_msg = (
        f"Attempt {attempt + 1}/{max_attempts} failed: {type(e).__name__}: {e}. "
        f"Retrying in {current_delay:.2f}s..."
    )

    if logger_func:
        logger_func(log_msg)
    else:
        logger.warning(log_msg)

    return current_delay


def _should_retry(attempt: int, max_attempts: int) -> bool:
    """Determine if we should make another retry attempt."""
    return attempt != max_attempts - 1  # Continue unless it's the last attempt


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float | None = None,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    logger_func: Callable[[str], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry a function when specific exceptions are raised.

    Args:
        max_attempts: Maximum number of attempts (including initial call)
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay between attempts (exponential backoff)
        max_delay: Maximum delay between retries (caps exponential growth)
        jitter: Add random jitter to delay to prevent thundering herd
        exceptions: Tuple of exception types to catch and retry on
        logger_func: Optional logger function to use for retry messages

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            return await _retry_async(
                func,
                args,
                kwargs,
                max_attempts,
                delay,
                backoff,
                max_delay,
                jitter,
                exceptions,
                logger_func,
            )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            return _retry_sync(
                func,
                args,
                kwargs,
                max_attempts,
                delay,
                backoff,
                max_delay,
                jitter,
                exceptions,
                logger_func,
            )

        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        return cast(Callable[..., T], sync_wrapper)

    return decorator


async def _retry_async[T](
    func: Callable[..., T],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    max_attempts: int,
    delay: float,
    backoff: float,
    max_delay: float | None,
    jitter: bool,
    exceptions: tuple[type[BaseException], ...],
    logger_func: Callable[[str], None] | None,
) -> T:
    """Execute async function with retry logic."""
    last_exception: BaseException | None = None
    current_delay = delay

    for attempt in range(max_attempts):
        try:
            result = await func(*args, **kwargs)  # type: ignore[misc]
            return result  # type: ignore[no-any-return]

        except exceptions as e:
            last_exception = e

            if not _should_retry(attempt, max_attempts):
                break

            current_delay = _prepare_next_attempt(
                current_delay,
                max_delay,
                backoff,
                jitter,
                attempt,
                max_attempts,
                e,
                logger_func,
            )

            await asyncio.sleep(current_delay)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Retry failed but no exception was captured")


def _retry_sync[T](
    func: Callable[..., T],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    max_attempts: int,
    delay: float,
    backoff: float,
    max_delay: float | None,
    jitter: bool,
    exceptions: tuple[type[BaseException], ...],
    logger_func: Callable[[str], None] | None,
) -> T:
    """Execute sync function with retry logic."""
    last_exception: BaseException | None = None
    current_delay = delay

    for attempt in range(max_attempts):
        try:
            result = func(*args, **kwargs)
            return result  # type: ignore[no-any-return]

        except exceptions as e:
            last_exception = e

            if not _should_retry(attempt, max_attempts):
                break

            current_delay = _prepare_next_attempt(
                current_delay,
                max_delay,
                backoff,
                jitter,
                attempt,
                max_attempts,
                e,
                logger_func,
            )

            time.sleep(current_delay)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Retry failed but no exception was captured")


# Common exception types for API connection retries
API_CONNECTION_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    OSError,  # Network-related OS errors
)


# Convenience decorator for API calls with common settings
def retry_api_call(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float | None = 30.0,  # Cap at 30 seconds
    jitter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Convenience decorator for API calls with sensible defaults.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        delay: Initial delay in seconds (default: 1.0)
        backoff: Exponential backoff multiplier (default: 2.0)
        max_delay: Maximum delay between retries (default: 30.0)
        jitter: Add jitter to prevent thundering herd (default: True)

    Returns:
        Decorator function configured for API calls
    """
    return retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=backoff,
        max_delay=max_delay,
        jitter=jitter,
        exceptions=API_CONNECTION_EXCEPTIONS,
    )


# Example usage functions for testing purposes
@retry_api_call(max_attempts=3, delay=0.5)
async def example_api_call_async(url: str) -> str:
    """Example async API call that might fail with network issues."""
    # Simulate an API call that might fail
    # import random  # Already imported at the top of the file

    if random.random() < 0.7:  # 70% chance of failure for testing # nosec B311
        raise ConnectionError("Simulated network error")

    return f"Success: {url}"


@retry_api_call(max_attempts=3, delay=0.5)
def example_api_call_sync(url: str) -> str:
    """Example sync API call that might fail with network issues."""
    # Simulate an API call that might fail
    # import random  # Already imported at the top of file

    if random.random() < 0.7:  # 70% chance of failure for testing # nosec B311
        raise ConnectionError("Simulated network error")

    return f"Success: {url}"
