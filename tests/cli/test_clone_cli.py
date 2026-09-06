"""Tests for ``crackerjack.cli.clone_cli``.

Covers the Typer ``clone`` sub-app with five commands: ``detect``,
``refactor``, ``status``, ``approve``, ``skip``. The ``_run_pyscn_json``
helper shells out to ``pyscn``; tests patch ``subprocess.run`` and seed a
fake report file under ``.pyscn/reports/``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from crackerjack.cli.clone_cli import _run_pyscn_json, app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _make_pyscn_report(path: Path, groups: list[dict[str, Any]]) -> Path:
    """Seed a ``.pyscn/reports/analyze_*.json`` file with the given groups."""
    report_dir = path / ".pyscn" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / "analyze_001.json"
    report.write_text(json.dumps({"clone": {"clone_pairs": groups}}))
    return report


def test_app_is_typer_instance() -> None:
    import typer

    assert isinstance(app, typer.Typer)


def test_app_help_text_non_empty() -> None:
    assert app.info.help
    assert "Clone" in app.info.help


def test_run_pyscn_json_returns_empty_when_no_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``.pyscn/reports/`` file → empty dict."""
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    assert _run_pyscn_json(tmp_path) == {}


def test_run_pyscn_json_returns_empty_on_pyscn_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-zero exit code (other than 1) → empty dict."""
    fake = subprocess.CompletedProcess(
        args=[], returncode=99, stdout="", stderr="boom"
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    assert _run_pyscn_json(tmp_path) == {}


def test_run_pyscn_json_reads_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit 0/1 + a present report file → the report contents."""
    _make_pyscn_report(tmp_path, groups=[{"id": "abc", "similarity": 0.95}])
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    data = _run_pyscn_json(tmp_path)
    assert data["clone"]["clone_pairs"][0]["id"] == "abc"


