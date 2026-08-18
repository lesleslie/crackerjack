"""Regression tests for MCP tool registration drift in Crackerjack.

These tests pin the contract that the ``register_*_tools`` functions declared
in ``crackerjack/mcp/tools/*.py`` are exercised by
``crackerjack/mcp/server_core.py`` and vice-versa. They are the
Contract 5.x guard documented in
``docs/architecture/MEMORY_ARCHITECTURE.md`` (paragraph on tool drift).

Four failure surfaces are covered:

1. ``test_server_core_calls_resolve`` — every ``register_X(mcp_app)`` call
   in ``server_core.py`` (lines 228-262 + line 495) resolves to an imported
   symbol — guards against typo'd call sites that NameError at server start.
2. ``test_no_unused_register_imports`` — every register_X imported at top
   of ``server_core.py`` is called somewhere in the file — guards against
   dead imports that load work into server startup without wiring it up.
3. ``test_each_register_function_has_unique_tools`` — each register_X
   function in ``crackerjack/mcp/tools/*.py`` registers at least one
   ``@mcp.tool`` / ``@mcp_app.tool`` decorator — guards against no-op
   register functions declared for show.
4. ``test_docs_match_registered_tools`` — if a Crackerjack MCP tool spec
   document exists, parse it for tool names and assert each register_X in
   ``server_core.py`` is documented. If no such file exists, skip with an
   explanatory note.
5. ``test_no_orphan_register_modules`` — every module file in
   ``crackerjack/mcp/tools/`` that defines a ``register_*`` function has
   that function called from ``server_core.py``. Otherwise the module is
   dead code.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVER_CORE_PATH = PROJECT_ROOT / "crackerjack" / "mcp" / "server_core.py"
TOOLS_INIT_PATH = PROJECT_ROOT / "crackerjack" / "mcp" / "tools" / "__init__.py"
TOOLS_DIR = PROJECT_ROOT / "crackerjack" / "mcp" / "tools"
DOCS_DIR = PROJECT_ROOT / "docs"

# Pin the import block in server_core.py where register_X symbols are imported.
SERVER_CORE_IMPORT_BLOCK_START = 75
SERVER_CORE_IMPORT_BLOCK_END = 90

# Server core call sites are scanned across the entire file (the line range
# shifted every time a new ``register_X(mcp_app)`` was added in the
# create_mcp_server() block). The skill-tools call lives in a separate
# entry-point function below the block. Scanning the whole file
# preserves both, robust to future edits.
SERVER_CORE_CALL_BLOCK_START = 1
SERVER_CORE_CALL_BLOCK_END = 10_000  # effectively whole file

# The skill-tools call lives outside the create_mcp_server() call block.
# Updated when the line range shifted; the full-file scan above makes
# this a fallback rather than the primary mechanism.
SERVER_CORE_SKILL_CALL_LINE = 497

# Register functions that are intentionally NOT wired into server_core.py.
# Each entry MUST be documented inline in its tool module with a TODO
# pointing to the plan that explains the deferral. The
# ``test_no_orphan_register_modules`` test subtracts this set from the
# orphan list before asserting.
#
# Current entries:
# - ``register_workspace_tools``: workspace manager backend was removed in
#   Phase 2; awaiting Phase 3 (Oneiric integration) reimplementation
#   per MEMORY_ARCHITECTURE.md Contract 5.7.
INTENTIONAL_DEFERRED_REGISTERS: frozenset[str] = frozenset({
    "register_workspace_tools",
})


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse(path: Path) -> ast.Module:
    return ast.parse(_read_text(path), filename=str(path))


def _imported_register_names(source: str) -> set[str]:
    """Return every ``register_*`` symbol imported anywhere in ``source``.

    Uses AST so multi-line parenthesised imports (the dominant style in
    ``server_core.py`` lines 75-90, plus ``register_health_tools`` at
    line 16) are handled uniformly.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name.startswith("register_"):
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("register_"):
                    names.add(alias.asname or alias.name.split(".")[0])
    return names


def _called_register_names(source: str, start: int, end: int) -> set[str]:
    """Return ``register_X`` tokens that appear as call targets in lines ``start..end``.

    Tokens are matched when followed by ``(`` on the same line. This catches
    both unconditional and conditional call sites (``register_eventbridge_tools(...)``,
    ``register_pycharm_tools(mcp_app)``).
    """
    line_iter = source.splitlines()
    names: set[str] = set()
    for lineno, line in enumerate(line_iter, start=1):
        if lineno < start or lineno > end:
            continue
        for match in re.finditer(r"\b(register_[A-Za-z0-9_]+)\s*\(", line):
            names.add(match.group(1))
    return names


