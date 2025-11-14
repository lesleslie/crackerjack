"""Code pattern descriptions."""

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "detect_tempfile_usage": ValidatedPattern(
        name="detect_tempfile_usage",
        pattern=r"tempfile\.(mkdtemp|NamedTemporaryFile|TemporaryDirectory)",
        replacement="MATCH",
        test_cases=[
            ("tempfile.mkdtemp()", "MATCH()"),
            ("tempfile.NamedTemporaryFile()", "MATCH()"),
            ("tempfile.TemporaryDirectory()", "MATCH()"),
            (
                "not_tempfile.other()",
                "not_tempfile.other()",
            ),
        ],
        description="Detect tempfile module usage for resource management integration",
    ),
    "detect_asyncio_create_task": ValidatedPattern(
        name="detect_asyncio_create_task",
        pattern=r"asyncio\.create_task",
        replacement="MATCH",
        test_cases=[
            ("asyncio.create_task(coro)", "MATCH(coro)"),
            ("not_asyncio.other()", "not_asyncio.other()"),
        ],
        description="Detect asyncio.create_task usage for resource management"
        " integration",
    ),
    "detect_file_open_operations": ValidatedPattern(
        name="detect_file_open_operations",
        pattern=r"(\.open\(|with open\()",
        replacement=r"MATCH",
        test_cases=[
            ("file.open()", "fileMATCH)"),
            ("with open('file.txt'): ", "MATCH'file.txt'): "),
            ("other_method()", "other_method()"),
        ],
        description="Detect file open operations for resource management integration",
    ),
    "detect_exception_patterns": ValidatedPattern(
        name="detect_exception_patterns",
        pattern=r"except\s+\w*Exception\s+as\s+\w+: ",
        replacement=r"MATCH",
        description="Detect exception handling patterns for base Exception class in Python code for DRY violations",
        test_cases=[
            ("except Exception as e: ", "MATCH"),
            ("except BaseException as error: ", "MATCH"),
            (
                "except ValueError as error: ",
                "except ValueError as error: ",
            ),
            ("try: ", "try: "),
        ],
    ),
    "match_async_function_definition": ValidatedPattern(
        name="match_async_function_definition",
        pattern=r"(async def \w+\([^)]*\)[^: ]*: )",
        replacement=r"\1",
        test_cases=[
            ("async def foo(): ", "async def foo(): "),
            ("async def bar(a, b) -> None: ", "async def bar(a, b) -> None: "),
            ("def sync_func(): ", "def sync_func(): "),
        ],
        description="Match async function definitions for resource management"
        " integration",
    ),
    "match_class_definition": ValidatedPattern(
        name="match_class_definition",
        pattern=r"class (\w+).*: ",
        replacement=r"\1",
        test_cases=[
            ("class MyClass: ", "MyClass"),
            ("class MyClass(BaseClass): ", "MyClass"),
            ("class MyClass(Base, Mixin): ", "MyClass"),
            ("def not_class(): ", "def not_class(): "),
        ],
        description="Match class definitions for resource management integration",
    ),
    "match_error_code_patterns": ValidatedPattern(
        name="match_error_code_patterns",
        pattern=r"F\d{3}|I\d{3}|E\d{3}|W\d{3}",
        replacement=r"\g<0>",
        description="Match standard error codes like F403, I001, etc.",
        test_cases=[
            ("F403", "F403"),
            ("I001", "I001"),
            ("E302", "E302"),
            ("W291", "W291"),
            ("ABC123", "ABC123"),
        ],
    ),
    "match_validation_patterns": ValidatedPattern(
        name="match_validation_patterns",
        pattern=r"if\s+not\s+\w+\s*: |if\s+\w+\s+is\s+None\s*: |if\s+len\(\w+\)\s*[<>=]",
        replacement=r"\g<0>",
        description="Match common validation patterns for extraction",
        test_cases=[
            ("if not var: ", "if not var: "),
            ("if item is None: ", "if item is None: "),
            ("if len(items) >", "if len(items) >"),
            ("other code", "other code"),
        ],
    ),
    "match_loop_patterns": ValidatedPattern(
        name="match_loop_patterns",
        pattern=r"\s*for\s+.*: \s*$|\s*while\s+.*: \s*$",
        replacement=r"\g<0>",
        description="Match for/while loop patterns",
        test_cases=[
            (" for i in items: ", " for i in items: "),
            (" while condition: ", " while condition: "),
            ("regular line", "regular line"),
        ],
    ),
}
