import asyncio
import threading
import time
import typing as t
from collections import defaultdict
from pathlib import Path

from .security_logger import SecurityEventLevel, SecurityEventType, get_security_logger


class StatusSecurityError(Exception):
    pass


class AccessDeniedError(StatusSecurityError):
    pass


class ResourceLimitExceededError(StatusSecurityError):
    pass


class RateLimitExceededError(StatusSecurityError):
    pass


class StatusSecurityManager:
    def __init__(
        self,
        max_concurrent_requests: int = 5,
        rate_limit_per_minute: int = 60,
        max_resource_usage_mb: int = 100,
        allowed_paths: set[str] | None = None,
    ):
        self.max_concurrent_requests = max_concurrent_requests
        self.rate_limit_per_minute = rate_limit_per_minute
        self.max_resource_usage_mb = max_resource_usage_mb
        self.allowed_paths = allowed_paths or set()

        self._lock = threading.RLock()
        self._concurrent_requests = 0
        self._rate_limit_tracker: dict[str, list[float]] = defaultdict(list)
        self._resource_usage = 0.0

        self.security_logger = get_security_logger()

        self._active_requests: set[str] = set()

    def validate_request(
        self,
        client_id: str,
        operation: str,
        request_data: dict[str, t.Any] | None = None,
    ) -> None:
        with self._lock:
            if self._concurrent_requests >= self.max_concurrent_requests:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                    level=SecurityEventLevel.WARNING,
                    message=f"Concurrent request limit exceeded: {self._concurrent_requests}",
                    client_id=client_id,
                    operation=operation,
                )
                raise ResourceLimitExceededError(
                    f"Too many concurrent requests: {self._concurrent_requests}"
                )

            self._check_rate_limit(client_id, operation)

            if request_data:
                self._validate_request_data(client_id, operation, request_data)

    def _check_rate_limit(self, client_id: str, operation: str) -> None:
        current_time = time.time()
        client_requests = self._rate_limit_tracker[client_id]

        client_requests[:] = [
            req_time for req_time in client_requests if current_time - req_time < 60
        ]

        if len(client_requests) >= self.rate_limit_per_minute:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                level=SecurityEventLevel.WARNING,
                message=f"Rate limit exceeded for client {client_id}",
                client_id=client_id,
                operation=operation,
            )
            raise RateLimitExceededError(
                f"Rate limit exceeded: {len(client_requests)} requests in last minute"
            )

        client_requests.append(current_time)

    def _validate_request_data(
        self,
        client_id: str,
        operation: str,
        request_data: dict[str, t.Any],
    ) -> None:
        for key, value in request_data.items():
            if isinstance(value, str):
                if self._contains_path_traversal(value):
                    self.security_logger.log_security_event(
                        event_type=SecurityEventType.PATH_TRAVERSAL_ATTEMPT,
                        level=SecurityEventLevel.CRITICAL,
                        message=f"Path traversal attempt detected in {key}: {value}",
                        client_id=client_id,
                        operation=operation,
                        additional_data={"suspicious_value": value},
                    )
                    raise AccessDeniedError(f"Invalid path in parameter: {key}")

        if "path" in request_data or "file_path" in request_data:
            path_value = request_data.get("path") or request_data.get("file_path")
            if path_value:
                self._validate_file_path(client_id, operation, str(path_value))

    def _contains_path_traversal(self, value: str) -> bool:
        traversal_patterns = [
            "../",
            "..\\",
            "..%2f",
            "..%5c",
            "%2e%2e%2f",
            "%2e%2e%5c",
            "....//",
            "....\\\\",
            "..\\/",
            "../\\",
            "%252e%252e%252f",
        ]

        value_lower = value.lower()
        return any(pattern in value_lower for pattern in traversal_patterns)

    def _validate_file_path(
        self, client_id: str, operation: str, file_path: str
    ) -> None:
        try:
            path = Path(file_path).resolve()

            if self.allowed_paths:
                path_allowed = any(
                    path.is_relative_to(Path(allowed_path).resolve())
                    for allowed_path in self.allowed_paths
                )

                if not path_allowed:
                    self.security_logger.log_security_event(
                        event_type=SecurityEventType.UNAUTHORIZED_ACCESS_ATTEMPT,
                        level=SecurityEventLevel.HIGH,
                        message=f"Access to unauthorized path: {path}",
                        client_id=client_id,
                        operation=operation,
                        additional_data={"requested_path": str(path)},
                    )
                    raise AccessDeniedError(f"Access denied to path: {file_path}")

        except (OSError, ValueError) as e:
            self.security_logger.log_security_event(
                event_type=SecurityEventType.INVALID_INPUT,
                level=SecurityEventLevel.WARNING,
                message=f"Invalid file path: {file_path} - {e}",
                client_id=client_id,
                operation=operation,
            )
            raise AccessDeniedError(f"Invalid file path: {file_path}")

    async def acquire_request_lock(
        self,
        client_id: str,
        operation: str,
        timeout: float = 30.0,
    ) -> "RequestLock":
        request_id = f"{client_id}: {operation}: {int(time.time())}"

        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if self._concurrent_requests < self.max_concurrent_requests:
                    self._concurrent_requests += 1
                    self._active_requests.add(request_id)

                    self.security_logger.log_security_event(
                        event_type=SecurityEventType.REQUEST_START,
                        level=SecurityEventLevel.INFO,
                        message=f"Request lock acquired: {request_id}",
                        client_id=client_id,
                        operation=operation,
                    )

                    return RequestLock(self, request_id, client_id, operation)

            await asyncio.sleep(0.1)

        self.security_logger.log_security_event(
            event_type=SecurityEventType.REQUEST_TIMEOUT,
            level=SecurityEventLevel.ERROR,
            message=f"Request lock timeout: {request_id}",
            client_id=client_id,
            operation=operation,
        )

        raise ResourceLimitExceededError(
            f"Unable to acquire request lock within {timeout}s"
        )

    def _release_request_lock(
        self, request_id: str, client_id: str, operation: str
    ) -> None:
        with self._lock:
            if request_id in self._active_requests:
                self._active_requests.remove(request_id)
                self._concurrent_requests = max(0, self._concurrent_requests - 1)

                self.security_logger.log_security_event(
                    event_type=SecurityEventType.REQUEST_END,
                    level=SecurityEventLevel.INFO,
                    message=f"Request lock released: {request_id}",
                    client_id=client_id,
                    operation=operation,
                )

    def get_security_status(self) -> dict[str, t.Any]:
        with self._lock:
            current_time = time.time()

            recent_requests = 0
            for client_requests in self._rate_limit_tracker.values():
                recent_requests += len(
                    [
                        req_time
                        for req_time in client_requests
                        if current_time - req_time < 60
                    ]
                )

            return {
                "concurrent_requests": self._concurrent_requests,
                "active_request_ids": list[t.Any](self._active_requests),
                "recent_requests_per_minute": recent_requests,
                "rate_limit_clients": len(self._rate_limit_tracker),
                "max_concurrent_limit": self.max_concurrent_requests,
                "rate_limit_per_minute": self.rate_limit_per_minute,
                "resource_usage_mb": self._resource_usage,
                "max_resource_limit_mb": self.max_resource_usage_mb,
                "allowed_paths_count": len(self.allowed_paths),
            }


