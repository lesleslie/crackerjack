"""Guard the invariants pytest-testmon depends on.

pytest-testmon selects tests by reusing pytest-cov's coverage instance
(``_get_nocollect_reasons`` returns no reason when the ``cov_plugin`` is
present). That reuse has one hard incompatibility: **branch mode**. With
``--cov-branch`` enabled, testmon raises ``TestmonException`` and the
entire test phase dies with an opaque error.

Branch coverage is off in every Bodai repo today. These tests keep it off
by failing loudly if someone turns it on, and pin the two properties the
selection path needs to work at all:

1. pytest-testmon is installed (it auto-registers via the ``pytest11``
   entry-point group).
2. The first run in a checkout with no ``.testmondata`` runs the *full*
   suite and writes the data file, rather than selecting nothing.
"""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import pytest

PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"
REPO_ROOT = PYPROJECT_PATH.parent
GITIGNORE_TEMPLATE_PATH = REPO_ROOT / "templates" / "GITIGNORE_BODAI.md"


def _pyproject() -> dict[str, Any]:
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)


def _pytest_addopts() -> str:
    ini_options = _pyproject().get("tool", {}).get("pytest", {}).get("ini_options", {})
    addopts = ini_options.get("addopts", "")
    if isinstance(addopts, list):
        return " ".join(addopts)
    return addopts


class TestTestmonInstall:
    def test_testmon_is_installed(self) -> None:
        assert importlib.metadata.version("pytest-testmon")


class TestBranchCoverageGuard:
    def test_no_branch_coverage_with_testmon(self) -> None:
        """Branch coverage makes testmon raise TestmonException."""
        addopts = _pytest_addopts()

        assert "--cov-branch" not in addopts, (
            "branch coverage is incompatible with pytest-testmon: testmon "
            "reuses pytest-cov's coverage instance and raises "
            "TestmonException in branch mode (testmon/testmon_core.py). "
            "Remove --cov-branch from the pytest addopts."
        )


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
    for the single-segment patterns this template uses.
    """
    for raw_line in template.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if fnmatchcase(filename, line):
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
