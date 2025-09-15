#!/usr/bin/env python3
"""Test runner for new Crackerjack features."""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run tests for new features."""
    # Change to project root
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "tests" / "test_new_features"

    if not test_dir.exists():
        print(f"Test directory not found: {test_dir}")
        return 1

    # Run pytest on the new test directory
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_dir), "-v", "--tb=short"],
            cwd=project_root,
            check=False,
        )
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
