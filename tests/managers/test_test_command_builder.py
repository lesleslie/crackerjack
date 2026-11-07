"""Tests for pytest command construction in :class:`TestCommandBuilder`.

The incremental-selection contract lives here: crackerjack no longer shells
out to an external ``snob`` binary to compute which tests to run. It passes
``--testmon`` and lets pytest-testmon deselect unaffected tests at
collection time, so the full test path must always reach pytest.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from crackerjack.managers.test_command_builder import TestCommandBuilder


@pytest.fixture
def builder(tmp_path: Path) -> TestCommandBuilder:
    return TestCommandBuilder(pkg_path=tmp_path)


def _options(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "incremental_tests": True,
        "test_workers": 1,
        "benchmark": False,
        "verbose": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _contains_path(cmd: list[str], expected: Path) -> bool:
    """Compare by string, not identity.

    ``_add_test_path`` appends a ``Path`` object into a ``list[str]``, so a
    plain ``str(path) in cmd`` can never match.
    """
    return any(str(argument) == str(expected) for argument in cmd)


class TestIncrementalSelection:
    """``--testmon`` is present exactly when incremental selection is on."""

    def test_build_command_includes_testmon_when_incremental(
        self,
        builder: TestCommandBuilder,
    ) -> None:
        cmd = builder.build_command(_options(incremental_tests=True))

        assert "--testmon" in cmd

    def test_build_command_omits_testmon_when_full(
        self,
        builder: TestCommandBuilder,
    ) -> None:
        cmd = builder.build_command(_options(incremental_tests=False))

        assert "--testmon" not in cmd

    def test_build_command_defaults_to_incremental_when_option_absent(
        self,
        builder: TestCommandBuilder,
    ) -> None:
        options = SimpleNamespace(test_workers=1, benchmark=False, verbose=False)

        cmd = builder.build_command(options)

        assert "--testmon" in cmd


class TestTestPath:
    """The test path always reaches pytest.

    testmon deselects *within* the collected suite, so pytest must be given
    the full test path in both modes. Passing a pre-filtered subset would
    defeat selection entirely.
    """

    def test_build_command_passes_test_path_when_incremental(
        self,
        builder: TestCommandBuilder,
    ) -> None:
        (builder.pkg_path / "tests").mkdir()

        cmd = builder.build_command(_options(incremental_tests=True))

        assert _contains_path(cmd, builder.pkg_path / "tests")

    def test_build_command_passes_test_path_when_full(
        self,
        builder: TestCommandBuilder,
    ) -> None:
        (builder.pkg_path / "tests").mkdir()

        cmd = builder.build_command(_options(incremental_tests=False))

        assert _contains_path(cmd, builder.pkg_path / "tests")


class TestSnobRemoval:
    """The external ``snob`` binary is gone from the command path."""

    def test_build_command_never_invokes_snob(
        self,
        builder: TestCommandBuilder,
    ) -> None:
        cmd = builder.build_command(_options(incremental_tests=True))

        assert "snob" not in cmd
        assert not any(argument.startswith("snob") for argument in cmd)

    def test_incremental_selection_helper_is_removed(self) -> None:
        assert not hasattr(TestCommandBuilder, "_get_incremental_tests")


class TestJsonReport:
    """The pytest run emits a machine-readable result file.

    Per-test results have to be captured as structured data, not scraped
    out of the human-readable terminal output.
    """

    def test_build_command_includes_json_report(self, builder: TestCommandBuilder) -> None:
        cmd = builder.build_command(_options(incremental_tests=True))

        assert "--json-report" in cmd

    def test_build_command_includes_json_report_file(self, builder: TestCommandBuilder) -> None:
        cmd = builder.build_command(_options(incremental_tests=True))

        assert any(
            argument.startswith("--json-report-file=") for argument in cmd
        )

    def test_json_report_path_is_project_local(self, builder: TestCommandBuilder) -> None:
        path = builder.get_json_report_path()

        assert path.name == "last-run.json"
        assert path.parent.name == ".crackerjack"
        assert path.parent.parent == builder.pkg_path

    def test_json_report_parent_directory_is_created(self, builder: TestCommandBuilder) -> None:
        builder.build_command(_options(incremental_tests=True))

        assert builder.get_json_report_path().parent.is_dir()
