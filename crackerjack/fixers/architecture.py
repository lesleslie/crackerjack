r"""Deterministic type-error fixer and FixPlan/ChangeSpec applicator.

Extracted from ``crackerjack.agents.architect_agent.ArchitectAgent`` (729
lines), which -- unlike ``SecurityAgent``/``DocumentationAgent`` -- mixes two
genuinely different kinds of logic in one class:

1. Real, self-contained deterministic fixing for ``IssueType.TYPE_ERROR``
   (regex/AST-based content transforms: adding typing imports, ``any`` ->
   ``Any``, missing return annotations, an ``await`` heuristic, plus a
   no-op ``Path``/``str`` conversion stub -- see "Preserved quirks" below)
   plus its own ``FixPlan``/``ChangeSpec`` applicator (``execute_fix_plan``).
2. Pure coordinator/dispatch plumbing that either (a) hands the ``Issue``
   off to a different ``SubAgent`` instance (``RefactoringAgent``,
   ``FormattingAgent``, ``ImportOptimizationAgent``, ``SecurityAgent`` --
   held on ``self`` and constructed in ``__init__``) or (b) returns a
   dict describing a plan without performing any fix, for the (now-removed)
   coordinator to act on.

Only (1) is ported here. All of (2) is dropped, per this task's brief:

- ``plan_before_action``/``_needs_external_specialist``/
  ``_get_specialist_plan``/``_get_internal_plan`` and their string-building
  helpers (``_get_specialist_approach``, ``_get_internal_approach``,
  ``_get_recommended_patterns``, ``_get_cached_patterns_for_issue``,
  ``_analyze_dependencies``, ``_identify_risks``, ``_get_validation_steps``)
  -- these only ever built a ``dict[str, Any]`` "plan" describing what
  *should* happen (including the ``{"strategy": "external_specialist_guided",
  "specialist": "crackerjack-architect"}`` dict for ``COMPLEXITY``/
  ``DRY_VIOLATION`` issues) for a coordinator to interpret. With the
  coordinator gone, none of this dict-construction does any fixing on its
  own -- it has zero independent value. ``_get_cached_patterns_for_issue``
  additionally depended on ``ProactiveAgent.get_cached_patterns()``
  (skills-tracker/memory plumbing), out of scope per this task's import
  restrictions.
- ``execute_with_plan`` -- explicitly named for dropping in the brief: it
  is the method that inspects ``plan["strategy"]`` and refuses to act
  (returns a failure ``FixResult``) when it sees
  ``"external_specialist_guided"``. Its other branches were one-line
  dispatches by ``issue.type`` to ``_fix_type_error_with_plan`` (kept here,
  see below), ``_fix_dependency_with_plan``, ``_fix_documentation_with_plan``,
  and ``_fix_test_organization_with_plan``.
- ``analyze_and_fix`` -- dispatches by ``issue.type`` to
  ``self._refactoring_agent``/``self._formatting_agent``/
  ``self._import_agent``/``self._security_agent`` (other ``SubAgent``
  instances) or falls back to ``ProactiveAgent.analyze_and_fix_proactively``.
  Pure coordinator plumbing, zero logic of its own.
- ``__init__``, ``get_supported_types``, ``can_handle`` -- standard
  ``SubAgent``/coordinator dispatch plumbing (decided *whether* and *how
  confidently* this agent should run for a given ``Issue``); same treatment
  as every other ``crackerjack/fixers/*.py`` extraction so far.
- ``agent_registry.register(ArchitectAgent)`` -- registry plumbing.
- ``self.log(...)`` calls throughout -- ``SubAgent.log`` is a no-op ``pass``
  on the base class, so these calls had no observable effect; dropped.

## ``DEPENDENCY``/``DOCUMENTATION``: confirmed to be unimplemented stubs, not fixes

The task brief lists ``TYPE_ERROR``/``DEPENDENCY``/``DOCUMENTATION`` as the
three issue types whose "fix methods" should be extracted, naming
``_apply_type_error_fixes``/``_fix_missing_typing_imports`` (both
``TYPE_ERROR``) as confirmed examples. Reading the full 729-line source
shows the ``DEPENDENCY``/``DOCUMENTATION`` handlers (and
``_fix_test_organization_with_plan``, for the file's third supported type)
are **not** deterministic fixes at all -- each is a two-line stub that logs
"not yet implemented" and unconditionally returns
``FixResult(success=False, ...)``:

```python
async def _fix_dependency_with_plan(self, issue, plan) -> FixResult:
    self.log(f"Dependency fixing not yet implemented: {issue.message}")
    return FixResult(success=False, confidence=0.0,
                      remaining_issues=[f"Dependency issue: {issue.message}"])
```

There is no branching, no content transform, nothing to preserve --
porting this as a "plain function" would mean inventing a function whose
entire behavior is "always fail with a templated message," which provides
no value and isn't a fix. Per the same reasoning already applied to the
dropped ``external_specialist_guided`` branch ("zero independent value"),
these three stubs are **not ported**. Real ``DEPENDENCY`` fixing lives in
``crackerjack/fixers/dependency.py`` (Task 17, extracted from
``DependencyAgent``); real ``DOCUMENTATION`` fixing lives in
``crackerjack/fixers/documentation.py`` (extracted from
``DocumentationAgent``, a different class from ``ArchitectAgent``). See
this task's report for the full "Concerns for reviewer" note.

## ``execute_fix_plan`` is kept, but its cross-agent branches are dropped

Per the plan's precedent (``ArchitectAgent`` is one of four agent classes --
alongside ``SecurityAgent``, ``DocumentationAgent``, and ``FormattingAgent``
-- with its own ``FixPlan``/``ChangeSpec`` applicator), ``execute_fix_plan``
and its real logic (``_apply_plan_changes``, ``_find_matching_line``) are
kept. However the original method special-cased three ``plan.issue_type``
strings by handing the whole plan to a *different* agent's
``execute_fix_plan``, with zero logic of its own:

- ``"COMPLEXITY"`` -> ``return await self._refactoring_agent.execute_fix_plan(plan)``
  (100% delegation, no direct-apply attempt at all).
- ``"SECURITY"`` -> ``return await self._security_agent.execute_fix_plan(plan)``
  (100% delegation, no direct-apply attempt at all).
- ``"FORMATTING"`` -> try ``_apply_plan_changes(plan)`` first, then (only on
  failure) ``return await self._formatting_agent.execute_fix_plan(plan)``.

Since ``RefactoringAgent``/``SecurityAgent``/``FormattingAgent`` are
``SubAgent`` instances built in the now-dropped ``__init__``, and each has
already been independently extracted as its own self-contained
``crackerjack/fixers/refactoring.py``/``security.py``/``formatting.py``
(each with its own ``execute_fix_plan``), these three special cases are
dropped here. The generic fallback path already used by the original code
for every *other* ``issue_type`` (``return await self._apply_plan_changes(plan)``)
now handles ``"COMPLEXITY"``/``"SECURITY"``/``"FORMATTING"`` too -- the same
plain ChangeSpec-application logic, just without a second, agent-specific
attempt when the first application fails. Callers that need
``COMPLEXITY``/``SECURITY``/``FORMATTING`` ``FixPlan`` routing with
agent-specific fallback should call ``crackerjack.fixers.refactoring``/
``security``/``formatting``'s own ``execute_fix_plan`` directly for those
issue types -- this module no longer performs that routing on their behalf,
matching the drop of ``analyze_and_fix``'s equivalent cross-agent dispatch.

``"TYPE_ERROR"`` keeps its special case, rewired rather than dropped: the
original tried ``_apply_plan_changes(plan)`` first, and on failure built an
``Issue`` plus a hardcoded ``{"strategy": "internal_pattern_based",
"approach": "add_type_annotations"}`` plan dict and called
``self.execute_with_plan(issue, plan_dict)`` -- which (since the strategy is
never ``"external_specialist_guided"`` and ``issue.type`` is always
``TYPE_ERROR`` at this call site) always resolved to
``self._fix_type_error_with_plan(issue, plan)``. That one real,
self-contained fixer (kept below as ``fix_type_error_with_plan``) is called
directly instead of through the now-dropped router, preserving the same
observable fallback behavior without resurrecting ``execute_with_plan``.

## Preserved quirks/bugs (not "fixed" -- see CLAUDE.md Rule 7)

1. **``_fix_path_str_conversion`` is a permanent no-op.** Its body is:
   ``if "expected str" in error_message.lower() or "path" in
   error_message.lower(): pass`` followed by ``return content`` --
   unconditionally, regardless of whether the ``if`` matched. No matter what
   ``error_message``/``content`` are, the function always returns
   ``content`` unchanged. Confirmed by direct inspection and pinned by
   ``TestFixPathStrConversion`` in ``tests/fixers/test_architecture.py``
   (kept named identically, ``_fix_path_str_conversion``, for anyone
   diffing against the original).
2. **``_add_await_keyword`` always produces syntactically invalid output
   for every real match -- this is a second, more significant preserved
   bug.** The only lines it ever touches are ones matching
   ``"=" in line`` (an assignment-shaped guard) *and* one of the async call
   patterns (``\w+\.async_\w+\(`` / ``\w+\.start\(``). For those lines it
   splices ``"await "`` in at the *start* of the statement (right after
   indentation) rather than immediately before the matched call:
   ``result = obj.start()`` becomes ``await result = obj.start()`` (invalid
   Python -- ``await`` before an assignment target), not the intended
   ``result = await obj.start()``. Since the ``"=" in line`` guard is a
   hard requirement for the branch to fire at all, this is not an edge
   case: it is the *only* shape of input this fixer ever acts on, so it
   never once produces valid output. Preserved verbatim, not "fixed" --
   per Task 14's precedent, a fixer that reliably breaks the files it
   touches is a Critical-severity preserved quirk, not a Minor one. Pinned
   by ``TestAddAwaitKeyword`` in ``tests/fixers/test_architecture.py``.
3. ``fix_type_error_with_plan``'s ``plan: dict[str, t.Any]`` parameter is
   accepted but never read in the body (mirrors the original
   ``_fix_type_error_with_plan``) -- preserved verbatim rather than dropped,
   matching the precedent from ``crackerjack/fixers/type_errors.py`` for
   signature-preserving unused parameters (this function is also the
   rewired fallback target inside ``execute_fix_plan``, so keeping its
   original call shape avoids any ambiguity about what changed). Pinned by
   ``TestFixTypeErrorWithPlan::test_plan_argument_is_accepted_but_unused``.
4. ``execute_fix_plan``'s ``TYPE_ERROR`` fallback builds
   ``severity=plan.changes[0].line_range[0] > 30 and Priority.HIGH or
   Priority.MEDIUM`` -- the classic Python "and/or" pseudo-ternary. This
   works correctly here only because every ``Priority`` enum member is
   truthy (so ``... and Priority.HIGH`` evaluates to ``Priority.HIGH``
   itself, not ``True``, when the left side is true), but it is an unusual
   way to write ``Priority.HIGH if ... else Priority.MEDIUM``. Preserved
   verbatim, not rewritten to an explicit ternary. Pinned by
   ``TestExecuteFixPlan::test_type_error_fallback_severity_is_high_past_line_30``.
5. ``_apply_plan_changes``/``_find_matching_line`` (the fuzzy line-drift
   recovery in the ``ChangeSpec`` applicator) are ported unchanged,
   including the diagnostic ``logger.debug(...)`` calls on mismatch (these
   are real ``logging`` module calls, not the no-op ``SubAgent.log``, so
   they are kept).

``AgentContext``-specific file I/O (path-traversal checks, file-size cap,
``wrap_long_lines`` post-processing which itself imports from the
to-be-removed ``crackerjack.ai_fix`` package) is replaced with direct
``pathlib.Path`` reads/writes via ``_read_file``/``_write_file`` below (same
helpers, byte-for-byte, as every other module in this package). Real file
I/O is still performed; only the framework wrapper around it is gone.
Likewise the async, cache-backed ``self._read_file_context`` (used only by
``_apply_plan_changes``) is replaced with a direct synchronous read via
``pathlib.Path.read_text`` inline in ``_apply_plan_changes``, matching
``security.py``'s treatment of the same ``FileContextReader``-backed
helper (kept as a plain ``try``/``except`` so the original's
``f"Could not read file: {e}"`` error message, with the real exception
text, is preserved rather than replaced with a generic message).
"""

