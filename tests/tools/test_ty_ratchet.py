"""Unit tests for crackerjack.tools.ty_ratchet (Phase Q.0).

These tests cover the existing single-target (legacy) mode of
``crackerjack.tools.ty_ratchet``. The Phase Q.1.B refactor will introduce a
``--split`` mode (one ty invocation per sub-package) and the JSON envelope
will gain a ``mode`` discriminator field. The tests below lock in the
behaviour of the *legacy* path that callers (pre-commit, crackerjack hook,
CI) depend on today.

Surface area covered:

1. CLI integration (``python -m crackerjack.tools.ty_ratchet ...``) — the
   hook invocation layer that consumers actually call. Subprocess-driven
   because in-process mocking would not catch argv / stdout / stderr /
   sys.exit interactions that CI relies on.
2. Unit-level tests of the two pure helpers (``_read_max_errors``,
   ``_count_diagnostics``) — fast feedback on the parsing rules.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from crackerjack.tools.ty_ratchet import (
    _count_diagnostics,
    _has_python_files,
    _include_glob,
    _read_max_errors,
)

# The subprocess invocations need to import crackerjack.tools.ty_ratchet.
# In a typical dev env the project is installed editable in the active venv,
# but for our test venv the package lives at this directory's parent
# (the crackerjack repo root). Add it to PYTHONPATH so ``python -m`` works
# regardless of install state.
_CRACKERJACK_ROOT = Path(__file__).resolve().parent.parent.parent
_SUBPROCESS_ENV = {**os.environ, "PYTHONPATH": str(_CRACKERJACK_ROOT)}


class TestLegacyModeJSONSchema:
    """``--json`` without ``--split`` returns the single-target schema."""

    def test_legacy_mode_returns_single_target_json(self, tmp_path: Path) -> None:
        """Invoking without --split returns the existing JSON schema unchanged."""
        # Run against a tiny target that exists (the ``crackerjack`` package)
        # so ty has *something* to look at. Use the repo's own crackerjack/
        # as the target because that is what the hook in this repo passes.
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "crackerjack",
                "--json",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,  # cwd irrelevant; we pass explicit target
            env=_SUBPROCESS_ENV,
        )

        # Even if ty fails on the package, --dry-run should not crash on
        # JSON emission. The script always prints JSON when --json is set.
        assert result.returncode in (0, 1), (
            f"Unexpected exit code {result.returncode}; stderr={result.stderr!r}"
        )
        assert result.stdout.strip(), f"Empty stdout; stderr={result.stderr!r}"

        payload = json.loads(result.stdout)

        # Schema assertions: legacy mode has these keys, and *only* these
        assert payload["target"] == "crackerjack"
        assert isinstance(payload["diagnostic_count"], int)
        assert payload["diagnostic_count"] >= 0
        assert isinstance(payload["max_errors"], int)
        assert isinstance(payload["gate_passes"], bool)
        assert isinstance(payload["ty_exit_code"], int)

        # Legacy mode has no ``mode`` discriminator (Phase Q.1.B will add one).
        assert "mode" not in payload, (
            "Legacy mode must not emit a 'mode' key (Q.1.B design contract)."
        )


class TestDryRunDoesNotEnforceGate:
    """``--dry-run`` reports the diagnostic count without enforcing the gate."""

    def test_dry_run_does_not_enforce_gate(self, tmp_path: Path) -> None:
        """``--dry-run`` exits 0 even when diagnostic count exceeds budget."""
        # ``--max-errors 0`` would normally fail any gate (count > 0).
        # ``--dry-run`` must short-circuit the gate and return 0.
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "crackerjack",
                "--max-errors",
                "0",
                "--dry-run",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 0, (
            f"--dry-run must exit 0; got {result.returncode}. stderr={result.stderr!r}"
        )

        # The JSON should still report gate_passes=False (count > 0 budget)
        # but the process exit code is 0 because --dry-run short-circuits.
        if result.stdout.strip():
            payload = json.loads(result.stdout)
            # diagnostic_count may be 0 or more; the gate must not be the
            # source of the exit code under --dry-run.
            assert payload["max_errors"] == 0
            # gate_passes reflects the diagnostic count vs budget, not the
            # process exit code (which is the point of --dry-run).
            assert isinstance(payload["gate_passes"], bool)


class TestConfigMissingReturnsDefault250:
    """Budget falls back to 250 when ``pyproject.toml`` is absent."""

    def test_config_missing_returns_default_250(self, tmp_path: Path) -> None:
        """When pyproject.toml is absent, the budget defaults to 250."""
        # tmp_path is empty -> no pyproject.toml -> default budget kicks in.
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "crackerjack",
                "--json",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode in (0, 1)
        assert result.stdout.strip()

        payload = json.loads(result.stdout)
        assert payload["max_errors"] == 250, (
            f"Expected default 250 when pyproject.toml is missing; "
            f"got max_errors={payload['max_errors']}"
        )


class TestInvalidMaxErrorsInConfigExits2:
    """Malformed ``ty_max_errors`` is an operator error (exit 2)."""

    def test_invalid_max_errors_in_config_exits_2(self, tmp_path: Path) -> None:
        """Malformed ty_max_errors value -> operator error (exit 2)."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.crackerjack]\nty_max_errors = "not-a-number"\n',
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "crackerjack",
                "--pyproject",
                str(pyproject),
                "--dry-run",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        # Exit code 2 is the operator-error contract documented in the
        # module docstring ("config missing or malformed").
        assert result.returncode == 2, (
            f"Malformed ty_max_errors must exit 2; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )
        # Stderr should mention the malformed value so the operator can
        # see what's wrong.
        assert "ty_max_errors" in result.stderr or "not-a-number" in result.stderr


class TestCountDiagnosticsPrefersSummaryLine:
    """``_count_diagnostics`` prefers the explicit ``Found N diagnostics`` line."""

    def test_count_diagnostics_prefers_summary_line(self) -> None:
        """``_count_diagnostics`` reads 'Found N diagnostics' when present."""
        output = (
            "crackerjack/foo.py:10:5: error[invalid-argument-type] Argument ...\n"
            "crackerjack/bar.py:42:9: warning[unused-type-ignore-comment] ...\n"
            "Found 252 diagnostics\n"
        )
        # Summary line says 252; line-prefixed count would say 2.
        assert _count_diagnostics(output) == 252


class TestCountDiagnosticsFallsBackToLineCount:
    """``_count_diagnostics`` falls back to prefix-matching when summary absent."""

    def test_count_diagnostics_falls_back_to_line_count(self) -> None:
        """When summary line is absent, count diagnostic-prefixed lines."""
        output = (
            "crackerjack/foo.py:10:5: error[invalid-argument-type] Argument ...\n"
            "crackerjack/bar.py:42:9: warning[unused-type-ignore-comment] ...\n"
            "crackerjack/baz.py:7:1: error[import-not-found] Cannot find ...\n"
            "Some unrelated text from the tool.\n"
        )
        # Three diagnostic-prefixed lines, no "Found N" line.
        assert _count_diagnostics(output) == 3


class TestReadMaxErrorsDefaults:
    """``_read_max_errors`` returns 250 when the field is absent."""

    def test_read_max_errors_missing_file(self, tmp_path: Path) -> None:
        """Missing pyproject.toml -> default 250."""
        assert _read_max_errors(tmp_path / "missing.toml") == 250

    def test_read_max_errors_missing_section(self, tmp_path: Path) -> None:
        """pyproject without ``[tool.crackerjack]`` -> default 250."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.something_else]\nfoo = "bar"\n',
            encoding="utf-8",
        )
        assert _read_max_errors(pyproject) == 250

    def test_read_max_errors_missing_field(self, tmp_path: Path) -> None:
        """``[tool.crackerjack]`` exists but no ``ty_max_errors`` -> 250."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\nother_field = 1\n",
            encoding="utf-8",
        )
        assert _read_max_errors(pyproject) == 250

    def test_read_max_errors_uses_section_field(self, tmp_path: Path) -> None:
        """``ty_max_errors`` value is read from ``[tool.crackerjack]``."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\nty_max_errors = 42\n",
            encoding="utf-8",
        )
        assert _read_max_errors(pyproject) == 42


class TestSplitModeDirFlags:
    """Option B: ``--prod-dir`` and ``test-dir`` override the hardcoded
    ``crackerjack``/``tests`` defaults so the ratchet can be pointed at
    any project's actual layout. Defaults are preserved for direct CLI
    callers and the legacy single-target path.
    """

    def test_split_mode_respects_prod_dir_flag(self, tmp_path: Path) -> None:
        """``--split --prod-dir X --test-dir Y`` should target X for prod
        and Y for test. We construct two empty dirs and a pyproject with
        permissive budgets; the ratchet must read them and report
        ``prod_dir``/``test_dir`` correctly in the JSON envelope (the
        only stable surface for asserting what was actually targeted).
        """
        prod = tmp_path / "src_pkg"
        test = tmp_path / "tests_alt"
        prod.mkdir()
        test.mkdir()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(prod),
                "--test-dir",
                str(test),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
        )

        summary = json.loads(result.stdout)
        assert summary["mode"] == "split"
        assert summary["prod_dir"] == str(prod)
        assert summary["test_dir"] == str(test)

    def test_split_mode_defaults_to_crackerjack_and_tests(self, tmp_path: Path) -> None:
        """Regression guard: when ``--prod-dir`` and ``--test-dir`` are
        not passed, the ratchet still defaults to ``crackerjack`` and
        ``tests`` (preserves the original CLI contract for direct
        callers).
        """
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
        )

        summary = json.loads(result.stdout)
        assert summary["prod_dir"] == "crackerjack"
        assert summary["test_dir"] == "tests"

    def test_split_json_envelope_includes_prod_dir_and_test_dir(
        self, tmp_path: Path
    ) -> None:
        """The JSON envelope advertises the resolved dirs so future CI
        consumers (or ``crackerjack run --json``) can show what was
        actually checked. Currently no consumer parses it, so this is
        purely additive.
        """
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                "src/custom_pkg",
                "--test-dir",
                "tests_unit",
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
        )

        envelope = json.loads(result.stdout)
        assert envelope["prod_dir"] == "src/custom_pkg"
        assert envelope["test_dir"] == "tests_unit"


class TestSplitModeMissingDirs:
    """``--split`` handles missing prod/test dirs gracefully.

    A missing dir produces a stderr warning and a vacuous-pass gate
    (0 ≤ any budget). No IO-error diagnostic leaks into the count.
    """

    def test_split_mode_missing_prod_dir_is_vacuous_pass(self, tmp_path: Path) -> None:
        """Missing prod dir → exit 0, prod count = 0, stderr warning."""
        prod_missing = tmp_path / "does_not_exist"
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(prod_missing),
                "--test-dir",
                str(test_dir),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
        )

        assert result.returncode == 0, (
            f"Vacuous-pass should exit 0; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )
        assert "does not exist" in result.stderr
        summary = json.loads(result.stdout)
        assert summary["prod"]["diagnostic_count"] == 0
        assert summary["prod"]["gate_passes"] is True
        assert summary["prod_dir_exists"] is False
        assert summary["test_dir_exists"] is True

    def test_split_mode_missing_test_dir_is_vacuous_pass(self, tmp_path: Path) -> None:
        """Missing test dir → exit 0, test count = 0, stderr warning."""
        prod_dir = tmp_path / "pkg"
        test_missing = tmp_path / "does_not_exist"
        prod_dir.mkdir()
        (prod_dir / "__init__.py").write_text("", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(prod_dir),
                "--test-dir",
                str(test_missing),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
        )

        assert result.returncode == 0
        assert "does not exist" in result.stderr
        summary = json.loads(result.stdout)
        assert summary["test"]["diagnostic_count"] == 0
        assert summary["test"]["gate_passes"] is True
        assert summary["test_dir_exists"] is False
        assert summary["prod_dir_exists"] is True

    def test_split_mode_both_dirs_missing_yields_exit_zero(
        self, tmp_path: Path
    ) -> None:
        """Both missing → exit 0, two stderr warnings."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(tmp_path / "missing_a"),
                "--test-dir",
                str(tmp_path / "missing_b"),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
        )

        assert result.returncode == 0
        # Two warnings (one per missing dir).
        assert result.stderr.count("does not exist") == 2
        summary = json.loads(result.stdout)
        assert summary["prod_dir_exists"] is False
        assert summary["test_dir_exists"] is False


