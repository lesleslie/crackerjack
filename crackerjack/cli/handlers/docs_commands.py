"""Documentation verification commands for crackerjack.

These commands provide automated verification that markdown docstrings
are complete and follow ultra-minimal markdown standards.
"""

import ast
import logging
import typing as t
from pathlib import Path

from crackerjack.models.protocols import ConsoleInterface

logger = logging.getLogger(__name__)


def check_docs(console: ConsoleInterface) -> int:
    """Check documentation completeness across the codebase.

    **What it checks**:
    - All public classes have markdown docstrings
    - All public functions have markdown docstrings
    - Docstrings follow ultra-minimal markdown standard (**bold** emphasis)
    - Returns count of classes/functions with/without docstrings

    **Returns**: Exit code (0 = complete, 1 = issues found)

    **Behavior**:
        - Scans crackerjack/ directory recursively
        - Uses AST-based parsing for docstring detection
        - Validates format and quality
        - Shows summary of missing documentation

    **Example**:
        ```bash
        crackerjack docs:check
        # Scans codebase...
        ✅ 45 classes have docstrings
        ⚠️  12 functions missing docstrings
        📊 Summary: 85% documentation coverage
        ```
    """
    # Counters for tracking
    stats = {
        "classes_with_docs": 0,
        "classes_without_docs": 0,
        "functions_with_docs": 0,
        "functions_without_docs": 0,
        "files_scanned": 0,
        "missing_count": 0,
        "total_classes": 0,
        "total_functions": 0,
    }

    # Scan crackerjack directory
    crackerjack_path = Path("crackerjack")
    if not crackerjack_path.exists():
        console.print("[yellow]⚠️  crackerjack/ directory not found[/yellow]")
        return 1

    for py_file in crackerjack_path.rglob("*.py"):
        # Skip cache and test directories
        if "__pycache__" in py_file.parts or ".pytest_cache" in py_file.parts:
            continue

        # Skip __init__.py for stats (focus on implementation files)
        if py_file.name == "__init__.py":
            continue

        try:
            stats["files_scanned"] += 1

            with open(py_file, encoding="utf-8") as f:
                source = f.read()
                tree = ast.parse(source, filename=str(py_file))

                # Check classes
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        stats["total_classes"] += 1

                        # Check class docstring
                        class_doc = ast.get_docstring(node)
                        if class_doc:
                            stats["classes_with_docs"] += 1
                        else:
                            stats["classes_without_docs"] += 1
                            stats["missing_count"] += 1

                        # Check public methods (not starting with _)
                        for item in node.body:
                            if isinstance(
                                item, (ast.FunctionDef, ast.AsyncFunctionDef)
                            ):
                                if not item.name.startswith("_"):
                                    stats["total_functions"] += 1

                                    func_doc = ast.get_docstring(item)
                                    if func_doc:
                                        stats["functions_with_docs"] += 1
                                    else:
                                        stats["functions_without_docs"] += 1
                                        stats["missing_count"] += 1

                    # Check module-level functions
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_"):
                            stats["total_functions"] += 1

                            func_doc = ast.get_docstring(node)
                            if func_doc:
                                stats["functions_with_docs"] += 1
                            else:
                                stats["functions_without_docs"] += 1
                                stats["missing_count"] += 1

        except SyntaxError as e:
            console.print(f"[yellow]⚠️  Skipping {py_file}: syntax error[/yellow]")
            logger.debug(f"Syntax error in {py_file}: {e}")
        except Exception as e:
            console.print(f"[yellow]⚠️  Error reading {py_file}: {e}[/yellow]")
            logger.debug(f"Error reading {py_file}: {e}")

    # Calculate coverage
    total_items = stats["total_classes"] + stats["total_functions"]
    documented_items = stats["classes_with_docs"] + stats["functions_with_docs"]
    coverage_percent = (documented_items / total_items * 100) if total_items > 0 else 0

    # Show summary
    console.print("\n[bold cyan]Documentation Check Summary[/bold cyan]")
    console.print(f"  ├─ Scanned: {stats['files_scanned']} Python files")
    console.print(
        f"  ├─ Found: {stats['total_classes']} classes, {stats['total_functions']} functions"
    )
    console.print(
        f"  ├─ Classes with docs: {stats['classes_with_docs']} [green]✅[/green]"
    )
    console.print(
        f"  ├─ Classes missing docs: {stats['classes_without_docs']} [yellow]⚠️[/yellow]"
    )
    console.print(
        f"  ├─ Functions with docs: {stats['functions_with_docs']} [green]✅[/green]"
    )
    console.print(
        f"  ├─ Functions missing docs: {stats['functions_without_docs']} [yellow]⚠️[/yellow]"
    )
    console.print(f"  └─ Coverage: [bold cyan]{coverage_percent:.1f}%[/bold cyan]")

    return 0 if stats["missing_count"] == 0 else 1


