import asyncio
import json
import time
import typing as t
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid4

from acb import console
from acb.depends import depends

from crackerjack.core.timeout_manager import TimeoutStrategy, get_timeout_manager
from crackerjack.services.input_validator import get_input_validator
from crackerjack.services.secure_path_utils import SecurePathValidator

# Phase 9.3: ACB Integration - Module registration for dependency injection
# Note: Currently using file-based JSON storage for job tracking
# Future enhancement: Consider ACB SQL adapter for scalability if needed
MODULE_ID: Final[UUID] = uuid4()
MODULE_STATUS: Final[str] = "stable"

# console imported from acb


class JobManager:
    def __init__(self, progress_dir: Path) -> None:
        self.progress_dir = SecurePathValidator.validate_safe_path(progress_dir)
        self.active_connections: dict[str, set[Any]] = {}
        self.known_jobs: set[str] = set()
        self.is_running = True

        self.progress_dir.mkdir(exist_ok=True)

    def validate_job_id(self, job_id: str) -> bool:
        if not job_id:
            return False

        with suppress(ValueError):
            uuid.UUID(job_id)
            return True

        result = get_input_validator().validate_job_id(job_id)
        return result.valid

    def add_connection(self, job_id: str, websocket: Any) -> None:
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)

    def remove_connection(self, job_id: str, websocket: Any) -> None:
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast_to_job(self, job_id: str, data: dict[str, t.Any]) -> None:
        if job_id not in self.active_connections:
            return

        timeout_manager = get_timeout_manager()
        connections = self.active_connections[job_id].copy()

        send_tasks = self._create_broadcast_tasks(connections, timeout_manager, data)

        if send_tasks:
            await self._execute_broadcast_tasks(job_id, send_tasks)

    def _create_broadcast_tasks(
        self, connections: set[t.Any], timeout_manager: t.Any, data: dict[str, t.Any]
    ) -> list[tuple[t.Any, asyncio.Task[t.Any]]]:
        send_tasks = []
        for websocket in connections:
            task = asyncio.create_task(
                timeout_manager.with_timeout(
                    "websocket_broadcast",
                    websocket.send_json(data),
                    timeout=2.0,
                )
            )
            send_tasks.append((websocket, task))
        return send_tasks

    async def _execute_broadcast_tasks(
        self, job_id: str, send_tasks: list[t.Any]
    ) -> None:
        try:
            done, pending = await asyncio.wait(
                [task for _, task in send_tasks],
                timeout=5.0,
                return_when=asyncio.ALL_COMPLETED,
            )

            await self._handle_broadcast_results(job_id, send_tasks, done, pending)

        except Exception as e:
            console.print(f"[red]Broadcast error: {e}[/red]")
            await self._cleanup_failed_broadcast(job_id, send_tasks)

    async def _handle_broadcast_results(
        self,
        job_id: str,
        send_tasks: list[t.Any],
        done: set[t.Any],
        pending: set[t.Any],
    ) -> None:
        for websocket, task in send_tasks:
            if task in pending:
                task.cancel()
                self.remove_connection(job_id, websocket)
            elif task in done:
                try:
                    await task
                except Exception:
                    self.remove_connection(job_id, websocket)

        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _cleanup_failed_broadcast(
        self, job_id: str, send_tasks: list[t.Any]
    ) -> None:
        for websocket, task in send_tasks:
            if not task.done():
                task.cancel()
            self.remove_connection(job_id, websocket)

    def get_latest_job_id(self) -> str | None:
        if not self.progress_dir.exists():
            return None

        progress_files = list[t.Any](self.progress_dir.glob("job-*.json"))
        if not progress_files:
            return None

        latest_file = max(progress_files, key=lambda f: f.stat().st_mtime)
        return self.extract_job_id_from_file(latest_file)

    def extract_job_id_from_file(self, progress_file: Path) -> str | None:
        return (
            progress_file.stem[4:] if progress_file.stem.startswith("job -") else None
        )

    def get_job_progress(self, job_id: str) -> dict[str, t.Any] | None:
        if not self.validate_job_id(job_id):
            return None

        try:
            progress_file = SecurePathValidator.secure_path_join(
                self.progress_dir, f"job-{job_id}.json"
            )
            if not progress_file.exists():
                return None

            SecurePathValidator.validate_file_size(progress_file)

            return json.loads(progress_file.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            return None

    async def _process_progress_file(self, progress_file: Path) -> None:
        try:
            validated_file = SecurePathValidator.validate_safe_path(
                progress_file, self.progress_dir
            )
        except Exception:
            return

        job_id = self.extract_job_id_from_file(validated_file)
        if not (job_id and self.validate_job_id(job_id)):
            return

        progress_data = self.get_job_progress(job_id)
        if progress_data and job_id not in self.known_jobs:
            self.known_jobs.add(job_id)
            console.print(f"[green]New job detected: {job_id}[/ green]")
            await self.broadcast_to_job(job_id, progress_data)

    async def _monitor_directory_changes(self) -> None:
        timeout_manager = get_timeout_manager()
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.is_running:
            try:
                async with timeout_manager.timeout_context(
                    "file_operations",
                    timeout=10.0,
                    strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
                ):
                    if self.progress_dir.exists():
                        for progress_file in self.progress_dir.glob("job-*.json"):
                            try:
                                await timeout_manager.with_timeout(
                                    "file_operations",
                                    self._process_progress_file(progress_file),
                                    timeout=5.0,
                                )
                            except Exception as e:
                                console.print(
                                    f"[yellow]File processing error: {e}[/yellow]"
                                )
                                continue

                    consecutive_errors = 0
                    await asyncio.sleep(1)

            except Exception as e:
                consecutive_errors += 1
                console.print(f"[red]Progress monitoring error: {e}[/red]")

                if consecutive_errors >= max_consecutive_errors:
                    console.print(
                        f"[red]Too many consecutive errors ({consecutive_errors}), stopping monitor[/red]"
                    )
                    break

                delay = min(5 * (2 ** (consecutive_errors - 1)), 60)
                await asyncio.sleep(delay)

    async def monitor_progress_files(self) -> None:
        from crackerjack.mcp.file_monitor import create_progress_monitor

        console.print("[blue]Starting progress file monitoring...[/blue]")
        timeout_manager = get_timeout_manager()

        try:
            async with timeout_manager.timeout_context(
                "file_operations",
                timeout=30.0,
                strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
            ):
                monitor = create_progress_monitor(self.progress_dir)
                await monitor.start()

                def on_progress_update(
                    job_id: str, progress_data: dict[str, t.Any]
                ) -> None:
                    if job_id and self.validate_job_id(job_id):

                        async def safe_broadcast() -> None:
                            try:
                                await timeout_manager.with_timeout(
                                    "websocket_broadcast",
                                    self.broadcast_to_job(job_id, progress_data),
                                    timeout=5.0,
                                )
                            except Exception as e:
                                console.print(
                                    f"[yellow]Broadcast failed for job {job_id}: {e}[/yellow]"
                                )

                        asyncio.create_task(safe_broadcast())  # type: ignore[no-untyped-call]

                        if job_id not in self.known_jobs:
                            self.known_jobs.add(job_id)
                            console.print(f"[green]New job detected: {job_id}[/green]")

                await self._monitor_directory_changes()

        except Exception as e:
            console.print(f"[red]Progress monitoring setup error: {e}[/red]")

    async def cleanup_old_jobs(self) -> None:
        timeout_manager = get_timeout_manager()

        while self.is_running:
            try:
                await timeout_manager.with_timeout(
                    "file_operations",
                    self._perform_cleanup_cycle(),
                    timeout=30.0,
                    strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
                )
                await asyncio.sleep(3600)
            except Exception as e:
                console.print(f"[red]Cleanup error: {e}[/red]")

                await asyncio.sleep(1800)

    async def _perform_cleanup_cycle(self) -> None:
        if not self.progress_dir.exists():
            return

        cutoff_time = self._calculate_cleanup_cutoff_time()
        old_job_files = self._find_old_job_files(cutoff_time)

        for progress_file in old_job_files:
            self._cleanup_old_job_file(progress_file)

    def _calculate_cleanup_cutoff_time(self) -> float:
        return time.time() - (24 * 60 * 60)

    def _find_old_job_files(self, cutoff_time: float) -> list[Path]:
        return [
            progress_file
            for progress_file in self.progress_dir.glob("job - *.json")
            if progress_file.stat().st_mtime < cutoff_time
        ]

    def _cleanup_old_job_file(self, progress_file: Path) -> None:
        job_id = self.extract_job_id_from_file(progress_file)

        if job_id not in self.active_connections:
            progress_file.unlink(missing_ok=True)
            console.print(f"[yellow]Cleaned up old job: {job_id}[/ yellow]")

    async def timeout_stuck_jobs(self) -> None:
        timeout_manager = get_timeout_manager()

        while self.is_running:
            try:
                await timeout_manager.with_timeout(
                    "file_operations",
                    self._check_and_timeout_stuck_jobs(),
                    timeout=60.0,
                    strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
                )
                await asyncio.sleep(300)
            except Exception as e:
                console.print(f"[red]Timeout check error: {e}[/red]")

                await asyncio.sleep(300)

    async def _check_and_timeout_stuck_jobs(self) -> None:
        if not self.progress_dir.exists():
            return

        current_time = time.time()
        timeout_seconds = 30 * 60

        for progress_file in self.progress_dir.glob("job-* .json"):
            await self._process_job_timeout_check(
                progress_file,
                current_time,
                timeout_seconds,
            )

    async def _process_job_timeout_check(
        self,
        progress_file: Path,
        current_time: float,
        timeout_seconds: int,
    ) -> None:
        try:
            validated_file = SecurePathValidator.validate_safe_path(
                progress_file, self.progress_dir
            )

            SecurePathValidator.validate_file_size(validated_file)

            progress_data = json.loads(validated_file.read_text())

            if self._should_timeout_job(
                progress_data,
                validated_file,
                current_time,
                timeout_seconds,
            ):
                self._timeout_job(progress_data, validated_file)

        except (json.JSONDecodeError, OSError, Exception):
            pass

    def _should_timeout_job(
        self,
        progress_data: dict[str, t.Any],
        progress_file: Path,
        current_time: float,
        timeout_seconds: int,
    ) -> bool:
        return (
            progress_data.get("status") == "running"
            and current_time - progress_file.stat().st_mtime > timeout_seconds
        )

    def _timeout_job(
        self, progress_data: dict[str, t.Any], progress_file: Path
    ) -> None:
        progress_data["status"] = "failed"
        progress_data["message"] = "Job timed out (no updates for 30 minutes)"

        progress_file.write_text(json.dumps(progress_data, indent=2))

        job_id = progress_data.get("job_id", "unknown")
        console.print(f"[red]Job {job_id} timed out and marked as failed[/ red]")

    def cleanup(self) -> None:
        self.is_running = False
        console.print("[blue]Job manager cleanup completed[/blue]")

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID for ACB integration."""
        return MODULE_ID

    @property
    def module_status(self) -> str:
        """Module status for ACB integration."""
        return MODULE_STATUS


# Phase 9.3: ACB Integration - Register JobManager with dependency injection system
with suppress(Exception):
    depends.set(JobManager)
