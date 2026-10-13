"""Regression tests for the ``plan_index_sync`` phase.

Change 2 of the ratchet-checkpoint-and-plan-index-sync-phase refactor
promotes ``plan-index-sync`` from a fast hook (which ran on every
``crackerjack run``) to an opt-in publish-time phase. The phase:

1. Defaults to *off* so plain ``crackerjack run`` does not pay for it.
2. Is auto-enabled when ``--publish`` is supplied and
   ``settings.documentation.auto_plan_index_sync_on_publish`` is true.
3. Sits in the phase order directly *after* ``documentation_cleanup`` and
   *before* ``fast_hooks``.
4. Is no longer present in the ``FAST_HOOKS`` list in
   ``crackerjack/config/hooks.py``.

These tests pin each of those four guarantees. Tearing the phase out
silently is a higher-risk move than its mirror
(``documentation_cleanup``), so we test both the surface (which phases
appear) and the source (which hooks are registered).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(
    "/Users/les/.local/state/mahavishnu/worktrees/crackerjack"
)


def _make_options(**overrides):
    """Build a ``SimpleNamespace`` mimicking the crackerjack Options model.

    Only the attributes ``_build_workflow_steps`` touches need real values;
    everything else takes a safe default that keeps the step functions
    guarded off.
    """
    defaults = {
        # ratchet-trigger flags kept off so the test is hermetic.
        "strip_code": False,
        "clean": False,
        "cleanup_docs": False,
        "docs_dry_run": False,
        "plan_index_sync": False,
        "cleanup_configs": False,
        "configs_dry_run": False,
        "cleanup_git": False,
        "update_docs": False,
        "skip_hooks": False,
        "comp": False,
        "fast": False,
        "fast_iteration": False,
        "run_tests": False,
        "test": False,
        "xcode_tests": False,
        "no_snob": False,
        "enable_parallel_phases": False,
        "coverage_ratchet": False,
        "no_config_updates": True,  # suppress "configuration" so steps list stays narrow
        "publish": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Tests 1 + 2 + 3 — phase list surface via ``_build_workflow_steps``
# ---------------------------------------------------------------------------


def test_plan_index_sync_absent_from_default_run_phase_list() -> None:
    """Default ``crackerjack run`` (no publish) does NOT enable the phase.

    The promotion moved plan_index_sync out of fast_hooks specifically
    because rebuilding docs/plans/PLAN_INDEX.md should NOT run on every
    developer invocation. Pin that here: with ``publish=False`` and
    ``plan_index_sync=False``, the step is absent.
    """
    from crackerjack.runtime.oneiric_workflow import _build_workflow_steps

    options = _make_options()

    steps = _build_workflow_steps(options)

    assert "plan_index_sync" not in steps


def test_plan_index_sync_present_when_explicitly_enabled() -> None:
    """``crackerjack run --plan-index-sync`` enables the phase.

    This is the escape hatch: even with ``publish=False`` an operator can
    force a PLAN_INDEX regeneration explicitly.
    """
    from crackerjack.runtime.oneiric_workflow import _build_workflow_steps

    options = _make_options(plan_index_sync=True)

    steps = _build_workflow_steps(options)

    assert "plan_index_sync" in steps


def test_plan_index_sync_position_between_doc_cleanup_and_fast_hooks() -> None:
    """Phase order must be documentation_cleanup -> plan_index_sync -> fast_hooks.

    Plan index regeneration needs to run *after* documentation cleanup so
    it picks up the post-cleanup state, but *before* fast_hooks so a stale
    PLAN_INDEX never reaches a test run.
    """
    from crackerjack.runtime.oneiric_workflow import _build_workflow_steps

    options = _make_options(
        cleanup_docs=True,
        plan_index_sync=True,
        # Turn off the rest so the asserted subsequence stays unique and
        # cheap to read.
        strip_code=False,
        clean=False,
        run_tests=False,
        test=False,
        xcode_tests=False,
        no_config_updates=True,
    )

    steps = _build_workflow_steps(options)

    doc_idx = steps.index("documentation_cleanup")
    pis_idx = steps.index("plan_index_sync")
    fast_idx = steps.index("fast_hooks")

    assert (
        doc_idx < pis_idx < fast_idx
    ), f"expected documentation_cleanup < plan_index_sync < fast_hooks; got {steps!r}"


# ---------------------------------------------------------------------------
# Test 4 — source-level guarantee that plan-index-sync is gone from FAST_HOOKS
# ---------------------------------------------------------------------------


def test_plan_index_sync_removed_from_fast_hooks_module_attribute() -> None:
    """plan-index-sync must NOT be in the FAST_HOOKS list exported by hooks.py.

    The hook system has its own executor and dispatch layer; leaving a
    plan-index-sync entry there would silently re-run PLAN_INDEX.md
    regeneration via the hook path even though the new phase is the
    canonical driver. Pin it at the module level so a revert trips the
    test immediately.
    """
    from crackerjack.config import hooks as hooks_module

    fast_hooks = hooks_module.FAST_HOOKS
    hook_names = [hook.name for hook in fast_hooks]

    assert "plan-index-sync" not in hook_names, (
        "plan-index-sync leaked back into FAST_HOOKS; the publish-time "
        "phase is the canonical driver now."
    )


def test_plan_index_sync_removed_from_fast_hooks_in_source() -> None:
    """Source-level pin: the hooks.py file must not reference plan-index-sync.

    Complements the runtime assertion in case the module is re-exported
    from a different namespace in the future.
    """
    hooks_source = (
        REPO_ROOT / "crackerjack" / "config" / "hooks.py"
    ).read_text()

    assert (
        'name="plan-index-sync"' not in hooks_source
    ), "plan-index-sync HookDefinition block reappeared in hooks.py"


# ---------------------------------------------------------------------------
# Bonus: settings + CLI wiring sanity
# ---------------------------------------------------------------------------


def test_documentation_settings_expose_auto_plan_index_sync_flag() -> None:
    """``DocumentationSettings.auto_plan_index_sync_on_publish`` exists.

    The CLI default-on block in
    ``crackerjack/cli/handlers/main_handlers.py`` flips
    ``options.plan_index_sync`` based on this setting. Missing the field
    means the getattr-with-default silently no-ops the implicit enable.
    """
    from crackerjack.config.settings import DocumentationSettings

    field_names = set(DocumentationSettings.model_fields.keys())

    assert "auto_plan_index_sync_on_publish" in field_names
    assert (
        DocumentationSettings().auto_plan_index_sync_on_publish is True
    )


def test_options_model_carries_plan_index_sync_field() -> None:
    """``Options.plan_index_sync`` is a first-class CLI flag defaulting to False."""
    from crackerjack.cli.options import Options

    assert "plan_index_sync" in Options.model_fields
    assert Options().plan_index_sync is False


# ---------------------------------------------------------------------------
# PhaseCoordinator.run_plan_index_sync_phase — direct unit tests
# ---------------------------------------------------------------------------


def test_run_plan_index_sync_phase_skips_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``plan_index_sync=True`` on options, the phase is a no-op.

    Mirrors the early-return contract for ``run_documentation_cleanup_phase``
    / ``run_git_cleanup_phase``: the ``track_task`` + tool call must not
    fire when the operator didn't ask for the phase.
    """
    from crackerjack.core.phase_coordinator import PhaseCoordinator

    tracked: list[tuple[str, str]] = []

    class _FakeSession:
        def track_task(self, key: str, label: str) -> None:
            tracked.append((key, label))

    coordinator = PhaseCoordinator.__new__(PhaseCoordinator)
    coordinator.session = _FakeSession()  # type: ignore[attr-defined]

    assert (
        coordinator.run_plan_index_sync_phase(  # type: ignore[arg-type]
            SimpleNamespace(plan_index_sync=False),
        )
        is True
    )
    assert tracked == []


