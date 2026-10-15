"""Conflict-marker detector for tracked markdown files.

Active hook name: ``no-conflict-markers`` (fast hook).

Scans every markdown file tracked by the current git repository for
git merge conflict markers (``<<<<<<<``, ``=======``, ``>>>>>>>`) and
exits non-zero if any are present. The check is a belt for the
procedural rule in
``docs/decisions/2026-10-14-bypass-gate-parallel-sessions.md`` Rule 2;
that decision's Rule 1 is the operator-level
``--no-consolidation-gate`` parallel-session pre-condition.

Trigger: the 2026-10-14 ``fd9b61ed`` commit landed 1.5K lines of
conflict markers in ``docs/plans/...`` and ``docs/specs/...`` because
a parallel session's stash was popped into a conflicting main tree.
This hook would have caught the landed markers on the first run.

Exit-code contract (mirrors ``audit_type_checking_runtime_refs``):

  - ``0`` — clean, no markers
  - ``1`` — markers found (one or more files)
  - ``2`` — scan error (git not on PATH, repo not a git repo, etc.)

The tool is deliberately read-only: it does not rewrite any file. The
user is expected to open the file, resolve the conflict, and re-run.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

CONFLICT_MARKER_RE = re.compile(r"^\s*(<<<<<<<|=======|>>>>>>>)(?:$|[^=])")

EXIT_OK = 0
EXIT_MARKERS_FOUND = 1
EXIT_SCAN_ERROR = 2


@dataclass(frozen=True)
class MarkerHit:
    """A single conflict-marker line in a single file."""

    path: Path
    line: int
    snippet: str


def get_tracked_markdown_files(repo_root: Path) -> list[Path]:
    """Return every ``*.md`` / ``*.markdown`` file tracked by git.

    Runs ``git ls-files -z`` from the given repo root and returns
    *absolute* paths. Raises :class:`FileNotFoundError` if ``git`` is
    not on PATH and :class:`subprocess.CalledProcessError` if the
    directory is not a git repo or the command fails. Callers (the
    CLI entry point) translate those into the right exit code; this
    function is pure with respect to the subprocess boundary.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md", "*.markdown"],
        cwd=repo_root,
        capture_output=True,
        check=True,
        text=True,
    )

    repo_root = repo_root.resolve()
    # Filter to existing files only. `git ls-files` returns tracked
    # files even when they have been deleted from the working tree
    # (e.g. mid-commit staged deletions); a file that is not on disk
    # cannot contain conflict markers and trying to read it would
    # just produce noise on stderr.
    candidates = [repo_root / p for p in result.stdout.split("\x00") if p]
    return [p for p in candidates if p.is_file()]


def scan_file(path: Path) -> list[MarkerHit]:
    """Return every conflict-marker line in ``path``.

    Silently skips files that cannot be read (permission, encoding).
    The intent is to surface marker lines, not to fail on unreadable
    files — a permission error in a single file should not block the
    whole run.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        sys.stderr.write(f"no-conflict-markers: cannot read {path}: {exc}\n")
        return []

    hits: list[MarkerHit] = [
        MarkerHit(path=path, line=line_no, snippet=line)
        for line_no, line in enumerate(text.splitlines(), start=1)
        if CONFLICT_MARKER_RE.match(line)
    ]
    return hits


def scan_repo(repo_root: Path) -> list[MarkerHit]:
    """Scan every tracked markdown file in ``repo_root`` for conflict markers.

    Returns the full hit list across all files. Empty list = clean.
    """
    files = get_tracked_markdown_files(repo_root)
    hits: list[MarkerHit] = []
    for path in files:
        hits.extend(scan_file(path))
    return hits


def _print_hits(hits: list[MarkerHit], repo_root: Path) -> None:
    """Render the hit list as a human-readable report on stderr.

    Paths are rendered **relative to** ``repo_root`` so the report does
    not leak the operator's local filesystem layout (e.g. ``/Users/...``
    on a developer laptop). ``repo_root`` is resolved before
    comparison so the relative form is stable across macOS's symlinked
    paths (e.g. ``/var`` vs ``/private/var``) and across ``Path.cwd()``
    variants.
    """
    resolved_root = repo_root.resolve()
    sys.stderr.write(
        f"no-conflict-markers: {len(hits)} conflict-marker line(s) found "
        f"in tracked markdown files\n"
    )
    for hit in hits:
        try:
            display = hit.path.relative_to(resolved_root)
        except ValueError:
            # Defensive: a hit outside the repo (shouldn't happen in
            # current code paths) falls back to the absolute path with
            # a marker so the operator can still locate it.
            display = hit.path
        sys.stderr.write(f"  {display}:{hit.line}: {hit.snippet.strip()}\n")
    sys.stderr.write(
        "Resolve all git merge conflict markers before committing. "
        "See docs/decisions/2026-10-14-bypass-gate-parallel-sessions.md.\n"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. The optional argv is honored for testability.

    Exit codes: 0 clean, 1 markers found, 2 scan error (git not on
    PATH, not a git repo, etc.).
    """
    _ = argv  # no positional args today; reserved for future path overrides
    repo_root = Path.cwd()
    try:
        hits = scan_repo(repo_root)
    except FileNotFoundError as exc:
        sys.stderr.write(
            f"no-conflict-markers: git not on PATH (cwd={repo_root}): {exc}\n"
        )
        return EXIT_SCAN_ERROR
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(
            f"no-conflict-markers: git ls-files failed in {repo_root}: "
            f"{exc.stderr.strip() or exc}\n"
        )
        return EXIT_SCAN_ERROR
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"no-conflict-markers: scan failed: {exc}\n")
        return EXIT_SCAN_ERROR

    if not hits:
        return EXIT_OK

    _print_hits(hits, repo_root)
    return EXIT_MARKERS_FOUND


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
