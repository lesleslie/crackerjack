"""Automated ACB import migration script for Phase 2.

Replaces:
- from acb.logger import Logger → import logging + logger = logging.getLogger(__name__)
- from acb.console import Console → from rich.console import Console
- depends.get_sync(Logger) → logger (module-level)
- depends.get_sync(Console) → Console() (direct instantiation)
- Remove @depends.inject decorators and Inject[Type] parameters
"""

import re
from pathlib import Path


def migrate_file(file_path: Path) -> tuple[bool, list[str]]:
    """Migrate single file from ACB to standard patterns.

    Returns:
        (changed, changes_made): Whether file changed and list of changes
    """
    content = file_path.read_text()
    original = content
    changes = []

    # 1. Replace ACB logger imports with standard logging
    if "from acb.logger import Logger" in content:
        content = re.sub(r"from acb\.logger import Logger.*\n", "", content)
        changes.append("Removed ACB logger import")

        # Add logging import if not present
        if "import logging" not in content:
            # Find first import line
            lines = content.split("\n")
            first_import_idx = next(
                (i for i, line in enumerate(lines) if line.startswith(("import ", "from "))),
                0
            )
            lines.insert(first_import_idx, "import logging")
            content = "\n".join(lines)
            changes.append("Added import logging")

    # 2. Replace ACB console with rich.console
    if "from acb.console import Console" in content:
        content = re.sub(
            r"from acb\.console import Console.*\n",
            "from rich.console import Console\n",
            content
        )
        changes.append("Replaced ACB Console with rich.console.Console")

    # Handle alternative console import pattern
    if "from acb import console as acb_console" in content:
        content = re.sub(r"from acb import console as acb_console.*\n", "", content)
        changes.append("Removed acb console alias import")

    if "from acb import console" in content and "# console imported from acb" not in content:
        content = re.sub(r"from acb import console.*\n", "", content)
        changes.append("Removed acb console import")

    # 3. Replace depends.get_sync(Logger) with module logger
    if "depends.get_sync(Logger)" in content:
        # Add module-level logger after imports if not present
        if "logger = logging.getLogger(__name__)" not in content:
            lines = content.split("\n")
            # Find end of imports section
            import_end = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith(("import ", "from ", "#", '"""', "'''")):
                    import_end = i
                    break

            # Insert module logger
            lines.insert(import_end, "\nlogger = logging.getLogger(__name__)\n")
            content = "\n".join(lines)
            changes.append("Added module-level logger")

        # Replace depends.get_sync(Logger) calls with logger reference
        content = re.sub(
            r"(\w+)\s*=\s*depends\.get_sync\(Logger\)",
            r"# \1 = logger  # Migrated from ACB",
            content
        )
        changes.append("Replaced depends.get_sync(Logger) with logger")

    # 4. Replace depends.get_sync(Console) with direct instantiation
    if "depends.get_sync(Console)" in content:
        content = re.sub(
            r"depends\.get_sync\(Console\)",
            "Console()",
            content
        )
        changes.append("Replaced depends.get_sync(Console) with Console()")

    # 5. Remove ACB depends imports that are no longer needed
    # (This will be handled in Task 3 when we remove @depends.inject decorators)

    # Write back if changed
    if content != original:
        file_path.write_text(content)
        return True, changes
    return False, []


def main() -> None:
    """Run migration across all Python files in crackerjack/."""
    changed_files = []
    total_changes = []

    for file in sorted(Path("crackerjack").rglob("*.py")):
        changed, changes = migrate_file(file)
        if changed:
            changed_files.append(file)
            total_changes.extend(changes)
            print(f"✓ Migrated: {file}")
            for change in changes:
                print(f"  - {change}")

    print(f"\n{'='*60}")
    print(f"Migration complete!")
    print(f"Files migrated: {len(changed_files)}")
    print(f"Total changes: {len(total_changes)}")
    print(f"{'='*60}")

    # Show summary of change types
    change_types = {}
    for change in total_changes:
        change_type = change.split()[0]  # First word
        change_types[change_type] = change_types.get(change_type, 0) + 1

    print("\nChange type summary:")
    for change_type, count in sorted(change_types.items()):
        print(f"  {change_type}: {count}")


if __name__ == "__main__":
    main()
