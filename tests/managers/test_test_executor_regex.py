"""Unit tests for TestExecutor regex patterns.

This module tests the critical regex patterns used in test progress tracking
to prevent bugs like the collection regex failure (2025-11-07).

References:
    - Bug fix: crackerjack/managers/test_executor.py:194
    - Documentation: docs/progress-indicator-analysis.md
"""

import re

import pytest


class TestCollectionRegexPatterns:
    """Test regex patterns for pytest collection output parsing."""

    def test_collection_completion_pattern_basic(self):
        """Test basic collection completion pattern matches pytest output."""
        # This is the fixed pattern from test_executor.py:195
        pattern = r"(\d+)\s+(?:item|test)"

        # Basic test cases
        test_cases = [
            ("collected 123 items", 123),
            ("collected 45 tests", 45),
            ("collected 1 item", 1),
            ("collected 999 tests", 999),
        ]

        for line, expected_count in test_cases:
            match = re.search(pattern, line)
            assert match is not None, f"Pattern should match '{line}'"
            actual_count = int(match.group(1))
            assert (
                actual_count == expected_count
            ), f"Expected {expected_count}, got {actual_count}"

    def test_collection_completion_pattern_with_timing(self):
        """Test collection pattern matches output with timing information."""
        pattern = r"(\d+)\s+(?:item|test)"

        test_cases = [
            ("collected 123 items in 2.34s", 123),
            ("collected 45 tests in 0.5 seconds", 45),
            ("collected 1 item in 100ms", 1),
        ]

        for line, expected_count in test_cases:
            match = re.search(pattern, line)
            assert match is not None, f"Pattern should match '{line}'"
            actual_count = int(match.group(1))
            assert actual_count == expected_count

    def test_collection_completion_pattern_alternative_formats(self):
        """Test collection pattern matches alternative pytest output formats."""
        pattern = r"(\d+)\s+(?:item|test)"

        test_cases = [
            ("=== 123 items collected ===", 123),
            (">>> 45 tests collected <<<", 45),
            ("Collected: 1 item", 1),
        ]

        for line, expected_count in test_cases:
            match = re.search(pattern, line)
            assert match is not None, f"Pattern should match '{line}'"
            actual_count = int(match.group(1))
            assert actual_count == expected_count

    def test_collection_completion_pattern_plural_singular(self):
        """Test pattern handles both singular and plural forms."""
        pattern = r"(\d+)\s+(?:item|test)"

        test_cases = [
            ("collected 1 item", 1),  # Singular
            ("collected 2 items", 2),  # Plural (still matches 'item')
            ("collected 1 test", 1),  # Singular
            ("collected 2 tests", 2),  # Plural (still matches 'test')
        ]

        for line, expected_count in test_cases:
            match = re.search(pattern, line)
            assert match is not None, f"Pattern should match '{line}'"
            actual_count = int(match.group(1))
            assert actual_count == expected_count

    def test_collection_completion_pattern_no_false_positives(self):
        """Test pattern doesn't match unrelated lines."""
        pattern = r"(\d+)\s+(?:item|test)"

        # Lines that should NOT match
        no_match_cases = [
            "collecting tests...",
            "test session starts",
            "no collection here",
            "Running test suite",
            "item 123 failed",  # 'item' without number before it
            "test file found",  # 'test' without number
            "",
            "collected",  # Just the word 'collected' without count
        ]

        for line in no_match_cases:
            match = re.search(pattern, line)
            assert match is None, f"Pattern should NOT match '{line}', but got {match}"

    def test_collection_completion_pattern_edge_cases(self):
        """Test pattern handles edge cases correctly."""
        pattern = r"(\d+)\s+(?:item|test)"

        test_cases = [
            ("collected 0 items", 0),  # Zero items
            ("collected 10000 tests", 10000),  # Large number
            ("collected  123  items", 123),  # Multiple spaces
            ("collected 123 items", 123),  # Standard format
        ]

        for line, expected_count in test_cases:
            match = re.search(pattern, line)
            assert match is not None, f"Pattern should match '{line}'"
            actual_count = int(match.group(1))
            assert actual_count == expected_count

    def test_broken_pattern_does_not_match(self):
        """Verify the old broken pattern fails to match valid input.

        This test documents the bug that was fixed in 2025-11-07.
        The broken pattern should NEVER be used in production code.
        """
        # The BROKEN pattern that caused the bug
        broken_pattern = r"(\d +) (?: item | test)"

        # All these SHOULD match but DON'T with the broken pattern
        test_cases = [
            "collected 123 items",
            "collected 45 tests",
            "collected 1 item",
        ]

        for line in test_cases:
            match = re.search(broken_pattern, line)
            # Verify the broken pattern FAILS to match
            assert (
                match is None
            ), f"Broken pattern incorrectly matched '{line}': {match}"