from __future__ import annotations

import ast
import logging
import re
import typing as t
from pathlib import Path

from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import FixResult, Issue, IssueType, Priority

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


# ---------------------------------------------------------------------------
# TYPE_ERROR content-transform pipeline
# (was ArchitectAgent._apply_type_error_fixes and its helpers)
# ---------------------------------------------------------------------------


def apply_type_error_fixes(content: str, error_message: str) -> tuple[str, list[str]]:
    fixes_applied: list[str] = []
    fixed_content = content
    fixed_content, new_fixes = _fix_missing_typing_imports(
        fixed_content, error_message, content
    )
    fixes_applied.extend(new_fixes)
    fixed_content, new_fixes = _fix_any_builtin_type(fixed_content, error_message)
    fixes_applied.extend(new_fixes)
    fixed_content, new_fixes = _fix_missing_annotations_type(
        fixed_content, error_message
    )
    fixes_applied.extend(new_fixes)
    fixed_content, new_fixes = _fix_path_str_type_conversion(
        fixed_content, error_message
    )
    fixes_applied.extend(new_fixes)
    fixed_content, new_fixes = _fix_missing_await(fixed_content, error_message)
    fixes_applied.extend(new_fixes)
    return (fixed_content, fixes_applied)


def _fix_missing_typing_imports(
    content: str, error_message: str, original_content: str
) -> tuple[str, list[str]]:
    imports_needed = []
    if re.search("\\bAny\\b", error_message):
        imports_needed.append("Any")
    if re.search("\\bList\\b", error_message):
        imports_needed.append("List")
    if re.search("\\bDict\\b", error_message):
        imports_needed.append("Dict")
    if re.search("\\bOptional\\b", error_message):
        imports_needed.append("Optional")
    if re.search("\\bUnion\\b", error_message):
        imports_needed.append("Union")
    if not imports_needed:
        return (content, [])
    fixed_content = _add_typing_imports(content, imports_needed)
    if fixed_content != original_content:
        return (
            fixed_content,
            [f"Added typing imports: {', '.join(imports_needed)}"],
        )
    return (content, [])


