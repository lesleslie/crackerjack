"""Early Return pattern for reducing cognitive complexity.

The Early Return pattern converts nested if-else structures into
flat code by using guard returns at the start of functions.

Example transformation:
    # Before (complexity 4)
    def process(data):
        if data:
            if data.valid:
                return data.value
            else:
                return None
        return None

    # After (complexity 2)
    def process(data):
        if not data:
            return None
        if not data.valid:
            return None
        return data.value
"""

import ast

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)


class EarlyReturnPattern(BasePattern):
    """Pattern that matches nested conditionals suitable for early returns.

    Matches when:
    - There's an if statement with an else clause
    - The else clause contains a return or is simple
    - Converting to early return would reduce complexity

    Does NOT match:
    - Simple if statements without else
    - If-elif chains (use DecomposeConditionalPattern)
    - Code with side effects in conditions
    """

    @property
    def name(self) -> str:
        return "early_return"

    @property
    def priority(self) -> PatternPriority:
        return PatternPriority.EARLY_RETURN

    @property
    def supports_async(self) -> bool:
        return True  # Pattern works the same for async functions

    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:
        """Check if this node can be converted to early return pattern.

        Looks for:
        1. If statements with else clauses
        2. Nested if statements where inner has return
        3. Long if bodies that could be simplified
        """
        # Only match if statements
        if not isinstance(node, ast.If):
            return None

        # Must have an else clause
        if not node.orelse:
            return None

        # Check if this is a good candidate for early return
        if not self._is_early_return_candidate(node):
            return None

        # Calculate estimated complexity reduction
        reduction = self._estimate_reduction(node)

        return PatternMatch(
            pattern_name=self.name,
            priority=self.priority,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            node=node,
            match_info={
                "type": "early_return",
                "if_node": node,
                "condition": node.test,
                "body": node.body,
                "orelse": node.orelse,
            },
            estimated_reduction=reduction,
            context={
                "body_length": len(node.body),
                "orelse_length": len(node.orelse),
                "has_nested_if": any(isinstance(n, ast.If) for n in ast.walk(node)),
            },
        )

    def _is_early_return_candidate(self, node: ast.If) -> bool:
        """Check if an if statement is a good early return candidate.

        Good candidates:
        - Has else clause that's simple (return, raise, simple assignment)
        - Body is complex enough to benefit from flattening
        - No side effects in condition
        """
        # Check body complexity - need at least some substance
        if len(node.body) < 1:
            return False

        # Check else clause - should be simple
        if not self._is_simple_else(node.orelse):
            return False

        # Check for side effects in condition
        if self._has_side_effects(node.test):
            return False

        # Check if body has returns (common pattern)
        body_has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))

        # Check if else has returns
        else_has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))

        # At least one branch should have a return for this to make sense
        return body_has_return or else_has_return

    def _is_simple_else(self, orelse: list[ast.stmt]) -> bool:
        """Check if else clause is simple enough to convert.

        Simple else clauses:
        - Single return statement
        - Single raise statement
        - Single simple assignment
        - Another if statement (elif chain - handled differently)
        """
        if len(orelse) == 0:
            return True

        if len(orelse) == 1:
            stmt = orelse[0]
            # Single return/raise is simple
            if isinstance(stmt, ast.Return | ast.Raise):
                return True
            # Single pass is simple
            if isinstance(stmt, ast.Pass):
                return True
            # Simple assignment is ok
            if isinstance(stmt, ast.Assign) and not any(
                isinstance(n, ast.Call) for n in ast.walk(stmt.value)
            ):
                return True
            # Nested if is handled by recursive matching
            if isinstance(stmt, ast.If):
                return True

        return False

    def _has_side_effects(self, node: ast.expr) -> bool:
        """Check if expression has side effects.

        Expressions with side effects:
        - Function calls
        - Attribute assignments
        - Yield/await expressions
        """
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                return True
            if isinstance(child, ast.Yield | ast.YieldFrom | ast.Await):
                return True
        return False

    def _estimate_reduction(self, node: ast.If) -> int:
        """Estimate complexity reduction from applying early return.

        Rough heuristic:
        - Each nested level eliminated = 1 point
        - Each else clause eliminated = 1 point
        - Branch simplification = 1 point
        """
        reduction = 1  # Base reduction for eliminating else

        # Count nesting levels in body
        max_depth = self._get_max_nesting(node.body)
        reduction += max(0, max_depth - 1)  # 1 point per eliminated nesting level

        # Bonus for simplifying complex conditions
        if isinstance(node.test, ast.BoolOp):
            reduction += 1

        return reduction

    def _get_max_nesting(self, stmts: list[ast.stmt]) -> int:
        """Get maximum nesting depth in statements."""
        max_depth = 0
        for stmt in stmts:
            if isinstance(stmt, ast.If):
                body_depth = 1 + self._get_max_nesting(stmt.body)
                else_depth = self._get_max_nesting(stmt.orelse) if stmt.orelse else 0
                max_depth = max(max_depth, body_depth, else_depth)
            elif isinstance(stmt, ast.For | ast.While):
                body_depth = 1 + self._get_max_nesting(stmt.body)
                else_depth = self._get_max_nesting(stmt.orelse) if stmt.orelse else 0
                max_depth = max(max_depth, body_depth, else_depth)
            elif isinstance(stmt, ast.With):
                body_depth = 1 + self._get_max_nesting(stmt.body)
                max_depth = max(max_depth, body_depth)
            elif isinstance(stmt, ast.Try):
                for handler in stmt.handlers:
                    handler_depth = 1 + self._get_max_nesting(handler.body)
                    max_depth = max(max_depth, handler_depth)
                if stmt.orelse:
                    else_depth = self._get_max_nesting(stmt.orelse)
                    max_depth = max(max_depth, else_depth)
                if stmt.finalbody:
                    final_depth = self._get_max_nesting(stmt.finalbody)
                    max_depth = max(max_depth, final_depth)
        return max_depth

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        """Return the estimated complexity reduction for this match."""
        return match.estimated_reduction
