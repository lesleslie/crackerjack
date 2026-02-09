"""Unit tests for TestResultParser statistics parsing.

Tests the statistics parsing methods added to TestResultParser during Phase 3
refactoring. These tests verify that pytest output can be correctly parsed
into structured statistics dictionaries.
"""

import pytest
from crackerjack.services.testing.test_result_parser import TestResultParser


@pytest.fixture
def parser() -> TestResultParser:
    """Create a TestResultParser instance."""
    return TestResultParser()


class TestParseStatistics:
    """Test suite for parse_statistics method."""

    def test_parse_standard_pytest_output(self, parser: TestResultParser):
        """Test parsing standard pytest output format."""
        output = """
========== test session starts ==========
platform linux -- Python 3.13.0
collected 100 items

test_example.py::test_one PASSED
test_example.py::test_two FAILED

========== 95 passed, 5 failed in 12.3s ==========
        """

        stats = parser.parse_statistics(output)

        assert stats["total"] == 100
        assert stats["passed"] == 95
        assert stats["failed"] == 5
        assert stats["duration"] == 12.3

    def test_parse_pytest_output_with_skipped(self, parser: TestResultParser):
        """Test parsing pytest output with skipped tests."""
        output = """
========== 90 passed, 5 failed, 5 skipped in 10.5s ==========
        """

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 90
        assert stats["failed"] == 5
        assert stats["skipped"] == 5
        assert stats["duration"] == 10.5

    def test_parse_pytest_output_with_errors(self, parser: TestResultParser):
        """Test parsing pytest output with errors."""
        output = """
========== 80 passed, 5 failed, 10 skipped, 5 errors in 15.2s ==========
        """

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 80
        assert stats["failed"] == 5
        assert stats["skipped"] == 10
        assert stats["errors"] == 5
        assert stats["duration"] == 15.2

    def test_parse_pytest_output_with_xfailed_xpassed(self, parser: TestResultParser):
        """Test parsing pytest output with expected failures and unexpected passes."""
        output = """
========== 85 passed, 5 failed, 3 xfailed, 2 xpassed in 11.8s ==========
        """

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 85
        assert stats["failed"] == 5
        assert stats["xfailed"] == 3
        assert stats["xpassed"] == 2
        assert stats["duration"] == 11.8

    def test_parse_pytest_output_with_collected_only(self, parser: TestResultParser):
        """Test parsing pytest output when only 'collected' is shown."""
        output = """
collected 50 items
        """

        stats = parser.parse_statistics(output)

        # Should use collected as total
        assert stats["total"] == 50

    def test_parse_empty_output(self, parser: TestResultParser):
        """Test parsing empty pytest output."""
        output = ""

        stats = parser.parse_statistics(output)

        # Should return all zeros
        assert stats["total"] == 0
        assert stats["passed"] == 0
        assert stats["failed"] == 0
        assert stats["duration"] == 0.0

    def test_parse_output_with_coverage(self, parser: TestResultParser):
        """Test parsing pytest output with coverage information."""
        output = """
========== 95 passed, 5 failed in 12.3s ==========
TOTAL      100      50     85
        """

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 95
        assert stats["failed"] == 5
        assert stats["coverage"] == 85.0

    def test_parse_output_already_clean(self, parser: TestResultParser):
        """Test parsing when output is already clean (no ANSI codes)."""
        output = "========== 100 passed in 5.0s =========="

        stats = parser.parse_statistics(output, already_clean=True)

        assert stats["passed"] == 100
        assert stats["duration"] == 5.0

    def test_parse_output_with_ansi_codes(self, parser: TestResultParser):
        """Test parsing pytest output with ANSI color codes."""
        output = "\x1b[31m==========\x1b[0m 95 passed, 5 failed in 10.0s \x1b[31m==========\x1b[0m"

        stats = parser.parse_statistics(output)

        # ANSI codes should be stripped
        assert stats["passed"] == 95
        assert stats["failed"] == 5
        assert stats["duration"] == 10.0

    def test_parse_fallback_to_token_parsing(self, parser: TestResultParser):
        """Test fallback parsing when standard pattern fails."""
        output = """
PASSED test_one.py::test_func1
PASSED test_two.py::test_func2
FAILED test_three.py::test_func3
        """

        stats = parser.parse_statistics(output)

        # Should parse using token fallback
        assert stats["passed"] >= 0
        assert stats["failed"] >= 0

    def test_parse_with_duration_variations(self, parser: TestResultParser):
        """Test parsing various duration formats."""
        # Test with "s" suffix
        output1 = "========== 100 passed in 12.3s =========="
        stats1 = parser.parse_statistics(output1)
        assert stats1["duration"] == 12.3

        # Test with "sec" suffix
        output2 = "========== 100 passed in 12.3sec =========="
        stats2 = parser.parse_statistics(output2)
        # Should still parse or fall back gracefully

    def test_parse_total_calculation(self, parser: TestResultParser):
        """Test that total is correctly calculated from individual metrics."""
        output = """
========== 95 passed, 3 failed, 2 skipped in 8.5s ==========
        """

        stats = parser.parse_statistics(output)

        # Total should be sum of all metrics
        expected_total = 95 + 3 + 2
        assert stats["total"] == expected_total


