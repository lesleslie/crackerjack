"""The log directory lives under XDG, not in the project tree.

Logs are state and history, not a cache: they grow without bound and
they are worth keeping. The project-local `.crackerjack/logs` was
gitignored, so `git clean -fd` took them away. They now resolve under
`$XDG_STATE_HOME/crackerjack/logs` - note *state*, not the cache tier
the previous fallback used.

The project-local directory stays in the chain as a fallback, for a
checkout that cannot write to the state directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.services.log_manager import LogManager


class TestLogDirectory:
    def test_resolves_under_the_xdg_state_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

        manager = LogManager()

        assert manager.log_dir == tmp_path / "state" / "crackerjack" / "logs"

    def test_does_not_use_the_cache_tier(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

        manager = LogManager()

        assert not manager.log_dir.is_relative_to(tmp_path / "cache")
        assert manager.log_dir != tmp_path / "cache" / "crackerjack" / "logs"

    def test_creates_its_subdirectories(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

        manager = LogManager()

        for name in ("debug", "error", "audit"):
            assert (manager.log_dir / name).is_dir()


class TestLegacyLogDirectoryMigration:
    def test_moves_the_project_local_logs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from crackerjack.services.log_manager import migrate_legacy_logs

        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        legacy = tmp_path / "project" / ".crackerjack" / "logs"
        (legacy / "debug").mkdir(parents=True)
        (legacy / "debug" / "old.log").write_text("history")

        assert migrate_legacy_logs(tmp_path / "project") is True
        assert (
            tmp_path / "state" / "crackerjack" / "logs" / "debug" / "old.log"
        ).exists()
        assert not legacy.exists()

    def test_leaves_an_existing_log_alone(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from crackerjack.services.log_manager import migrate_legacy_logs

        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        legacy = tmp_path / "project" / ".crackerjack" / "logs"
        legacy.mkdir(parents=True)
        (legacy / "old.log").write_text("legacy")
        target = tmp_path / "state" / "crackerjack" / "logs"
        target.mkdir(parents=True)
        (target / "old.log").write_text("live")

        assert migrate_legacy_logs(tmp_path / "project") is False
        assert (target / "old.log").read_text() == "live"
        assert (legacy / "old.log").read_text() == "legacy"

    def test_is_a_no_op_without_a_legacy_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from crackerjack.services.log_manager import migrate_legacy_logs

        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

        assert migrate_legacy_logs(tmp_path / "project") is False

    def test_importing_the_module_does_not_move_the_logs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A module-level LogManager must not migrate at import time.

        The module builds one when it is imported. A migration there
        would move the project's logs during an import - and, in a test
        session that redirects ``XDG_STATE_HOME`` into a temporary
        sandbox, move them somewhere that is about to be deleted.
        """
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        monkeypatch.chdir(tmp_path)
        legacy = tmp_path / ".crackerjack" / "logs"
        legacy.mkdir(parents=True)
        (legacy / "old.log").write_text("history")

        import importlib

        import crackerjack.services.log_manager as log_manager_module

        importlib.reload(log_manager_module)

        assert (legacy / "old.log").exists()
