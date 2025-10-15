from __future__ import annotations

import time
import typing as t
import uuid
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.models.task import SessionTracker

if t.TYPE_CHECKING:
    from crackerjack.core.workflow_orchestrator import WorkflowPipeline
    from crackerjack.models.protocols import OptionsProtocol


class SessionCoordinator:
    """Lightweight session tracking and cleanup coordinator."""

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        pkg_path: Path,
        web_job_id: str | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.web_job_id = web_job_id
        self.session_id = web_job_id or uuid.uuid4().hex[:8]
        self.start_time = time.time()
        self.cleanup_config: t.Any = None
        self.cleanup_handlers: list[t.Callable[[], None]] = []
        self.lock_files: set[Path] = set()
        self.current_task: str | None = None

        self.session_tracker = SessionTracker(
            session_id=self.session_id,
            start_time=self.start_time,
        )
        self.tasks = self.session_tracker.tasks

    def initialize_session_tracking(self, options: OptionsProtocol) -> None:
        """Initialize session metadata and baseline tracking."""
        self.session_tracker.metadata.update(
            {
                "options": getattr(options, "__dict__", {}),
                "pkg_path": str(self.pkg_path),
                "initialized_at": time.time(),
            },
        )
        self.start_session("workflow")

    def start_session(self, task_name: str) -> None:
        """Record the start of a high-level session task."""
        self.current_task = task_name
        self.session_tracker.metadata["current_session"] = task_name

    def end_session(self, success: bool) -> None:
        """Mark session completion."""
        self.session_tracker.metadata["completed_at"] = time.time()
        self.session_tracker.metadata["success"] = success
        self.current_task = None

    def track_task(
        self,
        task_id: str,
        task_name: str,
        details: str | None = None,
    ) -> str:
        """Track a task within the session."""
        self.session_tracker.start_task(task_id, task_name, details)
        return task_id

    def complete_task(
        self,
        task_id: str,
        details: str | None = None,
        files_changed: list[str] | None = None,
    ) -> None:
        """Mark task as completed."""
        self.session_tracker.complete_task(task_id, details, files_changed)

    def fail_task(
        self,
        task_id: str,
        error_message: str,
        details: str | None = None,
    ) -> None:
        """Mark task as failed."""
        self.session_tracker.fail_task(task_id, error_message, details)

    def finalize_session(self, start_time: float, success: bool) -> None:
        """Finalize session bookkeeping."""
        duration = time.time() - start_time
        self.session_tracker.metadata["duration"] = duration
        self.session_tracker.metadata["success"] = success
        if success and self.current_task:
            self.session_tracker.complete_task(self.current_task)
        elif not success and self.current_task:
            self.session_tracker.fail_task(self.current_task, "Session failed")
        self.current_task = None

    def cleanup_resources(self) -> None:
        """Execute registered cleanup handlers and release tracked resources."""
        for handler in list(self.cleanup_handlers):
            try:
                handler()
            except Exception as exc:  # pragma: no cover - defensive
                self.console.print(
                    f"[red]Cleanup handler error:[/ red] {type(exc).__name__}: {exc}",
                )

        for lock_path in list(self.lock_files):
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except OSError:
                pass
            finally:
                self.lock_files.discard(lock_path)

    def register_cleanup(self, handler: t.Callable[[], None]) -> None:
        """Register cleanup handler to execute when session completes."""
        self.cleanup_handlers.append(handler)

    def track_lock_file(self, path: Path) -> None:
        """Track lock file for cleanup."""
        self.lock_files.add(path)

    def set_cleanup_config(self, config: t.Any) -> None:
        """Store cleanup configuration from options."""
        self.cleanup_config = config

    def get_session_summary(self) -> dict[str, t.Any]:
        """Return high-level session summary."""
        return self.session_tracker.get_summary()

    def get_summary(self) -> dict[str, t.Any]:
        """Alias for get_session_summary."""
        return self.get_session_summary()


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
