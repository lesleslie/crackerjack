"""Tests for ``crackerjack.fixers.ast_transform.patterns.early_return``.

The ``EarlyReturnPattern`` matches ``if/else`` blocks where one branch
ends in a return/raise — the classic "guard clause" simplification.

Tests build AST nodes from small Python source strings so the matcher's
classification logic is exercised without touching the filesystem.
"""

from __future__ import annotations

import ast

import pytest

from crackerjack.fixers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternPriority,
)
from crackerjack.fixers.ast_transform.patterns.early_return import (
    EarlyReturnPattern,
)


def _parse(src: str) -> ast.If:
    """Parse source and return the outermost If node.

    Tries the source verbatim first (in case it starts with a function
    definition); otherwise wraps it in ``def f():`` so top-level
    if/else statements are syntactically valid in Python 3.14.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # Wrap in def f() so the if/else is a function-body statement.
        indented = "\n".join("    " + line for line in src.splitlines())
        tree = ast.parse(f"def f():\n{indented}\n")
    # If parsed at module level, body[0] is the If (after FunctionDef wrappers).
    for stmt in tree.body:
        if isinstance(stmt, ast.If):
            return stmt
    # Otherwise it's inside a FunctionDef or AsyncFunctionDef.
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for s in stmt.body:
                if isinstance(s, ast.If):
                    return s
    raise AssertionError(f"No If found in:\n{src}")


def _parse_stmt(src: str) -> ast.stmt:
    return ast.parse(src).body[0]


@pytest.fixture
def pattern() -> EarlyReturnPattern:
    return EarlyReturnPattern()


# ---------------------------------------------------------------------------
# Class surface
# ---------------------------------------------------------------------------


def test_name_property() -> None:
    assert EarlyReturnPattern().name == "early_return"


def test_priority_property() -> None:
    assert EarlyReturnPattern().priority == PatternPriority.EARLY_RETURN


def test_supports_async_property() -> None:
    assert EarlyReturnPattern().supports_async is True


def test_subclasses_base_pattern() -> None:
    assert isinstance(EarlyReturnPattern(), BasePattern)


# ---------------------------------------------------------------------------
# match() — dispatch on node type
# ---------------------------------------------------------------------------


def test_match_returns_none_for_non_if_node(pattern: EarlyReturnPattern) -> None:
    """Non-If nodes (e.g. FunctionDef) → None."""
    func = _parse_stmt("def f():\n    pass\n")
    assert pattern.match(func, ["def f():"]) is None


def test_match_returns_none_for_if_without_else(pattern: EarlyReturnPattern) -> None:
    """If with no orelse → None."""
    tree = ast.parse("if x:\n    pass\n")
    if_node = tree.body[0]
    assert pattern.match(if_node, []) is None


def test_match_returns_none_for_not_candidate(pattern: EarlyReturnPattern) -> None:
    """If with else but no return/raise/pass → None."""
    src = (
        "if x:\n"
        "    y = 1\n"
        "else:\n"
        "    z = 2\n"
    )
    if_node = _parse(src)
    # body has assignment but no return; orelse is also assignment
    assert pattern.match(if_node, src.splitlines()) is None


def test_match_returns_pattern_for_candidate(pattern: EarlyReturnPattern) -> None:
    """if/else with return → PatternMatch.

    Pre-existing bug: ``has_nested_if`` checks ``ast.walk(node)`` which
    yields the root If itself, so it always returns True. Per CLAUDE.md
    Rule 7, preserve verbatim — tests document observable behavior.
    """
    src = (
        "def f(x):\n"
        "    if x:\n"
        "        return 1\n"
        "    else:\n"
        "        return 2\n"
    )
    if_node = _parse(src)
    result = pattern.match(if_node, src.splitlines())
    assert result is not None
    assert result.pattern_name == "early_return"
    assert result.priority == PatternPriority.EARLY_RETURN
    assert result.line_start == if_node.lineno
    assert result.line_end == (if_node.end_lineno or if_node.lineno)
    assert result.match_info["type"] == "early_return"
    assert result.match_info["if_node"] is if_node
    assert result.context["body_length"] == 1
    assert result.context["orelse_length"] == 1
    # Buggy walk always returns True.
    assert result.context["has_nested_if"] is True


def test_match_with_nested_if_in_body(pattern: EarlyReturnPattern) -> None:
    """Body contains a nested If → context['has_nested_if'] is True.

    Pre-existing bug: ``ast.walk`` includes the root, so this is
    always True regardless of nesting. Tests assert observable
    behavior (True) but for a different reason than intended.
    """
    src = (
        "def f(x, y):\n"
        "    if x:\n"
        "        if y:\n"
        "            return 1\n"
        "        return 2\n"
        "    else:\n"
        "        return 3\n"
    )
    if_node = _parse(src)
    result = pattern.match(if_node, src.splitlines())
    assert result is not None
    assert result.context["has_nested_if"] is True


def test_match_end_lineno_fallback_to_lineno(pattern: EarlyReturnPattern) -> None:
    """If end_lineno is None, falls back to lineno."""
    src = (
        "def f(x):\n"
        "    if x:\n"
        "        return 1\n"
        "    else:\n"
        "        return 2\n"
    )
    if_node = _parse(src)
    # Strip end_lineno to simulate older ast.
    if_node.end_lineno = None  # type: ignore[attr-defined]
    result = pattern.match(if_node, src.splitlines())
    assert result is not None
    assert result.line_end == if_node.lineno


# ---------------------------------------------------------------------------
# _is_early_return_candidate
# ---------------------------------------------------------------------------


def test_is_candidate_empty_body(pattern: EarlyReturnPattern) -> None:
    """If body with 0 stmts → not a candidate.

    Note: the If must have non-empty body. We construct directly via ast
    rather than parsing source, because parse() would require a FunctionDef
    wrapper (the If-else at module level is a SyntaxError).
    """
    import textwrap
    tree = ast.parse(textwrap.dedent(
        """\
        def f(x):
            if x:
                pass
            else:
                return 1
        """
    ))
    if_node = tree.body[0].body[0]
    assert len(if_node.body) == 1  # body has Pass
    # Body has Pass (not Return) and orelse has Return → still candidate
    # because orelse_has_return is True. So this test exercises body[0]='pass'
    # not empty body.
    # To test EMPTY body, we'd need to mutate ast. Just verify the
    # _is_early_return_candidate function rejects empty body via direct
    # assertion below.
    # Build an If with empty body:
    empty_if = ast.If(test=ast.Name(id="x", ctx=ast.Load()), body=[], orelse=[ast.Return(value=ast.Constant(value=1))])
    assert pattern._is_early_return_candidate(empty_if) is False


def test_is_candidate_complex_else(pattern: EarlyReturnPattern) -> None:
    """orelse with 2+ statements → not simple, not candidate."""
    src = (
        "if x:\n"
        "    return 1\n"
        "else:\n"
        "    a = 1\n"
        "    b = 2\n"
    )
    if_node = _parse(src)
    assert pattern._is_early_return_candidate(if_node) is False


def test_is_candidate_test_has_call(pattern: EarlyReturnPattern) -> None:
    """Test containing a Call (side effect) → not a candidate."""
    src = (
        "if foo():\n"
        "    return 1\n"
        "else:\n"
        "    return 2\n"
    )
    if_node = _parse(src)
    assert pattern._is_early_return_candidate(if_node) is False


def test_is_candidate_test_has_yield(pattern: EarlyReturnPattern) -> None:
    """Test containing a Yield → side effect → not candidate."""
    src = (
        "def f():\n"
        "    if (yield x):\n"
        "        return 1\n"
        "    else:\n"
        "        return 2\n"
    )
    if_node = _parse(src)
    assert pattern._is_early_return_candidate(if_node) is False


def test_is_candidate_test_has_await(pattern: EarlyReturnPattern) -> None:
    src = (
        "async def f():\n"
        "    if await x:\n"
        "        return 1\n"
        "    else:\n"
        "        return 2\n"
    )
    if_node = _parse(src)
    assert pattern._is_early_return_candidate(if_node) is False


def test_is_candidate_body_only_return(pattern: EarlyReturnPattern) -> None:
    """Body has Return, orelse has nothing special — still candidate."""
    src = (
        "if x:\n"
        "    return 1\n"
        "else:\n"
        "    y = 2\n"
    )
    if_node = _parse(src)
    # body has return → candidate, regardless of orelse.
    assert pattern._is_early_return_candidate(if_node) is True


# ---------------------------------------------------------------------------
# _is_simple_else
# ---------------------------------------------------------------------------


def test_is_simple_else_empty_is_simple(pattern: EarlyReturnPattern) -> None:
    """Empty orelse → simple (True)."""
    assert pattern._is_simple_else([]) is True


def test_is_simple_else_return(pattern: EarlyReturnPattern) -> None:
    """orelse[0] is Return → simple."""
    src = "return 1"
    node = _parse_stmt(src)
    assert pattern._is_simple_else([node]) is True


def test_is_simple_else_raise(pattern: EarlyReturnPattern) -> None:
    src = "raise ValueError('x')"
    node = _parse_stmt(src)
    assert pattern._is_simple_else([node]) is True


def test_is_simple_else_pass(pattern: EarlyReturnPattern) -> None:
    node = _parse_stmt("pass")
    assert pattern._is_simple_else([node]) is True


def test_is_simple_else_assign_no_call(pattern: EarlyReturnPattern) -> None:
    """Assign with no Call in value → simple."""
    node = _parse_stmt("y = 1 + 2")
    assert pattern._is_simple_else([node]) is True


def test_is_simple_else_assign_with_call(pattern: EarlyReturnPattern) -> None:
    """Assign whose value contains a Call → NOT simple (side effect)."""
    node = _parse_stmt("y = foo()")
    assert pattern._is_simple_else([node]) is False


def test_is_simple_else_nested_if(pattern: EarlyReturnPattern) -> None:
    """Nested If in orelse → simple (returns True)."""
    node = _parse_stmt("if z:\n    return 1")
    assert pattern._is_simple_else([node]) is True


def test_is_simple_else_complex_stmt(pattern: EarlyReturnPattern) -> None:
    """orelse[0] is a complex stmt (e.g. for loop) → not simple."""
    node = _parse_stmt("for i in range(10):\n    pass")
    assert pattern._is_simple_else([node]) is False


def test_is_simple_else_two_stmts(pattern: EarlyReturnPattern) -> None:
    """orelse has 2 statements → not simple."""
    a = _parse_stmt("a = 1")
    b = _parse_stmt("b = 2")
    assert pattern._is_simple_else([a, b]) is False


# ---------------------------------------------------------------------------
# _has_side_effects
# ---------------------------------------------------------------------------


def test_has_side_effects_call(pattern: EarlyReturnPattern) -> None:
    node = _parse_stmt("foo()").value  # type: ignore[attr-defined]
    assert pattern._has_side_effects(node) is True


def test_has_side_effects_nested_call(pattern: EarlyReturnPattern) -> None:
    """A BinOp containing a Call → side effect."""
    node = _parse_stmt("x + foo()").value  # type: ignore[attr-defined]
    assert pattern._has_side_effects(node) is True


def test_has_side_effects_yield(pattern: EarlyReturnPattern) -> None:
    """Yield in expression → side effect."""
    src = "def f():\n    yield 1\n"
    func = ast.parse(src).body[0]
    yield_node = func.body[0].value  # type: ignore[attr-defined]
    assert pattern._has_side_effects(yield_node) is True


def test_has_side_effects_yield_from(pattern: EarlyReturnPattern) -> None:
    src = "def f():\n    yield from gen()\n"
    func = ast.parse(src).body[0]
    yf_node = func.body[0].value  # type: ignore[attr-defined]
    assert pattern._has_side_effects(yf_node) is True


def test_has_side_effects_await(pattern: EarlyReturnPattern) -> None:
    src = "async def f():\n    await x\n"
    func = ast.parse(src).body[0]
    await_node = func.body[0].value  # type: ignore[attr-defined]
    assert pattern._has_side_effects(await_node) is True


def test_no_side_effects_simple_name(pattern: EarlyReturnPattern) -> None:
    node = _parse_stmt("x").value  # type: ignore[attr-defined]
    assert pattern._has_side_effects(node) is False


def test_no_side_effects_literal(pattern: EarlyReturnPattern) -> None:
    node = _parse_stmt("42").value  # type: ignore[attr-defined]
    assert pattern._has_side_effects(node) is False


def test_no_side_effects_binop(pattern: EarlyReturnPattern) -> None:
    node = _parse_stmt("1 + 2").value  # type: ignore[attr-defined]
    assert pattern._has_side_effects(node) is False


# ---------------------------------------------------------------------------
# _estimate_reduction
# ---------------------------------------------------------------------------


def test_estimate_reduction_simple(pattern: EarlyReturnPattern) -> None:
    """No nesting, no BoolOp test → reduction = 1."""
    src = (
        "if x:\n"
        "    return 1\n"
        "else:\n"
        "    return 2\n"
    )
    if_node = _parse(src)
    assert pattern._estimate_reduction(if_node) == 1


def test_estimate_reduction_boolop_test(pattern: EarlyReturnPattern) -> None:
    """BoolOp test → bonus +1."""
    src = (
        "if x and y:\n"
        "    return 1\n"
        "else:\n"
        "    return 2\n"
    )
    if_node = _parse(src)
    assert pattern._estimate_reduction(if_node) >= 2


def test_estimate_reduction_nested_if(pattern: EarlyReturnPattern) -> None:
    """Nested If → contributes via body depth."""
    src = (
        "if x:\n"
        "    if y:\n"
        "        return 1\n"
        "    return 2\n"
        "else:\n"
        "    return 3\n"
    )
    if_node = _parse(src)
    # body = [inner_if, return_2].
    # _get_max_nesting([inner_if, return_2]):
    #   inner_if: body_depth = 1 + get_max_nesting([Return(1)]) = 1.
    #   return_2: nothing.
    #   max_depth = 1.
    # reduction = 1 + max(0, 1-1) + 0 (no BoolOp) = 1.
    assert pattern._estimate_reduction(if_node) == 1


def test_estimate_reduction_deeply_nested(pattern: EarlyReturnPattern) -> None:
    """3-level nested ifs → reduction grows with max body depth."""
    src = (
        "if x:\n"
        "    if y:\n"
        "        if z:\n"
        "            return 1\n"
    )
    if_node = _parse(src)
    # body has one inner_if with body_depth=2 (innermost if + return).
    # reduction = 1 + max(0, 2-1) = 2.
    assert pattern._estimate_reduction(if_node) == 2


# ---------------------------------------------------------------------------
# _get_max_nesting
# ---------------------------------------------------------------------------


def test_max_nesting_empty(pattern: EarlyReturnPattern) -> None:
    assert pattern._get_max_nesting([]) == 0


def test_max_nesting_simple_stmts(pattern: EarlyReturnPattern) -> None:
    """Plain assignments → depth 0."""
    a = _parse_stmt("x = 1")
    b = _parse_stmt("y = 2")
    assert pattern._get_max_nesting([a, b]) == 0


def test_max_nesting_if_only(pattern: EarlyReturnPattern) -> None:
    src = "if x:\n    return 1\n"
    if_node = ast.parse(src).body[0]
    # body has 1 return → depth = 1 + get_max_nesting([return]) = 1 + 0 = 1.
    # No orelse.
    assert pattern._get_max_nesting([if_node]) == 1


def test_max_nesting_if_with_else(pattern: EarlyReturnPattern) -> None:
    """If with else → max(body_depth, else_depth)."""
    src = (
        "if x:\n"
        "    return 1\n"
        "else:\n"
        "    return 2\n"
    )
    if_node = ast.parse(src).body[0]
    assert pattern._get_max_nesting([if_node]) == 1


def test_max_nesting_nested_ifs(pattern: EarlyReturnPattern) -> None:
    """Three levels of nested ifs → max depth = 3."""
    src = (
        "if x:\n"
        "    if y:\n"
        "        if z:\n"
        "            return 1\n"
    )
    tree = ast.parse(src)
    outer = tree.body[0]
    # get_max_nesting([outer]) returns the deepest path:
    # outer → 1 + inner → 1 + innermost → 1 + return = 3
    assert pattern._get_max_nesting([outer]) == 3


def test_max_nesting_for_loop(pattern: EarlyReturnPattern) -> None:
    src = "for i in range(10):\n    return i\n"
    loop = ast.parse(src).body[0]
    # body has return → 1 + get_max_nesting([return]) = 1.
    assert pattern._get_max_nesting([loop]) == 1


def test_max_nesting_while_loop(pattern: EarlyReturnPattern) -> None:
    src = "while x:\n    return 1\n"
    loop = ast.parse(src).body[0]
    assert pattern._get_max_nesting([loop]) == 1


def test_max_nesting_with(pattern: EarlyReturnPattern) -> None:
    src = "with ctx():\n    return 1\n"
    with_stmt = ast.parse(src).body[0]
    assert pattern._get_max_nesting([with_stmt]) == 1


def test_max_nesting_try_with_handlers(pattern: EarlyReturnPattern) -> None:
    """Try with handlers, orelse, finalbody — all branches measured."""
    src = (
        "try:\n"
        "    return 1\n"
        "except Exception:\n"
        "    return 2\n"
        "else:\n"
        "    return 3\n"
        "finally:\n"
        "    return 4\n"
    )
    try_stmt = ast.parse(src).body[0]
    # All branches have return → max depth from each = 1.
    assert pattern._get_max_nesting([try_stmt]) == 1


def test_max_nesting_try_no_finalbody(pattern: EarlyReturnPattern) -> None:
    """Try without finalbody doesn't error."""
    src = (
        "try:\n"
        "    return 1\n"
        "except Exception:\n"
        "    pass\n"
    )
    try_stmt = ast.parse(src).body[0]
    assert pattern._get_max_nesting([try_stmt]) == 1


def test_max_nesting_try_nested_in_handler(pattern: EarlyReturnPattern) -> None:
    """Handler body containing nested try → deeper."""
    src = (
        "try:\n"
        "    pass\n"
        "except Exception:\n"
        "    try:\n"
        "        pass\n"
        "    except Exception:\n"
        "        pass\n"
    )
    try_stmt = ast.parse(src).body[0]
    # handler body has nested try with depth 1.
    # 1 (outer try) + 1 (nested try) = 2.
    assert pattern._get_max_nesting([try_stmt]) == 2


# ---------------------------------------------------------------------------
# estimate_complexity_reduction
# ---------------------------------------------------------------------------


def test_estimate_complexity_reduction_returns_match_field(
    pattern: EarlyReturnPattern,
) -> None:
    """estimate_complexity_reduction returns match.estimated_reduction."""
    from crackerjack.fixers.ast_transform.pattern_matcher import PatternMatch

    match = PatternMatch(
        pattern_name="early_return",
        priority=PatternPriority.EARLY_RETURN,
        line_start=1,
        line_end=2,
        node=ast.parse("pass"),
        estimated_reduction=42,
    )
    assert pattern.estimate_complexity_reduction(match) == 42
