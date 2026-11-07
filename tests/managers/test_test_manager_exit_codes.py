"""Exit-code handling for the pytest test phase.

pytest exits with 5 (``EXIT_NOTESTSCOLLECTED``) when it collects no
tests at all. Under pytest-testmon that is *not* what "nothing was
affected" looks like: testmon empties the collected item list, pytest
computes ``testscollected == 0`` and would exit 5, but testmon's own
``pytest_sessionfinish`` hook rewrites that status to 0 **only when it
actually deselected something**:

    if len(self.deselected_tests) and exitstatus == ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = ExitCode.OK

So the exit code that actually reaches the caller discriminates the two
cases:

* **exit 0 with an empty result set** - testmon deselected every test.
  The change affects nothing. This is a pass.
* **exit 5** - testmon deselected *nothing* and pytest collected
  *nothing*. The test configuration is broken. This is a failure, in an
  incremental run as much as in a full one.

Treating exit 5 as a success in an incremental run therefore turns a
misconfigured test suite into a green run.
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
    """Exit code 5 means "pytest collected nothing", which is a failure."""

    def test_exit_code_five_is_failure_when_incremental(
        self,
        manager: TestManager,
    ) -> None:
        """A broken test configuration must not report a green run.

        testmon rewrites exit 5 to 0 when it deselected everything, so a
        5 that reaches the caller means pytest collected nothing at all.
        """
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

        assert result is False

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
