"""Unit tests for crackerjack.tools.ty_audit (Phase Q.1.F).

These tests cover the audit tool that walks a directory tree and reports
``# ty: ignore[...]`` suppressions. The audit is the "real enforcement"
side of the Phase Q split ratchet: the ratchet counts diagnostics; the
audit classifies suppressions by code and by age and detects unused
ones. It is invoked as a periodic-cadence tool, not a per-CI gate.

Surface area covered:

1. Unit-level tests of the two pure helpers (``enumerate_suppressions``,
   ``group_by_code``) — fast feedback on the parsing rules.
2. CLI integration (``python -m crackerjack.tools.ty_audit ...``) — the
   hook invocation layer that consumers actually call. Subprocess-driven
   because in-process mocking would not catch argv / stdout / stderr /
   sys.exit interactions that CI relies on.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from crackerjack.tools.ty_audit import (
    enumerate_suppressions,
    group_by_code,
)

# The subprocess invocations need to import crackerjack.tools.ty_audit.
# In a typical dev env the project is installed editable in the active venv,
# but for our test venv the package lives at this directory's parent
# (the crackerjack repo root). Add it to PYTHONPATH so ``python -m`` works
# regardless of install state.
_CRACKERJACK_ROOT = Path(__file__).resolve().parent.parent.parent
_SUBPROCESS_ENV = {**os.environ, "PYTHONPATH": str(_CRACKERJACK_ROOT)}


def _write_suppressions(
    tests_dir: Path,
    codes: list[tuple[str, str]],
) -> list[Path]:
    """Write one Python file per (filename, code) pair containing a suppression.

    Each file gets a single ``# ty: ignore[<code>]`` line so the test
    can place the suppression on a known line number.

    Returns the list of created files.
    """
    tests_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for filename, code in codes:
        f = tests_dir / filename
        f.write_text(
            f"x = 1  # ty: ignore[{code}]\n",
            encoding="utf-8",
        )
        files.append(f)
    return files


class TestEnumerateSuppressionsFindsTyStyleIgnores:
    """``enumerate_suppressions`` matches ``# ty: ignore[...]`` only.

    The regex must NOT match ``# type: ignore`` (mypy / ruff syntax); the
    audit only reports ty directives.
    """

    def test_enumerate_suppressions_finds_ty_style_ignores(
        self, tmp_path: Path,
    ) -> None:
        """The regex picks up ``# ty: ignore[...]`` but not ``# type: ignore``."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        mixed = tests_dir / "mixed.py"
        mixed.write_text(
            "x = 1  # ty: ignore[invalid-argument-type]\n"
            "y = 2  # type: ignore[arg-type]\n"
            "z = 3  # type: ignore\n"
            "w = 4  # ty: ignore[unresolved-attribute]\n",
            encoding="utf-8",
        )

        refs = enumerate_suppressions(tests_dir)

        codes = sorted(ref.code for ref in refs)
        assert codes == ["invalid-argument-type", "unresolved-attribute"], (
            f"Expected only ty-style suppressions; got {codes}"
        )
        assert len(refs) == 2


class TestGroupByCodeReturnsDictOfLists:
    """``group_by_code`` returns ``{code: [SuppressionRef, ...]}``."""

    def test_group_by_code_returns_dict_of_lists(self, tmp_path: Path) -> None:
        """Suppressions are grouped by diagnostic code with correct counts."""
        tests_dir = tmp_path / "tests"
        _write_suppressions(
            tests_dir,
            [
                ("a.py", "invalid-argument-type"),
                ("b.py", "invalid-argument-type"),
                ("c.py", "invalid-argument-type"),
                ("d.py", "unresolved-attribute"),
                ("e.py", "unresolved-attribute"),
            ],
        )

        refs = enumerate_suppressions(tests_dir)
        grouped = group_by_code(refs)

        # Dict keyed by code, each value is a list of SuppressionRef.
        assert set(grouped.keys()) == {
            "invalid-argument-type",
            "unresolved-attribute",
        }
        assert len(grouped["invalid-argument-type"]) == 3
        assert len(grouped["unresolved-attribute"]) == 2

        # Each entry is a SuppressionRef instance with the expected code.
        for ref in grouped["invalid-argument-type"]:
            assert ref.code == "invalid-argument-type"
        for ref in grouped["unresolved-attribute"]:
            assert ref.code == "unresolved-attribute"