class TestSplitModeVerboseNoTruncation:
    """``--verbose`` removes the ``[-20:]`` tail cap so operators see
    every diagnostic the wrapper captured. Default behaviour keeps
    the last-20 cap (legacy contract for plain runs).

    Authoritative count: ``Found N diagnostics`` from ty itself.
    Verbosity only changes whether the *detail lines* are bounded.
    """

    def test_split_verbose_flag_accepted(self, tmp_path: Path) -> None:
        """``--verbose`` flag is accepted by argparse and the JSON
        envelope is unaffected by the cap-or-no-cap mode."""
        prod = tmp_path / "src_pkg"
        test = tmp_path / "tests_alt"
        prod.mkdir()
        test.mkdir()
        (prod / "__init__.py").write_text("", encoding="utf-8")
        (test / "__init__.py").write_text("", encoding="utf-8")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\n"
            "ty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--verbose",
                "--prod-dir",
                str(prod),
                "--test-dir",
                str(test),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
        )

        # Verbose mode exits with gate result; what matters is no
        # flag-parsing crash. With budgets >= 1 and empty packages,
        # both gates pass and exit code is 0.
        assert result.returncode == 0, (
            f"--verbose must not crash; got {result.returncode}; "
            f"stderr={result.stderr!r}"
        )
        payload = json.loads(result.stdout)
        assert payload["prod_dir"] == str(prod)
        assert payload["test_dir"] == str(test)
        # JSON envelope is mode-agnostic — same keys in plain + verbose.
        assert "mode" in payload
        assert "prod" in payload
        assert "test" in payload

    def test_split_without_verbose_unchanged_envelope(self, tmp_path: Path) -> None:
        """Regression: plain (no ``--verbose``) still parses, same shape."""
        prod = tmp_path / "src_pkg"
        test = tmp_path / "tests_alt"
        prod.mkdir()
        test.mkdir()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\nty_max_errors_prod = 1000\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(prod),
                "--test-dir",
                str(test),
                "--pyproject",
                str(pyproject),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["prod_dir"] == str(prod)


