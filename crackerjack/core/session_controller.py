"""Helpers for coordinating workflow session initialization."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.models.protocols import OptionsProtocol

    from .workflow_orchestrator import WorkflowPipeline


class SessionController:
    """Encapsulates workflow session bootstrap tasks."""

    def __init__(self, pipeline: WorkflowPipeline) -> None:
        self._pipeline = pipeline

    def initialize(self, options: OptionsProtocol) -> None:
        """Initialize workflow session and supporting services."""
        pipeline = self._pipeline
        pipeline.session.initialize_session_tracking(options)
        pipeline.session.track_task("workflow", "Complete crackerjack workflow")

        pipeline._log_workflow_startup_debug(options)
        pipeline._configure_session_cleanup(options)
        pipeline._initialize_zuban_lsp(options)
        pipeline._configure_hook_manager_lsp(options)
        pipeline._register_lsp_cleanup_handler(options)
        pipeline._log_workflow_startup_info(options)
