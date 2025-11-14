import asyncio
import json
import time
import typing as t
from collections.abc import Callable
from pathlib import Path

# Type aliases for watchdog types
FileSystemEvent: t.Any
FileSystemEventHandler: t.Any
Observer: t.Any
WATCHDOG_AVAILABLE: bool

try:
    from watchdog.events import FileSystemEvent as WatchdogFileSystemEvent
    from watchdog.events import FileSystemEventHandler as WatchdogFileSystemEventHandler
    from watchdog.observers import Observer as WatchdogObserver

    FileSystemEvent = WatchdogFileSystemEvent
    FileSystemEventHandler = WatchdogFileSystemEventHandler
    Observer = WatchdogObserver
    WATCHDOG_AVAILABLE = True
except ImportError:
    # Type stubs for when watchdog is not available
    FileSystemEvent = t.Any
    FileSystemEventHandler = t.Any
    Observer = t.Any
    WATCHDOG_AVAILABLE = False

import contextlib

from acb import console

from crackerjack.services.secure_path_utils import SecurePathValidator

# console imported from acb


if WATCHDOG_AVAILABLE:

    class ProgressFileHandler(FileSystemEventHandler):
        def __init__(
            self, callback: Callable[[str, dict[str, t.Any]], None], progress_dir: Path
        ) -> None:
            super().__init__()
            self.callback = callback
            self.progress_dir = SecurePathValidator.validate_safe_path(progress_dir)
            self._last_processed: dict[str, float] = {}
            self._debounce_delay = 0.1

        def on_modified(self, event: FileSystemEvent) -> None:
            if event.is_directory:
                return

            try:
                file_path = Path(event.src_path)

                validated_path = SecurePathValidator.validate_safe_path(
                    file_path, self.progress_dir
                )

                if (
                    not validated_path.name.startswith("job-")
                    or validated_path.suffix != ".json"
                ):
                    return

                now = time.time()
                if validated_path.name in self._last_processed:
                    if (
                        now - self._last_processed[validated_path.name]
                        < self._debounce_delay
                    ):
                        return

                self._last_processed[validated_path.name] = now

                job_id = validated_path.stem.replace("job-", "")
            except Exception:
                return

            try:
                SecurePathValidator.validate_file_size(validated_path)

                with validated_path.open() as f:
                    progress_data = json.load(f)

                self.callback(job_id, progress_data)

            except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                console.print(
                    f"[yellow]Warning: Failed to read progress file {file_path}: {e}[/ yellow]",
                )

        def on_created(self, event: FileSystemEvent) -> None:
            self.on_modified(event)
else:
    # Create a stub class with the same interface when watchdog is not available
    class ProgressFileHandler:  # type: ignore[no-redef]
        def __init__(
            self, callback: Callable[[str, dict[str, t.Any]], None], progress_dir: Path
        ) -> None:
            self.callback = callback
            self.progress_dir = progress_dir
            self._last_processed: dict[str, float] = {}
            self._debounce_delay = 0.1

        def on_modified(self, event: FileSystemEvent) -> None:
            pass

        def on_created(self, event: FileSystemEvent) -> None:
            pass


class AsyncProgressMonitor:
    def __init__(self, progress_dir: Path) -> None:
        self.progress_dir = SecurePathValidator.validate_safe_path(progress_dir)
        self.observer: Observer | None = None
        self.subscribers: dict[str, set[Callable[[dict[str, t.Any]], None]]] = {}
        self._running = False

        self.progress_dir.mkdir(exist_ok=True)

        if not WATCHDOG_AVAILABLE:
            console.print(
                "[yellow]Warning: watchdog not available, falling back to polling[/ yellow]",
            )

    async def start(self) -> None:
        if not WATCHDOG_AVAILABLE:
            return

        self._running = True

        handler = ProgressFileHandler(self._on_file_changed, self.progress_dir)

        self.observer = Observer()
        self.observer.schedule(handler, str(self.progress_dir), recursive=False)
        self.observer.start()

        console.print(
            f"[green]📁 Started monitoring progress directory: {self.progress_dir}[/ green]",
        )

    async def stop(self) -> None:
        self._running = False

        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        console.print("[yellow]📁 Stopped progress directory monitoring[/ yellow]")

    def subscribe(
        self, job_id: str, callback: Callable[[dict[str, t.Any]], None]
    ) -> None:
        if job_id not in self.subscribers:
            self.subscribers[job_id] = set()

        self.subscribers[job_id].add(callback)
        console.print(f"[cyan]📋 Subscribed to job updates: {job_id}[/ cyan]")

    def unsubscribe(
        self, job_id: str, callback: Callable[[dict[str, t.Any]], None]
    ) -> None:
        if job_id in self.subscribers:
            self.subscribers[job_id].discard(callback)

            if not self.subscribers[job_id]:
                del self.subscribers[job_id]

        console.print(f"[cyan]📋 Unsubscribed from job updates: {job_id}[/ cyan]")

    def _on_file_changed(self, job_id: str, progress_data: dict[str, t.Any]) -> None:
        if job_id in self.subscribers:
            for callback in self.subscribers[job_id].copy():
                try:
                    callback(progress_data)
                except Exception as e:
                    console.print(
                        f"[red]Error in progress callback for job {job_id}: {e}[/ red]",
                    )

                    self.subscribers[job_id].discard(callback)

    async def get_current_progress(self, job_id: str) -> dict[str, t.Any] | None:
        progress_file = self.progress_dir / f"job-{job_id}.json"

        if not progress_file.exists():
            return None

        try:
            with progress_file.open() as f:
                json_result = json.load(f)
                return t.cast(dict[str, t.Any] | None, json_result)
        except (json.JSONDecodeError, OSError):
            return None

    async def cleanup_completed_jobs(self, max_age_minutes: int = 60) -> int:
        if not self.progress_dir.exists():
            return 0

        cleaned = 0
        cutoff_time = time.time() - (max_age_minutes * 60)

        for progress_file in self.progress_dir.glob("job-* .json"):
            try:
                if progress_file.stat().st_mtime < cutoff_time:
                    with progress_file.open() as f:
                        data = json.load(f)

                    if data.get("status") in ("completed", "failed"):
                        progress_file.unlink()
                        cleaned += 1
                        console.print(
                            f"[dim]🧹 Cleaned up old progress file: {progress_file.name}[/ dim]",
                        )

            except (json.JSONDecodeError, OSError, KeyError):
                from contextlib import suppress

                with suppress(OSError):
                    progress_file.unlink()
                    cleaned += 1
                    console.print(
                        f"[dim]🧹 Removed corrupted progress file: {progress_file.name}[/ dim]",
                    )

        return cleaned


