from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._git_utils import get_files_by_extension


def has_trailing_whitespace(line: str) -> bool:
    line_stripped = line.rstrip("\n\r")

    return line_stripped != line_stripped.rstrip()


def fix_trailing_whitespace(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        modified = False
        new_lines = []
        for line in lines:
            if has_trailing_whitespace(line):
                line_body = line.rstrip("\r\n")
                stripped = line_body.rstrip()
                if line.endswith("\r\n"):
                    stripped += "\r\n"
                elif line.endswith("\n"):
                    stripped += "\n"
                new_lines.append(stripped)
                modified = True
            else:
                new_lines.append(line)

        if modified:
            file_path.write_text("".join(new_lines), encoding="utf-8")
            print(f"Fixed trailing whitespace: {file_path}")  # noqa: T201

        return modified

    except UnicodeDecodeError:
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)  # noqa: T201
        return False


def _collect_files_to_check(args: argparse.Namespace) -> list[Path]:
    if not args.files:
        files = get_files_by_extension(
            [".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".json"]
        )
        if not files:
            files = list(Path.cwd().rglob("*.py"))
    else:
        files = args.files

    return [f for f in files if f.is_file()]


def _process_files_in_check_mode(files: list[Path]) -> int:
    modified_count = 0
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        if any(has_trailing_whitespace(line) for line in lines):
            print(f"Trailing whitespace found: {file_path}")  # noqa: T201
            modified_count += 1
    return modified_count


def _process_files_in_fix_mode(files: list[Path]) -> int:
    modified_count = 0
    for file_path in files:
        if fix_trailing_whitespace(file_path):
            modified_count += 1
    return modified_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove trailing whitespace from files"
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files to check (default: all Python files in current directory)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check only, don't modify files",
    )

    args = parser.parse_args(argv)

    files = _collect_files_to_check(args)

    if not files:
        print("No files to check")  # noqa: T201
        return 0

    if args.check:
        modified_count = _process_files_in_check_mode(files)
    else:
        modified_count = _process_files_in_fix_mode(files)

    if modified_count > 0:
        if args.check:
            print(f"\n{modified_count} file(s) with trailing whitespace")  # noqa: T201
        else:
            print(f"\nFixed {modified_count} file(s)")  # noqa: T201

            print("files were modified by this hook")  # noqa: T201
        return 1

    print("No trailing whitespace found")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
