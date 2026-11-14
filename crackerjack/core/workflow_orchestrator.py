from __future__ import annotations

import asyncio
import logging
import typing as t
from dataclasses import dataclass
from pathlib import Path

from crackerjack.config import CrackerjackSettings, load_settings
from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.eventbridge_resolver import resolve_event_publisher
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.config import CleanupConfig
from crackerjack.models.protocols import ConsoleInterface
from crackerjack.runtime.oneiric_workflow import (
    build_oneiric_runtime,
    register_crackerjack_workflow,
)


@dataclass
class WorkflowResult:
    success: bool
    details: dict[str, t.Any]


class WorkflowPipeline:
    def __init__(
        self,
        *,
        console: ConsoleInterface | None = None,
        pkg_path: Path | None = None,
        settings: CrackerjackSettings | None = None,
        session: SessionCoordinator | None = None,
        phases: PhaseCoordinator | None = None,
        logger: logging.Logger | None = None,
        enable_hooks: list[str] | None = None,
        bridge_resolver: t.Callable[[t.Any, t.Any], t.Any | None] | None = None,
    ) -> None:
        self.console = console or CrackerjackConsole()
        self.pkg_path = pkg_path or Path.cwd()
        self.settings = settings or load_settings(CrackerjackSettings)
        self.logger = logger or logging.getLogger(__name__)

        self.session = session or SessionCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
        )
        self.phases = phases or PhaseCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            settings=self.settings,
            enable_hooks=enable_hooks,
        )

        self._bridge_resolver = bridge_resolver

    async def run_complete_workflow(self, options: t.Any) -> bool:
        self._initialize_workflow_session(options)
        self._configure_session_cleanup(options)
        runtime = build_oneiric_runtime()
        # The orchestrator is built with enable_workflow_checkpoints=False
        # (see build_oneiric_runtime), so there is no persistent task
        # state to invalidate at run start. Every run re-executes every
        # phase from a known-fresh state.
        self._wire_event_publisher(runtime)
        register_crackerjack_workflow(
            runtime,
            phases=self.phases,
            options=_adapt_options(options),
        )

        try:
            result = await runtime.workflow_bridge.execute_dag(
                "crackerjack",
                context={"pkg_path": str(self.pkg_path)},
            )
        except Exception as exc:
            if self.settings.execution.verbose:
                self.logger.exception(
                    "Workflow failed: %s", exc, extra={"error": str(exc)}
                )
            else:
                self.logger.error("Workflow failed: %s", str(exc))
            self.session.finalize_session(self.session.start_time, success=False)
            return False
        else:
            success = _workflow_result_success(result)
            self.session.finalize_session(self.session.start_time, success=success)
            return success
        finally:
            self._cleanup_session_artifacts()

    def _wire_event_publisher(self, runtime: t.Any) -> None:
        if self._bridge_resolver is None:
            return
        try:
            bridge = self._bridge_resolver(self.settings, runtime)
        except Exception as exc:
            self.logger.warning(
                "bridge_resolver raised %s; skipping EventBridge wiring",
                exc,
            )
            return
        publisher = resolve_event_publisher(self.settings, bridge=bridge)
        if publisher is not None:
            self.phases.set_event_publisher(publisher)

    def run_complete_workflow_sync(self, options: t.Any) -> bool:
        return asyncio.run(self.run_complete_workflow(options))

    def execute_workflow(self, options: t.Any) -> bool:
        return self.run_complete_workflow_sync(options)

    def _initialize_workflow_session(self, options: t.Any) -> None:
        self.session.initialize_session_tracking(options)

    def _run_fast_hooks_phase(self, options: t.Any) -> bool:
        return self.phases.run_fast_hooks_only(options)  # ty: ignore[invalid-explicit-return]

    def _configure_session_cleanup(self, options: t.Any) -> None:
        """Hand the session its artifact-cleanup policy.

        ``CleanupSettings`` carries the policy — whether to clean at all,
        and how many of the newest coverage shards and debug logs to keep.
        The session needs it as a ``CleanupConfig`` before the workflow
        runs, because the teardown in :meth:`run_complete_workflow` reads
        it when it prunes.

        This was a stub that nothing called, so the session never
        received a cleanup policy at all. It is now called on every run
        and takes the configured policy.
        """
        cleanup_settings = getattr(self.settings, "cleanup", None)
        if cleanup_settings is None:
            return
        self.session.set_cleanup_config(CleanupConfig.from_settings(cleanup_settings))

    def _cleanup_session_artifacts(self) -> None:
        """Prune the session's stale artifacts once the workflow is done.

        Runs on every exit path — success, failure, and cancellation — so
        a crashed run does not leave the next one to clean up after it.

        The workflow's verdict is already decided by the time this runs,
        so a cleanup failure is logged and swallowed rather than allowed
        to change the outcome.
        """
        try:
            self.session.cleanup_resources()
        except Exception as exc:
            self.logger.debug("Session artifact cleanup failed: %s", exc)

    def _configure_hook_manager_lsp(self, options: t.Any) -> None:
        pass

    def _register_lsp_cleanup_handler(self, options: t.Any) -> None:
        pass

    def _log_workflow_startup_info(self, options: t.Any) -> None:
        pass

    async def run_fast_hooks_only(self, options: t.Any) -> bool:
        return await self.phases.run_fast_hooks_only(options)

    async def run_comprehensive_hooks_only(self, options: t.Any) -> bool:
        return await self.phases.run_comprehensive_hooks_only(options)

    def run_testing_phase(self, options: t.Any) -> bool:
        method = self.phases.run_testing_phase
        result = method(options)
        return t.cast(bool, result)

    def run_cleaning_phase(self, options: t.Any) -> bool:
        method = self.phases.run_cleaning_phase
        result = method(options)
        return t.cast(bool, result)


def _workflow_result_success(result: dict[str, t.Any]) -> bool:
    results = result.get("results") if isinstance(result, dict) else None
    if not results:
        return True
    return all(value is not False for value in results.values())


def _adapt_options(options: t.Any) -> t.Any:
    return options
