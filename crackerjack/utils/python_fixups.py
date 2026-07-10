from __future__ import annotations

import ast
import re


def normalize_future_import_position(content: str) -> str:
    had_trailing_newline = content.endswith("\n")
    lines = content.split("\n")

    future_lines = [
        line for line in lines if line.strip().startswith("from __future__ import ")
    ]
    if not future_lines:
        return content

    remaining = [
        line for line in lines if not line.strip().startswith("from __future__ import ")
    ]
    insert_idx = _find_future_import_index(remaining)

    for future_line in reversed(future_lines):
        remaining.insert(insert_idx, future_line)

    result = "\n".join(remaining)
    if had_trailing_newline and not result.endswith("\n"):
        result += "\n"
    return result


_TYPE_IGNORE_RE = re.compile(r"^\s*#\s*type:\s*ignore(\[[\w\-,\s]*\])?$")


def fix_misplaced_type_ignores(content: str, issue_line_number: int | None) -> str:
    if issue_line_number is None:
        return content

    had_trailing_newline = content.endswith("\n")
    lines = content.split("\n")

    if not (1 <= issue_line_number <= len(lines)):
        return content

    issue_idx = issue_line_number - 1

    if "# type: ignore" in lines[issue_idx]:
        return content

    next_idx = issue_idx + 1
    if next_idx >= len(lines):
        return content

    next_line = lines[next_idx]
    if not _TYPE_IGNORE_RE.match(next_line):
        return content

    type_ignore_comment = next_line.strip()
    lines.pop(next_idx)
    lines[issue_idx] = lines[issue_idx].rstrip() + " " + type_ignore_comment

    result = "\n".join(lines)
    if had_trailing_newline and not result.endswith("\n"):
        result += "\n"
    return result


def _find_future_import_index(lines: list[str]) -> int:
    insert_idx = 0
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        tree = None  # type: ignore[assignment]

    if tree and tree.body:
        first_node = tree.body[0]
        docstring = ast.get_docstring(tree, clean=False)
        if docstring and isinstance(first_node, ast.Expr):
            insert_idx = getattr(first_node, "end_lineno", first_node.lineno)

    while insert_idx < len(lines):
        stripped = lines[insert_idx].strip()
        if not stripped or stripped.startswith("#"):
            insert_idx += 1
            continue
        break

    return insert_idx
