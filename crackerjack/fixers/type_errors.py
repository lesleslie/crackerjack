"""Deterministic type-error fixing: AST/regex splicing for TYPE_ERROR issues.

Extracted from ``crackerjack.agents.type_error_specialist.TypeErrorSpecialistAgent``
(1,107 lines), which is entirely self-contained -- unlike
``RefactoringAgent``/``PerformanceAgent``, it does not delegate to any
``agents/helpers/*`` classes (verified by reading the full original file;
its only imports are ``from .base import FixResult, Issue, IssueType,
SubAgent`` plus stdlib).

What was intentionally dropped versus the original ``TypeErrorSpecialistAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__`` (which only ever
  built ``self.log``), ``get_supported_types``, and ``can_handle``. These
  only ever decided *whether* and *how confidently* this fixer should run
  for a given ``Issue``; that routing job belongs to whatever calls into
  this module now, not to the module itself.
- ``agent_registry.register(TypeErrorSpecialistAgent)`` -- registry plumbing.
- ``AgentContext``-specific file I/O (``self.context.get_file_content``'s
  path-traversal check and file-size cap) -- replaced with a direct
  ``pathlib.Path`` read via ``_read_file`` below. Real file I/O is still
  performed; only the framework wrapper around it is gone.
- ``_fix_generic_types`` -- this method existed in the original but was
  **never called anywhere**: it is not one of the ``run_fix(...)`` steps in
  ``_apply_type_fixes``'s pipeline, and no test in the original suite
  exercised it either. It was a no-op stub (``return (content, [])``
  unconditionally). Confirmed dead via
  ``grep -n "_fix_generic_types\\b"`` across the whole repo -- the only hit
  is the method's own ``def`` line. Not ported.

There is no ``FixPlan``/``ChangeSpec`` applicator (``execute_fix_plan``) in
the original agent -- not invented here, per the plan's own instruction not
to add one where the source has none.

## Scope: every real fixer in the pipeline was ported, not just "Literal"

The task brief's "Interfaces" section names "Literal-type fixes" as the
illustrative example, but ``_apply_type_fixes``'s ``run_fix(...)`` pipeline
dispatches to fourteen distinct real fixers (return-type inference, typing/
common import insertion, ``suppress()`` tuple flattening, unused-typing-
import pruning, ``UP031``/``var-annotated``/``Literal`` mismatch handling,
``Protocol``/``Self`` pattern detection, ``Optional``/``Union`` modernization,
and three ``ty``-specific error-code handlers) -- all fourteen are ported
here as plain module-level functions, matching the precedent from Task 13
(``refurb.py``): an illustrative brief example is not the full scope: the
full scope is everything the pipeline (here, the ``run_fix`` sequence in
``apply_type_fixes``) actually reaches.

## Preserved quirks/bugs (not "fixed" -- see CLAUDE.md Rule 7)

1. ``_infer_return_type_from_body``'s ``content: str`` parameter is accepted
   but never read in its body (return-type inference walks ``node`` via
   ``ast.walk`` only). Preserved verbatim -- the parameter stays, unused,
   matching the original signature and the ported test's call site.
2. ``_process_class_methods``'s ``class_names: set[str]`` parameter is
   accepted but never read in its body. Preserved verbatim for the same
   reason.
3. The original ``_apply_type_fixes(self, content, issue, file_path)`` took
   a ``file_path: Path`` parameter that was never referenced anywhere in
   its body. Dropped from the renamed ``apply_type_fixes(content, issue)``
   below -- this one is a pure argument-list simplification with zero
   behavioral effect (no test in the original suite called
   ``_apply_type_fixes`` directly, so there is no call site whose meaning
   changes).
4. ``_fix_unresolved_import_with_ty_ignore``'s ``if "# type: ignore" in
   line: ... else: ...`` branches are byte-for-byte identical -- both just
   append ``# ty: ignore[unresolved-import]`` regardless of which branch is
   taken. This looks like an incomplete original implementation (presumably
   intended to handle the "already has a mypy ignore" case differently), but
   it is preserved verbatim, not simplified/"fixed," per CLAUDE.md Rule 7.
5. ``apply_type_fixes`` and ``fix_type_error_issue`` are declared
   ``async def`` despite containing no ``await`` anywhere in their bodies --
   this matches the original ``_apply_type_fixes``/``analyze_and_fix``
   (both also ``async`` with no internal ``await``), and the same
   already-established precedent for this situation in
   ``crackerjack/fixers/dead_code.py`` (``_backup_file``/``_rollback_file``).
6. **``_add_self_type_for_methods``/``_try_convert_to_self`` is permanent
   dead code for any real function signature.** ``_try_convert_to_self``
   does ``re.sub(f"\\b-> {class_name}\\b", "-> Self", old_line)``. The
   leading ``\b`` requires a word/non-word transition immediately before
   ``-``, but in valid Python the character before ``-`` in a return
   annotation is always ``)`` or whitespace -- both non-word characters --
   so that boundary is never satisfied and the substitution never fires.
   Discovered empirically while writing this task's tests (the original
   test suite never exercised this method end-to-end with realistic
   content -- only its helper predicates in isolation, e.g.
   ``_is_self_type_issue``/``_should_skip_method``). Preserved verbatim,
   not "fixed." Pinned by
   ``TestSelfTypeHelpers::test_add_self_type_for_methods_is_a_no_op_due_to_preexisting_regex_bug``
   in ``tests/fixers/test_type_errors.py``.
7. **A line-number-based fix can silently miss its target because
   ``_apply_common_fixes`` unconditionally shifts line numbers first.**
   ``apply_type_fixes`` runs ``_apply_common_fixes`` (which calls
   ``_add_future_annotations``, inserting ``from __future__ import
   annotations`` as a new line 1 whenever it's missing -- regardless of
   what the current ``Issue`` is actually about) *before* any of the
   line-number-indexed fixers (``_fix_up031_percent_format``,
   ``_fix_var_annotated``, the three ``ty``-error-code handlers).
   ``issue.line_number`` is never adjusted for the shift. For a file
   lacking ``from __future__ import annotations``, a fix targeting line 1
   (or any line at/after the insertion point) will index into the wrong
   line -- the fix silently fails to land, while ``fix_type_error_issue``
   still reports ``success=True`` because *some* change was made (the
   future-annotations insertion), just not the intended one. This is the
   exact original ``_apply_type_fixes`` step order, unchanged by this
   port -- not introduced by flattening the class into functions. Pinned
   by
   ``TestFixTypeErrorIssue::test_up031_fix_missed_when_future_annotations_shifts_lines``.

## cwd-pinning gap fixed by Task 22a

``_format_python_file`` shells out via ``subprocess.run(["ruff", "format",
str(file_path)], capture_output=True, text=True, timeout=30)``. It originally
had **no** ``cwd=`` pin -- the same dormant gap flagged across every other
extracted fixer's subprocess helper. Task 22a fixed it here too:
``_format_python_file`` now takes a ``project_root: Path`` parameter and
passes it as ``cwd``, threaded from ``fix_type_error_issue``'s newly-added
``project_root: Path`` parameter (this entry point took none before).

## Out of scope: unrelated coverage in the original test file

The original ``tests/test_agents/test_type_error_specialist.py`` also
contains a ``TestStripNonErrorOutput`` class testing
``crackerjack.parsers.factory.strip_non_error_output`` -- a function that
has nothing to do with ``TypeErrorSpecialistAgent``; its own docstring says
it was parked there "to keep all parser-related TypeErrorSpecialist coverage
in one file." That class was **not** ported to ``tests/fixers/
test_type_errors.py`` (it doesn't exercise anything in this module). See
this task's report for a flag to the reviewer: that coverage will be lost
if/when the original agent test file is eventually deleted, and should be
relocated to a parser-specific test file at that point.
"""

