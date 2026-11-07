"""The ``snob_tests`` phase is gone from the crackerjack workflow.

pytest-testmon performs test selection *inside* pytest, so the separate
``snob_tests`` phase - which shelled out to a ``snob`` binary that is not
installed and therefore always degraded to a silent no-op - is redundant.

Keeping it was not free: the phase was registered in the workflow, emitted
``snob_tests`` test.started/completed/failed events that never corresponded
to real work, and carried a ``no_snob`` option that no code path ever set.

These tests pin that the phase is gone rather than merely dormant.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.runtime.oneiric_workflow import _build_workflow_steps


def _make_options(**overrides: Any) -> SimpleNamespace:
    """Build options that keep every optional phase guarded off."""
    defaults: dict[str, Any] = {
        "strip_code": False,
        "clean": False,
        "cleanup_docs": False,
        "plan_index_sync": False,
        "cleanup_git": False,
        "update_docs": False,
        "skip_hooks": False,
        "comp": False,
        "fast": False,
        "fast_iteration": False,
        "run_tests": False,
        "test": False,
        "xcode_tests": False,
        "enable_parallel_phases": False,
        "coverage_ratchet": False,
        "no_config_updates": True,
        "publish": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestSnobPhaseRemoved:
    """The snob_tests phase is removed, not merely disabled."""

    def test_snob_tests_step_not_in_workflow_steps(self) -> None:
        steps = _build_workflow_steps(_make_options())

        assert "snob_tests" not in steps

    def test_snob_tests_step_absent_even_with_fast_hooks_enabled(self) -> None:
        """Fast hooks used to imply the snob_tests step followed it."""
        steps = _build_workflow_steps(
            _make_options(skip_hooks=False, comp=False, fast=False)
        )

        assert "fast_hooks" in steps
        assert "snob_tests" not in steps

    def test_snob_tests_phase_not_registered(self) -> None:
        assert not hasattr(PhaseCoordinator, "run_snob_tests_phase")

    def test_snob_affected_test_helper_removed(self) -> None:
        assert not hasattr(PhaseCoordinator, "_get_snob_affected_tests")
