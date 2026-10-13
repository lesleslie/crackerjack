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
from crackerjack.models.protocols import ConsoleInterface
from crackerjack.runtime.oneiric_workflow import (
    OneiricWorkflowRuntime,
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
        runtime = build_oneiric_runtime()
        # Clear stale checkpoint before each run so completed phases re-execute
        # rather than being silently skipped (the "ratchet"). The previous
        # implementation targeted a hard-coded path that oneiric never read;
        # this delegates to oneiric's own WorkflowCheckpointStore so we wipe
        # the same database the workflow engine actually consults.
        self._clear_oneiric_cache(runtime)
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

        success = _workflow_result_success(result)
        self.session.finalize_session(self.session.start_time, success=success)
        return success

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

    def _clear_oneiric_cache(self, runtime: OneiricWorkflowRuntime) -> None:
        # UPSTREAM GAP: oneiric's WorkflowBridge exposes no public
        # ``clear_checkpoint`` (or equivalent) method on the bridge itself.
        # Its public surface is ``__init__``, ``update_settings``,
        # ``refresh_dags``, ``dag_specs``, ``execute_dag``,
        # ``enqueue_workflow``; the only ``_checkpoint_store.clear(...)``
        # call sits inside the private ``_execute_with_checkpoint`` at
        # oneiric/domains/workflows.py:244. Reaching the private
        # ``_checkpoint_store`` attribute is the only external seam
        # available to wipe a workflow key by name. TODO(upstream): add
        # ``WorkflowBridge.clear_checkpoint(workflow_key)`` to oneiric and
        # call that here instead.
        #
        # We delegate to oneiric's WorkflowCheckpointStore.clear so we wipe
        # the same database the workflow engine reads. The bridge's
        # ``_checkpoint_store`` is the canonical store wired up in
        # ``RuntimeOrchestrator.__init__``; if it is None the orchestrator
        # is running with checkpointing disabled and there is nothing to
        # clear.
        checkpoint_store = runtime.workflow_bridge._checkpoint_store
        if checkpoint_store is None:
            return
        try:
            checkpoint_store.clear("crackerjack")
            self.logger.debug(
                "Cleared Oneiric checkpoint cache for crackerjack workflow",
            )
        except Exception as exc:
            self.logger.warning(f"Failed to clear Oneiric cache: {exc}")

    def _run_fast_hooks_phase(self, options: t.Any) -> bool:
        return self.phases.run_fast_hooks_only(options)  # type: ignore

    def _configure_session_cleanup(self, options: t.Any) -> None:
        pass

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
