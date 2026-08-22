from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from pathspec import PathSpec


@lru_cache(maxsize=8)
def get_git_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()

    while True:
        git_path = current / ".git"
        if git_path.exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


# Directory names whose nested ``.gitignore`` files should NOT contribute
# patterns to the active repo's PathSpec. These are runtime/build artifacts
# (worktrees, virtualenvs, caches, backups) that carry their own ``.gitignore``
# but are not part of the source the user is linting. Without this filter,
# projects with many worktrees (e.g. 300+ ``.gitignore`` files in
# ``.claude/worktrees/``, ``.worktrees/``, ``.backups/``) blow up
# ``PathSpec.from_lines`` compilation time AND (more importantly) make
# ``Path.rglob`` spend tens of seconds traversing trees it then ignores,
# exceeding the 60s crackerjack fast-hook timeout on ``check-yaml``.
_GITIGNORE_SKIP_PARTS: frozenset[str] = frozenset({
    ".venv", "venv", "env", ".env",
    "node_modules",
    "__pycache__",
    ".worktrees", ".claude", ".backups",
    ".crackerjack", ".superpowers",
    "dist", "build",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".complexipy_cache", ".hypothesis", ".tox",
    "htmlcov", ".coverage", ".idea", ".vscode",
})


def _iter_gitignore_files(root: Path) -> Iterable[Path]:
    """Yield ``.gitignore`` files under ``root``, pruning noise directories.

    Uses :func:`os.walk` with in-place ``dirnames`` pruning so the traversal
    never descends into known runtime/build directories. This is much faster
    than :meth:`pathlib.Path.rglob` on trees that contain many worktrees or
    a populated virtualenv — ``rglob`` spends seconds enumerating files
    that are then filtered out, while ``os.walk`` skips the subtree
    entirely.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune noise directories so os.walk doesn't descend into them.
        # This is the equivalent of telling rglob to ignore the subtree.
        dirnames[:] = [d for d in dirnames if d not in _GITIGNORE_SKIP_PARTS]
        if ".gitignore" in filenames:
            yield Path(dirpath) / ".gitignore"


@lru_cache(maxsize=8)
def _load_gitignore_spec(root: str | None = None) -> PathSpec | None:
    root_path = Path(root or Path.cwd()).resolve()
    patterns: list[str] = []

    for gitignore_path in _iter_gitignore_files(root_path):
        if not gitignore_path.is_file():
            continue

        try:
            base_dir = gitignore_path.parent.resolve().relative_to(root_path)
        except ValueError:
            continue

        prefix = "" if str(base_dir) == "." else f"{base_dir.as_posix().rstrip('/')}/"
        for line in gitignore_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            negated = stripped.startswith("!")
            if negated:
                stripped = stripped[1:].strip()
            if not stripped:
                continue

            if stripped.startswith("/"):
                stripped = stripped.lstrip("/")

            pattern = f"{prefix}{stripped}" if prefix else stripped
            if negated:
                pattern = f"!{pattern}"
            patterns.append(pattern)

    if not patterns:
        return None

    return PathSpec.from_lines("gitignore", patterns)


def _is_gitignored(path: Path, root: Path | None = None) -> bool:
    root_path = (root or Path.cwd()).resolve()
    spec = _load_gitignore_spec(str(root_path))
    if spec is None:
        return False

    try:
        relative_path = path.resolve().relative_to(root_path)
    except ValueError:
        relative_path = path

    return spec.match_file(relative_path.as_posix())


def filter_gitignored_files(files: list[Path], root: Path | None = None) -> list[Path]:
    return [file_path for file_path in files if not _is_gitignored(file_path, root)]


def get_git_tracked_files(
    pattern: str | None = None,
    root: Path | None = None,
) -> list[Path]:

    cwd = root or Path.cwd()
    try:
        cmd = ["git", "ls-files"]
        if pattern:
            cmd.append(pattern)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )

        files = [
            Path(line.strip()) for line in result.stdout.splitlines() if line.strip()
        ]

        existing = [f for f in files if (cwd / f).exists()]

        return filter_gitignored_files(existing, root=cwd)

    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def get_files_by_extension(
    extensions: list[str],
    use_git: bool = True,
    root: Path | None = None,
) -> list[Path]:

    cwd = root or Path.cwd()
    if not use_git:
        files: list[Path] = []
        for ext in extensions:
            files.extend(cwd.rglob(f"*{ext}"))
        return [f for f in files if f.is_file()]

    git_files: list[Path] = []
    for ext in extensions:
        pattern = f"*{ext}"
        found = get_git_tracked_files(pattern, root=cwd)
        if found:
            git_files.extend(found)

    if git_files:
        return [f for f in git_files if (cwd / f).is_file()]

    result: list[Path] = []
    for ext in extensions:
        result.extend(cwd.rglob(f"*{ext}"))
    return [f for f in result if f.is_file()]
