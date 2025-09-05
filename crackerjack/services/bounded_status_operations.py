"""
Bounded Status Operations to prevent DoS attacks.

Provides comprehensive operation limits, circuit breakers, and
resource protection for status collection operations.
"""

import asyncio
import time
import typing as t
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock

from .security_logger import SecurityEventLevel, SecurityEventType, get_security_logger


class OperationState(str, Enum):
    """States for circuit breaker pattern."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit breaker tripped
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class OperationLimits:
    """Limits for status operations."""

    max_concurrent_operations: int = 10
    max_operations_per_minute: int = 60
    max_operation_duration: float = 30.0
    max_memory_usage_mb: int = 50
    max_cpu_time_seconds: float = 5.0
    max_file_operations: int = 100
    timeout_seconds: float = 15.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0


@dataclass
class OperationMetrics:
    """Metrics for operation tracking."""

    operation_id: str
    operation_type: str
    client_id: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    memory_usage: int = 0
    cpu_time: float = 0.0
    file_operations: int = 0
    success: bool | None = None
    error_message: str | None = None

    @property
    def duration(self) -> float:
        """Get operation duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def is_completed(self) -> bool:
        """Check if operation is completed."""
        return self.end_time is not None


class OperationLimitExceededError(Exception):
    """Raised when operation limits are exceeded."""

    pass


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class BoundedStatusOperations:
    """
    Bounded operations manager for status collection.

    Features:
    - Concurrent operation limits
    - Rate limiting per client
    - Memory and CPU usage monitoring
    - Circuit breaker pattern for fault tolerance
    - Operation timeout enforcement
    - Comprehensive metrics collection
    """

    def __init__(self, limits: OperationLimits | None = None):
        """
        Initialize bounded operations manager.

        Args:
            limits: Operation limits configuration
        """
        self.limits = limits or OperationLimits()
        self.security_logger = get_security_logger()

        # Thread-safe operation tracking
        self._lock = RLock()
        self._active_operations: dict[str, OperationMetrics] = {}
        self._client_operations: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=100)
        )
        self._operation_history: list[OperationMetrics] = []

        # Circuit breaker tracking
        self._circuit_states: dict[str, OperationState] = defaultdict(
            lambda: OperationState.CLOSED
        )
        self._failure_counts: dict[str, int] = defaultdict(int)
        self._last_failure_times: dict[str, float] = {}

        # Resource usage tracking
        self._total_memory_usage = 0
        self._total_cpu_time = 0.0
        self._total_file_operations = 0

        # Operation type definitions
        self._operation_types = {
            "collect_status": "Status collection operation",
            "get_jobs": "Job information retrieval",
            "get_services": "Service status check",
            "get_metrics": "Metrics collection",
            "health_check": "Health check operation",
        }

    async def execute_bounded_operation(
        self,
        operation_type: str,
        client_id: str,
        operation_func: t.Callable[..., t.Awaitable[t.Any]],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any:
        """
        Execute a bounded status operation with comprehensive limits.

        Args:
            operation_type: Type of operation being performed
            client_id: Client identifier
            operation_func: Async function to execute
            *args: Positional arguments for operation_func
            **kwargs: Keyword arguments for operation_func

        Returns:
            Result of the operation

        Raises:
            OperationLimitExceededError: If operation limits exceeded
            CircuitBreakerOpenError: If circuit breaker is open
            asyncio.TimeoutError: If operation times out
        """

        # Check circuit breaker
        self._check_circuit_breaker(operation_type)

        # Validate operation can be started
        operation_id = self._validate_and_reserve_operation(operation_type, client_id)

        # Create operation metrics
        metrics = OperationMetrics(
            operation_id=operation_id,
            operation_type=operation_type,
            client_id=client_id,
        )

        try:
            # Register operation
            with self._lock:
                self._active_operations[operation_id] = metrics

            # Execute with timeout and resource monitoring
            result = await self._execute_with_monitoring(
                operation_func, metrics, *args, **kwargs
            )

            # Mark as successful
            metrics.success = True
            metrics.end_time = time.time()

            # Update circuit breaker on success
            self._record_operation_success(operation_type)

            # Log successful operation
            self.security_logger.log_security_event(
                event_type=SecurityEventType.OPERATION_SUCCESS,
                level=SecurityEventLevel.LOW,
                message=f"Operation completed: {operation_type}",
                client_id=client_id,
                operation=operation_type,
                additional_data={
                    "operation_id": operation_id,
                    "duration": metrics.duration,
                    "memory_usage": metrics.memory_usage,
                    "cpu_time": metrics.cpu_time,
                    "file_operations": metrics.file_operations,
                },
            )

            return result

        except Exception as e:
            # Mark as failed
            metrics.success = False
            metrics.end_time = time.time()
            metrics.error_message = str(e)

            # Update circuit breaker on failure
            self._record_operation_failure(operation_type)

            # Log failed operation
            self.security_logger.log_security_event(
                event_type=SecurityEventType.OPERATION_FAILURE,
                level=SecurityEventLevel.HIGH,
                message=f"Operation failed: {operation_type} - {e}",
                client_id=client_id,
                operation=operation_type,
                additional_data={
                    "operation_id": operation_id,
                    "duration": metrics.duration,
                    "error": str(e),
                },
            )

            raise

        finally:
            # Clean up operation
            self._cleanup_operation(operation_id, metrics)

    def _check_circuit_breaker(self, operation_type: str) -> None:
        """Check if circuit breaker allows operation."""

        current_time = time.time()

        with self._lock:
            state = self._circuit_states[operation_type]
            failure_count = self._failure_counts[operation_type]
            last_failure = self._last_failure_times.get(operation_type, 0)

            if state == OperationState.OPEN:
                # Check if circuit breaker timeout has passed
                if current_time - last_failure >= self.limits.circuit_breaker_timeout:
                    # Move to half-open state for testing
                    self._circuit_states[operation_type] = OperationState.HALF_OPEN
                    self.security_logger.log_security_event(
                        event_type=SecurityEventType.CIRCUIT_BREAKER_HALF_OPEN,
                        level=SecurityEventLevel.LOW,
                        message=f"Circuit breaker half-open: {operation_type}",
                        operation=operation_type,
                    )
                else:
                    # Circuit breaker still open
                    self.security_logger.log_security_event(
                        event_type=SecurityEventType.CIRCUIT_BREAKER_OPEN,
                        level=SecurityEventLevel.MEDIUM,
                        message=f"Circuit breaker open: {operation_type}",
                        operation=operation_type,
                        additional_data={
                            "failure_count": failure_count,
                            "time_remaining": self.limits.circuit_breaker_timeout
                            - (current_time - last_failure),
                        },
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker open for {operation_type}"
                    )

    def _validate_and_reserve_operation(
        self, operation_type: str, client_id: str
    ) -> str:
        """Validate operation can be started and reserve resources."""

        current_time = time.time()
        operation_id = f"{operation_type}_{client_id}_{int(current_time * 1000)}"

        with self._lock:
            # Check concurrent operation limit
            if len(self._active_operations) >= self.limits.max_concurrent_operations:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                    level=SecurityEventLevel.MEDIUM,
                    message=f"Max concurrent operations exceeded: {len(self._active_operations)}",
                    client_id=client_id,
                    operation=operation_type,
                )
                raise OperationLimitExceededError(
                    f"Maximum concurrent operations exceeded: {len(self._active_operations)}"
                )

            # Check client rate limiting
            client_ops = self._client_operations[client_id]

            # Remove operations older than 1 minute
            while client_ops and current_time - client_ops[0] > 60.0:
                client_ops.popleft()

            if len(client_ops) >= self.limits.max_operations_per_minute:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                    level=SecurityEventLevel.MEDIUM,
                    message=f"Client operation rate limit exceeded: {len(client_ops)}",
                    client_id=client_id,
                    operation=operation_type,
                )
                raise OperationLimitExceededError(
                    f"Operation rate limit exceeded: {len(client_ops)} operations/min"
                )

            # Check resource usage limits
            if (
                self._total_memory_usage
                >= self.limits.max_memory_usage_mb * 1024 * 1024
            ):
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.RESOURCE_EXHAUSTED,
                    level=SecurityEventLevel.HIGH,
                    message=f"Memory limit exceeded: {self._total_memory_usage / 1024 / 1024:.1f}MB",
                    client_id=client_id,
                    operation=operation_type,
                )
                raise OperationLimitExceededError(
                    f"Memory limit exceeded: {self._total_memory_usage / 1024 / 1024:.1f}MB"
                )

            # Record operation start
            client_ops.append(current_time)

        return operation_id

    async def _execute_with_monitoring(
        self,
        operation_func: t.Callable[..., t.Awaitable[t.Any]],
        metrics: OperationMetrics,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any:
        """Execute operation with resource monitoring and timeout."""

        # Create monitoring task
        monitor_task = asyncio.create_task(self._monitor_operation(metrics))

        try:
            # Execute operation with timeout
            result = await asyncio.wait_for(
                operation_func(*args, **kwargs),
                timeout=self.limits.timeout_seconds,
            )

            return result

        except TimeoutError:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.OPERATION_TIMEOUT,
                level=SecurityEventLevel.HIGH,
                message=f"Operation timeout: {metrics.operation_type}",
                client_id=metrics.client_id,
                operation=metrics.operation_type,
                additional_data={
                    "operation_id": metrics.operation_id,
                    "timeout": self.limits.timeout_seconds,
                },
            )
            raise TimeoutError(
                f"Operation timed out after {self.limits.timeout_seconds}s"
            )

        finally:
            # Cancel monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_operation(self, metrics: OperationMetrics) -> None:
        """Monitor operation resource usage."""

        import os

        import psutil

        try:
            process = psutil.Process(os.getpid())
            initial_cpu_time = process.cpu_times().user + process.cpu_times().system

            while not metrics.is_completed:
                try:
                    # Update CPU time
                    current_cpu_time = (
                        process.cpu_times().user + process.cpu_times().system
                    )
                    metrics.cpu_time = current_cpu_time - initial_cpu_time

                    # Update memory usage
                    metrics.memory_usage = process.memory_info().rss

                    # Check limits
                    if metrics.cpu_time > self.limits.max_cpu_time_seconds:
                        self.security_logger.log_security_event(
                            event_type=SecurityEventType.RESOURCE_LIMIT_EXCEEDED,
                            level=SecurityEventLevel.MEDIUM,
                            message=f"CPU time limit exceeded: {metrics.cpu_time:.2f}s",
                            client_id=metrics.client_id,
                            operation=metrics.operation_type,
                            additional_data={"operation_id": metrics.operation_id},
                        )
                        break

                    if metrics.duration > self.limits.max_operation_duration:
                        self.security_logger.log_security_event(
                            event_type=SecurityEventType.OPERATION_DURATION_EXCEEDED,
                            level=SecurityEventLevel.MEDIUM,
                            message=f"Operation duration limit exceeded: {metrics.duration:.2f}s",
                            client_id=metrics.client_id,
                            operation=metrics.operation_type,
                            additional_data={"operation_id": metrics.operation_id},
                        )
                        break

                    await asyncio.sleep(0.1)  # Monitor every 100ms

                except psutil.NoSuchProcess:
                    break

        except Exception as e:
            # Monitoring failure shouldn't stop the operation
            self.security_logger.log_security_event(
                event_type=SecurityEventType.MONITORING_ERROR,
                level=SecurityEventLevel.MEDIUM,
                message=f"Operation monitoring failed: {e}",
                client_id=metrics.client_id,
                operation=metrics.operation_type,
            )

    def _record_operation_success(self, operation_type: str) -> None:
        """Record successful operation for circuit breaker."""

        with self._lock:
            state = self._circuit_states[operation_type]

            if state == OperationState.HALF_OPEN:
                # Success in half-open state - close circuit breaker
                self._circuit_states[operation_type] = OperationState.CLOSED
                self._failure_counts[operation_type] = 0

                self.security_logger.log_security_event(
                    event_type=SecurityEventType.CIRCUIT_BREAKER_CLOSED,
                    level=SecurityEventLevel.LOW,
                    message=f"Circuit breaker closed: {operation_type}",
                    operation=operation_type,
                )
            elif state == OperationState.CLOSED:
                # Reset failure count on success
                self._failure_counts[operation_type] = 0

    def _record_operation_failure(self, operation_type: str) -> None:
        """Record failed operation for circuit breaker."""

        current_time = time.time()

        with self._lock:
            self._failure_counts[operation_type] += 1
            self._last_failure_times[operation_type] = current_time

            state = self._circuit_states[operation_type]
            failure_count = self._failure_counts[operation_type]

            if failure_count >= self.limits.circuit_breaker_threshold:
                if state != OperationState.OPEN:
                    # Trip circuit breaker
                    self._circuit_states[operation_type] = OperationState.OPEN

                    self.security_logger.log_security_event(
                        event_type=SecurityEventType.CIRCUIT_BREAKER_OPEN,
                        level=SecurityEventLevel.HIGH,
                        message=f"Circuit breaker opened: {operation_type}",
                        operation=operation_type,
                        additional_data={
                            "failure_count": failure_count,
                            "threshold": self.limits.circuit_breaker_threshold,
                        },
                    )

    def _cleanup_operation(self, operation_id: str, metrics: OperationMetrics) -> None:
        """Clean up operation and update metrics."""

        with self._lock:
            # Remove from active operations
            if operation_id in self._active_operations:
                del self._active_operations[operation_id]

            # Add to history (keep last 1000 operations)
            self._operation_history.append(metrics)
            if len(self._operation_history) > 1000:
                self._operation_history.pop(0)

            # Update resource usage tracking
            self._total_memory_usage = max(
                0, self._total_memory_usage - metrics.memory_usage
            )
            self._total_cpu_time += metrics.cpu_time
            self._total_file_operations += metrics.file_operations

    def get_operation_status(self) -> dict[str, t.Any]:
        """Get current operation status and limits."""

        with self._lock:
            current_time = time.time()

            # Calculate recent operation stats
            recent_ops = [
                m
                for m in self._operation_history
                if current_time - m.start_time < 300  # Last 5 minutes
            ]

            successful_ops = [m for m in recent_ops if m.success is True]
            failed_ops = [m for m in recent_ops if m.success is False]

            return {
                "active_operations": len(self._active_operations),
                "max_concurrent": self.limits.max_concurrent_operations,
                "recent_operations": {
                    "total": len(recent_ops),
                    "successful": len(successful_ops),
                    "failed": len(failed_ops),
                    "success_rate": len(successful_ops) / len(recent_ops)
                    if recent_ops
                    else 1.0,
                },
                "circuit_breakers": {
                    op_type: {
                        "state": state.value,
                        "failure_count": self._failure_counts.get(op_type, 0),
                        "last_failure": self._last_failure_times.get(op_type),
                    }
                    for op_type, state in self._circuit_states.items()
                },
                "resource_usage": {
                    "memory_usage_mb": self._total_memory_usage / 1024 / 1024,
                    "memory_limit_mb": self.limits.max_memory_usage_mb,
                    "total_cpu_time": self._total_cpu_time,
                    "total_file_operations": self._total_file_operations,
                },
                "limits": {
                    "max_concurrent_operations": self.limits.max_concurrent_operations,
                    "max_operations_per_minute": self.limits.max_operations_per_minute,
                    "max_operation_duration": self.limits.max_operation_duration,
                    "timeout_seconds": self.limits.timeout_seconds,
                },
            }

    def reset_circuit_breaker(self, operation_type: str) -> bool:
        """
        Manually reset a circuit breaker.

        Args:
            operation_type: Type of operation

        Returns:
            True if circuit breaker was reset
        """

        with self._lock:
            if operation_type in self._circuit_states:
                self._circuit_states[operation_type] = OperationState.CLOSED
                self._failure_counts[operation_type] = 0

                self.security_logger.log_security_event(
                    event_type=SecurityEventType.CIRCUIT_BREAKER_RESET,
                    level=SecurityEventLevel.LOW,
                    message=f"Circuit breaker manually reset: {operation_type}",
                    operation=operation_type,
                )

                return True

        return False


# Global singleton instance
_bounded_operations: BoundedStatusOperations | None = None


def get_bounded_status_operations(
    limits: OperationLimits | None = None,
) -> BoundedStatusOperations:
    """Get the global bounded status operations instance."""

    global _bounded_operations
    if _bounded_operations is None:
        _bounded_operations = BoundedStatusOperations(limits)
    return _bounded_operations


async def execute_bounded_status_operation(
    operation_type: str,
    client_id: str,
    operation_func: t.Callable[..., t.Awaitable[t.Any]],
    *args: t.Any,
    **kwargs: t.Any,
) -> t.Any:
    """
    Convenience function for bounded operation execution.

    Args:
        operation_type: Type of operation
        client_id: Client identifier
        operation_func: Async function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Operation result
    """

    operations_manager = get_bounded_status_operations()
    return await operations_manager.execute_bounded_operation(
        operation_type, client_id, operation_func, *args, **kwargs
    )
