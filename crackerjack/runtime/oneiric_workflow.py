from __future__ import annotations

import inspect
import logging
import tempfile
import typing as t
from dataclasses import dataclass
from pathlib import Path

from oneiric.core.config import OneiricSettings, resolver_settings_from_config
from oneiric.core.lifecycle import LifecycleManager
from oneiric.core.resolution import Candidate, Resolver
from oneiric.runtime.orchestrator import RuntimeOrchestrator

if t.TYPE_CHECKING:
    from crackerjack.core.phase_coordinator import PhaseCoordinator

_logger = logging.getLogger(__name__)


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
    """Adapter that runs a crackerjack phase method inside a oneiric workflow task.

    The phase method returns ``True`` on success, ``False`` on recoverable
    failure (where the underlying error has already been recorded via
    ``PhaseCoordinator.session.fail_task``). This adapter translates both
    signals into something the orchestrator can act on:

    - **Runner raises**: the exception class and message are included in the
      raised :class:`RuntimeError` so the user sees *why* the task failed,
      not just its name.
    - **Runner returns False**: the task's recorded ``error_message`` (and, in
      verbose mode, its ``details``) is included in the raised
      :class:`RuntimeError`. Without this, a user sees only
      ``workflow-task-failed: documentation_cleanup`` even when the actual
      cause is captured in the session.

    The optional ``error_provider`` callback is wired in
    :func:`_register_tasks` so a task can reach back into the live session
    tracker for the most recent failure context. ``verbose`` controls
    whether the multi-line ``details`` block is also surfaced (when it
    contains a list of every failing file/line, that is what verbose mode
    is for).
    """

    def __init__(
        self,
        name: str,
        runner: t.Callable[[], t.Any],
        *,
        verbose: bool = False,
        error_provider: t.Callable[[], tuple[str | None, str | None]] | None = None,
    ) -> None:
        self._name = name
        self._runner = runner
        self._verbose = verbose
        self._error_provider = error_provider

    async def run(self, payload: dict[str, t.Any] | None = None) -> t.Any:
        try:
            result = self._runner()
        except Exception as exc:
            _logger.exception("Phase task %s raised", self._name)
            msg = f"workflow-task-failed: {self._name}: {type(exc).__name__}: {exc}"
            raise RuntimeError(msg) from exc

        if inspect.isawaitable(result):
            result = await result

        if result is False:
            error_message, details = self._load_failure_context()
            msg = f"workflow-task-failed: {self._name}"
            if error_message:
                msg = f"{msg}: {error_message}"
            if self._verbose and details:
                # details can be a multi-line breakdown (file/line/code per
                # line for frontmatter errors, or a traceback when the phase
                # surfaced an unhandled exception). Print to stderr so it
                # lands on the user's console even when the orchestrator
                # captures stdout.
                import sys

                sys.stderr.write(
                    f"\n[verbose] {self._name} failure details:\n{details}\n"
                )
                sys.stderr.flush()
            raise RuntimeError(msg)

        return result

    def _load_failure_context(self) -> tuple[str | None, str | None]:
        if self._error_provider is None:
            return None, None
        try:
            return self._error_provider()
        except Exception:
            _logger.exception(
                "Phase task %s error_provider raised; falling back to bare name",
                self._name,
            )
            return None, None


def build_oneiric_runtime() -> OneiricWorkflowRuntime:
    oneiric_settings = OneiricSettings()
    oneiric_settings.app.name = "crackerjack"
    oneiric_settings.profile.watchers_enabled = False
    oneiric_settings.profile.remote_enabled = False
    oneiric_settings.remote.enabled = False
    oneiric_settings.runtime_paths.workflow_checkpoints_path = str(
        _resolve_workflow_checkpoints_path()
    )

    import os

    debug_mode = os.environ.get("CRACKERJACK_DEBUG") == "1"

    if not debug_mode:
        oneiric_settings.logging.emit_json = False
        oneiric_settings.logging.level = "WARNING"
    else:
        oneiric_settings.logging.emit_json = True
        oneiric_settings.logging.level = "DEBUG"
    oneiric_settings.remote.refresh_interval = None

    oneiric_settings.logging.level = "WARNING" if not debug_mode else "DEBUG"
    oneiric_settings.logging.emit_json = debug_mode

    oneiric_settings.app.debug = debug_mode

    from oneiric.core.logging import configure_logging

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