def _fix_any_builtin_type(content: str, error_message: str) -> tuple[str, list[str]]:
    if "builtin" in error_message.lower() and "any" in error_message.lower():
        new_content = _fix_any_builtin(content)
        if new_content != content:
            return (new_content, ["Fixed `any` → `Any` in type annotations"])
    return (content, [])


def _fix_missing_annotations_type(
    content: str, error_message: str
) -> tuple[str, list[str]]:
    if (
        "annotation" in error_message.lower()
        or "has no attribute" in error_message.lower()
    ):
        new_content = _add_missing_annotations(content, error_message)
        if new_content != content:
            return (new_content, ["Added missing type annotations"])
    return (content, [])


def _fix_path_str_type_conversion(
    content: str, error_message: str
) -> tuple[str, list[str]]:
    if "path" in error_message.lower() and "str" in error_message.lower():
        new_content = _fix_path_str_conversion(content, error_message)
        if new_content != content:
            return (new_content, ["Fixed Path/str type conversion"])
    return (content, [])


def _fix_missing_await(content: str, error_message: str) -> tuple[str, list[str]]:
    if "await" in error_message.lower() or "coroutine" in error_message.lower():
        new_content = _add_await_keyword(content)
        if new_content != content:
            return (new_content, ["Added `await` keyword before async calls"])
    return (content, [])


