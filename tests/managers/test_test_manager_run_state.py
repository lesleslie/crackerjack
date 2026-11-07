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


def _write_report(project: Path, tests: list[dict[str, Any]]) -> Path:
    report_path = project / ".crackerjack" / "last-run.json"
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
        _write_report(
            project,
            [
                {
                    "nodeid": "tests/test_a.py::test_one",
                    "outcome": "passed",
                    "duration": 0.01,
                    "location": ["tests/test_a.py", 3, "test_one"],
                }
            ],
        )

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
        _write_report(
            project,
            [{"nodeid": "tests/test_a.py::test_one", "outcome": "passed", "duration": 0.01}],
        )

        with patch.object(
            manager,
            "_execute_test_workflow",
            return_value=subprocess.CompletedProcess(
                args=["pytest"], returncode=0, stdout="1 passed", stderr=""
            ),
        ):
            result = manager._run_pytest_if_needed(True, _options(), 0.0)

        assert result is True


def _head_sha(project: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