def test_run_plan_index_sync_phase_calls_tool_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run_plan_index_sync_phase`` delegates to ``plan_index_sync.main``
    and completes when the tool exits 0."""
    import sys

    from crackerjack.core import phase_coordinator as pc

    completed: list[tuple[str, str]] = []
    tracked: list[tuple[str, str]] = []

    class _FakeSession:
        def track_task(self, key: str, label: str) -> None:
            tracked.append((key, label))

        def complete_task(self, key: str, details: str = "") -> None:
            completed.append((key, details))

    coordinator = pc.PhaseCoordinator.__new__(pc.PhaseCoordinator)
    coordinator.session = _FakeSession()  # type: ignore[attr-defined]
    coordinator.pkg_path = Path("/tmp/repo")  # type: ignore[attr-defined]
    coordinator.console = MagicMock()  # type: ignore[attr-defined]

    fake_main = MagicMock(return_value=0)
    fake_module = MagicMock()
    fake_module.main = fake_main

    # The phase does ``from crackerjack.tools import plan_index_sync as _plan_index_sync``.
    # Patch ``sys.modules`` to swap the cached module for our shim so the
    # lazy import resolves to the MagicMock without needing to mutate the
    # package's `__init__`.
    monkeypatch.setitem(
        sys.modules, "crackerjack.tools.plan_index_sync", fake_module
    )

    assert (
        coordinator.run_plan_index_sync_phase(  # type: ignore[arg-type]
            SimpleNamespace(plan_index_sync=True, docs_dry_run=False),
        )
        is True
    )
    assert ("plan_index_sync", "Plan index sync") in tracked
    assert ("plan_index_sync", "Plan index up-to-date") in completed
    fake_main.assert_called_once()


def test_run_plan_index_sync_phase_dry_run_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``docs_dry_run=True`` flips the completion message to
    ``"Dry-run complete"`` and passes ``--dry-run`` to the tool."""
    import sys

    from crackerjack.core import phase_coordinator as pc

    completed: list[tuple[str, str]] = []

    class _FakeSession:
        def track_task(self, key: str, label: str) -> None:
            pass

        def complete_task(self, key: str, details: str = "") -> None:
            completed.append((key, details))

    coordinator = pc.PhaseCoordinator.__new__(pc.PhaseCoordinator)
    coordinator.session = _FakeSession()  # type: ignore[attr-defined]
    coordinator.pkg_path = Path("/tmp/repo")  # type: ignore[attr-defined]
    coordinator.console = MagicMock()  # type: ignore[attr-defined]

    fake_main = MagicMock(return_value=0)
    fake_module = MagicMock()
    fake_module.main = fake_main

    monkeypatch.setitem(
        sys.modules, "crackerjack.tools.plan_index_sync", fake_module
    )

    assert (
        coordinator.run_plan_index_sync_phase(  # type: ignore[arg-type]
            SimpleNamespace(plan_index_sync=True, docs_dry_run=True),
        )
        is True
    )
    assert ("plan_index_sync", "Dry-run complete") in completed
    # The dry-run argv fragment is appended last.
    args, _ = fake_main.call_args
    assert "--dry-run" in args[0]


