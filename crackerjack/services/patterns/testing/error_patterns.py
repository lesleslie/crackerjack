"""Test error pattern matching.

This module contains patterns for identifying and parsing various error
patterns in test failures, including assertions, imports, fixtures, and more.
"""

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "fixture_not_found_pattern": ValidatedPattern(
        name="fixture_not_found_pattern",
        pattern=r"fixture '(\w+)' not found",
        replacement=r"fixture '\1' not found",
        test_cases=[
            ("fixture 'temp_pkg_path' not found", "fixture 'temp_pkg_path' not found"),
            ("fixture 'console' not found", "fixture 'console' not found"),
            ("fixture 'tmp_path' not found", "fixture 'tmp_path' not found"),
        ],
        description="Match pytest fixture not found error patterns",
    ),
    "import_error_pattern": ValidatedPattern(
        name="import_error_pattern",
        pattern=r"ImportError|ModuleNotFoundError",
        replacement=r"ImportError",
        test_cases=[
            ("ImportError: No module named", "ImportError: No module named"),
            ("ModuleNotFoundError: No module", "ImportError: No module"),
            ("Other error types", "Other error types"),
        ],
        description="Match import error patterns in test failures",
    ),
    "assertion_error_pattern": ValidatedPattern(
        name="assertion_error_pattern",
        pattern=r"assert .+ ==",
        replacement=r"AssertionError",
        test_cases=[
            (
                "AssertionError: Values differ",
                "AssertionError: Values differ",
            ),
            ("assert result == expected", "AssertionError expected"),
            ("Normal code", "Normal code"),
        ],
        description="Match assertion error patterns in test failures",
    ),
    "attribute_error_pattern": ValidatedPattern(
        name="attribute_error_pattern",
        pattern=r"AttributeError: .+ has no attribute",
        replacement=r"AttributeError: has no attribute",
        test_cases=[
            (
                "AttributeError: 'Mock' has no attribute 'test'",
                "AttributeError: has no attribute 'test'",
            ),
            (
                "AttributeError: 'NoneType' has no attribute 'value'",
                "AttributeError: has no attribute 'value'",
            ),
            ("Normal error", "Normal error"),
        ],
        description="Match attribute error patterns in test failures",
    ),
    "mock_spec_error_pattern": ValidatedPattern(
        name="mock_spec_error_pattern",
        pattern=r"MockSpec|spec.*Mock",
        replacement=r"MockSpec",
        test_cases=[
            ("MockSpec error occurred", "MockSpec error occurred"),
            ("spec for Mock failed", "MockSpec failed"),
            ("Normal mock usage", "Normal mock usage"),
        ],
        description="Match mock specification error patterns in test failures",
    ),
    "hardcoded_path_pattern": ValidatedPattern(
        name="hardcoded_path_pattern",
        pattern=r"'/test/path'|/test/path",
        replacement=r"str(tmp_path)",
        test_cases=[
            ("'/test/path'", "str(tmp_path)"),
            ("/test/path", "str(tmp_path)"),
            ("'/other/path'", "'/other/path'"),
        ],
        description="Match hardcoded test path patterns that should use tmp_path",
    ),
    "missing_name_pattern": ValidatedPattern(
        name="missing_name_pattern",
        pattern=r"name '(\w+)' is not defined",
        replacement=r"name '\1' is not defined",
        test_cases=[
            ("name 'pytest' is not defined", "name 'pytest' is not defined"),
            ("name 'Mock' is not defined", "name 'Mock' is not defined"),
            ("name 'Path' is not defined", "name 'Path' is not defined"),
        ],
        description="Match undefined name patterns in test failures",
    ),
    "pydantic_validation_pattern": ValidatedPattern(
        name="pydantic_validation_pattern",
        pattern=r"ValidationError|validation error",
        replacement=r"ValidationError",
        test_cases=[
            ("ValidationError: field required", "ValidationError: field required"),
            ("validation error in field", "ValidationError in field"),
            ("Normal validation", "Normal validation"),
        ],
        description="Match Pydantic validation error patterns in test failures",
    ),
}
