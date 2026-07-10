"""Tests for the WorkingTreeSnapshot rollback layer.

The snapshot captures ``HEAD`` SHA + content of every tracked-dirty
file at the moment of ``take()``. ``restore()`` writes the captured
content back so the AI-fix run cannot leave the working tree in a
worse state than it found it. Untracked files are deliberately
ignored — we don't want to delete user work-in-progress if the
ai-fix run happens to touch a directory they were editing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from crackerjack.ai_fix.working_tree_snapshot import WorkingTreeSnapshot


def _git(cwd: Path, *args: str) -> str:
    """Run ``git <args>`` in ``cwd`` and return stdout (stripped)."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A real git repo with one commit + one tracked file."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "tracked.txt").write_text("original content\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-q", "-m", "initial commit")
    return tmp_path


class TestWorkingTreeSnapshot:
    def test_take_captures_head_sha(self, git_repo: Path) -> None:
        """``head_sha`` matches ``git rev-parse HEAD`` after ``take()``."""
        expected = _git(git_repo, "rev-parse", "HEAD")
        snapshot = WorkingTreeSnapshot(git_repo).take()
        assert snapshot.head_sha == expected

    def test_take_captures_dirty_file_content(self, git_repo: Path) -> None:
        """Modifying a tracked file before ``take()`` captures its content."""
        tracked = git_repo / "tracked.txt"
        tracked.write_text("user was editing this\n", encoding="utf-8")

        snapshot = WorkingTreeSnapshot(git_repo).take()

        assert tracked in snapshot.dirty_files
        assert snapshot.dirty_files[tracked] == "user was editing this\n"

    def test_take_ignores_clean_files(self, git_repo: Path) -> None:
        """A clean tree produces an empty ``dirty_files`` map."""
        snapshot = WorkingTreeSnapshot(git_repo).take()
        assert snapshot.dirty_files == {}

    def test_take_ignores_untracked_files(self, git_repo: Path) -> None:
        """Untracked files are NOT captured (we don't want to delete user WIP)."""
        (git_repo / "untracked_notes.txt").write_text("user's notes\n", encoding="utf-8")

        snapshot = WorkingTreeSnapshot(git_repo).take()

        assert git_repo / "untracked_notes.txt" not in snapshot.dirty_files

    def test_restore_reverts_dirty_file(self, git_repo: Path) -> None:
        """After ``restore()``, the file matches the snapshot, not the run's changes."""
        tracked = git_repo / "tracked.txt"
        tracked.write_text("user was editing this\n", encoding="utf-8")

        snapshot = WorkingTreeSnapshot(git_repo).take()

        # Simulate an ai-fix run corrupting the file.
        tracked.write_text("garbled ai-fix output\n", encoding="utf-8")
        assert tracked.read_text(encoding="utf-8") == "garbled ai-fix output\n"

        snapshot.restore()

        assert tracked.read_text(encoding="utf-8") == "user was editing this\n"

    def test_restore_on_clean_snapshot_is_noop(self, git_repo: Path) -> None:
        """``restore()`` on a clean snapshot succeeds without raising."""
        snapshot = WorkingTreeSnapshot(git_repo).take()
        # Should not raise.
        snapshot.restore()

    def test_take_is_chainable(self, git_repo: Path) -> None:
        """``WorkingTreeSnapshot(repo).take()`` returns ``self`` for one-liners."""
        snapshot = WorkingTreeSnapshot(git_repo)
        assert snapshot.take() is snapshot

    def test_snapshot_survives_subsequent_modifications(self, git_repo: Path) -> None:
        """The snapshot's captured content does not change when the file changes."""
        tracked = git_repo / "tracked.txt"
        tracked.write_text("first edit\n", encoding="utf-8")

        snapshot = WorkingTreeSnapshot(git_repo).take()
        assert snapshot.dirty_files[tracked] == "first edit\n"

        # Modify the file post-snapshot.
        tracked.write_text("second edit\n", encoding="utf-8")

        # Snapshot still has the original.
        assert snapshot.dirty_files[tracked] == "first edit\n"
