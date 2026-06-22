"""Tests for snob subset test stage (Task 5) — RED first."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestSnobStageSkipsWhenNoAffectedTests:
    async def test_snob_stage_skips_when_no_affected_tests(self) -> None:
        """Returns True immediately when snob finds no affected tests."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        coordinator = PhaseCoordinator.__new__(PhaseCoordinator)
        coordinator.console = MagicMock()

        options = MagicMock()
        options.no_snob = False

        with patch.object(
            coordinator, "_get_snob_affected_tests", return_value=[]
        ):
            result = await coordinator.run_snob_tests_phase(options)

        assert result is True, "Empty test list should return True (nothing to fail)"


@pytest.mark.unit
class TestSnobStagePassesWhenTestsPass:
    async def test_snob_stage_passes_when_all_affected_tests_pass(self) -> None:
        """Returns True when all affected tests pass."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        coordinator = PhaseCoordinator.__new__(PhaseCoordinator)
        coordinator.console = MagicMock()

        options = MagicMock()
        options.no_snob = False

        affected = [Path("tests/unit/test_foo.py")]

        with (
            patch.object(
                coordinator, "_get_snob_affected_tests", return_value=affected
            ),
            patch.object(
                coordinator, "_run_pytest_subset", return_value=True
            ),
        ):
            result = await coordinator.run_snob_tests_phase(options)

        assert result is True


@pytest.mark.unit
class TestSnobStageSoftFailsOnUnsafe:
    async def test_snob_stage_soft_fails_on_unsafe_failures(self) -> None:
        """Unsafe failures (no safe classification) → returns False but doesn't block."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        coordinator = PhaseCoordinator.__new__(PhaseCoordinator)
        coordinator.console = MagicMock()

        options = MagicMock()
        options.no_snob = False

        affected = [Path("tests/unit/test_bar.py")]

        with (
            patch.object(
                coordinator, "_get_snob_affected_tests", return_value=affected
            ),
            patch.object(
                coordinator, "_run_pytest_subset", return_value=False
            ),
            patch.object(
                coordinator,
                "_classify_safe_test_failures",
                return_value=[],  # no safe failures → unsafe
            ),
        ):
            result = await coordinator.run_snob_tests_phase(options)

        assert result is False


@pytest.mark.unit
class TestSnobStageAutoFixesSafe:
    async def test_snob_stage_auto_fixes_and_reruns_safe_failures(self) -> None:
        """Safe failures → auto-fix applied → rerun passes → returns True."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        coordinator = PhaseCoordinator.__new__(PhaseCoordinator)
        coordinator.console = MagicMock()
        coordinator.test_manager = MagicMock()
        coordinator.test_manager.get_test_failures.return_value = [
            "ImportError: cannot import name 'Foo'"
        ]

        options = MagicMock()
        options.no_snob = False

        affected = [Path("tests/unit/test_baz.py")]

        with (
            patch.object(
                coordinator, "_get_snob_affected_tests", return_value=affected
            ),
            patch.object(
                coordinator,
                "_run_pytest_subset",
                side_effect=[False, True],  # fail, then pass after fix
            ),
            patch.object(
                coordinator,
                "_classify_safe_test_failures",
                return_value=["ImportError: cannot import name 'Foo'"],
            ),
            patch.object(
                coordinator,
                "_apply_ai_fix_for_tests_auto",
                return_value=True,
            ),
        ):
            result = await coordinator.run_snob_tests_phase(options)

        assert result is True


@pytest.mark.unit
class TestSnobStageSoftFailsWhenFixDoesNotResolve:
    async def test_snob_stage_soft_fails_when_fix_does_not_resolve(self) -> None:
        """Fix applied but rerun still fails → returns False (soft fail, continue)."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        coordinator = PhaseCoordinator.__new__(PhaseCoordinator)
        coordinator.console = MagicMock()
        coordinator.test_manager = MagicMock()
        coordinator.test_manager.get_test_failures.return_value = [
            "ImportError: cannot import name 'Foo'"
        ]

        options = MagicMock()
        options.no_snob = False

        affected = [Path("tests/unit/test_baz.py")]

        with (
            patch.object(
                coordinator, "_get_snob_affected_tests", return_value=affected
            ),
            patch.object(
                coordinator,
                "_run_pytest_subset",
                side_effect=[False, False],  # fails both times
            ),
            patch.object(
                coordinator,
                "_classify_safe_test_failures",
                return_value=["ImportError: cannot import name 'Foo'"],
            ),
            patch.object(
                coordinator,
                "_apply_ai_fix_for_tests_auto",
                return_value=True,
            ),
        ):
            result = await coordinator.run_snob_tests_phase(options)

        assert result is False


@pytest.mark.unit
class TestNoSnobFlagSkipsStage:
    async def test_no_snob_flag_skips_stage_entirely(self) -> None:
        """--no-snob → run_snob_tests_phase returns True without running snob."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        coordinator = PhaseCoordinator.__new__(PhaseCoordinator)
        coordinator.console = MagicMock()

        options = MagicMock()
        options.no_snob = True

        with patch.object(
            coordinator, "_get_snob_affected_tests"
        ) as mock_snob:
            result = await coordinator.run_snob_tests_phase(options)

        mock_snob.assert_not_called()
        assert result is True


@pytest.mark.unit
class TestSnobWorkflowRegistration:
    def test_snob_step_registered_between_fast_and_comprehensive(self) -> None:
        """snob_tests step appears in workflow between fast_hooks and comprehensive_hooks."""
        from types import SimpleNamespace

        from crackerjack.runtime.oneiric_workflow import _build_workflow_steps

        # Use SimpleNamespace so getattr returns actual False for unset attrs
        options = SimpleNamespace(
            no_snob=False,
            no_config_updates=True,
            clean=False,
            skip_hooks=False,
            comp=False,          # ensures fast_hooks runs
            fast=False,          # ensures comp hooks runs
            fast_iteration=False,
            enable_parallel_phases=False,
            cleanup_docs=False,
            cleanup_git=False,
            publish=False,
            commit=False,
            bump_type=None,
            check=False,
            run_tests=False,
            test=False,
            xcode_tests=False,
        )

        steps = _build_workflow_steps(options)

        assert "fast_hooks" in steps, "fast_hooks must be in steps for this test to be meaningful"
        assert "comprehensive_hooks" in steps, "comp hooks must be present"

        fast_idx = steps.index("fast_hooks")
        comp_idx = steps.index("comprehensive_hooks")
        assert "snob_tests" in steps, "snob_tests must be registered in workflow steps"
        snob_idx = steps.index("snob_tests")
        assert fast_idx < snob_idx < comp_idx, (
            f"snob_tests (idx={snob_idx}) must be between "
            f"fast_hooks (idx={fast_idx}) and comprehensive_hooks (idx={comp_idx})"
        )
