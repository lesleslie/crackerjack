#!/usr/bin/env python3
"""Test script to verify semgrep output parsing logic."""

import tempfile
from pathlib import Path
from subprocess import CompletedProcess

from rich.console import Console

from crackerjack.executors.hook_executor import HookExecutor


def test_semgrep_parsing() -> None:
    # Create a mock HookExecutor
    console = Console()
    pkg_path = Path.cwd()
    executor = HookExecutor(console, pkg_path)

    # Test case 1: Semgrep passes with no issues found (should report 0 files)
    result1 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=0,
        stdout='{"results": [], "errors": []}',
        stderr="Scanning 377 files",
    )

    parsed1 = executor._parse_hook_output(result1, "semgrep")

    # Test case 2: Semgrep finds issues in 2 files
    result2 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=1,  # Non-zero means issues found
        stdout='{"results": [{"path": "file1.py", "check_id": "python.lang.security.audit.unquoted-search-param.unquoted-search-param"}, {"path": "file2.py", "check_id": "python.lang.security.audit.unsafe-deserialization.unsafe-deserialization"}, {"path": "file1.py", "check_id": "another.issue"}], "errors": []}',
        stderr="Found 3 issues in 2 files",
    )

    parsed2 = executor._parse_hook_output(result2, "semgrep")

    # Test case 3: Text-based parsing (when JSON fails)
    result3 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=1,
        stdout="",  # No JSON output
        stderr="found 3 issues in 2 files",
    )

    parsed3 = executor._parse_hook_output(result3, "semgrep")

    # Test case 4: Text parsing when no issues found
    result4 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=0,
        stdout="",  # No JSON output
        stderr="found no issues",
    )

    parsed4 = executor._parse_hook_output(result4, "semgrep")

    # Test case 5: Fallback - when semgrep runs but no specific parsing matches
    result5 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=0,
        stdout="",  # No JSON output
        stderr="Scanning 377 files with semgrep",
    )

    parsed5 = executor._parse_hook_output(result5, "semgrep")


if __name__ == "__main__":
    test_semgrep_parsing()
