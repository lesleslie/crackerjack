"""Deterministic AST/string-based anti-pattern detection logic.

Extracted from ``crackerjack.agents.anti_pattern_agent.AntiPatternAgent``
(115 lines). Unlike the larger agents in this extraction plan, this class
has no ``SubAgent``/coordinator-dispatch surface at all -- it never
inherited ``SubAgent``, has no ``get_supported_types``/``can_handle``/
``agent_registry.register`` methods, and is invoked directly by
``crackerjack.agents.analysis_coordinator.AnalysisCoordinator`` as a plain
helper object (``self.pattern_agent = AntiPatternAgent(project_path)``,
then ``await self.pattern_agent.identify_anti_patterns(context)``). It also
has no ``FixPlan``/``ChangeSpec`` applicator (precedent 3 -- none invented
here) and does not depend on ``crackerjack.models.issues.Issue`` at all --
the original class never imported it, so nothing is imported from
``crackerjack.models`` here either.

What was dropped versus the original ``AntiPatternAgent``:

- ``__init__`` -- stored ``self.project_path`` (never read by any method in
  the class) and ``self.file_reader = FileContextReader()`` (constructed
  but never used by any method either). Both are genuinely dead state, not
  load-bearing behavior; confirmed by reading the full original file and
  grepping for ``project_path``/``file_reader`` outside ``__init__`` --
  neither appears again anywhere in the class body. Dropped entirely, no
  parameter added to replace them.
- The ``from .file_context import FileContextReader`` import -- unused
  dependency of the dropped constructor state above.

Everything else -- ``identify_anti_patterns`` and its four ``_check_*``
helpers -- is real, independent detection logic and is ported verbatim as
module-level functions, with ``self`` dropped from each signature.

Several pre-existing behavioral quirks/bugs are preserved verbatim below,
not "fixed," per CLAUDE.md Rule 7 ("preserve functional requirements...
fix the technical issue, not the requirements"). Each was independently
verified against the *original* ``crackerjack/agents/anti_pattern_agent.py``
by direct execution before being documented here (not just inferred by
reading):

1. ``_check_duplicate_definitions``'s ``definitions`` variable is annotated
   ``set[Any]`` but assigned a dict literal (``{}``) and used exclusively
   with dict operations (``definitions[name] = node.lineno``,
   ``name in definitions``, ``definitions[name]``) -- the annotation is
   simply wrong; both the assignment and the later dict-write carry a
   ``# type: ignore`` comment, presumably because the original author
   noticed the mismatch and silenced the type checker instead of fixing the
   annotation. Preserved verbatim, including both ``# type: ignore``
   comments.
2. ``_check_duplicate_definitions`` only inspects **top-level** statements
   (``tree.body``, not ``ast.walk(tree)``), so a nested method sharing a
   name with a module-level function or another class's method is never
   flagged as a duplicate. It also returns on the **first** duplicate found
   rather than collecting all of them. Verified empirically: a method
   named ``helper`` inside a class alongside a module-level ``def
   helper():`` produces no warning; three top-level ``def foo():``
   definitions (plus a separate duplicated ``def baz():`` pair) produce
   exactly one warning total (for the second ``foo`` occurrence), not two
   or three.
3. ``_check_unclosed_brackets`` scans every character of ``code``,
   including characters inside string literals and comments, as if they
   were real bracket tokens -- it has no string/comment-awareness. A
   snippet as simple as ``x = "("`` is reported as
   ``Unclosed '(' at position 5`` even though the code is syntactically
   valid. Verified empirically.
4. ``_check_import_placement``'s guard against false positives is
   effectively inert for realistic code. It intends to skip flagging a
   line >10 that starts with ``import``/``from`` when the file has a
   docstring/class/def before it, but the check is
   ``not any(x in lines[:i] for x in (triple-single-quote,
   triple-double-quote, "class ", "def ", "async def "))`` -- since
   ``lines[:i]`` is a **list of raw, unstripped
   line strings**, ``x in lines[:i]`` is a list-membership check (exact
   whole-line equality), not the intended substring-of-the-source check.
   A real line like ``class Foo:`` or ``def foo():`` never equals the bare
   string ``"class "``/``"def "``, so those guards never fire in practice;
   the only way to suppress the warning is a raw source line that is
   *exactly* ``'''`` or a bare triple-double-quote on its own (e.g. a
   docstring whose opening/closing delimiter sits alone on its own line).
   Verified empirically: a module-level ``def foo():`` before line 11 does
   **not** suppress the "mid-file" warning at the later import line, while
   a lone triple-quote line does.
5. ``_check_future_imports``'s trigger condition,
   ``stripped.startswith("__future__")``, does not match the only valid
   Python syntax for a future import, ``from __future__ import ...``
   (whose stripped form starts with ``"from "``, not ``"__future__"``).
   As a result this function never sets ``future_found = True`` for any
   syntactically valid Python file and therefore never emits either of its
   two warnings ("Multiple __future__ imports" / "Code after __future__
   import") against real code -- it is permanently inert dead-detection
   logic for its intended purpose. Verified empirically: a file with
   ``from __future__ import annotations`` followed by other code produces
   ``[]``; only a syntactically-invalid line beginning literally with the
   bare word ``__future__`` (not preceded by ``from ``) triggers the
   warning path.

Note for Task 22a (the consolidated ``cwd=project_path`` fix, tracked
separately): this file has no subprocess-invoking helper at all -- nothing
to add to that task's file list from this extraction.

Functional-overlap note for the reviewer: ``crackerjack/agents/
logic_validator.py``'s ``LogicValidator`` class independently implements
its own ``_check_duplicate_definitions``/``_check_import_placement``
methods with materially different (and not obviously buggy) logic. That
file is not named anywhere in this extraction plan and is left untouched;
flagged here as a factual observation only, per the precedent of not
attempting to dedupe pre-existing overlap outside a task's stated scope.
"""

