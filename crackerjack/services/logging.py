"""Crackerjack logging compatibility layer using ACB's logger.

This module provides backward compatibility with Crackerjack's logging API
while delegating to ACB's logger system. It maintains the same public API
for LoggingContext, get_logger(), and other utilities.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

import structlog

_correlation_id_var: ContextVar[str | None] = ContextVar(
    "crackerjack_correlation_id",
    default=None,
)

_logger_cache: dict[str, Any] = {}
_configured: bool = False
_processors: list[Callable[..., dict[str, Any]] | Any] = []


def add_correlation_id(
    _: Any, __: str | None, event_dict: dict[str, Any]
) -> dict[str, Any]:
    event_dict.setdefault("correlation_id", get_correlation_id())
    return event_dict


def add_timestamp(_: Any, __: str | None, event_dict: dict[str, Any]) -> dict[str, Any]:
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    event_dict.setdefault("timestamp", timestamp)
    return event_dict


def _configure_structlog(
    *,
    level: str,
    json_output: bool,
) -> None:
    def _render_key_values(_: Any, __: str | None, event_dict: dict[str, Any]) -> str:
        ordered: list[tuple[str, Any]] = []
        if "event" in event_dict:
            ordered.append(("event", event_dict["event"]))
        for key in sorted(k for k in event_dict if k != "event"):
            ordered.append((key, event_dict[key]))
        return " ".join(f"{key} = {value}" for key, value in ordered)

    global _processors
    processors: list[Callable[..., dict[str, Any]] | Any] = [
        add_timestamp,
        add_correlation_id,
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(_render_key_values)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _processors = processors


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
    """Setup structured logging for Crackerjack."""
    global _configured

    root_logger = logging.getLogger()
    for h in root_logger.handlers.copy():
        h.close()
        root_logger.removeHandler(h)
    root_logger.setLevel(level.upper())

    if json_output and log_file is not None:
        handler: logging.Handler = logging.FileHandler(log_file, mode="a")
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(handler)

    _configure_structlog(level=level, json_output=json_output)
    _logger_cache.clear()
    _configured = True


def get_logger(name: str) -> Any:
    """Get a structlog logger bound to a specific name."""
    if not _configured or not _processors:
        setup_structured_logging()

    if name in _logger_cache:
        return _logger_cache[name]

    stdlib_logger = logging.getLogger(name)
    stdlib_logger.setLevel(logging.getLogger().level)
    stdlib_logger.propagate = True

    logger_with_context = structlog.BoundLogger(
        stdlib_logger,
        processors=_processors,
        context={"logger": name},
    )
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
