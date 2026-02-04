#!/usr/bin/env python3

import re
from pathlib import Path


def fix_test_file(file_path: Path, dry_run: bool = True) -> bool:
    with file_path.open() as f:
        original_lines = f.readlines()


    import_lines = []
    in_docstring = False
    docstring_delimiter = None

    for line_num, line in enumerate(original_lines):
        stripped = line.strip()


        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = True
                docstring_delimiter = stripped[:3]
                continue
        else:
            if stripped.startswith(docstring_delimiter):
                in_docstring = False
                docstring_delimiter = None
            continue


        if not (stripped.startswith("from crackerjack.") or stripped.startswith("import crackerjack.")):
            continue


        if any(safe in line for safe in ["models.protocols", "import CrackerjackSettings", "import pytest"]):
            continue


        indent = len(line) - len(line.lstrip())
        import_lines.append((line_num, line.rstrip(), indent))

    if not import_lines:
        return False


    new_lines = []
    imports_to_add = {}
    current_test_function = None
    in_docstring = False
    docstring_delimiter = None

    for line_num, line in enumerate(original_lines):
        stripped = line.strip()


        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = True
                docstring_delimiter = stripped[:3]
        else:
            if stripped.startswith(docstring_delimiter):
                in_docstring = False
                docstring_delimiter = None


        is_expensive_import = False
        for imp_line_num, imp_stmt, _ in import_lines:
            if line_num == imp_line_num:
                is_expensive_import = True

                if current_test_function:
                    if current_test_function not in imports_to_add:
                        imports_to_add[current_test_function] = []
                    imports_to_add[current_test_function].append(imp_stmt)
                break

        if is_expensive_import:
            continue


        if not in_docstring and stripped.startswith("def test_"):
            current_test_function = stripped.split("(")[0].replace("def ", "")

            if current_test_function in imports_to_add:
                new_lines.append(line)

                for imp_stmt in imports_to_add[current_test_function]:

                    base_indent = len(line) - len(line.lstrip())
                    new_lines.append(" " * (base_indent + 4) + imp_stmt + "\n")
                continue

        new_lines.append(line)


    print(f"\n{'[DRY RUN] ' if dry_run else ''}Fixing: {file_path}")
    print(f"  Moving {len(import_lines)} imports into test functions")

    if dry_run:

        for i, (line_num, imp_stmt, _) in enumerate(import_lines[:3]):
            print(f"  Line {line_num}: {imp_stmt}")
        if len(import_lines) > 3:
            print(f"  ... and {len(import_lines) - 3} more")
    else:

        with file_path.open("w") as f:
            f.writelines(new_lines)

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fix expensive test imports")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without modifying files")
    parser.add_argument("--file", help="Fix specific file only")
    args = parser.parse_args()

    if args.file:
        files = [Path(args.file)]
    else:
        files = list(Path("tests").glob("test_*.py"))

    print(f"Checking {len(files)} test files...\n")

    fixed_count = 0
    for file_path in files:
        if fix_test_file(file_path, dry_run=args.dry_run):
            fixed_count += 1

    print(f"\n{'Would fix' if args.dry_run else 'Fixed'} {fixed_count} files")

    if args.dry_run:
        print("\nRun without --dry-run to apply changes")


if __name__ == "__main__":
    main()
