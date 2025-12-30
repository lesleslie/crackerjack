import asyncio
import builtins
import logging
import time
import typing as t
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

logger = logging.getLogger("crackerjack.timeout_manager")


class _DummyPerformanceMonitor:
    def record_operation_start(self, operation: str) -> float:
        return time.time()

    def record_operation_success(self, operation: str, start_time: float) -> None:
        pass

    def record_operation_failure(self, operation: str, start_time: float) -> None:
        pass

    def record_operation_timeout(
        self,
        operation: str,
        start_time: float,
        timeout_value: float,
        error_message: str,
    ) -> None:
        pass

    def record_circuit_breaker_event(self, operation: str, opened: bool) -> None:
        pass

    def get_summary_stats(self) -> dict[str, t.Any]:
        return {}

    def get_all_metrics(self) -> dict[str, t.Any]:
        return {}

    def get_performance_alerts(self) -> list[str]:
        return []

    def get_recent_timeout_events(self, limit: int) -> list[t.Any]:
        return []


class TimeoutStrategy(Enum):
    FAIL_FAST = "fail_fast"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"
    GRACEFUL_DEGRADATION = "graceful_degradation"


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class TimeoutConfig:
    default_timeout: float = 30.0
    operation_timeouts: dict[str, float] = field(
        default_factory=lambda: {
            "fast_hooks": 60.0,
            "comprehensive_hooks": 300.0,
            "test_execution": 600.0,
            "ai_agent_processing": 180.0,
            "file_operations": 10.0,
            "network_operations": 15.0,
            "workflow_iteration": 900.0,
            "complete_workflow": 3600.0,
        }
    )

    max_retries: int = 3
    base_retry_delay: float = 1.0
    max_retry_delay: float = 60.0
    backoff_multiplier: float = 2.0

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3


@dataclass
class CircuitBreakerStateData:
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    half_open_calls: int = 0


class TimeoutError(Exception):
    def __init__(self, operation: str, timeout: float, elapsed: float = 0.0) -> None:
        self.operation = operation
        self.timeout = timeout
        self.elapsed = elapsed
        super().__init__(
            f"Operation '{operation}' timed out after {timeout}s "
            f"(elapsed: {elapsed: .1f}s)"
        )


