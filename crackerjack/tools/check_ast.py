from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

from ._git_utils import get_files_by_extension


def validate_ast_file(file_path: Path) -> tuple[bool, str | None]:
    try:
        with file_path.open(encoding="utf-8") as f:
            content = f.read()

        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Python file AST syntax")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Python files to check (default: all .py files)",
    )

    args = parser.parse_args(argv)

    if not args.files:
        files = get_files_by_extension([".py"])
        if not files:
            files = list(Path.cwd().rglob("*.py"))
    else:
        files = args.files

    files = [f for f in files if f.is_file()]

    if not files:
        print("No Python files to check")  # noqa: T201
        return 0

    error_count = 0
    for file_path in files:
        is_valid, error_msg = validate_ast_file(file_path)

        if not is_valid:
            print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
            error_count += 1
        else:
            print(f"✓ {file_path}: Valid AST")  # noqa: T201

    if error_count > 0:
        print(f"\n{error_count} Python file(s) with AST errors", file=sys.stderr)  # noqa: T201
        return 1

    print(f"\nAll {len(files)} Python file(s) have valid ASTs")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
