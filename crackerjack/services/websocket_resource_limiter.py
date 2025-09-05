"""
WebSocket Resource Limiter to prevent resource exhaustion attacks.

Provides comprehensive resource monitoring and limiting for WebSocket
connections, including connection limits, message limits, memory usage
tracking, and DoS prevention.
"""

import asyncio
import time
import typing as t
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import RLock

from .security_logger import SecurityEventLevel, SecurityEventType, get_security_logger


@dataclass
class ConnectionMetrics:
    """Metrics for individual WebSocket connections."""

    client_id: str
    connect_time: float = field(default_factory=time.time)
    message_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_activity: float = field(default_factory=time.time)

    @property
    def connection_duration(self) -> float:
        """Get connection duration in seconds."""
        return time.time() - self.connect_time

    @property
    def idle_time(self) -> float:
        """Get idle time since last activity."""
        return time.time() - self.last_activity


@dataclass
class ResourceLimits:
    """Resource limits configuration."""

    max_connections: int = 50
    max_connections_per_ip: int = 10
    max_message_size: int = 64 * 1024  # 64KB
    max_messages_per_minute: int = 100
    max_messages_per_connection: int = 10000
    max_connection_duration: float = 3600.0  # 1 hour
    max_idle_time: float = 300.0  # 5 minutes
    max_memory_usage_mb: int = 100
    connection_timeout: float = 30.0
    message_timeout: float = 10.0


class ResourceExhaustedError(Exception):
    """Raised when resource limits are exceeded."""

    pass