class TestAuditBelowThresholdExits0:
    """Below threshold: ``main()`` exits 0 (gate not triggered)."""

    def test_audit_below_threshold_exits_0(self, tmp_path: Path) -> None:
        """When total suppressions < threshold, exit code 0."""
        tests_dir = tmp_path / "tests"
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(5)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "10",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 0, (
            f"Below-threshold audit must exit 0; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )


class TestAuditAtOrAboveThresholdExits1:
    """At/above threshold: ``main()`` exits 1 (gate triggered)."""

    def test_audit_at_or_above_threshold_exits_1(self, tmp_path: Path) -> None:
        """When total suppressions >= threshold, audit triggers (exit 1)."""
        tests_dir = tmp_path / "tests"
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(12)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "10",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 1, (
            f"At-or-above-threshold audit must exit 1; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )


class TestAuditJSONSchemaMatchesSpec:
    """``--json`` output has all 6 expected fields per the plan."""

    def test_audit_json_schema_matches_spec(self, tmp_path: Path) -> None:
        """``--json`` output contains total/by_code/unused/by_age/threshold/triggered."""
        tests_dir = tmp_path / "tests"
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(3)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "10",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 0
        assert result.stdout.strip()

        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {
            "total",
            "by_code",
            "unused",
            "by_age",
            "threshold",
            "triggered",
        }, f"Unexpected JSON schema: {sorted(payload.keys())}"
        assert payload["total"] == 3
        assert payload["threshold"] == 10
        assert payload["triggered"] is False
        assert payload["by_code"] == {"invalid-argument-type": 3}


class TestAuditMissingPathExits2:
    """Nonexistent tests/ path -> config error (exit 2)."""

    def test_audit_missing_path_exits_2(self, tmp_path: Path) -> None:
        """Nonexistent path -> exit 2 (operator error contract)."""
        missing = tmp_path / "does_not_exist"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(missing),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 2, (
            f"Missing path must exit 2; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )


class TestAuditDryRunAlwaysExits0:
    """``--dry-run`` overrides threshold; always exits 0 even when over."""

    def test_audit_dry_run_always_exits_0(self, tmp_path: Path) -> None:
        """``--dry-run`` short-circuits gate and returns 0 regardless of total."""
        tests_dir = tmp_path / "tests"
        # 100 suppressions, threshold 10 -> would normally trigger (exit 1).
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(100)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "10",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 0, (
            f"--dry-run must always exit 0; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )


class TestSplitRatchetCatchesProdRegression:
    """``ty_ratchet --split`` gates prod diagnostics against prod budget.

    When prod diagnostics exceed prod budget, the split-mode gate fails
    (exit 1). This locks in the Q.1.B split behaviour that the audit
    report consumes.
    """

    def test_split_ratchet_catches_prod_regression(self, tmp_path: Path) -> None:
        """When prod diagnostics exceed prod budget, split-mode gate fails."""
        # Set up a temp repo with both crackerjack/ and tests/ directories
        # and a pyproject.toml with low prod budget so the gate trips.
        crackerjack_dir = tmp_path / "crackerjack"
        tests_dir = tmp_path / "tests"
        crackerjack_dir.mkdir()
        tests_dir.mkdir()

        pyproject = tmp_path / "pyproject.toml"
        # Budget of 0 means any prod diagnostic fails the gate.
        pyproject.write_text(
            "[tool.crackerjack]\nty_max_errors_prod = 0\nty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        # A crackerjack/ file with a real, intentional type error.
        broken = crackerjack_dir / "broken.py"
        broken.write_text(
            "x: int = 'this should be an int'\n",
            encoding="utf-8",
        )

        # tests/ has no suppressions / diagnostics; it's a tiny valid file.
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "crackerjack.tools.ty_ratchet",
                    "--split",
                    "--pyproject",
                    str(pyproject),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=tmp_path,
                env=_SUBPROCESS_ENV,
            )

            # prod_count > 0 with prod budget = 0 -> prod_gate = False -> exit 1.
            assert result.returncode == 1, (
                f"prod budget breach must exit 1; got {result.returncode}. "
                f"stderr={result.stderr!r}"
            )
        finally:
            # Cleanup: remove the file we created (and any pyproject remnants).
            shutil.rmtree(crackerjack_dir, ignore_errors=True)
            shutil.rmtree(tests_dir, ignore_errors=True)
            if pyproject.exists():
                pyproject.unlink()


class TestThresholdBreachSignalInJSON:
    """When suppressions cross threshold, ``triggered`` is True in JSON."""

    def test_threshold_breach_signal_in_json(self, tmp_path: Path) -> None:
        """``triggered`` is True when total >= threshold (JSON output)."""
        tests_dir = tmp_path / "tests"
        # 60 suppressions with threshold 50 -> triggered.
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(60)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "50",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 1
        assert result.stdout.strip()

        payload = json.loads(result.stdout)
        assert payload["total"] == 60
        assert payload["threshold"] == 50
        assert payload["triggered"] is True, (
            f"Expected triggered=True at total=60, threshold=50; "
            f"got {payload['triggered']}"
        )
