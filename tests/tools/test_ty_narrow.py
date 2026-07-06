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
* Subscripts where the LHS isn't a bare identifier (``self.cache[k]``
  or ``func()[k]``) — needs instance-narrow reasoning.

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
    find_subscript_candidates,
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

    def test_chooses_list_default_for_list_str_none(self) -> None:
        # Common ty pattern: ``x in items`` where ``items: list[str] | None``.
        # The subscript is stripped to ``list``; default ``[]`` is safe for
        # membership testing against any element type.
        content = "x = item in items\n"
        candidate = find_in_operator_candidates(
            content,
            line=1,
            operator="in",
            rhs_type="list[str] | None",
        )
        assert candidate is not None
        assert candidate.var_name == "items"
        assert candidate.default_value == "[]"
        assert candidate.replacement == "x = item in (items or [])"

    def test_chooses_list_default_for_list_int_none(self) -> None:
        # Element type (``int``) is irrelevant — ``[]`` is the safe default
        # for membership testing regardless of element type.
        content = "x = n in counts\n"
        candidate = find_in_operator_candidates(
            content,
            line=1,
            operator="in",
            rhs_type="list[int] | None",
        )
        assert candidate is not None
        assert candidate.default_value == "[]"
        assert candidate.replacement == "x = n in (counts or [])"

    def test_returns_none_for_list_with_multi_arm_union(self) -> None:
        # Multi-arm non-None union — no unambiguous default; defer to LLM tier.
        content = "x = item in items\n"
        candidate = find_in_operator_candidates(
            content,
            line=1,
            operator="in",
            rhs_type="list[str] | int | None",
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

    def test_refuses_to_write_outside_project_root(self, tmp_path: Path) -> None:
        # Path-traversal guard: refuse writes that resolve outside
        # the provided project_root.
        project_root = tmp_path / "project"
        project_root.mkdir()
        evil_target = tmp_path / "evil.py"
        fix = NarrowFix(
            line=1,
            col=1,
            operator="in",
            rhs_type="str | None",
            var_name="tool_name",
            default_value='""',
            original="tool_name\n",
            replacement='(tool_name or "")\n',
        )
        result = apply_narrow_fix(evil_target, fix, project_root=project_root)
        assert result is False
        assert not evil_target.exists()

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
# find_subscript_candidates
# ---------------------------------------------------------------------------


class TestFindSubscriptCandidates:
    """Given a line and an ``rhs_type``, find the subscript expression
    so we know how to wrap the suspect identifier in ``(var or {})``.
    """

    def test_finds_subscript_with_dict_none(self) -> None:
        content = 'value["key"]\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict | None",
        )
        assert candidate is not None
        assert candidate.var_name == "value"
        assert candidate.default_value == "{}"
        assert candidate.operator == "subscript"
        assert candidate.replacement == '(value or {})["key"]'

    def test_accepts_parameterized_dict_type(self) -> None:
        content = 'value["key"]\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict[str, int] | None",
        )
        assert candidate is not None
        assert candidate.default_value == "{}"

    def test_preserves_trailing_comment(self) -> None:
        content = 'value["key"]  # important\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict | None",
        )
        assert candidate is not None
        assert candidate.replacement == '(value or {})["key"]  # important'

    def test_subscript_skips_chained_lhs(self) -> None:
        # Bare identifier only — ``self.cache`` has a chained attribute.
        content = 'self.cache["key"]\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict | None",
        )
        assert candidate is None

    def test_subscript_skips_call_lhs(self) -> None:
        content = 'func()["key"]\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict | None",
        )
        assert candidate is None

    def test_subscript_skips_non_string_key(self) -> None:
        # Dynamic key — can't safely default with ``{}``.
        content = "value[some_var]\n"
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict | None",
        )
        assert candidate is None

    def test_subscript_skips_non_dict_union(self) -> None:
        # list[int] | None would need element-type reasoning.
        content = 'value["k"]\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="list | None",
        )
        assert candidate is None

    def test_subscript_skips_non_nullable_union(self) -> None:
        content = 'value["k"]\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict",
        )
        assert candidate is None

    def test_subscript_skips_multi_arm_union(self) -> None:
        # Ambiguous — two non-None arms, can't pick a default safely.
        content = 'value["k"]\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict | list | None",
        )
        assert candidate is None

    def test_subscript_idempotent_at_find_level(self) -> None:
        # Already-narrowed line: ``lhs`` is ``(value or {})`` — not a bare
        # identifier, so the candidate finder rejects it.
        content = '(value or {})["key"]\n'
        candidate = find_subscript_candidates(
            content,
            line=1,
            rhs_type="dict | None",
        )
        assert candidate is None


# ---------------------------------------------------------------------------
# apply_narrow_fix (subscript end-to-end)
# ---------------------------------------------------------------------------


class TestApplySubscriptFix:
    """End-to-end: build the fix from ``find_subscript_candidates`` and
    apply it to disk. Mirrors the ``in``-operator pattern in
    ``TestApplyNarrowFix``.
    """

    def _write(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "module.py"
        p.write_text(content)
        return p

    def test_subscript_apply_replaces_line(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, 'value["key"]\n')
        fix = find_subscript_candidates(
            p.read_text(),
            line=1,
            rhs_type="dict | None",
        )
        assert fix is not None
        changed = apply_narrow_fix(p, fix)
        assert changed is True
        assert p.read_text() == '(value or {})["key"]\n'

    def test_subscript_idempotent_when_already_narrowed(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, '(value or {})["key"]\n')
        # Run ``find_subscript_candidates`` against the already-narrowed line;
        # it should refuse (LHS is not a bare identifier), so there's nothing
        # to apply.
        fix = find_subscript_candidates(
            p.read_text(),
            line=1,
            rhs_type="dict | None",
        )
        assert fix is None
        # Re-running ``apply_narrow_fix`` with a manually-built fix whose
        # replacement equals the current line also short-circuits.
        identity_fix = NarrowFix(
            line=1,
            col=1,
            operator="subscript",
            rhs_type="dict | None",
            var_name="value",
            default_value="{}",
            original='(value or {})["key"]\n',
            replacement='(value or {})["key"]\n',
        )
        changed = apply_narrow_fix(p, identity_fix)
        assert changed is False
        assert p.read_text() == '(value or {})["key"]\n'


# ---------------------------------------------------------------------------
# AUTO_FIX_CODES constant
# ---------------------------------------------------------------------------


class TestAutoFixCodes:
    def test_lists_unsupported_operator_and_not_subscriptable(self) -> None:
        assert AUTO_FIX_CODES == frozenset(
            {"unsupported-operator", "not-subscriptable"}
        )

    def test_narrow_does_not_touch_unresolved_attribute(self) -> None:
        # unresolved-attribute is a different category; let the LLM handle.
        assert "unresolved-attribute" not in AUTO_FIX_CODES
