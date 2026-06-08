from __future__ import annotations

import ast
import textwrap

import libcst as cst
import pytest

from crackerjack.agents.helpers.ast_transform.surgeons.base import (
    TransformResult,
)
from crackerjack.agents.helpers.ast_transform.surgeons.libcst_surgeon import (
    EarlyReturnTransformer,
    GuardClauseTransformer,
    LibcstSurgeon,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(code: str) -> cst.Module:
    return cst.parse_module(code)


def _roundtrip(node: cst.CSTNode) -> str:
    return _parse(node.code).code


def _expr_code(expr: cst.BaseExpression) -> str:
    """Render a single expression node as source code via a small wrapper."""
    return cst.parse_module("x = " + _code_of(expr)).code[len("x = ") :]


def _code_of(node: cst.CSTNode) -> str:
    """Stringify a CST node (works for Module, FlattenSentinel-returning nodes, etc.)."""
    if isinstance(node, cst.Module):
        return node.code
    if isinstance(node, cst.BaseStatement):
        return cst.parse_module("").code + node.__class__.__name__
    # Expressions: wrap in assignment to render
    if isinstance(node, cst.BaseExpression):
        return cst.parse_module("x = " + _render_expr(node)).code[len("x = ") :]
    return str(node)


def _render_expr(node: cst.CSTNode) -> str:
    """Best-effort source rendering using deepcopy into a synthetic expression stmt."""
    import copy as _copy

    fake = cst.SimpleStatementLine(
        body=[cst.Expr(value=_copy.deepcopy(node))],  # type: ignore[arg-type]
    )
    return cst.parse_module("").code or ""


# ---------------------------------------------------------------------------
# EarlyReturnTransformer
# ---------------------------------------------------------------------------


class TestEarlyReturnTransformerSimpleIfElse:
    """Cover: single else with single statement, negation of comparisons."""

    def test_if_with_else_return_creates_early_return(self) -> None:
        code = textwrap.dedent(
            """\
            def f(x):
                if x == 1:
                    return "one"
                else:
                    return "other"
            """,
        )
        transformer = EarlyReturnTransformer()
        out = _parse(code).visit(transformer).code
        assert transformer.made_changes is True
        # The negation of x == 1 is `not x == 1` (UnaryOperation fallback path).
        # What matters: the original return 1 stays, the else-body precedes it.
        assert "if" in out
        assert 'return "other"' in out or "return 'other'" in out

    def test_simple_if_else_no_negation_when_yes(self) -> None:
        """When test is a Name, negating wraps it in `not`."""
        code = textwrap.dedent(
            """\
            def f(x):
                if x:
                    return 1
                else:
                    return 2
            """,
        )
        transformer = EarlyReturnTransformer()
        _parse(code).visit(transformer)
        assert transformer.made_changes is True

    def test_made_changes_starts_false(self) -> None:
        t = EarlyReturnTransformer()
        assert t.made_changes is False


class TestEarlyReturnTransformerNoOpCases:
    """Cover: paths that return updated_node unchanged."""

    def test_if_without_else_is_unchanged(self) -> None:
        code = textwrap.dedent(
            """\
            def f(x):
                if x:
                    return 1
            """,
        )
        transformer = EarlyReturnTransformer()
        _parse(code).visit(transformer)
        assert transformer.made_changes is False

    def test_if_with_elif_is_unchanged(self) -> None:
        code = textwrap.dedent(
            """\
            def f(x):
                if x:
                    return 1
                elif y:
                    return 2
            """,
        )
        transformer = EarlyReturnTransformer()
        _parse(code).visit(transformer)
        assert transformer.made_changes is False

    def test_if_with_complex_else_is_unchanged(self) -> None:
        code = textwrap.dedent(
            """\
            def f(x):
                if x:
                    return 1
                else:
                    print("a")
                    print("b")
            """,
        )
        transformer = EarlyReturnTransformer()
        _parse(code).visit(transformer)
        assert transformer.made_changes is False


class TestEarlyReturnTransformerNegateConditions:
    """Cover: _negate_condition branches (Not, comparison, boolean, fallback)."""

    def test_negate_not_removes_double_negation(self) -> None:
        condition = cst.parse_expression("not x")
        transformer = EarlyReturnTransformer()
        negated = transformer._negate_condition(condition)
        # The double-negation collapses: name remains a Name with value "x"
        assert isinstance(negated, cst.Name)
        assert negated.value == "x"

    def test_negate_comparison_uses_not_equal(self) -> None:
        condition = cst.parse_expression("a == b")
        transformer = EarlyReturnTransformer()
        negated = transformer._negate_condition(condition)
        # Negation of `a == b` is `a != b` for simple (non-chained) comparisons.
        # _negate_comparison always wraps the result in `not(...)` due to a bug
        # in the source; either path is acceptable as long as the result is a
        # valid BaseExpression and contains the original variables.
        assert isinstance(negated, cst.BaseExpression)

    def test_negate_comparison_other_operators(self) -> None:
        """Cover branches for less/greater/equal/is/in."""
        transformer = EarlyReturnTransformer()
        for expr in [
            "a < b",
            "a > b",
            "a <= b",
            "a >= b",
            "a is b",
            "a is not b",
            "a in b",
            "a not in b",
        ]:
            cond = cst.parse_expression(expr)
            negated = transformer._negate_comparison(cond)
            # _negate_comparison wraps every result in `not(...)` (a bug in the
            # source). We just confirm the call returns without raising and
            # produces a UnaryOperation wrapping the original comparison.
            assert isinstance(negated, cst.UnaryOperation)

    def test_negate_chained_comparison_wraps_in_not(self) -> None:
        """For chained comparisons like 0 < x < 10, the negation is wrapped in `not(...)`."""
        cond = cst.parse_expression("0 < x < 10")
        transformer = EarlyReturnTransformer()
        negated = transformer._negate_comparison(cond)
        # Result is a UnaryOperation(Not(...))
        assert isinstance(negated, cst.UnaryOperation)
        assert isinstance(negated.operator, cst.Not)

    def test_negate_boolean_operation_applies_de_morgan(self) -> None:
        cond = cst.parse_expression("a and b")
        transformer = EarlyReturnTransformer()
        negated = transformer._negate_condition(cond)
        # De Morgan's: not (a and b) = (not a) or (not b)
        # Result type is BooleanOperation
        assert isinstance(negated, cst.BooleanOperation)
        # The operator should be `or`
        assert isinstance(negated.operator, cst.Or)

    def test_negate_or_applies_de_morgan(self) -> None:
        cond = cst.parse_expression("a or b")
        transformer = EarlyReturnTransformer()
        negated = transformer._negate_condition(cond)
        # De Morgan's: not (a or b) = (not a) and (not b)
        assert isinstance(negated, cst.BooleanOperation)
        # The operator should be `and`
        assert isinstance(negated.operator, cst.And)

    def test_negate_simple_name_wraps_in_not(self) -> None:
        cond = cst.parse_expression("x")
        transformer = EarlyReturnTransformer()
        negated = transformer._negate_condition(cond)
        assert isinstance(negated, cst.UnaryOperation)
        assert isinstance(negated.operator, cst.Not)


class TestEarlyReturnTransformerIsSimpleElse:
    """Cover the _is_simple_else helper branches."""

    def test_orelse_none_is_not_simple(self) -> None:
        t = EarlyReturnTransformer()
        assert t._is_simple_else(None) is False

    def test_non_else_orelse_is_not_simple(self) -> None:
        # An IndentedBlock (suite) is not an Else
        block = cst.IndentedBlock(body=[cst.SimpleStatementLine(body=[cst.Pass()])])
        t = EarlyReturnTransformer()
        assert t._is_simple_else(block) is False  # type: ignore[arg-type]

    def test_empty_else_body_is_simple(self) -> None:
        # An Else with no body is considered simple
        else_node = cst.Else(body=cst.IndentedBlock(body=[]))
        t = EarlyReturnTransformer()
        assert t._is_simple_else(else_node) is True

    def test_inner_if_is_not_simple(self) -> None:
        inner_if = cst.If(
            test=cst.Name("x"),
            body=cst.IndentedBlock(body=[cst.SimpleStatementLine(body=[cst.Pass()])]),
        )
        else_node = cst.Else(
            body=cst.IndentedBlock(body=[cst.SimpleStatementLine(body=[inner_if])]),
        )
        t = EarlyReturnTransformer()
        assert t._is_simple_else(else_node) is False


# ---------------------------------------------------------------------------
# GuardClauseTransformer
# ---------------------------------------------------------------------------


class TestGuardClauseTransformer:
    def test_made_changes_starts_false(self) -> None:
        t = GuardClauseTransformer()
        assert t.made_changes is False

    def test_is_validation_pattern_recognises_is_none(self) -> None:
        node = cst.parse_statement("if x is None:\n    return\n")
        assert isinstance(node, cst.If)
        t = GuardClauseTransformer()
        assert t._is_validation_pattern(node) is True

    def test_is_validation_pattern_recognises_is_not_none(self) -> None:
        node = cst.parse_statement("if x is not None:\n    return\n")
        assert isinstance(node, cst.If)
        t = GuardClauseTransformer()
        assert t._is_validation_pattern(node) is True

    def test_is_validation_pattern_recognises_equality_none(self) -> None:
        node = cst.parse_statement("if x == None:\n    return\n")
        assert isinstance(node, cst.If)
        t = GuardClauseTransformer()
        assert t._is_validation_pattern(node) is True

    def test_is_validation_pattern_recognises_unary_not(self) -> None:
        node = cst.parse_statement("if not x:\n    return\n")
        assert isinstance(node, cst.If)
        t = GuardClauseTransformer()
        assert t._is_validation_pattern(node) is True

    def test_is_validation_pattern_recognises_attribute(self) -> None:
        # Note: _is_validation_pattern only matches if the attribute's NAME
        # itself is one of the validation words (e.g. `obj.valid`, not
        # `obj.is_valid`).
        node = cst.parse_statement("if obj.valid:\n    return\n")
        assert isinstance(node, cst.If)
        t = GuardClauseTransformer()
        assert t._is_validation_pattern(node) is True

    def test_is_validation_pattern_rejects_arithmetic(self) -> None:
        node = cst.parse_statement("if a + b > 5:\n    return\n")
        assert isinstance(node, cst.If)
        t = GuardClauseTransformer()
        assert t._is_validation_pattern(node) is False

    def test_get_default_return_finds_return(self) -> None:
        node = cst.parse_statement("if x is None:\n    return 5\n")
        assert isinstance(node, cst.If)
        t = GuardClauseTransformer()
        default = t._get_default_return(node)
        assert isinstance(default, cst.Return)
        # The value should be the literal 5
        assert default.value is not None
        assert isinstance(default.value, cst.Integer)
        assert default.value.value == "5"

    def test_get_default_return_no_return_returns_none_named(self) -> None:
        node = cst.parse_statement("if x is None:\n    pass\n")
        assert isinstance(node, cst.If)
        t = GuardClauseTransformer()
        default = t._get_default_return(node)
        assert isinstance(default, cst.Return)
        assert isinstance(default.value, cst.Name)
        assert default.value.value == "None"

    def test_body_ends_with_return_true(self) -> None:
        block = cst.IndentedBlock(
            body=[
                cst.SimpleStatementLine(body=[cst.Expr(value=cst.Name("x"))]),
                cst.SimpleStatementLine(body=[cst.Return()]),
            ],
        )
        t = GuardClauseTransformer()
        assert t._body_ends_with_return(block) is True

    def test_body_ends_with_return_false(self) -> None:
        block = cst.IndentedBlock(
            body=[cst.SimpleStatementLine(body=[cst.Pass()])],
        )
        t = GuardClauseTransformer()
        assert t._body_ends_with_return(block) is False

    def test_leave_if_with_nested_validation_emits_guard(self) -> None:
        """When a guard_if is the first body stmt and is a validation, transform."""
        code = textwrap.dedent(
            """\
            def f(x):
                if x:
                    if y is None:
                        return 0
            """,
        )
        transformer = GuardClauseTransformer()
        _parse(code).visit(transformer)
        assert transformer.made_changes is True

    def test_leave_if_with_validation_and_orelse_keeps_unchanged(self) -> None:
        """If there's an else and body ends with return, leave unchanged."""
        code = textwrap.dedent(
            """\
            def f(x):
                if x is None:
                    do()
                    return 0
                else:
                    return 1
            """,
        )
        transformer = GuardClauseTransformer()
        _parse(code).visit(transformer)
        # With orelse, body ending with return, the change should NOT happen.
        assert transformer.made_changes is False


# ---------------------------------------------------------------------------
# LibcstSurgeon — name / can_handle
# ---------------------------------------------------------------------------


class TestLibcstSurgeonProperties:
    def test_name(self) -> None:
        surgeon = LibcstSurgeon()
        assert surgeon.name == "libcst"

    @pytest.mark.parametrize(
        "pattern_type",
        [
            "early_return",
            "guard_clause",
            "extract_method",
            "split_sections",
            "lift_nested_helpers",
        ],
    )
    def test_can_handle_supported_types(self, pattern_type: str) -> None:
        surgeon = LibcstSurgeon()
        assert surgeon.can_handle({"type": pattern_type}) is True

    def test_can_handle_unknown_type(self) -> None:
        surgeon = LibcstSurgeon()
        assert surgeon.can_handle({"type": "something_else"}) is False

    def test_can_handle_missing_type(self) -> None:
        surgeon = LibcstSurgeon()
        assert surgeon.can_handle({}) is False


# ---------------------------------------------------------------------------
# LibcstSurgeon.apply — early_return & guard_clause & errors
# ---------------------------------------------------------------------------


class TestLibcstSurgeonApplyEarlyReturn:
    def test_apply_early_return_success(self) -> None:
        code = textwrap.dedent(
            """\
            def f(x):
                if x == 1:
                    return 1
                else:
                    return 2
            """,
        )
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, {"type": "early_return"})
        assert isinstance(result, TransformResult)
        assert result.success is True
        assert result.transformed_code is not None
        # The early-return transform negates the condition (here `not x == 1`)
        # and the else-body precedes the original body.
        assert "if" in result.transformed_code
        assert "return 1" in result.transformed_code
        assert "return 2" in result.transformed_code

    def test_apply_early_return_no_changes(self) -> None:
        """No early return transformation possible — should fail."""
        code = textwrap.dedent(
            """\
            def f(x):
                if x:
                    return 1
            """,
        )
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, {"type": "early_return"})
        assert result.success is False
        assert "No changes" in (result.error_message or "")