from __future__ import annotations

import ast
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def identify_anti_patterns(context: dict[str, Any]) -> list[str]:
    warnings = []
    code = (
        context.get("code")
        or context.get("relevant_code")
        or context.get("file_content")
    )
    if not code:
        warnings.append("No code content in context")
        return warnings
    duplicate_defs = _check_duplicate_definitions(code)
    if duplicate_defs:
        warnings.extend(duplicate_defs)
    unclosed = _check_unclosed_brackets(code)
    if unclosed:
        warnings.append(unclosed)
    misplaced = _check_import_placement(code)
    if misplaced:
        warnings.append(misplaced)
    future_issues = _check_future_imports(code)
    if future_issues:
        warnings.extend(future_issues)
    logger.info(f"Found {len(warnings)} anti-pattern warnings")
    return warnings


def _check_duplicate_definitions(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
        definitions: set[Any] = {}  # type: ignore
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                if name in definitions:
                    return [
                        f"Duplicate top-level definition of '{name}' at line {node.lineno} (previous at line {definitions[name]})"  # type: ignore
                    ]
                definitions[name] = node.lineno  # type: ignore
        return []
    except Exception as e:
        logger.debug(f"Duplicate definition check failed: {e}")
        return []


def _check_unclosed_brackets(code: str) -> str | None:
    open_brackets = {"(": ")", "[": "]", "{": "}"}
    stack = []
    for i, char in enumerate(code):
        if char in open_brackets:
            stack.append((char, i))
        elif char in open_brackets.values():
            if not stack:
                return f"Unmatched closing '{char}' at position {i}"
            expected_closing = open_brackets[stack[-1][0]]
            if char != expected_closing:
                return f"Mismatched brackets: expected '{expected_closing}' but got '{char}' at position {i}"
            stack.pop()
    if stack:
        open_char, pos = stack[-1]
        return f"Unclosed '{open_char}' at position {pos}"
    return None


def _check_import_placement(code: str) -> str | None:
    lines = code.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if (
            stripped.startswith(("import ", "from "))
            and i > 10
            and (
                not any(
                    x in lines[:i]
                    for x in ("'''", '"""', "class ", "def ", "async def ")
                )
            )
        ):
            return f"Import statement at line {i} appears mid-file"
    return None


def _check_future_imports(code: str) -> list[str]:
    warnings = []
    lines = code.split("\n")
    future_found = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("__future__"):
            if future_found:
                warnings.append(f"Multiple __future__ imports detected (line {i})")
            future_found = True
        elif stripped and (not stripped.startswith("#")) and future_found:
            if any(
                stripped.startswith(x)
                for x in ("import ", "from ", "class ", "def ", "async def ")
            ):
                warnings.append(
                    f"Code after __future__ import (line {i}) - move __future__ to top of file"
                )
    return warnings
