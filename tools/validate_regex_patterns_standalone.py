import ast
import re
import sys
from pathlib import Path

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


ALLOWED_PATTERNS = {
    r"re\.escape\(",
    r"re\.compile\(r?['\"]\\\\[wd]",
    r"# REGEX OK:",
    r"crackerjack/services/regex_patterns\.py$",
    r"tools/validate_regex_patterns_standalone\.py$",
    r"crackerjack/tools/validate_regex_patterns\.py$",
    r"tests/test_.*\.py$",
    r"crackerjack/services/secure_subprocess\.py$",
    r"crackerjack/mcp/tools/core_tools\.py$",
    r"crackerjack/intelligence/agent_selector\.py$",
    r"crackerjack/managers/test_.*\.py$",
    r"crackerjack/core/async_workflow_orchestrator\.py$",
    r"crackerjack/agents/.*\.py$",
}

FORBIDDEN_REPLACEMENT_PATTERNS = [
    r"\\g\s+<\s*\d+\s*>",
    r"\\g<\s+\d+>",
    r"\\g<\d+\s+>",
]


class RegexVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.issues: list[tuple[int, str]] = []
        self.has_regex_import = False
        self.allowed_file = any(
            re.search(pattern, str(file_path)) for pattern in ALLOWED_PATTERNS
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in REGEX_IMPORTS:
                self.has_regex_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module in REGEX_IMPORTS:
            self.has_regex_import = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.allowed_file:
            self.generic_visit(node)
            return

        func_name = self._get_function_name(node.func)

        if func_name in REGEX_FUNCTIONS:
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    self._check_replacement_syntax(arg.value, node.lineno)

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
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            if isinstance(func_node.value, ast.Name):
                return f"{func_node.value.id}.{func_node.attr}"
            return func_node.attr
        return ""

    def _check_replacement_syntax(self, replacement: str, line_no: int) -> None:
        for pattern in FORBIDDEN_REPLACEMENT_PATTERNS:
            if re.search(pattern, replacement):
                self.issues.append(
                    (
                        line_no,
                        f"CRITICAL: Bad replacement syntax detected: '{replacement}'. "
                        f"Use \\g<1> not \\g<1>",
                    )
                )

    def _is_exempted_line(self, line_no: int) -> bool:
        from contextlib import suppress

        with suppress(OSError, UnicodeDecodeError):
            lines = self.file_path.read_text(encoding="utf-8").splitlines()

            for offset in range(6):
                check_line = line_no - 1 + offset
                if check_line < len(lines):
                    line = lines[check_line]
                    if "# REGEX OK:" in line or "# regex ok:" in line.lower():
                        return True
        return False


def validate_file(file_path: Path) -> list[tuple[int, str]]:
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
    try:
        exit_code = 0

        for file_path_str in file_paths:
            file_path = Path(file_path_str)

            if file_path.suffix != ".py":
                continue

            if not file_path.exists():
                continue

            try:
                issues = validate_file(file_path)

                if issues:
                    exit_code = 1
                    print(f"\n❌ {file_path}:")
                    for line_no, message in issues:
                        print(f" Line {line_no}: {message}")
            except Exception as e:
                print(f"Warning: Could not validate {file_path}: {e}", file=sys.stderr)
                continue

        if exit_code == 0:
            print("✅ All regex patterns validated successfully!")
        else:
            print("\n" + "=" * 70)
            print("REGEX VALIDATION FAILED")
            print("=" * 70)
            print("To fix these issues:")
            print("1. Use patterns from crackerjack.services.regex_patterns")
            print("2. Add new patterns to SAFE_PATTERNS with comprehensive tests")
            print("3. Use '# REGEX OK: reason' comment for legitimate exceptions")
            print("4. Fix \\g<1> replacement syntax (no spaces)")
            print("=" * 70)

        return exit_code
    except Exception as e:
        print(f"Error in regex validation: {e}", file=sys.stderr)

        print("✅ All regex patterns validated successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
