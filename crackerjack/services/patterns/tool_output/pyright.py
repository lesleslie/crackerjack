"""Pyright type checker output parsing patterns.

This module provides regex patterns for parsing Pyright static type checker output,
including errors, warnings, and summary information.
"""

from ..core import ValidatedPattern

PATTERNS = {
    "pyright_error": ValidatedPattern(
        name="pyright_error",
        pattern=r"^(.+?): (\d+): (\d+) - error: (.+)$",
        replacement=r"File: \1, Line: \2, Col: \3, Error: \4",
        description="Parse pyright error output: file: line: col - error: message",
        test_cases=[
            (
                "src/main.py: 42: 10 - error: Type 'str' is not assignable to type "
                "'int'",
                "File: src/main.py, Line: 42, Col: 10, Error: Type 'str' is not "
                "assignable to type 'int'",
            ),
            (
                "crackerjack/core.py: 123: 5 - error: Cannot assign to None",
                "File: crackerjack/core.py, Line: 123, Col: 5, Error: Cannot assign "
                "to None",
            ),
            (
                "./main.py: 999: 50 - error: Missing return statement",
                "File: ./main.py, Line: 999, Col: 50, Error: Missing return statement",
            ),
        ],
    ),
    "pyright_warning": ValidatedPattern(
        name="pyright_warning",
        pattern=r"^(.+?): (\d+): (\d+) - warning: (.+)$",
        replacement=r"File: \1, Line: \2, Col: \3, Warning: \4",
        description="Parse pyright warning output: file: line: col - warning: message",
        test_cases=[
            (
                "src/main.py: 42: 10 - warning: Type 'Any' is not specific enough",
                "File: src/main.py, Line: 42, Col: 10, Warning: Type 'Any' is not "
                "specific enough",
            ),
            (
                "crackerjack/core.py: 123: 5 - warning: Variable is untyped",
                "File: crackerjack/core.py, Line: 123, Col: 5, Warning: Variable is "
                "untyped",
            ),
            (
                "./main.py: 999: 50 - warning: Type could be more specific",
                "File: ./main.py, Line: 999, Col: 50, Warning: Type could be more"
                " specific",
            ),
        ],
    ),
    "pyright_summary": ValidatedPattern(
        name="pyright_summary",
        pattern=r"(\d+) error[s]?, (\d+) warning[s]?",
        replacement=r"\1 errors, \2 warnings",
        description="Parse pyright summary with error and warning counts",
        test_cases=[
            ("5 errors, 3 warnings", "5 errors, 3 warnings"),
            ("1 error, 1 warning", "1 errors, 1 warnings"),
            ("0 errors, 10 warnings found", "0 errors, 10 warnings found"),
        ],
    ),
}
