"""The store can answer "how often was the incremental path taken?".

Every run records the selection mode it used - ``incremental`` or
``full`` - but nothing surfaced it. The coverage ratchet skips exactly
when the run was incremental, so the count of incremental runs *is* the
count of ratchet skips: no separate record is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from crackerjack.services.testing.run_state_store import RunStateStore


def _record(
    store: RunStateStore,
    *,
    selection_mode: str,
    exit_code: int = 0,
    commit_sha: str = "abc123",
    repo: str = "crackerjack",
) -> str:
    now = datetime.now(UTC)
    return store.record_run(
        repo=repo,
        commit_sha=commit_sha,
        worktree="/w",
        branch="main",
        started_at=now,
        finished_at=now,
        exit_code=exit_code,
        selection_mode=selection_mode,
        tests=[{"node_id": "tests/test_a.py::t1", "status": "passed", "duration": 0.1}],
    )


class TestSummarize:
    def test_counts_runs_by_selection_mode(self, tmp_path: Path) -> None:
        store = RunStateStore(tmp_path / "run_state.db")
        _record(store, selection_mode="incremental")
        _record(store, selection_mode="incremental")
        _record(store, selection_mode="full")

        summary = store.summarize()

        assert summary["runs"] == 3
        assert summary["incremental"] == 2
        assert summary["full"] == 1

    def test_counts_failed_runs(self, tmp_path: Path) -> None:
        store = RunStateStore(tmp_path / "run_state.db")
        _record(store, selection_mode="full", exit_code=0)
        _record(store, selection_mode="incremental", exit_code=1)

        summary = store.summarize()

        assert summary["failed_runs"] == 1

    def test_can_be_narrowed_to_one_repo(self, tmp_path: Path) -> None:
        store = RunStateStore(tmp_path / "run_state.db")
        _record(store, selection_mode="incremental", repo="crackerjack")
        _record(store, selection_mode="full", repo="other")

        summary = store.summarize(repo="crackerjack")

        assert summary["runs"] == 1
        assert summary["incremental"] == 1

    def test_an_empty_store_summarises_to_zero(self, tmp_path: Path) -> None:
        store = RunStateStore(tmp_path / "run_state.db")

        summary = store.summarize()

        assert summary["runs"] == 0
        assert summary["incremental"] == 0
        assert summary["full"] == 0

    def test_an_unknown_selection_mode_is_counted_separately(
        self, tmp_path: Path
    ) -> None:
        store = RunStateStore(tmp_path / "run_state.db")
        _record(store, selection_mode="something-new")

        summary = store.summarize()

        assert summary["runs"] == 1
        assert summary["incremental"] == 0
        assert summary["full"] == 0
        assert summary["other"] == 1
