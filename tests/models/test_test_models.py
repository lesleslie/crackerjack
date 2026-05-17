"""Tests for test_models module (TestFailure dataclass)."""

from __future__ import annotations

import pytest

from crackerjack.models.test_models import TestFailure


class TestTestFailure:
    """Tests for TestFailure dataclass."""

    def test_minimal_test_failure(self) -> None:
        """Verify minimal TestFailure creation."""
        failure = TestFailure(
            test_name="tests/test_foo.py::TestClass::test_method",
            status="FAILED",
            location="tests/test_foo.py: 42",
        )
        assert failure.test_name == "tests/test_foo.py::TestClass::test_method"
        assert failure.status == "FAILED"
        assert failure.location == "tests/test_foo.py: 42"
        assert failure.traceback == []
        assert failure.assertion is None
        assert failure.captured_stdout is None
        assert failure.captured_stderr is None
        assert failure.duration is None
        assert failure.short_summary is None
        assert failure.locals_context == {}

    def test_test_failure_with_traceback(self) -> None:
        """Verify TestFailure with traceback lines."""
        traceback_lines = [
            "Traceback (most recent call last):",
            '  File "test.py", line 10, in test_func',
            "    assert False",
            "AssertionError: test failed",
        ]
        failure = TestFailure(
            test_name="tests/test_bar.py::test_func",
            status="FAILED",
            location="tests/test_bar.py: 10",
            traceback=traceback_lines,
        )
        assert failure.traceback == traceback_lines
        assert len(failure.traceback) == 4

    def test_test_failure_with_assertion(self) -> None:
        """Verify TestFailure with assertion message."""
        failure = TestFailure(
            test_name="tests/test_baz.py::test_assertion",
            status="FAILED",
            location="tests/test_baz.py: 15",
            assertion="AssertionError: Expected True but got False",
        )
        assert failure.assertion == "AssertionError: Expected True but got False"

    def test_test_failure_with_captured_output(self) -> None:
        """Verify TestFailure with captured stdout/stderr."""
        failure = TestFailure(
            test_name="tests/test_output.py::test_print",
            status="FAILED",
            location="tests/test_output.py: 20",
            captured_stdout="Line 1\nLine 2\n",
            captured_stderr="Error message\n",
        )
        assert failure.captured_stdout == "Line 1\nLine 2\n"
        assert failure.captured_stderr == "Error message\n"

    def test_test_failure_with_duration(self) -> None:
        """Verify TestFailure with execution duration."""
        failure = TestFailure(
            test_name="tests/test_timed.py::test_slow",
            status="FAILED",
            location="tests/test_timed.py: 30",
            duration=2.45,
        )
        assert failure.duration == 2.45

    def test_test_failure_with_short_summary(self) -> None:
        """Verify TestFailure with short summary."""
        failure = TestFailure(
            test_name="tests/test_summary.py::test_fail",
            status="ERROR",
            location="tests/test_summary.py: 40",
            short_summary="Test error: NoneType has no attribute 'method'",
        )
        assert failure.short_summary == "Test error: NoneType has no attribute 'method'"

    def test_test_failure_with_locals_context(self) -> None:
        """Verify TestFailure with local variables context."""
        locals_context = {
            "x": 10,
            "y": 20,
            "result": None,
            "name": "test_var",
        }
        failure = TestFailure(
            test_name="tests/test_locals.py::test_vars",
            status="FAILED",
            location="tests/test_locals.py: 50",
            locals_context=locals_context,
        )
        assert failure.locals_context == locals_context
        assert len(failure.locals_context) == 4

    def test_test_failure_all_fields(self) -> None:
        """Verify TestFailure with all fields populated."""
        traceback = ["line1", "line2"]
        locals_ctx = {"var": "value"}
        failure = TestFailure(
            test_name="tests/test_full.py::TestClass::test_complete",
            status="ERROR",
            location="tests/test_full.py: 100",
            traceback=traceback,
            assertion="CustomError: Something went wrong",
            captured_stdout="stdout output",
            captured_stderr="stderr output",
            duration=1.23,
            short_summary="Critical error occurred",
            locals_context=locals_ctx,
        )
        assert failure.test_name == "tests/test_full.py::TestClass::test_complete"
        assert failure.status == "ERROR"
        assert failure.location == "tests/test_full.py: 100"
        assert failure.traceback == traceback
        assert failure.assertion == "CustomError: Something went wrong"
        assert failure.captured_stdout == "stdout output"
        assert failure.captured_stderr == "stderr output"
        assert failure.duration == 1.23
        assert failure.short_summary == "Critical error occurred"
        assert failure.locals_context == locals_ctx

    def test_get_file_path_from_location(self) -> None:
        """Verify get_file_path() extracts file path."""
        failure = TestFailure(
            test_name="tests/test_file.py::test_func",
            status="FAILED",
            location="tests/test_file.py: 42",
        )
        assert failure.get_file_path() == "tests/test_file.py"

    def test_get_file_path_no_colon(self) -> None:
        """Verify get_file_path() handles location without colon."""
        failure = TestFailure(
            test_name="tests/test_no_colon.py::test_func",
            status="FAILED",
            location="tests/test_no_colon.py",
        )
        assert failure.get_file_path() == "tests/test_no_colon.py"

    def test_get_file_path_various_formats(self) -> None:
        """Verify get_file_path() handles various location formats."""
        test_cases = [
            ("path/to/test.py: 10", "path/to/test.py"),
            ("test.py: 1", "test.py"),
            ("path/test.py", "path/test.py"),
            ("/absolute/path/test.py: 999", "/absolute/path/test.py"),
        ]
        for location, expected_file in test_cases:
            failure = TestFailure(
                test_name="test",
                status="FAILED",
                location=location,
            )
            assert failure.get_file_path() == expected_file

    def test_get_line_number_from_location(self) -> None:
        """Verify get_line_number() extracts line number."""
        failure = TestFailure(
            test_name="tests/test_line.py::test_func",
            status="FAILED",
            location="tests/test_line.py: 42",
        )
        assert failure.get_line_number() == 42

    def test_get_line_number_no_colon(self) -> None:
        """Verify get_line_number() returns None without colon."""
        failure = TestFailure(
            test_name="tests/test_no_line.py::test_func",
            status="FAILED",
            location="tests/test_no_line.py",
        )
        assert failure.get_line_number() is None

    def test_get_line_number_invalid_format(self) -> None:
        """Verify get_line_number() returns None on invalid format."""
        failure = TestFailure(
            test_name="tests/test_invalid.py::test_func",
            status="FAILED",
            location="tests/test_invalid.py: not_a_number",
        )
        assert failure.get_line_number() is None

    def test_get_line_number_various_formats(self) -> None:
        """Verify get_line_number() handles various formats."""
        test_cases = [
            ("test.py: 10", 10),
            ("test.py: 1", 1),
            ("test.py: 999", 999),
            ("test.py", None),
            ("test.py: abc", None),
            ("test.py: 42.5", None),
        ]
        for location, expected_line in test_cases:
            failure = TestFailure(
                test_name="test",
                status="FAILED",
                location=location,
            )
            assert failure.get_line_number() == expected_line

    def test_get_relevant_traceback_short(self) -> None:
        """Verify get_relevant_traceback() when traceback shorter than max_lines."""
        traceback = [
            "line1",
            "line2",
            "line3",
        ]
        failure = TestFailure(
            test_name="tests/test_short.py::test_func",
            status="FAILED",
            location="tests/test_short.py: 50",
            traceback=traceback,
        )
        result = failure.get_relevant_traceback(max_lines=15)
        assert result == traceback

    def test_get_relevant_traceback_truncated(self) -> None:
        """Verify get_relevant_traceback() truncates long traceback."""
        traceback = [f"line{i}" for i in range(1, 26)]  # 25 lines
        failure = TestFailure(
            test_name="tests/test_long.py::test_func",
            status="FAILED",
            location="tests/test_long.py: 60",
            traceback=traceback,
        )
        result = failure.get_relevant_traceback(max_lines=10)
        assert len(result) == 10
        # Should get the last 10 lines
        assert result == traceback[-10:]
        assert result[0] == "line16"
        assert result[-1] == "line25"

    def test_get_relevant_traceback_exact_max(self) -> None:
        """Verify get_relevant_traceback() when traceback length equals max."""
        traceback = [f"line{i}" for i in range(1, 16)]  # 15 lines
        failure = TestFailure(
            test_name="tests/test_exact.py::test_func",
            status="FAILED",
            location="tests/test_exact.py: 70",
            traceback=traceback,
        )
        result = failure.get_relevant_traceback(max_lines=15)
        assert result == traceback

    def test_get_relevant_traceback_empty(self) -> None:
        """Verify get_relevant_traceback() with empty traceback."""
        failure = TestFailure(
            test_name="tests/test_empty.py::test_func",
            status="FAILED",
            location="tests/test_empty.py: 80",
            traceback=[],
        )
        result = failure.get_relevant_traceback(max_lines=15)
        assert result == []

    def test_test_failure_test_class_flag(self) -> None:
        """Verify __test__ flag prevents pytest collection."""
        # The __test__ = False flag should prevent pytest from collecting TestFailure as a test class
        assert TestFailure.__test__ is False

    def test_test_failure_status_values(self) -> None:
        """Verify TestFailure works with standard pytest status values."""
        statuses = ["FAILED", "ERROR", "XFAIL"]
        for status in statuses:
            failure = TestFailure(
                test_name="test",
                status=status,
                location="test.py: 1",
            )
            assert failure.status == status
