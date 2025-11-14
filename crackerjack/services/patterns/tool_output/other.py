"""Additional tool output parsing patterns.

This module provides regex patterns for parsing output from various development tools
including mypy (type checking), vulture (dead code detection), and complexipy (complexity analysis).
"""

from ..core import ValidatedPattern

PATTERNS = {
    "complexipy_complex": ValidatedPattern(
        name="complexipy_complex",
        pattern=r"^(.+?): (\d+): (\d+) - (.+) is too complex \((\d+)\)",
        replacement=r"File: \1, Line: \2, Col: \3, Function: \4, Complexity: \5",
        description="Parse complexipy complexity detection: file: line: col - function "
        "is too complex (score)",
        test_cases=[
            (
                "src/main.py: 42: 1 - process_data is too complex (16)",
                "File: src/main.py, Line: 42, Col: 1, Function: process_data, "
                "Complexity: 16",
            ),
            (
                "crackerjack/core.py: 100: 5 - calculate_metrics is too complex (25)",
                "File: crackerjack/core.py, Line: 100, Col: 5, Function: "
                "calculate_metrics, Complexity: 25",
            ),
            (
                "./utils.py: 200: 1 - complex_function is too complex (18)",
                "File: ./utils.py, Line: 200, Col: 1, Function: complex_function, "
                "Complexity: 18",
            ),
        ],
    ),
    "mypy_error": ValidatedPattern(
        name="mypy_error",
        pattern=r"^(.+?): (\d+): error: (.+)$",
        replacement=r"File: \1, Line: \2, Error: \3",
        description="Parse mypy error output: file: line: error: message",
        test_cases=[
            (
                "src/main.py: 42: error: Incompatible types in assignment",
                "File: src/main.py, Line: 42, Error: Incompatible types in assignment",
            ),
            (
                "crackerjack/core.py: 123: error: Name 'undefined' is not defined",
                "File: crackerjack/core.py, Line: 123, Error: Name 'undefined' is not "
                "defined",
            ),
            (
                "./main.py: 999: error: Argument has incompatible type",
                "File: ./main.py, Line: 999, Error: Argument has incompatible type",
            ),
        ],
    ),
    "mypy_note": ValidatedPattern(
        name="mypy_note",
        pattern=r"^(.+?): (\d+): note: (.+)$",
        replacement=r"File: \1, Line: \2, Note: \3",
        description="Parse mypy note output: file: line: note: message",
        test_cases=[
            (
                "src/main.py: 42: note: See https://mypy.rtfd.io/...",
                "File: src/main.py, Line: 42, Note: See https://mypy.rtfd.io/...",
            ),
            (
                "crackerjack/core.py: 123: note: Consider using a type annotation",
                "File: crackerjack/core.py, Line: 123, Note: Consider using a type "
                "annotation",
            ),
            (
                "./main.py: 999: note: Consider using Optional[...]",
                "File: ./main.py, Line: 999, Note: Consider using Optional[...]",
            ),
        ],
    ),
    "vulture_unused": ValidatedPattern(
        name="vulture_unused",
        pattern=r"^(.+?): (\d+): unused (.+) '(.+)'",
        replacement=r"File: \1, Line: \2, Unused \3: '\4'",
        description="Parse vulture unused code detection: file: line: unused type"
        " 'name'",
        test_cases=[
            (
                "src/main.py: 42: unused function 'helper'",
                "File: src/main.py, Line: 42, Unused function: 'helper'",
            ),
            (
                "crackerjack/core.py: 123: unused variable 'result'",
                "File: crackerjack/core.py, Line: 123, Unused variable: 'result'",
            ),
            (
                "./main.py: 999: unused import 'os'",
                "File: ./main.py, Line: 999, Unused import: 'os'",
            ),
        ],
    ),
}
