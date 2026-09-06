from __future__ import annotations

import functools
import json
import subprocess
from types import FunctionType
from typing import Any, TypeVar, cast

from loguru import logger

_F = TypeVar("_F", bound=FunctionType)


def handle_file_errors(
    exceptions: tuple[type[Exception], ...] = (
        OSError,
        FileNotFoundError,
        PermissionError,
    ),
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool | None = None,
):
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.error(f"File operation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return cast(_F, wrapper)

    return decorator


def handle_json_errors(
    exceptions: tuple[type[Exception], ...] = (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ),
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool | None = None,
):
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.error(f"JSON operation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return cast(_F, wrapper)

    return decorator


def handle_subprocess_errors(
    exceptions: tuple[type[Exception], ...] = (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ),
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool | None = None,
):
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.error(f"Subprocess operation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return cast(_F, wrapper)

    return decorator


def handle_validation_errors(
    exceptions: tuple[type[Exception], ...] = (ValueError, TypeError, AttributeError),
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool | None = None,
):
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.error(f"Validation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return cast(_F, wrapper)

    return decorator


def handle_network_errors(
    exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        ConnectionRefusedError,
        TimeoutError,
    ),
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool | None = None,
):
    """Decorator that catches stdlib network exceptions and returns ``default_return``.

    Catches the built-in ``ConnectionError``, ``ConnectionRefusedError``, and
    ``TimeoutError`` by default. These cover stdlib networking (``socket``,
    ``urllib``, ``http.client``, ``asyncio``) and the errors raised by most
    third-party HTTP libraries that propagate stdlib exceptions.

    **Note**: ``requests.RequestException`` is intentionally NOT included —
    ``requests`` is not a crackerjack dependency. Callers that use ``requests``
    should pass ``exceptions=(requests.RequestException, ...)`` explicitly
    or import ``requests`` themselves and wrap the call. ``httpx`` errors are
    similarly NOT caught by default; ``httpx.ConnectError`` and
    ``httpx.TimeoutException`` inherit from stdlib ``ConnectionError`` /
    ``TimeoutError`` and are caught implicitly via those base classes.
    """
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.error(f"Network operation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return cast(_F, wrapper)

    return decorator


def handle_all_errors(
    log_error: bool = True,
    reraise: bool | None = None,
    default_return: Any = None,
    exclude: tuple[type[BaseException], ...] = (KeyboardInterrupt, SystemExit),
):
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exclude:
                raise
            except Exception as e:
                if log_error:
                    logger.error(f"Unexpected error in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return cast(_F, wrapper)

    return decorator


def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    log_retry: bool = True,
):
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    # Only warn when an actual retry will happen. Skipping
                    # the final attempt avoids duplicate noise — the loop
                    # exit already triggers `logger.error("All N attempts
                    # failed...")` below.
                    if log_retry and attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed in {func.__name__}: {e}. "
                            f"Retrying in {current_delay}s...",
                        )
                    if attempt < max_attempts - 1:
                        import time

                        time.sleep(current_delay)
                        current_delay *= backoff

            logger.error(
                f"All {max_attempts} attempts failed in {func.__name__}: {last_exception}",
            )
            if last_exception is None:
                msg = "Retry failed but no exception was captured"
                raise RuntimeError(msg)
            raise last_exception

        return cast(_F, wrapper)

    return decorator


__all__ = [
    "FunctionType",
    "handle_all_errors",
    "handle_file_errors",
    "handle_json_errors",
    "handle_network_errors",
    "handle_subprocess_errors",
    "handle_validation_errors",
    "retry_on_error",
]