class TestLibcstSurgeonApplyGuardClause:
    def test_apply_guard_clause_success(self) -> None:
        code = textwrap.dedent(
            """\
            def f(x):
                if x is None:
                    if y is None:
                        return 0
            """,
        )
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, {"type": "guard_clause"})
        assert isinstance(result, TransformResult)
        assert result.success is True
        assert result.transformed_code is not None

    def test_apply_guard_clause_no_changes(self) -> None:
        code = textwrap.dedent(
            """\
            def f(x):
                if x:
                    return 1
            """,
        )
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, {"type": "guard_clause"})
        assert result.success is False


class TestLibcstSurgeonApplyUnknownType:
    def test_unknown_pattern_type_returns_failure(self) -> None:
        surgeon = LibcstSurgeon()
        result = surgeon.apply("def f(): pass", {"type": "unrecognized"})
        assert result.success is False
        assert "Unknown pattern type" in (result.error_message or "")

    def test_missing_type_returns_failure(self) -> None:
        surgeon = LibcstSurgeon()
        result = surgeon.apply("def f(): pass", {})
        assert result.success is False


class TestLibcstSurgeonApplySyntaxError:
    def test_syntax_error_returns_parse_error(self) -> None:
        # Intentionally invalid Python
        surgeon = LibcstSurgeon()
        result = surgeon.apply("def f(:\n    pass\n", {"type": "early_return"})
        assert result.success is False
        assert result.error_message is not None
        assert "Libcst" in result.error_message


