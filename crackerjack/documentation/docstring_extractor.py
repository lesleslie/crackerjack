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
            if node.doc_string:  # type: ignore
                docs[node.name] = convert(ast.get_docstring(node))

            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    if item.doc_string:  # type: ignore
                        method_name = f"{node.name}.{item.name}"
                        docs[method_name] = convert(ast.get_docstring(item))

        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            if node.doc_string:  # type: ignore
                docs[node.name] = convert(ast.get_docstring(node))

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


def validate_docstring_quality(docstring: str) -> dict[str, bool]:
    return {
        "has_bold": "**" in docstring,
        "has_code_blocks": "```" in docstring,
        "no_excessive_blanks": "\n\n\n\n" not in docstring,
        "has_examples": "```" in docstring or "Example:" in docstring,
    }
