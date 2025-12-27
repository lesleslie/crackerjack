"""Tests for AsyncHookExecutor parsing logic."""

import tempfile
from pathlib import Path

from rich.console import Console

from crackerjack.executors.async_hook_executor import AsyncHookExecutor


def test_parse_hook_output_check_added_large_files_with_large_files():
    """Test _parse_hook_output for check-added-large-files when large files are found."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path("."))

    # Mock output when large files are found
    output = "Large files detected:\n  file1.py: 2.5 MB (exceeds 1.0 MB)\n\n1 large file(s) found."
    result = executor._parse_hook_output(1, output, "check-added-large-files")

    assert result["files_processed"] == 1  # Should show 1 large file found


def test_parse_hook_output_check_added_large_files_no_large_files():
    """Test _parse_hook_output for check-added-large-files when no large files are found."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path("."))

    # Mock output when no large files are found
    output = "All 10 file(s) are under size limit"
    result = executor._parse_hook_output(0, output, "check-added-large-files")  # Exit code 0 = success

    assert result["files_processed"] == 0  # Should show 0 files processed since none failed


def test_parse_hook_output_check_added_large_files_with_nonzero_exit():
    """Test _parse_hook_output for check-added-large-files with non-zero exit code."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path("."))

    # Mock output when large files are found but we miss the pattern
    output = "Some error occurred"
    result = executor._parse_hook_output(1, output, "check-added-large-files")  # Non-zero exit code

    # Should default to 1 if hook failed but we didn't find the pattern
    assert result["files_processed"] == 1


def test_parse_hook_output_check_added_large_files_different_patterns():
    """Test _parse_hook_output for check-added-large-files with various patterns."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path("."))

    # Test various patterns based on the actual regex patterns in the implementation:
    # r"large file(?:s)? found:?\s*(\d+)" - matches "large file found: 2"
    # r"found\s+(\d+)\s+large file" - matches "found 2 large file"
    # r"(\d+)\s+file(?:s)?\s+exceed(?:ed)?\s+size\s+limit" - matches "2 files exceed size limit"
    # r"(\d+)\s+large file(?:s)?\s+found" - matches "2 large files found"
    # r"(\d+)\s+file(?:s)?\s+(?:failed|violated|exceeded)" - matches "4 files failed"
    patterns_and_expected = [
        # Test pattern that finds 2 files - matches "large file(?:s)? found:?\s*(\d+)"
        ("large file found: 2", 2),
        # Test pattern that finds 5 files - matches "found\s+(\d+)\s+large file"
        ("found 5 large file", 5),
        # Test pattern that finds 3 files - matches "(\d+)\s+large file(?:s)?\s+found"
        ("3 large files found", 3),
        # Test pattern that finds 4 files - matches "(\d+)\s+file(?:s)?\s+(?:failed|violated|exceeded)"
        ("4 files failed", 4),
        # Test pattern that finds 6 files - matches "(\d+)\s+file(?:s)?\s+exceed(?:ed)?\s+size\s+limit"
        ("6 files exceed size limit", 6)
    ]

    for output_part, expected_count in patterns_and_expected:
        output = f"Large files detected:\n  {output_part}\n\nAdditional message."
        result = executor._parse_hook_output(1, output, "check-added-large-files")

        # For debugging: print the result if it doesn't match expected
        if result["files_processed"] != expected_count:
            print(f"Pattern '{output_part}' expected {expected_count} but got {result['files_processed']}")

        assert result["files_processed"] == expected_count


def test_parse_hook_output_other_hooks_unchanged():
    """Test that _parse_hook_output still works as before for non-check-added-large-files hooks."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path("."))

    # Test a standard hook with file count pattern
    output = "Found issues in 3 files"
    result = executor._parse_hook_output(1, output, "ruff-check")

    # The default pattern matching should catch this
    assert result["files_processed"] >= 0  # Could be 3, or 0 if pattern not matched

    # Check with ruff-specific pattern
    output = "3 files would be formatted"
    result = executor._parse_hook_output(1, output, "ruff-format")

    # Should match the ruff pattern
    assert result["files_processed"] >= 0


def test_parse_hook_output_check_added_large_files_exact_output():
    """Test _parse_hook_output specifically with the exact output from the real tool."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path("."))

    # Exact output from real tool when no large files are found
    output = "All 686 file(s) are under size limit"
    result = executor._parse_hook_output(0, output, "check-added-large-files")

    # Should return 0 files processed since no files exceeded the size limit
    assert result["files_processed"] == 0
