"""Syrupy wrapper — run pytest with the syrupy plugin to validate snapshots.

Auto-discovers test files that use syrupy fixtures by looking for a sibling
``__snapshots__/`` directory with at least one entry. If no syrupy snapshot
tests are found in the project, the hook exits 0 (silently skipped) so projects
that don't use syrupy are not falsely flagged as failures.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def find_snapshot_tests(tests_root: Path = Path("tests")) -> list[str]:
    """Return test files with a sibling ``__snapshots__/`` directory.

    Syrupy stores snapshots in a ``__snapshots__/`` directory next to the test
    file. A test file is considered a syrupy snapshot test only when its
    sibling directory exists and contains at least one entry (the ``.ambr``
    snapshot files). Filename heuristics are intentionally not used — a file
    named ``test_runtime_snapshots.py`` that does not touch syrupy should not
    be picked up here.

    The discovery walks ``tests_root`` recursively. Returns an empty list when
    no snapshot tests exist (so the hook can skip cleanly).
    """
    if not tests_root.is_dir():
        return []

    snapshot_files: list[str] = []
    for test_file in tests_root.rglob("test_*.py"):
        snapshot_dir = test_file.parent / "__snapshots__"
        if snapshot_dir.is_dir() and any(snapshot_dir.iterdir()):
            snapshot_files.append(str(test_file))

    return sorted(snapshot_files)


def main() -> int:
    snapshot_tests = find_snapshot_tests()
    if not snapshot_tests:
        # No syrupy snapshot tests in this project — skip cleanly so the
        # comprehensive hook reports zero issues rather than a false failure.
        print("syrupy: no snapshot tests found; skipping.")
        return 0

    return pytest.main(
        [
            "--tb=short",
            "-ra",
            "-q",
            "-p",
            "syrupy",
            "-m",
            "not slow",
            "--no-cov",
            "-x",
            *snapshot_tests,
        ],
    )


if __name__ == "__main__":
    sys.exit(main())