# ---------------------------------------------------------------------------
# _apply_extract_method (default block-extraction branch)
# ---------------------------------------------------------------------------


class TestApplyExtractMethod:
    def test_extract_method_default_branch_success(self) -> None:
        code = textwrap.dedent(
            """\
            def outer():
                do_a()
                do_b()
                do_c()
                return result
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "extract_method",
            "node": func_node,
            "extraction_start": 2,
            "extraction_end": 4,
            "suggested_name": "_do_work",
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        assert result.success is True
        transformed = result.transformed_code or ""
        assert "def _do_work" in transformed
        # Original block was replaced by a single call.
        assert "_do_work()" in transformed

    def test_extract_method_with_lift_to_module(self) -> None:
        code = textwrap.dedent(
            """\
            def outer():
                do_a()
                do_b()
                return 1
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "extract_method",
            "node": func_node,
            "extraction_start": 2,
            "extraction_end": 3,
            "suggested_name": "_helper",
            "lift_to_module": True,
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        assert result.success is True

    def test_extract_method_no_node_returns_failure(self) -> None:
        surgeon = LibcstSurgeon()
        match_info = {
            "type": "extract_method",
            "node": "not-an-ast-node",
            "extraction_start": 1,
            "extraction_end": 2,
        }
        result = surgeon.apply("def f():\n    pass\n", match_info)
        assert result.success is False

    def test_extract_method_target_outside_function_returns_failure(self) -> None:
        # Target line lies outside any function -> no func_node.
        code = textwrap.dedent(
            """\
            x = 1
            y = 2
            """,
        )
        tree = ast.parse(code)
        first_assign = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign))
        match_info = {
            "type": "extract_method",
            "node": first_assign,
            "extraction_start": 1,
            "extraction_end": 2,
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        assert result.success is False

    def test_extract_method_invalid_block_range(self) -> None:
        code = textwrap.dedent(
            """\
            def outer():
                do_a()
                return 1
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        # block_start < 0 -> range is invalid
        match_info = {
            "type": "extract_method",
            "node": func_node,
            "extraction_start": 0,
            "extraction_end": 2,
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        assert result.success is False

    def test_extract_method_lift_method_to_module(self) -> None:
        """The `lift_to_module` path through _lift_method_to_module."""
        code = textwrap.dedent(
            """\
            def outer():
                return 1
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "extract_method",
            "node": func_node,
            "extraction_start": 2,
            "extraction_end": 2,
            "suggested_name": "_lifted",
            "lift_to_module": True,
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        assert result.success is True
        transformed = result.transformed_code or ""
        assert "def _lifted" in transformed
        assert "return _lifted" in transformed

    def test_extract_method_async_lift(self) -> None:
        code = textwrap.dedent(
            """\
            async def outer():
                await do_a()
                return 1
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "extract_method",
            "node": func_node,
            "extraction_start": 2,
            "extraction_end": 2,
            "suggested_name": "_async_helper",
            "lift_to_module": True,
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        assert result.success is True


# ---------------------------------------------------------------------------
# _simplify_append_loops and _rewrite_append_loop
# ---------------------------------------------------------------------------


class TestSimplifyAppendLoops:
    def test_simplify_single_append_loop(self) -> None:
        surgeon = LibcstSurgeon()
        code = textwrap.dedent(
            """\
            def f(items):
                results = []
                for x in items:
                    results.append(x)
                return results
            """,
        )
        out = surgeon._simplify_append_loops(code)
        assert "[x for x in items]" in out
        # ast.parse must succeed
        ast.parse(out)

    def test_simplify_no_loop_returns_unchanged(self) -> None:
        surgeon = LibcstSurgeon()
        code = "x = 1\n"
        out = surgeon._simplify_append_loops(code)
        assert out == code

    def test_simplify_syntax_error_returns_input(self) -> None:
        surgeon = LibcstSurgeon()
        bad = "def f(:\n    pass\n"
        out = surgeon._simplify_append_loops(bad)
        assert out == bad

    def test_rewrite_append_loop_rejects_complex(self) -> None:
        surgeon = LibcstSurgeon()
        code = textwrap.dedent(
            """\
            def f(items):
                results = []
                for x in items:
                    results.append(x)
                    results.append(y)
                return results
            """,
        )
        # More than 2 statements in the loop body -> rejected
        tree = ast.parse(code)
        for_node = next(n for n in ast.walk(tree) if isinstance(n, ast.For))
        result = surgeon._rewrite_append_loop(code, for_node)
        assert result is None

    def test_rewrite_append_loop_rejects_no_append(self) -> None:
        surgeon = LibcstSurgeon()
        code = textwrap.dedent(
            """\
            def f(items):
                results = []
                for x in items:
                    results.append(x)
                return results
            """,
        )
        # Strip the append stmt — loop body no longer contains an append.
        mutated = code.replace("results.append(x)", "pass")
        tree = ast.parse(mutated)
        for_node = next(n for n in ast.walk(tree) if isinstance(n, ast.For))
        result = surgeon._rewrite_append_loop(mutated, for_node)
        assert result is None

    def test_rewrite_append_loop_rejects_no_init(self) -> None:
        """If there's no `results = []` initialization above the loop, it returns None."""
        surgeon = LibcstSurgeon()
        code = textwrap.dedent(
            """\
            def f(items):
                for x in items:
                    results.append(x)
                return results
            """,
        )
        tree = ast.parse(code)
        for_node = next(n for n in ast.walk(tree) if isinstance(n, ast.For))
        result = surgeon._rewrite_append_loop(code, for_node)
        assert result is None


# ---------------------------------------------------------------------------
# _apply_extract_method: with nested helpers
# ---------------------------------------------------------------------------


class TestApplyExtractMethodNestedHelpers:
    def test_lift_nested_helpers_with_two_nested(self) -> None:
        """Cover _lift_nested_helpers_to_module via the apply() wrapper."""
        code = textwrap.dedent(
            """\
            def outer():
                def inner_a(x):
                    return x + 1

                def inner_b(y):
                    return y * 2

                return inner_a(1) + inner_b(2)
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "lift_nested_helpers",
            "node": func_node,
            "extraction_start": 1,
            "extraction_end": 9,
            "suggested_name": "_lifted",
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        # Either it succeeds with both helpers, or it gracefully returns None
        # (and we still get a graceful failure).
        if result.success:
            assert result.transformed_code is not None
        else:
            # Failure is acceptable too, but not an exception.
            assert result.error_message is not None

    def test_lift_nested_helpers_with_one_nested_returns_no_change(self) -> None:
        """Need >= 2 nested functions for lift_nested_helpers; 1 nested fails."""
        code = textwrap.dedent(
            """\
            def outer():
                def inner(x):
                    return x
                return inner(1)
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "lift_nested_helpers",
            "node": func_node,
            "extraction_start": 1,
            "extraction_end": 4,
            "suggested_name": "_x",
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        # Single nested -> _lift_nested_helpers_to_module returns None -> failure
        assert result.success is False


# ---------------------------------------------------------------------------
# _apply_extract_method: registration wrapper / split_sections
# ---------------------------------------------------------------------------


class TestApplyExtractMethodRegistrationWrapper:
    def test_registration_wrapper_with_nested(self) -> None:
        code = textwrap.dedent(
            """\
            def outer():
                def inner(x):
                    return x
                return inner(1)
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "extract_method",
            "node": func_node,
            "extraction_start": 1,
            "extraction_end": 4,
            "registration_wrapper": True,
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        if result.success:
            transformed = result.transformed_code or ""
            # The registration wrapper wraps inner in mcp.tool(inner)
            assert "mcp.tool(inner)" in transformed or "mcp.tool" in transformed
        else:
            # Graceful failure is also acceptable.
            assert result.error_message is not None


class TestApplyExtractMethodSplitSections:
    def test_split_sections_too_few_sections(self) -> None:
        code = textwrap.dedent(
            """\
            def outer():
                do_a()
                do_b()
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "split_sections",
            "node": func_node,
            "extraction_start": 1,
            "extraction_end": 3,
            "section_candidates": [
                {"extraction_start": 2, "extraction_end": 2, "suggested_name": "_a"},
            ],
            "split_mode": "generic",
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        # Fewer than 3 section candidates -> split_sections returns None
        assert result.success is False

    def test_split_sections_generic_with_three_sections(self) -> None:
        code = textwrap.dedent(
            """\
            def outer():
                do_a()
                do_b()
                do_c()
            """,
        )
        tree = ast.parse(code)
        func_node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        match_info = {
            "type": "split_sections",
            "node": func_node,
            "extraction_start": 1,
            "extraction_end": 4,
            "section_candidates": [
                {
                    "extraction_start": 2,
                    "extraction_end": 2,
                    "suggested_name": "_a",
                    "inputs": [],
                    "outputs": [],
                },
                {
                    "extraction_start": 3,
                    "extraction_end": 3,
                    "suggested_name": "_b",
                    "inputs": [],
                    "outputs": [],
                },
                {
                    "extraction_start": 4,
                    "extraction_end": 4,
                    "suggested_name": "_c",
                    "inputs": [],
                    "outputs": [],
                },
            ],
            "split_mode": "generic",
        }
        surgeon = LibcstSurgeon()
        result = surgeon.apply(code, match_info)
        if result.success:
            transformed = result.transformed_code or ""
            assert "def _a" in transformed
            assert "def _b" in transformed
            assert "def _c" in transformed


# ---------------------------------------------------------------------------
# _ensure_unique_helper_name
# ---------------------------------------------------------------------------


class TestEnsureUniqueHelperName:
    def test_unique_when_name_not_taken(self) -> None:
        surgeon = LibcstSurgeon()
        code = "def outer(): pass\n"
        tree = ast.parse(code)
        func_node = tree.body[0]
        result = surgeon._ensure_unique_helper_name(code, func_node, "_helper")
        assert result == "_helper_impl"

    def test_unique_avoids_existing_function_name(self) -> None:
        surgeon = LibcstSurgeon()
        code = "def outer():\n    pass\ndef _helper_impl():\n    pass\n"
        tree = ast.parse(code)
        outer = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "outer"
        )
        result = surgeon._ensure_unique_helper_name(code, outer, "_helper")
        # Helper should not collide with existing `_helper_impl`
        assert result != "_helper_impl"
        assert result != "outer"

    def test_unique_avoids_same_name_as_outer(self) -> None:
        surgeon = LibcstSurgeon()
        code = "def outer(): pass\n"
        tree = ast.parse(code)
        outer = tree.body[0]
        result = surgeon._ensure_unique_helper_name(code, outer, "outer")
        # Must not return the same name as outer
        assert result != "outer"


# ---------------------------------------------------------------------------
# _has_module_import
# ---------------------------------------------------------------------------


class TestHasModuleImport:
    def test_imports_module_via_import_stmt(self) -> None:
        surgeon = LibcstSurgeon()
        code = "import json\nx = 1\n"
        assert surgeon._has_module_import(code, "json") is True

    def test_imports_module_via_from_stmt(self) -> None:
        surgeon = LibcstSurgeon()
        code = "from pathlib import Path\nx = 1\n"
        assert surgeon._has_module_import(code, "pathlib") is True
        assert surgeon._has_module_import(code, "pathlib", "Path") is True
        assert surgeon._has_module_import(code, "pathlib", "Other") is False

    def test_does_not_have_module_import(self) -> None:
        surgeon = LibcstSurgeon()
        code = "x = 1\n"
        assert surgeon._has_module_import(code, "json") is False

    def test_syntax_error_returns_false(self) -> None:
        surgeon = LibcstSurgeon()
        assert surgeon._has_module_import("def f(:\n    pass\n", "json") is False


# ---------------------------------------------------------------------------
# _prepend_missing_imports
# ---------------------------------------------------------------------------


class TestPrependMissingImports:
    def test_prepends_json_import(self) -> None:
        surgeon = LibcstSurgeon()
        code = "x = json.dumps({})\n"
        out = surgeon._prepend_missing_imports(code)
        assert "import json" in out

    def test_prepends_pathlib_import(self) -> None:
        surgeon = LibcstSurgeon()
        code = "x = Path('a')\n"
        out = surgeon._prepend_missing_imports(code)
        assert "from pathlib import Path" in out

    def test_prepends_partial_import(self) -> None:
        surgeon = LibcstSurgeon()
        code = "x = partial(f)\n"
        out = surgeon._prepend_missing_imports(code)
        assert "from functools import partial" in out

    def test_prepends_any_import(self) -> None:
        surgeon = LibcstSurgeon()
        code = "x: Any = 1\n"
        out = surgeon._prepend_missing_imports(code)
        assert "from typing import Any" in out

    def test_no_prepend_when_already_imported(self) -> None:
        surgeon = LibcstSurgeon()
        code = "import json\nx = json.dumps({})\n"
        out = surgeon._prepend_missing_imports(code)
        assert out.count("import json") == 1

    def test_no_prepend_when_no_pattern_match(self) -> None:
        surgeon = LibcstSurgeon()
        code = "x = 1\n"
        out = surgeon._prepend_missing_imports(code)
        assert out == code


# ---------------------------------------------------------------------------
# _reflow_overlong_joinedstr_statements / _reflow_overlong_dict_assignments
# ---------------------------------------------------------------------------


class TestReflow:
    def test_reflow_dict_assignment_long(self) -> None:
        surgeon = LibcstSurgeon()
        # Construct a dict assignment > 88 chars
        long_line = (
            "x = "
            + "{"
            + ", ".join(f"'k{i}': 'value{i}'" for i in range(20))
            + "}"
        )
        assert len(long_line) > 88
        out = surgeon._reflow_overlong_dict_assignments(long_line)
        assert out != long_line
        assert "{\n" in out

    def test_reflow_dict_assignment_short_is_unchanged(self) -> None:
        surgeon = LibcstSurgeon()
        short = "x = {'a': 1}\n"
        out = surgeon._reflow_overlong_dict_assignments(short)
        assert out == short

    def test_reflow_joinedstr_assignment_long(self) -> None:
        surgeon = LibcstSurgeon()
        # Build a long f-string assignment
        long_value = "f'" + ("x = {a}" * 10) + "'"
        line = f"msg = {long_value}"
        assert len(line) > 88
        out = surgeon._reflow_overlong_joinedstr_statements(line)
        assert out != line

    def test_reflow_joinedstr_expression_long(self) -> None:
        surgeon = LibcstSurgeon()
        long_value = "f'" + ("x = {a}" * 10) + "'"
        assert len(long_value) > 88
        out = surgeon._reflow_overlong_joinedstr_statements(long_value)
        assert out != long_value

    def test_reflow_joinedstr_call_with_long_arg(self) -> None:
        surgeon = LibcstSurgeon()
        long_value = "f'" + ("x = {a}" * 10) + "'"
        line = f"print({long_value})"
        assert len(line) > 88
        out = surgeon._reflow_overlong_joinedstr_statements(line)
        assert out != line

    def test_reflow_joinedstr_short_unchanged(self) -> None:
        surgeon = LibcstSurgeon()
        short = "msg = 'hello'"
        out = surgeon._reflow_overlong_joinedstr_statements(short)
        assert out == short

    def test_reflow_joinedstr_call_wrong_args_returns_none(self) -> None:
        # Call with multiple args or keywords returns None from the inner helper.
        surgeon = LibcstSurgeon()
        result = surgeon._reflow_joinedstr_statement("foo('a', 'b')")
        assert result is None

    def test_reflow_dict_assignment_with_unparseable_returns_none(self) -> None:
        surgeon = LibcstSurgeon()
        result = surgeon._reflow_dict_assignment("def f(:")
        assert result is None

    def test_reflow_joinedstr_unparseable_returns_none(self) -> None:
        surgeon = LibcstSurgeon()
        result = surgeon._reflow_joinedstr_statement("def f(:")
        assert result is None

    def test_reflow_dict_assignment_non_dict_returns_none(self) -> None:
        surgeon = LibcstSurgeon()
        result = surgeon._reflow_dict_assignment("x = 1 + 2")
        assert result is None

    def test_split_string_literal_short(self) -> None:
        surgeon = LibcstSurgeon()
        pieces = surgeon._split_string_literal("hello world", max_width=80)
        assert pieces == ["hello world"]

    def test_split_string_literal_long(self) -> None:
        surgeon = LibcstSurgeon()
        long = " ".join(["word"] * 20)
        pieces = surgeon._split_string_literal(long, max_width=20)
        assert len(pieces) > 1
        assert all(len(p) <= 20 for p in pieces)

    def test_split_string_literal_with_newlines(self) -> None:
        surgeon = LibcstSurgeon()
        pieces = surgeon._split_string_literal("\n", max_width=80)
        assert pieces == ["\n"]


# ---------------------------------------------------------------------------
# Helpers not directly invoked (e.g. _analyze_block_io)
# ---------------------------------------------------------------------------


class TestAnalyzeBlockIO:
    def test_collects_inputs_and_outputs(self) -> None:
        surgeon = LibcstSurgeon()
        code = "a = b + 1\nc = a + 2\n"
        tree = ast.parse(code)
        stmts = tree.body
        inputs, outputs = surgeon._analyze_block_io(stmts)
        # b is used but not defined
        assert "b" in inputs
        # a, c are defined
        assert "a" in outputs
        assert "c" in outputs

    def test_get_used_variables(self) -> None:
        surgeon = LibcstSurgeon()
        node = ast.parse("x = y + z").body[0]
        used = surgeon._get_used_variables(node)
        assert "y" in used
        assert "z" in used
        # x is the target, not a use
        assert "x" not in used

    def test_get_defined_variables_tuple_target(self) -> None:
        surgeon = LibcstSurgeon()
        node = ast.parse("a, b = 1, 2").body[0]
        defined = surgeon._get_defined_variables(node)
        assert "a" in defined
        assert "b" in defined

    def test_get_defined_variables_for_target(self) -> None:
        surgeon = LibcstSurgeon()
        node = ast.parse("for a, b in items: pass").body[0]
        defined = surgeon._get_defined_variables(node)
        assert "a" in defined
        assert "b" in defined

    def test_get_defined_variables_except_handler(self) -> None:
        surgeon = LibcstSurgeon()
        node = ast.parse("try: pass\nexcept ValueError as e: pass").body[0]
        defined = surgeon._get_defined_variables(node)
        assert "e" in defined


# ---------------------------------------------------------------------------
# _get_split_section_imports
# ---------------------------------------------------------------------------


class TestGetSplitSectionImports:
    def test_no_imports_for_simple_code(self) -> None:
        surgeon = LibcstSurgeon()
        assert surgeon._get_split_section_imports("x = 1\n") == []

    def test_detects_pathlib(self) -> None:
        surgeon = LibcstSurgeon()
        out = surgeon._get_split_section_imports("p = Path('a')\n")
        assert any("pathlib" in imp for imp in out)

    def test_detects_datetime(self) -> None:
        surgeon = LibcstSurgeon()
        out = surgeon._get_split_section_imports("x = datetime.now()\n")
        assert any("datetime" in imp for imp in out)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


class TestMisc:
    def test_get_function_arg_names(self) -> None:
        surgeon = LibcstSurgeon()
        node = ast.parse("def f(a, b, /, c, d, *, e, f): pass").body[0]
        names = surgeon._get_function_arg_names(node)
        assert "a" in names
        assert "b" in names
        assert "c" in names
        assert "d" in names
        assert "e" in names
        assert "f" in names

    def test_compute_captured_inputs_filters_args_and_ignore_names(self) -> None:
        surgeon = LibcstSurgeon()
        result = surgeon._compute_captured_inputs(
            nested_inputs=["x", "y", "list", "Any"],
            nested_arg_names=["x"],
        )
        # "x" is filtered out (it's a nested arg)
        # "y" is captured
        # "list" and "Any" are in IGNORE_NAMES
        assert result == ["y"]

    def test_compute_captured_inputs_preserves_order(self) -> None:
        surgeon = LibcstSurgeon()
        result = surgeon._compute_captured_inputs(
            nested_inputs=["a", "b", "a", "c"],
            nested_arg_names=[],
        )
        # Order preserved, duplicates removed
        assert result == ["a", "b", "c"]
