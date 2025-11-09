"""Validate Python file AST syntax.

This tool is a native Python implementation replacing pre-commit's
check-ast hook. It scans Python files and validates their AST syntax.

Usage:
    python -m crackerjack.tools.check_ast [files...]

Exit Codes:
    0: All Python files have valid ASTs
    1: One or more Python files have syntax errors (invalid ASTs)
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

from ._git_utils import get_files_by_extension


def validate_ast_file(file_path: Path) -> tuple[bool, str | None]:
    """Validate a Python file's AST syntax.

    Args:
        file_path: Path to Python file to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if file has valid Python AST syntax
        - error_message: Error description if is_valid is False, None otherwise
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            content = f.read()

        # Parse the content into an AST
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def main(argv: list[str] | None = None) -> int:
    """Main entry point for check-ast tool.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 if all Python files have valid ASTs, 1 if any errors found
    """
    parser = argparse.ArgumentParser(description="Validate Python file AST syntax")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Python files to check (default: all .py files)",
    )

    args = parser.parse_args(argv)

    # Default to all git-tracked Python files if none specified
    if not args.files:
        # Get all tracked Python files (respects .gitignore via git ls-files)
        files = get_files_by_extension([".py"])
        if not files:
            # Fallback to rglob if not in git repo
            files = list(Path.cwd().rglob("*.py"))
    else:
        files = args.files

    # Filter to existing files only
    files = [f for f in files if f.is_file()]

    if not files:
        print("No Python files to check")  # noqa: T201
        return 0

    # Process files
    error_count = 0
    for file_path in files:
        is_valid, error_msg = validate_ast_file(file_path)

        if not is_valid:
            print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
            error_count += 1
        else:
            print(f"✓ {file_path}: Valid AST")  # noqa: T201

    # Return appropriate exit code
    if error_count > 0:
        print(f"\n{error_count} Python file(s) with AST errors", file=sys.stderr)  # noqa: T201
        return 1

    print(f"\nAll {len(files)} Python file(s) have valid ASTs")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