def _register_function_names_in_module(module_path: Path) -> set[str]:
    """Return the set of top-level ``def register_X(...)`` function names."""
    if not module_path.exists():
        return set()
    try:
        tree = _parse(module_path)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("register_"):
                names.add(node.name)
    return names


def _register_function_body_lines(module_path: Path) -> list[ast.AST]:
    """Return top-level ``register_*`` FunctionDef/AsyncFunctionDef nodes.

    Used to inspect function bodies for at least one ``@mcp.tool`` (or
    equivalent ``mcp_app.tool(...)`` invocation).
    """
    try:
        tree = _parse(module_path)
    except SyntaxError:
        return []
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("register_")
    ]


def _function_registers_tool(
    module_path: Path,
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """True if ``func`` registers at least one tool, directly or via helpers.

    Three patterns are accepted:

    * a nested ``async def`` / ``def`` directly inside ``func`` carrying
      ``@mcp_app.tool(...)`` (common for one-shot register functions);
    * a call to ``mcp_app.tool(...)`` / ``mcp.tool(...)`` inside ``func``
      (used by ``workspace_tools``-style adapters);
    * a call from ``func`` to a module-level ``_register_<helper>`` that
      contains the decorator on one of its nested functions (the dominant
      pattern across ``crackerjack/mcp/tools/*.py``).
    """
    source_lines = _read_text(module_path).splitlines()
    # Slice from the ``def`` line to end_lineno — captures decorators that
    # sit on the line immediately preceding ``body[0]``.
    func_text = "\n".join(source_lines[func.lineno - 1 : func.end_lineno])

    if re.search(r"@mcp(?:_app)?\.tool\s*\(", func_text):
        return True
    if re.search(r"\bmcp(?:_app)?\.tool\s*\(", func_text):
        return True

    # Indirect: ``func`` calls a ``_register_<helper>(mcp_app)`` and that
    # helper carries the decorator. One level of indirection is enough for
    # the Crackerjack tools directory.
    helper_names: set[str] = set()
    for node in ast.walk(ast.parse(func_text)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id.startswith("_register_")
        ):
            helper_names.add(node.func.id)

    if not helper_names:
        return False

    try:
        tree = _parse(module_path)
    except SyntaxError:
        return False
    for helper in tree.body:
        if (
            isinstance(helper, (ast.FunctionDef, ast.AsyncFunctionDef))
            and helper.name in helper_names
        ):
            if _function_registers_tool(module_path, helper):
                return True
    return False


# ---------------------------------------------------------------------------
# Test fixtures / module-level discovery
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def server_core_source() -> str:
    return _read_text(SERVER_CORE_PATH)


@pytest.fixture(scope="module")
def imported_register_names(server_core_source: str) -> set[str]:
    return _imported_register_names(server_core_source)


@pytest.fixture(scope="module")
def called_register_names(server_core_source: str) -> set[str]:
    """Union of register_X tokens called inside the create_mcp_server block
    and the additional ``register_skill_tools(mcp_app)`` call at line 495.
    """
    in_block = _called_register_names(
        server_core_source,
        SERVER_CORE_CALL_BLOCK_START,
        SERVER_CORE_CALL_BLOCK_END,
    )
    # The skill-tools call lives outside the create_mcp_server() call block.
    lines = server_core_source.splitlines()
    if SERVER_CORE_SKILL_CALL_LINE - 1 < len(lines):
        line = lines[SERVER_CORE_SKILL_CALL_LINE - 1]
        for match in re.finditer(r"\b(register_[A-Za-z0-9_]+)\s*\(", line):
            in_block.add(match.group(1))
    # W2a: also count kwarg-style calls like ``register_all_fn=register_all_tool_groups``
    # (the W0 helper is invoked with kwargs, not positional calls).
    for match in re.finditer(
        r"\bregister_[A-Za-z0-9_]+=\s*\b(register_[A-Za-z0-9_]+)\b",
        server_core_source,
    ):
        in_block.add(match.group(1))
    return in_block


@pytest.fixture(scope="module")
def tool_module_paths() -> list[Path]:
    return sorted(p for p in TOOLS_DIR.glob("*.py") if p.name != "__init__.py")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_server_core_calls_resolve(
    imported_register_names: set[str],
    called_register_names: set[str],
) -> None:
    """Every ``register_X(mcp_app)`` call in server_core.py must resolve.

    Prevents NameError at server startup if a future refactor renames an
    imported register_X but leaves the call site behind (or vice-versa).
    """
    unresolved = called_register_names - imported_register_names

    assert not unresolved, (
        "server_core.py calls register_X symbols that are not imported "
        f"anywhere in the file: {sorted(unresolved)}"
    )


@pytest.mark.unit
def test_no_unused_register_imports(
    imported_register_names: set[str],
    called_register_names: set[str],
) -> None:
    """Every imported ``register_X`` must be called at least once.

    Catches dead imports that load modules at server start without
    wiring them up — a gateway anti-pattern that produces silent drift
    between the surface documented in MEMORY_ARCHITECTURE.md and what
    the running server actually exposes.
    """
    unused = imported_register_names - called_register_names

    assert not unused, (
        "server_core.py imports register_X symbols but never calls them "
        f"(lines {SERVER_CORE_IMPORT_BLOCK_START}-{SERVER_CORE_IMPORT_BLOCK_END} "
        "imports vs. "
        f"{SERVER_CORE_CALL_BLOCK_START}-{SERVER_CORE_CALL_BLOCK_END} + "
        f"line {SERVER_CORE_SKILL_CALL_LINE} calls): "
        f"{sorted(unused)}"
    )


@pytest.mark.unit
def test_each_register_function_has_unique_tools(tool_module_paths: list[Path]) -> None:
    """Every register_X function must register at least one tool.

    Catches the no-op pattern where a register function is declared for
    show but contains no decorators. We also assert that consecutive
    register functions in the same module don't register tools with the
    same name (which would silently shadow each other).
    """
    missing_tools: list[str] = []
    duplicate_tools: dict[str, list[str]] = {}

    for module_path in tool_module_paths:
        try:
            tree = _parse(module_path)
        except SyntaxError:
            continue
        register_nodes = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("register_")
        ]
        if not register_nodes:
            continue

        for func in register_nodes:
            # W2a: wrappers (e.g., ``register_crackerjack_health``) wrap an
            # existing register_X and may not have a direct @mcp_app.tool().
            # Skip files explicitly tagged as wrappers.
            if module_path.name in {"health_tools_wrapper.py", "eventbridge_tools_wrapper.py"}:
                continue
            if module_path.name == "profiles.py" and func.name in {
                "register_all_tool_groups",
            }:
                # profiles.py's register_all_tool_groups is the W0
                # ``register_all_fn`` — delegates to per-group register
                # functions; not a direct tool registrar.
                continue
            if not _function_registers_tool(module_path, func):
                missing_tools.append(f"{module_path.name}::{func.name}")

            # Detect tools whose ``name=`` argument clashes with another
            # tool in the same module — silent shadowing.
            source_lines = _read_text(module_path).splitlines()
            func_text = "\n".join(source_lines[func.lineno - 1 : func.end_lineno])
            for match in re.finditer(
                r"@\s*mcp(?:_app)?\.tool\s*\(\s*name\s*=\s*['\"]([A-Za-z0-9_]+)['\"]",
                func_text,
            ):
                tool_name = match.group(1)
                duplicate_tools.setdefault(tool_name, []).append(
                    f"{module_path.name}::{func.name}"
                )

    assert not missing_tools, (
        "register_X functions that register zero tools (no-op stubs): "
        f"{missing_tools}"
    )

    clashing = {name: sites for name, sites in duplicate_tools.items() if len(sites) > 1}
    assert not clashing, (
        "Two or more register_X functions in the same module declare a "
        "tool with the same name (silent shadowing): "
        f"{clashing}"
    )


