"""Extract and normalize docstrings to markdown for Zensical.

Provides helper functions for extracting docstrings from Python code
and converting them to clean markdown format suitable for AI understanding
and web documentation generation.
"""

import ast
import inspect
from pathlib import Path

from docstring_to_markdown import convert


def extract_function_markdown(func: callable) -> str:
    """Extract function docstring and convert to markdown.

    **Input**: Function or method callable
    **Returns**: Markdown-formatted documentation

    **Behavior**:
    - Extracts docstring via inspect.getdoc()
    - Converts to markdown via docstring-to-markdown
    - Returns placeholder if no docstring exists

    **Example**:
        ```python
        from crackerjack.documentation.docstring_extractor import extract_function_markdown

        doc_md = extract_function_markdown(my_function)
        print(doc_md)
        ```
    """
    docstring = inspect.getdoc(func)
    if not docstring:
        return "**No documentation available**"

    # Convert any format (reST, Google-style) to markdown
    return convert(docstring)


def extract_class_markdown(cls: type) -> dict[str, str]:
    """Extract all method docstrings from class.

    **Input**: Class type
    **Returns**: Dict mapping method names to markdown docs

    **Behavior**:
    - Extracts docstrings for all public methods (not starting with _)
    - Converts each to markdown format
    - Skips private methods

    **Example**:
        ```python
        from crackerjack.services.vector_store import VectorStore

        docs = extract_class_markdown(VectorStore)
        for method_name, doc_md in docs.items():
            print(f"{method_name}: {doc_md}")
        ```
    """
    docs = {}
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if not name.startswith("_"):
            docs[name] = extract_function_markdown(method)
    return docs


def extract_module_markdown(module_path: Path) -> dict[str, str]:
    """Extract all docstrings from a Python module.

    **Input**: Path to Python module file
    **Returns**: Dict mapping class/function names to markdown docs

    **Behavior**:
    - Parses module via AST (no import execution)
    - Extracts class and function definitions
    - Converts all docstrings to markdown

    **Example**:
        ```python
        from pathlib import Path
        from crackerjack.documentation.docstring_extractor import extract_module_markdown

        docs = extract_module_markdown(Path("crackerjack/services/vector_store.py"))
        for name, doc_md in docs.items():
            print(f"{name}: {doc_md}")
        ```
    """
    source = module_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"error": f"Syntax error in {module_path}: {e}"}

    docs = {}

    # Extract class docstrings
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.doc_string:
                docs[node.name] = convert(ast.get_docstring(node))

            # Extract method docstrings
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    if item.doc_string:
                        method_name = f"{node.name}.{item.name}"
                        docs[method_name] = convert(ast.get_docstring(item))

        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            if node.doc_string:
                docs[node.name] = convert(ast.get_docstring(node))

    return docs


def extract_for_zensical(
    file_path: Path,
    symbol_name: str | None = None,
) -> str:
    """Extract markdown docstring for Zensical documentation.

    **Input**: File path and optional symbol name
    **Returns**: Markdown-formatted documentation string

    **Purpose**: Format docstrings for Zensical/mkdocs-material consumption

    **Example**:
        ```python
        from crackerjack.documentation.docstring_extractor import extract_for_zensical

        doc_md = extract_for_zensical(
            Path("crackerjack/services/vector_store.py"),
            symbol_name="VectorStore",
        )
        print(doc_md)
        ```
    """
    module_docs = extract_module_markdown(file_path)

    if symbol_name and symbol_name in module_docs:
        return module_docs[symbol_name]

    # Return all docs if no specific symbol requested
    if symbol_name is None:
        return "\n\n".join(f"## {name}\n\n{doc}" for name, doc in module_docs.items())

    return f"# {symbol_name}\n\nNo documentation found for this symbol."


def validate_docstring_quality(docstring: str) -> dict[str, bool]:
    """Validate docstring meets ultra-minimal markdown standards.

    **Input**: Docstring to validate
    **Returns**: Dict with quality criteria results

    **Criteria**:
    - `has_bold`: Uses **bold** emphasis
    - `has_code_blocks`: Contains ```fenced code blocks
    - `no_excessive_blanks`: No more than 2 consecutive blank lines
    - `has_examples`: Contains usage examples

    **Example**:
        ```python
        from crackerjack.documentation.docstring_extractor import validate_docstring_quality

        quality = validate_docstring_quality(my_docstring)
        if quality["has_bold"] and quality["has_examples"]:
            print("✅ High quality docstring")
        ```
    """
    return {
        "has_bold": "**" in docstring,
        "has_code_blocks": "```" in docstring,
        "no_excessive_blanks": "\n\n\n\n" not in docstring,
        "has_examples": "```" in docstring or "Example:" in docstring,
    }
