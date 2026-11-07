"""The async task store lives under XDG, and its legacy file is migrated.

``AsyncTaskSettings.storage_path`` used to resolve to
``~/.crackerjack/state/async_tasks.db`` - a path outside every XDG base
directory, so the test suite wrote into the developer's real home
directory on every run. The store now resolves under
``$XDG_DATA_HOME/crackerjack``, and the file left at the old path is
moved rather than stranded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.config.settings import AsyncTaskSettings


class TestAsyncTaskStorePath:
    def test_resolves_under_the_xdg_data_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

        settings = AsyncTaskSettings()

        assert settings.storage_path == tmp_path / "crackerjack" / "async_tasks.db"

    def test_does_not_resolve_under_the_legacy_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        settings = AsyncTaskSettings()

        assert ".crackerjack" not in str(settings.storage_path)


class TestLegacyAsyncTaskStoreMigration:
    def test_moves_the_legacy_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from crackerjack.mcp.persistence import migrate_legacy_async_task_store

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        legacy = tmp_path / "home" / ".crackerjack" / "state" / "async_tasks.db"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"legacy payload")
        target = tmp_path / "crackerjack" / "async_tasks.db"

        assert migrate_legacy_async_task_store(target) is True
        assert target.read_bytes() == b"legacy payload"
        assert not legacy.exists()

    def test_leaves_an_existing_target_alone(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from crackerjack.mcp.persistence import migrate_legacy_async_task_store

        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        legacy = tmp_path / "home" / ".crackerjack" / "state" / "async_tasks.db"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"legacy payload")
        target = tmp_path / "crackerjack" / "async_tasks.db"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"live")

        assert migrate_legacy_async_task_store(target) is False
        assert target.read_bytes() == b"live"
        assert legacy.exists()

    def test_is_a_no_op_without_a_legacy_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from crackerjack.mcp.persistence import migrate_legacy_async_task_store

        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        assert migrate_legacy_async_task_store(tmp_path / "crackerjack" / "async_tasks.db") is False
