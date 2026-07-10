from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


_TRACKED_DIRTY_INDEX = frozenset({"M", "A", "D", "R", "C"})
_TRACKED_DIRTY_WORKTREE = frozenset({"M", "D"})


def _run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


class WorkingTreeSnapshot:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)
        self._head_sha: str = ""
        self._dirty_files: dict[Path, str] = {}

    @property
    def head_sha(self) -> str:
        return self._head_sha

    @property
    def dirty_files(self) -> dict[Path, str]:
        return self._dirty_files

    def take(self) -> WorkingTreeSnapshot:
        self._head_sha = _run_git(self._repo_root, "rev-parse", "HEAD").strip()
        self._dirty_files = {}

        status_output = _run_git(self._repo_root, "status", "--porcelain")
        for line in status_output.splitlines():
            line = line.rstrip()

            if len(line) < 4:
                continue
            x = line[0]
            y = line[1]
            relative = line[3:]
            if x not in _TRACKED_DIRTY_INDEX and y not in _TRACKED_DIRTY_WORKTREE:
                continue

            path = self._repo_root / relative

            if not path.is_file():
                continue
            try:
                self._dirty_files[path] = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning(
                    f"Could not snapshot {path}: {exc}; restore will skip it"
                )

        return self

    def restore(self) -> None:
        for path, content in self._dirty_files.items():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            except OSError as exc:
                logger.error(
                    f"Could not restore {path}: {exc}; tree may be partially restored"
                )

    def __enter__(self) -> WorkingTreeSnapshot:
        if not self._head_sha:
            self.take()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:

        return None


__all__ = ["WorkingTreeSnapshot"]
