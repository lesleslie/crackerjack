"""Syrupy wrapper — run pytest with the syrupy plugin to validate snapshots."""

from __future__ import annotations

import sys

import pytest


def main() -> int:
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
            "tests/unit/test_progress_snapshots.py",
        ],
    )


if __name__ == "__main__":
    sys.exit(main())