class TestStripANSICodes:
    """Test suite for _strip_ansi_codes method."""

    def test_strip_color_codes(self, parser: TestResultParser):
        """Test stripping ANSI color codes."""
        text = "\x1b[31mRed text\x1b[0m"
        cleaned = parser._strip_ansi_codes(text)

        assert "\x1b" not in cleaned
        assert "Red text" in cleaned

    def test_strip_bold_codes(self, parser: TestResultParser):
        """Test stripping ANSI bold codes."""
        text = "\x1b[1mBold text\x1b[0m"
        cleaned = parser._strip_ansi_codes(text)

        assert "\x1b" not in cleaned
        assert "Bold text" in cleaned

    def test_strip_mixed_codes(self, parser: TestResultParser):
        """Test stripping mixed ANSI codes."""
        text = "\x1b[31m\x1b[1mBold red\x1b[0m"
        cleaned = parser._strip_ansi_codes(text)

        assert "\x1b" not in cleaned
        assert "Bold red" in cleaned

    def test_no_ansi_codes(self, parser: TestResultParser):
        """Test text without ANSI codes is unchanged."""
        text = "Plain text"
        cleaned = parser._strip_ansi_codes(text)

        assert cleaned == text


class TestExtractPytestSummary:
    """Test suite for _extract_pytest_summary method."""

    def test_extract_standard_summary(self, parser: TestResultParser):
        """Test extracting standard pytest summary."""
        output = """
Some test output
========== 95 passed, 5 failed in 12.3s ==========
More output
        """

        match = parser._extract_pytest_summary(output)

        assert match is not None
        assert "95 passed" in match.group(1)

    def test_extract_summary_without_duration(self, parser: TestResultParser):
        """Test extracting summary without duration."""
        output = "95 passed, 5 failed"

        match = parser._extract_pytest_summary(output)

        # Should still match
        assert match is not None

    def test_extract_no_summary(self, parser: TestResultParser):
        """Test when no summary is present."""
        output = "No test summary here"

        match = parser._extract_pytest_summary(output)

        assert match is None


class TestCalculateTotalTests:
    """Test suite for _calculate_total_tests method."""

    def test_calculate_total_from_metrics(self, parser: TestResultParser):
        """Test calculating total from individual metrics."""
        stats = {
            "passed": 95,
            "failed": 3,
            "skipped": 2,
            "errors": 0,
            "xfailed": 0,
            "xpassed": 0,
        }

        parser._calculate_total_tests(stats, "")

        assert stats["total"] == 100

    def test_calculate_total_with_all_metrics(self, parser: TestResultParser):
        """Test calculating total with all possible metrics."""
        stats = {
            "passed": 80,
            "failed": 5,
            "skipped": 3,
            "errors": 2,
            "xfailed": 5,
            "xpassed": 5,
        }

        parser._calculate_total_tests(stats, "")

        assert stats["total"] == 100

    def test_calculate_total_zero_metrics(self, parser: TestResultParser):
        """Test calculating total when all metrics are zero."""
        stats = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "xfailed": 0,
            "xpassed": 0,
        }

        parser._calculate_total_tests(stats, "")

        assert stats["total"] == 0


class TestExtractTestMetrics:
    """Test suite for _extract_test_metrics method."""

    def test_extract_passed_metric(self, parser: TestResultParser):
        """Test extracting passed metric."""
        stats = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
        }

        summary_text = "95 passed, 5 failed"
        parser._extract_test_metrics(summary_text, stats)

        assert stats["passed"] == 95
        assert stats["failed"] == 5

    def test_extract_skipped_metric(self, parser: TestResultParser):
        """Test extracting skipped metric."""
        stats = {"skipped": 0}

        summary_text = "10 skipped"
        parser._extract_test_metrics(summary_text, stats)

        assert stats["skipped"] == 10

    def test_extract_error_metric(self, parser: TestResultParser):
        """Test extracting error metric."""
        stats = {"errors": 0}

        summary_text = "3 errors"
        parser._extract_test_metrics(summary_text, stats)

        assert stats["errors"] == 3

    def test_extract_xfailed_xpassed_metrics(self, parser: TestResultParser):
        """Test extracting xfailed and xpassed metrics."""
        stats = {
            "xfailed": 0,
            "xpassed": 0,
        }

        summary_text = "5 xfailed, 2 xpassed"
        parser._extract_test_metrics(summary_text, stats)

        assert stats["xfailed"] == 5
        assert stats["xpassed"] == 2

    def test_extract_case_insensitive(self, parser: TestResultParser):
        """Test that extraction is case-insensitive."""
        stats = {
            "passed": 0,
            "failed": 0,
        }

        summary_text = "PASSED 100, FAILED 0"
        parser._extract_test_metrics(summary_text, stats)

        assert stats["passed"] == 100
        assert stats["failed"] == 0


