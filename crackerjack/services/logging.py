import logging
import sys
import time
import typing as t
import uuid
from contextvars import ContextVar
from pathlib import Path
from types import TracebackType
from typing import Any

import structlog
from structlog.types import EventDict, Processor

correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(cid: str) -> None:
    correlation_id.set(cid)


def get_correlation_id() -> str:
    cid = correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        correlation_id.set(cid)
    return cid


def add_correlation_id(_: Any, __: Any, event_dict: EventDict) -> EventDict:
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict


def add_timestamp(_: Any, __: Any, event_dict: EventDict) -> EventDict:
    event_dict["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return event_dict


def setup_structured_logging(
    level: str = "INFO",
    json_output: bool = True,
    log_file: Path | None = None,
) -> None:
    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        add_timestamp,
        add_correlation_id,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log_level = getattr(logging, level.upper())

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    handlers = [console_handler]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        format="%(message)s",
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


class LoggingContext:
    def __init__(self, operation: str, **kwargs: Any) -> None:
        self.operation = operation
        self.kwargs = kwargs
        self.correlation_id = str(uuid.uuid4())[:8]
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
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        def wrapper(*args: t.Any, **func_kwargs: t.Any) -> t.Any:
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
