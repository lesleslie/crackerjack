"""Decompose Conditional pattern for reducing cognitive complexity.

The Decompose Conditional pattern breaks down complex boolean expressions
into simpler, named sub-expressions that are easier to understand.

Example transformation:
    # Before (complexity 5)
    def process(data):
        if (data.is_valid and data.status == "active" and
            data.permissions and "write" in data.permissions and
            not data.is_locked):
            return perform_action(data)

    # After (complexity 2)
    def process(data):
        is_active_and_valid = data.is_valid and data.status == "active"
        has_write_permission = data.permissions and "write" in data.permissions
        if is_active_and_valid and has_write_permission and not data.is_locked:
            return perform_action(data)
"""

import ast
from collections import Counter

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)


class DecomposeConditionalPattern(BasePattern):
    """Pattern that matches complex conditions suitable for decomposition.

    Matches when:
    - BoolOp (and/or) chains with 3+ operands
    - Nested comparisons that can be extracted into variables
    - Repeated sub-expressions
    - Negated complex expressions (De Morgan's law candidates)

    Does NOT match:
    - Simple comparisons (a > b)
    - Single boolean checks
    - Conditions with side effects
    """

    # Minimum number of BoolOp operands to consider for decomposition
    MIN_OPERANDS = 3

    # Minimum expression complexity score to consider
    MIN_COMPLEXITY_SCORE = 4

    @property
    def name(self) -> str:
        return "decompose_conditional"

    @property
    def priority(self) -> PatternPriority:
        return PatternPriority.DECOMPOSE_CONDITIONAL

    @property
    def supports_async(self) -> bool:
        return True

    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:
        """Check if this node contains a complex condition that can be decomposed.

        Looks for:
        1. If statements with complex BoolOp conditions
        2. While loops with complex conditions
        3. Complex conditions with repeated sub-expressions
        4. Deeply nested boolean operations
        """
        # Find condition-bearing nodes
        condition = None

        if isinstance(node, ast.If):
            condition = node.test
        elif isinstance(node, ast.While):
            condition = node.test
        elif isinstance(node, ast.BoolOp) and len(node.values) >= self.MIN_OPERANDS:
            # Standalone BoolOp (might be part of assignment or other expression)
            condition = node

        if condition is None:
            return None

        # Check for decomposition candidates
        suggested_extractions = self._find_extraction_candidates(condition)
        if not suggested_extractions:
            return None

        # Check for side effects
        if self._has_side_effects(condition):
            return None

        # Calculate estimated complexity reduction
        reduction = self._estimate_reduction(condition, suggested_extractions)

        # Get line information
        line_start = node.lineno if hasattr(node, "lineno") else 1
        line_end = (
            node.end_lineno
            if hasattr(node, "end_lineno") and node.end_lineno
            else line_start
        )

        return PatternMatch(
            pattern_name=self.name,
            priority=self.priority,
            line_start=line_start,
            line_end=line_end,
            node=node,
            match_info={
                "type": "decompose_conditional",
                "condition": condition,
                "suggested_extractions": suggested_extractions,
                "estimated_reduction": reduction,
            },
            estimated_reduction=reduction,
            context={
                "operand_count": self._count_operands(condition),
                "complexity_score": self._calculate_complexity_score(condition),
                "has_repeated_expressions": len(
                    self._find_repeated_subexpressions(condition)
                )
                > 0,
                "is_demorgan_candidate": self._is_demorgan_candidate(condition),
            },
        )

    def _find_extraction_candidates(
        self, condition: ast.expr
    ) -> list[tuple[str, ast.expr]]:
        """Find sub-expressions that could be extracted into named variables.

        Returns list of (variable_name, sub_expression) tuples.
        """
        candidates = []

        # Check for complex BoolOp chains
        if isinstance(condition, ast.BoolOp):
            # Extract complex operands from the chain
            for operand in condition.values:
                if self._is_extractable_operand(operand):
                    var_name = self._generate_variable_name(operand)
                    candidates.append((var_name, operand))

        # Check for nested boolean operations
        for node in ast.walk(condition):
            if isinstance(node, ast.BoolOp) and node is not condition:
                if len(node.values) >= 2:
                    var_name = self._generate_variable_name(node)
                    candidates.append((var_name, node))
                    break  # Only suggest one nested extraction at a time

        # Check for repeated sub-expressions
        repeated = self._find_repeated_subexpressions(condition)
        for expr, _ in repeated:
            var_name = self._generate_variable_name(expr)
            candidates.append((var_name, expr))

        # Check for De Morgan's law candidates (not (a and b) -> not a or not b)
        if self._is_demorgan_candidate(condition):
            # The whole expression is a candidate
            var_name = self._generate_variable_name(condition)
            candidates.append((var_name, condition))

        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            expr_str = ast.dump(candidate[1])
            if expr_str not in seen:
                seen.add(expr_str)
                unique_candidates.append(candidate)

        return unique_candidates

    def _is_extractable_operand(self, operand: ast.expr) -> bool:
        """Check if an operand is complex enough to warrant extraction."""
        # Simple names are not worth extracting
        if isinstance(operand, ast.Name):
            return False

        # Simple attributes might not be worth it
        if isinstance(operand, ast.Attribute):
            # But complex chains like a.b.c.d are
            depth = self._get_attribute_depth(operand)
            return depth >= 2

        # Comparisons with complex sides
        if isinstance(operand, ast.Compare):
            return self._calculate_complexity_score(operand) >= 2

        # BoolOp (nested and/or)
        if isinstance(operand, ast.BoolOp):
            return True

        # Unary operations on complex expressions
        if isinstance(operand, ast.UnaryOp):
            return self._calculate_complexity_score(operand.operand) >= 2

        # Calls are complex
        if isinstance(operand, ast.Call):
            return True

        # Subscripts
        if isinstance(operand, ast.Subscript):
            return True

        return False

    def _get_attribute_depth(self, node: ast.expr) -> int:
        """Get the depth of an attribute chain (a.b.c = 3)."""
        if isinstance(node, ast.Attribute):
            return 1 + self._get_attribute_depth(node.value)
        return 1

    def _generate_variable_name(self, expr: ast.expr) -> str:
        """Generate a descriptive variable name for an expression."""
        # Handle comparisons
        if isinstance(expr, ast.Compare):
            if len(expr.ops) == 1:
                left_name = self._get_expr_name(expr.left)
                op_name = self._get_op_name(expr.ops[0])
                right_name = self._get_expr_name(expr.comparators[0])
                return f"{left_name}_{op_name}_{right_name}"

        # Handle attribute access
        if isinstance(expr, ast.Attribute):
            return expr.attr

        # Handle BoolOp
        if isinstance(expr, ast.BoolOp):
            op_type = "and" if isinstance(expr.op, ast.And) else "or"
            return f"is_{op_type}_condition"

        # Handle UnaryOp
        if isinstance(expr, ast.UnaryOp):
            if isinstance(expr.op, ast.Not):
                inner_name = self._get_expr_name(expr.operand)
                return f"is_not_{inner_name}"

        # Handle Call
        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Attribute):
                return f"{expr.func.attr}_result"
            if isinstance(expr.func, ast.Name):
                return f"{expr.func.id}_result"

        # Default
        return "condition"

    def _get_expr_name(self, expr: ast.expr) -> str:
        """Get a simple name representation of an expression."""
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            return expr.attr
        if isinstance(expr, ast.Constant):
            return str(expr.value).lower().replace(" ", "_")
        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name):
                return expr.func.id
            if isinstance(expr.func, ast.Attribute):
                return expr.func.attr
        return "value"

    def _get_op_name(self, op: ast.cmpop) -> str:
        """Get a readable name for a comparison operator."""
        op_names = {
            ast.Eq: "eq",
            ast.NotEq: "ne",
            ast.Lt: "lt",
            ast.LtE: "lte",
            ast.Gt: "gt",
            ast.GtE: "gte",
            ast.Is: "is",
            ast.IsNot: "is_not",
            ast.In: "in",
            ast.NotIn: "not_in",
        }
        return op_names.get(type(op), "cmp")

    def _find_repeated_subexpressions(
        self, condition: ast.expr
    ) -> list[tuple[ast.expr, int]]:
        """Find sub-expressions that appear multiple times."""
        expr_counts: Counter[str] = Counter()
        expr_map: dict[str, ast.expr] = {}

        for node in ast.walk(condition):
            # Skip simple names and constants
            if isinstance(node, ast.Name | ast.Constant):
                continue

            # Only consider expression nodes
            if not isinstance(node, ast.expr):
                continue

            expr_str = ast.dump(node)

            # Only track expressions with some complexity
            if self._calculate_complexity_score(node) >= 2:
                expr_counts[expr_str] += 1
                expr_map[expr_str] = node

        # Return expressions that appear more than once
        repeated = []
        for expr_str, count in expr_counts.items():
            if count >= 2:
                repeated.append((expr_map[expr_str], count))

        return repeated

    def _is_demorgan_candidate(self, condition: ast.expr) -> bool:
        """Check if condition is a candidate for De Morgan's law transformation.

        Matches patterns like:
        - not (a and b) -> could be (not a) or (not b)
        - not (a or b) -> could be (not a) and (not b)
        """
        if isinstance(condition, ast.UnaryOp) and isinstance(condition.op, ast.Not):
            operand = condition.operand
            if isinstance(operand, ast.BoolOp):
                # Check if the inner BoolOp has complex enough operands
                return len(operand.values) >= 2
        return False

    def _has_side_effects(self, node: ast.expr) -> bool:
        """Check if expression has side effects."""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                return True
            if isinstance(child, ast.Yield | ast.YieldFrom | ast.Await):
                return True
        return False

    def _count_operands(self, condition: ast.expr) -> int:
        """Count operands in a boolean expression."""
        if isinstance(condition, ast.BoolOp):
            return len(condition.values)
        return 1

    def _calculate_complexity_score(self, node: ast.expr) -> int:
        """Calculate a complexity score for an expression.

        Factors:
        - Number of operators
        - Nesting depth
        - Number of different names involved
        """
        score = 0.0

        for child in ast.walk(node):
            # BoolOp adds complexity
            if isinstance(child, ast.BoolOp):
                score += len(child.values)

            # Comparisons add complexity
            elif isinstance(child, ast.Compare):
                score += len(child.ops)

            # Unary operations add complexity
            elif isinstance(child, ast.UnaryOp):
                score += 1

            # Attribute chains add complexity
            elif isinstance(child, ast.Attribute):
                score += 0.5

            # Subscripts add complexity
            elif isinstance(child, ast.Subscript):
                score += 1

            # Calls add complexity
            elif isinstance(child, ast.Call):
                score += 2

        return int(score)

    def _estimate_reduction(
        self, condition: ast.expr, extractions: list[tuple[str, ast.expr]]
    ) -> int:
        """Estimate complexity reduction from decomposition.

        Heuristic:
        - Each extraction reduces cognitive load
        - More complex conditions benefit more
        """
        base_score = self._calculate_complexity_score(condition)

        # Each extraction saves some cognitive complexity
        extraction_savings = len(extractions)

        # Bonus for extracting repeated expressions
        repeated = self._find_repeated_subexpressions(condition)
        repeated_bonus = len(repeated)

        # Bonus for De Morgan candidates
        demorgan_bonus = 1 if self._is_demorgan_candidate(condition) else 0

        # Calculate total reduction
        reduction = extraction_savings + repeated_bonus + demorgan_bonus

        # Scale based on base complexity
        if base_score >= 6:
            reduction += 1
        if base_score >= 10:
            reduction += 1

        return max(1, reduction)

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        """Return the estimated complexity reduction for this match."""
        return match.estimated_reduction
