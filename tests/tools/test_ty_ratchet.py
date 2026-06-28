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

from crackerjack.tools.ty_ratchet import (
    _count_diagnostics,
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
            f"Unexpected exit code {result.returncode}; "
            f"stderr={result.stderr!r}"
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
            f"--dry-run must exit 0; got {result.returncode}. "
            f"stderr={result.stderr!r}"
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
            "crackerjack/baz.py:7:1: error[unresolved-import] Cannot find ...\n"
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
