from __future__ import annotations

import time
import uuid

try:
    from druva import generate as generate_ulid
except ImportError:
    generate_ulid = None
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import TracebackType

_correlation_id_var: ContextVar[str | None] = ContextVar(
    "crackerjack_correlation_id",
    default=None,
)

_logger_cache: dict[str, Any] = {}
_configured: bool = False
_processors: list[Callable[..., dict[str, Any]] | Any] = []


def add_correlation_id(
    _: Any,
    __: str | None,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    event_dict.setdefault("correlation_id", get_correlation_id())
    return event_dict


def _generate_correlation_id() -> str:
    if generate_ulid:
        return generate_ulid()[:16]

    return uuid.uuid4().hex[:8]


def get_correlation_id() -> str:
    correlation = _correlation_id_var.get()
    if correlation is None:
        correlation = _generate_correlation_id()
        _correlation_id_var.set(correlation)
    return correlation


def set_correlation_id(correlation_id: str) -> None:
    _correlation_id_var.set(correlation_id)


def _configure_structlog_correlation(
    *,
    level: str,
    json_output: bool,
) -> None:
    import logging as stdlib_logging

    current_cfg = structlog.get_config()
    base_processors = list(current_cfg.get("processors", []))
    if add_correlation_id not in base_processors:
        base_processors.insert(0, add_correlation_id)

    global _processors
    _processors = base_processors

    structlog.configure(
        processors=base_processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(stdlib_logging, level.upper(), stdlib_logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def setup_structured_logging(
    *,
    level: str = "INFO",
    json_output: bool = False,
    log_file: Path | None = None,
) -> None:
    from oneiric.core.logging import LoggingConfig
    from oneiric.core.logging import configure_logging as oneiric_configure

    oneiric_cfg = LoggingConfig(
        level=level.upper(),
        emit_json=json_output,
    )
    oneiric_configure(oneiric_cfg)

    _configure_structlog_correlation(level=level, json_output=json_output)
    _logger_cache.clear()
    _configured = True


def get_logger(name: str) -> Any:
    global _configured
    if not _configured:
        _configure_structlog_correlation(level="INFO", json_output=False)
        _configured = True

    return structlog.get_logger(name)


class LoggingContext:
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


hook_logger = get_logger("crackerjack.hooks")
test_logger = get_logger("crackerjack.tests")
config_logger = get_logger("crackerjack.config")
cache_logger = get_logger("crackerjack.cache")
security_logger = get_logger("crackerjack.security")
performance_logger = get_logger("crackerjack.performance")
