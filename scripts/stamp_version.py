#!/usr/bin/env python3
"""stamp_version.py — re-stamp this repo's version claims from pyproject.toml.

A release bumps ``version`` in ``pyproject.toml``. Every doc surface that
carries a version claim has to move with it. When it does not, the repo's
own release audit (``crackerjack/checks/release_audit.py``) fails on the
freshly-bumped main — so the release commit is red on the branch the next
release starts from, and the drift stays invisible until someone reads the
failing test.

This script closes that loop. It reads the version from ``pyproject.toml``
and rewrites the claims listed in ``SURFACES``. It is idempotent: with the
surfaces already in sync it changes nothing and exits 0.

The fleet runs this from the pre-commit hook, so the commit that bumps the
version carries the claims with it. ``--check`` asks the same question
without writing, for use outside a commit.

Staging is opt-in via ``--stage``. The pre-commit hook passes it, because
the hook has no other staging step. The release path does not: crackerjack's
publish flow rewrites the claims and then stages them itself, as part of the
commit that carries the version bump.

Exit codes:
    0 — surfaces are in sync, or were rewritten
    1 — a surface is out of sync and ``--check`` was given
    2 — a claim could not be found, or a file could not be read

Usage:
    python3 scripts/stamp_version.py [--stage] [--check] [REPO_ROOT]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

#: The surfaces in this repo that carry a version claim, as
#: ``(path relative to the repo root, pattern)`` pairs. Each pattern has ONE
#: named group, ``version``, spanning the version string and nothing else —
#: so the rewrite replaces the number and leaves the surrounding text (and any
#: suffix) alone.
#:
#: The pattern must match the claim that ``crackerjack/checks/release_audit.py``
#: reads: its version regex is ``Current Status:\s*v?(\d+\.\d+(?:\.\d+)?)``,
#: so this pattern deliberately keeps the same ``Current Status:`` prefix and
#: the optional ``v``. If one changes, the other has to change with it —
#: otherwise the release audit checks a claim the stamper never moves.
#: The ``[project]`` table in pyproject.toml and the ``version`` key inside
#: it. Parsed with a regex rather than ``tomllib`` so the script runs on any
#: Python 3: the pre-commit hook invokes it with whatever ``python3`` the
#: committing shell happens to have, and on some machines that is 3.9 — which
#: has no ``tomllib`` and would fail every commit in the repo. The other
#: hook scripts in the fleet are written the same way, for the same reason.
_PROJECT_TABLE = re.compile(
    r"^\[project\]\s*$(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL
)
_VERSION_KEY = re.compile(r"""^\s*version\s*=\s*["']([^"']+)["']""", re.MULTILINE)

SURFACES: tuple[tuple[str, str], ...] = (
    (
        "CLAUDE.md",
        r"(\*\*Current Status:\s*v?)(?P<version>\d+\.\d+\.\d+)",
    ),
)


def read_version(root: Path) -> str:
    """Return the canonical version declared in ``pyproject.toml``."""
    text = (root / "pyproject.toml").read_text()
    table = _PROJECT_TABLE.search(text)
    if table is None:
        raise ValueError("pyproject.toml has no [project] table")
    version = _VERSION_KEY.search(table.group(1))
    if version is None:
        raise ValueError("pyproject.toml has no [project] version")
    return version.group(1)


def _substitute(match: re.Match[str], version: str) -> str:
    """Replace only the ``version`` group, leaving the rest of the match."""
    start = match.start("version") - match.start(0)
    end = match.end("version") - match.start(0)
    return match.group(0)[:start] + version + match.group(0)[end:]


def plan(root: Path, version: str) -> list[tuple[Path, str]]:
    """Return the ``(path, rewritten text)`` pairs that are out of sync.

    Raises:
        FileNotFoundError: a surface does not exist.
        ValueError: a surface carries no recognisable version claim.
    """
    planned: list[tuple[Path, str]] = []
    for relative, pattern in SURFACES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"{relative} does not exist")
        text = path.read_text()
        regex = re.compile(pattern)
        matches = list(regex.finditer(text))
        if not matches:
            raise ValueError(f"no version claim matched in {relative}")
        found = {match.group("version") for match in matches}
        if found == {version}:
            continue
        planned.append((path, regex.sub(lambda m: _substitute(m, version), text)))
    return planned


def write_all(root: Path, planned: list[tuple[Path, str]], version: str) -> None:
    """Rewrite every planned surface, restoring what was written on failure.

    The release path snapshots ``pyproject.toml`` and restores it when the
    bump fails. That snapshot knows nothing about the doc surfaces, so a
    failure *here* — a disk error partway through the writes — would leave
    one surface stamped for a version the rollback just undid. Restoring
    what this function wrote keeps the stamp atomic from the caller's point
    of view: either every claim moves to the new version, or none does.
    """
    written: list[tuple[Path, str]] = []
    try:
        for path, text in planned:
            original = path.read_text()
            # Recorded BEFORE the write. ``write_text`` opens in truncate
            # mode, so a write that fails partway through leaves the file
            # empty rather than untouched — the original has to be in hand
            # before that can happen.
            written.append((path, original))
            path.write_text(text)
            print(f"stamped {path.relative_to(root)} -> {version}")
    except OSError:
        for path, original in reversed(written):
            with suppress(OSError):
                path.write_text(original)
        raise


def stage(root: Path, paths: list[Path]) -> None:
    """Stage the rewritten surfaces so the commit carries them."""
    if not paths:
        return
    relatives = [str(path.relative_to(root)) for path in paths]
    subprocess.run(
        ["git", "-C", str(root), "add", "--", *relatives],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="Re-stamp this repo's version claims from pyproject.toml.",
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="repo root (default: the current directory)",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="git add the rewritten surfaces, so the bump commit carries them",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if a surface is out of sync; change nothing",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()

    try:
        version = read_version(root)
    except (OSError, ValueError) as exc:
        print(
            f"ERROR: could not read the version from {root / 'pyproject.toml'}: {exc}",
            file=sys.stderr,
        )
        return 2

    try:
        planned = plan(root, version)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.check:
        if planned:
            for path, _ in planned:
                print(
                    f"OUT OF SYNC: {path.relative_to(root)} does not carry {version}",
                    file=sys.stderr,
                )
            return 1
        print(f"version claims are in sync with pyproject.toml ({version})")
        return 0

    if planned:
        try:
            write_all(root, planned, version)
        except OSError as exc:
            print(
                f"ERROR: could not rewrite the version claims: {exc}", file=sys.stderr
            )
            return 2
        if args.stage:
            stage(root, [path for path, _ in planned])
    else:
        print(f"version claims already match pyproject.toml ({version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
