"""Crackerjack logging compatibility layer using ACB's logger.

This module provides backward compatibility with Crackerjack's logging API
while delegating to ACB's logger system. It maintains the same public API
for LoggingContext, get_logger(), and other utilities.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from pathlib import Path
from types import TracebackType
from typing import Any

# Use ACB's Logger instead of loguru directly
from acb.logger import Logger

_correlation_id_var: ContextVar[str | None] = ContextVar(
    "crackerjack_correlation_id",
    default=None,
)

_logger_cache: dict[str, Any] = {}


def _get_acb_logger() -> Logger:
    """Get ACB logger instance from dependency injection."""
    # Create a new logger instance directly
    # ACB's Logger class is already properly initialized
    logger = Logger()
    return logger


def _generate_correlation_id() -> str:
    """Generate a unique correlation ID."""
    return uuid.uuid4().hex[:8]


def get_correlation_id() -> str:
    """Get or create correlation ID for current context."""
    correlation = _correlation_id_var.get()
    if correlation is None:
        correlation = _generate_correlation_id()
        _correlation_id_var.set(correlation)
    return correlation


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    _correlation_id_var.set(correlation_id)


def setup_structured_logging(
    *,
    level: str = "INFO",
    json_output: bool = False,
    log_file: Path | None = None,
) -> None:
    """Setup structured logging using ACB's logger.

    This function is maintained for backward compatibility but now uses
    ACB's logger configuration system.
    """
    # ACB logger is already configured via adapters
    # This function is kept for API compatibility but delegates to ACB
    _get_acb_logger()

    # ACB's logger is already configured, but we can adjust settings if needed
    # The actual configuration is handled by ACB's adapter system
    pass


def get_logger(name: str) -> Any:
    """Get a logger bound to a specific name using ACB's logger.

    This function provides backward compatibility with Crackerjack's
    logging API while using ACB's logger internally.
    """
    # Check cache first for performance
    if name in _logger_cache:
        return _logger_cache[name]

    # Get ACB logger and bind with context
    acb_logger = _get_acb_logger()
    logger_with_context = acb_logger.bind(logger=name)

    # Add correlation ID if available
    correlation_id = get_correlation_id()
    if correlation_id:
        logger_with_context = logger_with_context.bind(correlation_id=correlation_id)

    # Cache the logger for reuse
    _logger_cache[name] = logger_with_context
    return logger_with_context


class LoggingContext:
    """Context manager for operation logging with correlation IDs.

    Uses ACB's logger internally while maintaining Crackerjack's API.
    """

    def __init__(self, operation: str, **kwargs: Any) -> None:
        self.operation = operation
        self.kwargs = kwargs
        self.correlation_id = _generate_correlation_id()
        self.logger = get_logger("crackerjack.context")
        self.start_time = time.time()

    def __enter__(self) -> str:
        set_correlation_id(self.correlation_id)
        self.logger.info("Operation started", operation=self.operation, **self.kwargs)
        return self.correlation_id

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        _: TracebackType | None,
    ) -> None:
        duration = time.time() - self.start_time

        if exc_type is None:
            self.logger.info(
                "Operation completed",
                operation=self.operation,
                duration_seconds=round(duration, 3),
                **self.kwargs,
            )
        else:
            self.logger.error(
                "Operation failed",
                operation=self.operation,
                duration_seconds=round(duration, 3),
                error=str(exc_val),
                error_type=exc_type.__name__ if exc_type else None,
                **self.kwargs,
            )


def log_performance(
    operation: str,
    **kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for performance logging using ACB's logger.

    Maintains Crackerjack's API while delegating to ACB's logger.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **func_kwargs: Any) -> Any:
            logger = get_logger(f"crackerjack.perf.{func.__name__}")
            start_time = time.time()

            try:
                result = func(*args, **func_kwargs)
                duration = time.time() - start_time
                logger.info(
                    "Function completed",
                    operation=operation,
                    function=func.__name__,
                    duration_seconds=round(duration, 3),
                    success=True,
                    **kwargs,
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.exception(
                    "Function failed",
                    operation=operation,
                    function=func.__name__,
                    duration_seconds=round(duration, 3),
                    success=False,
                    error=str(e),
                    error_type=type(e).__name__,
                    **kwargs,
                )
                raise

        return wrapper

    return decorator


# Module-level logger instances using ACB's logger
hook_logger = get_logger("crackerjack.hooks")
test_logger = get_logger("crackerjack.tests")
config_logger = get_logger("crackerjack.config")
cache_logger = get_logger("crackerjack.cache")
security_logger = get_logger("crackerjack.security")
performance_logger = get_logger("crackerjack.performance")
