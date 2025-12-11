"""Git-aware wrapper for linkcheckmd (comprehensive link checking).

This wrapper runs full link validation including external URLs.
Intended for comprehensive hooks (~30s budget) to catch all link issues.

Features:
- Validates both local AND external links (http://, https://, etc.)
- Checks link reachability via network requests
- Automatically respects .gitignore via git-tracked file discovery

Usage:
    python -m crackerjack.tools.linkcheckmd_wrapper [path]

Exit Codes:
    0 = all links valid
    22 = broken links found (matches linkcheckmd convention)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files


def _get_scan_paths(files: list[Path], repo_root: Path) -> list[Path]:
    """Determine which directories to scan based on file distribution.

    Args:
        files: List of markdown files to check
        repo_root: Repository root directory

    Returns:
        List of paths to scan (either specific directories or repo root)
    """
    dirs = {f.parent for f in files}

    # If only one directory or very few files, scan specific dirs
    # Otherwise scan from repo root
    if len(dirs) <= 5:
        return sorted(dirs)
    return [repo_root]


def _run_linkcheckmd(path: Path, repo_root: Path) -> subprocess.CompletedProcess:
    """Execute linkcheckmd on a specific path.

    Args:
        path: Directory path to scan
        repo_root: Repository root for working directory

    Returns:
        CompletedProcess with results

    Raises:
        subprocess.TimeoutExpired: If scan exceeds 5 minutes
        FileNotFoundError: If linkcheckmd is not installed
    """
    return subprocess.run(
        ["python", "-m", "linkcheckmd", str(path)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minute timeout
    )


def _check_broken_links(all_results: list[str]) -> bool:
    """Check if any results indicate broken links.

    Args:
        all_results: List of stdout strings from linkcheckmd runs

    Returns:
        True if broken links were found, False otherwise
    """
    return any(
        "broken link" in output.lower() or "404" in output for output in all_results
    )


def _process_scan_results(
    scan_paths: list[Path], repo_root: Path
) -> tuple[list[str], int]:
    """Execute linkcheckmd on all scan paths and collect results.

    Args:
        scan_paths: List of directories to scan
        repo_root: Repository root for working directory

    Returns:
        Tuple of (all_results, exit_code) where exit_code is 0 for success
    """
    all_results = []

    for path in scan_paths:
        try:
            result = _run_linkcheckmd(path, repo_root)

            # Capture output
            if result.stdout:
                all_results.append(result.stdout)

            if result.stderr:
                print(result.stderr, file=sys.stderr, end="")

            # linkcheckmd returns exit code 22 for broken links
            if result.returncode == 22:
                continue  # Collect all broken links
            elif result.returncode != 0:
                print(
                    f"Error running linkcheckmd on {path}: exit code {result.returncode}",
                    file=sys.stderr,
                )
                return all_results, result.returncode

        except subprocess.TimeoutExpired:
            print(f"Timeout checking links in {path} (>5 minutes)", file=sys.stderr)
            return all_results, 1
        except FileNotFoundError:
            print(
                "Error: linkcheckmd not found. Install with: uv pip install linkcheckmd",
                file=sys.stderr,
            )
            return all_results, 127

    return all_results, 0


def main(argv: list[str] | None = None) -> int:
    """Run linkcheckmd on git-tracked markdown files.

    This performs comprehensive link checking including external URLs.

    Args:
        argv: Optional arguments (currently unused, for future extension)

    Returns:
        Exit code: 0 if all links valid, 22 if broken links found
    """
    repo_root = Path.cwd()

    # Get all git-tracked markdown files
    md_files = get_git_tracked_files("*.md")
    markdown_files = get_git_tracked_files("*.markdown")
    files = md_files + markdown_files

    if not files:
        print("No git-tracked markdown files found")
        return 0

    scan_paths = _get_scan_paths(files, repo_root)
    print(f"Checking links in {len(files)} markdown files...")

    # Run linkcheckmd on all paths and collect results
    all_results, exit_code = _process_scan_results(scan_paths, repo_root)

    # If error occurred during scanning, return early
    if exit_code != 0:
        return exit_code

    # Print all collected output
    for output in all_results:
        print(output, end="")

    # Check if any broken links were found
    if _check_broken_links(all_results):
        print("\n✗ Found broken links (see above)")
        return 22  # Match linkcheckmd convention

    print(f"\n✓ All links valid in {len(files)} markdown files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
