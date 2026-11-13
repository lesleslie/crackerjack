"""Guard test: every published MCP tool must carry a non-empty description.

FastMCP derives a tool's ``description`` field from its function
docstring. When the docstring is absent the tool is published with
``description: null`` — the tool still appears in ``tools/list``, so the
damage is invisible to a caller that only counts tools, but clients that
require both a name and a description treat it as unusable. qwen-code is
one such client: it counts ``serverTools.filter(x => !x.name ||
!x.description).length`` as "invalid tools". Every one of Crackerjack's
invalid tools was a tool function with no docstring.

The guard is static (AST-based) so it is CI-safe and needs no running MCP
server. It scans ``crackerjack/mcp/tools/**/*.py`` for functions carrying
a tool decorator (``@mcp.tool(...)``, ``@mcp_app.tool(...)``,
``@app.tool(...)``) and asserts each one has a non-empty docstring.

A second test pins a floor on the number of tool-decorated functions the
scan finds, so the scan cannot silently stop matching (a guard that
matches nothing is worse than no guard).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = PROJECT_ROOT / "crackerjack" / "mcp" / "tools"

# Floor on the number of tool-decorated functions the scan must find.
# Bump this when tools are added; the point is to catch a scan that
# silently stops matching (renamed decorator, moved directory, ...).
MIN_TOOL_FUNCTIONS = 30

# Tool functions that are intentionally excluded from the docstring
# requirement. Each entry MUST be justified inline.
#
# ``eventbridge_tools.py::publish_to_eventbridge`` is registered only when
# ``crackerjack.yaml::eventbridge.enabled=true`` (default false), so it is
# absent from the live server's tool surface. It is still listed here so
# the exclusion is explicit rather than an accident of the scan.
EXCLUDED_TOOL_FUNCTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("eventbridge_tools.py", "publish_to_eventbridge"),
    },
)


def _tool_module_paths() -> list[Path]:
    """Return every ``.py`` file under ``crackerjack/mcp/tools/``."""
    return sorted(p for p in TOOLS_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _is_tool_decorator(decorator: ast.expr) -> bool:
    """True when ``decorator`` is a ``<something>.tool(...)`` call.

    Covers ``@mcp.tool(...)``, ``@mcp_app.tool(...)`` and ``@app.tool(...)``.
    A bare ``@tool`` (no attribute) is not a tool decorator.
    """
    return (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "tool"
    )


def _tool_functions() -> list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Return every tool-decorated function under the tools directory."""
    found: list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for module_path in _tool_module_paths():
        try:
            tree = ast.parse(
                module_path.read_text(encoding="utf-8"), filename=str(module_path)
            )
        except SyntaxError:  # pragma: no cover - a syntax error fails CI elsewhere
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_is_tool_decorator(d) for d in node.decorator_list):
                found.append((module_path, node))
    return found


@pytest.mark.unit
def test_tool_functions_have_docstrings() -> None:
    """Every tool-decorated function must have a non-empty docstring.

    Without one, FastMCP publishes the tool with ``description: null``.
    MCP clients that require a description to consider a tool usable
    (qwen-code counts ``!x.name || !x.description`` as invalid) then
    refuse to call it, so a missing docstring silently removes the tool
    from those clients' tool surface.
    """
    missing: list[str] = []

    for module_path, node in _tool_functions():
        if (module_path.name, node.name) in EXCLUDED_TOOL_FUNCTIONS:
            continue
        docstring = ast.get_docstring(node)
        if docstring is None or not docstring.strip():
            missing.append(f"{module_path.name}:{node.lineno} {node.name}")

    assert not missing, (
        "Tool functions with no usable docstring (FastMCP publishes these "
        "with `description: null`, and MCP clients that require a "
        "description count them as invalid tools):\n"
        + "\n".join(f"  - {entry}" for entry in missing)
    )


@pytest.mark.unit
def test_tool_function_scan_matches_expected_volume() -> None:
    """The scan must find at least ``MIN_TOOL_FUNCTIONS`` tool functions.

    A guard that matches nothing passes vacuously. This pins the scan's
    reach so a renamed decorator, a moved directory or a broken glob is
    caught here rather than silently disabling the docstring guard.
    """
    tool_functions = _tool_functions()

    assert len(tool_functions) >= MIN_TOOL_FUNCTIONS, (
        f"Only {len(tool_functions)} tool-decorated functions found under "
        f"{TOOLS_DIR.relative_to(PROJECT_ROOT)} — expected at least "
        f"{MIN_TOOL_FUNCTIONS}. The tool-decorator scan has probably "
        "stopped matching; the docstring guard above would then pass "
        "vacuously."
    )
