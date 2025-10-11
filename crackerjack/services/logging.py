from acb.logging import get_logger, setup_logging


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
