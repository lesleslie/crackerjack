#!/usr/bin/env python3
"""
Test script to verify semgrep output parsing logic.
"""

import tempfile
from pathlib import Path
from crackerjack.executors.hook_executor import HookExecutor
from rich.console import Console
from subprocess import CompletedProcess


def test_semgrep_parsing():
    # Create a mock HookExecutor
    console = Console()
    pkg_path = Path.cwd()
    executor = HookExecutor(console, pkg_path)

    # Test case 1: Semgrep passes with no issues found (should report 0 files)
    result1 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=0,
        stdout='{"results": [], "errors": []}',
        stderr="Scanning 377 files"
    )

    parsed1 = executor._parse_hook_output(result1, "semgrep")
    print(f"Test 1 - No issues found:")
    print(f"  Files processed: {parsed1['files_processed']}")
    print(f"  Expected: 0")
    print(f"  Result: {'PASS' if parsed1['files_processed'] == 0 else 'FAIL'}")
    print()

    # Test case 2: Semgrep finds issues in 2 files
    result2 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=1,  # Non-zero means issues found
        stdout='{"results": [{"path": "file1.py", "check_id": "python.lang.security.audit.unquoted-search-param.unquoted-search-param"}, {"path": "file2.py", "check_id": "python.lang.security.audit.unsafe-deserialization.unsafe-deserialization"}, {"path": "file1.py", "check_id": "another.issue"}], "errors": []}',
        stderr="Found 3 issues in 2 files"
    )

    parsed2 = executor._parse_hook_output(result2, "semgrep")
    print(f"Test 2 - Issues found in 2 files:")
    print(f"  Files processed: {parsed2['files_processed']}")
    print(f"  Expected: 2")
    print(f"  Result: {'PASS' if parsed2['files_processed'] == 2 else 'FAIL'}")
    print()

    # Test case 3: Text-based parsing (when JSON fails)
    result3 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=1,
        stdout="",  # No JSON output
        stderr="found 3 issues in 2 files"
    )

    parsed3 = executor._parse_hook_output(result3, "semgrep")
    print(f"Test 3 - Text parsing for 'found 3 issues in 2 files':")
    print(f"  Files processed: {parsed3['files_processed']}")
    print(f"  Expected: 2")
    print(f"  Result: {'PASS' if parsed3['files_processed'] == 2 else 'FAIL'}")
    print()

    # Test case 4: Text parsing when no issues found
    result4 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=0,
        stdout="",  # No JSON output
        stderr="found no issues"
    )

    parsed4 = executor._parse_hook_output(result4, "semgrep")
    print(f"Test 4 - Text parsing for 'found no issues':")
    print(f"  Files processed: {parsed4['files_processed']}")
    print(f"  Expected: 0")
    print(f"  Result: {'PASS' if parsed4['files_processed'] == 0 else 'FAIL'}")
    print()

    # Test case 5: Fallback - when semgrep runs but no specific parsing matches
    result5 = CompletedProcess(
        args=["semgrep", "scan"],
        returncode=0,
        stdout="",  # No JSON output
        stderr="Scanning 377 files with semgrep"
    )

    parsed5 = executor._parse_hook_output(result5, "semgrep")
    print(f"Test 5 - Fallback for 'Scanning 377 files' (should not report 377):")
    print(f"  Files processed: {parsed5['files_processed']}")
    print(f"  Expected: 0 (not 377)")
    print(f"  Result: {'PASS' if parsed5['files_processed'] != 377 else 'FAIL'}")
    print()


if __name__ == "__main__":
    test_semgrep_parsing()