from __future__ import annotations

import ast
import logging
import re
import subprocess
import typing as t
from collections.abc import Callable
from pathlib import Path
from typing import cast

from crackerjack.models.issues import FixResult, Issue

logger = logging.getLogger(__name__)


def _read_file(file_path: str | Path) -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def _write_file(file_path: str | Path, content: str) -> bool:
    try:
        Path(file_path).write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


def _format_python_file(file_path: Path, project_root: Path) -> None:
    try:
        result = subprocess.run(
            ["ruff", "format", str(file_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.debug(f"Applied ruff format to {file_path}")
        else:
            logger.warning(
                f"Ruff format warning for {file_path}: {result.stderr.strip()}"
            )
    except Exception as e:
        logger.warning(f"Ruff format failed for {file_path}: {e}")


def _apply_common_fixes(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[str] = []
    new_content = content

    new_content, fix_future = _add_future_annotations(new_content)
    if fix_future:
        fixes.append("Added 'from __future__ import annotations'")

    new_content, fix_typing = _add_typing_imports(new_content, issue)
    if fix_typing:
        fixes.extend(fix_typing)

    new_content, fix_common = _add_common_imports(new_content, issue)
    if fix_common:
        fixes.extend(fix_common)

    return new_content, fixes


def _fix_up031_percent_format(content: str, issue: Issue) -> tuple[str, list[str]]:
    message_lower = issue.message.lower()
    if "up031" not in message_lower:
        return content, []
    if not issue.line_number:
        return content, []

    lines = content.split("\n")
    index = issue.line_number - 1
    if not (0 <= index < len(lines)):
        return content, []

    old_line = lines[index]
    if "%" not in old_line:
        return content, []
    if "# noqa: UP031" in old_line:
        return content, []

    lines[index] = f"{old_line.rstrip()} # noqa: UP031"
    return "\n".join(lines), [
        f"Suppressed UP031 on line {issue.line_number} with noqa annotation"
    ]


def _fix_var_annotated(content: str, issue: Issue) -> tuple[str, list[str]]:
    if "var-annotated" not in issue.message:
        return content, []
    var_match = re.search(
        r'Need type annotation for ["\'](?P<name>\w+)["\']', issue.message
    )
    if not var_match:
        return content, []
    var_name = var_match.group("name")

    lines = content.split("\n")

    candidates: list[int] = []
    if issue.line_number:
        start = max(0, issue.line_number - 21)
        end = min(len(lines), issue.line_number + 20)
        candidates.extend(range(start, end))
    candidates.extend(range(len(lines)))
    seen: set[int] = set()
    index: int | None = None
    for i in candidates:
        if i in seen:
            continue
        seen.add(i)
        if re.match(
            rf"^\s*{re.escape(var_name)}\s*=\s*[^=]", lines[i]
        ) and not re.match(rf"^\s*{re.escape(var_name)}\s*:", lines[i]):
            index = i
            break

    if index is None:
        return content, []

    old_line = lines[index]
    annotation = _infer_annotation_from_rhs(old_line, var_name)
    if annotation is None:
        return content, []

    new_line = re.sub(
        rf"^(\s*)({re.escape(var_name)})(\s*=)",
        rf"\1\2: {annotation}\3",
        old_line,
        count=1,
    )
    if new_line == old_line:
        return content, []

    lines[index] = new_line
    return (
        "\n".join(lines),
        [f"Added type annotation `{annotation}` for `{var_name}` on line {index + 1}"],
    )


def _infer_annotation_from_rhs(line: str, var_name: str) -> str | None:
    rhs_match = re.search(rf"^\s*{re.escape(var_name)}\s*=\s*(.+?)\s*$", line)
    if not rhs_match:
        return None
    rhs = rhs_match.group(1)

    if re.search(r"\b(?:or|else)\s*\{\s*\}", rhs) or re.search(
        r"\bor\s*dict\s*\(", rhs
    ):
        return "dict[str, object]"

    if re.search(r"\b(?:or|else)\s*\[\s*\]", rhs) or re.search(
        r"\bor\s*list\s*\(", rhs
    ):
        return "list[object]"

    return None


def _fix_literal_mismatch(content: str, issue: Issue) -> tuple[str, list[str]]:
    match = _parse_literal_mismatch_message(issue.message)
    if match is None:
        return content, []
    param_name, type_name, new_value = match

    tree = _safe_parse(content)
    if tree is None:
        return content, []

    target_class = _find_class(tree, type_name)
    if target_class is None:
        return content, []

    target_field = _find_literal_field(target_class, param_name)
    if target_field is None:
        return content, []

    existing_values = _collect_existing_literal_values(target_field)
    if existing_values is None or new_value in existing_values:
        return content, []

    return _splice_literal_value(
        content, target_field.annotation, new_value, type_name, param_name
    )


def _parse_literal_mismatch_message(message: str) -> tuple[str, str, str] | None:
    if "incompatible type" not in message or "Literal" not in message:
        return None
    m = re.search(
        r"""Argument\s+["'](?P<param>\w+)["']\s+to\s+["'](?P<type>\w+)["']\s+
            has\s+incompatible\s+type\s+["']Literal\[
            (?P<q>['"])(?P<value>[^'"]+)(?P=q)
            \]""",
        message,
        re.VERBOSE,
    )
    if not m:
        return None
    return m.group("param"), m.group("type"), m.group("value")


def _safe_parse(content: str) -> ast.Module | None:
    try:
        return ast.parse(content)
    except SyntaxError:
        return None


def _find_class(tree: ast.Module, type_name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == type_name:
            return node
    return None


def _find_literal_field(
    target_class: ast.ClassDef, param_name: str
) -> ast.AnnAssign | None:
    for node in target_class.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id != param_name:
            continue
        annotation = node.annotation
        if not isinstance(annotation, ast.Subscript):
            continue

        if not isinstance(annotation.value, ast.Name):
            continue
        if annotation.value.id != "Literal":
            continue
        return node
    return None


def _collect_existing_literal_values(target_field: ast.AnnAssign) -> set[str] | None:
    slice_node = cast(ast.Subscript, target_field.annotation).slice
    if isinstance(slice_node, ast.Tuple):
        return {
            elt.value
            for elt in slice_node.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        }
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return {slice_node.value}
    return None


def _splice_literal_value(
    content: str,
    annotation: ast.expr,
    new_value: str,
    type_name: str,
    param_name: str,
) -> tuple[str, list[str]]:
    slice_node = cast(ast.Subscript, annotation).slice
    if not hasattr(slice_node, "end_lineno") or not hasattr(
        slice_node, "end_col_offset"
    ):
        return content, []

    try:
        slice_text = ast.get_source_segment(content, slice_node) or ""
    except Exception:
        slice_text = ""

    if '"' in slice_text and "'" not in slice_text:
        quote = '"'
    elif "'" in slice_text and '"' not in slice_text:
        quote = "'"
    else:
        quote = "'"

    lines = content.split("\n")
    end_line_idx = cast(int, slice_node.end_lineno) - 1  # type: ignore[attr-defined]
    end_col = cast(int, slice_node.end_col_offset)  # type: ignore[attr-defined]
    if not (0 <= end_line_idx < len(lines)):
        return content, []

    line = lines[end_line_idx]

    prefix = line[:end_col]
    suffix = line[end_col:]
    if prefix.rstrip().endswith(","):
        new_prefix = prefix.rstrip() + f" {quote}{new_value}{quote} "
    else:
        new_prefix = prefix.rstrip() + f", {quote}{new_value}{quote} "

    lines[end_line_idx] = new_prefix + suffix
    new_content = "\n".join(lines)

    return new_content, [
        (
            f"Added '{new_value}' to {type_name}.{param_name} Literal type "
            f"on line {end_line_idx + 1}"
        )
    ]


def _prune_unused_typing_imports(content: str) -> tuple[str, list[str]]:
    lines = content.split("\n")
    updated_lines: list[str] = []
    fixes: list[str] = []

    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)from typing import (.+)$", line)
        if not match:
            updated_lines.append(line)
            continue

        indent, names_text = match.groups()
        import_names = [name.strip() for name in names_text.split(", ") if name.strip()]
        search_space = "\n".join(lines[:index] + lines[index + 1 :])
        kept_names: list[str] = []

        for import_name in import_names:
            base_name = import_name.split(" as ", 1)[0].strip()
            if re.search(rf"\b{re.escape(base_name)}\b", search_space):
                kept_names.append(import_name)
            else:
                fixes.append(f"Removed unused typing import: {base_name}")

        if kept_names:
            updated_lines.append(f"{indent}from typing import {', '.join(kept_names)}")
        else:
            fixes.append("Removed unused typing import block")

    return ("\n".join(updated_lines), fixes)


def _fix_missing_return_types(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[t.Any] = []
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        if re.match("^\\s*def\\s+\\w+\\s*\\([^)]*\\)\\s*:", line) and (
            "->" not in line
            and "async def" not in line
            and any(
                keyword in issue.message.lower()
                for keyword in ("missing", "return", "type")
            )
        ):
            modified = line.rstrip().rstrip(":") + " -> None:"
            if modified != line:
                new_lines.append(modified)
                fixes.append(f"Added return type annotation: {modified[:80]}...")
                continue
        new_lines.append(line)
    return ("\n".join(new_lines), fixes)


def _add_future_annotations(content: str) -> tuple[str, list[str]]:
    if "from __future__ import annotations" in content:
        return (content, [])
    lines = content.split("\n")
    insert_index = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(('"""', "'''")):
            continue
        if stripped.startswith(("import ", "from ")):
            insert_index = i
            break
        if stripped and (not stripped.startswith("#")):
            insert_index = i
            break
    lines.insert(insert_index, "from __future__ import annotations")
    return ("\n".join(lines), ["Added __future__ annotations import"])


def _add_typing_imports(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[t.Any] = []
    new_imports: list[str] = []
    message_lower = issue.message.lower()
    content = _maybe_add_typing_import(
        content,
        new_imports,
        fixes,
        trigger="any" in message_lower and "not defined" in message_lower,
        import_names=["Any"],
    )
    content = _maybe_add_typing_import(
        content,
        new_imports,
        fixes,
        trigger="optional" in message_lower or "None" in message_lower,
        import_names=["Optional"],
    )
    content = _maybe_add_typing_import(
        content,
        new_imports,
        fixes,
        trigger="union" in message_lower or " | " in issue.message,
        import_names=["Union"],
    )
    content = _maybe_add_typing_import(
        content,
        new_imports,
        fixes,
        trigger="list[" in message_lower or "dict[" in message_lower,
        import_names=["List", "Dict"],
    )
    if new_imports:
        lines = content.split("\n")
        insert_index = 0
        for i, line in enumerate(lines):
            if "from __future__ import annotations" in line:
                insert_index = i + 1
                break
            elif line.strip().startswith(("import", "from")) and insert_index == 0:
                insert_index = i
        typing_names: list[str] = []
        for new_import in new_imports:
            typing_names.extend(
                name.strip()
                for name in new_import.replace("from typing import ", "", 1).split(", ")
                if name.strip()
            )
        combined_import = f"from typing import {', '.join(dict.fromkeys(typing_names))}"
        lines.insert(insert_index, combined_import)
        fixes.append(f"Added import: {combined_import}")
        return ("\n".join(lines), fixes)
    return (content, fixes)


def _maybe_add_typing_import(
    content: str,
    new_imports: list[str],
    fixes: list[str],
    *,
    trigger: bool,
    import_names: list[str],
) -> str:
    if not trigger:
        return content

    if "from typing import" in content:
        if not all(name in content for name in import_names):
            replacement = ", ".join(import_names)
            content = re.sub(
                "(from typing import [^\\n]+)", f"\\1, {replacement}", content
            )
            fixes.append(f"Added {replacement} to typing imports")
    else:
        new_imports.append(f"from typing import {', '.join(import_names)}")

    return content


def _add_common_imports(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[str] = []
    message_lower = issue.message.lower()

    import_specs = [
        ("operator" in message_lower, "import operator", "Added operator import"),
        (
            "suppress" in message_lower,
            "from contextlib import suppress",
            "Added suppress import",
        ),
    ]

    for trigger, import_line, fix_message in import_specs:
        if not trigger or import_line in content:
            continue
        content = _insert_import_line(content, import_line)
        fixes.append(fix_message)

    return (content, fixes)


def _fix_suppress_tuple_arg_type(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[str] = []
    message_lower = issue.message.lower()
    if "suppress" not in message_lower:
        return (content, fixes)

    new_content = re.sub(
        r"with suppress\(\(([^)]+)\)\)",
        lambda match: f"with suppress({match.group(1)})",
        content,
        count=1,
    )
    if new_content != content:
        fixes.append("Flattened suppress() exception tuple")
    return (new_content, fixes)


def _insert_import_line(content: str, import_line: str) -> str:
    lines = content.split("\n")
    insert_index = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(('"""', "'''")):
            continue
        if stripped.startswith(("import ", "from ")):
            insert_index = i + 1
            continue
        if stripped and not stripped.startswith("#"):
            insert_index = i
            break
    lines.insert(insert_index, import_line)
    return "\n".join(lines)


def _infer_and_add_return_types(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[str] = []
    message_lower = issue.message.lower()
    if not any(kw in message_lower for kw in ("missing return", "return type", "->")):
        return (content, fixes)
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return (content, fixes)
    lines = content.split("\n")
    modified_lines = lines.copy()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                continue
            if issue.line_number and abs(node.lineno - issue.line_number) > 5:
                continue
            inferred_type = _infer_return_type_from_body(node, content)
            if inferred_type:
                line_idx = node.lineno - 1
                if 0 <= line_idx < len(modified_lines):
                    old_line = modified_lines[line_idx]
                    colon_pos = old_line.rfind(":")
                    if colon_pos > 0:
                        if old_line.rstrip().endswith(":"):
                            new_line = (
                                old_line[:colon_pos].rstrip() + f" -> {inferred_type}:"
                            )
                            if "\n" not in old_line[colon_pos + 1 :]:
                                modified_lines[line_idx] = new_line
                                fixes.append(
                                    f"Inferred return type '{inferred_type}' for {node.name}() at line {node.lineno}"
                                )
    return ("\n".join(modified_lines), fixes)


def _infer_return_type_from_body(
    node: ast.FunctionDef | ast.AsyncFunctionDef, content: str
) -> str | None:
    # `content` is accepted but unused, matching the original method's
    # signature verbatim -- see the module docstring's "Preserved quirks"
    # section, item 1.
    return_types: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value:
            inferred = _infer_type_from_expr(child.value)
            if inferred:
                return_types.add(inferred)
        if isinstance(child, ast.Yield):
            if child.value:
                inner_type = _infer_type_from_expr(child.value)
                return_types.add(f"Iterator[{inner_type or 'Any'}]")
            else:
                return_types.add("Iterator[Any]")
        if isinstance(child, ast.YieldFrom):
            return_types.add("Iterator[Any]")
    if not return_types:
        return "None"
    if len(return_types) == 1:
        return return_types.pop()
    return f"Union[{', '.join(sorted(return_types))}]"


def _infer_type_from_expr(expr: ast.expr) -> str | None:
    handlers = {
        ast.Constant: _infer_constant_type,
        ast.List: _infer_list_type,
        ast.Dict: _infer_dict_type,
        ast.Set: _infer_set_type,
        ast.Tuple: _infer_tuple_type,
        ast.Call: _infer_call_type,
        ast.BinOp: _infer_binop_type,
        ast.Compare: lambda e: "bool",
        ast.BoolOp: lambda e: "bool",
        ast.UnaryOp: _infer_unaryop_type,
    }
    handler = cast("Callable[[ast.expr], str] | None", handlers.get(type(expr)))
    return handler(expr) if handler else None


def _infer_constant_type(expr: ast.Constant) -> str:
    type_map = {
        type(None): "None",
        bool: "bool",
        int: "int",
        float: "float",
        str: "str",
        bytes: "bytes",
    }
    return type_map.get(type(expr.value)) or type(expr.value).__name__  # type: ignore[call-overload,return-value]


def _infer_list_type(expr: ast.List) -> str:
    if expr.elts:
        inner_types = {_infer_type_from_expr(e) or "Any" for e in expr.elts}
        if len(inner_types) == 1:
            return f"list[{inner_types.pop()}]"
    return "list[Any]"


def _infer_dict_type(expr: ast.Dict) -> str:
    if expr.keys and expr.values:
        key_types = {_infer_type_from_expr(k) or "Any" for k in expr.keys if k}
        val_types = {_infer_type_from_expr(v) or "Any" for v in expr.values}
        kt = key_types.pop() if len(key_types) == 1 else "Any"
        vt = val_types.pop() if len(val_types) == 1 else "Any"
        return f"dict[{kt}, {vt}]"
    return "dict[Any, Any]"


def _infer_set_type(expr: ast.Set) -> str:
    if expr.elts:
        inner_types = {_infer_type_from_expr(e) or "Any" for e in expr.elts}
        if len(inner_types) == 1:
            return f"set[{inner_types.pop()}]"
    return "set[Any]"


def _infer_tuple_type(expr: ast.Tuple) -> str:
    if expr.elts:
        inner_types = [_infer_type_from_expr(e) or "Any" for e in expr.elts]
        return f"tuple[{', '.join(inner_types)}]"
    return "tuple[()]"


def _infer_call_type(expr: ast.Call) -> str | None:
    if isinstance(expr.func, ast.Name):
        factory_returns = {
            "list": "list[Any]",
            "dict": "dict[Any, Any]",
            "set": "set[Any]",
            "tuple": "tuple[Any, ...]",
            "str": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "frozenset": "frozenset[Any]",
            "range": "range",
        }
        return factory_returns.get(expr.func.id)
    return None


def _infer_binop_type(expr: ast.BinOp) -> str | None:
    left_type = _infer_type_from_expr(expr.left)
    return left_type if left_type in ("str", "int", "float") else None


def _infer_unaryop_type(expr: ast.UnaryOp) -> str | None:
    return (
        "bool" if isinstance(expr.op, ast.Not) else _infer_type_from_expr(expr.operand)
    )


def _fix_complex_generic_types(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[str] = []
    message_lower = issue.message.lower()
    if not any(
        kw in message_lower for kw in ("generic", "subscript", "type arguments", "[")
    ):
        return (content, fixes)
    has_future_annotations = "from __future__ import annotations" in content
    lines = content.split("\n")
    modified_lines = lines.copy()
    for i, line in enumerate(lines):
        if has_future_annotations:
            new_line = re.sub("\\bList\\[", "list[", line)
            new_line = re.sub("\\bDict\\[", "dict[", new_line)
            new_line = re.sub("\\bSet\\[", "set[", new_line)
            new_line = re.sub("\\bTuple\\[", "tuple[", new_line)
            new_line = re.sub("\\bFrozenSet\\[", "frozenset[", new_line)
            if new_line != line:
                modified_lines[i] = new_line
                fixes.append(f"Modernized generic syntax on line {i + 1}")
    return ("\n".join(modified_lines), fixes)


def _detect_and_fix_protocol_patterns(
    content: str, issue: Issue
) -> tuple[str, list[str]]:
    fixes: list[str] = []
    message_lower = issue.message.lower()
    if not any(
        kw in message_lower for kw in ("protocol", "compatible", "structural", "duck")
    ):
        return (content, fixes)
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return (content, fixes)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            method_count = sum(
                1
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            attr_count = sum(1 for n in node.body if isinstance(n, ast.AnnAssign))
            if method_count >= 2 and attr_count <= 1:
                inherits_protocol = any(
                    isinstance(base, ast.Name)
                    and base.id == "Protocol"
                    or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
                    for base in node.bases
                )
                if not inherits_protocol and (not node.bases):
                    fixes.append(
                        f"Class '{node.name}' may benefit from Protocol (structural subtyping) - has {method_count} methods"
                    )
    return (content, fixes)


def _is_self_type_issue(message: str) -> bool:
    keywords = ("return type", "self", "instance", "same type")
    return any(kw in message.lower() for kw in keywords)


def _collect_class_names(tree: ast.AST) -> set[str]:
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}


def _should_skip_method(item: ast.FunctionDef) -> bool:
    if item.name.startswith("_") and (
        not item.name.startswith(("__enter__", "__exit__"))
    ):
        return True
    return any(
        isinstance(d, ast.Name) and d.id == "staticmethod" for d in item.decorator_list
    )


def _get_return_type_name(returns: ast.expr) -> str | None:
    if isinstance(returns, ast.Name):
        return returns.id
    if isinstance(returns, ast.Constant):
        return str(returns.value)
    return None


def _try_convert_to_self(
    item: ast.FunctionDef, class_name: str, lines: list[str]
) -> dict[str, t.Any] | None:
    if not item.returns:
        return None
    return_type = _get_return_type_name(item.returns)
    if return_type != class_name:
        return None
    if isinstance(item.returns, ast.Name) and item.returns.id == "Self":
        return None
    line_idx = item.lineno - 1
    if not 0 <= line_idx < len(lines):
        return None
    old_line = lines[line_idx]
    new_line = re.sub(f"\\b-> {class_name}\\b", "-> Self", old_line)
    if new_line == old_line:
        return None
    return {"line_idx": line_idx, "new_line": new_line}


def _process_class_methods(
    node: ast.ClassDef,
    class_names: set[str],
    lines: list[str],
    fixes: list[str],
    needs_import: bool,
) -> bool:
    # `class_names` is accepted but unused, matching the original method's
    # signature verbatim -- see the module docstring's "Preserved quirks"
    # section, item 2.
    class_name = node.name
    for item in node.body:
        if not isinstance(item, ast.FunctionDef):
            continue
        if _should_skip_method(item):
            continue
        result = _try_convert_to_self(item, class_name, lines)
        if result:
            lines[result["line_idx"]] = result["new_line"]
            fixes.append(
                f"Changed return type to 'Self' for {class_name}.{item.name}()"
            )
            needs_import = True
    return needs_import


def _add_self_import(lines: list[str], fixes: list[str]) -> None:
    for i, line in enumerate(lines):
        if "from typing import" in line and "Self" not in line:
            lines[i] = re.sub("(from typing import [^\\n]+)", "\\1, Self", line)
            fixes.append("Added Self to typing imports")
            break


def _add_self_type_for_methods(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[t.Any] = []
    if not _is_self_type_issue(issue.message):
        return (content, fixes)
    has_self_import = "from typing import Self" in content
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return (content, fixes)
    lines = content.split("\n")
    modified_lines = lines.copy()
    needs_self_import = False
    class_names = _collect_class_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            needs_self_import = _process_class_methods(
                node, class_names, modified_lines, fixes, needs_self_import
            )
    if needs_self_import and (not has_self_import):
        _add_self_import(modified_lines, fixes)
    return ("\n".join(modified_lines), fixes)


def _split_union_types(inner: str) -> list[str]:
    types = []
    current = ""
    depth = 0
    for char in inner:
        if char == "[":
            depth += 1
            current += char
        elif char == "]":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            if current.strip():
                types.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        types.append(current.strip())
    return types


def _fix_optional_union_types(content: str, issue: Issue) -> tuple[str, list[str]]:
    fixes: list[str] = []
    message_lower = issue.message.lower()
    if not any(kw in message_lower for kw in ("optional", "union", "none")):
        return (content, fixes)
    has_future_annotations = "from __future__ import annotations" in content
    if not has_future_annotations:
        return (content, fixes)
    lines = content.split("\n")
    modified_lines = lines.copy()
    for i, line in enumerate(lines):
        new_line = line
        optional_pattern = "Optional\\[([^\\]]+(?:\\[[^\\]]*\\][^\\]]*)*)\\]"
        while re.search(optional_pattern, new_line):
            match = re.search(optional_pattern, new_line)
            if match:
                inner_type = match.group(1)
                new_line = (
                    new_line[: match.start()]
                    + f"{inner_type} | None"
                    + new_line[match.end() :]
                )
                fixes.append(
                    f"Converted Optional[{inner_type}] to {inner_type} | None on line {i + 1}"
                )
        union_pattern = "Union\\[([^\\]]+(?:\\[[^\\]]*\\][^\\]]*)*)\\]"
        while re.search(union_pattern, new_line):
            match = re.search(union_pattern, new_line)
            if match:
                inner = match.group(1)
                types = _split_union_types(inner)
                if 2 <= len(types) <= 5:
                    union_syntax = " | ".join(t.strip() for t in types)
                    new_line = (
                        new_line[: match.start()]
                        + union_syntax
                        + new_line[match.end() :]
                    )
                    fixes.append(
                        f"Converted Union[{inner}] to {union_syntax} on line {i + 1}"
                    )
                else:
                    break
        if new_line != line:
            modified_lines[i] = new_line
    return ("\n".join(modified_lines), fixes)


def _fix_invalid_assignment_paired_ty_ignore(
    content: str, issue: Issue
) -> tuple[str, list[str]]:
    msg = issue.message
    if "invalid-assignment" not in msg:
        return content, []
    if issue.line_number is None:
        return content, []
    if not issue.file_path:
        return content, []

    lines = content.split("\n")
    idx = issue.line_number - 1
    if not (0 <= idx < len(lines)):
        return content, []

    line = lines[idx]

    if "# ty: ignore" in line:
        return content, []

    if "# type: ignore" not in line:
        return content, []

    lines[idx] = f"{line.rstrip()} # ty: ignore[invalid-assignment]"
    return (
        "\n".join(lines),
        [f"Added # ty: ignore[invalid-assignment] on line {issue.line_number}"],
    )


def _fix_invalid_typed_dict_subscript(
    content: str, issue: Issue
) -> tuple[str, list[str]]:
    msg = issue.message
    if "invalid-assignment" not in msg:
        return content, []
    if "is not assignable to" not in msg:
        return content, []
    if issue.line_number is None:
        return content, []
    if not issue.file_path:
        return content, []

    lines = content.split("\n")
    idx = issue.line_number - 1
    if not (0 <= idx < len(lines)):
        return content, []

    line = lines[idx]

    if "cast(" in line:
        return content, []
    m = re.match(
        r"^(\s*)(?P<var>[A-Za-z_]\w*)\s*:\s*(?P<typ>[^=]+?)\s*=\s*(?P<rhs>.+)$",
        line.rstrip(),
    )
    if not m or ".get(" not in m.group("rhs"):
        return content, []

    indent = m.group(1)
    var_name = m.group("var")
    typ = m.group("typ").strip()
    rhs = m.group("rhs").strip()
    new_line = f"{indent}{var_name}: {typ} = cast({typ}, {rhs})"
    lines[idx] = new_line
    return (
        "\n".join(lines),
        [f"Wrapped .get() result in cast() on line {issue.line_number}"],
    )


def _fix_unresolved_import_with_ty_ignore(
    content: str, issue: Issue
) -> tuple[str, list[str]]:
    msg = issue.message
    if "unresolved-import" not in msg:
        return content, []
    if issue.line_number is None:
        return content, []
    if not issue.file_path:
        return content, []

    lines = content.split("\n")
    idx = issue.line_number - 1
    if not (0 <= idx < len(lines)):
        return content, []

    line = lines[idx]
    if "# ty: ignore" in line:
        return content, []

    if "workspace_tools" in (issue.file_path or ""):
        return content, []

    # Both branches are byte-for-byte identical in the original -- preserved
    # verbatim, not simplified. See the module docstring's "Preserved
    # quirks" section, item 4.
    if "# type: ignore" in line:
        lines[idx] = f"{line.rstrip()} # ty: ignore[unresolved-import]"
    else:
        lines[idx] = f"{line.rstrip()} # ty: ignore[unresolved-import]"
    return (
        "\n".join(lines),
        [
            (
                f"Added # ty: ignore[unresolved-import] on line "
                f"{issue.line_number} (intentionally-absent module)"
            )
        ],
    )


async def apply_type_fixes(content: str, issue: Issue) -> tuple[str, list[str]]:
    """Run the full type-error fix pipeline over ``content`` for ``issue``.

    Mirrors the original ``TypeErrorSpecialistAgent._apply_type_fixes``
    exactly, including step order (order matters: later steps see the
    output of earlier ones). ``async`` with no internal ``await`` --
    preserved verbatim, see the module docstring's "Preserved quirks"
    section, item 5.
    """
    fixes: list[t.Any] = []
    new_content = content

    def run_fix(
        current: str,
        fixer: t.Callable[..., tuple[str, list[str]]],
    ) -> str:
        updated, fix_messages = fixer(current, issue)
        if fix_messages:
            fixes.extend(fix_messages)
        return updated

    new_content = run_fix(new_content, _fix_missing_return_types)
    new_content = run_fix(new_content, _apply_common_fixes)
    new_content = run_fix(new_content, _fix_suppress_tuple_arg_type)
    new_content = run_fix(new_content, _infer_and_add_return_types)
    new_content = run_fix(new_content, _fix_complex_generic_types)
    new_content = run_fix(new_content, _detect_and_fix_protocol_patterns)
    new_content = run_fix(new_content, _add_self_type_for_methods)
    new_content = run_fix(new_content, _fix_optional_union_types)

    prune_content, prune_fixes = _prune_unused_typing_imports(new_content)
    if prune_fixes:
        new_content = prune_content
        fixes.extend(prune_fixes)

    new_content = run_fix(new_content, _fix_up031_percent_format)
    new_content = run_fix(new_content, _fix_var_annotated)
    new_content = run_fix(new_content, _fix_literal_mismatch)

    new_content = run_fix(new_content, _fix_invalid_assignment_paired_ty_ignore)
    new_content = run_fix(new_content, _fix_invalid_typed_dict_subscript)
    new_content = run_fix(new_content, _fix_unresolved_import_with_ty_ignore)

    return (new_content, fixes)


async def fix_type_error_issue(issue: Issue, project_root: Path) -> FixResult:
    """Entry point mirroring the original ``analyze_and_fix``.

    Reads the file named by ``issue.file_path``, runs ``apply_type_fixes``,
    writes the result back, and (for ``.py`` files) applies ``ruff format``
    via ``_format_python_file``. ``async`` with no internal ``await`` --
    preserved verbatim, see the module docstring's "Preserved quirks"
    section, item 5.
    """
    if issue.file_path is None:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path provided"],
        )
    file_path = Path(issue.file_path)
    if not file_path.exists():
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"File not found: {file_path}"],
        )
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Could not read file content"],
        )
    new_content, fixes_applied = await apply_type_fixes(content, issue)
    if new_content == content:
        return FixResult(
            success=False, confidence=0.0, remaining_issues=["No changes applied"]
        )
    if not _write_file(file_path, new_content):
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write file: {file_path}"],
        )
    if file_path.suffix == ".py":
        _format_python_file(file_path, project_root)
    return FixResult(
        success=True,
        confidence=0.7,
        fixes_applied=fixes_applied,
        files_modified=[file_path],  # type: ignore
    )


__all__ = [
    "apply_type_fixes",
    "fix_type_error_issue",
]