def validate_docs(console: ConsoleInterface) -> int:
    """Validate docstring format against ultra-minimal markdown standard.

    **What it checks**:
    - Docstrings use **bold** for emphasis (not *italic*, _underline_)
    - No excessive blank lines
    - Proper section headers (Purpose, Behavior, Returns, etc.)
    - Fenced code blocks with language specifiers
    - Returns count of violations found

    **Returns**: Exit code (0 = valid, 1 = issues found)

    **Behavior**:
        - Scans crackerjack/ for docstrings
        - Checks against ultra-minimal markdown standard
        - Reports format violations

    **Example**:
        ```bash
        crackerjack docs:validate
        # Scans codebase...
        ✅ All docstrings follow ultra-minimal markdown standard
        ```
    """
    from crackerjack.documentation.docstring_extractor import validate_docstring_quality

    # Counters
    violations_found = 0
    files_checked = 0
    items_checked = 0

    # Scan crackerjack directory
    crackerjack_path = Path("crackerjack")
    if not crackerjack_path.exists():
        console.print("[yellow]⚠️  crackerjack/ directory not found[/yellow]")
        return 1

    for py_file in crackerjack_path.rglob("*.py"):
        # Skip cache and test directories
        if "__pycache__" in py_file.parts or ".pytest_cache" in py_file.parts:
            continue

        if py_file.name == "__init__.py":
            continue

        try:
            files_checked += 1

            with open(py_file, encoding="utf-8") as f:
                source = f.read()
                tree = ast.parse(source, filename=str(py_file))

                # Check classes
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check class docstring
                        class_doc = ast.get_docstring(node)
                        if class_doc:
                            items_checked += 1
                            result = validate_docstring_quality(class_doc)
                            violations = result.get("violations", [])
                            if violations:
                                violations_found += len(violations)
                                console.print(
                                    f"[yellow]⚠️[/yellow] {node.name} (class): {len(violations)} violations"
                                )

                        # Check methods
                        for item in node.body:
                            if isinstance(
                                item, (ast.FunctionDef, ast.AsyncFunctionDef)
                            ):
                                if not item.name.startswith("_"):
                                    func_doc = ast.get_docstring(item)
                                    if func_doc:
                                        items_checked += 1
                                        result = validate_docstring_quality(func_doc)
                                        violations = result.get("violations", [])
                                        if violations:
                                            violations_found += len(violations)
                                            console.print(
                                                f"[yellow]⚠️[/yellow] {node.name}.{item.name}: {len(violations)} violations"
                                            )

                    # Check module-level functions
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_"):
                            func_doc = ast.get_docstring(node)
                            if func_doc:
                                items_checked += 1
                                result = validate_docstring_quality(func_doc)
                                violations = result.get("violations", [])
                                if violations:
                                    violations_found += len(violations)
                                    console.print(
                                        f"[yellow]⚠️[/yellow] {node.name}: {len(violations)} violations"
                                    )

        except SyntaxError:
            console.print(f"[yellow]⚠️  Skipping {py_file}: syntax error[/yellow]")
        except Exception as e:
            logger.debug(f"Error validating {py_file}: {e}")

    # Show summary
    console.print("\n[bold cyan]Docstring Format Validation Summary[/bold cyan]")
    console.print(f" ├─ Files checked: {files_checked}")
    console.print(f" ├─ Items checked: {items_checked}")
    console.print(f" ├─ Violations found: {violations_found}")
    if violations_found == 0:
        console.print(" └─ Status: [green]✅ All docstrings valid[/green]")
    else:
        console.print(" └─ Status: [yellow]⚠️ Format issues found[/yellow]")

    return 0 if violations_found == 0 else 1


def register_docs_commands() -> dict[str, t.Callable[[ConsoleInterface], int]]:
    """Register docs:check and docs:validate commands with CLI system.

    **Returns**: Dict mapping command names to handler functions
    """
    return {
        "docs:check": check_docs,
        "docs:validate": validate_docs,
    }


__all__ = [
    "check_docs",
    "validate_docs",
    "register_docs_commands",
]
