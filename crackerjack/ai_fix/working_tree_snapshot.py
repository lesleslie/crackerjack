"""Snapshot the working tree at the start of an AI-fix run.

The ai-fix loop can corrupt files (24-file corruption events were
observed in the 2026-07-04 run, plus 2 ``float('inf')`` type
regressions). This module gives the coordinator a rollback target:

* ``take()`` captures HEAD SHA + content of every tracked-dirty file
* ``restore()`` writes the captured content back, so a corrupted
  run leaves the tree in the same state it found it.

Untracked files are deliberately ignored — we don't want to delete
user work-in-progress if the run happens to touch a directory they
were editing. Only tracked-dirty files are snapshotted; tracked-dirty
covers both unstaged modifications (``M``) and staged-but-uncommitted
changes (``A``, ``M`` in the index column).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


# ``git status --porcelain`` columns: XY where X is the index status
# and Y is the worktree status. We consider a file "tracked-dirty" if
# either column indicates a divergence from HEAD.
#
# Index column (X) values that count as tracked-dirty:
#   M = modified in index (staged change)
#   A = added in index
#   D = deleted in index
#   R = renamed in index
#   C = copied in index
#
# Worktree column (Y) values that count as tracked-dirty:
#   M = modified in worktree
#   D = deleted in worktree (file no longer on disk)
#
# We do NOT consider ``??`` (untracked) or ``!!`` (ignored) — see
# the module docstring for why.
_TRACKED_DIRTY_INDEX = frozenset({"M", "A", "D", "R", "C"})
_TRACKED_DIRTY_WORKTREE = frozenset({"M", "D"})


def _run_git(repo_root: Path, *args: str) -> str:
    """Run ``git <args>`` in ``repo_root`` and return raw stdout.

    Raises ``subprocess.CalledProcessError`` on non-zero exit so the
    caller can decide whether a git failure is fatal. We deliberately
    do NOT strip the output: ``git status --porcelain`` uses leading
    spaces in its format (``" M tracked.txt"``) and stripping would
    destroy them. Callers that want a clean single-line value should
    strip themselves.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


class WorkingTreeSnapshot:
    """Capture-and-restore guard for the working tree during ai-fix.

    The intended usage:

        with WorkingTreeSnapshot(repo_root).take() as snap:
            ... run ai-fix ...
            if validation_failed:
                snap.restore()  # explicitly roll back

    Or simply rely on the captured state — the snapshot holds the
    content in memory, so ``restore()`` can be called any number of
    times after ``take()``.

    The class is not thread-safe (the captured dict is mutated by
    ``take()``); each ai-fix run should construct its own instance.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)
        self._head_sha: str = ""
        self._dirty_files: dict[Path, str] = {}

    @property
    def head_sha(self) -> str:
        """The SHA captured by ``take()``. Empty before ``take()`` runs."""
        return self._head_sha

    @property
    def dirty_files(self) -> dict[Path, str]:
        """Map of tracked-dirty file → captured content (post-``take()``).

        Keys are absolute paths (resolved against ``repo_root``); values
        are the file content as text. Mutating this dict does not affect
        the on-disk tree; use ``restore()`` for that.
        """
        return self._dirty_files

    def take(self) -> WorkingTreeSnapshot:
        """Capture HEAD SHA + content of every tracked-dirty file.

        Returns ``self`` so the call can be chained:
        ``WorkingTreeSnapshot(repo).take()``.
        """
        self._head_sha = _run_git(self._repo_root, "rev-parse", "HEAD").strip()
        self._dirty_files = {}

        status_output = _run_git(self._repo_root, "status", "--porcelain")
        for line in status_output.splitlines():
            # Don't strip the whole output — that would erase the leading
            # space in ``" M tracked.txt"`` (the index column). Strip
            # each line individually instead.
            line = line.rstrip()
            # porcelain format: "XY filename" (3-char prefix + space + path)
            if len(line) < 4:
                continue
            x = line[0]
            y = line[1]
            relative = line[3:]
            if x not in _TRACKED_DIRTY_INDEX and y not in _TRACKED_DIRTY_WORKTREE:
                continue

            path = self._repo_root / relative
            # Only capture files we can read back later. Deleted files
            # (worktree ``D``) and renamed-source entries are skipped.
            if not path.is_file():
                continue
            try:
                self._dirty_files[path] = path.read_text(encoding="utf-8")
            except OSError as exc:
                # If we can't read it, we can't restore it. Log and
                # continue; the run will still proceed but ``restore``
                # won't help with this particular file.
                logger.warning(
                    f"Could not snapshot {path}: {exc}; restore will skip it"
                )

        return self

    def restore(self) -> None:
        """Write the captured content back to each tracked-dirty file.

        Files that no longer exist on disk are recreated. Files that
        are no longer in the captured set (because the run touched
        new files) are NOT touched — we only restore the snapshot's
        captured set, never delete.

        This is intentionally idempotent: calling ``restore()`` twice
        yields the same state as calling it once.
        """
        for path, content in self._dirty_files.items():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            except OSError as exc:
                logger.error(
                    f"Could not restore {path}: {exc}; tree may be partially restored"
                )

    # Context-manager support so callers can write
    # ``with WorkingTreeSnapshot(repo).take() as snap: ...``
    def __enter__(self) -> WorkingTreeSnapshot:
        if not self._head_sha:
            self.take()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # We do NOT auto-restore on context exit — the caller decides
        # whether to roll back (validation failed) or keep the result
        # (validation passed). Restoring unconditionally would discard
        # the very fixes the run just produced.
        return None


__all__ = ["WorkingTreeSnapshot"]