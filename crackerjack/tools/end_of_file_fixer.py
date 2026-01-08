from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._git_utils import get_files_by_extension


def needs_newline_fix(content: bytes) -> tuple[bool, bytes | None]:
    if not content:
        return False, None

    if content.endswith(b"\n"):
        stripped = content.rstrip(b"\n")
        if len(content) - len(stripped) > 1:
            return True, stripped + b"\n"

        return False, None

    return True, content + b"\n"


def fix_end_of_file(file_path: Path) -> bool:
    try:
        content = file_path.read_bytes()

        needs_fix, fixed_content = needs_newline_fix(content)

        if needs_fix and fixed_content is not None:
            file_path.write_bytes(fixed_content)
            print(f"Fixed end-of-file: {file_path}")  # noqa: T201
            return True

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
        try:
            content = file_path.read_bytes()
            needs_fix, _ = needs_newline_fix(content)

            if needs_fix:
                print(f"Missing/incorrect end-of-file: {file_path}")  # noqa: T201
                modified_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)  # noqa: T201
    return modified_count


def _process_files_in_fix_mode(files: list[Path]) -> int:
    modified_count = 0
    for file_path in files:
        try:
            if fix_end_of_file(file_path):
                modified_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)  # noqa: T201
    return modified_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ensure files end with exactly one newline"
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files to check (default: all text files in current directory)",
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
            print(f"\n{modified_count} file(s) with incorrect end-of-file")  # noqa: T201
        else:
            print(f"\nFixed {modified_count} file(s)")  # noqa: T201

            print("files were modified by this hook")  # noqa: T201
        return 1

    print("All files end with correct newline")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
