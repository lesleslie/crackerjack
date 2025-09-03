#!/usr/bin/env python3
"""Script to integrate comprehensive resource management into existing crackerjack components.

This script updates existing files to use the new resource management patterns
for better error handling and resource leak prevention.
"""

import logging
import re
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent
CRACKERJACK_DIR = PROJECT_ROOT / "crackerjack"


def update_import_statements(file_path: Path) -> bool:
    """Update import statements to include resource management modules."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Skip if already has resource management imports
        if "resource_manager" in content or "websocket_lifecycle" in content:
            return False

        # Add resource management imports for specific patterns
        patterns_to_add = []

        # For files using temporary files/directories
        if re.search(
            r"tempfile\.(mkdtemp|NamedTemporaryFile|TemporaryDirectory)", content
        ):
            patterns_to_add.append(
                "from crackerjack.core.resource_manager import ResourceContext, with_temp_file, with_temp_dir"
            )

        # For files using subprocess
        if re.search(r"subprocess\.(Popen|run)", content):
            patterns_to_add.append(
                "from crackerjack.core.websocket_lifecycle import NetworkResourceManager, with_managed_subprocess"
            )

        # For files using asyncio tasks
        if re.search(r"asyncio\.create_task", content):
            patterns_to_add.append(
                "from crackerjack.core.resource_manager import ResourceContext"
            )

        # For files doing file operations
        if re.search(r"\.open\(|with open\(", content):
            patterns_to_add.append(
                "from crackerjack.core.file_lifecycle import SafeFileOperations, atomic_file_write"
            )

        if not patterns_to_add:
            return False

        # Find the last import statement
        import_lines = []
        other_lines = []
        in_imports = True

        for line in content.split("\n"):
            if in_imports and (
                line.startswith("import ")
                or line.startswith("from ")
                or line.strip() == ""
            ):
                import_lines.append(line)
            elif line.strip() and not line.startswith("#"):
                in_imports = False
                other_lines.append(line)
            else:
                if in_imports:
                    import_lines.append(line)
                else:
                    other_lines.append(line)

        # Add new imports
        for pattern in patterns_to_add:
            if pattern not in "\n".join(import_lines):
                import_lines.append(pattern)

        # Reconstruct content
        new_content = "\n".join(import_lines + [""] + other_lines)

        if new_content != original_content:
            file_path.write_text(new_content, encoding="utf-8")
            logger.info(f"Updated imports in {file_path}")
            return True

    except Exception as e:
        logger.error(f"Error updating imports in {file_path}: {e}")

    return False


def add_resource_context_to_async_functions(file_path: Path) -> bool:
    """Add ResourceContext to async functions that create resources."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Pattern for async functions that might benefit from resource context
        async_func_pattern = r"(async def \w+\([^)]*\)[^:]*:)"

        # Look for functions that create subprocess or temporary files
        functions_to_update = []
        lines = content.split("\n")

        current_function = None
        function_start = 0

        for i, line in enumerate(lines):
            # Check if this is an async function definition
            match = re.match(async_func_pattern, line.strip())
            if match:
                current_function = match.group(1)
                function_start = i
            elif current_function and (
                "subprocess.Popen" in line
                or "tempfile." in line
                or "asyncio.create_task" in line
            ):
                # This function creates resources - mark for update
                functions_to_update.append((current_function, function_start, i))
                current_function = None  # Only mark once per function

        if not functions_to_update:
            return False

        # Update functions to use resource context
        new_lines = lines[:]
        offset = 0

        for func_def, start_idx, resource_line_idx in functions_to_update:
            # Find the function body start
            body_start = start_idx + offset + 1

            # Skip if already has resource context
            if any(
                "ResourceContext" in line
                for line in new_lines[body_start : body_start + 5]
            ):
                continue

            # Find indentation level
            func_line = new_lines[start_idx + offset]
            indentation = len(func_line) - len(func_line.lstrip())
            body_indent = " " * (indentation + 4)

            # Insert resource context
            context_lines = [
                body_indent + "# Use resource context for proper cleanup",
                body_indent + "async with ResourceContext() as resource_ctx:",
            ]

            # Insert after function definition
            new_lines[body_start:body_start] = context_lines
            offset += len(context_lines)

            # Update indentation of existing function body
            func_end = len(new_lines)
            for j in range(body_start + len(context_lines), func_end):
                line = new_lines[j]
                if line.strip() and not line.startswith(
                    body_indent[:-4]
                ):  # Not another function
                    if line.startswith(" " * indentation) and line.strip():
                        new_lines[j] = body_indent + line[indentation:]
                    elif line.strip() and not line.startswith(" "):
                        break  # End of function

        new_content = "\n".join(new_lines)

        if new_content != original_content:
            file_path.write_text(new_content, encoding="utf-8")
            logger.info(f"Added resource contexts to {file_path}")
            return True

    except Exception as e:
        logger.error(f"Error adding resource contexts to {file_path}: {e}")

    return False


def update_subprocess_calls(file_path: Path) -> bool:
    """Update subprocess calls to use managed processes."""
    try:
        content = file_path.read_text(encoding="utf-8")

        # Replace subprocess.Popen with managed version
        patterns = [
            # Basic Popen calls
            (
                r"subprocess\.Popen\(",
                "managed_proc = resource_ctx.managed_process(subprocess.Popen(",
            ),
            # Popen with variable assignment
            (r"(\w+)\s*=\s*subprocess\.Popen\(", r"process = subprocess.Popen("),
        ]

        updated = False
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                updated = True

        if updated:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Updated subprocess calls in {file_path}")
            return True

    except Exception as e:
        logger.error(f"Error updating subprocess calls in {file_path}: {e}")

    return False


