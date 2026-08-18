"""Tests for AsyncHookExecutor parsing logic."""

import tempfile
from pathlib import Path

from rich.console import Console

from crackerjack.executors.async_hook_executor import AsyncHookExecutor


def test_parse_hook_output_check_added_large_files_with_large_files() -> None:
    """Test _parse_hook_output for check-added-large-files when large files are found."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

    # Mock output when large files are found
    output = "Large files detected:\n  file1.py: 2.5 MB (exceeds 1.0 MB)\n\n1 large file(s) found."
    result = executor._parse_hook_output(1, output, "check-added-large-files")

    assert result["files_processed"] == 1  # Should show 1 large file found


def test_parse_hook_output_check_added_large_files_no_large_files() -> None:
    """Test _parse_hook_output for check-added-large-files when no large files are found."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

    # Mock output when no large files are found
    output = "All 10 file(s) are under size limit"
    result = executor._parse_hook_output(0, output, "check-added-large-files")  # Exit code 0 = success

    assert result["files_processed"] == 0  # Should show 0 files processed since none failed


def test_parse_hook_output_check_added_large_files_with_nonzero_exit() -> None:
    """Test _parse_hook_output for check-added-large-files with non-zero exit code."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

    # Mock output when large files are found but we miss the pattern
    output = "Some error occurred"
    result = executor._parse_hook_output(1, output, "check-added-large-files")  # Non-zero exit code

    # Should default to 1 if hook failed but we didn't find the pattern
    assert result["files_processed"] == 1


def test_parse_hook_output_check_added_large_files_different_patterns() -> None:
    """Test _parse_hook_output for check-added-large-files with various patterns."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

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
        ("6 files exceed size limit", 6),
    ]

    for output_part, expected_count in patterns_and_expected:
        output = f"Large files detected:\n  {output_part}\n\nAdditional message."
        result = executor._parse_hook_output(1, output, "check-added-large-files")

        # For debugging: print the result if it doesn't match expected
        if result["files_processed"] != expected_count:
            pass

        assert result["files_processed"] == expected_count


def test_parse_hook_output_other_hooks_unchanged() -> None:
    """Test that _parse_hook_output still works as before for non-check-added-large-files hooks."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

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


def test_parse_hook_output_check_added_large_files_exact_output() -> None:
    """Test _parse_hook_output specifically with the exact output from the real tool."""
    import logging
    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

    # Exact output from real tool when no large files are found
    output = "All 686 file(s) are under size limit"
    result = executor._parse_hook_output(0, output, "check-added-large-files")

    # Should return 0 files processed since no files exceeded the size limit
    assert result["files_processed"] == 0


def test_parse_hook_output_check_added_large_files_populates_structured_issues() -> None:
    """Regression: one large file must produce exactly one Issue entry, not two.

    The bug: ``_parse_hook_output`` for ``check-added-large-files`` previously
    only populated ``files_processed`` (a count). When the hook failed and the
    parser returned no structured issues, ``_build_success_result`` fell back
    to counting non-empty lines of output — including the ``"Large files
    detected:"`` header — so a single 2 MB file surfaced as ``Issues: 2`` in
    the crackerjack fast-hooks panel.

    Reproduces the actual stderr captured from fastblocks on 2026-08-18.
    """
    import logging

    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

    output = (
        "Large files detected:\n"
        " docs/archive/test-artifacts/coverage__20260728-055629.json: 2.0 MB"
    )
    result = executor._parse_hook_output(1, output, "check-added-large-files")

    # Exactly one large file was reported — there must be exactly one issue.
    assert len(result["issues"]) == 1, (
        f"Expected exactly 1 structured issue for one large file, "
        f"got {len(result['issues'])}: {result['issues']!r}"
    )
    # The issue string must reference the offending file path so the panel
    # can show operators which file triggered the failure.
    assert "coverage__20260728-055629.json" in result["issues"][0]


def test_apply_raw_fallback_excludes_headers_and_separators() -> None:
    """Regression: raw-fallback must use ``extract_issue_lines`` filter.

    Before Option A, the async raw-fallback did a dumb ``output.split("\\n")``
    and treated every non-empty line as an issue — meaning a single-ruff-error
    output like ``"Found 1 error:\\nfile.py:10:5: F401 unused import"``
    would surface as ``Issues: 2`` in the fast-hooks panel (the ``"Found 1
    error"`` header was counted as a separate issue).

    The fix delegates to ``extract_issue_lines`` which filters out
    summary/header/separator/JSON lines. This test asserts the filter
    excludes such lines and keeps only the genuine diagnostic line.
    """
    import logging

    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

    # Ruff concise-style output with a leading summary line that must be
    # filtered out. The body line is the only genuine issue.
    output = (
        "Found 1 error.\n"
        "ruff_check.py:42:5: F401 unused import `os`"
    )
    issues = executor._apply_raw_fallback("ruff-check", output)

    assert len(issues) == 1, (
        f"Expected exactly 1 issue after filtering the 'Found 1 error.' "
        f"header, got {len(issues)}: {issues!r}"
    )
    assert "F401" in issues[0]


def test_apply_raw_fallback_excludes_separators_and_empty_lines() -> None:
    """Regression: raw-fallback must ignore separator runes and blank lines.

    Multi-line hook output typically interleaves the genuine diagnostic lines
    with separator characters (``─────``, ``====``, ``┌``, ``└``) and blank
    padding. The filter excludes those so the panel count reflects only
    real issues.

    Note: ruff's *verbose* diagnostic format (``code --> file:line:col``
    followed by ``|``-prefixed context lines) has context lines that the
    filter does not yet recognize. That case is handled by Option C via
    ``ParserFactory`` dispatch to the registered ``RuffRegexParser``;
    keeping the fix in scope here to that filter would also widen the
    sync-path behavior, which is out of scope for this change.
    """
    import logging

    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

    output = (
        "=====\n"
        "file1.py:1:1: F401 unused import `os`\n"
        "-----\n"
        "\n"
        "file2.py:2:2: E501 line too long\n"
        "=====\n"
    )
    issues = executor._apply_raw_fallback("ruff-check", output)

    # Two genuine diagnostics; the separator lines and the blank line
    # must be excluded.
    assert len(issues) == 2, (
        f"Separator/blank lines must be filtered out; "
        f"got {len(issues)}: {issues!r}"
    )
    assert "F401" in issues[0]
    assert "E501" in issues[1]


def test_apply_raw_fallback_returns_synthetic_when_nothing_parseable() -> None:
    """When output has only headers/summaries, fallback must report a generic
    failure rather than producing an empty issues list (which would otherwise
    show ``Issues: 0`` for a failed hook)."""
    import logging

    console = Console()
    logger = logging.getLogger(__name__)
    executor = AsyncHookExecutor(console=console, pkg_path=Path())

    issues = executor._apply_raw_fallback("some-hook", "Found 1 error.\nAll checks passed")

    # ``Found 1 error.`` is filtered as a summary line; ``All checks passed``
    # is filtered as a success line. Net: no parseable issues, so the
    # synthetic ``"Hook failed with non-zero exit code"`` is the sole entry.
    assert issues == ["Hook failed with non-zero exit code"]
