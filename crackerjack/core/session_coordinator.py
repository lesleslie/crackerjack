import json
import logging
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from rich.console import Console

from crackerjack.models.protocols import OptionsProtocol
from crackerjack.models.task import SessionTracker


class SessionCoordinator:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        web_job_id: str | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.session_tracker: SessionTracker | None = None
        self._cleanup_handlers: list[t.Callable[[], None]] = []
        self._thread_pool = None
        self._lock_files: set[Path] = set()

        import uuid

        self.session_id = web_job_id or str(uuid.uuid4())
        self.web_job_id = web_job_id
        self.start_time = time.time()
        self.tasks: dict[str, t.Any] = {}
        self.current_task: str | None = None
        self.success: bool = False

        self._setup_logging()

        if self.web_job_id:
            self._setup_websocket_progress_file()

    def start_session(self, task_name: str) -> None:
        self.current_task = task_name

    def end_session(self, success: bool = True) -> None:
        self.success = success
        self.end_time = time.time()
        if success:
            self.complete_task("session", "Session completed successfully")
        else:
            self.fail_task("session", "Session completed with errors")

    def initialize_session_tracking(self, options: OptionsProtocol) -> None:
        if hasattr(options, "track_progress") and options.track_progress:
            import uuid

            self.session_tracker = SessionTracker(
                console=self.console,
                session_id=str(uuid.uuid4()),
                start_time=time.time(),
            )

    def track_task(self, task_id: str, task_name: str) -> str:
        import time

        task_obj = type(
            "Task",
            (),
            {
                "task_id": task_id,
                "description": task_name,
                "start_time": time.time(),
                "status": "in_progress",
                "details": None,
                "end_time": None,
                "progress": 0,
            },
        )()

        self.tasks[task_id] = task_obj

        if self.session_tracker:
            self.session_tracker.start_task(task_id, task_name)

        return task_id

    def update_task(
        self,
        task_id: str,
        status: str,
        details: str | None = None,
        progress: int | None = None,
    ) -> None:
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = status
            if details:
                task.details = details
            if progress is not None:
                task.progress = progress

            if status in ("completed", "failed"):
                task.end_time = time.time()

    def complete_task(self, task_id: str, details: str | None = None) -> None:
        if self.session_tracker:
            self.session_tracker.complete_task(task_id, details=details)

    def fail_task(self, task_id: str, error: str) -> None:
        if self.session_tracker:
            self.session_tracker.fail_task(task_id, error)

    def get_session_summary(self) -> dict[str, int] | None:
        if self.session_tracker:
            return self.session_tracker.get_summary()
        return None

    def get_summary(self) -> dict[str, t.Any]:
        duration = getattr(self, "end_time", time.time()) - self.start_time
        tasks_count = len(self.tasks)

        if self.session_tracker:
            return self.session_tracker.get_summary()

        return {
            "session_id": self.session_id,
            "duration": duration,
            "tasks_count": tasks_count,
            "success": self.success,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "description": task.description,
                    "status": task.status,
                    "details": task.details,
                    "start_time": task.start_time,
                    "end_time": task.end_time,
                    "progress": task.progress,
                }
                for task in self.tasks.values()
            ],
        }

    def finalize_session(self, start_time: float, success: bool) -> None:
        total_time = time.time() - start_time
        if success:
            self.complete_task(
                "workflow",
                f"Completed successfully in {total_time: .1f}s",
            )
        else:
            self.complete_task(
                "workflow",
                f"Completed with issues in {total_time: .1f}s",
            )

    def register_cleanup(self, cleanup_handler: t.Callable[[], None]) -> None:
        self._cleanup_handlers.append(cleanup_handler)

    def track_lock_file(self, lock_file_path: Path) -> None:
        self._lock_files.add(lock_file_path)

    def cleanup_resources(self) -> None:
        for cleanup_handler in self._cleanup_handlers:
            with suppress(Exception):
                cleanup_handler()

        self._cleanup_temporary_files()

    def _cleanup_temporary_files(self) -> None:
        if not hasattr(self, "_cleanup_config") or self._cleanup_config is None:
            self._cleanup_debug_logs()
            self._cleanup_coverage_files()
            self._cleanup_pycache_directories()
        elif self._cleanup_config.auto_cleanup:
            self._cleanup_debug_logs(keep_recent=self._cleanup_config.keep_debug_logs)
            self._cleanup_coverage_files(
                keep_recent=self._cleanup_config.keep_coverage_files,
            )
            self._cleanup_pycache_directories()

    def set_cleanup_config(self, cleanup_config: t.Any) -> None:
        self._cleanup_config = cleanup_config

    def _cleanup_debug_logs(self, keep_recent: int = 5) -> None:
        with suppress(Exception):
            from crackerjack.services.log_manager import get_log_manager

            log_manager = get_log_manager()

            log_manager.rotate_logs(
                log_manager.debug_dir,
                "debug-*.log",
                max_files=keep_recent,
                max_age_days=7,
            )

            legacy_pattern = "crackerjack-debug-*.log"
            legacy_files = sorted(
                self.pkg_path.glob(legacy_pattern),
                key=lambda p: p.stat().st_mtime,
            )

            for old_file in legacy_files[:-keep_recent]:
                with suppress(FileNotFoundError, PermissionError):
                    old_file.unlink()

    def _cleanup_coverage_files(self, keep_recent: int = 10) -> None:
        with suppress(Exception):
            cache_dir = Path.home() / ".cache" / "crackerjack" / "coverage"
            if cache_dir.exists():
                pattern = ".coverage *"
                coverage_files = sorted(
                    cache_dir.glob(pattern),
                    key=lambda p: p.stat().st_mtime,
                )

                for old_file in coverage_files[:-keep_recent]:
                    with suppress(FileNotFoundError, PermissionError):
                        old_file.unlink()

            pattern = ".coverage.*"
            coverage_files = sorted(
                self.pkg_path.glob(pattern),
                key=lambda p: p.stat().st_mtime,
            )

            for old_file in coverage_files:
                with suppress(FileNotFoundError, PermissionError):
                    old_file.unlink()

    def _cleanup_pycache_directories(self) -> None:
        with suppress(Exception):
            import shutil

            for pycache_dir in self.pkg_path.rglob("__pycache__"):
                if pycache_dir.is_dir():
                    with suppress(FileNotFoundError, PermissionError):
                        shutil.rmtree(pycache_dir)

    def _setup_logging(self) -> None:
        logger = logging.getLogger("crackerjack")
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.WARNING)
            logger.addHandler(handler)
            logger.setLevel(logging.WARNING)

    def _setup_websocket_progress_file(self) -> None:
        import tempfile

        self.progress_dir = Path(tempfile.gettempdir()) / "crackerjack-mcp-progress"
        self.progress_file = self.progress_dir / f"job-{self.web_job_id}.json"

        if self.progress_file.exists():
            self._update_websocket_progress("running", "Crackerjack process started")

    def _update_websocket_progress(self, status: str, message: str) -> None:
        if not hasattr(self, "progress_file") or not self.progress_file:
            return

        try:
            progress_data = {}
            if self.progress_file.exists():
                progress_data = json.loads(self.progress_file.read_text())

            progress_data.update(
                {
                    "status": status,
                    "message": message,
                    "updated_at": time.time(),
                    "current_stage": message,
                },
            )

            self.progress_file.write_text(json.dumps(progress_data, indent=2))

        except Exception as e:
            self.console.print(
                f"[dim yellow]Warning: Could not update progress file: {e}[/ dim yellow]",
            )

    def update_stage(self, stage: str, status: str) -> None:
        if self.web_job_id:
            self._update_websocket_progress(status, f"{stage}: {status}")
