"""Pytest output parsing patterns.

This module contains patterns for parsing pytest test output, including
test collection, results, coverage, and session information.
"""

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "pytest_test_start": ValidatedPattern(
        name="pytest_test_start",
        pattern=r"^(.+?):: ?(.+?):: ?(.+?) (PASSED|FAILED|SKIPPED|ERROR)$",
        replacement=r"\1::\2::\3",
        description="Parse pytest test start line with file, class, and method "
        "(3-part format)",
        test_cases=[
            (
                "test_file.py::TestClass::test_method PASSED",
                "test_file.py::TestClass::test_method",
            ),
            (
                "tests/test_core.py::TestCore::test_function FAILED",
                "tests/test_core.py::TestCore::test_function",
            ),
            (
                "src/test.py::MyTest::test_case SKIPPED",
                "src/test.py::MyTest::test_case",
            ),
        ],
    ),
    "pytest_test_result": ValidatedPattern(
        name="pytest_test_result",
        pattern=r"^(.+?) (PASSED|FAILED|SKIPPED|ERROR)(?: \[.*?\])?\s*$",
        replacement=r"\1",
        description="Parse pytest test result line with test identifier",
        test_cases=[
            ("test_file.py::test_method PASSED", "test_file.py::test_method"),
            (
                "tests/test_core.py::test_func FAILED [100%]",
                "tests/test_core.py::test_func",
            ),
            ("src/test.py::test_case SKIPPED ", "src/test.py::test_case"),
        ],
    ),
    "pytest_collection_count": ValidatedPattern(
        name="pytest_collection_count",
        pattern=r"collected (\d+) items?",
        replacement=r"\1",
        description="Parse pytest test collection count",
        test_cases=[
            ("collected 5 items", "5"),
            ("collected 1 item", "1"),
            (
                "collected 42 items for execution",
                "42 for execution",
            ),
        ],
    ),
    "pytest_session_start": ValidatedPattern(
        name="pytest_session_start",
        pattern=r"test session starts",
        replacement=r"test session starts",
        description="Match pytest session start indicator",
        test_cases=[
            ("test session starts", "test session starts"),
            ("pytest test session starts", "pytest test session starts"),
        ],
    ),
    "pytest_coverage_total": ValidatedPattern(
        name="pytest_coverage_total",
        pattern=r"TOTAL\s+\d+\s+\d+\s+(\d+)%",
        replacement=r"\1",
        description="Parse pytest coverage total percentage",
        test_cases=[
            ("TOTAL 123 45 85%", "85"),
            ("TOTAL 1000 250 75%", "75"),
            ("TOTAL 50 0 100%", "100"),
        ],
    ),
    "pytest_detailed_test": ValidatedPattern(
        name="pytest_detailed_test",
        pattern=r"^(.+\.py)::(.+) (PASSED|FAILED|SKIPPED|ERROR)",
        replacement=r"\1::\2",
        description="Parse detailed pytest test output with file, test name, and "
        "status",
        test_cases=[
            (
                "test_file.py::test_method PASSED [50%]",
                "test_file.py::test_method [50%]",
            ),
            (
                "tests/core.py::TestClass::test_func FAILED [75%] [0.1s]",
                "tests/core.py::TestClass::test_func [75%] [0.1s]",
            ),
            (
                "src/test.py::test_case SKIPPED",
                "src/test.py::test_case",
            ),
        ],
    ),
    "remove_coverage_fail_under": ValidatedPattern(
        name="remove_coverage_fail_under",
        pattern=r"--cov-fail-under=\d+\.?\d*\s*",
        replacement="",
        description="Remove coverage fail-under flags from pytest addopts",
        global_replace=True,
        test_cases=[
            ("--cov-fail-under=85 --verbose", "--verbose"),
            ("--cov-fail-under=90.5 -x", "-x"),
            ("--verbose --cov-fail-under=80 ", "--verbose "),
            ("--no-cov", "--no-cov"),
        ],
    ),
    "update_coverage_requirement": ValidatedPattern(
        name="update_coverage_requirement",
        pattern=r"(--cov-fail-under=)\d+\.?\d*",
        replacement=r"\1NEW_COVERAGE",
        description="Update coverage fail-under requirement (NEW_COVERAGE placeholder"
        " replaced dynamically)",
        test_cases=[
            ("--cov-fail-under=85", "--cov-fail-under=NEW_COVERAGE"),
            ("--cov-fail-under=90.5", "--cov-fail-under=NEW_COVERAGE"),
            ("--verbose", "--verbose"),
        ],
    ),
}