class RequestLock:
    def __init__(
        self,
        security_manager: StatusSecurityManager,
        request_id: str,
        client_id: str,
        operation: str,
    ):
        self.security_manager = security_manager
        self.request_id = request_id
        self.client_id = client_id
        self.operation = operation

    async def __aenter__(self) -> "RequestLock":
        return self

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        self.security_manager._release_request_lock(
            self.request_id,
            self.client_id,
            self.operation,
        )


_security_manager: StatusSecurityManager | None = None


def get_status_security_manager() -> StatusSecurityManager:
    global _security_manager
    if _security_manager is None:
        import tempfile
        from pathlib import Path

        project_root = Path.cwd()
        temp_dir = Path(tempfile.gettempdir())
        allowed_paths = {
            str(project_root),
            str(project_root / "temp"),
            str(temp_dir / "crackerjack-mcp-progress"),
        }

        _security_manager = StatusSecurityManager(
            allowed_paths=allowed_paths,
        )

    return _security_manager


async def validate_status_request(
    client_id: str,
    operation: str,
    request_data: dict[str, t.Any] | None = None,
) -> None:
    security_manager = get_status_security_manager()
    security_manager.validate_request(client_id, operation, request_data)


async def secure_status_operation(
    client_id: str,
    operation: str,
    timeout: float = 30.0,
) -> RequestLock:
    security_manager = get_status_security_manager()
    return await security_manager.acquire_request_lock(client_id, operation, timeout)
