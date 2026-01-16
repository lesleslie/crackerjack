from __future__ import annotations

import logging
import time
import typing as t
import uuid
from contextlib import suppress
from pathlib import Path

from crackerjack.core.console import CrackerjackConsole
from crackerjack.models.protocols import ConsoleInterface
from crackerjack.models.task import SessionTracker

logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    from crackerjack.core.workflow_orchestrator import WorkflowPipeline
    from crackerjack.models.protocols import OptionsProtocol


class SessionCoordinator:
    def __init__(
        self,
        console: ConsoleInterface | None = None,
        pkg_path: Path | None = None,
        web_job_id: str | None = None,
    ) -> None:
        self.console = console or CrackerjackConsole()
        self.pkg_path = pkg_path or Path.cwd()
        self.web_job_id = web_job_id
        self.session_id = web_job_id or uuid.uuid4().hex[:8]
        self.start_time = time.time()
        self.cleanup_config: t.Any = None
        self._cleanup_config: t.Any = None
        self.cleanup_handlers: list[t.Callable[[], None]] = []
        self.lock_files: set[Path] = set()
        self.current_task: str | None = None
        self._cleanup_handlers = self.cleanup_handlers
        self._lock_files = self.lock_files
        self._thread_pool = None

        self.session_tracker: SessionTracker | None = None
        self.tasks: dict[str, t.Any] = {}

    def initialize_session_tracking(self, options: OptionsProtocol) -> None:
        if not getattr(options, "track_progress", False):
            return

        self._setup_logging(options)
        self._setup_websocket_progress_file()
        self._initialize_quality_service()

        self.session_tracker = SessionTracker(
            session_id=self.session_id,
            start_time=self.start_time,
        )

        self.session_tracker.metadata.update(
            {
                "options": getattr(options, "__dict__", {}),
                "pkg_path": str(self.pkg_path),
                "initialized_at": time.time(),
            },
        )
        self.tasks = self.session_tracker.tasks
        self.start_session("workflow")
        self.console.print("[cyan]📊[/ cyan] Session tracking enabled")

    def start_session(self, task_name: str) -> None:
        self.current_task = task_name

        if self.session_tracker is None:
            self.session_tracker = SessionTracker(
                session_id=self.session_id,
                start_time=self.start_time,
            )
            self.tasks = self.session_tracker.tasks
            self.session_tracker.metadata.update({"pkg_path": str(self.pkg_path)})
        self.session_tracker.metadata["current_session"] = task_name

    def end_session(self, success: bool) -> None:
        self.end_time = time.time()
        if self.session_tracker:
            self.session_tracker.metadata["completed_at"] = self.end_time
            self.session_tracker.metadata["success"] = success
        self.current_task = None

    def track_task(
        self,
        task_id: str,
        task_name: str,
        details: str | None = None,
    ) -> str:
        if self.session_tracker is None:
            self.session_tracker = SessionTracker(
                session_id=self.session_id,
                start_time=self.start_time,
            )
            self.tasks = self.session_tracker.tasks
            self.session_tracker.metadata.update({"pkg_path": str(self.pkg_path)})
        self.session_tracker.start_task(task_id, task_name, details)
        return task_id

    def complete_task(
        self,
        task_id: str,
        details: str | None = None,
        files_changed: list[str] | None = None,
    ) -> None:
        if self.session_tracker:
            self.session_tracker.complete_task(task_id, details, files_changed)

    def update_task(
        self,
        task_id: str,
        status: str,
        *,
        details: str | None = None,
        files_changed: list[str] | None = None,
        error_message: str | None = None,
        progress: int | None = None,
    ) -> None:
        self._ensure_session_tracker()

        normalized = status.lower()

        if normalized == "completed":
            self._update_completed_task(task_id, details, files_changed)
        elif normalized == "failed":
            self._update_failed_task(task_id, error_message, details)
        elif normalized == "in_progress":
            self._update_in_progress_task(task_id, details, progress)
        else:
            self._update_generic_task(task_id, normalized, details, progress)

    def _ensure_session_tracker(self) -> None:
        if self.session_tracker is None:
            self.session_tracker = SessionTracker(
                session_id=self.session_id,
                start_time=self.start_time,
            )
            self.tasks = self.session_tracker.tasks
            self.session_tracker.metadata.update({"pkg_path": str(self.pkg_path)})

    def _update_completed_task(
        self,
        task_id: str,
        details: str | None,
        files_changed: list[str] | None,
    ) -> None:
        assert self.session_tracker is not None
        self.session_tracker.complete_task(task_id, details, files_changed)

    def _update_failed_task(
        self,
        task_id: str,
        error_message: str | None,
        details: str | None,
    ) -> None:
        assert self.session_tracker is not None
        self.session_tracker.fail_task(task_id, error_message or "Task failed", details)

    def _update_in_progress_task(
        self,
        task_id: str,
        details: str | None,
        progress: int | None,
    ) -> None:
        assert self.session_tracker is not None
        if task_id not in self.session_tracker.tasks:
            self.session_tracker.start_task(task_id, task_id, details)
        else:
            task = self.session_tracker.tasks[task_id]
            task.status = "in_progress"
            if details:
                task.details = details
            if progress is not None:
                task.progress = progress

    def _update_generic_task(
        self,
        task_id: str,
        status: str,
        details: str | None,
        progress: int | None,
    ) -> None:
        assert self.session_tracker is not None
        if task_id in self.session_tracker.tasks:
            task = self.session_tracker.tasks[task_id]
            task.status = status or task.status
            if details:
                task.details = details
            if progress is not None:
                task.progress = progress

    def fail_task(
        self,
        task_id: str,
        error_message: str,
        details: str | None = None,
    ) -> None:
        if self.session_tracker:
            if details:
                self.session_tracker.fail_task(task_id, error_message, details)
            else:
                self.session_tracker.fail_task(task_id, error_message)

    def get_session_summary(self) -> dict[str, t.Any]:
        if self.session_tracker is None:
            return {"tasks_count": 0}
        return self.session_tracker.get_summary()

    def get_summary(self) -> dict[str, t.Any]:
        tasks = (
            {tid: task.__dict__ for tid, task in self.session_tracker.tasks.items()}
            if self.session_tracker
            else {}
        )
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "tasks": tasks,
            "metadata": self.session_tracker.metadata if self.session_tracker else {},
        }

    def finalize_session(self, start_time: float, success: bool) -> None:
        duration = time.time() - start_time
        self._end_time = time.time()
        if self.session_tracker:
            self.session_tracker.metadata["duration"] = duration
            self.session_tracker.metadata["success"] = success
        if success:
            self.complete_task(
                self.current_task or "workflow",
                f"Completed successfully in {duration:.1f}s",
            )
        elif not success:
            self.fail_task(
                self.current_task or "workflow",
                f"Completed with issues in {duration:.1f}s",
            )
        self.current_task = None

    def cleanup_resources(self) -> None:
        for handler in self._cleanup_handlers.copy():
            try:
                handler()
            except Exception as exc:  # pragma: no cover - defensive
                self.console.print(
                    f"[red]Cleanup handler error:[/ red] {type(exc).__name__}: {exc}",
                )

        with suppress(Exception):
            self._cleanup_temporary_files()
        with suppress(Exception):
            self._cleanup_pycache_directories()

        for lock_path in list(self._lock_files):
            with suppress(OSError):
                if lock_path.exists():
                    lock_path.unlink()
            self._lock_files.discard(lock_path)

    def register_cleanup(self, handler: t.Callable[[], None]) -> None:
        self._cleanup_handlers.append(handler)

    def track_lock_file(self, path: Path) -> None:
        self._lock_files.add(path)

    def set_cleanup_config(self, config: t.Any) -> None:
        self._cleanup_config = config

    def _cleanup_temporary_files(self) -> None:
        if self._cleanup_config is None:
            self._cleanup_debug_logs()
            self._cleanup_coverage_files()
            return

        if not getattr(self._cleanup_config, "auto_cleanup", False):
            return

        keep_debug = getattr(self._cleanup_config, "keep_debug_logs", None)
        keep_coverage = getattr(self._cleanup_config, "keep_coverage_files", None)

        if keep_debug is not None:
            self._cleanup_debug_logs(keep_recent=keep_debug)
        else:
            self._cleanup_debug_logs()

        if keep_coverage is not None:
            self._cleanup_coverage_files(keep_recent=keep_coverage)
        else:
            self._cleanup_coverage_files()

    def _cleanup_debug_logs(self, keep_recent: int | None = None) -> None:
        pattern = "crackerjack-debug-*.log"
        debug_files = sorted(
            self.pkg_path.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if keep_recent is None or keep_recent < 0:
            files_to_remove = debug_files
        else:
            files_to_remove = debug_files[keep_recent:]

        for file_path in files_to_remove:
            try:
                file_path.unlink()
            except PermissionError:
                logger.debug(f"Permission denied: {file_path}")
            except FileNotFoundError:
                logger.debug(f"File not found: {file_path}")

    def _cleanup_coverage_files(self, keep_recent: int | None = None) -> None:
        pattern = ".coverage.*"
        coverage_files = sorted(
            self.pkg_path.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if keep_recent is None or keep_recent < 0:
            files_to_remove = coverage_files
        else:
            files_to_remove = coverage_files[keep_recent:]

        for file_path in files_to_remove:
            try:
                file_path.unlink()
            except FileNotFoundError:
                logger.debug(f"File not found: {file_path}")

    def _cleanup_pycache_directories(self) -> None:
        pass

    def _setup_logging(self, options: OptionsProtocol) -> None:
        pass

    def _setup_websocket_progress_file(self) -> None:
        pass

    def _initialize_quality_service(self) -> None:
        pass

    def update_stage(self, stage: str, status: str) -> None:
        self._update_websocket_progress(stage, status)

    def _update_websocket_progress(self, stage: str, status: str) -> None:
        pass


class SessionController:
    def __init__(self, pipeline: WorkflowPipeline) -> None:
        self._pipeline = pipeline

    def initialize(self, options: OptionsProtocol) -> None:
        pipeline = self._pipeline
        pipeline.session.initialize_session_tracking(options)
        pipeline._configure_session_cleanup(options)
        pipeline._initialize_zuban_lsp(options)
        pipeline._configure_hook_manager_lsp(options)
        pipeline._register_lsp_cleanup_handler(options)
        pipeline._log_workflow_startup_info(options)