class TestIncludeGlob:
    """``_include_glob`` builds the ``src.include`` override for a gate.

    Repos that scope ty with ``[tool.ty] src = { include = [...] }`` filter
    ty's whole file discovery, so ``ty check tests`` finds nothing. The
    ratchet passes an explicit include so each gate measures the directory
    it claims to measure.
    """

    def test_plain_relative_dir(self) -> None:
        assert _include_glob("tests") == "tests/**/*.py"

    def test_leading_dot_slash_is_stripped(self) -> None:
        assert _include_glob("./tests") == "tests/**/*.py"

    def test_trailing_slash_is_stripped(self) -> None:
        assert _include_glob("tests/") == "tests/**/*.py"

    def test_repo_root_covers_everything(self) -> None:
        assert _include_glob(".") == "**/*.py"

    def test_empty_string_covers_everything(self) -> None:
        assert _include_glob("") == "**/*.py"

    def test_absolute_dir_is_rebased_onto_the_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An absolute directory comes back relative to the working directory.

        The ratchet is invoked with ``--prod-dir``/``--test-dir`` that may
        be absolute, but ty's ``src.include`` is a repo-relative glob, so
        the path has to be rebased onto the cwd.
        """
        base = Path(tmp_path).resolve()
        monkeypatch.chdir(base)
        assert _include_glob(str(base / "pkg")) == "pkg/**/*.py"


class TestHasPythonFiles:
    """An empty directory and a filtered-out directory are different cases.

    A directory with no ``.py`` files is legitimately empty — zero
    diagnostics is the honest answer. A directory full of them that ty
    reports as containing nothing is a broken measurement.
    """

    def test_empty_directory_has_no_python_files(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert _has_python_files(str(empty)) is False

    def test_directory_with_python_file(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("x = 1\n", encoding="utf-8")
        assert _has_python_files(str(pkg)) is True

    def test_missing_directory(self, tmp_path: Path) -> None:
        assert _has_python_files(str(tmp_path / "nope")) is False


class TestSplitModeMeasuresFilteredDirectories:
    """The split gates must see files that a repo's ty config filters out.

    Regression: with ``src = { include = ["pkg/**/*.py"] }`` in place,
    ``ty check tests`` printed "No python files found" and exited 0, so the
    ratchet reported a fabricated "test: PASS (0/30)" over thousands of
    diagnostics it had never looked at.
    """

    def _make_repo(self, tmp_path: Path, ty_config: str) -> tuple[Path, Path]:
        pkg = tmp_path / "pkg"
        tests = tmp_path / "tests"
        pkg.mkdir()
        tests.mkdir()
        (tmp_path / "pyproject.toml").write_text(ty_config, encoding="utf-8")
        (pkg / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (tests / "test_mod.py").write_text(
            "def f() -> int:\n    return 'not an int'\n",
            encoding="utf-8",
        )
        return pkg, tests

    def _run(self, tmp_path: Path, pkg: Path, tests: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir",
                str(pkg),
                "--test-dir",
                str(tests),
                "--pyproject",
                str(tmp_path / "pyproject.toml"),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
            check=False,
        )
        return json.loads(result.stdout)

    def test_test_gate_counts_diagnostics_the_config_would_hide(
        self, tmp_path: Path
    ) -> None:
        """The test gate reports the real count, not zero."""
        pkg, tests = self._make_repo(
            tmp_path,
            '[tool.ty]\nsrc = { include = ["pkg/**/*.py"] }\n',
        )
        payload = self._run(tmp_path, pkg, tests)
        assert payload["test"]["diagnostic_count"] == 1, payload
        assert payload["test"]["gate_error"] is False

    def test_gate_error_when_ty_finds_nothing_in_a_populated_dir(
        self, tmp_path: Path
    ) -> None:
        """A populated directory ty could not see is an error, not a pass."""
        pkg, tests = self._make_repo(
            tmp_path,
            '[tool.ty.src]\nexclude = ["tests/**"]\n',
        )
        payload = self._run(tmp_path, pkg, tests)
        assert payload["test"]["gate_error"] is True, payload
        assert payload["test"]["gate_passes"] is False


class TestReadMaxErrorsIgnoresSplitKeys:
    """``ty_max_errors_prod``/``_test`` must not hijack the legacy budget.

    The legacy single-target path reads ``ty_max_errors``. If it matched
    the split keys first it would silently adopt the prod budget, so a repo
    with only split keys configured would run its legacy gate at the wrong
    threshold.
    """

    def test_split_keys_are_skipped(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\nty_max_errors_prod = 0\nty_max_errors_test = 564\n",
            encoding="utf-8",
        )
        assert _read_max_errors(pyproject) == 250

    def test_plain_key_is_still_read(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\nty_max_errors = 42\n", encoding="utf-8"
        )
        assert _read_max_errors(pyproject) == 42


class TestSplitModeBudgetIsTheGate:
    """The budget decides the gate; ty's exit code is not the gate.

    ty exits non-zero whenever it reports error-level diagnostics. A
    ratchet that also required ``returncode == 0`` would therefore reject
    every repo whose known diagnostics sit inside the budget — the
    allowance would be meaningless. A non-zero exit with *zero* diagnostics
    is the opposite case: ty could not run at all.
    """

    def _repo(self, tmp_path: Path, budget: int, errors: int = 1) -> Path:
        tests = tmp_path / "tests"
        tests.mkdir()
        (tmp_path / "pyproject.toml").write_text(
            f"[tool.crackerjack]\nty_max_errors_prod = 0\n"
            f"ty_max_errors_test = {budget}\n",
            encoding="utf-8",
        )
        for index in range(errors):
            (tests / f"test_{index}.py").write_text(
                "def f() -> int:\n    return 'not an int'\n",
                encoding="utf-8",
            )
        return tests

    def _payload(self, tmp_path: Path, tests: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir", str(tmp_path / "src_pkg"),
                "--test-dir", str(tests),
                "--pyproject", str(tmp_path / "pyproject.toml"),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
            check=False,
        )
        return json.loads(result.stdout)

    def test_count_at_budget_passes(self, tmp_path: Path) -> None:
        """A count equal to the budget is within the allowance."""
        tests = self._repo(tmp_path, budget=1)
        payload = self._payload(tmp_path, tests)
        assert payload["test"]["diagnostic_count"] == 1
        assert payload["test"]["gate_passes"] is True
        assert payload["test"]["gate_error"] is False

    def test_count_over_budget_fails(self, tmp_path: Path) -> None:
        """A count above the budget fails even though ty ran fine."""
        tests = self._repo(tmp_path, budget=1, errors=2)
        payload = self._payload(tmp_path, tests)
        assert payload["test"]["diagnostic_count"] == 2
        assert payload["test"]["gate_passes"] is False
        assert payload["test"]["gate_error"] is False

    def test_ty_that_could_not_run_is_a_gate_error(self, tmp_path: Path) -> None:
        """A broken ty config is a tooling error, not a clean measurement."""
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_x.py").write_text("x = 1\n", encoding="utf-8")
        # ty discovers its own config from the working directory, so the
        # broken config goes there; the budgets come from a separate file
        # passed with --pyproject.
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ty]\nenvironment = 'not-a-real-environment'\n",
            encoding="utf-8",
        )
        budgets = tmp_path / "budgets.toml"
        budgets.write_text(
            "[tool.crackerjack]\nty_max_errors_prod = 0\n"
            "ty_max_errors_test = 1000\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_ratchet",
                "--split",
                "--prod-dir", str(tmp_path / "src_pkg"),
                "--test-dir", str(tests),
                "--pyproject", str(budgets),
                "--json",
            ],
            capture_output=True,
            text=True,
            env=_SUBPROCESS_ENV,
            cwd=tmp_path,
            check=False,
        )
        payload = json.loads(result.stdout)
        assert payload["test"]["gate_error"] is True, payload
        assert payload["test"]["gate_passes"] is False