@pytest.mark.unit
def test_docs_match_registered_tools(
    called_register_names: set[str],
) -> None:
    """Documented tools should match the registered tool surface.

    If ``crackerjack/docs/MCP_TOOLS_SPECIFICATION.md`` (or a clearly-named
    sibling) exists, parse it and assert every ``register_X`` called
    from ``server_core.py`` shows up in the spec. Flag spec entries that
    document register names that aren't called.

    If no spec exists, skip with a note rather than fail — the lack of a
    spec is itself a finding (documented in the MEMORY_ARCHITECTURE.md
    gap list at the top of this file).
    """
    spec_candidates = [
        DOCS_DIR / "MCP_TOOLS_SPECIFICATION.md",
        DOCS_DIR / "MCP_TOOLS.md",
        DOCS_DIR / "mcp_tools_specification.md",
    ]
    spec_path = next((p for p in spec_candidates if p.exists()), None)

    if spec_path is None:
        pytest.skip(
            "No MCP_TOOLS_SPECIFICATION.md found under docs/ — this is a "
            "documentation gap (see contract 5.x in MEMORY_ARCHITECTURE.md). "
            "Create one to enable this test."
        )

    spec_text = _read_text(spec_path)

    # Strip code fences so we don't false-match decorator references.
    cleaned = re.sub(r"```.*?```", "", spec_text, flags=re.DOTALL)

    documented_registers: set[str] = set()
    for match in re.finditer(r"\bregister_[A-Za-z0-9_]+\b", cleaned):
        documented_registers.add(match.group(0))

    undocumented = called_register_names - documented_registers
    extra_documented = documented_registers - called_register_names

    # Spec files commonly reference the *module name* (``register_doc_tools``)
    # alongside the *function*; both are valid. Allow extras as informational
    # (not a hard fail) but require every call site to show up somewhere.
    assert not undocumented, (
        f"register_X functions called by server_core.py but missing from "
        f"{spec_path.relative_to(PROJECT_ROOT)}: {sorted(undocumented)}"
    )

    # Stash extras on a module attribute so a developer can spot them
    # without seeing the test as failed.
    if extra_documented:
        # Surface in the test output without failing.
        print(
            f"[INFO] {spec_path.name} references register_X symbols that are "
            f"not called from server_core.py: {sorted(extra_documented)}"
        )


