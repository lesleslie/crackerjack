import asyncio
import json
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


class JobManager:
    def __init__(self, progress_dir: Path) -> None:
        self.progress_dir = progress_dir
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

        import re

        # Performance: Use simpler regex pattern without whitespace
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", job_id) and len(job_id) <= 50)

    def add_connection(self, job_id: str, websocket: Any) -> None:
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)

    def remove_connection(self, job_id: str, websocket: Any) -> None:
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast_to_job(self, job_id: str, data: dict) -> None:
        if job_id not in self.active_connections:
            return

        connections = self.active_connections[job_id].copy()
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception:
                self.remove_connection(job_id, websocket)

    def get_latest_job_id(self) -> str | None:
        if not self.progress_dir.exists():
            return None

        # Performance: Use more specific glob pattern to reduce filesystem calls
        progress_files = list(self.progress_dir.glob("job-*.json"))
        if not progress_files:
            return None

        latest_file = max(progress_files, key=lambda f: f.stat().st_mtime)
        return self.extract_job_id_from_file(latest_file)

    def extract_job_id_from_file(self, progress_file: Path) -> str | None:
        # Performance: Use slice instead of replace for fixed prefix removal
        return (
            progress_file.stem[4:]  # Remove "job-" prefix (4 chars)
            if progress_file.stem.startswith("job-")
            else None
        )

    def get_job_progress(self, job_id: str) -> dict | None:
        if not self.validate_job_id(job_id):
            return None

        progress_file = self.progress_dir / f"job-{job_id}.json"
        if not progress_file.exists():
            return None

        try:
            return json.loads(progress_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    async def _process_progress_file(self, progress_file: Path) -> None:
        """Process a single progress file and handle new job detection."""
        job_id = self.extract_job_id_from_file(progress_file)
        if not (job_id and self.validate_job_id(job_id)):
            return

        progress_data = self.get_job_progress(job_id)
        if progress_data and job_id not in self.known_jobs:
            self.known_jobs.add(job_id)
            console.print(f"[green]New job detected: {job_id}[/green]")
            await self.broadcast_to_job(job_id, progress_data)

    async def _monitor_directory_changes(self) -> None:
        """Monitor the progress directory for new job files."""
        while self.is_running:
            try:
                if self.progress_dir.exists():
                    for progress_file in self.progress_dir.glob("job-*.json"):
                        await self._process_progress_file(progress_file)

                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                console.print(f"[red]Progress monitoring error: {e}[/red]")
                await asyncio.sleep(5)  # Wait longer on error

    async def monitor_progress_files(self) -> None:
        from crackerjack.mcp.file_monitor import create_progress_monitor

        console.print("[blue]Starting progress file monitoring...[/blue]")

        try:
            monitor = create_progress_monitor(self.progress_dir)
            await monitor.start()

            def on_progress_update(job_id: str, progress_data: dict) -> None:
                """Callback for when progress files are updated."""
                if job_id and self.validate_job_id(job_id):
                    # Schedule the broadcast in the event loop
                    asyncio.create_task(self.broadcast_to_job(job_id, progress_data))

                    if job_id not in self.known_jobs:
                        self.known_jobs.add(job_id)
                        console.print(f"[green]New job detected: {job_id}[/green]")

            # Monitor for new job files by checking the directory periodically
            await self._monitor_directory_changes()

        except Exception as e:
            console.print(f"[red]Progress monitoring setup error: {e}[/red]")

    async def cleanup_old_jobs(self) -> None:
        """Periodically clean up old job files."""
        while self.is_running:
            try:
                await self._perform_cleanup_cycle()
                await asyncio.sleep(3600)
            except Exception as e:
                console.print(f"[red]Cleanup error: {e}[/red]")
                await asyncio.sleep(3600)

    async def _perform_cleanup_cycle(self) -> None:
        """Perform a single cleanup cycle for old jobs."""
        if not self.progress_dir.exists():
            return

        cutoff_time = self._calculate_cleanup_cutoff_time()
        old_job_files = self._find_old_job_files(cutoff_time)

        for progress_file in old_job_files:
            self._cleanup_old_job_file(progress_file)

    def _calculate_cleanup_cutoff_time(self) -> float:
        """Calculate cutoff time for job cleanup (24 hours ago)."""
        return time.time() - (24 * 60 * 60)

    def _find_old_job_files(self, cutoff_time: float) -> list[Path]:
        """Find job files older than the cutoff time."""
        return [
            progress_file
            for progress_file in self.progress_dir.glob("job-*.json")
            if progress_file.stat().st_mtime < cutoff_time
        ]

    def _cleanup_old_job_file(self, progress_file: Path) -> None:
        """Clean up a single old job file if it's safe to do so."""
        job_id = self.extract_job_id_from_file(progress_file)

        if job_id not in self.active_connections:
            progress_file.unlink(missing_ok=True)
            console.print(f"[yellow]Cleaned up old job: {job_id}[/yellow]")

    async def timeout_stuck_jobs(self) -> None:
        """Monitor and timeout stuck jobs that haven't been updated."""
        while self.is_running:
            try:
                await self._check_and_timeout_stuck_jobs()
                await asyncio.sleep(300)
            except Exception as e:
                console.print(f"[red]Timeout check error: {e}[/red]")
                await asyncio.sleep(300)

    async def _check_and_timeout_stuck_jobs(self) -> None:
        """Check for stuck jobs and timeout those that are inactive."""
        if not self.progress_dir.exists():
            return

        current_time = time.time()
        timeout_seconds = 30 * 60

        for progress_file in self.progress_dir.glob("job -* .json"):
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
        """Process timeout check for a single job file."""
        try:
            progress_data = json.loads(progress_file.read_text())

            if self._should_timeout_job(
                progress_data,
                progress_file,
                current_time,
                timeout_seconds,
            ):
                self._timeout_job(progress_data, progress_file)

        except (json.JSONDecodeError, OSError):
            pass  # Skip files that can't be processed

    def _should_timeout_job(
        self,
        progress_data: dict,
        progress_file: Path,
        current_time: float,
        timeout_seconds: int,
    ) -> bool:
        """Determine if a job should be timed out."""
        return (
            progress_data.get("status") == "running"
            and current_time - progress_file.stat().st_mtime > timeout_seconds
        )

    def _timeout_job(self, progress_data: dict, progress_file: Path) -> None:
        """Mark a job as failed due to timeout."""
        progress_data["status"] = "failed"
        progress_data["message"] = "Job timed out (no updates for 30 minutes)"

        progress_file.write_text(json.dumps(progress_data, indent=2))

        job_id = progress_data.get("job_id", "unknown")
        console.print(f"[red]Job {job_id} timed out and marked as failed[/red]")

    def cleanup(self) -> None:
        self.is_running = False
        console.print("[blue]Job manager cleanup completed[/blue]")
