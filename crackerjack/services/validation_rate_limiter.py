import time
import typing as t
from collections import defaultdict, deque
from threading import Lock

from .security_logger import SecurityEventLevel, get_security_logger


class ValidationRateLimit:
    def __init__(
        self,
        max_failures: int = 10,
        window_seconds: int = 60,
        block_duration: int = 300,
    ):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.block_duration = block_duration


class ValidationRateLimiter:
    def __init__(self) -> None:
        self._failure_windows: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = Lock()
        self._logger = get_security_logger()

        self._limits = {
            "default": ValidationRateLimit(),
            "command_injection": ValidationRateLimit(
                max_failures=3, block_duration=600
            ),
            "path_traversal": ValidationRateLimit(max_failures=3, block_duration=600),
            "sql_injection": ValidationRateLimit(max_failures=2, block_duration=900),
            "code_injection": ValidationRateLimit(max_failures=2, block_duration=900),
            "json_payload": ValidationRateLimit(max_failures=20),
            "job_id": ValidationRateLimit(max_failures=15),
            "project_name": ValidationRateLimit(max_failures=15),
        }

    def is_blocked(self, client_id: str) -> bool:
        with self._lock:
            if client_id in self._blocked_until:
                if time.time() < self._blocked_until[client_id]:
                    return True
                else:
                    del self._blocked_until[client_id]
            return False

    def record_failure(
        self,
        client_id: str,
        validation_type: str,
        severity: SecurityEventLevel = SecurityEventLevel.MEDIUM,
    ) -> bool:
        with self._lock:
            current_time = time.time()

            limit = self._limits.get(validation_type, self._limits["default"])

            if client_id not in self._failure_windows:
                self._failure_windows[client_id] = deque()

            window = self._failure_windows[client_id]
            while window and current_time - window[0] > limit.window_seconds:
                window.popleft()

            window.append(current_time)

            if len(window) >= limit.max_failures:
                self._blocked_until[client_id] = current_time + limit.block_duration

                self._logger.log_rate_limit_exceeded(
                    limit_type=validation_type,
                    current_count=len(window),
                    max_allowed=limit.max_failures,
                    client_id=client_id,
                    block_duration=limit.block_duration,
                )

                self._failure_windows[client_id].clear()

                return True

            return False

    def get_remaining_attempts(self, client_id: str, validation_type: str) -> int:
        with self._lock:
            if self.is_blocked(client_id):
                return 0

            limit = self._limits.get(validation_type, self._limits["default"])
            current_failures = len(self._failure_windows.get(client_id, []))
            return max(0, limit.max_failures - current_failures)

    def get_block_time_remaining(self, client_id: str) -> int:
        with self._lock:
            if client_id in self._blocked_until:
                remaining = max(0, int(self._blocked_until[client_id] - time.time()))
                return remaining
            return 0

    def get_client_stats(self, client_id: str) -> dict[str, t.Any]:
        with self._lock:
            current_time = time.time()

            stats = {
                "client_id": client_id,
                "is_blocked": self.is_blocked(client_id),
                "block_time_remaining": self.get_block_time_remaining(client_id),
                "recent_failures": 0,
                "total_failures": 0,
            }

            if client_id in self._failure_windows:
                window = self._failure_windows[client_id]
                stats["total_failures"] = len(window)

                recent_count = sum(
                    1 for failure_time in window if current_time - failure_time <= 300
                )
                stats["recent_failures"] = recent_count

            return stats

    def cleanup_expired_data(self) -> int:
        with self._lock:
            current_time = time.time()
            removed_count = 0

            expired_blocks = [
                client_id
                for client_id, block_until in self._blocked_until.items()
                if current_time >= block_until
            ]

            for client_id in expired_blocks:
                del self._blocked_until[client_id]
                removed_count += 1

            for client_id, window in list[t.Any](self._failure_windows.items()):
                while window and current_time - window[0] > 86400:
                    window.popleft()
                    removed_count += 1

                if not window:
                    del self._failure_windows[client_id]

            return removed_count

    def update_rate_limits(
        self,
        validation_type: str,
        max_failures: int,
        window_seconds: int,
        block_duration: int,
    ) -> None:
        with self._lock:
            self._limits[validation_type] = ValidationRateLimit(
                max_failures=max_failures,
                window_seconds=window_seconds,
                block_duration=block_duration,
            )

    def get_all_stats(self) -> dict[str, t.Any]:
        with self._lock:
            current_time = time.time()

            stats: dict[str, t.Any] = {
                "total_clients_tracked": len(self._failure_windows),
                "currently_blocked": len(self._blocked_until),
                "rate_limits": {
                    vtype: {
                        "max_failures": limit.max_failures,
                        "window_seconds": limit.window_seconds,
                        "block_duration": limit.block_duration,
                    }
                    for vtype, limit in self._limits.items()
                },
                "blocked_clients": [],
                "active_clients": [],
            }

            for client_id, block_until in self._blocked_until.items():
                remaining = max(0, int(block_until - current_time))
                stats["blocked_clients"].append(
                    {
                        "client_id": client_id,
                        "blocked_until": block_until,
                        "time_remaining": remaining,
                    }
                )

            for client_id, window in self._failure_windows.items():
                if client_id not in self._blocked_until and window:
                    recent_failures = sum(
                        1
                        for failure_time in window
                        if current_time - failure_time <= 300
                    )
                    if recent_failures > 0:
                        stats["active_clients"].append(
                            {
                                "client_id": client_id,
                                "recent_failures": recent_failures,
                                "total_failures": len(window),
                            }
                        )

            return stats


_rate_limiter: ValidationRateLimiter | None = None


def get_validation_rate_limiter() -> ValidationRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = ValidationRateLimiter()
    return _rate_limiter
