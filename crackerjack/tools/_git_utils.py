from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from pathspec import PathSpec


@lru_cache(maxsize=8)
def _load_gitignore_spec(root: str | None = None) -> PathSpec | None:
    root_path = Path(root or Path.cwd()).resolve()
    patterns: list[str] = []

    for gitignore_path in root_path.rglob(".gitignore"):
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
    # When `root` is given, anchor `git ls-files` to that directory and
    # return paths relative to it. Without `root`, fall back to the
    # process CWD (backward compat for existing callers like
    # local_link_checker that rely on cwd == project root).
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

        # Anchor existence check to `cwd`, not the process CWD. A
        # relative path like `mahavishnu/core/dhara_client.py` resolves
        # against the process CWD when `Path.exists()` is called — so
        # from a different cwd (e.g. /tmp) every path silently fails
        # the check and the function returns []. Joining with `cwd`
        # makes the check root-relative, matching where the path was
        # actually produced.
        return [f for f in files if (cwd / f).exists()]

    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def get_files_by_extension(
    extensions: list[str],
    use_git: bool = True,
    root: Path | None = None,
) -> list[Path]:
    # `root` anchors both the git subprocess and any rglob fallback
    # to the caller's project directory instead of the process CWD.
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
        # Anchor existence check to `cwd`, not process CWD (same
        # reason as in get_git_tracked_files above).
        return [f for f in git_files if (cwd / f).is_file()]

    # No tracked files (not a git repo, git unavailable, or `cwd` is
    # not a git working tree). Return the rglob result without a
    # gitignore filter: the filter's `_load_gitignore_spec` does a
    # full-tree `rglob` (43k+ dirs on mahavishnu) that takes
    # O(total_dirs) seconds, and without git we can't reliably consult
    # `.gitignore` rules anyway. Callers needing strict gitignore
    # filtering should use `use_git=True` against a real git repo.
    result: list[Path] = []
    for ext in extensions:
        result.extend(cwd.rglob(f"*{ext}"))
    return [f for f in result if f.is_file()]
