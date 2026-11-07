"""Tests for the ``crackerjack run-state`` command.

The point of the run-state store is that "what was the test status at
commit X" is a question you can ask. These tests pin that the CLI answers
it - and, just as importantly, that it says so plainly when there is no
recorded run rather than printing an empty table that reads like success.
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
    commit_sha: str,
    worktree: str,
    tests: list[dict[str, Any]],
) -> str:
    store = RunStateStore(db_path)
    now = datetime.now(UTC)
    return store.record_run(
        repo="crackerjack",
        commit_sha=commit_sha,
        worktree=worktree,
        branch="main",
        started_at=now,
        finished_at=now,
        exit_code=0,
        selection_mode="full",
        tests=tests,
    )


def _test(node_id: str, status: str) -> dict[str, Any]:
    return {"node_id": node_id, "status": status, "duration": 0.01}


class TestShow:
    def test_show_reports_no_recorded_run(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"

        result = runner.invoke(
            app,
            [
                "show",
                "--commit",
                "deadbeef",
                "--repo",
                "crackerjack",
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "no recorded run" in result.output.lower()
        assert "deadbeef" in result.output

    def test_show_lists_recorded_tests(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"
        _record(
            db_path,
            commit_sha="abc123",
            worktree=str(tmp_path),
            tests=[
                _test("tests/test_a.py::test_one", "passed"),
                _test("tests/test_a.py::test_two", "failed"),
            ],
        )

        result = runner.invoke(
            app,
            [
                "show",
                "--commit",
                "abc123",
                "--repo",
                "crackerjack",
                "--worktree",
                str(tmp_path),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "tests/test_a.py::test_one" in result.output
        assert "tests/test_a.py::test_two" in result.output
        assert "passed" in result.output
        assert "failed" in result.output

    def test_show_reports_a_summary(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"
        _record(
            db_path,
            commit_sha="abc123",
            worktree=str(tmp_path),
            tests=[
                _test("tests/test_a.py::test_one", "passed"),
                _test("tests/test_a.py::test_two", "failed"),
            ],
        )

        result = runner.invoke(
            app,
            [
                "show",
                "--commit",
                "abc123",
                "--repo",
                "crackerjack",
                "--worktree",
                str(tmp_path),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "2" in result.output

    def test_a_long_node_id_is_not_wrapped(self, tmp_path: Path) -> None:
        """A wrapped node id cannot be pasted back into a pytest selector.

        The whole point of printing node ids is to copy one back into a
        command line, so the console must not fold them across lines.
        """
        db_path = tmp_path / "run_state.db"
        long_node_id = (
            "tests/unit/managers/test_test_manager_coverage.py::"
            "TestCoverageManagerReports::test_a_long_name_that_will_not_fit"
        )
        _record(
            db_path,
            commit_sha="abc123",
            worktree=str(tmp_path),
            tests=[_test(long_node_id, "passed")],
        )

        result = runner.invoke(
            app,
            [
                "show",
                "--commit",
                "abc123",
                "--repo",
                "crackerjack",
                "--worktree",
                str(tmp_path),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert long_node_id in result.output, (
            "the node id was folded across lines, so it cannot be copied "
            "back into a pytest selector"
        )


class TestCLIRegistration:
    """``run-state`` must be reachable through the real ``crackerjack`` CLI.

    ``crackerjack/__main__.py`` registers sub-apps through
    ``_safe_add_typer``, which logs a warning and returns instead of
    raising when the module cannot be imported. A broken import would
    therefore drop the command silently - the sub-app's own tests would
    still pass, because they import the sub-app directly. These guard the
    wiring itself.
    """

    def test_run_state_is_reachable_from_the_main_cli(self) -> None:
        from crackerjack.__main__ import app

        result = CliRunner().invoke(app, ["run-state", "--help"])

        assert result.exit_code == 0, result.output
        assert "run-state" in result.output

    def test_run_state_exposes_show_and_diff(self) -> None:
        from crackerjack.__main__ import app

        result = CliRunner().invoke(app, ["run-state", "--help"])

        assert result.exit_code == 0, result.output
        assert "show" in result.output
        assert "diff" in result.output


class TestDiff:
    def test_diff_reports_changed_tests(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"
        _record(
            db_path,
            commit_sha="base001",
            worktree=str(tmp_path),
            tests=[
                _test("tests/test_a.py::test_one", "passed"),
                _test("tests/test_a.py::test_two", "passed"),
            ],
        )
        _record(
            db_path,
            commit_sha="head001",
            worktree=str(tmp_path),
            tests=[
                _test("tests/test_a.py::test_one", "passed"),
                _test("tests/test_a.py::test_two", "failed"),
            ],
        )

        result = runner.invoke(
            app,
            [
                "diff",
                "--base",
                "base001",
                "--commit",
                "head001",
                "--repo",
                "crackerjack",
                "--worktree",
                str(tmp_path),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "tests/test_a.py::test_two" in result.output
        assert "tests/test_a.py::test_one" not in result.output

    def test_diff_reports_no_changes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"
        _record(
            db_path,
            commit_sha="base001",
            worktree=str(tmp_path),
            tests=[_test("tests/test_a.py::test_one", "passed")],
        )
        _record(
            db_path,
            commit_sha="head001",
            worktree=str(tmp_path),
            tests=[_test("tests/test_a.py::test_one", "passed")],
        )

        result = runner.invoke(
            app,
            [
                "diff",
                "--base",
                "base001",
                "--commit",
                "head001",
                "--repo",
                "crackerjack",
                "--worktree",
                str(tmp_path),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "no status changes" in result.output.lower()

    def test_diff_reports_missing_base_run(self, tmp_path: Path) -> None:
        db_path = tmp_path / "run_state.db"
        _record(
            db_path,
            commit_sha="head001",
            worktree=str(tmp_path),
            tests=[_test("tests/test_a.py::test_one", "passed")],
        )

        result = runner.invoke(
            app,
            [
                "diff",
                "--base",
                "never-recorded",
                "--commit",
                "head001",
                "--repo",
                "crackerjack",
                "--worktree",
                str(tmp_path),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "no recorded run" in result.output.lower()