def _add_typing_imports(content: str, imports_needed: list[str]) -> str:
    lines = content.splitlines(keepends=True)
    typing_imports_to_add = set(imports_needed)
    typing_import_idx, existing_typing_imports = _find_existing_typing_imports(
        lines, imports_needed
    )
    typing_imports_to_add -= existing_typing_imports
    if not typing_imports_to_add:
        return content
    import_line = f"from typing import {', '.join(sorted(typing_imports_to_add))}\n"
    if typing_import_idx is not None:
        lines = _merge_existing_imports(lines, typing_import_idx, typing_imports_to_add)
    else:
        insert_idx = _find_import_insertion_point(lines)
        lines.insert(insert_idx, import_line)
    return "".join(lines)


def _find_existing_typing_imports(
    lines: list[str], imports_needed: list[str]
) -> tuple[int | None, set[str]]:
    typing_import_idx = None
    existing_typing_imports = set()
    for i, line in enumerate(lines):
        if i < 2 and line.startswith(("#!", "# -*-")):
            continue
        if i < 10 and line.strip().startswith('"""'):
            i = _skip_docstring(lines, i)
            continue
        if line.strip().startswith("from typing import"):
            typing_import_idx = i
            match = re.search("from typing import (.+)", line)
            if match:
                existing_imports_str = match.group(1)
                for imp in imports_needed:
                    if re.search(f"\\b{imp}\\b", existing_imports_str):
                        existing_typing_imports.add(imp)
            break
        if line.strip() and (not line.strip().startswith("#")):
            if not line.strip().startswith(("from ", "import ")):
                break
    return (typing_import_idx, existing_typing_imports)


