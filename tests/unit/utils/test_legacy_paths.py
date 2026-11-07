"""Tests for the legacy-to-XDG migration helper.

The helper moves a file or a directory's contents from an old location
to its new one. The properties that matter: a move never destroys
data, a move that fails leaves the legacy copy intact, and a symlink is
not followed.
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.utils.legacy_paths import migrate_legacy_dir, migrate_legacy_file


class TestMigrateLegacyFile:
    def test_moves_a_legacy_file_when_the_target_is_absent(self, tmp_path: Path) -> None:
        legacy = tmp_path / "old" / "db.sqlite"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"payload")
        target = tmp_path / "new" / "db.sqlite"

        assert migrate_legacy_file(legacy, target) is True
        assert target.read_bytes() == b"payload"
        assert not legacy.exists()

    def test_leaves_an_existing_target_alone(self, tmp_path: Path) -> None:
        legacy = tmp_path / "old.sqlite"
        legacy.write_bytes(b"legacy")
        target = tmp_path / "new.sqlite"
        target.write_bytes(b"live")

        assert migrate_legacy_file(legacy, target) is False
        assert target.read_bytes() == b"live"
        assert legacy.exists()

    def test_an_absent_legacy_path_is_not_an_error(self, tmp_path: Path) -> None:
        assert migrate_legacy_file(tmp_path / "nope.sqlite", tmp_path / "new.sqlite") is False

    def test_a_legacy_symlink_is_not_followed(self, tmp_path: Path) -> None:
        real = tmp_path / "real.sqlite"
        real.write_bytes(b"payload")
        legacy = tmp_path / "legacy.sqlite"
        legacy.symlink_to(real)
        target = tmp_path / "new.sqlite"

        assert migrate_legacy_file(legacy, target) is False
        assert not target.exists()
        assert real.read_bytes() == b"payload"

    def test_a_legacy_directory_is_not_moved_as_a_file(self, tmp_path: Path) -> None:
        legacy = tmp_path / "old"
        legacy.mkdir()
        target = tmp_path / "new.sqlite"

        assert migrate_legacy_file(legacy, target) is False
        assert not target.exists()

    def test_a_failed_move_leaves_the_legacy_copy(self, tmp_path: Path) -> None:
        legacy = tmp_path / "old.sqlite"
        legacy.write_bytes(b"payload")
        # The target's parent is a file, so creating it must fail.
        blocker = tmp_path / "blocked"
        blocker.write_text("not a directory")
        target = blocker / "new.sqlite"

        assert migrate_legacy_file(legacy, target) is False
        assert legacy.read_bytes() == b"payload"


class TestMigrateLegacyDir:
    def test_moves_directory_contents_and_merges(self, tmp_path: Path) -> None:
        legacy = tmp_path / "old"
        (legacy / "run-a").mkdir(parents=True)
        (legacy / "run-a" / "events.jsonl").write_text("{}\n")
        target = tmp_path / "new"
        (target / "run-b").mkdir(parents=True)

        assert migrate_legacy_dir(legacy, target) is True
        assert (target / "run-a" / "events.jsonl").exists()
        assert (target / "run-b").is_dir()

    def test_removes_the_legacy_directory_once_it_is_empty(self, tmp_path: Path) -> None:
        legacy = tmp_path / "old"
        legacy.mkdir()
        (legacy / "child.txt").write_text("x")
        target = tmp_path / "new"

        assert migrate_legacy_dir(legacy, target) is True
        assert not legacy.exists()

    def test_keeps_a_child_that_already_exists_at_the_target(self, tmp_path: Path) -> None:
        legacy = tmp_path / "old"
        legacy.mkdir()
        (legacy / "child.txt").write_text("legacy")
        target = tmp_path / "new"
        target.mkdir()
        (target / "child.txt").write_text("live")

        assert migrate_legacy_dir(legacy, target) is False
        assert (target / "child.txt").read_text() == "live"
        assert (legacy / "child.txt").read_text() == "legacy"

    def test_an_absent_legacy_directory_is_not_an_error(self, tmp_path: Path) -> None:
        assert migrate_legacy_dir(tmp_path / "nope", tmp_path / "new") is False

    def test_a_legacy_file_is_not_migrated_as_a_directory(self, tmp_path: Path) -> None:
        legacy = tmp_path / "old"
        legacy.write_text("x")

        assert migrate_legacy_dir(legacy, tmp_path / "new") is False
