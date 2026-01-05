#!/usr/bin/env python3

import logging
import sys
from pathlib import Path

from crackerjack.services.regex_patterns import SAFE_PATTERNS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).parent.parent
CRACKERJACK_DIR = PROJECT_ROOT / "crackerjack"


def update_import_statements(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        if "resource_manager" in content:
            return False

        patterns_to_add = _determine_import_patterns(content)
        if not patterns_to_add:
            return False

        new_content = _add_imports_to_content(content, patterns_to_add)

        if new_content != original_content:
            file_path.write_text(new_content, encoding="utf-8")
            logger.info(f"Updated imports in {file_path}")
            return True

    except Exception as e:
        logger.error(f"Error updating imports in {file_path}: {e}")

    return False


def _determine_import_patterns(content: str) -> list[str]:
    patterns_to_add = []

    if SAFE_PATTERNS["detect_tempfile_usage"].test(content):
        patterns_to_add.append(
            "from crackerjack.core.resource_manager import ResourceContext, with_temp_file, with_temp_dir"
        )

    if SAFE_PATTERNS["detect_subprocess_usage"].test(content):
        patterns_to_add.append(
            "from crackerjack.core.resource_manager import ResourceContext"
        )

    if SAFE_PATTERNS["detect_asyncio_create_task"].test(content):
        patterns_to_add.append(
            "from crackerjack.core.resource_manager import ResourceContext"
        )

    if SAFE_PATTERNS["detect_file_open_operations"].test(content):
        patterns_to_add.append(
            "from crackerjack.core.file_lifecycle import SafeFileOperations, atomic_file_write"
        )

    return patterns_to_add


def _add_imports_to_content(content: str, patterns_to_add: list[str]) -> str:
    import_lines, other_lines = _separate_import_and_other_lines(content)

    for pattern in patterns_to_add:
        if pattern not in "\n".join(import_lines):
            import_lines.append(pattern)

    return "\n".join(import_lines + [""] + other_lines)


def _separate_import_and_other_lines(content: str) -> tuple[list[str], list[str]]:
    import_lines = []
    other_lines = []
    in_imports = True

    for line in content.split("\n"):
        if in_imports and (line.startswith(("import ", "from ")) or line.strip() == ""):
            import_lines.append(line)
        elif line.strip() and not line.startswith("#"):
            in_imports = False
            other_lines.append(line)
        else:
            if in_imports:
                import_lines.append(line)
            else:
                other_lines.append(line)

    return import_lines, other_lines


def add_resource_context_to_async_functions(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        functions_to_update = _find_functions_that_create_resources(content)
        if not functions_to_update:
            return False

        new_content = _update_functions_with_resource_context(
            content, functions_to_update
        )

        if new_content != original_content:
            file_path.write_text(new_content, encoding="utf-8")
            logger.info(f"Added resource contexts to {file_path}")
            return True

    except Exception as e:
        logger.error(f"Error adding resource contexts to {file_path}: {e}")

    return False


def _find_functions_that_create_resources(content: str) -> list[tuple[str, int, int]]:
    functions_to_update = []
    lines = content.split("\n")

    current_function = None
    function_start = 0

    for i, line in enumerate(lines):
        if SAFE_PATTERNS["match_async_function_definition"].test(line.strip()):
            current_function = SAFE_PATTERNS["match_async_function_definition"].apply(
                line.strip()
            )
            function_start = i
        elif current_function and (
            "subprocess.Popen" in line
            or "tempfile." in line
            or "asyncio.create_task" in line
        ):
            functions_to_update.append((current_function, function_start, i))
            current_function = None

    return functions_to_update


def _update_functions_with_resource_context(
    content: str, functions_to_update: list[tuple[str, int, int]]
) -> str:
    lines = content.split("\n")
    new_lines = lines.copy()
    offset = 0

    for func_def, start_idx, resource_line_idx in functions_to_update:
        body_start = start_idx + offset + 1

        if any(
            "ResourceContext" in line for line in new_lines[body_start : body_start + 5]
        ):
            continue

        new_lines, offset = _insert_resource_context(
            new_lines, offset, start_idx, body_start
        )

    return "\n".join(new_lines)


def _insert_resource_context(
    new_lines: list[str], offset: int, start_idx: int, body_start: int
) -> tuple[list[str], int]:
    func_line = new_lines[start_idx + offset]
    indentation = len(func_line) - len(func_line.lstrip())
    body_indent = " " * (indentation + 4)

    context_lines = [
        body_indent + "# Use resource context for proper cleanup",
        body_indent + "async with ResourceContext() as resource_ctx:",
    ]

    new_lines[body_start: body_start] = context_lines
    offset += len(context_lines)

    func_end = len(new_lines)
    for j in range(body_start + len(context_lines), func_end):
        line = new_lines[j]
        if line.strip() and not line.startswith(body_indent[:-4]):
            if line.startswith(" " * indentation) and line.strip():
                new_lines[j] = body_indent + line[indentation:]
            elif line.strip() and not line.startswith(" "):
                break

    return new_lines, offset


def update_subprocess_calls(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")

        updated = False

        new_content = SAFE_PATTERNS["replace_subprocess_popen_basic"].apply(content)
        if new_content != content:
            content = new_content
            updated = True

        new_content = SAFE_PATTERNS["replace_subprocess_popen_assignment"].apply(
            content
        )
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
    try:
        content = file_path.read_text(encoding="utf-8")

        updated = False

        new_content = SAFE_PATTERNS["replace_path_open_write"].apply(content)
        if new_content != content:
            content = new_content
            updated = True

        new_content = SAFE_PATTERNS["replace_path_write_text"].apply(content)
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
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        lines = content.split("\n")
        new_lines = lines.copy()
        offset = 0

        for i, line in enumerate(lines):
            if SAFE_PATTERNS["match_class_definition"].test(line.strip()):
                class_name = SAFE_PATTERNS["match_class_definition"].apply(line.strip())

                new_lines, offset = _process_class_for_cleanup(
                    lines, new_lines, offset, i, class_name, file_path
                )

        new_content = "\n".join(new_lines)

        if new_content != original_content:
            file_path.write_text(new_content, encoding="utf-8")
            return True

    except Exception as e:
        logger.error(f"Error adding cleanup handlers to {file_path}: {e}")

    return False


def _process_class_for_cleanup(
    lines: list[str],
    new_lines: list[str],
    offset: int,
    i: int,
    class_name: str,
    file_path: Path,
) -> tuple[list[str], int]:
    class_body_start = i + 1
    class_body_end = _find_class_end(lines, class_body_start)

    class_body = lines[class_body_start: class_body_end]

    if any("cleanup" in line for line in class_body):
        return new_lines, offset

    if any(
        "subprocess" in line or "tempfile" in line or "asyncio" in line
        for line in class_body
    ):
        new_lines, new_offset = _add_cleanup_methods_to_class(
            new_lines, offset, class_body_end, class_name, file_path
        )
        return new_lines, new_offset

    return new_lines, offset


def _find_class_end(lines: list[str], start_idx: int) -> int:
    class_body_end = len(lines)

    for j in range(start_idx, len(lines)):
        if lines[j].strip() and not lines[j].startswith(" "):
            class_body_end = j
            break

    return class_body_end


def _add_cleanup_methods_to_class(
    new_lines: list[str],
    offset: int,
    class_body_end: int,
    class_name: str,
    file_path: Path,
) -> tuple[list[str], int]:
    indentation = " "

    cleanup_methods = [
        "",
        indentation + "async def cleanup(self) -> None:",
        indentation + ' """Clean up resources used by this class."""',
        indentation + " # TODO: Implement cleanup for class resources",
        indentation + " pass",
        "",
        indentation + "async def __aenter__(self):",
        indentation + " return self",
        "",
        indentation + "async def __aexit__(self, exc_type, exc_val, exc_tb):",
        indentation + " await self.cleanup()",
    ]

    insert_pos = class_body_end + offset
    new_lines[insert_pos: insert_pos] = cleanup_methods
    offset += len(cleanup_methods)

    logger.info(f"Added cleanup methods to class {class_name} in {file_path}")

    return new_lines, offset


def process_file(file_path: Path) -> int:
    updates_made = 0

    logger.info(f"Processing {file_path}")

    if any(name in str(file_path) for name in ("resource_manager", "file_lifecycle")):
        logger.info(f"Skipping resource management module {file_path}")
        return 0

    try:
        if update_import_statements(file_path):
            updates_made += 1

        if add_resource_context_to_async_functions(file_path):
            updates_made += 1

        if update_subprocess_calls(file_path):
            updates_made += 1

        if update_file_operations(file_path):
            updates_made += 1

        if add_cleanup_handlers(file_path):
            updates_made += 1

    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")

    return updates_made


def main():
    logger.info("Starting resource management integration")

    python_files = list(CRACKERJACK_DIR.glob("**/*.py"))

    python_files = [
        f for f in python_files if "__pycache__" not in str(f) and ".pyc" not in str(f)
    ]

    logger.info(f"Found {len(python_files)} Python files to process")

    total_updates = 0
    files_updated = 0

    priority_patterns = [
        "**/mcp/**/*.py",
        "**/core/**/*.py",
        "**/executors/**/*.py",
        "**/managers/**/*.py",
    ]

    priority_files: list[Path] = []
    for pattern in priority_patterns:
        priority_files.extend(CRACKERJACK_DIR.glob(pattern))

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