class WebSocketResourceLimiter:
    """
    Resource limiter for WebSocket connections.

    Features:
    - Connection count and per-IP limits
    - Message size and rate limiting
    - Memory usage monitoring
    - Connection duration limits
    - Idle connection cleanup
    - DoS attack prevention
    """

    def __init__(self, limits: ResourceLimits | None = None):
        """
        Initialize WebSocket resource limiter.

        Args:
            limits: Resource limits configuration
        """
        self.limits = limits or ResourceLimits()
        self.security_logger = get_security_logger()

        self._setup_limiter_components()

    def _setup_limiter_components(self) -> None:
        """Set up all limiter components in initialization."""
        self._initialize_connection_tracking()
        self._initialize_metrics_tracking()
        self._initialize_cleanup_system()

    def _initialize_connection_tracking(self) -> None:
        """Initialize thread-safe connection tracking structures."""
        self._lock = RLock()
        self._connections: dict[str, ConnectionMetrics] = {}
        self._ip_connections: dict[str, set[str]] = defaultdict(set)
        self._message_history: dict[str, deque[t.Any]] = defaultdict(
            lambda: deque(maxlen=100)
        )
        self._blocked_ips: dict[str, float] = {}

    def _initialize_metrics_tracking(self) -> None:
        """Initialize metrics tracking with proper typing."""
        self._connection_metrics: dict[str, ConnectionMetrics] = {}
        self._message_queues: dict[str, deque[bytes]] = defaultdict(deque)
        self._resource_usage: dict[str, dict[str, t.Any]] = {}
        self._memory_usage: int = 0

    def _initialize_cleanup_system(self) -> None:
        """Initialize the background cleanup system."""
        self._cleanup_task: asyncio.Task[t.Any] | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the resource limiter with background cleanup."""

        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            self.security_logger.log_security_event(
                event_type=SecurityEventType.SERVICE_START,
                level=SecurityEventLevel.INFO,
                message="WebSocket resource limiter started",
                operation="limiter_start",
            )

    async def stop(self) -> None:
        """Stop the resource limiter and cleanup resources."""

        self._shutdown_event.set()

        if self._cleanup_task:
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=5.0)
            except TimeoutError:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass

            self._cleanup_task = None

        # Force cleanup all connections
        with self._lock:
            self._connections.clear()
            self._ip_connections.clear()
            self._message_history.clear()

        self.security_logger.log_security_event(
            event_type=SecurityEventType.SERVICE_STOP,
            level=SecurityEventLevel.INFO,
            message="WebSocket resource limiter stopped",
            operation="limiter_stop",
        )

    def validate_new_connection(self, client_id: str, client_ip: str) -> None:
        """
        Validate if a new connection can be accepted.

        Args:
            client_id: Unique client identifier
            client_ip: Client IP address

        Raises:
            ResourceExhaustedError: If connection limits exceeded
        """

        with self._lock:
            current_time = time.time()

            self._check_ip_blocking_status(client_ip, current_time)
            self._check_total_connection_limit(client_id, client_ip)
            self._check_per_ip_connection_limit(client_id, client_ip, current_time)

    def _check_ip_blocking_status(self, client_ip: str, current_time: float) -> None:
        """Check if IP is currently blocked."""
        if client_ip in self._blocked_ips:
            if current_time < self._blocked_ips[client_ip]:
                raise ResourceExhaustedError(f"IP {client_ip} is temporarily blocked")
            else:
                del self._blocked_ips[client_ip]

    def _check_total_connection_limit(self, client_id: str, client_ip: str) -> None:
        """Check if total connection limit is exceeded."""
        if len(self._connections) >= self.limits.max_connections:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                level=SecurityEventLevel.WARNING,
                message=f"Max connections exceeded: {len(self._connections)}",
                client_id=client_id,
                operation="connection_validation",
                additional_data={"client_ip": client_ip},
            )
            raise ResourceExhaustedError(
                f"Maximum connections exceeded: {len(self._connections)}"
            )

    def _check_per_ip_connection_limit(
        self, client_id: str, client_ip: str, current_time: float
    ) -> None:
        """Check if per-IP connection limit is exceeded."""
        ip_connection_count = len(self._ip_connections[client_ip])
        if ip_connection_count >= self.limits.max_connections_per_ip:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                level=SecurityEventLevel.HIGH,
                message=f"Max connections per IP exceeded: {ip_connection_count}",
                client_id=client_id,
                operation="connection_validation",
                additional_data={"client_ip": client_ip},
            )

            # Block IP temporarily for repeated violations
            self._blocked_ips[client_ip] = current_time + 300.0  # 5 minute block

            raise ResourceExhaustedError(
                f"Maximum connections per IP exceeded: {ip_connection_count}"
            )

    def register_connection(self, client_id: str, client_ip: str) -> None:
        """
        Register a new WebSocket connection.

        Args:
            client_id: Unique client identifier
            client_ip: Client IP address
        """

        with self._lock:
            metrics = ConnectionMetrics(client_id=client_id)
            self._connections[client_id] = metrics
            self._ip_connections[client_ip].add(client_id)

        self.security_logger.log_security_event(
            event_type=SecurityEventType.CONNECTION_ESTABLISHED,
            level=SecurityEventLevel.INFO,
            message=f"WebSocket connection registered: {client_id}",
            client_id=client_id,
            operation="connection_registration",
            additional_data={"client_ip": client_ip},
        )

    def unregister_connection(self, client_id: str, client_ip: str) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            client_id: Unique client identifier
            client_ip: Client IP address
        """

        with self._lock:
            if client_id in self._connections:
                metrics = self._connections[client_id]
                del self._connections[client_id]

                self.security_logger.log_security_event(
                    event_type=SecurityEventType.CONNECTION_CLOSED,
                    level=SecurityEventLevel.INFO,
                    message=f"WebSocket connection unregistered: {client_id}",
                    client_id=client_id,
                    operation="connection_unregistration",
                    additional_data={
                        "client_ip": client_ip,
                        "connection_duration": metrics.connection_duration,
                        "message_count": metrics.message_count,
                        "bytes_transferred": metrics.bytes_sent
                        + metrics.bytes_received,
                    },
                )

            # Remove from IP tracking
            if client_ip in self._ip_connections:
                self._ip_connections[client_ip].discard(client_id)
                if not self._ip_connections[client_ip]:
                    del self._ip_connections[client_ip]

            # Clear message history
            if client_id in self._message_history:
                del self._message_history[client_id]

    def validate_message(self, client_id: str, message_size: int) -> None:
        """
        Validate if a message can be processed.

        Args:
            client_id: Client identifier
            message_size: Size of the message in bytes

        Raises:
            ResourceExhaustedError: If message limits exceeded
        """

        with self._lock:
            self._check_message_size(client_id, message_size)
            metrics = self._get_connection_metrics(client_id)
            self._check_message_count(client_id, metrics)
            self._check_message_rate(client_id)

    def _check_message_size(self, client_id: str, message_size: int) -> None:
        """Check if message size exceeds limits."""
        if message_size > self.limits.max_message_size:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                level=SecurityEventLevel.HIGH,
                message=f"Message size limit exceeded: {message_size} bytes",
                client_id=client_id,
                operation="message_validation",
            )
            raise ResourceExhaustedError(f"Message too large: {message_size} bytes")

    def _get_connection_metrics(self, client_id: str) -> ConnectionMetrics:
        """Get connection metrics, raising error if connection doesn't exist."""
        if client_id not in self._connections:
            raise ResourceExhaustedError(f"Connection not registered: {client_id}")
        return self._connections[client_id]

    def _check_message_count(self, client_id: str, metrics: ConnectionMetrics) -> None:
        """Check if total message count per connection exceeds limits."""
        if metrics.message_count >= self.limits.max_messages_per_connection:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                level=SecurityEventLevel.WARNING,
                message=f"Message count limit exceeded: {metrics.message_count}",
                client_id=client_id,
                operation="message_validation",
            )
            raise ResourceExhaustedError(
                f"Message count limit exceeded: {metrics.message_count}"
            )

    def _check_message_rate(self, client_id: str) -> None:
        """Check if message rate exceeds per-minute limits."""
        current_time = time.time()
        message_times = self._message_history[client_id]

        # Remove old messages (older than 1 minute)
        while message_times and current_time - message_times[0] > 60.0:
            message_times.popleft()

        if len(message_times) >= self.limits.max_messages_per_minute:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                level=SecurityEventLevel.WARNING,
                message=f"Message rate limit exceeded: {len(message_times)} messages/min",
                client_id=client_id,
                operation="message_validation",
            )
            raise ResourceExhaustedError(
                f"Message rate limit exceeded: {len(message_times)} messages/min"
            )

    def track_message(
        self, client_id: str, message_size: int, is_sent: bool = True
    ) -> None:
        """
        Track a processed message.

        Args:
            client_id: Client identifier
            message_size: Size of the message in bytes
            is_sent: True if message was sent, False if received
        """

        with self._lock:
            current_time = time.time()

            if client_id in self._connections:
                metrics = self._connections[client_id]
                metrics.message_count += 1
                metrics.last_activity = current_time

                if is_sent:
                    metrics.bytes_sent += message_size
                else:
                    metrics.bytes_received += message_size

            # Track message timing for rate limiting
            self._message_history[client_id].append(current_time)

    async def check_connection_limits(self, client_id: str) -> None:
        """
        Check if connection has exceeded limits.

        Args:
            client_id: Client identifier

        Raises:
            ResourceExhaustedError: If connection limits exceeded
        """

        with self._lock:
            if client_id not in self._connections:
                return

            metrics = self._connections[client_id]
            time.time()

            # Check connection duration
            if metrics.connection_duration > self.limits.max_connection_duration:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.CONNECTION_TIMEOUT,
                    level=SecurityEventLevel.WARNING,
                    message=f"Connection duration exceeded: {metrics.connection_duration:.1f}s",
                    client_id=client_id,
                    operation="connection_limit_check",
                )
                raise ResourceExhaustedError(
                    f"Connection duration exceeded: {metrics.connection_duration:.1f}s"
                )

            # Check idle time
            if metrics.idle_time > self.limits.max_idle_time:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.CONNECTION_IDLE,
                    level=SecurityEventLevel.INFO,
                    message=f"Connection idle timeout: {metrics.idle_time:.1f}s",
                    client_id=client_id,
                    operation="connection_limit_check",
                )
                raise ResourceExhaustedError(
                    f"Connection idle timeout: {metrics.idle_time:.1f}s"
                )

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for expired connections and resources."""

        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=30.0,  # Cleanup every 30 seconds
                )
                break  # Shutdown requested

            except TimeoutError:
                # Perform cleanup
                await self._perform_cleanup()

        self.security_logger.log_security_event(
            event_type=SecurityEventType.SERVICE_CLEANUP,
            level=SecurityEventLevel.INFO,
            message="WebSocket resource limiter cleanup loop ended",
            operation="cleanup_loop",
        )

    async def _perform_cleanup(self) -> None:
        """Perform resource cleanup."""
        current_time = time.time()

        with self._lock:
            cleanup_count = self._cleanup_expired_connections(current_time)
            self._cleanup_empty_ip_entries()
            self._cleanup_expired_ip_blocks(current_time)

        self._log_cleanup_results(cleanup_count)

    def _cleanup_expired_connections(self, current_time: float) -> int:
        """Clean up expired connections and return count of cleaned connections."""
        expired_connections = self._find_expired_connections()
        cleanup_count = 0

        for client_id in expired_connections:
            if self._remove_expired_connection(client_id):
                cleanup_count += 1

        return cleanup_count

    def _find_expired_connections(self) -> list[str]:
        """Find connections that have exceeded duration or idle time limits."""
        return [
            client_id
            for client_id, metrics in self._connections.items()
            if (
                metrics.connection_duration > self.limits.max_connection_duration
                or metrics.idle_time > self.limits.max_idle_time
            )
        ]

    def _remove_expired_connection(self, client_id: str) -> bool:
        """Remove a specific expired connection and its associated data."""
        if client_id not in self._connections:
            return False

        # Remove connection metrics
        del self._connections[client_id]

        # Clean up IP tracking
        for client_set in self._ip_connections.values():
            client_set.discard(client_id)

        # Clean up message history
        if client_id in self._message_history:
            del self._message_history[client_id]

        return True

    def _cleanup_empty_ip_entries(self) -> None:
        """Remove IP entries that no longer have any connections."""
        empty_ips = [ip for ip, clients in self._ip_connections.items() if not clients]
        for ip in empty_ips:
            del self._ip_connections[ip]

    def _cleanup_expired_ip_blocks(self, current_time: float) -> None:
        """Remove IP blocks that have expired."""
        expired_blocks = [
            ip
            for ip, block_until in self._blocked_ips.items()
            if current_time >= block_until
        ]
        for ip in expired_blocks:
            del self._blocked_ips[ip]

    def _log_cleanup_results(self, cleanup_count: int) -> None:
        """Log cleanup results if any connections were cleaned up."""
        if cleanup_count > 0:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.RESOURCE_CLEANUP,
                level=SecurityEventLevel.INFO,
                message=f"Cleaned up {cleanup_count} expired connections",
                operation="resource_cleanup",
            )

    def get_resource_status(self) -> dict[str, t.Any]:
        """Get current resource usage status."""

        with self._lock:
            return {
                "connections": {
                    "total": len(self._connections),
                    "limit": self.limits.max_connections,
                    "utilization": len(self._connections) / self.limits.max_connections,
                },
                "ip_distribution": {
                    ip: len(clients) for ip, clients in self._ip_connections.items()
                },
                "blocked_ips": len(self._blocked_ips),
                "memory_usage_mb": self._memory_usage,
                "memory_limit_mb": self.limits.max_memory_usage_mb,
                "limits": {
                    "max_connections": self.limits.max_connections,
                    "max_connections_per_ip": self.limits.max_connections_per_ip,
                    "max_message_size": self.limits.max_message_size,
                    "max_messages_per_minute": self.limits.max_messages_per_minute,
                    "max_connection_duration": self.limits.max_connection_duration,
                    "max_idle_time": self.limits.max_idle_time,
                },
            }

    def get_connection_metrics(self, client_id: str) -> ConnectionMetrics | None:
        """Get metrics for a specific connection."""

        with self._lock:
            return self._connections.get(client_id)


# Global singleton instance
_resource_limiter: WebSocketResourceLimiter | None = None


def get_websocket_resource_limiter(
    limits: ResourceLimits | None = None,
) -> WebSocketResourceLimiter:
    """Get the global WebSocket resource limiter instance."""

    global _resource_limiter
    if _resource_limiter is None:
        _resource_limiter = WebSocketResourceLimiter(limits)
    return _resource_limiter
