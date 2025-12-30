from __future__ import annotations

import asyncio
import logging
import typing as t
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from crackerjack.config import CrackerjackSettings, load_settings
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.runtime.oneiric_workflow import (
    build_oneiric_runtime,
    register_crackerjack_workflow,
)


@dataclass
class WorkflowResult:
    success: bool
    details: dict[str, t.Any]


class WorkflowPipeline:
    """Oneiric-backed workflow pipeline for Crackerjack."""

    def __init__(
        self,
        *,
        console: Console | None = None,
        pkg_path: Path | None = None,
        settings: CrackerjackSettings | None = None,
        session: SessionCoordinator | None = None,
        phases: PhaseCoordinator | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()
        self.settings = settings or load_settings(CrackerjackSettings)
        self.logger = logger or logging.getLogger(__name__)

        self.session = session or SessionCoordinator(
            console=self.console, pkg_path=self.pkg_path
        )
        self.phases = phases or PhaseCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            settings=self.settings,
        )

    async def run_complete_workflow(self, options: t.Any) -> bool:
        self._initialize_workflow_session(options)
        self._clear_oneiric_cache()  # Clear checkpoint cache to ensure fresh execution
        runtime = build_oneiric_runtime()
        register_crackerjack_workflow(
            runtime,
            phases=self.phases,
            options=_adapt_options(options),
        )

        try:
            result = await runtime.workflow_bridge.execute_dag(
                "crackerjack", context={"pkg_path": str(self.pkg_path)}
            )
        except Exception as exc:
            self.logger.exception("workflow-failed", extra={"error": str(exc)})
            self.session.finalize_session(self.session.start_time, success=False)
            return False
        except Exception as exc:
            self.logger.exception("workflow-failed", extra={"error": str(exc)})
            self.session.finalize_session(self.session.start_time, success=False)
            return False

        success = _workflow_result_success(result)
        self.session.finalize_session(self.session.start_time, success=success)
        return success

    def run_complete_workflow_sync(self, options: t.Any) -> bool:
        return asyncio.run(self.run_complete_workflow(options))

    def execute_workflow(self, options: t.Any) -> bool:
        return self.run_complete_workflow_sync(options)

    def _initialize_workflow_session(self, options: t.Any) -> None:
        self.session.initialize_session_tracking(options)

    def _clear_oneiric_cache(self) -> None:
        """Clear Oneiric checkpoint cache to ensure fresh workflow execution.

        Oneiric caches workflow execution state in .oneiric_cache/workflow_checkpoints.sqlite,
        which can cause tasks to be skipped on subsequent runs. For Crackerjack's quality
        checks, we need to ensure all hooks run fresh every time.
        """
        import sqlite3

        cache_db = self.pkg_path / ".oneiric_cache" / "workflow_checkpoints.sqlite"
        if not cache_db.exists():
            return

        try:
            conn = sqlite3.connect(cache_db)
            cursor = conn.cursor()

            # Clear all checkpoint data for crackerjack workflow
            cursor.execute(
                "DELETE FROM workflow_checkpoints WHERE workflow_key = ?",
                ("crackerjack",),
            )
            cursor.execute(
                "DELETE FROM workflow_executions WHERE workflow_key = ?",
                ("crackerjack",),
            )
            cursor.execute(
                "DELETE FROM workflow_execution_nodes WHERE run_id IN (SELECT run_id FROM workflow_executions WHERE workflow_key = ?)",
                ("crackerjack",),
            )

            conn.commit()
            conn.close()
            self.logger.debug(
                "Cleared Oneiric checkpoint cache for crackerjack workflow"
            )
        except Exception as e:
            # Log but don't fail if cache clearing fails
            self.logger.warning(f"Failed to clear Oneiric cache: {e}")

    def _run_fast_hooks_phase(self, options: t.Any) -> bool:
        if not self.phases.run_fast_hooks_only(options):
            return False
        return True


def _workflow_result_success(result: dict[str, t.Any]) -> bool:
    results = result.get("results") if isinstance(result, dict) else None
    if not results:
        return True
    return all(value is not False for value in results.values())


def _adapt_options(options: t.Any) -> t.Any:
    # Return options as-is since semantic attributes (strip_code, run_tests) are already available
    return options