class AsyncTimeoutManager:
    def __init__(self, config: TimeoutConfig | None = None) -> None:
        self.config = config or TimeoutConfig()
        self.circuit_breakers: dict[str, CircuitBreakerStateData] = {}
        self.operation_stats: dict[str, list[float]] = {}

        self._performance_monitor: t.Any = None

    def get_timeout(self, operation: str) -> float:
        return self.config.operation_timeouts.get(
            operation, self.config.default_timeout
        )

    @property
    def performance_monitor(self) -> t.Any:
        if self._performance_monitor is None:
            try:
                from .performance_monitor import get_performance_monitor

                self._performance_monitor = get_performance_monitor()
            except ImportError:
                self._performance_monitor = _DummyPerformanceMonitor()
        return self._performance_monitor

    def _handle_operation_success(self, operation: str, start_time: float) -> float:
        """Handle successful operation completion."""
        self.performance_monitor.record_operation_success(operation, start_time)
        elapsed = time.time() - start_time
        self._record_success(operation, elapsed)
        return elapsed

    def _handle_timeout_error(
        self,
        operation: str,
        start_time: float,
        timeout_value: float,
        strategy: TimeoutStrategy,
        error_msg: str = "",
        error_type: str = "custom_timeout",
    ) -> float | None:
        """Handle timeout error based on strategy."""
        elapsed = time.time() - start_time
        self.performance_monitor.record_operation_timeout(
            operation, start_time, timeout_value, error_msg
        )
        self._record_failure(operation, elapsed)

        if strategy == TimeoutStrategy.CIRCUIT_BREAKER:
            self._update_circuit_breaker(operation, False)

        if strategy == TimeoutStrategy.GRACEFUL_DEGRADATION:
            logger.warning(
                f"Operation {operation} {error_type} ({elapsed: .1f}s), continuing gracefully"
            )
            return elapsed  # Return elapsed time to indicate graceful degradation

        return None

    @asynccontextmanager
    async def _execute_with_timeout_context(self, timeout_value: float):
        """Execute the context with timeout handling."""
        try:
            async with asyncio.timeout(timeout_value):
                yield
        except AttributeError:
            task = asyncio.current_task()
            if task:
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=timeout_value)
                    yield
                except builtins.TimeoutError:
                    raise TimeoutError("operation", timeout_value)
            else:
                yield

    def _should_yield_on_graceful_degradation(self, result: float | None) -> bool:
        """Check if graceful degradation should yield."""
        return result is not None

    def _handle_custom_timeout_exception(
        self,
        operation: str,
        start_time: float,
        timeout_value: float,
        strategy: TimeoutStrategy,
        error: TimeoutError,
    ) -> float | None:
        """Handle custom TimeoutError exception."""
        return self._handle_timeout_error(
            operation, start_time, timeout_value, strategy, str(error), "timed out"
        )

    def _handle_asyncio_timeout_exception(
        self,
        operation: str,
        start_time: float,
        timeout_value: float,
        strategy: TimeoutStrategy,
    ) -> float | None:
        """Handle asyncio.timeout context manager timeout."""
        return self._handle_timeout_error(
            operation,
            start_time,
            timeout_value,
            strategy,
            "asyncio timeout",
            "timed out",
        )

    def _handle_cancelled_exception(
        self,
        operation: str,
        start_time: float,
        timeout_value: float,
        strategy: TimeoutStrategy,
    ) -> float | None:
        """Handle asyncio.CancelledError exception."""
        return self._handle_timeout_error(
            operation, start_time, timeout_value, strategy, "cancelled", "was cancelled"
        )

    def _handle_generic_exception(
        self, operation: str, start_time: float, strategy: TimeoutStrategy
    ) -> None:
        """Handle generic exceptions."""
        self.performance_monitor.record_operation_failure(operation, start_time)
        elapsed = time.time() - start_time
        self._record_failure(operation, elapsed)

        if strategy == TimeoutStrategy.CIRCUIT_BREAKER:
            self._update_circuit_breaker(operation, False)

    def _dispatch_exception_handler(
        self,
        error: Exception,
        operation: str,
        start_time: float,
        timeout_value: float,
        strategy: TimeoutStrategy,
    ) -> tuple[bool, Exception | None]:
        """Dispatch exception to appropriate handler."""
        # Custom TimeoutError
        if isinstance(error, TimeoutError):
            result = self._handle_custom_timeout_exception(
                operation, start_time, timeout_value, strategy, error
            )
            should_yield = self._should_yield_on_graceful_degradation(result)
            return should_yield, (None if should_yield else error)

        # Asyncio timeout
        if isinstance(error, builtins.TimeoutError):
            result = self._handle_asyncio_timeout_exception(
                operation, start_time, timeout_value, strategy
            )
            should_yield = self._should_yield_on_graceful_degradation(result)
            reraise_error = TimeoutError(
                operation, timeout_value, time.time() - start_time
            )
            return should_yield, (None if should_yield else reraise_error)

        # Cancelled error
        if isinstance(error, asyncio.CancelledError):
            result = self._handle_cancelled_exception(
                operation, start_time, timeout_value, strategy
            )
            should_yield = self._should_yield_on_graceful_degradation(result)
            reraise_error = TimeoutError(
                operation, timeout_value, time.time() - start_time
            )
            return should_yield, (None if should_yield else reraise_error)

        # Generic exception
        self._handle_generic_exception(operation, start_time, strategy)
        return False, error

    @asynccontextmanager
    async def timeout_context(
        self,
        operation: str,
        timeout: float | None = None,
        strategy: TimeoutStrategy = TimeoutStrategy.FAIL_FAST,
    ) -> t.AsyncIterator[None]:
        timeout_value = timeout or self.get_timeout(operation)
        start_time = self.performance_monitor.record_operation_start(operation)

        if timeout_value > 7200.0:
            logger.warning(
                f"Capping excessive timeout for {operation}: {timeout_value}s -> 7200s"
            )
            timeout_value = 7200.0

        try:
            async with self._execute_with_timeout_context(timeout_value):
                yield
            self._handle_operation_success(operation, start_time)

        except Exception as e:
            should_yield, error = self._dispatch_exception_handler(
                e, operation, start_time, timeout_value, strategy
            )
            # For graceful degradation, don't re-raise the exception
            if error:
                raise error

    async def with_timeout(
        self,
        operation: str,
        coro: t.Awaitable[t.Any],
        timeout: float | None = None,
        strategy: TimeoutStrategy = TimeoutStrategy.FAIL_FAST,
    ) -> t.Any:
        if strategy == TimeoutStrategy.CIRCUIT_BREAKER:
            if not self._check_circuit_breaker(operation):
                raise TimeoutError(operation, 0.0, 0.0)

        timeout_value = timeout or self.get_timeout(operation)
        start_time = self.performance_monitor.record_operation_start(operation)

        try:
            result = await asyncio.wait_for(coro, timeout=timeout_value)

            self.performance_monitor.record_operation_success(operation, start_time)
            elapsed = time.time() - start_time
            self._record_success(operation, elapsed)

            if strategy == TimeoutStrategy.CIRCUIT_BREAKER:
                self._update_circuit_breaker(operation, True)

            return result

        except builtins.TimeoutError as e:
            elapsed = time.time() - start_time
            self.performance_monitor.record_operation_timeout(
                operation, start_time, timeout_value, str(e)
            )
            self._record_failure(operation, elapsed)

            if strategy == TimeoutStrategy.CIRCUIT_BREAKER:
                self._update_circuit_breaker(operation, False)

            if strategy == TimeoutStrategy.GRACEFUL_DEGRADATION:
                logger.warning(
                    f"Operation {operation} timed out ({elapsed: .1f}s), returning None"
                )
                return None

            raise TimeoutError(operation, timeout_value, elapsed) from e

        except Exception:
            self.performance_monitor.record_operation_failure(operation, start_time)
            elapsed = time.time() - start_time
            self._record_failure(operation, elapsed)

            if strategy == TimeoutStrategy.CIRCUIT_BREAKER:
                self._update_circuit_breaker(operation, False)

            raise

    async def _with_retry(
        self,
        operation: str,
        coro_factory: t.Callable[[], t.Awaitable[t.Any]],
        timeout: float | None = None,
    ) -> t.Any:
        last_exception = None
        delay = self.config.base_retry_delay

        for attempt in range(self.config.max_retries + 1):
            try:
                async with self.timeout_context(operation, timeout):
                    return await coro_factory()
            except (TimeoutError, Exception) as e:
                last_exception = e

                if attempt == self.config.max_retries:
                    break

                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_retries + 1} "
                    f"failed for {operation}: {e}, retrying in {delay}s"
                )

                await asyncio.sleep(delay)
                delay = min(
                    delay * self.config.backoff_multiplier, self.config.max_retry_delay
                )

        if last_exception is not None:
            raise last_exception
        raise RuntimeError(f"No attempts made for operation: {operation}")

    def _check_circuit_breaker(self, operation: str) -> bool:
        if operation not in self.circuit_breakers:
            self.circuit_breakers[operation] = CircuitBreakerStateData()
            return True

        breaker = self.circuit_breakers[operation]
        current_time = time.time()

        if breaker.state == CircuitBreakerState.CLOSED:
            return True
        elif breaker.state == CircuitBreakerState.OPEN:
            if current_time - breaker.last_failure_time > self.config.recovery_timeout:
                breaker.state = CircuitBreakerState.HALF_OPEN
                breaker.half_open_calls = 0
                return True
            return False
        else:
            if breaker.half_open_calls < self.config.half_open_max_calls:
                breaker.half_open_calls += 1
                return True
            return False

    def _update_circuit_breaker(self, operation: str, success: bool) -> None:
        if operation not in self.circuit_breakers:
            self.circuit_breakers[operation] = CircuitBreakerStateData()

        breaker = self.circuit_breakers[operation]
        previous_state = breaker.state

        if success:
            if breaker.state == CircuitBreakerState.HALF_OPEN:
                breaker.state = CircuitBreakerState.CLOSED
                breaker.failure_count = 0
            elif breaker.state == CircuitBreakerState.CLOSED:
                breaker.failure_count = max(0, breaker.failure_count - 1)
        else:
            breaker.failure_count += 1
            breaker.last_failure_time = time.time()

            if breaker.failure_count >= self.config.failure_threshold:
                breaker.state = CircuitBreakerState.OPEN

                if previous_state != CircuitBreakerState.OPEN:
                    self.performance_monitor.record_circuit_breaker_event(
                        operation, True
                    )

    def _record_success(self, operation: str, elapsed: float) -> None:
        if operation not in self.operation_stats:
            self.operation_stats[operation] = []

        stats = self.operation_stats[operation]
        stats.append(elapsed)

        if len(stats) > 100:
            stats.pop(0)

        if self.config.operation_timeouts.get(operation):
            self._update_circuit_breaker(operation, True)

    def _record_failure(self, operation: str, elapsed: float) -> None:
        logger.warning(
            f"Operation '{operation}' failed after {elapsed: .1f}s "
            f"(timeout: {self.get_timeout(operation)}s)"
        )

    def get_stats(self, operation: str) -> dict[str, t.Any]:
        stats = self.operation_stats.get(operation, [])
        if not stats:
            return {
                "count": 0,
                "avg_time": 0.0,
                "min_time": 0.0,
                "max_time": 0.0,
                "success_rate": 0.0,
            }

        return {
            "count": len(stats),
            "avg_time": sum(stats) / len(stats),
            "min_time": min(stats),
            "max_time": max(stats),
            "success_rate": len(stats)
            / (
                len(stats)
                + self.circuit_breakers.get(
                    operation, CircuitBreakerStateData()
                ).failure_count
            ),
        }


