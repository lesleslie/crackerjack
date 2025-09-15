#!/usr/bin/env python3
"""Fix missing 'import typing as t' in files that use 't' but don't import it."""

import subprocess
from pathlib import Path

from crackerjack.services.regex_patterns import SAFE_PATTERNS


def get_files_needing_typing_import() -> list[str]:
    """Get files that use 't' but don't have the import."""
    try:
        result = subprocess.run(
            ["python", "-m", "mypy", "crackerjack/", "--ignore-missing-imports"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        files = set()
        for line in result.stderr.splitlines():
            if 'Name "t" is not defined' in line:
                file_path = line.split(":")[0]
                files.add(file_path)

        return list(files)
    except Exception as e:
        print(f"Error getting files: {e}")
        return []


def file_needs_typing_import(file_path: str) -> bool:
    """Check if file uses 't.' but doesn't have 'import typing as t'."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # REGEX OK: Using safe pattern for typing detection
        uses_t = SAFE_PATTERNS["detect_typing_usage"].test(content)

        # Check if it already has the import
        has_import = "import typing as t" in content or "from typing import" in content

        return uses_t and not has_import
    except Exception:
        return False


def add_typing_import(file_path: str) -> None:
    """Add 'import typing as t' to a file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Find where to insert the import
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("import ") or line.strip().startswith("from "):
                insert_idx = i
                break

        # Insert at the beginning of imports
        lines.insert(insert_idx, "import typing as t\n")
        if insert_idx < len(lines) - 1 and not lines[insert_idx + 1].strip():
            # Don't add extra blank line if one already exists
            pass
        else:
            lines.insert(insert_idx + 1, "\n")

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"✅ Added typing import to {file_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to fix {file_path}: {e}")
        return False


def main() -> None:
    print("🔍 Finding files that need 'import typing as t'...")

    files = get_files_needing_typing_import()
    print(f"Found {len(files)} files with 't' import errors")

    fixed_count = 0
    for file_path in files:
        if file_needs_typing_import(file_path):
            if add_typing_import(file_path):
                fixed_count += 1

    print(f"\n✅ Fixed {fixed_count} files")
    print("🔍 Verifying fixes...")

    # Run mypy again to check
    files_after = get_files_needing_typing_import()
    remaining = len(files_after)

    print(f"📊 Results: {len(files) - remaining} errors fixed, {remaining} remaining")

    return 0 if remaining < len(files) else 1


if __name__ == "__main__":
    exit(main())
