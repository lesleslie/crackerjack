import asyncio
import contextlib
import time
import typing as t
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from acb import console

# console imported from acb


@dataclass
class RateLimitConfig:
    requests_per_minute: int = 30
    requests_per_hour: int = 300

    max_concurrent_jobs: int = 5
    max_job_duration_minutes: int = 30
    max_file_size_mb: int = 100
    max_progress_files: int = 1000

    max_cache_entries: int = 10000
    max_state_history: int = 100


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 30,
        requests_per_hour: int = 300,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        self.minute_windows: dict[str, deque[float]] = defaultdict(
            lambda: deque[float](maxlen=requests_per_minute),  # type: ignore[arg-type,misc]
        )
        self.hour_windows: dict[str, deque[float]] = defaultdict(
            lambda: deque[float](maxlen=requests_per_hour),  # type: ignore[arg-type,misc]
        )

        self.global_minute_window: deque[float] = deque[float](
            maxlen=requests_per_minute * 10
        )
        self.global_hour_window: deque[float] = deque[float](
            maxlen=requests_per_hour * 10
        )

        self._lock = asyncio.Lock()

    async def is_allowed(
        self,
        client_id: str = "default",
    ) -> tuple[bool, dict[str, t.Any]]:
        async with self._lock:
            now = time.time()

            self._cleanup_windows(now)

            minute_count = len(self.minute_windows[client_id])
            hour_count = len(self.hour_windows[client_id])

            global_minute_count = len(self.global_minute_window)
            global_hour_count = len(self.global_hour_window)

            if minute_count >= self.requests_per_minute:
                return False, {
                    "reason": "minute_limit_exceeded",
                    "limit": self.requests_per_minute,
                    "window": "1 minute",
                    "retry_after": 60,
                }

            if hour_count >= self.requests_per_hour:
                return False, {
                    "reason": "hour_limit_exceeded",
                    "limit": self.requests_per_hour,
                    "window": "1 hour",
                    "retry_after": 3600,
                }

            if global_minute_count >= self.requests_per_minute * 10:
                return False, {
                    "reason": "global_minute_limit_exceeded",
                    "retry_after": 60,
                }

            if global_hour_count >= self.requests_per_hour * 10:
                return False, {
                    "reason": "global_hour_limit_exceeded",
                    "retry_after": 3600,
                }

            self.minute_windows[client_id].append(now)
            self.hour_windows[client_id].append(now)
            self.global_minute_window.append(now)
            self.global_hour_window.append(now)

            return True, {
                "allowed": True,
                "minute_requests_remaining": self.requests_per_minute
                - minute_count
                - 1,
                "hour_requests_remaining": self.requests_per_hour - hour_count - 1,
            }

    def _cleanup_windows(self, now: float) -> None:
        minute_cutoff = now - 60
        hour_cutoff = now - 3600

        self._cleanup_client_windows(minute_cutoff, hour_cutoff)
        self._cleanup_global_windows(minute_cutoff, hour_cutoff)

    def _cleanup_client_windows(self, minute_cutoff: float, hour_cutoff: float) -> None:
        for client_id in list[t.Any](self.minute_windows.keys()):
            minute_window = self.minute_windows[client_id]
            hour_window = self.hour_windows[client_id]

            self._remove_expired_entries(minute_window, minute_cutoff)
            self._remove_expired_entries(hour_window, hour_cutoff)

            if not minute_window:
                del self.minute_windows[client_id]
            if not hour_window:
                del self.hour_windows[client_id]

    def _cleanup_global_windows(self, minute_cutoff: float, hour_cutoff: float) -> None:
        self._remove_expired_entries(self.global_minute_window, minute_cutoff)
        self._remove_expired_entries(self.global_hour_window, hour_cutoff)

    def _remove_expired_entries(self, window: deque[float], cutoff: float) -> None:
        while window and window[0] < cutoff:
            window.popleft()

    def get_stats(self) -> dict[str, t.Any]:
        now = time.time()
        self._cleanup_windows(now)

        return {
            "active_clients": len(self.minute_windows),
            "global_minute_requests": len(self.global_minute_window),
            "global_hour_requests": len(self.global_hour_window),
            "limits": {
                "requests_per_minute": self.requests_per_minute,
                "requests_per_hour": self.requests_per_hour,
            },
        }


