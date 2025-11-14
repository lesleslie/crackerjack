"""Code pattern descriptions."""

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "detect_error_response_patterns": ValidatedPattern(
        name="detect_error_response_patterns",
        pattern=r'return\s+.*[\'\"]\{.*[\'\""]error[\'\""].*\}.*[\'\""]',
        replacement=r"MATCH",
        description="Detect error response patterns in Python code for DRY violations",
        test_cases=[
            ('return \'{"error": "msg"}\'', "MATCH"),
            ('return f\'{"error": "msg"}\'', "MATCH"),
            ('return {"success": True}', 'return {"success": True}'),
            ('return \'{"error": "test message", "code": 500}\'', "MATCH"),
        ],
    ),
    "detect_path_conversion_patterns": ValidatedPattern(
        name="detect_path_conversion_patterns",
        pattern=r"Path\([^)]+\)\s+if\s+isinstance\([^)]+, \s*str\)\s+else\s+[^)]+",
        replacement=r"MATCH",
        description="Detect path conversion patterns in Python code for DRY violations",
        test_cases=[
            ("Path(value) if isinstance(value, str) else value", "MATCH"),
            ("Path(path) if isinstance(path, str) else path", "MATCH"),
            ("Path('/tmp/file')", "Path('/tmp/file')"),
            (
                "Path(input_path) if isinstance(input_path, str) else input_path",
                "MATCH",
            ),
        ],
    ),
    "detect_file_existence_patterns": ValidatedPattern(
        name="detect_file_existence_patterns",
        pattern=r"if\s+not\s+\w+\.exists\(\): ",
        replacement=r"MATCH",
        description="Detect file existence check patterns in Python code for DRY"
        " violations",
        test_cases=[
            ("if not file.exists(): ", "MATCH"),
            ("if not path.exists(): ", "MATCH"),
            ("if not file_path.exists(): ", "MATCH"),
            ("if file.exists(): ", "if file.exists(): "),
        ],
    ),
    "fix_path_conversion_with_ensure_path": ValidatedPattern(
        name="fix_path_conversion_with_ensure_path",
        pattern=r"Path\([^)]+\)\s+if\s+isinstance\([^)]+, \s*str\)\s+else\s+([^)]+)",
        replacement=r"_ensure_path(\1)",
        description="Replace path conversion patterns with _ensure_path utility "
        "function",
        test_cases=[
            ("Path(value) if isinstance(value, str) else value", "_ensure_path(value)"),
            ("Path(path) if isinstance(path, str) else path", "_ensure_path(path)"),
            (
                "Path(input_path) if isinstance(input_path, str) else input_path",
                "_ensure_path(input_path)",
            ),
        ],
    ),
    "fix_path_conversion_simple": ValidatedPattern(
        name="fix_path_conversion_simple",
        pattern=r"Path\(([^)]+)\)\s+if\s+isinstance\(\1, \s*str\)\s+else\s+\1",
        replacement=r"_ensure_path(\1)",
        description="Replace simple path conversion patterns with _ensure_path utility "
        "function",
        test_cases=[
            ("Path(value) if isinstance(value, str) else value", "_ensure_path(value)"),
            ("Path(path) if isinstance(path, str) else path", "_ensure_path(path)"),
            (
                "Path(file_path) if isinstance(file_path, str) else file_path",
                "_ensure_path(file_path)",
            ),
        ],
    ),
    "detect_hardcoded_temp_paths_basic": ValidatedPattern(
        name="detect_hardcoded_temp_paths_basic",
        pattern=r"(?:/tmp/|/temp/|C:\\temp\\|C:\\tmp\\)",  # nosec B108
        replacement="[TEMP_PATH]/",
        description="Detect hardcoded temporary directory paths",
        global_replace=True,
        test_cases=[
            ("/tmp/myfile.txt", "[TEMP_PATH]/myfile.txt"),  # nosec B108
            (r"C:\tmp\data.log", "[TEMP_PATH]/data.log"),
            ("/temp/cache", "[TEMP_PATH]/cache"),
            (r"C:\temp\work", "[TEMP_PATH]/work"),
            ("/regular/path", "/regular/path"),
        ],
    ),
    "replace_hardcoded_temp_paths": ValidatedPattern(
        name="replace_hardcoded_temp_paths",
        pattern=r'Path\("/tmp/([^"]+)"\)',
        replacement=r'Path(tempfile.gettempdir()) / "\1"',
        description="Replace hardcoded /tmp paths with tempfile.gettempdir()",
        global_replace=True,
        test_cases=[
            ('Path("/tmp/myfile.txt")', 'Path(tempfile.gettempdir()) / "myfile.txt"'),
            ('Path("/tmp/data.log")', 'Path(tempfile.gettempdir()) / "data.log"'),
            ('Path("/regular/path")', 'Path("/regular/path")'),
        ],
    ),
    "replace_hardcoded_temp_strings": ValidatedPattern(
        name="replace_hardcoded_temp_strings",
        pattern=r'"/tmp/([^"]+)"',
        replacement=r'str(Path(tempfile.gettempdir()) / "\1")',
        description="Replace hardcoded /tmp string paths with tempfile equivalent",
        global_replace=True,
        test_cases=[
            ('"/tmp/myfile.txt"', 'str(Path(tempfile.gettempdir()) / "myfile.txt")'),
            ('"/tmp/data.log"', 'str(Path(tempfile.gettempdir()) / "data.log")'),
            ('"/regular/path"', '"/regular/path"'),
        ],
    ),
    "replace_hardcoded_temp_single_quotes": ValidatedPattern(
        name="replace_hardcoded_temp_single_quotes",
        pattern=r"'/tmp/([^']+)'",
        replacement=r"str(Path(tempfile.gettempdir()) / '\1')",
        description="Replace hardcoded /tmp paths (single quotes) with tempfile"
        " equivalent",
        global_replace=True,
        test_cases=[
            ("'/tmp/myfile.txt'", "str(Path(tempfile.gettempdir()) / 'myfile.txt')"),
            ("'/tmp/data.log'", "str(Path(tempfile.gettempdir()) / 'data.log')"),
            ("'/regular/path'", "'/regular/path'"),
        ],
    ),
    "replace_test_path_patterns": ValidatedPattern(
        name="replace_test_path_patterns",
        pattern=r'Path\("/test/path"\)',
        replacement=r"Path(tempfile.gettempdir()) / 'test-path'",
        description="Replace hardcoded /test/path patterns with tempfile equivalent",
        test_cases=[
            ('Path("/test/path")', "Path(tempfile.gettempdir()) / 'test-path'"),
            ('Path("/other/path")', 'Path("/other/path")'),
        ],
    ),
    "replace_path_open_write": ValidatedPattern(
        name="replace_path_open_write",
        pattern=r'(\w+)\.open\(["\']wb?["\'][^)]*\)',
        replacement=r"atomic_file_write(\1)",
        test_cases=[
            ("path.open('w')", "atomic_file_write(path)"),
            ("file.open('wb')", "atomic_file_write(file)"),
        ],
        description="Replace file.open() with atomic_file_write",
    ),
    "replace_path_write_text": ValidatedPattern(
        name="replace_path_write_text",
        pattern=r"(\w+)\.write_text\(([^)]+)\)",
        replacement=r"await SafeFileOperations.safe_write_text(\1, \2, atomic=True)",
        test_cases=[
            (
                "path.write_text(content)",
                "await SafeFileOperations.safe_write_text(path, content, atomic=True)",
            ),
        ],
        description="Replace path.write_text with safe atomic write",
    ),
}
