"""General utility patterns for extraction and manipulation."""

from .core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "extract_coverage_percentage": ValidatedPattern(
        name="extract_coverage_percentage",
        pattern=r"coverage-([\d\.]+)%25",
        replacement="",  # Not used for extraction, just validation
        description="Search for coverage percentage in badge URL",
        test_cases=[
            ("coverage-85.0%25", ""),  # Will use search() to get group(1)
            ("coverage-75.5%25", ""),
            ("coverage-100.0%25", ""),
            ("no coverage here", "no coverage here"),  # No match
        ],
    ),
    "extract_range_size": ValidatedPattern(
        name="extract_range_size",
        pattern=r"range\((\d+)\)",
        replacement=r"\1",
        description="Extract numeric size from range() calls",
        test_cases=[
            ("range(1000)", "1000"),
            ("range(50)", "50"),
            ("for i in range(100): ", "for i in 100: "),
            ("other_func(10)", "other_func(10)"),
        ],
    ),
    "extract_variable_name_from_assignment": ValidatedPattern(
        name="extract_variable_name_from_assignment",
        pattern=r"\s*(\w+)\s*=.*",
        replacement=r"\1",
        description="Extract variable name from assignment statement",
        test_cases=[
            ("password = 'secret'", "password"),
            ("api_key = 'value'", "api_key"),
            (" token =", "token"),
            ("complex_variable_name = value", "complex_variable_name"),
        ],
    ),
}
