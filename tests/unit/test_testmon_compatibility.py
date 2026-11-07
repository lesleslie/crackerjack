"""Guard the invariants pytest-testmon depends on.

pytest-testmon selects tests by reusing pytest-cov's coverage instance
(``_get_nocollect_reasons`` returns no reason when the ``cov_plugin`` is
present). That reuse has one hard incompatibility: **branch mode**. With
``--cov-branch`` enabled, testmon raises ``TestmonException`` and the
entire test phase dies with an opaque error.

Branch coverage *is* on in the Bodai fleet -- every pyproject template
carries ``branch = true`` -- so the incompatibility is resolved by the
gate rather than by asking projects to leave branch coverage off. These
tests pin that resolution, plus the two properties the selection path
needs to work at all:

1. The incremental run disables coverage collection, so branch mode
   cannot reach testmon.
2. pytest-testmon is installed (it auto-registers via the ``pytest11``
   entry-point group).
3. The first run in a checkout with no ``.testmondata`` runs the *full*
   suite and writes the data file, rather than selecting nothing.
"""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from types import SimpleNamespace

import pytest

from crackerjack.managers.test_command_builder import TestCommandBuilder

PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"
REPO_ROOT = PYPROJECT_PATH.parent
GITIGNORE_TEMPLATE_PATH = REPO_ROOT / "templates" / "GITIGNORE_BODAI.md"


class TestTestmonInstall:
    def test_testmon_is_installed(self) -> None:
        assert importlib.metadata.version("pytest-testmon")


class TestBranchCoverageIsNeutralised:
    """Branch coverage is allowed; the incremental run has to survive it.

    pytest-cov 7.1 offers ``--cov-branch`` to turn branch coverage on and
    nothing to turn it off, so a project that enables it in
    ``[tool.coverage.run]`` puts testmon in branch mode, where it raises
    ``TestmonException``. The gate therefore switches coverage collection
    off for the incremental run. These tests pin that resolution, so a
    later change cannot quietly reintroduce the INTERNALERROR that made
    the gate report a failed run that executed zero tests.
    """

    def test_the_incremental_run_disables_coverage_collection(self) -> None:
        builder = TestCommandBuilder(pkg_path=REPO_ROOT)
        options = SimpleNamespace(
            incremental_tests=True,
            test_workers=1,
            benchmark=False,
            verbose=False,
        )

        cmd = builder.build_command(options)

        assert "--testmon" in cmd
        assert "--no-cov" in cmd
        assert not [argument for argument in cmd if argument.startswith("--cov")]

    def test_the_full_run_keeps_coverage_collection(self) -> None:
        """The full run is the one whose coverage the ratchet compares."""
        builder = TestCommandBuilder(pkg_path=REPO_ROOT)
        options = SimpleNamespace(
            incremental_tests=False,
            test_workers=1,
            benchmark=False,
            verbose=False,
        )

        cmd = builder.build_command(options)

        assert "--testmon" not in cmd
        assert "--no-cov" not in cmd
        assert any(argument.startswith("--cov=") for argument in cmd)


class TestFirstRunBehaviour:
    def test_first_run_without_testmondata_runs_full_suite(
        self,
        tmp_path: Path,
    ) -> None:
        """A checkout with no .testmondata must run every test once.

        If the first run selected nothing, the dependency map would never
        be written and every later incremental run would be empty too.
        """
        (tmp_path / "my_module.py").write_text("VALUE = 1\n")
        (tmp_path / "test_my_module.py").write_text(
            "import my_module\n"
            "\n"
            "\n"
            "def test_one():\n"
            "    assert my_module.VALUE == 1\n"
            "\n"
            "\n"
            "def test_two():\n"
            "    assert my_module.VALUE + 1 == 2\n"
        )

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--testmon", "-v"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"first testmon run failed:\n{result.stdout}\n{result.stderr}"
        )
        assert "test_one" in result.stdout
        assert "test_two" in result.stdout
        assert (tmp_path / ".testmondata").exists(), (
            "testmon did not write .testmondata, so no dependency map was "
            "collected and later incremental runs would select nothing"
        )


def _template_ignores(template: Path, filename: str) -> bool:
    """Whether *template* carries a gitignore rule matching *filename*.

    Gitignore patterns without a slash match at any directory level, and
    ``*`` spans path separators - the same as :func:`fnmatch.fnmatchcase`
    for the single-segment patterns this template uses. A pattern that
    ends in a slash names a directory, and covers everything under it.
    """
    for raw_line in template.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if fnmatchcase(filename, line):
            return True
        if line.endswith("/") and filename.startswith(line):
            return True
    return False


class TestTestmonDataFilesAreIgnored:
    """testmon's data file is a SQLite database, and SQLite leaves sidecars.

    ``.testmondata`` on its own does not cover ``.testmondata-shm`` and
    ``.testmondata-wal``, which SQLite creates alongside the database.
    Leaving them unignored turns every testmon run into untracked cruft
    in ``git status``.
    """

    DATA_FILES = (".testmondata", ".testmondata-shm", ".testmondata-wal")

    @pytest.mark.parametrize("filename", DATA_FILES)
    def test_repo_gitignore_ignores_testmon_data_files(self, filename: str) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", filename],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"{filename} is not ignored by .gitignore; it shows up as "
            f"untracked cruft after every testmon run"
        )

    @pytest.mark.parametrize("filename", DATA_FILES)
    def test_fleet_template_ignores_testmon_data_files(self, filename: str) -> None:
        assert _template_ignores(GITIGNORE_TEMPLATE_PATH, filename), (
            f"{filename} is not ignored by templates/GITIGNORE_BODAI.md; every "
            f"Bodai repo that adopts pytest-testmon inherits the cruft"
        )


class TestRunStateReportIsIgnored:
    """The JSON report the test phase writes must never be committable.

    ``TestCommandBuilder`` writes the pytest JSON report to
    ``<repo>/.crackerjack/last-run.json``. It holds per-test results for
    the working tree, so it is runtime state, not source. The fleet
    template has to carry the rule, or every Bodai repo that adopts the
    run-state feature inherits an untracked file that a ``git add .``
    would sweep into a commit.
    """

    REPORT_PATH = ".crackerjack/last-run.json"

    def test_the_repo_gitignore_ignores_the_report(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", self.REPORT_PATH],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"{self.REPORT_PATH} is not ignored by .gitignore; the per-test "
            f"results of the working tree can be swept into a commit"
        )

    def test_the_fleet_template_ignores_the_report(self) -> None:
        assert _template_ignores(GITIGNORE_TEMPLATE_PATH, self.REPORT_PATH), (
            f"{self.REPORT_PATH} is not ignored by templates/GITIGNORE_BODAI.md; "
            f"every Bodai repo that adopts the run-state feature inherits it"
        )
