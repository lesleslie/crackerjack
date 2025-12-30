from __future__ import annotations

import inspect
import typing as t
from dataclasses import dataclass

from oneiric.core.config import OneiricSettings, resolver_settings_from_config
from oneiric.core.lifecycle import LifecycleManager
from oneiric.core.resolution import Candidate, Resolver
from oneiric.runtime.orchestrator import RuntimeOrchestrator

if t.TYPE_CHECKING:
    from crackerjack.core.phase_coordinator import PhaseCoordinator


@dataclass(frozen=True)
class OneiricWorkflowRuntime:
    resolver: Resolver
    lifecycle: LifecycleManager
    orchestrator: RuntimeOrchestrator

    @property
    def workflow_bridge(self):
        return self.orchestrator.workflow_bridge

    @property
    def task_bridge(self):
        return self.orchestrator.task_bridge


class _PhaseTask:
    def __init__(self, name: str, runner: t.Callable[[], t.Any]) -> None:
        self._name = name
        self._runner = runner

    async def run(self, payload: dict[str, t.Any] | None = None) -> t.Any:
        result = self._runner()
        if inspect.isawaitable(result):
            result = await result
        if result is False:
            raise RuntimeError(f"workflow-task-failed: {self._name}")
        return result


def build_oneiric_runtime() -> OneiricWorkflowRuntime:
    oneiric_settings = OneiricSettings()
    oneiric_settings.app.name = "crackerjack"
    oneiric_settings.profile.watchers_enabled = False
    oneiric_settings.profile.remote_enabled = False
    oneiric_settings.remote.enabled = False

    # Configure logging to suppress event logs in non-debug mode
    import os

    debug_mode = os.environ.get("CRACKERJACK_DEBUG") == "1"

    if not debug_mode:
        # Disable JSON event logging for clean output in production mode
        oneiric_settings.logging.emit_json = False
        oneiric_settings.logging.level = "WARNING"
    else:
        # Enable full debug logging in debug mode
        oneiric_settings.logging.emit_json = True
        oneiric_settings.logging.level = "DEBUG"
    oneiric_settings.remote.refresh_interval = None

    # Suppress verbose event logging for cleaner TUI output unless in debug mode
    oneiric_settings.logging.level = "WARNING" if not debug_mode else "DEBUG"
    oneiric_settings.logging.emit_json = debug_mode  # Only emit JSON in debug mode

    # Set the debug flag in the app settings to control event logging
    oneiric_settings.app.debug = debug_mode

    # Configure Oneiric logging with the debug setting
    from oneiric.core.logging import configure_logging

    # Configure logging based on debug mode
    configure_logging(oneiric_settings.logging)

    resolver = Resolver(settings=resolver_settings_from_config(oneiric_settings))
    lifecycle = LifecycleManager(resolver)
    orchestrator = RuntimeOrchestrator(
        oneiric_settings,
        resolver,
        lifecycle,
        secrets=_build_secrets_hook(oneiric_settings, lifecycle),
        health_path=None,
    )
    return OneiricWorkflowRuntime(
        resolver=resolver,
        lifecycle=lifecycle,
        orchestrator=orchestrator,
    )


def _build_secrets_hook(
    oneiric_settings: OneiricSettings, lifecycle: LifecycleManager
) -> t.Any:
    from oneiric.core.config import SecretsHook

    return SecretsHook(lifecycle, oneiric_settings.secrets)


def register_crackerjack_workflow(
    runtime: OneiricWorkflowRuntime,
    *,
    phases: PhaseCoordinator,
    options: t.Any,
) -> None:
    _register_tasks(runtime, phases, options)
    _register_workflow(runtime, options)
    runtime.workflow_bridge.refresh_dags()


def _register_tasks(
    runtime: OneiricWorkflowRuntime,
    phases: PhaseCoordinator,
    options: t.Any,
) -> None:
    task_factories = {
        "configuration": lambda: _PhaseTask(
            "configuration", lambda: phases.run_configuration_phase(options)
        ),
        "cleaning": lambda: _PhaseTask(
            "cleaning", lambda: phases.run_cleaning_phase(options)
        ),
        "fast_hooks": lambda: _PhaseTask(
            "fast_hooks", lambda: phases.run_fast_hooks_only(options)
        ),
        "tests": lambda: _PhaseTask("tests", lambda: phases.run_testing_phase(options)),
        "comprehensive_hooks": lambda: _PhaseTask(
            "comprehensive_hooks", lambda: phases.run_comprehensive_hooks_only(options)
        ),
        "publishing": lambda: _PhaseTask(
            "publishing", lambda: phases.run_publishing_phase(options)
        ),
        "commit": lambda: _PhaseTask(
            "commit", lambda: phases.run_commit_phase(options)
        ),
    }

    for key, factory in task_factories.items():
        runtime.resolver.register(
            Candidate(
                domain="task",
                key=key,
                provider="crackerjack",
                factory=factory,
                metadata={"package": "crackerjack"},
            )
        )


def _register_workflow(runtime: OneiricWorkflowRuntime, options: t.Any) -> None:
    dag_nodes = _build_dag_nodes(options)
    runtime.resolver.register(
        Candidate(
            domain="workflow",
            key="crackerjack",
            provider="crackerjack",
            factory=object,
            metadata={"dag": {"nodes": dag_nodes}},
        )
    )


def _build_dag_nodes(options: t.Any) -> list[dict[str, t.Any]]:
    steps: list[str] = []

    if not getattr(options, "no_config_updates", False):
        steps.append("configuration")

    if _should_clean(options):
        steps.append("cleaning")

    if _should_run_fast_hooks(options):
        steps.append("fast_hooks")

    if _should_run_tests(options):
        steps.append("tests")

    # Add comprehensive hooks BEFORE publishing and commit
    if _should_run_comprehensive_hooks(options):
        steps.append("comprehensive_hooks")

    # Publishing and commit come after all quality checks
    steps.extend(("publishing", "commit"))

    nodes: list[dict[str, t.Any]] = []
    previous: str | None = None
    for step in steps:
        node = {"id": step, "task": step}
        if previous:
            node["depends_on"] = [previous]
        nodes.append(node)
        previous = step

    return nodes


def _should_clean(options: t.Any) -> bool:
    return bool(
        getattr(options, "strip_code", False) or getattr(options, "clean", False)
    )


def _should_run_tests(options: t.Any) -> bool:
    return bool(getattr(options, "run_tests", False) or getattr(options, "test", False))


def _should_run_fast_hooks(options: t.Any) -> bool:
    if getattr(options, "skip_hooks", False):
        return False
    if getattr(options, "comp", False):
        return False
    return True


def _should_run_comprehensive_hooks(options: t.Any) -> bool:
    if getattr(options, "skip_hooks", False):
        return False
    if getattr(options, "fast", False):
        return False
    if getattr(options, "fast_iteration", False):
        return False
    return True