def _skip_docstring(lines: list[str], start_idx: int) -> int:
    if start_idx < 10 and lines[start_idx].strip().startswith('"""'):
        if lines[start_idx].strip().count('"""') == 1:
            for j in range(start_idx + 1, min(start_idx + 10, len(lines))):
                if '"""' in lines[j]:
                    return j
    return start_idx


def _merge_existing_imports(
    lines: list[str], typing_import_idx: int, imports_to_add: set[str]
) -> list[str]:
    old_line = lines[typing_import_idx]
    match = re.search("(from typing import .+)", old_line)
    if match:
        existing_imports = match.group(1)
        new_imports = f"{existing_imports}, {', '.join(sorted(imports_to_add))}"
        lines[typing_import_idx] = new_imports + "\n"
    return lines


def _find_import_insertion_point(lines: list[str]) -> int:
    insert_idx = 0
    for i, line in enumerate(lines):
        if i < 2 and line.startswith(("#!", "# -*-")):
            insert_idx = i + 1
            continue
        if i < 10 and line.strip().startswith('"""'):
            insert_idx = i + 1
            if line.strip().count('"""') == 1:
                for j in range(i + 1, min(i + 10, len(lines))):
                    if '"""' in lines[j]:
                        insert_idx = j + 1
                        break
            continue
        if line.strip() and (not line.strip().startswith("#")):
            insert_idx = i
            break
    return insert_idx


def _fix_any_builtin(content: str) -> str:
    pattern1 = "(\\w+)\\s*:\\s*any\\b"
    content = re.sub(pattern1, "\\1: Any", content)
    pattern2 = "->\\s*any\\s*:"
    content = re.sub(pattern2, "-> Any:", content)
    pattern3 = "\\[\\s*any\\s*\\]"
    content = re.sub(pattern3, "[Any]", content)
    pattern4 = "(\\w+)\\s*:\\s*any\\s*="
    content = re.sub(pattern4, "\\1: Any =", content)
    return content


def _add_missing_annotations(content: str, error_message: str) -> str:
    try:
        tree = ast.parse(content)
        lines = content.splitlines(keepends=True)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is None:
                    has_return = False
                    for body_node in ast.walk(node):
                        if (
                            isinstance(body_node, ast.Return)
                            and body_node.value is not None
                        ):
                            has_return = True
                            break
                    if not has_return:
                        func_line = node.lineno - 1
                        line = lines[func_line]
                        colon_pos = line.rfind(":")
                        if colon_pos > 0:
                            if "->" not in line:
                                new_line = (
                                    line[:colon_pos] + " -> None" + line[colon_pos:]
                                )
                                lines[func_line] = new_line
        return "".join(lines)
    except Exception as e:
        logger.debug(f"Could not add annotations via AST: {e}")
        return content