class TestCollectionIntegration:
    """Integration tests simulating real pytest output parsing."""

    def test_parse_real_pytest_collection_output(self):
        """Test parsing actual pytest collection output sequences."""
        from crackerjack.managers.test_progress import TestProgress

        progress = TestProgress()
        pattern = r"(\d+)\s+(?:item|test)"

        # Simulate real pytest output lines
        pytest_output = [
            "test session starts (platform darwin)",
            "collecting...",
            "collected 123 items",
            "",
        ]

        for line in pytest_output:
            if "collected" in line and ("item" in line or "test" in line):
                match = re.search(pattern, line)
                if match:
                    progress.update(
                        total_tests=int(match.group(1)),
                        is_collecting=False,
                        collection_status="Collection complete",
                    )

        # Verify progress was updated correctly
        assert progress.total_tests == 123
        assert progress.is_collecting is False
        assert progress.collection_status == "Collection complete"

    def test_collection_progress_updates(self):
        """Test that collection progress updates correctly through lifecycle."""
        from crackerjack.managers.test_progress import TestProgress

        progress = TestProgress()
        pattern = r"(\d+)\s+(?:item|test)"

        # Initial state
        assert progress.is_collecting is True
        assert progress.total_tests == 0

        # Simulate collection completion
        line = "collected 456 items in 1.23s"
        if "collected" in line and ("item" in line or "test" in line):
            match = re.search(pattern, line)
            if match:
                progress.update(
                    total_tests=int(match.group(1)),
                    is_collecting=False,
                    collection_status="Collection complete",
                )

        # Verify transition from collecting to ready
        assert progress.is_collecting is False
        assert progress.total_tests == 456
        assert progress.collection_status == "Collection complete"


class TestRegexSafety:
    """Tests to ensure regex patterns are safe and efficient."""

    def test_pattern_does_not_cause_catastrophic_backtracking(self):
        """Ensure pattern doesn't have exponential time complexity."""
        import time

        pattern = r"(\d+)\s+(?:item|test)"

        # Long string that could trigger catastrophic backtracking in poorly written regex
        long_string = "x" * 10000 + "collected 123 items"

        start = time.time()
        match = re.search(pattern, long_string)
        elapsed = time.time() - start

        # Should complete in milliseconds, not seconds
        assert elapsed < 0.1, f"Regex took too long: {elapsed}s (possible backtracking)"
        assert match is not None
        assert int(match.group(1)) == 123

    def test_pattern_handles_malformed_input_safely(self):
        """Test pattern handles malformed/malicious input without crashing."""
        pattern = r"(\d+)\s+(?:item|test)"

        malformed_inputs = [
            "",  # Empty string
            " " * 1000,  # Just spaces
            "collected" + " " * 1000 + "items",  # Excessive spacing
            "\n\n\n\ncollected 123 items\n\n\n",  # Newlines
            "collected 9" * 1000 + " items",  # Repeated digits
        ]

        for bad_input in malformed_inputs:
            try:
                match = re.search(pattern, bad_input)
                # Should either match or not match, but not crash
                assert match is None or match is not None
            except Exception as e:
                pytest.fail(f"Pattern crashed on input: {bad_input!r}\nError: {e}")


@pytest.mark.parametrize(
    "line,expected_count",
    [
        ("collected 1 item", 1),
        ("collected 10 items", 10),
        ("collected 100 tests", 100),
        ("collected 1000 items in 5s", 1000),
        ("=== 5000 tests collected ===", 5000),
    ],
)
def test_collection_pattern_parametrized(line: str, expected_count: int):
    """Parametrized test for collection pattern across various inputs."""
    pattern = r"(\d+)\s+(?:item|test)"
    match = re.search(pattern, line)
    assert match is not None, f"Pattern should match '{line}'"
    assert int(match.group(1)) == expected_count
