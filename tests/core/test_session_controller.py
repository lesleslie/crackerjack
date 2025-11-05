from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from crackerjack.core.session_coordinator import SessionController


@dataclass
class _FakeSession:
    initialized: bool = False
    tracked_tasks: list[tuple[str, str]] = field(default_factory=list)

    def initialize_session_tracking(self, options: Any) -> None:
        self.initialized = True

    def track_task(self, group: str, description: str) -> None:
        self.tracked_tasks.append((group, description))


class _FakePipeline:
    def __init__(self) -> None:
        self.session = _FakeSession()
        self.calls: list[str] = []

    def _log_workflow_startup_debug(self, options: Any) -> None:
        self.calls.append("debug")

    def _configure_session_cleanup(self, options: Any) -> None:
        self.calls.append("cleanup")

    def _initialize_zuban_lsp(self, options: Any) -> None:
        self.calls.append("zuban")

    def _configure_hook_manager_lsp(self, options: Any) -> None:
        self.calls.append("hook_manager")

    def _register_lsp_cleanup_handler(self, options: Any) -> None:
        self.calls.append("register_cleanup")

    def _log_workflow_startup_info(self, options: Any) -> None:
        self.calls.append("info")


class _Options:
    pass


@pytest.mark.asyncio
async def test_session_controller_initializes_pipeline_components() -> None:
    pipeline = _FakePipeline()
    controller = SessionController(pipeline)
    opts = _Options()

    controller.initialize(opts)

    assert pipeline.session.initialized is True
    # In the current model, high-level session bookkeeping is handled by
    # SessionTracker; no explicit 'workflow' task is tracked here.
    assert pipeline.calls == [
        "cleanup",
        "zuban",
        "hook_manager",
        "register_cleanup",
        "info",
    ]
