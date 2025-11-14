"""Code pattern descriptions."""

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "match_star_import": ValidatedPattern(
        name="match_star_import",
        pattern=r"from\s+\w+\s+import\s+\*",
        replacement=r"\g<0>",
        description="Match star import statements",
        test_cases=[
            ("from module import *", "from module import *"),
            ("from my_pkg import *", "from my_pkg import *"),
            ("from module import specific", "from module import specific"),
        ],
    ),
    "clean_unused_import": ValidatedPattern(
        name="clean_unused_import",
        pattern=r"^\s*import\s+unused_module\s*$",
        replacement=r"",
        description="Remove unused import statements (example with unused_module)",
        test_cases=[
            (" import unused_module", ""),
            (
                "import other_module",
                "import other_module",
            ),
        ],
    ),
    "clean_unused_from_import": ValidatedPattern(
        name="clean_unused_from_import",
        pattern=r"^\s*from\s+\w+\s+import\s+.*\bunused_item\b",
        replacement=r"\g<0>",
        description="Match from import statements with unused items (example with "
        "unused_item)",
        test_cases=[
            (
                "from module import used, unused_item",
                "from module import used, unused_item",
            ),
            ("from other import needed", "from other import needed"),
        ],
    ),
    "clean_import_commas": ValidatedPattern(
        name="clean_import_commas",
        pattern=r", \s*, ",
        replacement=r", ",
        description="Clean double commas in import statements",
        test_cases=[
            ("from module import a, , b", "from module import a, b"),
            ("items = [a, , b]", "items = [a, b]"),
            ("normal, list[t.Any]", "normal, list[t.Any]"),
        ],
    ),
    "clean_trailing_import_comma": ValidatedPattern(
        name="clean_trailing_import_comma",
        pattern=r", \s*$",
        replacement=r"",
        description="Remove trailing commas from lines",
        test_cases=[
            ("from module import a, b, ", "from module import a, b"),
            ("import item, ", "import item"),
            ("normal line", "normal line"),
        ],
    ),
    "clean_import_prefix": ValidatedPattern(
        name="clean_import_prefix",
        pattern=r"import\s*, \s*",
        replacement=r"import ",
        description="Clean malformed import statements with leading comma",
        test_cases=[
            ("import , module", "import module"),
            ("from pkg import , item", "from pkg import item"),
            ("import normal", "import normal"),
        ],
    ),
    "extract_unused_import_name": ValidatedPattern(
        name="extract_unused_import_name",
        pattern=r"unused import ['\"]([^'\"]+)['\"]",
        replacement=r"\1",
        description="Extract import name from vulture unused import messages",
        test_cases=[
            ("unused import 'module_name'", "module_name"),
            ('unused import "other_module"', "other_module"),
            ("some other text", "some other text"),
        ],
    ),
    "detect_typing_usage": ValidatedPattern(
        name="detect_typing_usage",
        pattern=r"\bt\.[A-Z]",
        replacement="",
        description="Detect usage of typing module aliases like t.Any, t.Dict, etc.",
        global_replace=True,
        test_cases=[
            (
                "def func(x: t.Any) -> t.Dict:",
                "def func(x: ny) -> ict:",
            ),  # Removes t.A and t.D
            (
                "value: t.Optional[str] = None",
                "value: ptional[str] = None",
            ),  # Removes t.O
            ("from typing import Dict", "from typing import Dict"),  # No match
            ("data = dict()", "data = dict()"),  # No match
        ],
    ),
}