def _resolve_workflow_checkpoints_path() -> Path:
    candidates = [
        Path.cwd() / ".crackerjack" / "oneiric_cache" / "workflow_checkpoints.sqlite",
        Path(tempfile.gettempdir())
        / "crackerjack"
        / "oneiric_cache"
        / "workflow_checkpoints.sqlite",
    ]

    for candidate in candidates:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue

    return candidates[-1]


def _build_secrets_hook(
    oneiric_settings: OneiricSettings,
    lifecycle: LifecycleManager,
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
    verbose = bool(getattr(options, "verbose", False))

    def _make_error_provider(
        task_name: str,
    ) -> t.Callable[[], tuple[str | None, str | None]]:
        def _provider() -> tuple[str | None, str | None]:
            session_coordinator = getattr(phases, "session", None)
            session_tracker = getattr(session_coordinator, "session_tracker", None)
            if session_tracker is None:
                return None, None
            task = session_tracker.tasks.get(task_name)
            if task is None:
                return None, None
            return task.error_message, task.details

        return _provider

    task_factories = {
        "config_cleanup": lambda: _PhaseTask(
            "config_cleanup",
            lambda: phases.run_config_cleanup_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("config_cleanup"),
        ),
        "configuration": lambda: _PhaseTask(
            "configuration",
            lambda: phases.run_configuration_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("configuration"),
        ),
        "cleaning": lambda: _PhaseTask(
            "cleaning",
            lambda: phases.run_cleaning_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("cleaning"),
        ),
        "fast_hooks": lambda: _PhaseTask(
            "fast_hooks",
            lambda: phases.run_fast_hooks_only(options),  # type: ignore[unused-coroutine]
            verbose=verbose,
            error_provider=_make_error_provider("fast_hooks"),
        ),
        "tests": lambda: _PhaseTask(
            "tests",
            lambda: phases.run_testing_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("tests"),
        ),
        "documentation_cleanup": lambda: _PhaseTask(
            "documentation_cleanup",
            lambda: phases.run_documentation_cleanup_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("documentation_cleanup"),
        ),
        "git_cleanup": lambda: _PhaseTask(
            "git_cleanup",
            lambda: phases.run_git_cleanup_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("git_cleanup"),
        ),
        "doc_updates": lambda: _PhaseTask(
            "doc_updates",
            lambda: phases.run_doc_update_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("doc_updates"),
        ),
        "snob_tests": lambda: _PhaseTask(
            "snob_tests",
            lambda: phases.run_snob_tests_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("snob_tests"),
        ),
        "comprehensive_hooks": lambda: _PhaseTask(
            "comprehensive_hooks",
            lambda: phases.run_comprehensive_hooks_only(options),
            verbose=verbose,
            error_provider=_make_error_provider("comprehensive_hooks"),
        ),
        "coverage_ratchet": lambda: _PhaseTask(
            "coverage_ratchet",
            lambda: phases.run_coverage_ratchet_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("coverage_ratchet"),
        ),
        "publishing": lambda: _PhaseTask(
            "publishing",
            lambda: phases.run_publishing_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("publishing"),
        ),
        "commit": lambda: _PhaseTask(
            "commit",
            lambda: phases.run_commit_phase(options),
            verbose=verbose,
            error_provider=_make_error_provider("commit"),
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
            ),
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
        ),
    )


def _build_dag_nodes(options: t.Any) -> list[dict[str, t.Any]]:
    steps = _build_workflow_steps(options)
    enable_parallel = getattr(options, "enable_parallel_phases", False)
    return _build_nodes_with_dependencies(steps, enable_parallel)


