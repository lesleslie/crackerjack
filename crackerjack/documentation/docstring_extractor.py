import ast
import inspect
from pathlib import Path

from docstring_to_markdown import convert


def extract_function_markdown(func: callable) -> str:  # type: ignore
    docstring = inspect.getdoc(func)
    if not docstring:
        return "**No documentation available**"

    return convert(docstring)


def extract_class_markdown(cls: type) -> dict[str, str]:
    docs = {}
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if not name.startswith("_"):
            docs[name] = extract_function_markdown(method)
    return docs


def extract_module_markdown(module_path: Path) -> dict[str, str]:
    source = module_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"error": f"Syntax error in {module_path}: {e}"}

    docs = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_docstring = ast.get_docstring(node)
            if class_docstring is not None:
                docs[node.name] = convert(class_docstring)

            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    method_docstring = ast.get_docstring(item)
                    if method_docstring is not None:
                        method_name = f"{node.name}.{item.name}"
                        docs[method_name] = convert(method_docstring)

        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            func_docstring = ast.get_docstring(node)
            if func_docstring is not None:
                docs[node.name] = convert(func_docstring)

    return docs


def extract_for_zensical(
    file_path: Path,
    symbol_name: str | None = None,
) -> str:
    module_docs = extract_module_markdown(file_path)

    if symbol_name and symbol_name in module_docs:
        return module_docs[symbol_name]

    if symbol_name is None:
        return "\n\n".join(f"## {name}\n\n{doc}" for name, doc in module_docs.items())

    return f"# {symbol_name}\n\nNo documentation found for this symbol."


def validate_docstring_quality(docstring: str) -> dict[str, list[str]]:
    """Return markdown rendering quality violations for a docstring.

    The CLI consumer (`cli.handlers.docs_commands.validate_docs`) reads
    ``result["violations"]`` to flag docstrings. Returning boolean keys
    (``has_bold``, ``has_code_blocks``...) would never feed the CLI,
    so the function returns a list of human-readable violation strings
    instead. Empty list = no issues.

    Checks performed:
        - Has at least one bold marker (``**...**``) for emphasis.
        - Has at least one fenced code block (`` ``` ``) or inline example marker.
        - No four-or-more consecutive blank lines (markdown rendering glitch).
        - Has either a code block or an explicit ``Example:`` header.
    """
    violations: list[str] = []

    if "**" not in docstring:
        violations.append("Missing bold marker (**)")

    has_code_blocks = "```" in docstring
    if not has_code_blocks:
        violations.append("Missing fenced code block (```)")

    if "\n\n\n\n" in docstring:
        violations.append("Excessive blank lines (4+ consecutive)")

    if not (has_code_blocks or "Example:" in docstring):
        violations.append("Missing example section (need ``` or 'Example:')")

    return {"violations": violations}
