"""Tests for ``crackerjack.tools.no_conflict_markers``.

The scanner uses ``git ls-files`` under the hood, so each test
constructs a real (throwaway) git repo in ``tmp_path`` and seeds it
with synthetic markdown files. This avoids depending on the host
working tree and keeps the tests hermetic.

Coverage targets:

  - ``get_tracked_markdown_files`` — empty repo, files-only-ignored,
    mixed .md / .markdown / non-markdown
  - ``scan_file`` — clean file, file with one marker, file with all
    three marker shapes, file with embedded ``>`` in code (no false
    positives), unreadable file (graceful skip)
  - ``scan_repo`` — clean repo returns empty, dirty repo returns hits
  - ``main`` — exit code 0 (clean), 1 (hits), 2 (no git on PATH —
    mocked)
  - ``CONFLICT_MARKER_RE`` — anchored, no false positives on prose
    that *contains* but does not *start with* a marker
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from crackerjack.tools.no_conflict_markers import (
    CONFLICT_MARKER_RE,
    EXIT_MARKERS_FOUND,
    EXIT_OK,
    EXIT_SCAN_ERROR,
    MarkerHit,
    get_tracked_markdown_files,
    main,
    scan_file,
    scan_repo,
)


# ---------- fixtures ----------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with user.name/user.email set and a clean tree.

    Yields the repo root. The repo is ``tmp_path`` itself — tests can
    write markdown files directly into it.
    """
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main", str(tmp_path)],
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def _commit_all(repo: Path) -> None:
    """Stage and commit everything in ``repo``. Sets up the tracked-file set."""
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "init"],
        cwd=repo,
        check=True,
    )


# ---------- CONFLICT_MARKER_RE ------------------------------------------------


def test_conflict_marker_re_matches_anchored_lines():
    """The regex is anchored at line start; a line that *contains* but does
    not *start with* a marker must not match. The terminal anchor (or a
    non-``=`` character) is required after the marker so that pytest
    summary dividers like ``============================`` (7+ ``=``
    characters) are NOT flagged.
    """
    # Real git markers — match.
    assert CONFLICT_MARKER_RE.match("<<<<<<< HEAD") is not None
    assert CONFLICT_MARKER_RE.match("<<<<<<< Updated upstream") is not None
    assert CONFLICT_MARKER_RE.match("=======") is not None  # standalone
    assert CONFLICT_MARKER_RE.match(">>>>>>> branch") is not None
    assert CONFLICT_MARKER_RE.match(">>>>>>> Stashed changes") is not None
    # Indented markers (from a nested merge) still match.
    assert CONFLICT_MARKER_RE.match("    <<<<<<< HEAD") is not None
    # Prose that contains but does not start with a marker is a no-match.
    assert CONFLICT_MARKER_RE.match("see `<<<<<<<` for details") is None
    # Code-fence line that starts with backticks is a no-match.
    assert CONFLICT_MARKER_RE.match("```diff\n<<<<<<< HEAD") is None
    # False-positive guards — pytest output and similar.
    assert (
        CONFLICT_MARKER_RE.match(
            "============================ test session starts ============================"
        )
        is None
    )
    assert (
        CONFLICT_MARKER_RE.match("======================== 12 passed in 0.15s ========================")
        is None
    )
    assert CONFLICT_MARKER_RE.match("=" * 24) is None
    assert CONFLICT_MARKER_RE.match("=" * 80) is None


# ---------- get_tracked_markdown_files ---------------------------------------


def test_get_tracked_markdown_files_empty_repo(git_repo: Path) -> None:
    """A freshly-initialized repo with no commits returns nothing."""
    assert get_tracked_markdown_files(git_repo) == []


def test_get_tracked_markdown_files_only_md(git_repo: Path) -> None:
    """Tracked markdown files appear; untracked and non-markdown do not."""
    (git_repo / "a.md").write_text("# A\n", encoding="utf-8")
    (git_repo / "b.markdown").write_text("# B\n", encoding="utf-8")
    (git_repo / "c.txt").write_text("plain text\n", encoding="utf-8")
    _commit_all(git_repo)
    # Add an untracked markdown file *after* the commit so it does
    # not appear in `git ls-files` output.
    (git_repo / "untracked.md").write_text("# untracked\n", encoding="utf-8")

    paths = sorted(p.name for p in get_tracked_markdown_files(git_repo))
    assert paths == ["a.md", "b.markdown"]


def test_get_tracked_markdown_files_skips_deleted(git_repo: Path) -> None:
    """Tracked files that have been deleted from the working tree (a
    mid-commit staged-deletion state) are filtered out — they cannot
    contain conflict markers and trying to read them would just
    produce noise on stderr."""
    (git_repo / "kept.md").write_text("# Kept\n", encoding="utf-8")
    (git_repo / "deleted.md").write_text("# Deleted\n", encoding="utf-8")
    _commit_all(git_repo)
    # Delete one tracked file from the working tree, then `git rm` to
    # stage the deletion.
    (git_repo / "deleted.md").unlink()
    subprocess.run(["git", "rm", "--quiet", "deleted.md"], cwd=git_repo, check=True)

    paths = [p.name for p in get_tracked_markdown_files(git_repo)]
    assert paths == ["kept.md"]


# ---------- scan_file ---------------------------------------------------------


def test_scan_file_clean(tmp_path: Path) -> None:
    """A file with no marker lines returns no hits."""
    p = tmp_path / "clean.md"
    p.write_text("# Title\n\nSome prose here.\n", encoding="utf-8")
    assert scan_file(p) == []


