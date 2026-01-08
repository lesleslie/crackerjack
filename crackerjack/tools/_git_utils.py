from __future__ import annotations

import subprocess
from pathlib import Path


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

        return [
            Path(line.strip()) for line in result.stdout.splitlines() if line.strip()
        ]

    except subprocess.CalledProcessError:
        return []
    except FileNotFoundError:
        return []


def get_files_by_extension(extensions: list[str], use_git: bool = True) -> list[Path]:
    if not use_git:
        files = []
        for ext in extensions:
            files.extend(Path.cwd().rglob(f"*{ext}"))
        return [f for f in files if f.is_file()]

    files = []
    for ext in extensions:
        pattern = f"*{ext}"
        git_files = get_git_tracked_files(pattern)
        if git_files:
            files.extend(git_files)

    if files:
        return files

    result = []
    for ext in extensions:
        result.extend(Path.cwd().rglob(f"*{ext}"))
    return [f for f in result if f.is_file()]
