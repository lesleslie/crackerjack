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


def get_git_tracked_files(pattern: str | None = None) -> list[Path]:
    try:
        cmd = ["git", "ls-files"]
        if pattern:
            cmd.append(pattern)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=Path.cwd(),
        )

        files = [
            Path(line.strip()) for line in result.stdout.splitlines() if line.strip()
        ]

        return [f for f in filter_gitignored_files(files) if f.exists()]

    except subprocess.CalledProcessError:
        return []
    except FileNotFoundError:
        return []


def get_files_by_extension(extensions: list[str], use_git: bool = True) -> list[Path]:
    if not use_git:
        files: list[Path] = []
        for ext in extensions:
            files.extend(Path.cwd().rglob(f"*{ext}"))
        return [f for f in files if f.is_file()]

    git_files: list[Path] = []
    for ext in extensions:
        pattern = f"*{ext}"
        found = get_git_tracked_files(pattern)
        if found:
            git_files.extend(found)

    if git_files:
        return [f for f in git_files if f.is_file()]

    result: list[Path] = []
    for ext in extensions:
        result.extend(Path.cwd().rglob(f"*{ext}"))
    return [f for f in filter_gitignored_files(result) if f.is_file()]
