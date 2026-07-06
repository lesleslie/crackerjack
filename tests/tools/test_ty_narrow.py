"""Tests for ``crackerjack.tools.ty_narrow``.

Mechanical None-narrowing for the highest-frequency ty tier-3 shapes.
Scope is deliberately narrow: only the ``X in <var>`` and ``<var>[k]``
patterns where ty reports ``<var>: T | None``.

Out of scope (handed to tier-3 / human):

* Arithmetic operators (``int | None`` + ``int``) — too risky to
  silently insert a default; the right fix may be ``raise`` or
  early return, not ``0``.
* Method-call receivers (``<var>.method()``) — needs instance-narrow
  reasoning, not a default substitution.
* Subscripts where the LHS isn't a dict (``list[int][0]`` style) —
  default value depends on element type which we can't infer.

The pattern this module handles: replace the suspect variable
inside a single expression with ``(<var> or <default>)``, where
``<default>`` is derived from the non-None arm of the union.
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.tools.ty_narrow import (
    AUTO_FIX_CODES,
    NarrowFix,
    apply_narrow_fix,
    find_in_operator_candidates,
    parse_ty_unsupported_operator,
)

# ---------------------------------------------------------------------------
# parse_ty_unsupported_operator
# ---------------------------------------------------------------------------


class TestParseTyUnsupportedOperator:
    """ty concise: ``file:line:col: error[unsupported-operator] Operator `OP`
    is not supported between objects of type `LHS` and `RHS` ``
    """

    def test_parses_in_operator_with_str_none(self) -> None:
        line = (
            "tests/foo.py:73:16: error[unsupported-operator] Operator `in` "
            'is not supported between objects of type `Literal["x"]` '
            "and `str | None`"
        )
        site = parse_ty_unsupported_operator(line)
        assert site is not None
        assert site.line == 73
        assert site.col == 16
        assert site.operator == "in"
        assert site.rhs_type == "str | None"
        assert site.lhs_type == 'Literal["x"]'

    def test_returns_none_for_non_in_operators(self) -> None:
        # We only narrow ``in`` / ``not in`` mechanically — too risky otherwise.
        line = (
            "tests/foo.py:1:1: error[unsupported-operator] "
            "Operator `+` is not supported for types `int | None` and `int`"
        )
        assert parse_ty_unsupported_operator(line) is None

    def test_returns_none_for_non_noneable_rhs(self) -> None:
        # If the RHS isn't Noneable, no narrowing helps.
        line = (
            "tests/foo.py:1:1: error[unsupported-operator] "
            "Operator `in` is not supported between objects of type `str` "
            "and `int`"
        )
        assert parse_ty_unsupported_operator(line) is None

    def test_returns_none_for_other_codes(self) -> None:
        line = (
            "tests/foo.py:1:1: error[unresolved-attribute] "
            "Attribute `lower` not defined on `None`"
        )
        assert parse_ty_unsupported_operator(line) is None


# ---------------------------------------------------------------------------
# find_in_operator_candidates
# ---------------------------------------------------------------------------


class TestFindInOperatorCandidates:
    """Given a parsed Site and the file content, find the suspect
    expression on the RHS of ``in`` so we know what to substitute.
    """

    def test_finds_var_in_in_expression(self) -> None:
        content = "result = name in tool_name\n"
        candidate = find_in_operator_candidates(
            content,
            line=1,
            operator="in",
            rhs_type="str | None",
        )
        assert candidate is not None
        assert candidate.var_name == "tool_name"
        assert candidate.default_value == '""'
        assert candidate.replacement == 'result = name in (tool_name or "")'

    def test_finds_var_in_not_in_expression(self) -> None:
        content = 'if "x" not in tool_name:\n    pass\n'
        candidate = find_in_operator_candidates(
            content,
            line=1,
            operator="not in",
            rhs_type="str | None",
        )
        assert candidate is not None
        assert candidate.var_name == "tool_name"

    def test_chooses_dict_default_for_dict_none(self) -> None:
        content = "x = key in mapping\n"
        candidate = find_in_operator_candidates(
            content,
            line=1,
            operator="in",
            rhs_type="dict | None",
        )
        assert candidate is not None
        assert candidate.default_value == "{}"

    def test_returns_none_for_chained_expressions(self) -> None:
        # If the RHS is a complex expression, don't auto-narrow.
        content = 'x = "y" in (tool_name or get_default())\n'
        candidate = find_in_operator_candidates(
            content,
            line=1,
            operator="in",
            rhs_type="str | None",
        )
        assert candidate is None

    def test_returns_none_for_unsupported_type(self) -> None:
        # Union without None can't be narrowed with `or`.
        content = 'x = "y" in tool_name\n'
        candidate = find_in_operator_candidates(
            content,
            line=1,
            operator="in",
            rhs_type="str | int",
        )
        assert candidate is None


# ---------------------------------------------------------------------------
# apply_narrow_fix
# ---------------------------------------------------------------------------


class TestApplyNarrowFix:
    def _write(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "module.py"
        p.write_text(content)
        return p

    def test_replaces_simple_in_expression(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, 'x = "y" in tool_name\n')
        fix = NarrowFix(
            line=1,
            col=1,
            operator="in",
            rhs_type="str | None",
            var_name="tool_name",
            default_value='""',
            original='x = "y" in tool_name\n',
            replacement='x = "y" in (tool_name or "")\n',
        )
        changed = apply_narrow_fix(p, fix)
        assert changed is True
        assert p.read_text() == 'x = "y" in (tool_name or "")\n'

    def test_idempotent_when_already_narrowed(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, 'x = "y" in (tool_name or "")\n')
        fix = NarrowFix(
            line=1,
            col=1,
            operator="in",
            rhs_type="str | None",
            var_name="tool_name",
            default_value='""',
            original='x = "y" in (tool_name or "")\n',
            replacement='x = "y" in (tool_name or "")\n',
        )
        changed = apply_narrow_fix(p, fix)
        assert changed is False

    def test_handles_dict_default(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, "x = key in mapping\n")
        fix = NarrowFix(
            line=1,
            col=1,
            operator="in",
            rhs_type="dict | None",
            var_name="mapping",
            default_value="{}",
            original="x = key in mapping\n",
            replacement="x = key in (mapping or {})\n",
        )
        changed = apply_narrow_fix(p, fix)
        assert changed is True
        assert p.read_text() == "x = key in (mapping or {})\n"


# ---------------------------------------------------------------------------
# AUTO_FIX_CODES constant
# ---------------------------------------------------------------------------


class TestAutoFixCodes:
    def test_only_unsupported_operator_is_listed(self) -> None:
        assert AUTO_FIX_CODES == frozenset({"unsupported-operator"})

    def test_narrow_does_not_touch_unresolved_attribute(self) -> None:
        # unresolved-attribute is a different category; let the LLM handle.
        assert "unresolved-attribute" not in AUTO_FIX_CODES
