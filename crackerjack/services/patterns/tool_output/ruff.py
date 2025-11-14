"""Ruff linter output parsing patterns.

This module provides regex patterns for parsing Ruff static analysis tool output,
including error messages and summary lines.
"""

from ..core import ValidatedPattern

PATTERNS = {
    "ruff_check_error": ValidatedPattern(
        name="ruff_check_error",
        pattern=r"^(.+?): (\d+): (\d+): ([A-Z]\d+) (.+)$",
        replacement=r"File: \1, Line: \2, Col: \3, Code: \4, Message: \5",
        description="Parse ruff-check error output: file: line: col: code message",
        test_cases=[
            (
                "src/main.py: 42: 10: E501 Line too long (88 > 79 characters)",
                "File: src/main.py, Line: 42, Col: 10, Code: E501, Message: Line too "
                "long (88 > 79 characters)",
            ),
            (
                "crackerjack/core.py: 123: 5: F401 'os' imported but unused",
                "File: crackerjack/core.py, Line: 123, Col: 5, Code: F401, Message: "
                "'os' imported but unused",
            ),
            (
                "src/main.py: 999: 80: W291 trailing whitespace",
                "File: src/main.py, Line: 999, Col: 80, Code: W291, Message: trailing "
                "whitespace",
            ),
        ],
    ),
    "ruff_check_summary": ValidatedPattern(
        name="ruff_check_summary",
        pattern=r"Found (\d+) error",
        replacement=r"Found \1 error(s)",
        description="Parse ruff-check summary line for error count",
        test_cases=[
            ("Found 5 error", "Found 5 error(s)"),
            ("Found 1 error in 3 files", "Found 1 error(s) in 3 files"),
            ("Found 42 error detected", "Found 42 error(s) detected"),
        ],
    ),
}