def _fix_path_str_conversion(content: str, error_message: str) -> str:
    # Preserved verbatim from ArchitectAgent._fix_path_str_conversion: this
    # is a permanent no-op. The `if` body is just `pass`, and `content` is
    # returned unconditionally and unchanged regardless of whether the
    # condition matched. See the module docstring's "Preserved quirks"
    # section, item 1.
    if "expected str" in error_message.lower() or "path" in error_message.lower():
        pass
    return content


def _add_await_keyword(content: str) -> str:
    # See the module docstring's "Preserved quirks" section, item 2: this
    # always splices "await " at the *start* of the (unindented) statement,
    # not before the matched call -- so for the only shape of line it ever
    # fires on (an assignment containing `.start(`/`.async_x(`), the result
    # is syntactically invalid Python. Preserved verbatim.
    lines = content.splitlines(keepends=True)
    modified = False
    async_patterns = ["(\\w+)\\.async_(\\w+)\\(", "(\\w+)\\.start\\("]
    for i, line in enumerate(lines):
        if "await" in line:
            continue
        stripped = line.strip()
        if stripped.startswith("#") or (
            stripped.startswith('"') and stripped.endswith('"')
        ):
            continue
        for pattern in async_patterns:
            if re.search(pattern, line) and "=" in line:
                indent = len(line) - len(line.lstrip())
                lines[i] = line[:indent] + "await " + line[indent:]
                modified = True
                break
    if modified:
        return "".join(lines)
    return content


# ---------------------------------------------------------------------------
# fix_type_error_with_plan (was ArchitectAgent._fix_type_error_with_plan)
# ---------------------------------------------------------------------------


def fix_type_error_with_plan(issue: Issue, plan: dict[str, t.Any]) -> FixResult:
    confidence = 0.5
    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                f"Cannot fix type error without file path: {issue.message}"
            ],
            recommendations=["Provide file path for type error fixing"],
        )
    file_content = _read_file(issue.file_path)
    if not file_content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {issue.file_path}"],
            recommendations=["Check file path and permissions"],
        )
    fixed_content, fixes_applied = apply_type_error_fixes(file_content, issue.message)
    if not fixes_applied:
        return FixResult(
            success=False,
            confidence=confidence,
            remaining_issues=[f"Type error: {issue.message}"],
            recommendations=[
                "Add missing typing imports: from typing import Any, Dict, List",
                "Replace `any` with `Any` in type annotations",
                "Add `await` keyword before async function calls",
                "Add type annotations to function parameters and returns",
                "Ensure Console/ConsoleInterface protocol compatibility",
                "Convert Path to str: `path_obj` or str to Path: `Path(str_obj)`",
            ],
        )
    write_success = _write_file(issue.file_path, fixed_content)
    if not write_success:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write fixes to {issue.file_path}"],
            recommendations=["Check file permissions and disk space"],
        )
    return FixResult(
        success=True,
        confidence=confidence,
        fixes_applied=fixes_applied,
        remaining_issues=[],
        recommendations=[f"Fixed type error: {issue.message}"],
        files_modified=[issue.file_path],
    )


# ---------------------------------------------------------------------------
# execute_fix_plan / ChangeSpec applicator
# ---------------------------------------------------------------------------


async def execute_fix_plan(plan: FixPlan) -> FixResult:
    if not plan.changes:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Plan has no changes to apply"],
            recommendations=["PlanningAgent should generate actual changes"],
        )
    if plan.issue_type == "TYPE_ERROR":
        direct_result = await _apply_plan_changes(plan)
        if direct_result.success:
            return direct_result
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=plan.changes[0].line_range[0] > 30
            and Priority.HIGH
            or Priority.MEDIUM,
            message=plan.rationale,
            file_path=plan.file_path,
        )
        plan_dict: dict[str, t.Any] = {
            "strategy": "internal_pattern_based",
            "approach": "add_type_annotations",
        }
        return fix_type_error_with_plan(issue, plan_dict)
    return await _apply_plan_changes(plan)


