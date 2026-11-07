"""Tests for the commit-keyed run-state store.

The store answers "what was the test status of repo X at commit Y in
worktree Z?" with a query. These tests pin the parts that make that
answer trustworthy:

- a recorded run round-trips through the store,
- runs from different worktrees stay distinct,
- a commit with no recorded run returns ``None`` rather than an empty
  result that would read like "the run was empty",
- per-test results survive alongside the run summary.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from crackerjack.services.testing.run_state_store import (
    RunStateStore,
    load_pytest_json_report,
)


@pytest.fixture
def store(tmp_path: Path) -> RunStateStore:
    return RunStateStore(tmp_path / "run_state.db")


def _tests() -> list[dict[str, Any]]:
    return [
        {
            "node_id": "tests/test_a.py::test_one",
            "status": "passed",
            "duration": 0.01,
            "file_path": "tests/test_a.py",
            "error_message": None,
        },
        {
            "node_id": "tests/test_a.py::test_two",
            "status": "failed",
            "duration": 0.02,
            "file_path": "tests/test_a.py",
            "error_message": "AssertionError: boom",
        },
        {
            "node_id": "tests/test_a.py::test_three",
            "status": "skipped",
            "duration": 0.0,
            "file_path": "tests/test_a.py",
            "error_message": None,
        },
    ]


def _record(
    store: RunStateStore,
    *,
    commit_sha: str = "abc123",
    worktree: str = "/worktrees/one",
    tests: list[dict[str, Any]] | None = None,
) -> str:
    started = datetime.now(UTC)
    return store.record_run(
        repo="crackerjack",
        commit_sha=commit_sha,
        worktree=worktree,
        branch="main",
        started_at=started,
        finished_at=started + timedelta(seconds=12.5),
        exit_code=1,
        selection_mode="full",
        tests=_tests() if tests is None else tests,
    )


class TestRecordAndRetrieve:
    def test_record_run_then_get_run_roundtrips(self, store: RunStateStore) -> None:
        run_id = _record(store)

        run = store.get_run(repo="crackerjack", commit_sha="abc123")

        assert run is not None
        assert run["id"] == run_id
        assert run["repo"] == "crackerjack"
        assert run["commit_sha"] == "abc123"
        assert run["worktree"] == "/worktrees/one"
        assert run["branch"] == "main"
        assert run["exit_code"] == 1
        assert run["selection_mode"] == "full"
        assert run["total"] == 3
        assert run["passed"] == 1
        assert run["failed"] == 1
        assert run["skipped"] == 1
        assert run["errors"] == 0
        assert run["duration"] == pytest.approx(12.5)

    def test_record_run_persists_per_test_results(self, store: RunStateStore) -> None:
        run_id = _record(store)

        results = store.get_test_results(run_id)

        assert [result["node_id"] for result in results] == [
            "tests/test_a.py::test_one",
            "tests/test_a.py::test_three",
            "tests/test_a.py::test_two",
        ]
        by_node = {result["node_id"]: result for result in results}
        assert by_node["tests/test_a.py::test_two"]["status"] == "failed"
        assert (
            by_node["tests/test_a.py::test_two"]["error_message"]
            == "AssertionError: boom"
        )

    def test_status_map_is_the_diffing_primitive(self, store: RunStateStore) -> None:
        run_id = _record(store)

        status_map = store.get_status_map(run_id)

        assert status_map == {
            "tests/test_a.py::test_one": "passed",
            "tests/test_a.py::test_two": "failed",
            "tests/test_a.py::test_three": "skipped",
        }


class TestScoping:
    def test_runs_from_different_worktrees_are_distinct(
        self,
        store: RunStateStore,
    ) -> None:
        _record(store, worktree="/worktrees/one")
        _record(store, worktree="/worktrees/two")

        one = store.get_run(
            repo="crackerjack", commit_sha="abc123", worktree="/worktrees/one"
        )
        two = store.get_run(
            repo="crackerjack", commit_sha="abc123", worktree="/worktrees/two"
        )

        assert one is not None
        assert two is not None
        assert one["id"] != two["id"]

    def test_get_run_returns_none_for_unknown_commit(
        self, store: RunStateStore
    ) -> None:
        _record(store, commit_sha="abc123")

        run = store.get_run(repo="crackerjack", commit_sha="never-recorded")

        assert run is None

    def test_get_run_returns_none_for_unknown_repo(self, store: RunStateStore) -> None:
        _record(store)

        run = store.get_run(repo="some-other-repo", commit_sha="abc123")

        assert run is None

    def test_list_runs_returns_every_run_for_a_commit(
        self, store: RunStateStore
    ) -> None:
        first = _record(store, worktree="/worktrees/one")
        second = _record(store, worktree="/worktrees/two")

        runs = store.list_runs(repo="crackerjack", commit_sha="abc123")

        assert {run["id"] for run in runs} == {first, second}

    def test_empty_run_is_distinct_from_no_run(self, store: RunStateStore) -> None:
        _record(store, tests=[])

        run = store.get_run(repo="crackerjack", commit_sha="abc123")

        assert run is not None
        assert run["total"] == 0


class TestJsonReportLoading:
    def test_load_pytest_json_report_normalizes(self, tmp_path: Path) -> None:
        report = tmp_path / "last-run.json"
        report.write_text(
            """
            {
              "summary": {"passed": 1, "failed": 1, "total": 2},
              "tests": [
                {
                  "nodeid": "tests/test_a.py::TestA::test_one",
                  "outcome": "passed",
                  "setup": {"duration": 0.1, "outcome": "passed"},
                  "call": {"duration": 0.01, "outcome": "passed"},
                  "teardown": {"duration": 0.005, "outcome": "passed"}
                },
                {
                  "nodeid": "tests/test_a.py::TestA::test_two",
                  "outcome": "failed",
                  "setup": {"duration": 0.1, "outcome": "passed"},
                  "call": {"duration": 0.02, "outcome": "failed",
                           "longrepr": "AssertionError: boom"},
                  "teardown": {"duration": 0.005, "outcome": "passed"}
                }
              ]
            }
            """,
            encoding="utf-8",
        )

        parsed = load_pytest_json_report(report)

        assert parsed["summary"] == {"passed": 1, "failed": 1, "total": 2}
        assert len(parsed["tests"]) == 2
        assert parsed["tests"][0]["node_id"] == "tests/test_a.py::TestA::test_one"
        assert parsed["tests"][0]["status"] == "passed"
        assert parsed["tests"][0]["file_path"] == "tests/test_a.py"
        assert parsed["tests"][0]["duration"] == pytest.approx(0.115)
        assert parsed["tests"][1]["error_message"] == "AssertionError: boom"

    def test_load_missing_report_yields_no_tests(self, tmp_path: Path) -> None:
        parsed = load_pytest_json_report(tmp_path / "does-not-exist.json")

        assert parsed == {"tests": [], "summary": {}, "available": False}

    def test_load_malformed_report_yields_no_tests(self, tmp_path: Path) -> None:
        report = tmp_path / "last-run.json"
        report.write_text("{not json", encoding="utf-8")

        parsed = load_pytest_json_report(report)

        assert parsed == {"tests": [], "summary": {}, "available": False}

    def test_an_empty_but_readable_report_is_available(self, tmp_path: Path) -> None:
        """A report with no tests is not the same as no report.

        An incremental run whose change affects nothing writes a real
        report with an empty ``tests`` list. The caller has to be able to
        tell that apart from a report it could not read.
        """
        report = tmp_path / "last-run.json"
        report.write_text(
            json.dumps({"summary": {"total": 0, "collected": 0}, "tests": []}),
            encoding="utf-8",
        )

        parsed = load_pytest_json_report(report)

        assert parsed["tests"] == []
        assert parsed["available"] is True
        assert parsed["summary"] == {"total": 0, "collected": 0}


class TestPathRedaction:
    """A recorded run's log line must not disclose the OS account name.

    The worktree path is absolute and lands in a log line that lands in
    log files on disk. The repo has a standing rule against disclosing
    home-directory paths in output (``crackerjack.utils.path_redaction``).
    """

    def test_the_recorded_run_log_does_not_disclose_the_home_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        home = tmp_path / "home"
        (home / "Projects" / "crackerjack").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        worktree = home / "Projects" / "crackerjack"

        store = RunStateStore(tmp_path / "run_state.db")
        with caplog.at_level(
            logging.INFO, logger="crackerjack.services.testing.run_state_store"
        ):
            store.record_run(
                repo="crackerjack",
                commit_sha="abc1234",
                worktree=str(worktree),
                branch="main",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                exit_code=0,
                selection_mode="incremental",
                tests=[{"node_id": "tests/test_a.py::test_one", "status": "passed"}],
            )

        assert str(home) not in caplog.text, (
            f"the home directory leaked into the run-state log: {caplog.text}"
        )
        assert "~/Projects/crackerjack" in caplog.text, (
            f"the worktree was not rendered home-relative: {caplog.text}"
        )
