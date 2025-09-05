#!/usr/bin/env python3
"""
Pre-commit hook to validate regex pattern usage.

This script ensures all regex patterns use validated patterns from
crackerjack.services.regex_patterns instead of raw re.sub() calls.

CRITICAL: Prevents spacing issues by catching bad regex patterns before they
enter the codebase.
"""

import ast
import re
import sys
from pathlib import Path

# Patterns that indicate regex usage
REGEX_IMPORTS = {
    "re",
    "regex",
}

REGEX_FUNCTIONS = {
    "re.sub",
    "re.search",
    "re.match",
    "re.findall",
    "re.split",
    "re.compile",
    "regex.sub",
    "regex.search",
    "regex.match",
    "regex.findall",
    "regex.split",
    "regex.compile",
}

# Allowed regex usage patterns (whitelisted)
ALLOWED_PATTERNS = {
    # Simple string operations are OK
    r"re\.escape\(",
    r"re\.compile\(r?['\"]\\\\[wd]",  # Simple character classes
    # Test files can use regex for testing
    r"# REGEX OK:",  # Comment-based exemption
    # Validation in regex_patterns.py itself
    r"crackerjack/services/regex_patterns\.py$",
}

FORBIDDEN_REPLACEMENT_PATTERNS = [
    r"\\g\s*<\s*\d+\s*>",  # \g < 1 > with spaces
    r"\\g<\s+\d+>",  # \g< 1> with space after <
    r"\\g<\d+\s+>",  # \g<1 > with space before >
]


class RegexVisitor(ast.NodeVisitor):
    """AST visitor to find regex usage patterns."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.issues: list[tuple[int, str]] = []
        self.has_regex_import = False
        self.allowed_file = any(
            re.search(pattern, str(file_path)) for pattern in ALLOWED_PATTERNS
        )

    def visit_Import(self, node: ast.Import) -> None:
        """Check for regex module imports."""
        for alias in node.names:
            if alias.name in REGEX_IMPORTS:
                self.has_regex_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check for regex imports from modules."""
        if node.module in REGEX_IMPORTS:
            self.has_regex_import = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check for regex function calls."""
        if self.allowed_file:
            self.generic_visit(node)
            return

        func_name = self._get_function_name(node.func)

        if func_name in REGEX_FUNCTIONS:
            # Check for bad replacement syntax in arguments
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    self._check_replacement_syntax(arg.value, node.lineno)

            # Flag non-whitelisted regex usage
            if not self._is_exempted_line(node.lineno):
                self.issues.append(
                    (
                        node.lineno,
                        f"Raw regex usage detected: {func_name}(). "
                        f"Use validated patterns from crackerjack.services.regex_patterns instead.",
                    )
                )

        self.generic_visit(node)

    def _get_function_name(self, func_node: ast.AST) -> str:
        """Extract function name from AST node."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            if isinstance(func_node.value, ast.Name):
                return f"{func_node.value.id}.{func_node.attr}"
            return func_node.attr
        return ""

    def _check_replacement_syntax(self, replacement: str, line_no: int) -> None:
        """Check for forbidden replacement syntax patterns."""
        for pattern in FORBIDDEN_REPLACEMENT_PATTERNS:
            if re.search(pattern, replacement):
                self.issues.append(
                    (
                        line_no,
                        f"CRITICAL: Bad replacement syntax detected: '{replacement}'. "
                        f"Use \\g<1> not \\g < 1 >",
                    )
                )

    def _is_exempted_line(self, line_no: int) -> bool:
        """Check if line has exemption comment."""
        from contextlib import suppress

        with suppress(OSError, UnicodeDecodeError):
            with self.file_path.open(encoding="utf-8") as f:
                lines = f.readlines()
                if line_no <= len(lines):
                    line = lines[line_no - 1]
                    return "# REGEX OK:" in line or "# regex ok:" in line.lower()
        return False


def validate_file(file_path: Path) -> list[tuple[int, str]]:
    """Validate a single Python file for regex pattern usage."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [(1, f"Error reading file: {e}")]

    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        return [(e.lineno or 1, f"Syntax error: {e}")]

    visitor = RegexVisitor(file_path)
    visitor.visit(tree)
    return visitor.issues


def main(file_paths: list[str]) -> int:
    """Main validation function for pre-commit hook."""
    exit_code = 0

    for file_path_str in file_paths:
        file_path = Path(file_path_str)

        # Skip non-Python files
        if file_path.suffix != ".py":
            continue

        # Skip files that don't exist
        if not file_path.exists():
            continue

        issues = validate_file(file_path)

        if issues:
            exit_code = 1
            print(f"\n❌ {file_path}:")
            for line_no, message in issues:
                print(f"  Line {line_no}: {message}")

    if exit_code == 0:
        print("✅ All regex patterns validated successfully!")
    else:
        print("\n" + "=" * 80)
        print("REGEX VALIDATION FAILED")
        print("=" * 80)
        print("To fix these issues:")
        print("1. Use patterns from crackerjack.services.regex_patterns")
        print("2. Add new patterns to SAFE_PATTERNS with comprehensive tests")
        print("3. Use '# REGEX OK: reason' comment for legitimate exceptions")
        print("4. Fix \\g<1> replacement syntax (no spaces)")
        print("=" * 80)

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
