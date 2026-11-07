"""An incremental run's coverage is partial, and must not be read as a
full-suite measurement.

pytest-testmon selects the affected tests *inside* pytest, so an
incremental run measures only the code those tests touch. Its coverage
number is therefore not comparable to the full-suite baseline the
coverage ratchet is calibrated against.

That distinction only became reachable with this branch. Before it, the
selection shell-out always failed (the ``snob`` binary is not installed),
so every run was a full-suite run and the ratchet always saw a
comparable number. Now that selection actually works, an incremental run
that deselects everything writes ``coverage.json`` with 0% covered, and
the ratchet reads that as a 68-point coverage regression that never
happened.

These tests pin two consequences:

1. A run in which nothing was affected says so plainly, instead of
   reporting "Tests passed" over an empty selection.
2. The coverage ratchet is skipped for an incremental run, instead of
   reporting a regression that did not happen.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.managers.test_command_builder import TestCommandBuilder
from crackerjack.managers.test_manager import TestManager


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "testproject"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def console() -> MagicMock:
    return MagicMock(spec=Console)


def _manager(project: Path, console: MagicMock) -> TestManager:
    return TestManager(
        console=console,
        pkg_path=project,
        command_builder=TestCommandBuilder(pkg_path=project),
        run_state_db_path=project / "run_state.db",
    )


def _options(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "incremental_tests": True,
        "test_workers": 1,
        "benchmark": False,
        "verbose": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _write_report(project: Path, tests: list[dict[str, Any]]) -> None:
    report_path = project / ".crackerjack" / "last-run.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({"summary": {"total": len(tests)}, "tests": tests}),
        encoding="utf-8",
    )


def _completed(returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["pytest"], returncode=returncode, stdout="", stderr=""
    )


def _printed(console: MagicMock) -> str:
    return " ".join(
        str(arg) for call in console.print.call_args_list for arg in call.args
    )


class TestNothingAffected:
    def test_an_empty_selection_is_reported_plainly(
        self, project: Path, console: MagicMock
    ) -> None:
        """testmon deselected everything: say so, do not claim tests passed."""
        manager = _manager(project, console)
        _write_report(project, [])

        with (
            patch.object(
                manager, "_execute_test_workflow", return_value=_completed(0)
            ),
            patch.object(manager, "_handle_test_success") as success_mock,
        ):
            result = manager._run_pytest_if_needed(True, _options(), 0.0)

        assert result is True
        success_mock.assert_not_called()
        assert "No tests affected" in _printed(console)

    def test_a_populated_selection_uses_the_normal_success_path(
        self, project: Path, console: MagicMock
    ) -> None:
        manager = _manager(project, console)
        _write_report(
            project,
            [{"nodeid": "tests/test_a.py::test_one", "outcome": "passed"}],
        )

        with (
            patch.object(
                manager, "_execute_test_workflow", return_value=_completed(0)
            ),
            patch.object(
                manager, "_handle_test_success", return_value=True
            ) as success_mock,
        ):
            result = manager._run_pytest_if_needed(True, _options(), 0.0)

        assert result is True
        success_mock.assert_called_once()
        assert "No tests affected" not in _printed(console)


class TestRunModeIsObservable:
    def test_an_incremental_run_is_reported_as_incremental(
        self, project: Path, console: MagicMock
    ) -> None:
        manager = _manager(project, console)
        _write_report(project, [])

        with (
            patch.object(
                manager, "_execute_test_workflow", return_value=_completed(0)
            ),
            patch.object(manager, "_handle_test_success", return_value=True),
        ):
            manager._run_pytest_if_needed(True, _options(incremental_tests=True), 0.0)

        assert manager.last_run_was_incremental() is True

    def test_a_full_run_is_not_reported_as_incremental(
        self, project: Path, console: MagicMock
    ) -> None:
        manager = _manager(project, console)
        _write_report(project, [])

        with (
            patch.object(
                manager, "_execute_test_workflow", return_value=_completed(0)
            ),
            patch.object(manager, "_handle_test_success", return_value=True),
        ):
            manager._run_pytest_if_needed(True, _options(incremental_tests=False), 0.0)

        assert manager.last_run_was_incremental() is False


class TestCoverageRatchetSkipsIncrementalRuns:
    def test_the_ratchet_phase_is_skipped_after_an_incremental_run(self) -> None:
        """A partial coverage number must not be compared to the baseline."""
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        test_manager = MagicMock()
        test_manager.last_run_was_incremental.return_value = True
        coordinator = PhaseCoordinator(test_manager=test_manager)

        with patch.object(
            test_manager.coverage_manager, "process_coverage_ratchet"
        ) as ratchet_mock:
            result = coordinator.run_coverage_ratchet_phase(_options())

        assert result is True
        ratchet_mock.assert_not_called()

    def test_the_ratchet_phase_still_runs_after_a_full_run(self) -> None:
        from crackerjack.core.phase_coordinator import PhaseCoordinator

        test_manager = MagicMock()
        test_manager.last_run_was_incremental.return_value = False
        test_manager.coverage_manager.process_coverage_ratchet.return_value = True
        coordinator = PhaseCoordinator(test_manager=test_manager)

        result = coordinator.run_coverage_ratchet_phase(_options())

        assert result is True
        test_manager.coverage_manager.process_coverage_ratchet.assert_called_once()
