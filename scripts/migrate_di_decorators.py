"""Remove @depends.inject decorators and Inject[Type] parameters.

This script handles the mechanical removal of ACB DI decorators and type hints.
Complex cases requiring direct instantiation may need manual review.
"""

import re
from pathlib import Path


def remove_di_decorator(content: str) -> tuple[str, bool]:
    """Remove @depends.inject decorators.

    Returns:
        (modified_content, changed)
    """
    original = content

    # Remove @depends.inject decorators (with optional # type: ignore comment)
    content = re.sub(
        r"^\s*@depends\.inject(?:\s*#[^\n]*)?\s*$\n",
        "",
        content,
        flags=re.MULTILINE
    )

    return content, content != original


def remove_inject_parameters(content: str) -> tuple[str, bool]:
    """Remove Inject[Type] parameters from function signatures.

    Handles patterns like:
    - console: Inject[Console] = None
    - logger: Inject[LoggerProtocol]
    - service: Inject[SomeProtocol] = None

    Returns:
        (modified_content, changed)
    """
    original = content

    # Pattern 1: parameter_name: Inject[Type] = default (with default value)
    # Remove middle parameter with default
    content = re.sub(
        r",\s*\w+:\s*Inject\[[^\]]+\](?:\s*=\s*[^,\)]+)?",
        "",
        content
    )

    # Remove first parameter with default
    content = re.sub(
        r"\(\s*\w+:\s*Inject\[[^\]]+\](?:\s*=\s*[^,\)]+)?\s*,",
        "(",
        content
    )

    # Remove last parameter with default
    content = re.sub(
        r",\s*\w+:\s*Inject\[[^\]]+\](?:\s*=\s*[^,\)]+)?\s*\)",
        ")",
        content
    )

    # Remove only parameter (no comma)
    content = re.sub(
        r"\(\s*\w+:\s*Inject\[[^\]]+\](?:\s*=\s*[^,\)]+)?\s*\)",
        "()",
        content
    )

    return content, content != original


def remove_depends_imports(content: str) -> tuple[str, bool]:
    """Remove ACB depends imports that are no longer needed.

    Only removes if there are no remaining uses of depends/Inject in the file.

    Returns:
        (modified_content, changed)
    """
    original = content

    # Check if depends or Inject are still used (excluding imports)
    lines_without_imports = [
        line for line in content.split("\n")
        if not line.strip().startswith(("import ", "from "))
    ]
    remaining_content = "\n".join(lines_without_imports)

    has_depends_usage = (
        "depends." in remaining_content or
        "Inject[" in remaining_content or
        "@depends" in remaining_content
    )

    if not has_depends_usage:
        # Safe to remove depends imports
        content = re.sub(r"from acb\.depends import.*\n", "", content)
        content = re.sub(r"import acb\.depends.*\n", "", content)

    return content, content != original


def migrate_file(file_path: Path) -> tuple[bool, list[str]]:
    """Migrate single file to remove DI decorators and parameters.

    Returns:
        (changed, changes_made): Whether file changed and list of changes
    """
    content = file_path.read_text()
    original = content
    changes = []

    # Step 1: Remove @depends.inject decorators
    content, changed = remove_di_decorator(content)
    if changed:
        changes.append("Removed @depends.inject decorators")

    # Step 2: Remove Inject[Type] parameters
    content, changed = remove_inject_parameters(content)
    if changed:
        changes.append("Removed Inject[Type] parameters")

    # Step 3: Remove depends imports if no longer used
    content, changed = remove_depends_imports(content)
    if changed:
        changes.append("Removed unused ACB depends imports")

    # Write back if changed
    if content != original:
        file_path.write_text(content)
        return True, changes
    return False, []


def main() -> None:
    """Run DI decorator migration across all Python files."""
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
    print(f"DI Decorator Migration Complete!")
    print(f"Files migrated: {len(changed_files)}")
    print(f"Total changes: {len(total_changes)}")
    print(f"{'='*60}")

    # Show summary
    change_types = {}
    for change in total_changes:
        change_type = change.split()[0]
        change_types[change_type] = change_types.get(change_type, 0) + 1

    print("\nChange type summary:")
    for change_type, count in sorted(change_types.items()):
        print(f"  {change_type}: {count}")


if __name__ == "__main__":
    main()
