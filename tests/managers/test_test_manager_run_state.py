"""The test phase records its per-test results in the run-state store.

After a run, "what was the test status of this repo at this commit?"
must be a query, not another suite run. That requires the test phase to
write what it observed, every time it runs - including when the run was
incremental, when the run produced no JSON report, and when the store
itself is broken.

Recording must never fail a test run: a store error is logged and the
phase's own result stands.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from crackerjack.managers.test_command_builder import TestCommandBuilder
from crackerjack.managers.test_manager import TestManager
from crackerjack.services.testing.run_state_store import RunStateStore

PROJECT_NAME = "testproject"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A throwaway git repository, so commit resolution has something to read."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("x\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "testproject"\nversion = "0.0.0"\n'
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


def _manager(project: Path, db_path: Path) -> TestManager:
    return TestManager(
        pkg_path=project,
        command_builder=TestCommandBuilder(pkg_path=project),
        run_state_db_path=db_path,
    )


def _options(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "incremental_tests": True,
        "test_workers": 1,
        "benchmark": False,
        "verbose": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _write_report(report_path: Path, tests: list[dict[str, Any]]) -> Path:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "summary": {"passed": 1, "failed": 0, "total": 1},
                "tests": tests,
            }
        ),
        encoding="utf-8",
    )
    return report_path


class TestRecording:
    def test_test_phase_records_run_state(self, project: Path) -> None:
        db_path = project / "run_state.db"
        manager = _manager(project, db_path)
        report = [
            {
                "nodeid": "tests/test_a.py::test_one",
                "outcome": "passed",
                "duration": 0.01,
                "location": ["tests/test_a.py", 3, "test_one"],
            }
        ]

        def _execute(options: Any) -> subprocess.CompletedProcess[str]:
            # pytest writes the report while the run is in progress.
            _write_report(manager.command_builder.get_json_report_path(), report)
            return subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="1 passed", stderr=""
            )

        with patch.object(manager, "_execute_test_workflow", side_effect=_execute):
            result = manager._run_pytest_if_needed(True, _options(), 0.0)

        assert result is True

        store = RunStateStore(db_path)
        run = store.get_run(repo=PROJECT_NAME, commit_sha=_head_sha(project))
        assert run is not None
        assert run["total"] == 1
        assert run["passed"] == 1
        assert run["exit_code"] == 0
        assert run["selection_mode"] == "incremental"
        assert run["worktree"] == str(project)

        results = store.get_test_results(run["id"])
        assert [r["node_id"] for r in results] == ["tests/test_a.py::test_one"]
        assert results[0]["status"] == "passed"

    def test_missing_json_report_still_records_a_run(self, project: Path) -> None:
        db_path = project / "run_state.db"
        manager = _manager(project, db_path)

        with patch.object(
            manager,
            "_execute_test_workflow",
            return_value=subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="1 passed", stderr=""
            ),
        ):
            result = manager._run_pytest_if_needed(True, _options(), 0.0)

        assert result is True

        store = RunStateStore(db_path)
        run = store.get_run(repo=PROJECT_NAME, commit_sha=_head_sha(project))
        assert run is not None
        assert run["total"] == 0

    def test_recording_failure_does_not_fail_the_run(self, project: Path) -> None:
        # A store path that cannot be created: the directory is a file.
        blocked = project / "blocked"
        blocked.write_text("not a directory\n")
        manager = _manager(project, blocked / "run_state.db")

        def _execute(options: Any) -> subprocess.CompletedProcess[str]:
            _write_report(
                manager.command_builder.get_json_report_path(),
                [
                    {
                        "nodeid": "tests/test_a.py::test_one",
                        "outcome": "passed",
                        "duration": 0.01,
                    }
                ],
            )
            return subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="1 passed", stderr=""
            )

        with patch.object(manager, "_execute_test_workflow", side_effect=_execute):
            result = manager._run_pytest_if_needed(True, _options(), 0.0)

        assert result is True


class TestStaleReportIsNotRead:
    """The report the phase reads must be the one this run produced.

    Each run writes its own report file, so a report left behind by an
    earlier run - or by a run that was killed before pytest wrote its
    report - sits at a different path and cannot be read as this run's
    result. A stale report carrying a passing test would otherwise turn
    "this run observed nothing" into "this run observed one passing test".
    """

    def test_a_report_from_an_earlier_run_is_not_read_as_this_run(
        self, project: Path
    ) -> None:
        db_path = project / "run_state.db"
        manager = _manager(project, db_path)

        # A report left behind by an earlier run, at that run's path.
        stale_path = manager.command_builder.get_json_report_path()
        _write_report(
            stale_path,
            [
                {
                    "nodeid": "tests/test_a.py::test_one",
                    "outcome": "passed",
                    "duration": 0.01,
                }
            ],
        )

        with patch.object(
            manager,
            "_execute_test_workflow",
            return_value=subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="no tests ran", stderr=""
            ),
        ):
            result = manager._run_pytest_if_needed(True, _options(), 0.0)

        assert result is True

        store = RunStateStore(db_path)
        run = store.get_run(repo=PROJECT_NAME, commit_sha=_head_sha(project))
        assert run is not None
        assert run["total"] == 0, (
            "the run recorded a stale report's tests instead of the ones "
            "this run observed"
        )


class TestPathRedaction:
    """A store failure must not disclose the OS account name.

    The failure log interpolates the store's absolute path, which lives
    under the user's home directory. The repo has a standing rule against
    disclosing home-directory paths in output: every path a message
    interpolates goes through ``crackerjack.utils.path_redaction``.

    The assertion is on the interpolated *message*. The stdlib's own
    exception text inside the traceback still names the path - that is a
    repo-wide gap (``logger.exception`` renders the original message),
    not something this call site introduces.
    """

    def test_the_failure_log_does_not_disclose_the_home_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        home = tmp_path / "home"
        (home / ".local" / "share").mkdir(parents=True)
        # A file where the store's parent directory should be: the
        # database cannot be created, so recording fails.
        (home / ".local" / "share" / "crackerjack").write_text("not a directory\n")
        monkeypatch.setenv("HOME", str(home))

        db_path = home / ".local" / "share" / "crackerjack" / "run_state.db"
        manager = TestManager(pkg_path=tmp_path, run_state_db_path=db_path)

        with (
            caplog.at_level(logging.ERROR),
            patch.object(
                manager,
                "_execute_test_workflow",
                return_value=subprocess.CompletedProcess(
                    args=["pytest"], returncode=0, stdout="1 passed", stderr=""
                ),
            ),
        ):
            result = manager._run_pytest_if_needed(True, _options(), 0.0)

        assert result is True
        messages = [record.getMessage() for record in caplog.records]
        assert messages, "the store failure was not logged at all"
        joined = " ".join(messages)
        assert str(home) not in joined, (
            f"the home directory leaked into the failure message: {joined}"
        )
        assert any(
            "~/.local/share/crackerjack/run_state.db" in message for message in messages
        ), f"the store path was not rendered home-relative: {joined}"

    def test_the_rendered_log_record_does_not_disclose_the_home_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The whole rendered record, traceback and all, must be clean.

        The exception's own text names the absolute path, so the log line
        carries the exception *type* rather than the exception, and no
        traceback.
        """
        import logging

        home = tmp_path / "home"
        (home / ".local" / "share").mkdir(parents=True)
        (home / ".local" / "share" / "crackerjack").write_text("not a directory\n")
        monkeypatch.setenv("HOME", str(home))

        db_path = home / ".local" / "share" / "crackerjack" / "run_state.db"
        manager = TestManager(pkg_path=tmp_path, run_state_db_path=db_path)

        with (
            caplog.at_level(logging.ERROR),
            patch.object(
                manager,
                "_execute_test_workflow",
                return_value=subprocess.CompletedProcess(
                    args=["pytest"], returncode=0, stdout="1 passed", stderr=""
                ),
            ),
        ):
            manager._run_pytest_if_needed(True, _options(), 0.0)

        assert str(home) not in caplog.text, (
            f"the home directory leaked into the rendered log record: {caplog.text}"
        )
        for record in caplog.records:
            assert not record.exc_info, (
                "the failure log still carries a traceback, and the "
                f"exception's own text names the absolute path: {record.exc_info}"
            )


class TestRunReportIsCleanedUp:
    """The run's report file must not outlive the run.

    It holds the per-test results of the working tree, so it is runtime
    state in the project directory rather than something to leave behind.
    """

    def test_the_report_is_removed_after_the_run(self, project: Path) -> None:
        db_path = project / "run_state.db"
        manager = _manager(project, db_path)

        def _execute(options: Any) -> subprocess.CompletedProcess[str]:
            report_path = manager.command_builder.get_json_report_path()
            _write_report(
                report_path,
                [{"nodeid": "tests/test_a.py::test_one", "outcome": "passed"}],
            )
            return subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="1 passed", stderr=""
            )

        with patch.object(manager, "_execute_test_workflow", side_effect=_execute):
            manager._run_pytest_if_needed(True, _options(), 0.0)

        assert not manager.command_builder.get_json_report_path().exists()


def _head_sha(project: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
