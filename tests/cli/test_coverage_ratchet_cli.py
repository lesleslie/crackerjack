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
    # The enforced floor is the whole point below the measurement, not
    # the measurement itself.
    assert ratchet["baseline"] == 47.0
    assert ratchet["current_minimum"] == 47.0


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
def test_init_with_reinit_actually_rewrites_the_ratchet(tmp_path: Path) -> None:
    """``--reinit`` must rewrite the file, not just report that it did.

    The command's own "already exists" guard was the only thing
    ``--reinit`` bypassed; the write underneath it early-returned, so
    the ratchet came out byte-identical while the command printed
    "Ratchet initialized" and mirrored a new floor into pyproject.
    """
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 62.0}})
    )
    (tmp_path / ".coverage-ratchet.json").write_text(
        json.dumps({"baseline": 50.0, "current_minimum": 50.0})
    )
    before = (tmp_path / ".coverage-ratchet.json").read_text()

    result = runner.invoke(app, ["init", "--reinit", "--pkg-path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    after = (tmp_path / ".coverage-ratchet.json").read_text()
    assert after != before, "the ratchet was not rewritten"
    ratchet = json.loads(after)
    assert ratchet["baseline"] == 62.0
    assert ratchet["current_minimum"] == 62.0


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
def test_init_trims_trailing_whitespace_and_newlines(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 50.0}})
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=80"'
        "\n\n\n"  # multiple trailing newlines
    )
    result = runner.invoke(app, ["init", "--pkg-path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    content = (tmp_path / "pyproject.toml").read_text()
    # Single trailing newline, no whitespace-only trailing lines
    assert content.endswith("\n")
    assert not content.endswith("\n\n")