def timeout_async(
    operation: str,
    timeout: float | None = None,
    strategy: TimeoutStrategy = TimeoutStrategy.FAIL_FAST,
) -> t.Callable[
    [t.Callable[..., t.Awaitable[t.Any]]], t.Callable[..., t.Awaitable[t.Any]]
]:
    def decorator(
        func: t.Callable[..., t.Awaitable[t.Any]],
    ) -> t.Callable[..., t.Awaitable[t.Any]]:
        @wraps(func)
        async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            manager = AsyncTimeoutManager()
            return await manager.with_timeout(
                operation, func(*args, **kwargs), timeout, strategy
            )

        return wrapper

    return decorator


_global_timeout_manager: AsyncTimeoutManager | None = None


def get_timeout_manager() -> AsyncTimeoutManager:
    global _global_timeout_manager
    if _global_timeout_manager is None:
        _global_timeout_manager = AsyncTimeoutManager()
    return _global_timeout_manager


def configure_timeouts(config: TimeoutConfig) -> None:
    global _global_timeout_manager
    _global_timeout_manager = AsyncTimeoutManager(config)


def get_performance_report() -> dict[str, t.Any]:
    timeout_manager = get_timeout_manager()
    monitor = timeout_manager.performance_monitor

    return {
        "summary": monitor.get_summary_stats(),
        "metrics": {
            name: {
                "success_rate": m.success_rate,
                "average_time": m.average_time,
                "recent_average_time": m.recent_average_time,
                "total_calls": m.total_calls,
                "timeout_calls": m.timeout_calls,
            }
            for name, m in monitor.get_all_metrics().items()
        },
        "alerts": monitor.get_performance_alerts(),
        "recent_timeouts": [
            {
                "operation": event.operation,
                "expected_timeout": event.expected_timeout,
                "actual_duration": event.actual_duration,
                "timestamp": event.timestamp,
            }
            for event in monitor.get_recent_timeout_events(10)
        ],
        "circuit_breakers": {
            operation: {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "last_failure_time": breaker.last_failure_time,
            }
            for operation, breaker in timeout_manager.circuit_breakers.items()
        },
    }
