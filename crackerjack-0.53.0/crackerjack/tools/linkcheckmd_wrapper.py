from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files


def _get_scan_paths(files: list[Path], repo_root: Path) -> list[Path]:
    dirs = {f.parent for f in files}

    if len(dirs) <= 5:
        return sorted(dirs)
    return [repo_root]


def _run_linkcheckmd(path: Path, repo_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python", "-m", "linkcheckmd", str(path)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _check_broken_links(all_results: list[str]) -> bool:
    return any(
        "broken link" in output.lower() or "404" in output for output in all_results
    )


def _process_scan_results(
    scan_paths: list[Path],
    repo_root: Path,
) -> tuple[list[str], int]:
    all_results = []

    for path in scan_paths:
        try:
            result = _run_linkcheckmd(path, repo_root)

            if result.stdout:
                all_results.append(result.stdout)

            if result.stderr:
                pass

            if result.returncode == 22:
                continue
            if result.returncode != 0:
                return all_results, result.returncode

        except subprocess.TimeoutExpired:
            return all_results, 1
        except FileNotFoundError:
            return all_results, 127

    return all_results, 0


def main(argv: list[str] | None = None) -> int:
    repo_root = Path.cwd()

    md_files = get_git_tracked_files("*.md")
    markdown_files = get_git_tracked_files("*.markdown")
    files = md_files + markdown_files

    if not files:
        return 0

    scan_paths = _get_scan_paths(files, repo_root)

    all_results, exit_code = _process_scan_results(scan_paths, repo_root)

    if exit_code != 0:
        return exit_code

    for _output in all_results:
        pass

    if _check_broken_links(all_results):
        return 22

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
