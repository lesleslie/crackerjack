"""audit_type_checking_runtime_refs.py — detect TYPE_CHECKING imports used at runtime.

When a Python file uses ``from __future__ import annotations`` (the crackerjack
convention) and ALSO imports names under ``if TYPE_CHECKING:``, those names
are not visible at runtime — only the type checker sees them. Any non-annotation
reference to those names at runtime will raise ``NameError`` (or, for Pydantic
models, ``PydanticUserError: class-not-fully-defined``).

This audit walks each Python file's AST and reports any non-annotation reference
to a name that was imported under a TYPE_CHECKING block. The fix is mechanical:
move the offending import out of ``if TYPE_CHECKING:`` and keep
``from __future__ import annotations`` for forward-compat.

Confirmed bug instances in the Bodai ecosystem (2026-08-31):
  - opera-cloud-mcp — 31 test failures (Pydantic forward-ref)
  - graphics-mcp   — runtime NameError in pillow result constructors
  See: docs/audit/2026-08-31-pydantic-future-annotations-bodai-survey.md

Exit codes:
    0 — no violations found
    1 — at least one violation found
    2 — could not scan (e.g. file unreadable)

Usage:
    python scripts/audit_type_checking_runtime_refs.py [ROOT...] [--json]
    python scripts/audit_type_checking_runtime_refs.py --root /Users/les/Projects/mahavishnu
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

# Directories that should never be scanned. Path-component match (not glob)
# so "scripts/__pycache__/foo.py" is also excluded by the "__pycache__" entry.
EXCLUDE_DIRS: tuple[str, ...] = (
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "build",
    "dist",
    ".git",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    ".eggs",
    ".worktrees",
    ".claude",  # exclude worktree metadata + skill scripts
    ".crackerjack",  # uv sdist cache (binary vendored sources)
    ".backups",  # worktree backup directories
    "site-packages",  # third-party installed packages
)

# Functions whose first positional argument is type-only (annotation context).
# ``typing.cast(T, x)`` returns x unchanged; T is never evaluated at runtime.
TYPE_ERASED_FUNCTIONS: frozenset[str] = frozenset({"cast"})


@dataclass(frozen=True)
class ImportedName:
    """A single name imported under TYPE_CHECKING.

    ``runtime_name`` is what the caller sees at runtime (after ``as`` aliasing).
    For ``from X import Y as Z`` -> runtime_name is ``Z``.
    For ``import X`` -> runtime_name is ``X`` (the module).
    For ``from X import *`` -> we record ``*`` and skip the runtime check
    because we can't statically know the names.
    """

    runtime_name: str
    import_lineno: int
    is_star: bool = False


@dataclass(frozen=True)
class Violation:
    """A runtime reference to a TYPE_CHECKING-only name."""

    file: Path
    lineno: int
    col_offset: int
    name: str
    import_lineno: int
    context: str  # short snippet of how the name is used


@dataclass
class FileResult:
    """Audit outcome for one Python file."""

    path: Path
    violations: list[Violation] = field(default_factory=list)
    parse_error: str | None = None


def _is_type_checking_test(node: ast.expr) -> bool:
    """True when ``if <node>:`` is the standard ``if TYPE_CHECKING:`` guard.

    Accepts:
      - ``if TYPE_CHECKING:``           (ast.Name id='TYPE_CHECKING')
      - ``if typing.TYPE_CHECKING:``    (ast.Attribute attr='TYPE_CHECKING')
      - ``if not TYPE_CHECKING:`` is NOT accepted — that branch is the runtime path.
    """
    if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
        return True
    return isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING"


def _collect_type_checking_imports(tree: ast.Module) -> list[ImportedName]:
    """Find names that are TC-only (imported under TYPE_CHECKING AND NOT bound at runtime elsewhere).

    The two-pass design matters for the common patterns::

        # Pattern A: TC-only name with runtime fallback in else
        if TYPE_CHECKING:
            from foo import Bar  # TC-only when NOT in else
        else:
            from foo import Bar  # runtime import — name IS bound at runtime
        Bar()  # safe — else-branch import binds Bar

        # Pattern B: TC + try/except runtime import (same name in both)
        if TYPE_CHECKING:
            from foo import Bar
        try:
            from foo import Bar
        except ImportError:
            Bar = None
        Bar()  # safe — try block imports Bar at runtime

    Algorithm:
      1. Collect all Import/ImportFrom nodes in the file.
      2. Classify each as TC-body or runtime based on whether it lives
         inside an ``if TYPE_CHECKING:`` body (recursively through nested
         TC ifs). Imports inside TC ifs' ``else`` branches are runtime.
      3. Collect names bound at runtime via three patterns:
         - Direct imports outside TC body (top-level, function-local)
         - Else-branch imports (Pattern B variant 1)
         - Else-branch assignments like ``Msg = Any`` (Pattern B variant 2)
         - Else-branch rebinds like ``trace = _trace`` where ``_trace`` is
           imported via the else-branch's aliased import (Pattern B variant 3)
      4. Names in TC-body that are also bound at runtime are excluded
         — they're not TC-only.
    """
    parents = _build_parent_map(tree)
    tc_body_ids = _collect_tc_body_node_ids(tree, parents)

    # First pass: classify all import sites.
    tc_candidates: list[ImportedName] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                if id(node) in tc_body_ids:
                    tc_candidates.append(
                        ImportedName(runtime_name=name, import_lineno=node.lineno)
                    )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    if id(node) in tc_body_ids:
                        tc_candidates.append(
                            ImportedName(
                                runtime_name="*",
                                import_lineno=node.lineno,
                                is_star=True,
                            )
                        )
                    # Star imports at runtime contribute unknown names —
                    # we can't statically know what they are, so don't add
                    # to runtime_names.
                    continue
                name = alias.asname or alias.name
                if id(node) in tc_body_ids:
                    tc_candidates.append(
                        ImportedName(runtime_name=name, import_lineno=node.lineno)
                    )

    # Collect runtime-bound names: any name imported outside TC body, OR
    # any name assigned in the else-branch of a TC If (Pattern B variants 2+3).
    runtime_names = _collect_runtime_bound_names(tree, parents, tc_body_ids)

    # Filter: drop TC candidates that are also bound at runtime.
    return [n for n in tc_candidates if n.runtime_name not in runtime_names]


def _is_in_tc_else(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """True when ``node`` lives in the orelse branch of a TYPE_CHECKING If.

    Walks ancestors to determine if any ancestor is a TYPE_CHECKING ``if``
    whose ``orelse`` clause contains the node. A node inside the ``body``
    of a TYPE_CHECKING If returns False (it's still TC-only).
    """
    cur: ast.AST | None = node
    while cur is not None:
        par = parents.get(id(cur))
        if par is None:
            return False
        if isinstance(par, ast.If):
            if cur in par.body:
                # We're in a TC If's body — NOT in the else branch.
                # (Could still be in outer If's orelse if outer If isn't TC,
                # but that's a runtime conditional, not a TC body. The point
                # is: we're inside a TC body, which is TC-only territory.)
                return False
            # orelse of a TC If → True; orelse of a non-TC If → False (runtime).
            return cur in par.orelse and _is_type_checking_test(par.test)
        cur = par
    return False


def _collect_runtime_bound_names(
    tree: ast.Module, parents: dict[int, ast.AST], tc_body_ids: set[int]
) -> set[str]:
    """Collect every name bound at runtime outside TYPE_CHECKING body.

    Captures three runtime-binding patterns:

    A. **Direct imports outside TC body** — top-level imports, function-local
       imports, try/except runtime imports.
    B. **Else-branch imports** — ``if TYPE_CHECKING: ... else: from foo import X``
    C. **Else-branch assignments** — ``if TYPE_CHECKING: ... else: X = Any``
       (Pattern B variant 2) or ``... else: X = _X`` where ``_X`` was imported
       in the same else-branch via an aliased import (Pattern B variant 3).

    The LHS of else-branch assignments is added to the runtime-bound set
    because the assignment executes at runtime whenever TYPE_CHECKING is
    False, binding the name even if the RHS is a TC-only thing the audit
    missed. The audit is conservative — it assumes any assignment to a name
    binds it. If the RHS is itself broken, the runtime error surfaces
    there; we still correctly exclude the LHS from TC-only tracking.
    """
    return _collect_runtime_imports(
        tree, tc_body_ids
    ) | _collect_else_branch_assignments(tree, parents)


def _collect_runtime_imports(tree: ast.Module, tc_body_ids: set[int]) -> set[str]:
    """Pass 1: names bound by Import / ImportFrom outside any TYPE_CHECKING body."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if id(node) in tc_body_ids:
            continue
        if isinstance(node, ast.Import):
            names.update(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )
        else:
            names.update(
                alias.asname or alias.name for alias in node.names if alias.name != "*"
            )
    return names


def _collect_else_branch_assignments(
    tree: ast.Module, parents: dict[int, ast.AST]
) -> set[str]:
    """Pass 2: names assigned inside the else-branch of a TYPE_CHECKING If.

    Covers both ``X = Any`` (Pattern B variant 2) and ``X = _X`` after an
    aliased import in the same else-branch (Pattern B variant 3).
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if not _is_in_tc_else(node, parents):
                continue
            for target in node.targets:
                if target is not None:
                    names.update(_names_under_target(target))
        elif isinstance(node, ast.AnnAssign):
            if node.target is None or not _is_in_tc_else(node, parents):
                continue
            names.update(_names_under_target(node.target))
    return names


def _names_under_target(target: ast.AST) -> set[str]:
    """Names bound by walking a single assignment target (e.g. ``a.b`` → ``{"a"}``)."""
    names: set[str] = set()
    for inner in ast.walk(target):
        if isinstance(inner, ast.Name):
            names.add(inner.id)
        elif isinstance(inner, ast.Attribute):
            names.add(inner.attr)
    return names


def _has_future_annotations(tree: ast.Module) -> bool:
    """True when the module starts with ``from __future__ import annotations``."""
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "__future__":
            continue
        for alias in node.names:
            if alias.name == "annotations":
                return True
    return False


def _build_parent_map(tree: ast.Module) -> dict[int, ast.AST]:
    """Return ``{id(child): parent}`` for every child in the tree."""
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _collect_annotation_node_ids(tree: ast.Module) -> set[int]:
    """Return ``{id(node)}`` for every node that lives in annotation context.

    Under ``from __future__ import annotations``, the following positions are
    stringified and never trigger a runtime name lookup:
      - Function/AsyncFunction return annotation
      - Function/lambda parameter annotations
      - Annotated assignment (``x: Foo = ...``)
      - The contents of those annotations (recursively, since annotation
        subtrees like ``Foo | None`` contain nested Name nodes)

    Base classes in ``class Foo(Base):`` are NOT stringified; they're
    evaluated at class-definition time. ``except E as V:`` evaluates E at
    runtime. Default values in parameter lists are evaluated at runtime.
    """
    annotation_ids: set[int] = set()
    for node in ast.walk(tree):
        subtrees: list[ast.AST] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                subtrees.append(node.returns)
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                if arg.annotation is not None:
                    subtrees.append(arg.annotation)
            if node.args.vararg and node.args.vararg.annotation is not None:
                subtrees.append(node.args.vararg.annotation)
            if node.args.kwarg and node.args.kwarg.annotation is not None:
                subtrees.append(node.args.kwarg.annotation)
        elif isinstance(node, ast.Lambda):
            # Lambda has no return annotation (PEP 8 forbids them; PEP 563
            # only stringifies FunctionDef/AsyncFunctionDef returns). Just
            # handle parameter annotations.
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                if arg.annotation is not None:
                    subtrees.append(arg.annotation)
            if node.args.vararg and node.args.vararg.annotation is not None:
                subtrees.append(node.args.vararg.annotation)
            if node.args.kwarg and node.args.kwarg.annotation is not None:
                subtrees.append(node.args.kwarg.annotation)
        elif isinstance(node, ast.AnnAssign):
            if node.annotation is not None:
                subtrees.append(node.annotation)
        for subtree in subtrees:
            annotation_ids.update(id(inner) for inner in ast.walk(subtree))
    return annotation_ids


def _collect_tc_body_node_ids(
    tree: ast.Module, parents: dict[int, ast.AST]
) -> set[int]:
    """Return ``{id(node)}`` for every node living in a TYPE_CHECKING If body.

    Walks the tree collecting every node that is inside the BODY of a TYPE_CHECKING
    If (recursively through nested non-TC Ifs). Critically, a node in the orelse
    of any If is NOT in the TC body — even if the If is ``if TYPE_CHECKING:``.
    """
    body_ids: set[int] = set()

    # First, find every TYPE_CHECKING If node.
    tc_ifs: list[ast.If] = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If) and _is_type_checking_test(n.test)
    ]

    # For every node in the tree, determine if it's inside a TC If body by
    # walking ancestors. If any ancestor If puts us in its orelse, we're out.
    for node in ast.walk(tree):
        cur: ast.AST | None = node
        inside_tc = False
        while cur is not None:
            par = parents.get(id(cur))
            if par is None:
                break
            if isinstance(par, ast.If):
                # If we're in the orelse of any If, we left the TC body.
                if cur in par.orelse:
                    inside_tc = False
                    break
                # If we're in the body of a TC If, we're inside.
                if cur in par.body and par in tc_ifs:
                    inside_tc = True
                    break
                # In the body of a non-TC If: keep walking up.
            cur = par
        if inside_tc:
            body_ids.add(id(node))
    return body_ids


def _collect_type_erased_call_arg_ids(
    tree: ast.Module, parents: dict[int, ast.AST]
) -> set[int]:
    """Return ``{id(node)}`` for every node that's the type arg of a type-erased call.

    Currently handles ``typing.cast(T, x)`` — the first positional arg is
    annotation-only (cast returns x unchanged).
    """
    erased_ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name: str | None = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        if func_name not in TYPE_ERASED_FUNCTIONS:
            continue
        if not node.args:
            continue
        # Mark the entire first-arg subtree as type-erased.
        first_arg = node.args[0]
        erased_ids.update(id(inner) for inner in ast.walk(first_arg))
    return erased_ids


def _collect_binding_node_ids(
    tree: ast.Module, parents: dict[int, ast.AST]
) -> set[int]:
    """Return ``{id(node)}`` for every Name/Attribute that is a binding site.

    Binding sites are positions where the name is being assigned to (not
    read). Examples:
      - ``x = None``               -> ``x`` is binding (Assign.targets)
      - ``x: int = None``          -> ``x`` is binding (AnnAssign.target)
      - ``x += 1``                 -> ``x`` is binding (AugAssign.target)
      - ``del x``                  -> ``x`` is binding (Delete.targets)
      - ``for x in iter``          -> ``x`` is binding (For.target)
      - ``with foo as x``          -> ``x`` is binding (withitem.optional_vars)
      - ``except E as x``          -> ``x`` is binding (ExceptHandler.name)

    Treating these as runtime references would produce false positives
    because the LHS Name is not looked up — it's defined.
    """
    binding_ids: set[int] = set()
    for node in ast.walk(tree):
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if node.target is not None:
                targets.append(node.target)
        elif isinstance(node, ast.Delete):
            targets.extend(node.targets)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            if node.target is not None:
                targets.append(node.target)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    targets.append(item.optional_vars)
        elif isinstance(node, ast.ExceptHandler):
            # In Python <3.13, ``name`` is a plain str; in 3.13+ it's an
            # ``ast.Name``. Guard against the legacy str form.
            if node.name is not None and isinstance(node.name, ast.AST):
                targets.append(node.name)
        for target in targets:
            binding_ids.update(id(inner) for inner in ast.walk(target))
    return binding_ids


def _format_context(node: ast.AST) -> str:
    """Short snippet describing how the offending name is used."""
    try:
        return ast.unparse(node).split("\n")[0][:120]
    except Exception:  # pragma: no cover — defensive
        return f"<{type(node).__name__}>"


def _scan_file(path: Path) -> FileResult:
    """Parse one file and return any TYPE_CHECKING-vs-runtime violations."""
    try:
        source = _read_source(path)
    except (OSError, UnicodeDecodeError) as exc:
        return FileResult(path=path, parse_error=f"unreadable: {exc}")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return FileResult(path=path, parse_error=f"syntax error: {exc}")
    return _scan_parsed_tree(tree, path)


def _read_source(path: Path) -> str:
    """Read source text, falling back from UTF-8 to latin-1.

    Raises ``OSError`` or ``UnicodeDecodeError`` on hard failure (after latin-1
    fallback failure). Callers should catch and surface the error as a
    ``FileResult.parse_error`` so the audit can keep going on other files.
    """
    with suppress(UnicodeDecodeError):
        return path.read_text(encoding="utf-8")
    return path.read_text(encoding="latin-1")


def _scan_parsed_tree(tree: ast.Module, path: Path) -> FileResult:
    """Run all audit passes over a parsed AST and assemble a FileResult."""
    tc_imports = _collect_type_checking_imports(tree)
    if not tc_imports:
        return FileResult(path=path)

    name_to_import = _build_name_to_import_lookup(tc_imports)
    if not name_to_import:
        return FileResult(path=path)

    result = FileResult(path=path)
    has_future = _has_future_annotations(tree)
    parents = _build_parent_map(tree)
    skip_ids = _compute_skip_ids(tree, parents, has_future)
    result.violations = _find_runtime_violations(tree, path, name_to_import, skip_ids)
    return result


def _build_name_to_import_lookup(tc_imports: list[ImportedName]) -> dict[str, int]:
    """Build runtime-name → import-line lookup, excluding star imports."""
    return {
        imp.runtime_name: imp.import_lineno for imp in tc_imports if not imp.is_star
    }


def _compute_skip_ids(
    tree: ast.Module, parents: dict[int, ast.AST], has_future: bool
) -> set[int]:
    """Union of all node-id sets we never want to flag as a violation."""
    annotation_ids = _collect_annotation_node_ids(tree) if has_future else set()
    tc_body_ids = _collect_tc_body_node_ids(tree, parents)
    erased_ids = _collect_type_erased_call_arg_ids(tree, parents)
    binding_ids = _collect_binding_node_ids(tree, parents)
    return tc_body_ids | annotation_ids | erased_ids | binding_ids


def _find_runtime_violations(
    tree: ast.Module,
    path: Path,
    name_to_import: dict[str, int],
    skip_ids: set[int],
) -> list[Violation]:
    """Walk tree, emitting a Violation for each non-skipped runtime reference."""
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if id(node) in skip_ids:
            continue
        candidate = _extract_candidate(node)
        if candidate is None:
            continue
        name, lineno, col_offset = candidate
        if name not in name_to_import:
            continue
        violations.append(
            Violation(
                file=path,
                lineno=lineno,
                col_offset=col_offset,
                name=name,
                import_lineno=name_to_import[name],
                context=_format_context(node),
            )
        )
    return violations


def _extract_candidate(node: ast.AST) -> tuple[str, int, int] | None:
    """Return ``(name, lineno, col_offset)`` for Name/Attribute, else ``None``.

    Captures lineno/col_offset inside the ``isinstance`` narrowing so ty
    accepts ``.lineno`` / ``.col_offset`` on the narrowed type.
    """
    if isinstance(node, ast.Name):
        return node.id, node.lineno, node.col_offset
    if isinstance(node, ast.Attribute):
        return node.attr, node.lineno, node.col_offset
    return None


def _walk_python_files(roots: list[Path]) -> list[Path]:
    """Yield ``.py`` files under each root, excluding build/venv/etc dirs."""
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            parts = set(path.parts)
            if parts & set(EXCLUDE_DIRS):
                continue
            out.append(path)
    return sorted(out)


def render_markdown(results: list[FileResult], root_label: str) -> str:
    """Render the audit as a Markdown report grouped by file."""
    lines: list[str] = []
    lines.extend(
        (
            "# TYPE_CHECKING → Runtime Reference Audit",
            "",
            (
                "Generated by `scripts/audit_type_checking_runtime_refs.py`. "
                "Each entry below is a name imported under `if TYPE_CHECKING:` that "
                "is referenced at runtime (non-annotation context). The fix is to "
                "move the import out of `if TYPE_CHECKING:` while keeping "
                "`from __future__ import annotations` for forward-compat."
            ),
            "",
        )
    )
    total_files = len(results)
    files_with_violations = sum(1 for r in results if r.violations)
    total_violations = sum(len(r.violations) for r in results)
    parse_errors = sum(1 for r in results if r.parse_error)
    lines.extend(
        (
            f"- **Roots**: `{root_label}`",
            f"- **Files scanned**: {total_files}",
            f"- **Files with violations**: {files_with_violations}",
            f"- **Total violations**: {total_violations}",
        )
    )
    if parse_errors:
        lines.append(f"- **Parse errors**: {parse_errors} (see end of report)")
    lines.append("")

    if total_violations == 0 == parse_errors:
        lines.append("**No violations found.**")
        return "\n".join(lines)

    # Cluster summary — group violations by import site across all files.
    # This surfaces "32 failures → 1 fix" patterns at a glance (e.g., when
    # a single TYPE_CHECKING import is referenced in 30 places, all 30
    # usages collapse to one fix: move that one import to top level).
    clusters = _cluster_by_import_site(results)
    if clusters:
        lines.extend(
            (
                "## Cluster summary (by fix site)",
                "",
                (
                    "Each row groups violations that share an import site. Fixing "
                    "the import at that line resolves every violation in the row."
                ),
                "",
            )
        )
        lines.extend(
            (
                "| Files | Import site | Name | Count |",
                "| --- | --- | --- | ---: |",
            )
        )
        # Sort by total count descending — biggest cluster first.
        for key, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
            file_count = len({v.file for v in members})
            import_lineno, name = key
            lines.append(
                f"| {file_count} | line {import_lineno} | `{name}` | {len(members)} |"
            )
        lines.append("")

    # Group violations by file for readability
    for result in results:
        if not result.violations:
            continue
        try:
            rel = result.path.resolve().relative_to(Path.cwd()).as_posix()
        except ValueError:
            rel = str(result.path)
        lines.extend(
            (
                f"## `{rel}`",
                "",
                "| Line | Name | Imported at | Context |",
                "| --- | --- | --- | --- |",
            )
        )
        for v in result.violations:
            ctx = v.context.replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {v.lineno} | `{v.name}` | line {v.import_lineno} | `{ctx}` |"
            )
        lines.append("")

    # Parse-error section
    parse_error_files = [r for r in results if r.parse_error]
    if parse_error_files:
        lines.extend(("## Parse errors (file skipped, not a violation)", ""))
        for r in parse_error_files:
            try:
                rel = r.path.resolve().relative_to(Path.cwd()).as_posix()
            except ValueError:
                rel = str(r.path)
            lines.append(f"- `{rel}` — {r.parse_error}")
        lines.append("")

    return "\n".join(lines)


def _cluster_by_import_site(
    results: list[FileResult],
) -> dict[tuple[int, str], list[Violation]]:
    """Group violations by (import_lineno, name) across all files.

    Returns ``{(import_lineno, name): [Violation, ...]}``. Reviewers use
    this to spot "many usages, one fix" patterns — the canonical example
    is a single TYPE_CHECKING import referenced in 30 places; fixing the
    one import site resolves all 30 violations.
    """
    clusters: dict[tuple[int, str], list[Violation]] = defaultdict(list)
    for result in results:
        for v in result.violations:
            clusters[(v.import_lineno, v.name)].append(v)
    return clusters.copy()


def render_json(results: list[FileResult]) -> str:
    """Render the audit as JSON for downstream tooling."""
    payload: list[dict[str, object]] = []
    for result in results:
        if not result.violations and not result.parse_error:
            continue
        entry: dict[str, object] = {"file": str(result.path)}
        if result.parse_error:
            entry["parse_error"] = result.parse_error
        if result.violations:
            entry["violations"] = [
                {
                    "line": v.lineno,
                    "col": v.col_offset,
                    "name": v.name,
                    "import_lineno": v.import_lineno,
                    "context": v.context,
                }
                for v in result.violations
            ]
        payload.append(entry)
    return json.dumps({"violations": payload}, indent=2)


def parse_args() -> argparse.Namespace:
    """Parse CLI flags."""
    parser = argparse.ArgumentParser(
        prog="audit_type_checking_runtime_refs",
        description=(
            "Find names imported under `if TYPE_CHECKING:` that are referenced "
            "at runtime outside annotation context. Catches a latent bug class "
            "in Bodai ecosystem repos that use `from __future__ import annotations`."
        ),
    )
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        help="Root directories to scan (default: /Users/les/Projects).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of Markdown.",
    )
    parser.add_argument(
        "--out",
        default=None,
        type=Path,
        help="Write report to this file instead of stdout.",
    )
    parser.add_argument(
        "--per-repo",
        action="store_true",
        help=(
            "When scanning /Users/les/Projects, group violations by immediate "
            "parent directory of each file (one report section per Bodai repo)."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Run the audit end-to-end and return a shell exit code."""
    args = parse_args()
    roots = args.roots or [Path("/Users/les/Projects")]
    files = _walk_python_files(roots)
    results: list[FileResult] = [_scan_file(p) for p in files]

    # Optionally regroup by immediate parent (per-repo view)
    if args.per_repo and not args.roots:
        by_repo: dict[Path, list[FileResult]] = defaultdict(list)
        for r in results:
            if r.path.is_relative_to(Path("/Users/les/Projects")):
                rel = r.path.relative_to(Path("/Users/les/Projects"))
                if rel.parts:
                    repo_root = Path("/Users/les/Projects") / rel.parts[0]
                    by_repo[repo_root].append(r)
                else:
                    by_repo[Path("/Users/les/Projects")].append(r)
            else:
                by_repo[r.path.parent].append(r)

        chunks: list[str] = []
        total_violations = 0
        total_files = 0
        for repo_root in sorted(by_repo):
            repo_results = by_repo[repo_root]
            repo_label = str(repo_root)
            repo_violations = sum(len(r.violations) for r in repo_results)
            total_violations += repo_violations
            total_files += len(repo_results)
            chunks.append(render_markdown(repo_results, repo_label))
        header = (
            f"# TYPE_CHECKING → Runtime Reference Audit (per-repo)\n\n"
            f"- **Repos scanned**: {len(by_repo)}\n"
            f"- **Files scanned**: {total_files}\n"
            f"- **Total violations**: {total_violations}\n\n"
        )
        body = header + "\n---\n\n".join(chunks)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(body, encoding="utf-8")
        else:
            print(body)
        return 1 if total_violations > 0 else 0

    # Single-tree mode
    root_label = ", ".join(str(r) for r in roots)
    if args.json:
        body = render_json(results)
    else:
        body = render_markdown(results, root_label)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")
    else:
        print(body)

    has_violations = any(bool(r.violations) for r in results)
    return 1 if has_violations else 0


if __name__ == "__main__":
    sys.exit(main())