async def _apply_plan_changes(plan: FixPlan) -> FixResult:
    if not plan.file_path:
        return FixResult(
            success=False, confidence=0.0, remaining_issues=["No file path in plan"]
        )
    try:
        file_content = Path(plan.file_path).read_text(encoding="utf-8")
    except Exception as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {e}"],
        )
    lines = file_content.split("\n")
    applied_changes = []
    failed_changes = []
    line_offset = 0
    for i, change in enumerate(plan.changes):
        try:
            start_idx = change.line_range[0] - 1 + line_offset
            end_idx = change.line_range[1] + line_offset
            if start_idx < 0 or end_idx > len(lines) or start_idx >= end_idx:
                failed_changes.append(
                    f"Change {i}: Invalid line range {change.line_range}"
                )
                continue
            old_lines = lines[start_idx:end_idx]
            old_code = "\n".join(old_lines)

            old_code_normalized = old_code.rstrip("\n")
            planned_normalized = change.old_code.rstrip("\n") if change.old_code else ""
            if change.old_code and old_code_normalized != planned_normalized:
                logger.debug("=== DIAGNOSTIC: Change %d mismatch ===", i)
                logger.debug(" line_range: %s", change.line_range)
                logger.debug(" start_idx: %d, end_idx: %d", start_idx, end_idx)
                old_code_preview = (
                    change.old_code[:200] if change.old_code else "<empty>"
                )
                logger.debug(" change.old_code (first 200 chars): %s", old_code_preview)
                actual_preview = old_code[:200] if old_code else "<empty>"
                logger.debug(
                    " old_code from file (first 200 chars): %s", actual_preview
                )

                matched_line = _find_matching_line(
                    lines,
                    change.old_code,
                    change.line_range[0],
                    window=10,
                )
                if matched_line is not None:
                    new_start = matched_line
                    new_end = matched_line + (end_idx - start_idx)
                    logger.debug(
                        " Found match at line %d, adjusting line_range from %s to (%d, %d)",
                        matched_line + 1,
                        change.line_range,
                        new_start + 1,
                        new_end,
                    )

                    old_lines_adjusted = lines[new_start:new_end]
                    old_code_adjusted = "\n".join(old_lines_adjusted)
                    old_code_normalized_adjusted = old_code_adjusted.rstrip("\n")
                    if old_code_normalized_adjusted == planned_normalized:
                        start_idx = new_start
                        end_idx = new_end
                        logger.debug(" Adjusted line_range accepted, applying change")
                    else:
                        failed_changes.append(
                            f"Change {i}: Planned old code did not match target range (searched ±{10} lines)"
                        )
                        continue
                else:
                    failed_changes.append(
                        f"Change {i}: Planned old code did not match target range"
                    )
                    continue
            new_lines = change.new_code.split("\n")
            lines[start_idx:end_idx] = new_lines
            new_content = "\n".join(lines)
            success = _write_file(plan.file_path, new_content)
            if success:
                applied_changes.append(f"Change {i}: {change.reason}")
                line_offset += len(new_lines) - len(old_lines)
            else:
                lines[start_idx : start_idx + len(new_lines)] = old_lines
                failed_changes.append(f"Change {i} failed: {change.reason}")
        except Exception as e:
            message = f"Change {i} failed: {e}"
            failed_changes.append(message)
    success = len(applied_changes) == len(plan.changes)
    remaining_issues = (
        []
        if success
        else failed_changes or [f"Failed to apply planned changes to {plan.file_path}"]
    )
    return FixResult(
        success=success,
        confidence=0.7 if success else 0.0,
        fixes_applied=applied_changes,
        remaining_issues=remaining_issues,
        files_modified=[plan.file_path] if success else [],
    )


def _find_matching_line(
    lines: list[str],
    target_code: str,
    original_line: int,
    window: int = 10,
) -> int | None:
    target_normalized = target_code.strip()
    start_search = max(0, original_line - 1 - window)
    end_search = min(len(lines), original_line - 1 + window)

    for idx in range(start_search, end_search):
        line_normalized = lines[idx].strip()
        if line_normalized == target_normalized:
            return idx

        if idx + 1 < len(lines):
            two_line = lines[idx].strip() + "\n" + lines[idx + 1].strip()
            if two_line.strip() == target_normalized:
                return idx

    return None


__all__ = [
    "ChangeSpec",
    "FixPlan",
    "apply_type_error_fixes",
    "execute_fix_plan",
    "fix_type_error_with_plan",
]