class ResourceMonitor:
    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config
        self.active_jobs: dict[str, float] = {}
        self.job_locks = asyncio.Semaphore(config.max_concurrent_jobs)
        self._lock = asyncio.Lock()

    async def acquire_job_slot(self, job_id: str) -> bool:
        try:
            if (
                self.job_locks.locked()
                and len(self.active_jobs) >= self.config.max_concurrent_jobs
            ):
                console.print(
                    f"[yellow]🚫 Job {job_id} rejected: max concurrent jobs ({self.config.max_concurrent_jobs}) reached[/ yellow]",
                )
                return False

            try:
                await asyncio.wait_for(self.job_locks.acquire(), timeout=0.1)
            except TimeoutError:
                console.print(
                    f"[yellow]🚫 Job {job_id} rejected: max concurrent jobs ({self.config.max_concurrent_jobs}) reached[/ yellow]",
                )
                return False

            async with self._lock:
                self.active_jobs[job_id] = time.time()

            console.print(
                f"[green]🎯 Job {job_id} acquired slot ({len(self.active_jobs)} / {self.config.max_concurrent_jobs})[/ green]",
            )
            return True

        except Exception as e:
            console.print(f"[red]Error acquiring job slot for {job_id}: {e}[/ red]")
            return False

    async def release_job_slot(self, job_id: str) -> None:
        async with self._lock:
            if job_id in self.active_jobs:
                start_time = self.active_jobs.pop(job_id)
                duration = time.time() - start_time
                console.print(
                    f"[blue]🏁 Job {job_id} completed in {duration: .1f}s ({len(self.active_jobs)} / {self.config.max_concurrent_jobs} active)[/ blue]",
                )

        self.job_locks.release()

    async def cleanup_stale_jobs(self) -> int:
        now = time.time()
        max_duration = self.config.max_job_duration_minutes * 60
        stale_jobs = []

        async with self._lock:
            for job_id, start_time in list[t.Any](self.active_jobs.items()):
                if now - start_time > max_duration:
                    stale_jobs.append(job_id)
                    del self.active_jobs[job_id]
                    self.job_locks.release()

        if stale_jobs:
            console.print(
                f"[yellow]🧹 Cleaned up {len(stale_jobs)} stale jobs (exceeded {self.config.max_job_duration_minutes}m)[/ yellow]",
            )

        return len(stale_jobs)

    def check_file_size(self, file_path: Path) -> bool:
        try:
            if not file_path.exists():
                return True

            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                console.print(
                    f"[red]🚫 File {file_path} ({size_mb: .1f}MB) exceeds limit ({self.config.max_file_size_mb}MB)[/ red]",
                )
                return False

            return True
        except OSError:
            return False

    def check_progress_files_limit(self, progress_dir: Path) -> bool:
        try:
            if not progress_dir.exists():
                return True

            file_count = len(list[t.Any](progress_dir.glob("job-* .json")))
            if file_count > self.config.max_progress_files:
                console.print(
                    f"[red]🚫 Progress files ({file_count}) exceed limit ({self.config.max_progress_files})[/ red]",
                )
                return False

            return True
        except OSError:
            return False

    def get_stats(self) -> dict[str, t.Any]:
        return {
            "active_jobs": len(self.active_jobs),
            "max_concurrent_jobs": self.config.max_concurrent_jobs,
            "available_slots": self.job_locks._value,
            "job_details": {
                job_id: {"duration": time.time() - start_time, "start_time": start_time}
                for job_id, start_time in self.active_jobs.items()
            },
            "limits": {
                "max_concurrent_jobs": self.config.max_concurrent_jobs,
                "max_job_duration_minutes": self.config.max_job_duration_minutes,
                "max_file_size_mb": self.config.max_file_size_mb,
                "max_progress_files": self.config.max_progress_files,
            },
        }


class RateLimitMiddleware:
    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self.config = config or RateLimitConfig()
        self.rate_limiter = RateLimiter(
            self.config.requests_per_minute,
            self.config.requests_per_hour,
        )
        self.resource_monitor = ResourceMonitor(self.config)

        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        console.print("[green]🛡️ Rate limiting middleware started[/ green]")

    async def stop(self) -> None:
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
        console.print("[yellow]🛡️ Rate limiting middleware stopped[/ yellow]")

    async def check_request_allowed(
        self,
        client_id: str = "default",
    ) -> tuple[bool, dict[str, t.Any]]:
        return await self.rate_limiter.is_allowed(client_id)

    async def acquire_job_resources(self, job_id: str) -> bool:
        return await self.resource_monitor.acquire_job_slot(job_id)

    async def release_job_resources(self, job_id: str) -> None:
        await self.resource_monitor.release_job_slot(job_id)

    def validate_file_size(self, file_path: Path) -> bool:
        return self.resource_monitor.check_file_size(file_path)

    def validate_progress_files(self, progress_dir: Path) -> bool:
        return self.resource_monitor.check_progress_files_limit(progress_dir)

    async def _cleanup_loop(self) -> None:
        while self._running:
            try:
                await self.resource_monitor.cleanup_stale_jobs()
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception as e:
                console.print(f"[red]Error in cleanup loop: {e}[/ red]")
                await asyncio.sleep(60)

    def get_comprehensive_stats(self) -> dict[str, t.Any]:
        return {
            "rate_limiting": self.rate_limiter.get_stats(),
            "resource_usage": self.resource_monitor.get_stats(),
            "config": {
                "requests_per_minute": self.config.requests_per_minute,
                "requests_per_hour": self.config.requests_per_hour,
                "max_concurrent_jobs": self.config.max_concurrent_jobs,
                "max_job_duration_minutes": self.config.max_job_duration_minutes,
                "max_file_size_mb": self.config.max_file_size_mb,
                "max_progress_files": self.config.max_progress_files,
            },
        }
