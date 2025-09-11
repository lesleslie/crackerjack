#!/usr/bin/env python3
"""Local regex patterns for session-mgmt-mcp using crackerjack's SAFE_PATTERNS architecture.

This module contains all validated regex patterns used throughout the session-mgmt-mcp
codebase, following crackerjack's centralized pattern approach for security and reliability.

All patterns are validated with comprehensive test cases and use proper replacement syntax.
"""

import re

from crackerjack.services.regex_patterns import ValidatedPattern

# Session Management MCP Validated Patterns Registry
SAFE_PATTERNS: dict[str, ValidatedPattern] = {
    # Code extraction patterns for search_enhanced.py
    "python_code_block": ValidatedPattern(
        name="python_code_block",
        pattern=r"```python\n(.*?)\n```",
        replacement=r"\1",
        description="Extract Python code from markdown code blocks",
        flags=re.DOTALL,
        test_cases=[
            ("```python\nprint('hello')\n```", "print('hello')"),
            ("```python\ndef func():\n    pass\n```", "def func():\n    pass"),
            ("```python\n\n```", ""),
            ("no code here", "no code here"),  # No change
        ],
    ),
    "generic_code_block": ValidatedPattern(
        name="generic_code_block",
        pattern=r"```\n(.*?)\n```",
        replacement=r"\1",
        description="Extract code from generic markdown code blocks",
        flags=re.DOTALL,
        test_cases=[
            ("```\nsome code\n```", "some code"),
            ("```\nline1\nline2\n```", "line1\nline2"),
            ("```\n\n```", ""),
            ("no fenced code", "no fenced code"),  # No change
        ],
    ),
    # Error pattern matching for search_enhanced.py
    "python_traceback": ValidatedPattern(
        name="python_traceback",
        pattern=r"Traceback \(most recent call last\):.*?(?=\n\n|\Z)",
        replacement=r"<TRACEBACK_MASKED>",
        description="Match Python traceback blocks with safe termination",
        flags=re.MULTILINE | re.DOTALL,
        test_cases=[
            (
                "Traceback (most recent call last):\n  File test.py\nError: msg\n\nNext line",
                "<TRACEBACK_MASKED>\n\nNext line",
            ),
            (
                "Traceback (most recent call last):\n  File test.py\nError: msg",
                "<TRACEBACK_MASKED>",
            ),
            ("No traceback here", "No traceback here"),  # No change
        ],
    ),
    "python_exception": ValidatedPattern(
        name="python_exception",
        pattern=r"\b(ValueError|TypeError|RuntimeError|SyntaxError|ImportError|AttributeError|KeyError|IndexError|FileNotFoundError|PermissionError|ConnectionError|TimeoutError|AssertionError|Exception|BaseException): (.+)",
        replacement=r"\1: <ERROR_MESSAGE_MASKED>",
        description="Match Python exception patterns safely",
        test_cases=[
            ("ValueError: invalid input", "ValueError: <ERROR_MESSAGE_MASKED>"),
            (
                "RuntimeError: something went wrong",
                "RuntimeError: <ERROR_MESSAGE_MASKED>",
            ),
            (
                "NotAnError: this should not match",
                "NotAnError: this should not match",
            ),  # No change
            ("SyntaxError: bad syntax", "SyntaxError: <ERROR_MESSAGE_MASKED>"),
        ],
    ),
    "javascript_error": ValidatedPattern(
        name="javascript_error",
        pattern=r"\b(Error|TypeError|ReferenceError): (.+)",
        replacement=r"\1: <JS_ERROR_MASKED>",
        description="Match JavaScript error patterns",
        test_cases=[
            ("TypeError: Cannot read property", "TypeError: <JS_ERROR_MASKED>"),
            ("Error: Something failed", "Error: <JS_ERROR_MASKED>"),
            ("ReferenceError: x is not defined", "ReferenceError: <JS_ERROR_MASKED>"),
            ("CustomError: not matched", "CustomError: not matched"),  # No change
        ],
    ),
    "compile_error": ValidatedPattern(
        name="compile_error",
        pattern=r"(error|Error): (.+) at line (\d+)",
        replacement=r"\1: <COMPILE_ERROR_MASKED> at line \3",
        description="Match compilation error patterns with line numbers",
        test_cases=[
            (
                "error: syntax error at line 42",
                "error: <COMPILE_ERROR_MASKED> at line 42",
            ),
            (
                "Error: missing semicolon at line 10",
                "Error: <COMPILE_ERROR_MASKED> at line 10",
            ),
            (
                "warning: deprecated at line 5",
                "warning: deprecated at line 5",
            ),  # No change
        ],
    ),
    "warning_pattern": ValidatedPattern(
        name="warning_pattern",
        pattern=r"(warning|Warning): (.+)",
        replacement=r"\1: <WARNING_MASKED>",
        description="Match warning message patterns",
        test_cases=[
            ("warning: deprecated function", "warning: <WARNING_MASKED>"),
            ("Warning: potential issue", "Warning: <WARNING_MASKED>"),
            ("info: just information", "info: just information"),  # No change
        ],
    ),
    "assertion_error": ValidatedPattern(
        name="assertion_error",
        pattern=r"AssertionError: (.+)",
        replacement=r"AssertionError: <ASSERTION_MASKED>",
        description="Match assertion error patterns",
        test_cases=[
            ("AssertionError: expected True", "AssertionError: <ASSERTION_MASKED>"),
            (
                "AssertionError: values don't match",
                "AssertionError: <ASSERTION_MASKED>",
            ),
            ("ValueError: not assertion", "ValueError: not assertion"),  # No change
        ],
    ),
    "import_error": ValidatedPattern(
        name="import_error",
        pattern=r"ImportError: (.+)",
        replacement=r"ImportError: <IMPORT_ERROR_MASKED>",
        description="Match import error patterns",
        test_cases=[
            (
                "ImportError: No module named 'xyz'",
                "ImportError: <IMPORT_ERROR_MASKED>",
            ),
            ("ImportError: cannot import name", "ImportError: <IMPORT_ERROR_MASKED>"),
            (
                "ModuleNotFoundError: different",
                "ModuleNotFoundError: different",
            ),  # No change
        ],
    ),
    "module_not_found": ValidatedPattern(
        name="module_not_found",
        pattern=r"ModuleNotFoundError: (.+)",
        replacement=r"ModuleNotFoundError: <MODULE_NOT_FOUND_MASKED>",
        description="Match module not found error patterns",
        test_cases=[
            (
                "ModuleNotFoundError: No module named 'test'",
                "ModuleNotFoundError: <MODULE_NOT_FOUND_MASKED>",
            ),
            (
                "ModuleNotFoundError: missing dependency",
                "ModuleNotFoundError: <MODULE_NOT_FOUND_MASKED>",
            ),
            (
                "ImportError: different error",
                "ImportError: different error",
            ),  # No change
        ],
    ),
    "file_not_found": ValidatedPattern(
        name="file_not_found",
        pattern=r"FileNotFoundError: (.+)",
        replacement=r"FileNotFoundError: <FILE_NOT_FOUND_MASKED>",
        description="Match file not found error patterns",
        test_cases=[
            (
                "FileNotFoundError: [Errno 2] No such file",
                "FileNotFoundError: <FILE_NOT_FOUND_MASKED>",
            ),
            (
                "FileNotFoundError: file missing",
                "FileNotFoundError: <FILE_NOT_FOUND_MASKED>",
            ),
            ("PermissionError: different", "PermissionError: different"),  # No change
        ],
    ),
    "permission_denied": ValidatedPattern(
        name="permission_denied",
        pattern=r"PermissionError: (.+)",
        replacement=r"PermissionError: <PERMISSION_ERROR_MASKED>",
        description="Match permission error patterns",
        test_cases=[
            (
                "PermissionError: [Errno 13] Permission denied",
                "PermissionError: <PERMISSION_ERROR_MASKED>",
            ),
            (
                "PermissionError: access denied",
                "PermissionError: <PERMISSION_ERROR_MASKED>",
            ),
            (
                "FileNotFoundError: different",
                "FileNotFoundError: different",
            ),  # No change
        ],
    ),
    "network_error": ValidatedPattern(
        name="network_error",
        pattern=r"(ConnectionError|TimeoutError|HTTPError): (.+)",
        replacement=r"\1: <NETWORK_ERROR_MASKED>",
        description="Match network-related error patterns",
        test_cases=[
            (
                "ConnectionError: Failed to connect",
                "ConnectionError: <NETWORK_ERROR_MASKED>",
            ),
            ("TimeoutError: Request timed out", "TimeoutError: <NETWORK_ERROR_MASKED>"),
            ("HTTPError: 404 Not Found", "HTTPError: <NETWORK_ERROR_MASKED>"),
            ("ValueError: not network", "ValueError: not network"),  # No change
        ],
    ),
    # Context pattern matching (boolean search)
    "debugging_context": ValidatedPattern(
        name="debugging_context",
        pattern=r"\b(debug|debugging|breakpoint|pdb|print\(\))\b",
        replacement=r"<DEBUG_CONTEXT>",
        description="Match debugging-related context patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("let's debug this issue", "let's <DEBUG_CONTEXT> this issue"),
            ("debugging the problem", "<DEBUG_CONTEXT> the problem"),
            ("set a breakpoint here", "set a <DEBUG_CONTEXT> here"),
            ("regular code", "regular code"),  # No change
        ],
    ),
    "testing_context": ValidatedPattern(
        name="testing_context",
        pattern=r"(test|pytest|unittest|assert|mock)",
        replacement=r"<TEST_CONTEXT>",
        description="Match testing-related context patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("run the test suite", "run the <TEST_CONTEXT> suite"),
            ("pytest configuration", "<TEST_CONTEXT> configuration"),
            ("unittest framework", "<TEST_CONTEXT> framework"),
            ("regular text", "regular text"),  # No change
        ],
    ),
    "error_handling_context": ValidatedPattern(
        name="error_handling_context",
        pattern=r"(try|except|finally|raise|catch)",
        replacement=r"<ERROR_HANDLING_CONTEXT>",
        description="Match error handling context patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("try to handle", "<ERROR_HANDLING_CONTEXT> to handle"),
            ("except ValueError", "<ERROR_HANDLING_CONTEXT> ValueError"),
            ("finally block", "<ERROR_HANDLING_CONTEXT> block"),
            ("normal flow", "normal flow"),  # No change
        ],
    ),
    "performance_context": ValidatedPattern(
        name="performance_context",
        pattern=r"(slow|performance|benchmark|optimize|profil)",
        replacement=r"<PERFORMANCE_CONTEXT>",
        description="Match performance-related context patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("this is slow", "this is <PERFORMANCE_CONTEXT>"),
            ("performance improvement", "<PERFORMANCE_CONTEXT> improvement"),
            ("benchmark results", "<PERFORMANCE_CONTEXT> results"),
            ("fast code", "fast code"),  # No change
        ],
    ),
    "security_context": ValidatedPattern(
        name="security_context",
        pattern=r"(security|authentication|authorization|token|password)",
        replacement=r"<SECURITY_CONTEXT>",
        description="Match security-related context patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("security audit", "<SECURITY_CONTEXT> audit"),
            ("authentication required", "<SECURITY_CONTEXT> required"),
            ("token validation", "<SECURITY_CONTEXT> validation"),
            ("regular text", "regular text"),  # No change
        ],
    ),
    # Time parsing patterns for search_enhanced.py
    "time_ago_pattern": ValidatedPattern(
        name="time_ago_pattern",
        pattern=r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago",
        replacement=r"\1 \2 ago",
        description="Match time ago expressions for parsing",
        test_cases=[
            ("5 minutes ago", "5 minute ago"),
            ("2 hours ago", "2 hour ago"),
            ("1 day ago", "1 day ago"),
            ("3 weeks ago", "3 week ago"),
            ("not a time", "not a time"),  # No change
        ],
    ),
    "relative_time_pattern": ValidatedPattern(
        name="relative_time_pattern",
        pattern=r"(today|yesterday|this\s+week|last\s+week|this\s+month|last\s+month)",
        replacement=r"<RELATIVE_TIME>",
        description="Match relative time expressions",
        flags=re.IGNORECASE,
        test_cases=[
            ("today is good", "<RELATIVE_TIME> is good"),
            ("yesterday we worked", "<RELATIVE_TIME> we worked"),
            ("this week's plan", "<RELATIVE_TIME>'s plan"),
            ("some other day", "some other day"),  # No change
        ],
    ),
    "since_time_pattern": ValidatedPattern(
        name="since_time_pattern",
        pattern=r"since\s+(today|yesterday|this\s+week|last\s+week)",
        replacement=r"since <TIME_REFERENCE>",
        description="Match 'since' time expressions",
        flags=re.IGNORECASE,
        test_cases=[
            ("since today", "since <TIME_REFERENCE>"),
            ("since yesterday", "since <TIME_REFERENCE>"),
            ("since this week", "since <TIME_REFERENCE>"),
            ("since forever", "since forever"),  # No change
        ],
    ),
    "last_duration_pattern": ValidatedPattern(
        name="last_duration_pattern",
        pattern=r"in\s+the\s+last\s+(\d+)\s+(minute|hour|day|week|month|year)s?",
        replacement=r"in the last \1 \2",
        description="Match 'in the last X units' patterns",
        test_cases=[
            ("in the last 5 minutes", "in the last 5 minute"),
            ("in the last 2 hours", "in the last 2 hour"),
            ("in the last 10 days", "in the last 10 day"),
            ("not a duration", "not a duration"),  # No change
        ],
    ),
    "iso_date_pattern": ValidatedPattern(
        name="iso_date_pattern",
        pattern=r"(\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))",
        replacement=r"<ISO_DATE>",
        description="Match valid ISO date format (YYYY-MM-DD)",
        test_cases=[
            ("2023-12-25", "<ISO_DATE>"),
            ("Date: 2024-01-15 is today", "Date: <ISO_DATE> is today"),
            ("not-a-date", "not-a-date"),  # No change
            (
                "2023-13-45",
                "2023-13-45",
            ),  # Invalid date, no change expected
        ],
    ),
    "us_date_pattern": ValidatedPattern(
        name="us_date_pattern",
        pattern=r"(\d{1,2}/\d{1,2}/\d{4})",
        replacement=r"<US_DATE>",
        description="Match US date format (MM/DD/YYYY or M/D/YYYY)",
        test_cases=[
            ("12/25/2023", "<US_DATE>"),
            ("1/5/2024", "<US_DATE>"),
            ("Meeting on 3/15/2024 at noon", "Meeting on <US_DATE> at noon"),
            ("not/a/date", "not/a/date"),  # No change
        ],
    ),
    # Crackerjack integration patterns for output parsing
    "pytest_result": ValidatedPattern(
        name="pytest_result",
        pattern=r"(\w+\.py)::\s*(\w+)\s*(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\s*(?:\[(\d+%)\])?\s*(?:\((.+)\))?",
        replacement=r"TEST: \1::\2 -> \3",
        description="Parse pytest test results with optional percentage and timing",
        test_cases=[
            (
                "test_file.py:: test_function PASSED",
                "TEST: test_file.py::test_function -> PASSED",
            ),
            (
                "test_example.py:: test_method FAILED [50%] (0.05s)",
                "TEST: test_example.py::test_method -> FAILED",
            ),
            (
                "test_skip.py:: test_skip SKIPPED",
                "TEST: test_skip.py::test_skip -> SKIPPED",
            ),
            ("not a test result", "not a test result"),  # No change
        ],
    ),
    "coverage_summary": ValidatedPattern(
        name="coverage_summary",
        pattern=r"TOTAL\s+\d+\s+\d+\s+(\d+)%",
        replacement=r"COVERAGE: \1%",
        description="Extract total coverage percentage from coverage reports",
        test_cases=[
            ("TOTAL    1000    50    95%", "COVERAGE: 95%"),
            ("TOTAL    500    25    78%", "COVERAGE: 78%"),
            ("subtotal   100    5    90%", "subtotal   100    5    90%"),  # No change
        ],
    ),
    "ruff_error": ValidatedPattern(
        name="ruff_error",
        pattern=r"([^:\s]+):(\d+):(\d+):\s*([A-Z]\d{3,4})\s*(.+)",
        replacement=r"RUFF: \1 line \2 -> \4: \5",
        description="Parse Ruff linting errors with file, line, column, code, and message",
        test_cases=[
            (
                "src/main.py:42:10: E501 line too long (88 > 79 characters)",
                "RUFF: src/main.py line 42 -> E501: line too long (88 > 79 characters)",
            ),
            (
                "test.py:1:1: F401 imported but unused",
                "RUFF: test.py line 1 -> F401: imported but unused",
            ),
            ("not a ruff error", "not a ruff error"),  # No change
        ],
    ),
    "mypy_error": ValidatedPattern(
        name="mypy_error",
        pattern=r"([^:\s]+):(\d+):\s*error:\s*(.+)",
        replacement=r"MYPY: \1 line \2 -> \3",
        description="Parse mypy type checking errors with file, line, and message",
        test_cases=[
            (
                "src/module.py:15: error: Argument 1 has incompatible type",
                "MYPY: src/module.py line 15 -> Argument 1 has incompatible type",
            ),
            (
                "main.py:8: error: Name 'x' is not defined",
                "MYPY: main.py line 8 -> Name 'x' is not defined",
            ),
            ("not a mypy error", "not a mypy error"),  # No change
        ],
    ),
    "bandit_finding": ValidatedPattern(
        name="bandit_finding",
        pattern=r">> Issue: \[([A-Z]\d+):([a-z_]+)\]\s*(.+)",
        replacement=r"BANDIT: \1 (\2) -> \3",
        description="Parse Bandit security findings with code, severity, and description",
        test_cases=[
            (
                ">> Issue: [B602:subprocess_popen_with_shell_equals_true] Possible shell injection",
                "BANDIT: B602 (subprocess_popen_with_shell_equals_true) -> Possible shell injection",
            ),
            (
                ">> Issue: [B108:hardcoded_tmp_directory] Use of insecure temp",
                "BANDIT: B108 (hardcoded_tmp_directory) -> Use of insecure temp",
            ),
            ("not a bandit finding", "not a bandit finding"),  # No change
        ],
    ),
    "quality_score": ValidatedPattern(
        name="quality_score",
        pattern=r"Quality Score:\s*(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\s*\((\d+(?:\.\d+)?)%\)",
        replacement=r"QUALITY: \3% (\1/\2)",
        description="Parse quality score with percentage calculation",
        test_cases=[
            ("Quality Score: 85.5/100 (85.5%)", "QUALITY: 85.5% (85.5/100)"),
            ("Quality Score: 90/100 (90%)", "QUALITY: 90% (90/100)"),
            ("Final Score: 95/100", "Final Score: 95/100"),  # No change
        ],
    ),
    "execution_time": ValidatedPattern(
        name="execution_time",
        pattern=r"(\d+(?:\.\d+)?)\s*(s|ms|seconds?|milliseconds?)",
        replacement=r"\1\2",
        description="Normalize execution time formats",
        test_cases=[
            ("2.5 seconds", "2.5seconds"),
            ("150 ms", "150ms"),
            ("0.05 s", "0.05s"),
            ("fast enough", "fast enough"),  # No change
        ],
    ),
    "progress_indicator": ValidatedPattern(
        name="progress_indicator",
        pattern=r"\[([=>\s]*)\]\s*(\d+)%",
        replacement=r"PROGRESS: \2%",
        description="Parse progress bars with percentage",
        test_cases=[
            ("[=====>    ] 50%", "PROGRESS: 50%"),
            ("[=========>] 90%", "PROGRESS: 90%"),
            ("[          ]  0%", "PROGRESS: 0%"),
            ("not progress", "not progress"),  # No change
        ],
    ),
    "git_commit_hash": ValidatedPattern(
        name="git_commit_hash",
        pattern=r"\b([a-f0-9]{7,40})\b",
        replacement=r"<COMMIT:\1>",
        description="Match Git commit hashes (7-40 hex characters)",
        test_cases=[
            ("commit abc1234 was merged", "commit <COMMIT:abc1234> was merged"),
            (
                "long hash abcdef1234567890abcdef1234567890abcdef12",
                "long hash <COMMIT:abcdef1234567890abcdef1234567890abcdef12>",
            ),
            ("short ab12", "short ab12"),  # Too short
            ("not hex ghi1234", "not hex ghi1234"),  # Contains non-hex
        ],
    ),
    "file_path_with_line": ValidatedPattern(
        name="file_path_with_line",
        pattern=r"([A-Za-z_][A-Za-z0-9_/.-]*\.py):(\d+)",
        replacement=r"\1 line \2",
        description="Match file paths with line numbers (file.py:123)",
        test_cases=[
            ("src/main.py:42", "src/main.py line 42"),
            ("test_file.py:1", "test_file.py line 1"),
            ("sub/dir/module.py:100", "sub/dir/module.py line 100"),
            ("not-python.txt:50", "not-python.txt:50"),  # No change
        ],
    ),
    # Memory optimizer patterns
    "sentence_split": ValidatedPattern(
        name="sentence_split",
        pattern=r"[.!\?]+",
        replacement=r" ",
        description="Replace sentence-ending punctuation with spaces for splitting",
        test_cases=[
            ("Hello world.", "Hello world "),
            ("How are you?", "How are you "),
            ("Multiple!!!", "Multiple "),
        ],
    ),
    "code_block_cleanup": ValidatedPattern(
        name="code_block_cleanup",
        pattern=r"```.*?```",
        replacement=r"",
        description="Remove code blocks from text for keyword extraction",
        flags=re.DOTALL,
        test_cases=[
            ("Text ```python\ncode\n``` more text", "Text  more text"),
            ("```\njust code\n```", ""),
            ("no code blocks", "no code blocks"),
        ],
    ),
    "inline_code_cleanup": ValidatedPattern(
        name="inline_code_cleanup",
        pattern=r"`[^`]+`",
        replacement=r"",
        description="Remove inline code from text",
        test_cases=[
            ("Use `function()` to call", "Use  to call"),
            ("No inline code", "No inline code"),
            ("`code`", ""),
        ],
    ),
    "word_extraction": ValidatedPattern(
        name="word_extraction",
        pattern=r"\b[a-zA-Z]{1,2}\b",
        replacement=r"",
        description="Remove short words (1-2 chars) for keyword analysis",
        test_cases=[
            ("short words", "short words"),
            ("a test", " test"),
            ("123 in 456", "123  456"),
        ],
    ),
    "word_boundary": ValidatedPattern(
        name="word_boundary",
        pattern=r"[^\w\s]+",
        replacement=r" ",
        description="Replace non-word characters with spaces for word boundary detection",
        test_cases=[
            ("hello-world", "hello world"),
            ("test@example", "test example"),
            ("underscored_var", "underscored_var"),
        ],
    ),
    # File extension patterns for memory optimizer
    "python_files": ValidatedPattern(
        name="python_files",
        pattern=r"(\w+\.py)",
        replacement=r"[\1]",
        description="Wrap Python file references in brackets",
        test_cases=[
            ("main.py script", "[main.py] script"),
            ("test_file.py found", "[test_file.py] found"),
            ("no files here", "no files here"),
        ],
    ),
    "javascript_files": ValidatedPattern(
        name="javascript_files",
        pattern=r"(\w+\.js)",
        replacement=r"[\1]",
        description="Wrap JavaScript file references in brackets",
        test_cases=[
            ("app.js file", "[app.js] file"),
            ("script.js found", "[script.js] found"),
            ("no files", "no files"),
        ],
    ),
    "typescript_files": ValidatedPattern(
        name="typescript_files",
        pattern=r"(\w+\.ts)",
        replacement=r"[\1]",
        description="Wrap TypeScript file references in brackets",
        test_cases=[
            ("index.ts file", "[index.ts] file"),
            ("component.ts interface", "[component.ts] interface"),
            ("other files", "other files"),
        ],
    ),
    "json_files": ValidatedPattern(
        name="json_files",
        pattern=r"(\w+\.json)",
        replacement=r"[\1]",
        description="Match JSON file references",
        test_cases=[
            ("config.json settings", "[config.json] settings"),
            ("package.json file", "[package.json] file"),
            ("no json", "no json"),
        ],
    ),
    "markdown_files": ValidatedPattern(
        name="markdown_files",
        pattern=r"(\w+\.md)",
        replacement=r"[\1]",
        description="Match Markdown file references",
        test_cases=[
            ("README.md documentation", "[README.md] documentation"),
            ("docs.md file", "[docs.md] file"),
            ("no markdown", "no markdown"),
        ],
    ),
    # Advanced search patterns
    "function_definition": ValidatedPattern(
        name="function_definition",
        pattern=r"\bdef\s+(\w+)",
        replacement=r"function:\1",
        description="Extract Python function definitions",
        test_cases=[
            ("def main():", "function:main():"),
            ("def get_data(param):", "function:get_data(param):"),
            ("no functions here", "no functions here"),
        ],
    ),
    "class_definition": ValidatedPattern(
        name="class_definition",
        pattern=r"\bclass\s+(\w+)",
        replacement=r"class:\1",
        description="Extract Python class definitions",
        test_cases=[
            ("class MyClass:", "class:MyClass:"),
            ("class SearchEngine(Base):", "class:SearchEngine(Base):"),
            ("no classes here", "no classes here"),
        ],
    ),
    "file_extension": ValidatedPattern(
        name="file_extension",
        pattern=r"\.(\w{2,4})\b",
        replacement=r"filetype:\1",
        description="Extract file extensions for categorization",
        test_cases=[
            ("file.py and test.json", "filefiletype:py and test.json"),
            ("config.yaml setup", "configfiletype:yaml setup"),
            ("no extensions", "no extensions"),
        ],
    ),
    # Language detection patterns
    "python_code": ValidatedPattern(
        name="python_code",
        pattern=r"\b(def|class|import|from|if __name__|async|await|yield)\b",
        replacement=r"python",
        description="Detect Python code patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("def function():", "python function():"),
            ("import os", "python os"),
            ("if __name__ == '__main__'", "python == '__main__'"),
            ("regular text", "regular text"),
        ],
    ),
    "javascript_code": ValidatedPattern(
        name="javascript_code",
        pattern=r"\b(function|var|let|const|=>|require|module\.exports|console\.log)\b",
        replacement=r"javascript",
        description="Detect JavaScript code patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("function myFunc()", "javascript myFunc()"),
            ("const data = []", "javascript data = []"),
            ("console.log('hello')", "javascript('hello')"),
            ("regular text", "regular text"),
        ],
    ),
    "sql_code": ValidatedPattern(
        name="sql_code",
        pattern=r"\b(SELECT|FROM|WHERE|JOIN|INSERT|UPDATE|DELETE|CREATE|TABLE)\b",
        replacement=r"sql",
        description="Detect SQL code patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("SELECT * FROM users", "sql * FROM users"),
            ("INSERT INTO table", "sql INTO table"),
            ("CREATE TABLE test", "sql TABLE test"),
            ("regular text", "regular text"),
        ],
    ),
    "error_keywords": ValidatedPattern(
        name="error_keywords",
        pattern=r"\b(Error|Exception|Traceback|Failed|TypeError|ValueError)\b",
        replacement=r"error",
        description="Detect error-related keywords",
        flags=re.IGNORECASE,
        test_cases=[
            ("ValueError occurred", "error occurred"),
            ("Exception raised", "error raised"),
            ("Traceback found", "error found"),
            ("regular text", "regular text"),
        ],
    ),
    # Crackerjack-specific patterns for tools integration
    "crackerjack_command": ValidatedPattern(
        name="crackerjack_command",
        pattern=r"crackerjack\s+(\w+)",
        replacement=r"[\1]",
        description="Extract command from crackerjack execution logs",
        flags=0,
        test_cases=[
            ("crackerjack lint", "[lint]"),
            ("running crackerjack test now", "running [test] now"),
            ("crackerjack analyze completed", "[analyze] completed"),
            ("just crackerjack", "just crackerjack"),  # No change - no command
        ],
    ),
    # Token optimization patterns
    "whitespace_normalize": ValidatedPattern(
        name="whitespace_normalize",
        pattern=r"\s+",
        replacement=r" ",
        description="Normalize whitespace for content hashing",
        flags=0,
        test_cases=[
            ("  multiple   spaces  ", " multiple   spaces  "),
            ("tabs\t\tand\nnewlines\n\n", "tabs and\nnewlines\n\n"),
            ("normal text", "normal text"),
        ],
    ),
}
