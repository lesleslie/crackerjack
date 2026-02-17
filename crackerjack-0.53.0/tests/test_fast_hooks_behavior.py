#!/usr/bin/env python3
"""Test script to verify that crackerjack workflow properly stops at fast hooks failures.

This script tests:
1. Fast hooks failure should stop execution before running tests
2. Fast hooks success should continue to run the full test suite
3. Workflow order is correct: fast hooks -> stop if failed OR continue to tests + comprehensive hooks
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
    pytest.mark.chaos,
    pytest.mark.external,
]


if os.getenv("CRACKERJACK_E2E") != "1":
    pytest.skip(
        "Fast-hooks workflow tests are opt-in (set CRACKERJACK_E2E=1).",
        allow_module_level=True,
    )


def run_command(cmd, capture_output=True, timeout=60):
    """Run a command and return the result."""
    try:
        return subprocess.run(
            cmd,
            check=False, shell=True,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        return None


def create_test_project():
    """Create a temporary test project with intentional fast hook failures."""
    temp_dir = tempfile.mkdtemp(prefix="crackerjack_test_")

    # Create a basic Python file with formatting issues (fast hook failure)
    test_file = Path(temp_dir) / "test_file.py"
    test_file.write_text("""#!/usr/bin/env python3

# This file has intentional formatting issues for fast hooks

def   badly_formatted_function( a,b ,c):
    # trailing whitespace here
    return a+b+c



# Extra blank lines and bad formatting
class  BadlyFormattedClass:
    def  __init__( self ):
        pass


# File ends without newline""")

    # Create pyproject.toml
    pyproject = Path(temp_dir) / "pyproject.toml"
    pyproject.write_text("""[project]
name = "test-project"
version = "0.1.0"
description = "Test project for crackerjack workflow testing"
requires-python = ">=3.13"

[tool.ruff]
line-length = 88

[tool.ruff.format]
quote-style = "double"
""")

    # Create .pre-commit-config.yaml with fast hooks
    precommit = Path(temp_dir) / ".pre-commit-config.yaml"
    precommit.write_text("""repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff-check
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
""")

    return temp_dir


def test_fast_hooks_failure_stops_workflow() -> bool:
    """Test that fast hooks failure stops the workflow before running tests."""
    temp_dir = create_test_project()
    os.chdir(temp_dir)

    # Initialize git repo
    subprocess.run(["git", "init"], check=False, capture_output=True)
    subprocess.run(["git", "add", "."], check=False, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], check=False, capture_output=True)

    # Run crackerjack with tests - should stop at fast hooks
    result = run_command("python -m crackerjack run -t", timeout=30)

    if result is None:
        return False


    # Check that fast hooks failed and workflow stopped
    output = result.stdout + result.stderr

    # Look for evidence of fast hooks failure
    fast_hooks_failed = any(
        phrase in output.lower()
        for phrase in [
            "fast hooks failed",
            "fast hooks: failed",
            "failed, 0 errors",
            "format check failed",
            "trailing whitespace",
        ]
    )

    # Look for evidence that tests were NOT run (workflow stopped)
    tests_not_run = "running test suite" not in output.lower()

    if fast_hooks_failed and tests_not_run:
        return True
    if fast_hooks_failed and not tests_not_run:
        return False
    if not fast_hooks_failed:
        return False
    return False


def test_fast_hooks_success_continues_workflow() -> bool:
    """Test that fast hooks success allows workflow to continue."""
    temp_dir = create_test_project()
    os.chdir(temp_dir)

    # Initialize git repo
    subprocess.run(["git", "init"], check=False, capture_output=True)
    subprocess.run(["git", "add", "."], check=False, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], check=False, capture_output=True)

    # First, fix the formatting issues by running ruff format
    result = run_command("python -m ruff format test_file.py")
    result = run_command("python -m ruff check --fix test_file.py")

    # Remove trailing whitespace manually
    test_file = Path(temp_dir) / "test_file.py"
    content = test_file.read_text()
    fixed_content = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
    test_file.write_text(fixed_content)

    # Now run crackerjack with tests - should pass fast hooks and continue
    result = run_command("python -m crackerjack run -t", timeout=60)

    if result is None:
        return False


    output = result.stdout + result.stderr

    # Look for evidence of fast hooks success
    fast_hooks_passed = any(
        phrase in output.lower()
        for phrase in [
            "fast hooks passed",
            "fast hooks: passed",
            "✅ fast hooks",
        ]
    )

    # Look for evidence that tests were run (workflow continued)
    tests_run = any(
        phrase in output.lower()
        for phrase in ["running test suite", "tests passed", "pytest", "test execution"]
    )

    if fast_hooks_passed and tests_run:
        return True
    if fast_hooks_passed and not tests_run:
        return False
    if not fast_hooks_passed:
        return False
    return False


def test_workflow_order() -> bool:
    """Test that the workflow order is correct."""
    temp_dir = create_test_project()
    os.chdir(temp_dir)

    # Initialize git repo
    subprocess.run(["git", "init"], check=False, capture_output=True)
    subprocess.run(["git", "add", "."], check=False, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], check=False, capture_output=True)

    # Create a proper test file
    test_py = Path(temp_dir) / "test_example.py"
    test_py.write_text("""def test_example():
    assert True
""")

    # Fix formatting issues
    result = run_command("python -m ruff format .")
    result = run_command("python -m ruff check --fix .")

    # Fix trailing whitespace manually
    for py_file in Path(temp_dir).glob("*.py"):
        content = py_file.read_text()
        fixed_content = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
        py_file.write_text(fixed_content)

    # Run crackerjack and capture the order of operations
    result = run_command("python -m crackerjack run -t", timeout=90)

    if result is None:
        return False


    output = result.stdout.lower()

    # Find positions of key workflow phases
    fast_hooks_pos = -1
    tests_pos = -1
    comprehensive_pos = -1

    lines = output.split("\n")
    for i, line in enumerate(lines):
        if "fast hooks" in line and ("passed" in line or "failed" in line):
            fast_hooks_pos = i
        elif "running test suite" in line or "tests" in line:
            if tests_pos == -1:  # Take first occurrence
                tests_pos = i
        elif "comprehensive" in line and ("passed" in line or "failed" in line):
            comprehensive_pos = i


    # Validate order
    order_correct = True
    if fast_hooks_pos == -1:
        order_correct = False

    if tests_pos != -1 and fast_hooks_pos != -1 and fast_hooks_pos >= tests_pos:
        order_correct = False

    if comprehensive_pos != -1 and tests_pos != -1:
        # Comprehensive hooks should run after or in parallel with tests
        # We're more flexible here since they might run in parallel
        pass

    return bool(order_correct)


def main() -> int | None:
    """Run all tests."""
    original_cwd = Path.cwd()

    try:
        # Test 1: Fast hooks failure should stop workflow
        test1_result = test_fast_hooks_failure_stops_workflow()
        os.chdir(original_cwd)

        # Test 2: Fast hooks success should continue workflow
        test2_result = test_fast_hooks_success_continues_workflow()
        os.chdir(original_cwd)

        # Test 3: Workflow order validation
        test3_result = test_workflow_order()
        os.chdir(original_cwd)

        # Summary

        all_passed = test1_result and test2_result and test3_result

        if all_passed:
            return 0
        return 1

    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    sys.exit(main())