def _build_workflow_steps(options: t.Any) -> list[str]:
    steps: list[str] = []

    if _should_run_config_cleanup(options):
        steps.append("config_cleanup")

    if not getattr(options, "no_config_updates", False):
        steps.append("configuration")

    if _should_clean(options):
        steps.append("cleaning")

    if _should_run_documentation_cleanup(options):
        steps.append("documentation_cleanup")

    if _should_run_fast_hooks(options):
        steps.append("fast_hooks")

    if _should_run_fast_hooks(options) and not getattr(options, "no_snob", False):
        steps.append("snob_tests")

    if _should_run_tests(options) and _should_run_comprehensive_hooks(options):
        enable_parallel = getattr(options, "enable_parallel_phases", False)
        if enable_parallel:
            steps.extend(("tests", "comprehensive_hooks"))
        else:
            steps.extend(("tests", "comprehensive_hooks"))
    elif _should_run_tests(options):
        steps.append("tests")
    elif _should_run_comprehensive_hooks(options):
        steps.append("comprehensive_hooks")

    if _should_run_coverage_ratchet(options):
        steps.append("coverage_ratchet")

    if _should_run_git_cleanup(options):
        steps.append("git_cleanup")

    if _should_run_doc_updates(options):
        steps.append("doc_updates")

    steps.extend(("publishing", "commit"))
    return steps


def _build_nodes_with_dependencies(
    steps: list[str], enable_parallel: bool
) -> list[dict[str, t.Any]]:
    nodes: list[dict[str, t.Any]] = []
    previous: str | None = None
    parallel_start_index: int | None = None
    parallel_predecessor: str | None = None

    for idx, step in enumerate(steps):
        node: dict[str, t.Any] = {"id": step, "task": step}

        if enable_parallel:
            node = _handle_parallel_step(
                node, step, previous, parallel_start_index, parallel_predecessor
            )

            if step in ("tests", "comprehensive_hooks"):
                if parallel_start_index is None:
                    parallel_start_index = idx
                    parallel_predecessor = previous
            else:
                parallel_start_index = None
                parallel_predecessor = None
        else:
            if previous:
                node["depends_on"] = [previous]

        nodes.append(node)
        previous = step

    return nodes


def _handle_parallel_step(
    node: dict[str, t.Any],
    step: str,
    previous: str | None,
    parallel_start_index: int | None,
    parallel_predecessor: str | None,
) -> dict[str, t.Any]:
    if step in ("tests", "comprehensive_hooks"):
        if parallel_start_index is None:
            if previous:
                node["depends_on"] = [previous]
        elif parallel_predecessor is not None:
            node["depends_on"] = [parallel_predecessor]
    else:
        if previous:
            node["depends_on"] = [previous]

    return node


def _should_clean(options: t.Any) -> bool:
    return bool(
        getattr(options, "strip_code", False) or getattr(options, "clean", False),
    )


def _should_run_config_cleanup(_options: t.Any) -> bool:
    # TODO: Revert this temporary fix after config_cleanup debugging
    return False


def _should_run_tests(options: t.Any) -> bool:
    return bool(
        getattr(options, "run_tests", False)
        or getattr(options, "test", False)
        or getattr(options, "xcode_tests", False)
    )


def _should_run_fast_hooks(options: t.Any) -> bool:
    if getattr(options, "skip_hooks", False):
        return False
    return not getattr(options, "comp", False)


def _should_run_comprehensive_hooks(options: t.Any) -> bool:
    if getattr(options, "skip_hooks", False):
        return False
    if getattr(options, "fast", False):
        return False
    return not getattr(options, "fast_iteration", False)


def _should_run_coverage_ratchet(options: t.Any) -> bool:

    return not getattr(options, "no_coverage_ratchet", False)


def _should_run_documentation_cleanup(options: t.Any) -> bool:
    return bool(getattr(options, "cleanup_docs", False))


def _should_run_git_cleanup(options: t.Any) -> bool:
    return bool(getattr(options, "cleanup_git", False))


def _should_run_doc_updates(options: t.Any) -> bool:
    return bool(getattr(options, "update_docs", False))