class PollingProgressMonitor:
    def __init__(self, progress_dir: Path) -> None:
        self.progress_dir = SecurePathValidator.validate_safe_path(progress_dir)
        self.subscribers: dict[str, set[Callable[[dict[str, t.Any]], None]]] = {}
        self._running = False
        self._poll_task: asyncio.Task[None] | None = None
        self._file_mtimes: dict[str, float] = {}

        self.progress_dir.mkdir(exist_ok=True)

    async def start(self) -> None:
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        console.print(
            f"[yellow]📁 Started polling progress directory: {self.progress_dir}[/ yellow]",
        )

    async def stop(self) -> None:
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        console.print("[yellow]📁 Stopped progress directory polling[/ yellow]")

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._check_files()
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                console.print(f"[red]Error in polling loop: {e}[/ red]")
                await asyncio.sleep(1)

    async def _check_files(self) -> None:
        if not self.progress_dir.exists():
            return

        current_files = {}

        for progress_file in self.progress_dir.glob("job-*.json"):
            try:
                validated_file = SecurePathValidator.validate_safe_path(
                    progress_file, self.progress_dir
                )

                mtime = validated_file.stat().st_mtime
                current_files[validated_file.name] = mtime

                if (
                    validated_file.name not in self._file_mtimes
                    or mtime > self._file_mtimes[validated_file.name]
                ):
                    job_id = validated_file.stem.replace("job-", "")

                    try:
                        SecurePathValidator.validate_file_size(validated_file)
                        with validated_file.open() as f:
                            progress_data = json.load(f)

                        self._notify_subscribers(job_id, progress_data)

                    except (json.JSONDecodeError, OSError) as e:
                        console.print(
                            f"[yellow]Warning: Failed to read progress file {progress_file}: {e}[/ yellow]",
                        )

            except OSError:
                continue

        self._file_mtimes = current_files

    def _notify_subscribers(self, job_id: str, progress_data: dict[str, t.Any]) -> None:
        if job_id in self.subscribers:
            for callback in self.subscribers[job_id].copy():
                try:
                    callback(progress_data)
                except Exception as e:
                    console.print(
                        f"[red]Error in progress callback for job {job_id}: {e}[/ red]",
                    )
                    self.subscribers[job_id].discard(callback)

    def subscribe(
        self, job_id: str, callback: Callable[[dict[str, t.Any]], None]
    ) -> None:
        if job_id not in self.subscribers:
            self.subscribers[job_id] = set()

        self.subscribers[job_id].add(callback)
        console.print(f"[cyan]📋 Subscribed to job updates: {job_id} (polling)[/ cyan]")

    def unsubscribe(
        self, job_id: str, callback: Callable[[dict[str, t.Any]], None]
    ) -> None:
        if job_id in self.subscribers:
            self.subscribers[job_id].discard(callback)

            if not self.subscribers[job_id]:
                del self.subscribers[job_id]

        console.print(
            f"[cyan]📋 Unsubscribed from job updates: {job_id} (polling)[/ cyan]",
        )

    async def get_current_progress(self, job_id: str) -> dict[str, t.Any] | None:
        progress_file = self.progress_dir / f"job-{job_id}.json"

        if not progress_file.exists():
            return None

        try:
            with progress_file.open() as f:
                json_result = json.load(f)
                return t.cast(dict[str, t.Any] | None, json_result)
        except (json.JSONDecodeError, OSError):
            return None

    async def cleanup_completed_jobs(self, max_age_minutes: int = 60) -> int:
        if not self.progress_dir.exists():
            return 0

        cleaned = 0
        cutoff_time = time.time() - (max_age_minutes * 60)

        for progress_file in self.progress_dir.glob("job-* .json"):
            try:
                if progress_file.stat().st_mtime < cutoff_time:
                    with progress_file.open() as f:
                        data = json.load(f)

                    if data.get("status") in ("completed", "failed"):
                        progress_file.unlink()
                        cleaned += 1
                        console.print(
                            f"[dim]🧹 Cleaned up old progress file: {progress_file.name}[/ dim]",
                        )

            except (json.JSONDecodeError, OSError, KeyError):
                from contextlib import suppress

                with suppress(OSError):
                    progress_file.unlink()
                    cleaned += 1
                    console.print(
                        f"[dim]🧹 Removed corrupted progress file: {progress_file.name}[/ dim]",
                    )

        return cleaned


def create_progress_monitor(
    progress_dir: Path,
) -> AsyncProgressMonitor | PollingProgressMonitor:
    if WATCHDOG_AVAILABLE:
        return AsyncProgressMonitor(progress_dir)
    return PollingProgressMonitor(progress_dir)