@pytest.mark.unit
def test_no_orphan_register_modules(
    called_register_names: set[str],
    tool_module_paths: list[Path],
) -> None:
    """Every ``register_X`` declared in a tools module must be called.

    Catches the case where a developer adds a new register_X function
    but forgets to wire it into ``create_mcp_server``. The function
    then looks production-ready but contributes zero tools to the surface.

    W2a: the ``register_X`` function is considered "called" if it appears
    as a value in :data:`crackerjack.mcp.tools.profiles.REGISTRATION_MAP`
    (the W0 helper dispatches via the map) OR if ``create_mcp_server``
    invokes it directly.
    """
    orphans: list[str] = []
    modules_without_register: list[str] = []

    # W2a: scan profiles.py::REGISTRATION_MAP for wired register functions.
    # The W0 helper dispatches via the map; if a register_X is in the map,
    # it's wired. REGISTRATION_MAP keys are group names like ``"core_tools"``
    # (not ``"register_core_tools"``); values reference the actual
    # ``register_X`` functions.
    profiles_path = TOOLS_DIR / "profiles.py"
    registration_map_targets: set[str] = set()
    if profiles_path.exists():
        profiles_source = _read_text(profiles_source := profiles_path)
        # Match values like:    "core_tools": register_core_tools,
        # (the trailing comma is optional).
        for match in re.finditer(
            r'"[A-Za-z0-9_]+_tools":\s*(register_[A-Za-z0-9_]+)',
            profiles_source,
        ):
            registration_map_targets.add(match.group(1))
        # Also catch non-tool group keys like ``"health_tools"`` → ``register_crackerjack_health``
        for match in re.finditer(
            r'"[A-Za-z0-9_]+":\s*(register_[A-Za-z0-9_]+)',
            profiles_source,
        ):
            registration_map_targets.add(match.group(1))

    wired_names = called_register_names | registration_map_targets

    # W2a: wrappers call ``register_X(...)`` transitively. Scan wrapper
    # files for inner register_X calls so transitive wiring is counted.
    wrapper_files = {"health_tools_wrapper.py", "eventbridge_tools_wrapper.py"}
    for module_path in tool_module_paths:
        if module_path.name not in wrapper_files:
            continue
        for match in re.finditer(
            r"\b(register_[A-Za-z0-9_]+)\s*\(",
            _read_text(module_path),
        ):
            wired_names.add(match.group(1))

    for module_path in tool_module_paths:
        # W2a: profiles.py is the W0 dispatcher — skip it (its register_*
        # names are internal aliases, not module surface).
        if module_path.name == "profiles.py":
            continue
        module_register_names = _register_function_names_in_module(module_path)
        if not module_register_names:
            modules_without_register.append(module_path.name)
            continue
        for register_name in sorted(module_register_names):
            if register_name not in wired_names:
                if register_name in INTENTIONAL_DEFERRED_REGISTERS:
                    continue
                orphans.append(f"{module_path.name}::{register_name}")

    assert not orphans, (
        "register_X functions declared in mcp/tools/*.py but never called "
        f"from server_core.py: {orphans}"
    )

    # Modules without any register_X function are still informative — they
    # may be helpers (e.g., ``error_analyzer.py``, ``workflow_executor.py``).
    # We only warn; the test won't fail on this so that legitimate
    # helper modules don't break the contract.
    if modules_without_register:
        print(
            f"[INFO] Tools modules without any register_X function "
            f"(not orphans — likely helpers): {sorted(modules_without_register)}"
        )