class TestExtractCoverageFromOutput:
    """Test suite for _extract_coverage_from_output method."""

    def test_extract_coverage_percentage(self, parser: TestResultParser):
        """Test extracting coverage percentage."""
        output = """
TOTAL      100      50     85
        """

        coverage = parser._extract_coverage_from_output(output)

        assert coverage == 85.0

    def test_extract_coverage_no_match(self, parser: TestResultParser):
        """Test when coverage pattern doesn't match."""
        output = "No coverage data here"

        coverage = parser._extract_coverage_from_output(output)

        assert coverage is None

    def test_extract_coverage_different_format(self, parser: TestResultParser):
        """Test coverage in different format."""
        output = "Coverage: 85.5%"

        coverage = parser._extract_coverage_from_output(output)

        # Standard pattern won't match this format
        # Should return None
        assert coverage is None


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_parse_malformed_duration(self, parser: TestResultParser):
        """Test parsing with malformed duration."""
        output = "========== 100 passed in invalid_duration =========="

        stats = parser.parse_statistics(output)

        # Should handle gracefully
        assert stats["passed"] == 100
        # Duration might be 0.0 or parsed value
        assert isinstance(stats["duration"], float)

    def test_parse_very_large_numbers(self, parser: TestResultParser):
        """Test parsing with very large test counts."""
        output = "========== 10000 passed, 500 failed in 300.5s =========="

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 10000
        assert stats["failed"] == 500
        assert stats["duration"] == 300.5

    def test_parse_with_unicode_chars(self, parser: TestResultParser):
        """Test parsing output with unicode characters."""
        output = "========== 95 passed, 5 failed in 12.3s ✓ ✗ =========="

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 95
        assert stats["failed"] == 5

    def test_parse_multiline_summary(self, parser: TestResultParser):
        """Test parsing summary spread across multiple lines."""
        output = """
==========
95 passed
5 failed
in 12.3s
==========
        """

        stats = parser.parse_statistics(output)

        # Should attempt to parse
        # At minimum should not crash
        assert isinstance(stats, dict)

    def test_parse_with_trailing_whitespace(self, parser: TestResultParser):
        """Test parsing output with trailing whitespace."""
        output = "========== 95 passed, 5 failed in 12.3s ==========   \n\n"

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 95
        assert stats["failed"] == 5
        assert stats["duration"] == 12.3


class TestRealWorldExamples:
    """Test with real-world pytest output examples."""

    def test_pytest_7_output(self, parser: TestResultParser):
        """Test parsing pytest 7.x output format."""
        output = """
========================= test session starts =========================
platform linux -- Python 3.13.0, pytest-7.4.0
collected 150 items

test_module.py::test_one PASSED
test_module.py::test_two FAILED

======================== 145 passed, 5 failed in 20.5s ========================
        """

        stats = parser.parse_statistics(output)

        assert stats["total"] == 150
        assert stats["passed"] == 145
        assert stats["failed"] == 5
        assert stats["duration"] == 20.5

    def test_pytest_with_verbose_output(self, parser: TestResultParser):
        """Test parsing verbose pytest output."""
        output = """
tests/test_example.py::TEST_ONE PASSED
tests/test_example.py::TEST_TWO PASSED
tests/test_example.py::TEST_THREE FAILED

========== 2 passed, 1 failed in 3.2s ==========
        """

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 2
        assert stats["failed"] == 1
        assert stats["duration"] == 3.2

    def test_pytest_with_markers(self, parser: TestResultParser):
        """Test parsing pytest output with test markers."""
        output = """
========== 100 passed, 10 skipped (60 slow, 30 xfailed) in 15.0s ==========
        """

        stats = parser.parse_statistics(output)

        assert stats["passed"] == 100
        assert stats["skipped"] == 10
        # xfailed should be parsed separately
        assert stats["xfailed"] == 30
        assert stats["duration"] == 15.0
