"""Tests for :class:`crackerjack.cli.base.CrackerjackCLI` BodaiCLIBase subclass.

Phase 3 Task 4.5 — BodaiCLIBase adoption for crackerjack. These tests
guard that the subclass wires up version/doctor/health correctly and that
the override hooks return real data (not ``{}`` or ``UNAVAILABLE`` stubs).
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from crackerjack.cli.base import CrackerjackCLI

runner = CliRunner()


def test_crackerjackcli_component_name() -> None:
    """The subclass must declare component_name='crackerjack'."""
    cli = CrackerjackCLI()
    assert cli.component_name == "crackerjack"


def test_crackerjackcli_inherits_typer() -> None:
    """BodaiCLIBase inherits typer.Typer, so CrackerjackCLI must too."""
    import typer

    assert issubclass(CrackerjackCLI, typer.Typer)


def test_doctor_checks_returns_real_entries() -> None:
    """_doctor_checks() must return a non-empty dict with real check entries.

    Not a stub that returns []. Per BodaiCLIBase contract, doctor must call
    into the repo's existing health surface.
    """
    cli = CrackerjackCLI()
    checks = cli._doctor_checks()
    assert isinstance(checks, dict)
    assert len(checks) > 0
    for label, info in checks.items():
        assert isinstance(info, dict)
        assert "status" in info
        assert "detail" in info


def test_doctor_checks_contains_expected_categories() -> None:
    """_doctor_checks() must include adapters/managers/services categories."""
    cli = CrackerjackCLI()
    checks = cli._doctor_checks()
    assert "adapters" in checks
    assert "managers" in checks
    assert "services" in checks


def test_health_probe_returns_real_snapshot() -> None:
    """_health_probe() must return a non-empty dict with status/component.

    Not a stub that raises NotImplementedError (-> UNAVAILABLE).
    """
    cli = CrackerjackCLI()
    snapshot = cli._health_probe()
    assert isinstance(snapshot, dict)
    assert snapshot.get("component") == "crackerjack"
    assert "status" in snapshot
    assert snapshot["status"] in {"healthy", "degraded", "unhealthy"}


def test_version_command_runs() -> None:
    """`crackerjack version` should print the component version."""
    cli = CrackerjackCLI()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "crackerjack" in result.stdout


def test_doctor_command_runs_and_outputs_checks() -> None:
    """`crackerjack doctor` must run via BodaiCLIBase and emit check info."""
    cli = CrackerjackCLI()
    result = runner.invoke(cli, ["doctor"])
    # exit_code 0 (all healthy) or 1 (some unhealthy) both acceptable; the
    # critical assertion is that doctor did NOT raise UNAVAILABLE (exit 3).
    assert result.exit_code in {0, 1}
    assert "adapters" in result.stdout or "managers" in result.stdout


def test_doctor_command_json_output() -> None:
    """`crackerjack --json doctor` must emit a JSON payload.

    BodaiCLIBase wires `--json` as a global option on the root callback;
    typer requires the global option to come BEFORE the subcommand.
    """
    cli = CrackerjackCLI()
    result = runner.invoke(cli, ["--json", "doctor"])
    assert result.exit_code in {0, 1}
    # Output is a JSON object containing a "checks" key.
    payload = json.loads(result.stdout)
    assert "checks" in payload
    assert isinstance(payload["checks"], dict)


def test_health_command_runs() -> None:
    """`crackerjack health` must run via BodaiCLIBase and emit a snapshot."""
    cli = CrackerjackCLI()
    result = runner.invoke(cli, ["health"])
    # Should NOT be UNAVAILABLE (3) — _health_probe is real.
    assert result.exit_code != 3
    assert "crackerjack" in result.stdout


def test_health_command_json_output() -> None:
    """`crackerjack --json health` must emit a JSON payload.

    BodaiCLIBase wires `--json` as a global option; it must precede the
    subcommand for typer to dispatch correctly.
    """
    cli = CrackerjackCLI()
    result = runner.invoke(cli, ["--json", "health"])
    assert result.exit_code != 3
    payload = json.loads(result.stdout)
    assert payload.get("component") == "crackerjack"


def test_bodai_cli_base_run_wires_typer() -> None:
    """BodaiCLIBase.run() wires up typer correctly.

    The base typer.Typer is callable. CrackerjackCLI inherits this
    behaviour, so invoking the cli with no args should NOT raise a
    Typer-specific error (it may print help and exit 0).
    """
    cli = CrackerjackCLI()
    # Calling the typer with no command should show help (exit 0 or 2).
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code in {0, 2}
    assert "crackerjack" in result.stdout.lower() or "Crackerjack" in result.stdout


def test_crackerjackcli_detects_version() -> None:
    """BodaiCLIBase._detect_version should resolve crackerjack's metadata."""
    cli = CrackerjackCLI()
    # Either a real version or the "(not installed)" sentinel.
    assert isinstance(cli.component_version, str)
    assert cli.component_version != ""
