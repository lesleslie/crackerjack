from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from crackerjack.cli.coverage_ratchet_cli import app


runner = CliRunner()


@pytest.mark.unit
def test_init_creates_ratchet_at_current_coverage(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 47.5}})
    )
    result = runner.invoke(app, ["init", "--pkg-path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    ratchet = json.loads((tmp_path / ".coverage-ratchet.json").read_text())
    assert ratchet["baseline"] == 47.5
    assert ratchet["current_minimum"] == 47.5


@pytest.mark.unit
def test_init_refuses_overwrite_without_reinit(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 50.0}})
    )
    (tmp_path / ".coverage-ratchet.json").write_text(
        json.dumps({"baseline": 50.0, "current_minimum": 50.0})
    )
    result = runner.invoke(app, ["init", "--pkg-path", str(tmp_path)])
    assert result.exit_code != 0, result.output


@pytest.mark.unit
def test_lower_requires_reason(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 50.0}})
    )
    init_result = runner.invoke(app, ["init", "--pkg-path", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    result = runner.invoke(
        app, ["lower", "--to", "45.0", "--pkg-path", str(tmp_path)]
    )
    assert result.exit_code != 0, result.output


@pytest.mark.unit
def test_lower_with_reason_succeeds(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 50.0}})
    )
    init_result = runner.invoke(app, ["init", "--pkg-path", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    result = runner.invoke(
        app,
        [
            "lower",
            "--to",
            "45.0",
            "--reason",
            "reverted untested prototype",
            "--pkg-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads((tmp_path / ".coverage-ratchet.json").read_text())
    assert data["current_minimum"] == 45.0


@pytest.mark.unit
def test_status_prints_ratchet_state(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 50.0}})
    )
    init_result = runner.invoke(app, ["init", "--pkg-path", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    result = runner.invoke(app, ["status", "--pkg-path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Baseline" in result.output or "50" in result.output


@pytest.mark.unit
def test_migrate_prints_hint(tmp_path: Path) -> None:
    result = runner.invoke(app, ["migrate"])
    assert result.exit_code == 0, result.output
    assert "temporary" in result.output.lower()
