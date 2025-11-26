"""Reusable decorators for consistent error handling across the codebase."""

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
    reraise: bool
    | None = None,  # If None, reraise is False when default_return is provided
):
    """
    Decorator to handle common file operation errors consistently.

    Args:
        exceptions: Tuple of exception types to catch
        default_return: Value to return when an exception occurs
        log_error: Whether to log the error
        reraise: Whether to reraise the exception after handling (None means False if default_return is provided)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.error(f"File operation failed in {func.__name__}: {e}")
                # Determine if we should reraise:
                # - if reraise is explicitly set to True/False, respect that
                # - if reraise is None (default):
                #   - reraise if no default_return is provided (when default_return is None)
                #   - don't reraise if default_return is provided
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
    reraise: bool
    | None = None,  # If None, reraise is False when default_return is provided
):
    """
    Decorator to handle JSON parsing errors consistently.

    Args:
        exceptions: Tuple of exception types to catch
        default_return: Value to return when an exception occurs
        log_error: Whether to log the error
        reraise: Whether to reraise the exception after handling (None means False if default_return is provided)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except exceptions as e:
                if log_error:
                    logger.error(f"JSON operation failed in {func.__name__}: {e}")
                # Determine if we should reraise:
                # - if reraise is explicitly set to True/False, respect that
                # - if reraise is None (default):
                #   - reraise if no default_return is provided (when default_return is None)
                #   - don't reraise if default_return is provided
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
    reraise: bool
    | None = None,  # If None, reraise is False when default_return is provided
):
    """
    Decorator to handle subprocess execution errors consistently.

    Args:
        exceptions: Tuple of exception types to catch
        default_return: Value to return when an exception occurs
        log_error: Whether to log the error
        reraise: Whether to reraise the exception after handling (None means False if default_return is provided)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except exceptions as e:
                if log_error:
                    logger.error(f"Subprocess operation failed in {func.__name__}: {e}")
                # Determine if we should reraise:
                # - if reraise is explicitly set to True/False, respect that
                # - if reraise is None (default):
                #   - reraise if no default_return is provided (when default_return is None)
                #   - don't reraise if default_return is provided
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
    reraise: bool
    | None = None,  # If None, reraise is False when default_return is provided
):
    """
    Decorator to handle data validation errors consistently.

    Args:
        exceptions: Tuple of exception types to catch
        default_return: Value to return when an exception occurs
        log_error: Whether to log the error
        reraise: Whether to reraise the exception after handling (None means False if default_return is provided)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except exceptions as e:
                if log_error:
                    logger.error(f"Validation failed in {func.__name__}: {e}")
                # Determine if we should reraise:
                # - if reraise is explicitly set to True/False, respect that
                # - if reraise is None (default):
                #   - reraise if no default_return is provided (when default_return is None)
                #   - don't reraise if default_return is provided
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
        # Add more common network errors as needed
    ),
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool
    | None = None,  # If None, reraise is False when default_return is provided
):
    """
    Decorator to handle network-related errors consistently.

    Args:
        exceptions: Tuple of exception types to catch
        default_return: Value to return when an exception occurs
        log_error: Whether to log the error
        reraise: Whether to reraise the exception after handling (None means False if default_return is provided)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except exceptions as e:
                if log_error:
                    logger.error(f"Network operation failed in {func.__name__}: {e}")
                # Determine if we should reraise:
                # - if reraise is explicitly set to True/False, respect that
                # - if reraise is None (default):
                #   - reraise if no default_return is provided (when default_return is None)
                #   - don't reraise if default_return is provided
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
    reraise: bool
    | None = None,  # If None, reraise is False when default_return is provided
    default_return: Any = None,
    exclude: tuple[type[BaseException], ...] = (KeyboardInterrupt, SystemExit),
):
    """
    Decorator to handle all errors except for specific system exceptions.

    Args:
        log_error: Whether to log the error
        reraise: Whether to reraise the exception after handling (None means False if default_return is provided)
        default_return: Value to return when an exception occurs
        exclude: Tuple of exception types to exclude from handling
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exclude:
                # Don't handle system exceptions like KeyboardInterrupt
                raise
            except Exception as e:
                if log_error:
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                # Determine if we should reraise:
                # - if reraise is explicitly set to True/False, respect that
                # - if reraise is None (default):
                #   - reraise if no default_return is provided (when default_return is None)
                #   - don't reraise if default_return is provided
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
    """
    Decorator to retry a function on specific exceptions.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts (in seconds)
        backoff: Multiplier for delay after each attempt
        exceptions: Tuple of exception types to retry on
        log_retry: Whether to log retry attempts
    """

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
                    if attempt < max_attempts - 1:  # Don't sleep after the last attempt
                        import time

                        time.sleep(current_delay)
                        current_delay *= backoff

            logger.error(
                f"All {max_attempts} attempts failed in {func.__name__}: {last_exception}"
            )
            raise last_exception

        return wrapper

    return decorator