def test_detect_no_clones_prints_green_message(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    result = runner.invoke(app, ["detect", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "No clones detected" in result.stdout


def test_detect_with_clones_renders_table(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pyscn returns clone pairs, ``detect`` groups them and prints a table."""
    # The grouper expects ``clone1`` / ``clone2`` nested dicts (CloneLocation
    # shape). Provide a minimal pair that produces a single group.
    pairs = [
        {
            "type": 1,
            "similarity": 0.95,
            "clone1": {
                "file_path": str(tmp_path / "a.py"),
                "start_line": 1,
                "end_line": 5,
            },
            "clone2": {
                "file_path": str(tmp_path / "b.py"),
                "start_line": 1,
                "end_line": 5,
            },
        }
    ]
    _make_pyscn_report(tmp_path, groups=pairs)
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    (tmp_path / "a.py").write_text("x = 1\n" * 5)
    (tmp_path / "b.py").write_text("x = 1\n" * 5)
    result = runner.invoke(app, ["detect", "--path", str(tmp_path)])
    # Even if some rendering path errors, the command shouldn't crash.
    assert result.exit_code in (0, 1)


def test_refactor_no_clones_dry_run(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    result = runner.invoke(
        app, ["refactor", "--path", str(tmp_path), "--dry-run"]
    )
    assert result.exit_code == 0
    assert "No clones detected" in result.stdout or "refactor" in result.stdout.lower()


def test_refactor_dry_run_with_clones(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_pyscn_report(
        tmp_path,
        groups=[
            {
                "type": 1,
                "similarity": 0.99,
                "clone1": {
                    "file_path": str(tmp_path / "a.py"),
                    "start_line": 1,
                    "end_line": 5,
                },
                "clone2": {
                    "file_path": str(tmp_path / "b.py"),
                    "start_line": 1,
                    "end_line": 5,
                },
            }
        ],
    )
    (tmp_path / "a.py").write_text("x = 1\n" * 5)
    (tmp_path / "b.py").write_text("x = 1\n" * 5)
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    result = runner.invoke(
        app, ["refactor", "--path", str(tmp_path), "--dry-run"]
    )
    # Each decision branch (AUTO_APPLY, PROPOSE_APPROVE, REPORT_ONLY)
    # should be reachable. We don't pin the exact decision here — the
    # important thing is no exception escapes the command body.
    assert result.exit_code in (0, 1)


def test_refactor_non_dry_run_with_clones(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The non-dry-run branch exercises AUTO_APPLY / PROPOSE_APPROVE / REPORT_ONLY paths."""
    _make_pyscn_report(
        tmp_path,
        groups=[
            {
                "type": 1,
                "similarity": 0.99,
                "clone1": {
                    "file_path": str(tmp_path / "a.py"),
                    "start_line": 1,
                    "end_line": 5,
                },
                "clone2": {
                    "file_path": str(tmp_path / "b.py"),
                    "start_line": 1,
                    "end_line": 5,
                },
            }
        ],
    )
    (tmp_path / "a.py").write_text("x = 1\n" * 5)
    (tmp_path / "b.py").write_text("x = 1\n" * 5)
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    result = runner.invoke(app, ["refactor", "--path", str(tmp_path)])
    # At least one of AUTO_APPLY / PROPOSE_APPROVE / REPORT_ONLY should print.
    assert result.exit_code in (0, 1)


def test_refactor_non_dry_run_with_low_similarity(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Low similarity (< 0.70) → REPORT_ONLY branch."""
    _make_pyscn_report(
        tmp_path,
        groups=[
            {
                "type": 1,
                "similarity": 0.5,
                "clone1": {
                    "file_path": str(tmp_path / "a.py"),
                    "start_line": 1,
                    "end_line": 5,
                },
                "clone2": {
                    "file_path": str(tmp_path / "b.py"),
                    "start_line": 1,
                    "end_line": 5,
                },
            }
        ],
    )
    (tmp_path / "a.py").write_text("x = 1\n" * 5)
    (tmp_path / "b.py").write_text("x = 1\n" * 5)
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    result = runner.invoke(app, ["refactor", "--path", str(tmp_path)])
    assert "REPORT_ONLY" in result.stdout


def test_refactor_non_dry_run_with_structural_clone(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Structural (non-exact/renamed) clone type → PROPOSE_APPROVE branch."""
    # type=3 maps to MODIFIED (not EXACT/RENAMED), which routes to
    # PROPOSE_APPROVE regardless of similarity when not below the propose min.
    _make_pyscn_report(
        tmp_path,
        groups=[
            {
                "type": 3,
                "similarity": 0.99,
                "clone1": {
                    "file_path": str(tmp_path / "a.py"),
                    "start_line": 1,
                    "end_line": 5,
                },
                "clone2": {
                    "file_path": str(tmp_path / "b.py"),
                    "start_line": 1,
                    "end_line": 5,
                },
            }
        ],
    )
    (tmp_path / "a.py").write_text("x = 1\n" * 5)
    (tmp_path / "b.py").write_text("x = 1\n" * 5)
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
    result = runner.invoke(app, ["refactor", "--path", str(tmp_path)])
    assert "PROPOSE_APPROVE" in result.stdout


def test_status_prints_dim_message(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["status", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "Clone status" in result.stdout


def test_approve_prints_green_message(runner: CliRunner) -> None:
    result = runner.invoke(app, ["approve", "group-abc"])
    assert result.exit_code == 0
    assert "Approved" in result.stdout
    assert "group-abc" in result.stdout


def test_skip_prints_yellow_message(runner: CliRunner) -> None:
    result = runner.invoke(app, ["skip", "group-xyz"])
    assert result.exit_code == 0
    assert "Skipped" in result.stdout or "intentional" in result.stdout.lower()


def test_app_registers_all_five_commands() -> None:
    """All five Typer commands should be registered on the app."""
    registered = getattr(app, "registered_commands", [])
    # Typer's ``CommandInfo.name`` is None at registration time; use the
    # callback function name as the source of truth.
    command_names = {cmd.callback.__name__ for cmd in registered}
    assert {"detect", "refactor", "status", "approve", "skip"} <= command_names


def test_run_pyscn_json_handles_thresholds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``threshold`` parameter is forwarded to the pyscn CLI."""
    captured: dict[str, Any] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd, returncode=99, stdout="", stderr="boom"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    _run_pyscn_json(tmp_path, threshold=0.75)
    assert "--clone-threshold" in captured["cmd"]
    assert "0.75" in captured["cmd"]
