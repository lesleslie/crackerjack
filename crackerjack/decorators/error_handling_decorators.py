import functools
import json
import subprocess
from collections.abc import Callable
from typing import Any

from loguru import logger


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
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
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

        return wrapper

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
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except exceptions as e:
                if log_error:
                    logger.error(f"JSON operation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return wrapper

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
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except exceptions as e:
                if log_error:
                    logger.error(f"Subprocess operation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return wrapper

    return decorator


def handle_validation_errors(
    exceptions: tuple[type[Exception], ...] = (ValueError, TypeError, AttributeError),
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool | None = None,
):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except exceptions as e:
                if log_error:
                    logger.error(f"Validation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return wrapper

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
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except exceptions as e:
                if log_error:
                    logger.error(f"Network operation failed in {func.__name__}: {e}")

                should_reraise = (
                    reraise if reraise is not None else (default_return is None)
                )
                if should_reraise:
                    raise
                return default_return

        return wrapper

    return decorator


def handle_all_errors(
    log_error: bool = True,
    reraise: bool | None = None,
    default_return: Any = None,
    exclude: tuple[type[BaseException], ...] = (KeyboardInterrupt, SystemExit),
):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
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

        return wrapper

    return decorator


def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    log_retry: bool = True,
):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if log_retry:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed in {func.__name__}: {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                    if attempt < max_attempts - 1:
                        import time

                        time.sleep(current_delay)
                        current_delay *= backoff

            logger.error(
                f"All {max_attempts} attempts failed in {func.__name__}: {last_exception}"
            )
            raise last_exception

        return wrapper

    return decorator