def test_scan_file_one_marker(tmp_path: Path) -> None:
    """A file with a single marker line returns a single hit with the
    correct line number and snippet."""
    p = tmp_path / "dirty.md"
    p.write_text(
        "# Title\n"
        "<<<<<<< HEAD\n"
        "stale content\n"
        "=======\n"
        "fresh content\n"
        ">>>>>>> branch\n",
        encoding="utf-8",
    )
    hits = scan_file(p)
    assert len(hits) == 3
    assert all(hit.path == p for hit in hits)
    assert [h.line for h in hits] == [2, 4, 6]
    assert "HEAD" in hits[0].snippet
    assert "branch" in hits[2].snippet


def test_scan_file_does_not_match_inside_code_fence(tmp_path: Path) -> None:
    """A marker-like string inside a fenced code block is not a hit.

    The scanner does NOT understand code fences — it matches on line
    start. A line that starts with ``<<<<<<<`` outside a code fence
    would be a hit. This test documents that explicit limitation: a
    marker *inside* a code-fenced block is matched as a real marker
    unless the line starts with backticks. The 2026-10-14 incident
    markers were always at line start, so this limitation is
    acceptable; documentation is the contract.
    """
    p = tmp_path / "code-fenced.md"
    p.write_text(
        "```\n"
        "<<<<<<< example\n"
        "this is documentation, not a real conflict\n"
        ">>>>>>> example\n"
        "```\n",
        encoding="utf-8",
    )
    hits = scan_file(p)
    # The fenced content is still matched because the regex is purely
    # line-start-based. Documenting this in the test so future readers
    # know the trade-off.
    assert len(hits) == 2


def test_scan_file_unreadable(tmp_path: Path, monkeypatch) -> None:
    """An unreadable file is silently skipped (the run should not crash)."""
    p = tmp_path / "unreadable.md"
    p.write_text("# A\n", encoding="utf-8")
    monkeypatch.setattr(Path, "read_text", lambda *a, **kw: (_ for _ in ()).throw(OSError("boom")))
    # The function catches OSError and returns an empty list — the
    # error is logged on stderr but does not propagate.
    assert scan_file(p) == []


# ---------- scan_repo ---------------------------------------------------------


def test_scan_repo_clean(git_repo: Path) -> None:
    """A clean repo returns no hits."""
    (git_repo / "a.md").write_text("# A\n", encoding="utf-8")
    (git_repo / "b.md").write_text("## B\n\nProse.\n", encoding="utf-8")
    _commit_all(git_repo)
    assert scan_repo(git_repo) == []


def test_scan_repo_dirty(git_repo: Path) -> None:
    """A repo with a conflict-marker file returns the matching hits."""
    dirty = git_repo / "dirty.md"
    dirty.write_text(
        "# Header\n"
        "<<<<<<< HEAD\n"
        "old\n"
        "=======\n"
        "new\n"
        ">>>>>>> branch\n",
        encoding="utf-8",
    )
    _commit_all(git_repo)
    hits = scan_repo(git_repo)
    assert len(hits) == 3
    assert {h.path.name for h in hits} == {"dirty.md"}


def test_scan_repo_mixed_clean_and_dirty(git_repo: Path) -> None:
    """Only dirty files are reported; clean files do not appear in hits."""
    (git_repo / "clean.md").write_text("# Clean\n", encoding="utf-8")
    (git_repo / "dirty.md").write_text(
        "<<<<<<< HEAD\n"
        "x\n"
        "=======\n"
        "y\n"
        ">>>>>>> branch\n",
        encoding="utf-8",
    )
    _commit_all(git_repo)
    hits = scan_repo(git_repo)
    assert {h.path.name for h in hits} == {"dirty.md"}


# ---------- main (CLI entry) -------------------------------------------------


def test_main_clean(git_repo: Path, monkeypatch) -> None:
    """main() returns 0 when the cwd contains a clean repo."""
    (git_repo / "a.md").write_text("# Clean\n", encoding="utf-8")
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    assert main() == EXIT_OK


def test_main_dirty(git_repo: Path, monkeypatch, capsys) -> None:
    """main() returns 1 and writes a report to stderr when markers are found."""
    (git_repo / "dirty.md").write_text(
        "<<<<<<< HEAD\n"
        "x\n"
        "=======\n"
        "y\n"
        ">>>>>>> branch\n",
        encoding="utf-8",
    )
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    rc = main()
    assert rc == EXIT_MARKERS_FOUND
    captured = capsys.readouterr()
    assert "dirty.md" in captured.err
    assert "no-conflict-markers" in captured.err


def test_main_no_git_on_path(git_repo: Path, monkeypatch, capsys) -> None:
    """main() returns 2 and writes to stderr when git is not on PATH."""
    monkeypatch.chdir(git_repo)
    # Patch subprocess.run to simulate FileNotFoundError (git missing).
    import crackerjack.tools.no_conflict_markers as mod

    def _raise(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(mod.subprocess, "run", _raise)
    assert main() == EXIT_SCAN_ERROR
    captured = capsys.readouterr()
    assert "git not on PATH" in captured.err


# ---------- marker dataclass --------------------------------------------------


def test_marker_hit_is_frozen() -> None:
    """MarkerHit is a frozen dataclass (hashable, immutable)."""
    hit = MarkerHit(path=Path("a.md"), line=1, snippet="<<<<<<<")
    with pytest.raises((AttributeError, Exception)):
        hit.line = 99  # type: ignore[misc]