def test_run_plan_index_sync_phase_handles_systemexit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The argparse error path raises SystemExit — the phase coerces
    ``exc.code`` to an int and fails the task."""
    import sys

    from crackerjack.core import phase_coordinator as pc

    failed: list[tuple[str, str]] = []

    class _FakeSession:
        def track_task(self, key: str, label: str) -> None:
            pass

        def fail_task(self, key: str, details: str = "") -> None:
            failed.append((key, details))

    coordinator = pc.PhaseCoordinator.__new__(pc.PhaseCoordinator)
    coordinator.session = _FakeSession()  # type: ignore[attr-defined]
    coordinator.pkg_path = Path("/tmp/repo")  # type: ignore[attr-defined]
    coordinator.console = MagicMock()  # type: ignore[attr-defined]

    def raise_system_exit(_argv: list[str]) -> None:
        raise SystemExit(2)

    fake_module = MagicMock()
    fake_module.main = MagicMock(side_effect=raise_system_exit)

    monkeypatch.setitem(
        sys.modules, "crackerjack.tools.plan_index_sync", fake_module
    )

    assert (
        coordinator.run_plan_index_sync_phase(  # type: ignore[arg-type]
            SimpleNamespace(plan_index_sync=True, docs_dry_run=False),
        )
        is False
    )
    assert failed == [("plan_index_sync", "plan_index_sync exited with code 2")]


def test_run_plan_index_sync_phase_handles_systemexit_nonint_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``SystemExit.code`` may be non-int (e.g. None); the phase coerces
    to the safe ``1`` default."""
    import sys

    from crackerjack.core import phase_coordinator as pc

    failed: list[tuple[str, str]] = []

    class _FakeSession:
        def track_task(self, key: str, label: str) -> None:
            pass

        def fail_task(self, key: str, details: str = "") -> None:
            failed.append((key, details))

    coordinator = pc.PhaseCoordinator.__new__(pc.PhaseCoordinator)
    coordinator.session = _FakeSession()  # type: ignore[attr-defined]
    coordinator.pkg_path = Path("/tmp/repo")  # type: ignore[attr-defined]
    coordinator.console = MagicMock()  # type: ignore[attr-defined]

    def raise_system_exit(_argv: list[str]) -> None:
        raise SystemExit(None)  # argparse with error: SystemExit(2), but cover None.

    fake_module = MagicMock()
    fake_module.main = MagicMock(side_effect=raise_system_exit)

    monkeypatch.setitem(
        sys.modules, "crackerjack.tools.plan_index_sync", fake_module
    )

    assert (
        coordinator.run_plan_index_sync_phase(  # type: ignore[arg-type]
            SimpleNamespace(plan_index_sync=True, docs_dry_run=False),
        )
        is False
    )
    assert failed == [("plan_index_sync", "plan_index_sync exited with code 1")]
