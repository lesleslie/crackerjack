"""The AI-fix run history lives under XDG, not in the project tree.

``runs/<run_id>/events.jsonl`` is append-only history that grows without
bound. It used to live in the project's ``.crackerjack/`` directory,
which is gitignored - so ``git clean -fd`` destroyed it. The decision
record puts it under ``$XDG_STATE_HOME/crackerjack/runs``: state and
history, not a cache, and not something a clean can take away.

An explicit ``base_dir`` still wins, so a caller that wants a run
directory somewhere specific keeps getting it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.core.ai_fix_sinks import JsonlSink, detect_orphan_sidecars, runs_root


class TestRunsRoot:
    def test_resolves_under_the_xdg_state_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

        assert runs_root() == tmp_path / "crackerjack" / "runs"

    def test_an_explicit_base_dir_still_wins(self, tmp_path: Path) -> None:
        assert runs_root(tmp_path) == tmp_path / ".crackerjack" / "runs"


class TestJsonlSinkResolvesTheStateHome:
    def test_writes_its_events_under_the_xdg_state_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

        sink = JsonlSink()
        sink._open("run-1")

        assert (tmp_path / "crackerjack" / "runs" / "run-1" / "events.jsonl").exists()
        sink.close()

    def test_an_explicit_base_dir_is_unchanged(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        sink._open("run-1")

        assert (tmp_path / ".crackerjack" / "runs" / "run-1" / "events.jsonl").exists()
        sink.close()

    async def test_restore_run_finds_a_run_under_the_state_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from crackerjack.core.ai_fix_sinks import RunStarted

        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        sink = JsonlSink()
        await sink.handle(RunStarted(run_id="run-1", iteration=0))
        sink.close()

        restored = list(JsonlSink.restore_run("run-1"))

        assert len(restored) == 1

    def test_detect_orphan_sidecars_scans_the_state_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        run_dir = tmp_path / "crackerjack" / "runs" / "run-1"
        run_dir.mkdir(parents=True)
        (run_dir / "events.jsonl").write_text("{}\n")
        (run_dir / ".open").write_text("1")

        assert detect_orphan_sidecars() == ["run-1"]
