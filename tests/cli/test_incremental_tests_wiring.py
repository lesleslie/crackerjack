"""The ``incremental_tests`` option must reach the ``run`` command.

``CLI_OPTIONS`` declared ``incremental_tests`` with a
``--incremental-tests/--full-tests`` pair, but the ``run`` command
never took the option as a parameter, so Typer never registered the
flags. ``crackerjack run --full-tests`` was rejected outright.

That mattered because the incremental path is the default and it turns
coverage collection OFF (``--no-cov``), so an incremental run writes no
coverage.json — and the coverage ratchet refreshes only from
coverage.json. With no way to ask for a full run, the ratchet could
never be refreshed inside a ``run`` workflow, which is what left it
time-stale and failing the release audit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from crackerjack.__main__ import app
from crackerjack.cli.options import CLI_OPTIONS
from crackerjack.managers.test_command_builder import TestCommandBuilder

runner = CliRunner()


@pytest.mark.unit
def test_run_accepts_the_full_tests_flag() -> None:
    """``--full-tests`` must be accepted by the run command."""
    result = runner.invoke(app, ["run", "--full-tests", "--help"])
    assert result.exit_code == 0, result.output


@pytest.mark.unit
def test_run_accepts_the_incremental_tests_flag() -> None:
    result = runner.invoke(app, ["run", "--incremental-tests", "--help"])
    assert result.exit_code == 0, result.output


@pytest.mark.unit
def test_run_help_lists_the_full_tests_flag() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0, result.output
    # Rich truncates the ``--incremental-tests/--full-tests`` pair's first
    # name to ``--incremental-t...`` at the runner's terminal width, so
    # only the second name is greppable here. Both are accepted, which
    # the two invocation tests above cover.
    assert "--full-tests" in result.output


@pytest.mark.unit
def test_incremental_tests_option_is_declared() -> None:
    """The option itself must exist in the shared CLI_OPTIONS table."""
    assert "incremental_tests" in CLI_OPTIONS


@pytest.mark.unit
def test_incremental_run_writes_no_coverage_json() -> None:
    """The default path turns coverage off, so no coverage.json appears."""
    from crackerjack.cli.options import Options

    builder = TestCommandBuilder(pkg_path=Path.cwd())
    options = Options()
    options.incremental_tests = True
    options.run_tests = True

    cmd = builder.build_command(options)

    assert "--testmon" in cmd
    assert "--no-cov" in cmd
    assert "--cov-report=json" not in cmd


@pytest.mark.unit
def test_full_run_writes_coverage_json() -> None:
    """A full run must emit the JSON report the ratchet refreshes from."""
    from crackerjack.cli.options import Options

    builder = TestCommandBuilder(pkg_path=Path.cwd())
    options = Options()
    options.incremental_tests = False
    options.run_tests = True

    cmd = builder.build_command(options)

    assert "--testmon" not in cmd
    assert "--no-cov" not in cmd
    assert "--cov-report=json" in cmd
