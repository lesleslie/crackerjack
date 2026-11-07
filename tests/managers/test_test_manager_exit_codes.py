"""Exit-code handling for the pytest test phase.

pytest exits with 5 (``EXIT_NOTESTSCOLLECTED``) when a run collects no
tests at all. Under pytest-testmon that is the *normal* outcome of an
incremental run whose change affects no test: the suite is collected and
every test is deselected. It must be a pass, not a red gate.

For a full (non-incremental) run, exit 5 still means something is wrong -
the suite is non-empty but nothing was collected - so it stays a failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from crackerjack.managers.test_manager import TestManager

EXIT_NOTESTSCOLLECTED = 5


@pytest.fixture
def manager(tmp_path: Path) -> TestManager:
    return TestManager(pkg_path=tmp_path)


def _options(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "incremental_tests": True,
        "test_workers": 1,
        "benchmark": False,
        "verbose": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _completed(returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["pytest"],
        returncode=returncode,
        stdout="no tests ran",
        stderr="",
    )


class TestNoTestsCollected:
    """Exit code 5 means "nothing was affected", not "the suite broke"."""

    def test_exit_code_five_is_success_when_incremental(
        self,
        manager: TestManager,
    ) -> None:
        with patch.object(
            manager,
            "_execute_test_workflow",
            return_value=_completed(EXIT_NOTESTSCOLLECTED),
        ):
            result = manager._run_pytest_if_needed(
                True,
                _options(incremental_tests=True),
                0.0,
            )

        assert result is True

    def test_exit_code_five_is_failure_when_not_incremental(
        self,
        manager: TestManager,
    ) -> None:
        with patch.object(
            manager,
            "_execute_test_workflow",
            return_value=_completed(EXIT_NOTESTSCOLLECTED),
        ):
            result = manager._run_pytest_if_needed(
                True,
                _options(incremental_tests=False),
                0.0,
            )

        assert result is False

    def test_other_failure_codes_still_fail(
        self,
        manager: TestManager,
    ) -> None:
        with patch.object(
            manager,
            "_execute_test_workflow",
            return_value=_completed(1),
        ):
            result = manager._run_pytest_if_needed(
                True,
                _options(incremental_tests=True),
                0.0,
            )

        assert result is False

    def test_zero_exit_code_still_succeeds(
        self,
        manager: TestManager,
    ) -> None:
        with patch.object(
            manager,
            "_execute_test_workflow",
            return_value=_completed(0),
        ):
            result = manager._run_pytest_if_needed(
                True,
                _options(incremental_tests=True),
                0.0,
            )

        assert result is True
