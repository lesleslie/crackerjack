from __future__ import annotations

import time
import typing as t
import uuid
from contextlib import suppress
from pathlib import Path

from rich.console import Console

from crackerjack.models.task import SessionTracker

if t.TYPE_CHECKING:
    from crackerjack.core.workflow_orchestrator import WorkflowPipeline
    from crackerjack.models.protocols import OptionsProtocol


class SessionCoordinator:
    """Lightweight session tracking and cleanup coordinator."""

    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        web_job_id: str | None = None,
    ) -> None:
        self.console = console or Console()
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
        """Initialize session metadata and baseline tracking."""
        if not getattr(options, "track_progress", False):
            return

        self._setup_logging(options)
        self._setup_websocket_progress_file()
        self._initialize_quality_service()

        self.session_tracker = SessionTracker(
            session_id=self.session_id, start_time=self.start_time
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
        """Record the start of a high-level session task."""
        self.current_task = task_name
        # Lazily initialize session tracker if not already set
        if self.session_tracker is None:
            self.session_tracker = SessionTracker(
                session_id=self.session_id, start_time=self.start_time
            )
            self.tasks = self.session_tracker.tasks
            self.session_tracker.metadata.update({"pkg_path": str(self.pkg_path)})
        self.session_tracker.metadata["current_session"] = task_name

    def end_session(self, success: bool) -> None:
        """Mark session completion."""
        # Record wall-clock end time for tests and summaries
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
        """Track a task within the session."""
        if self.session_tracker is None:
            self.session_tracker = SessionTracker(
                session_id=self.session_id, start_time=self.start_time
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
        """Mark task as completed."""
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
        """Update a task's status in the current session.

        Supports 'completed', 'failed', and 'in_progress' states. Unknown statuses
        are set directly on the TaskStatusData if present.
        """
        if self.session_tracker is None:
            # Initialize tracker lazily to ensure tasks dict exists
            self.session_tracker = SessionTracker(
                session_id=self.session_id, start_time=self.start_time
            )
            self.tasks = self.session_tracker.tasks
            self.session_tracker.metadata.update({"pkg_path": str(self.pkg_path)})

        normalized = status.lower()
        if normalized == "completed":
            self.session_tracker.complete_task(task_id, details, files_changed)
            return
        if normalized == "failed":
            self.session_tracker.fail_task(
                task_id, error_message or "Task failed", details
            )
            return
        if normalized == "in_progress":
            # Ensure task exists; if not, create it as in-progress
            if task_id not in self.session_tracker.tasks:
                self.session_tracker.start_task(task_id, task_id, details)
            else:
                task = self.session_tracker.tasks[task_id]
                task.status = "in_progress"
                if details:
                    task.details = details
                if progress is not None:
                    task.progress = progress
            return

        # Fallback: set arbitrary status value if task exists
        if task_id in self.session_tracker.tasks:
            task = self.session_tracker.tasks[task_id]
            task.status = normalized or task.status
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
        """Mark task as failed."""
        if self.session_tracker:
            self.session_tracker.fail_task(task_id, error_message, details)

    def get_session_summary(self) -> dict[str, t.Any] | None:
        """Return a summary of session task outcomes."""
        if not self.session_tracker or not self.session_tracker.tasks:
            return None
        tasks = list(self.session_tracker.tasks.values())
        total = len(tasks)
        completed = len([t for t in tasks if t.status == "completed"])
        failed = len([t for t in tasks if t.status == "failed"])
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
        }

    def get_summary(self) -> dict[str, t.Any]:
        """Return session summary details."""
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
        """Finalize session bookkeeping."""
        duration = time.time() - start_time
        self._end_time = time.time()
        if self.session_tracker:
            self.session_tracker.metadata["duration"] = duration
            self.session_tracker.metadata["success"] = success
            if success and self.current_task:
                self.session_tracker.complete_task(self.current_task)
            elif not success and self.current_task:
                self.session_tracker.fail_task(self.current_task, "Session failed")
        self.current_task = None

    def cleanup_resources(self) -> None:
        """Execute registered cleanup handlers and release tracked resources."""
        for handler in self.cleanup_handlers.copy():
            try:
                handler()
            except Exception as exc:  # pragma: no cover - defensive
                self.console.print(
                    f"[red]Cleanup handler error:[/ red] {type(exc).__name__}: {exc}",
                )

        with suppress(Exception):
            self._cleanup_temporary_files()
        with suppress(Exception):
            self._cleanup_debug_logs()
        with suppress(Exception):
            self._cleanup_coverage_files()
        with suppress(Exception):
            self._cleanup_pycache_directories()

        for lock_path in list(self.lock_files):
            with suppress(OSError):
                if lock_path.exists():
                    lock_path.unlink()
            self.lock_files.discard(lock_path)

    def register_cleanup(self, handler: t.Callable[[], None]) -> None:
        """Register cleanup handler to execute when session completes."""
        self.cleanup_handlers.append(handler)

    def track_lock_file(self, path: Path) -> None:
        """Track lock file for cleanup."""
        self.lock_files.add(path)

    def set_cleanup_config(self, config: t.Any) -> None:
        """Set cleanup configuration used by cleanup helpers."""
        self._cleanup_config = config

    def _cleanup_temporary_files(self) -> None:
        pass

    def _cleanup_debug_logs(self) -> None:
        pass

    def _cleanup_coverage_files(self) -> None:
        pass

    def _cleanup_pycache_directories(self) -> None:
        pass

    def _setup_logging(self, options: OptionsProtocol) -> None:
        pass

    def _setup_websocket_progress_file(self) -> None:
        pass

    def _initialize_quality_service(self) -> None:
        pass

    def update_stage(self, stage: str, status: str) -> None:
        """Update stage status and write progress if applicable."""
        self._update_websocket_progress(stage, status)

    def _update_websocket_progress(self, stage: str, status: str) -> None:
        pass


class SessionController:
    """Coordinates session setup for the workflow pipeline."""

    def __init__(self, pipeline: WorkflowPipeline) -> None:
        self._pipeline = pipeline

    def initialize(self, options: OptionsProtocol) -> None:
        """Initialize session state and ancillary services."""
        pipeline = self._pipeline
        pipeline.session.initialize_session_tracking(options)
        pipeline._configure_session_cleanup(options)
        pipeline._initialize_zuban_lsp(options)
        pipeline._configure_hook_manager_lsp(options)
        pipeline._register_lsp_cleanup_handler(options)
        pipeline._log_workflow_startup_info(options)
