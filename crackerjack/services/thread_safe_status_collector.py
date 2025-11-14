import asyncio
import json
import threading
import time
import typing as t
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from ..mcp.context import MCPServerContext
from .security_logger import SecurityEventLevel, SecurityEventType, get_security_logger


@dataclass
class StatusSnapshot:
    services: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    jobs: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    server_stats: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    agent_suggestions: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    timestamp: float = field(default_factory=time.time)
    collection_duration: float = 0.0
    is_complete: bool = False
    errors: list[str] = field(default_factory=list)


class ThreadSafeStatusCollector:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.security_logger = get_security_logger()

        self._collection_lock = threading.RLock()
        self._data_lock = threading.RLock()
        self._file_lock = threading.RLock()

        self._current_snapshot: StatusSnapshot | None = None
        self._collection_in_progress = False
        self._collection_start_time = 0.0

        self._cache: dict[str, t.Any] = {}
        self._cache_timestamps: dict[str, float] = {}
        self._cache_ttl = 5.0

        self._local = threading.local()

    async def collect_comprehensive_status(
        self,
        client_id: str = "unknown",
        include_jobs: bool = True,
        include_services: bool = True,
        include_stats: bool = True,
    ) -> StatusSnapshot:
        async with self._collection_context(client_id):
            start_time = time.time()

            try:
                snapshot = StatusSnapshot(timestamp=start_time)

                collection_tasks = []

                if include_services:
                    collection_tasks.append(
                        self._collect_services_data(client_id, snapshot)
                    )

                if include_jobs:
                    collection_tasks.append(
                        self._collect_jobs_data(client_id, snapshot)
                    )

                if include_stats:
                    collection_tasks.append(
                        self._collect_server_stats(client_id, snapshot)
                    )

                await asyncio.wait_for(
                    asyncio.gather(*collection_tasks, return_exceptions=True),
                    timeout=self.timeout,
                )

                snapshot.collection_duration = time.time() - start_time
                snapshot.is_complete = True

                self.security_logger.log_security_event(
                    event_type=SecurityEventType.STATUS_COLLECTED,
                    level=SecurityEventLevel.INFO,
                    message=f"Status collection completed in {snapshot.collection_duration: .2f}s",
                    client_id=client_id,
                    operation="collect_status",
                    additional_data={
                        "components": {
                            "services": include_services,
                            "jobs": include_jobs,
                            "stats": include_stats,
                        },
                        "duration": snapshot.collection_duration,
                    },
                )

                return snapshot

            except TimeoutError:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.REQUEST_TIMEOUT,
                    level=SecurityEventLevel.ERROR,
                    message=f"Status collection timeout after {self.timeout}s",
                    client_id=client_id,
                    operation="collect_status",
                )
                raise TimeoutError(f"Status collection timed out after {self.timeout}s")

            except Exception as e:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.COLLECTION_ERROR,
                    level=SecurityEventLevel.ERROR,
                    message=f"Status collection failed: {e}",
                    client_id=client_id,
                    operation="collect_status",
                    additional_data={"error": str(e)},
                )

                snapshot = StatusSnapshot(
                    timestamp=start_time,
                    collection_duration=time.time() - start_time,
                    errors=[str(e)],
                    is_complete=False,
                )

                return snapshot

    @asynccontextmanager
    async def _collection_context(self, client_id: str) -> t.AsyncGenerator[None]:
        collection_acquired = False
        start_wait = time.time()

        try:
            while time.time() - start_wait < 5.0:
                with self._collection_lock:
                    if not self._collection_in_progress:
                        self._collection_in_progress = True
                        self._collection_start_time = time.time()
                        collection_acquired = True
                        break

                await asyncio.sleep(0.1)

            if not collection_acquired:
                raise RuntimeError("Unable to acquire collection lock - system busy")

            self.security_logger.log_security_event(
                event_type=SecurityEventType.COLLECTION_START,
                level=SecurityEventLevel.INFO,
                message="Status collection started",
                client_id=client_id,
                operation="collect_status",
            )

            yield

        finally:
            if collection_acquired:
                with self._collection_lock:
                    self._collection_in_progress = False
                    self._collection_start_time = 0.0

                self.security_logger.log_security_event(
                    event_type=SecurityEventType.COLLECTION_END,
                    level=SecurityEventLevel.INFO,
                    message="Status collection ended",
                    client_id=client_id,
                    operation="collect_status",
                )

    async def _collect_services_data(
        self,
        client_id: str,
        snapshot: StatusSnapshot,
    ) -> None:
        try:
            cached_data = self._get_cached_data("services")
            if cached_data is not None:
                with self._data_lock:
                    snapshot.services = cached_data
                return

            from crackerjack.services.server_manager import (
                find_mcp_server_processes,
                find_websocket_server_processes,
            )

            mcp_task = asyncio.create_task(asyncio.to_thread(find_mcp_server_processes))
            websocket_task = asyncio.create_task(
                asyncio.to_thread(find_websocket_server_processes)
            )

            mcp_processes, websocket_processes = await asyncio.wait_for(
                asyncio.gather(mcp_task, websocket_task),
                timeout=10.0,
            )

            services_data = {
                "mcp_server": {
                    "running": len(mcp_processes) > 0,
                    "processes": mcp_processes,
                },
                "websocket_server": {
                    "running": len(websocket_processes) > 0,
                    "processes": websocket_processes,
                },
            }

            with self._data_lock:
                snapshot.services = services_data
                self._set_cached_data("services", services_data)

        except Exception as e:
            error_msg = f"Failed to collect services data: {e}"
            with self._data_lock:
                snapshot.errors.append(error_msg)
                snapshot.services = {"error": error_msg}

    async def _collect_jobs_data(
        self,
        client_id: str,
        snapshot: StatusSnapshot,
    ) -> None:
        try:
            cached_data = self._get_cached_data("jobs")
            if cached_data is not None:
                with self._data_lock:
                    snapshot.jobs = cached_data
                return

            active_jobs = await self._get_active_jobs_safe()

            jobs_data = {
                "active_count": len(
                    [j for j in active_jobs if j["status"] == "running"]
                ),
                "completed_count": len(
                    [j for j in active_jobs if j["status"] == "completed"]
                ),
                "failed_count": len(
                    [j for j in active_jobs if j["status"] == "failed"]
                ),
                "details": active_jobs,
            }

            with self._data_lock:
                snapshot.jobs = jobs_data
                self._set_cached_data("jobs", jobs_data)

        except Exception as e:
            error_msg = f"Failed to collect jobs data: {e}"
            with self._data_lock:
                snapshot.errors.append(error_msg)
                snapshot.jobs = {"error": error_msg}

    async def _collect_server_stats(
        self,
        client_id: str,
        snapshot: StatusSnapshot,
    ) -> None:
        try:
            from crackerjack.mcp.context import get_context

            try:
                context: MCPServerContext | None = get_context()
            except RuntimeError:
                context = None

            if not context:
                with self._data_lock:
                    snapshot.server_stats = {"error": "Server context not available"}
                return

            stats_task = asyncio.create_task(
                asyncio.to_thread(self._build_server_stats_safe, context)
            )

            server_stats = await asyncio.wait_for(stats_task, timeout=5.0)

            with self._data_lock:
                snapshot.server_stats = server_stats

        except Exception as e:
            error_msg = f"Failed to collect server stats: {e}"
            with self._data_lock:
                snapshot.errors.append(error_msg)
                snapshot.server_stats = {"error": error_msg}

    async def _get_active_jobs_safe(self) -> list[dict[str, t.Any]]:
        jobs: list[dict[str, t.Any]] = []

        with self._file_lock:
            try:
                from crackerjack.mcp.context import get_context

                context = get_context()
                if not context or not context.progress_dir.exists():
                    return jobs

                for progress_file in context.progress_dir.glob("job-*.json"):
                    try:
                        content = progress_file.read_text(encoding="utf-8")
                        progress_data = json.loads(content)

                        job_data = {
                            "job_id": progress_data.get("job_id", "unknown"),
                            "status": progress_data.get("status", "unknown"),
                            "iteration": progress_data.get("iteration", 0),
                            "max_iterations": progress_data.get("max_iterations", 10),
                            "current_stage": progress_data.get(
                                "current_stage", "unknown"
                            ),
                            "overall_progress": progress_data.get(
                                "overall_progress", 0
                            ),
                            "stage_progress": progress_data.get("stage_progress", 0),
                            "message": progress_data.get("message", ""),
                            "timestamp": progress_data.get("timestamp", ""),
                            "error_counts": progress_data.get("error_counts", {}),
                        }

                        jobs.append(job_data)

                    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
                        self.security_logger.log_security_event(
                            event_type=SecurityEventType.FILE_READ_ERROR,
                            level=SecurityEventLevel.WARNING,
                            message=f"Failed to read job file {progress_file}: {e}",
                            operation="get_active_jobs",
                        )
                        continue

            except Exception as e:
                self.security_logger.log_security_event(
                    event_type=SecurityEventType.COLLECTION_ERROR,
                    level=SecurityEventLevel.ERROR,
                    message=f"Failed to get active jobs: {e}",
                    operation="get_active_jobs",
                )

        return jobs

    def _build_server_stats_safe(self, context: t.Any) -> dict[str, t.Any]:
        try:
            stats = {
                "server_info": {
                    "project_path": str(context.config.project_path),
                    "websocket_port": getattr(context, "websocket_server_port", None),
                    "websocket_active": getattr(
                        context, "websocket_server_process", None
                    )
                    is not None,
                },
                "rate_limiting": {
                    "enabled": context.rate_limiter is not None,
                    "config": context.rate_limiter.config.__dict__
                    if context.rate_limiter
                    else None,
                },
                "resource_usage": {
                    "temp_files_count": len(
                        list[t.Any](context.progress_dir.glob("*.json"))
                    )
                    if context.progress_dir.exists()
                    else 0,
                    "progress_dir": str(context.progress_dir),
                },
                "timestamp": time.time(),
            }

            state_manager = getattr(context, "state_manager", None)
            if state_manager:
                stats["state_manager"] = {
                    "iteration_count": getattr(state_manager, "iteration_count", 0),
                    "session_active": getattr(state_manager, "session_active", False),
                    "issues_count": len(getattr(state_manager, "issues", [])),
                }

            return stats

        except Exception as e:
            return {"error": f"Failed to build server stats: {e}"}

    def _get_cached_data(self, key: str) -> dict[str, t.Any] | None:
        current_time = time.time()

        with self._data_lock:
            if key in self._cache and key in self._cache_timestamps:
                cache_age = current_time - self._cache_timestamps[key]
                if cache_age < self._cache_ttl:
                    cached_result: dict[str, t.Any] = self._cache[key]
                    return cached_result

        return None

    def _set_cached_data(self, key: str, data: dict[str, t.Any]) -> None:
        with self._data_lock:
            self._cache[key] = data.copy() if hasattr(data, "copy") else data
            self._cache_timestamps[key] = time.time()

    def clear_cache(self) -> None:
        with self._data_lock:
            self._cache.clear()
            self._cache_timestamps.clear()

    def get_collection_status(self) -> dict[str, t.Any]:
        with self._collection_lock:
            return {
                "collection_in_progress": self._collection_in_progress,
                "collection_duration": time.time() - self._collection_start_time
                if self._collection_in_progress
                else 0.0,
                "cache_entries": len(self._cache),
                "timeout": self.timeout,
            }


_status_collector: ThreadSafeStatusCollector | None = None


def get_thread_safe_status_collector() -> ThreadSafeStatusCollector:
    global _status_collector
    if _status_collector is None:
        _status_collector = ThreadSafeStatusCollector()
    return _status_collector


async def collect_secure_status(
    client_id: str = "unknown",
    include_jobs: bool = True,
    include_services: bool = True,
    include_stats: bool = True,
) -> StatusSnapshot:
    collector = get_thread_safe_status_collector()
    return await collector.collect_comprehensive_status(
        client_id=client_id,
        include_jobs=include_jobs,
        include_services=include_services,
        include_stats=include_stats,
    )
