"""Tests for the ``crackerjack run-state stats`` command and the
selection mode the ``show`` command reports.

Every run records the selection mode it used. Nothing surfaced it, so
"how often was the incremental path taken?" - the question the whole
test-selection feature exists to answer - had no query behind it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from crackerjack.cli.run_state_cli import app
from crackerjack.services.testing.run_state_store import RunStateStore

runner = CliRunner()


def _record(
    db_path: Path,
    *,
    selection_mode: str,
    commit_sha: str = "abc123",
    exit_code: int = 0,
) -> str:
    store = RunStateStore(db_path)
    now = datetime.now(UTC)
    return store.record_run(
        repo="crackerjack",
        commit_sha=commit_sha,
        worktree="/w",
        branch="main",
        started_at=now,
        finished_at=now,
        exit_code=exit_code,
        selection_mode=selection_mode,
        tests=[
            {"node_id": "tests/test_a.py::t1", "status": "passed", "duration": 0.01}
        ],
    )


class TestShowReportsTheSelectionMode:
    def test_show_prints_the_selection_mode(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"
        _record(db_path, selection_mode="incremental")

        result = runner.invoke(
            app,
            [
                "show",
                "--commit",
                "abc123",
                "--repo",
                "crackerjack",
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0
        assert "incremental" in result.stdout


class TestStats:
    def test_stats_counts_the_selection_modes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"
        _record(db_path, selection_mode="incremental")
        _record(db_path, selection_mode="incremental")
        _record(db_path, selection_mode="full")

        result = runner.invoke(app, ["stats", "--db-path", str(db_path)])

        assert result.exit_code == 0
        assert "3" in result.stdout
        assert "incremental" in result.stdout
        assert "full" in result.stdout

    def test_stats_reports_the_ratchet_skip_count(self, tmp_path: Path) -> None:
        """The ratchet skips exactly when a run was incremental, so the
        incremental count is the skip count."""
        db_path = tmp_path / "run_state.db"
        _record(db_path, selection_mode="incremental")
        _record(db_path, selection_mode="full")

        result = runner.invoke(app, ["stats", "--db-path", str(db_path)])

        assert result.exit_code == 0
        assert "ratchet" in result.stdout.lower()

    def test_stats_says_so_when_nothing_is_recorded(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"

        result = runner.invoke(app, ["stats", "--db-path", str(db_path)])

        assert result.exit_code == 0
        # Plainly, rather than a table of zeros that reads like a clean
        # result.
        assert "No recorded runs" in result.stdout

    def test_stats_can_be_narrowed_to_one_repo(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"
        _record(db_path, selection_mode="incremental")

        result = runner.invoke(
            app, ["stats", "--db-path", str(db_path), "--repo", "other-project"]
        )

        assert result.exit_code == 0
        assert "No recorded runs" in result.stdout