def update_file_operations(file_path: Path) -> bool:
    """Update file operations to use safe patterns."""
    try:
        content = file_path.read_text(encoding="utf-8")

        # Replace risky file operations
        patterns = [
            # Replace simple open() with context manager
            (r'(\w+)\.open\(["\']w["\'][^)]*\)', r"atomic_file_write(\1)"),
            # Replace path.write_text with safe version
            (
                r"(\w+)\.write_text\(([^)]+)\)",
                r"await SafeFileOperations.safe_write_text(\1, \2, atomic=True)",
            ),
        ]

        updated = False
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                updated = True

        if updated:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Updated file operations in {file_path}")
            return True

    except Exception as e:
        logger.error(f"Error updating file operations in {file_path}: {e}")

    return False


def add_cleanup_handlers(file_path: Path) -> bool:
    """Add cleanup handlers to classes and functions."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Look for classes that might need cleanup
        class_pattern = r"class (\w+).*:"

        lines = content.split("\n")
        new_lines = lines[:]
        offset = 0

        for i, line in enumerate(lines):
            match = re.match(class_pattern, line.strip())
            if match:
                class_name = match.group(1)

                # Skip if already has cleanup methods
                class_body_start = i + 1
                class_body_end = len(lines)

                # Find end of class
                for j in range(class_body_start, len(lines)):
                    if lines[j].strip() and not lines[j].startswith("    "):
                        class_body_end = j
                        break

                class_body = lines[class_body_start:class_body_end]

                if any("cleanup" in line for line in class_body):
                    continue  # Already has cleanup

                if any(
                    "subprocess" in line or "tempfile" in line or "asyncio" in line
                    for line in class_body
                ):
                    # This class needs cleanup methods
                    indentation = "    "

                    cleanup_methods = [
                        "",
                        indentation + "async def cleanup(self) -> None:",
                        indentation
                        + '    """Clean up resources used by this class."""',
                        indentation
                        + "    # TODO: Implement cleanup for class resources",
                        indentation + "    pass",
                        "",
                        indentation + "async def __aenter__(self):",
                        indentation + "    return self",
                        "",
                        indentation
                        + "async def __aexit__(self, exc_type, exc_val, exc_tb):",
                        indentation + "    await self.cleanup()",
                    ]

                    # Insert cleanup methods at end of class
                    insert_pos = class_body_end + offset
                    new_lines[insert_pos:insert_pos] = cleanup_methods
                    offset += len(cleanup_methods)

                    logger.info(
                        f"Added cleanup methods to class {class_name} in {file_path}"
                    )

        new_content = "\n".join(new_lines)

        if new_content != original_content:
            file_path.write_text(new_content, encoding="utf-8")
            return True

    except Exception as e:
        logger.error(f"Error adding cleanup handlers to {file_path}: {e}")

    return False


def process_file(file_path: Path) -> int:
    """Process a single Python file to add resource management."""
    updates_made = 0

    logger.info(f"Processing {file_path}")

    # Skip files that are already resource management modules
    if any(
        name in str(file_path)
        for name in ["resource_manager", "websocket_lifecycle", "file_lifecycle"]
    ):
        logger.info(f"Skipping resource management module {file_path}")
        return 0

    try:
        # Update imports
        if update_import_statements(file_path):
            updates_made += 1

        # Add resource contexts to async functions
        if add_resource_context_to_async_functions(file_path):
            updates_made += 1

        # Update subprocess calls
        if update_subprocess_calls(file_path):
            updates_made += 1

        # Update file operations
        if update_file_operations(file_path):
            updates_made += 1

        # Add cleanup handlers
        if add_cleanup_handlers(file_path):
            updates_made += 1

    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")

    return updates_made


def main():
    """Main function to process all Python files in crackerjack."""
    logger.info("Starting resource management integration")

    # Find all Python files
    python_files = list(CRACKERJACK_DIR.glob("**/*.py"))

    # Filter out __pycache__ and other unwanted directories
    python_files = [
        f for f in python_files if "__pycache__" not in str(f) and ".pyc" not in str(f)
    ]

    logger.info(f"Found {len(python_files)} Python files to process")

    total_updates = 0
    files_updated = 0

    # Priority files to update first (core components)
    priority_patterns = [
        "**/mcp/**/*.py",
        "**/core/**/*.py",
        "**/executors/**/*.py",
        "**/managers/**/*.py",
    ]

    priority_files = []
    for pattern in priority_patterns:
        priority_files.extend(CRACKERJACK_DIR.glob(pattern))

    # Remove duplicates and ensure priority files are processed first
    priority_files = list(set(priority_files))
    remaining_files = [f for f in python_files if f not in priority_files]

    all_files = priority_files + remaining_files

    for file_path in all_files:
        updates = process_file(file_path)
        total_updates += updates
        if updates > 0:
            files_updated += 1

    logger.info("Integration complete!")
    logger.info(f"Files updated: {files_updated}")
    logger.info(f"Total updates made: {total_updates}")

    if files_updated > 0:
        logger.info("Recommendations:")
        logger.info("1. Run tests to ensure functionality is preserved")
        logger.info("2. Review the TODO comments added for manual implementation")
        logger.info("3. Test resource cleanup in error scenarios")
        logger.info("4. Update existing exception handlers to include cleanup")

    return 0


if __name__ == "__main__":
    sys.exit(main())
