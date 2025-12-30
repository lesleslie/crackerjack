from __future__ import annotations

import asyncio
import logging
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.timeout_manager import AsyncTimeoutManager
from crackerjack.core.workflow_orchestrator import WorkflowPipeline


class AsyncWorkflowPipeline:
    """Async workflow pipeline wrapper using Oneiric-backed workflow pipeline."""

    def __init__(
        self,
        logger: logging.Logger | t.Any,
        console: Console,
        pkg_path: Path,
        session: SessionCoordinator,
        phases: PhaseCoordinator,
    ) -> None:
        self.logger = logger
        self.console = console
        self.pkg_path = pkg_path
        self.session = session
        self.phases = phases
        self.timeout_manager = AsyncTimeoutManager()
        self._pipeline = WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            session=session,
            phases=phases,
        )

    async def run_complete_workflow_async(self, options: t.Any) -> bool:
        return await self._pipeline.run_complete_workflow(options)


def run_complete_workflow_async(*args: t.Any, **kwargs: t.Any) -> t.Any:
    async def _runner() -> t.Any:
        pipeline = WorkflowPipeline()
        return await pipeline.run_complete_workflow(*args, **kwargs)

    return asyncio.run(_runner())
