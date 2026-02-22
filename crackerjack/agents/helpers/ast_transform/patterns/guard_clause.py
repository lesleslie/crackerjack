"""Guard Clause pattern for reducing cognitive complexity.

The Guard Clause pattern converts nested validation checks at the
start of functions into flat guard returns.

Example transformation:
    # Before (complexity 4)
    def process(data):
        if data is not None:
            if data.valid:
                if data.value > 0:
                    return process_value(data.value)
        return None

    # After (complexity 1)
    def process(data):
        if data is None:
            return None
        if not data.valid:
            return None
        if data.value <= 0:
            return None
        return process_value(data.value)
"""

import ast

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)


class GuardClausePattern(BasePattern):
    """Pattern that matches validation chains suitable for guard clauses.

    Matches when:
    - There are consecutive if statements at function start
    - Each if contains validation logic (checking for None, empty, invalid)
    - The body returns or raises on invalid conditions

    Does NOT match:
    - Single if statements (use EarlyReturnPattern)
    - If statements with complex else bodies
    - Code with walrus operator assignments in conditions
    """

    @property
    def name(self) -> str:
        return "guard_clause"

    @property
    def priority(self) -> PatternPriority:
        return PatternPriority.GUARD_CLAUSE

    @property
    def supports_async(self) -> bool:
        return True

    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:
        """Check if this node is part of a validation chain for guard clauses.

        Looks for:
        1. Nested if statements that check conditions
        2. Patterns like "if x is not None" or "if x.valid"
        3. Deep nesting that could be flattened
        """
        # Only match if statements
        if not isinstance(node, ast.If):
            return None

        # Check if this is a validation-style condition
        if not self._is_validation_condition(node.test):
            return None

        # Check if this has nested validation (potential for flattening)
        if not self._has_nested_validation(node):
            return None

        # Check for walrus operator conflicts
        if self._has_walrus_operator(node):
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
                "type": "guard_clause",
                "if_node": node,
                "condition": node.test,
                "body": node.body,
                "orelse": node.orelse,
            },
            estimated_reduction=reduction,
            context={
                "nesting_depth": self._get_nesting_depth(node),
                "validation_count": self._count_validations(node),
            },
        )

    # Common validation attribute names
    VALIDATION_ATTRS = frozenset(
        (
            "valid",
            "enabled",
            "active",
            "ready",
            "ok",
            "success",
            "exists",
            "available",
        )
    )

    def _is_validation_condition(self, condition: ast.expr) -> bool:
        """Check if a condition looks like a validation check."""
        # Handle comparisons first
        if isinstance(condition, ast.Compare):
            return self._is_validation_comparison(condition)

        # x (truthy check)
        if isinstance(condition, ast.Name):
            return True

        # not x / not x.attr
        if isinstance(condition, ast.UnaryOp) and isinstance(condition.op, ast.Not):
            return isinstance(condition.operand, ast.Name | ast.Attribute)

        # x.attr where attr is validation-like
        if isinstance(condition, ast.Attribute):
            return condition.attr.lower() in self.VALIDATION_ATTRS

        # BoolOp with validation-like components
        if isinstance(condition, ast.BoolOp):
            return all(self._is_validation_condition(v) for v in condition.values)

        return False

    def _is_validation_comparison(self, condition: ast.Compare) -> bool:
        """Check if a comparison is a validation pattern."""
        for op, comparator in zip(condition.ops, condition.comparators):
            # x is None / x is not None / x == None / x != None
            if isinstance(op, ast.Is | ast.IsNot | ast.Eq | ast.NotEq):
                if isinstance(comparator, ast.Constant) and comparator.value is None:
                    return True

            # x in values / x not in values
            if isinstance(op, ast.In | ast.NotIn):
                return True

            # len(x) > 0 style checks
            if isinstance(op, ast.Gt | ast.GtE | ast.Lt | ast.LtE):
                if isinstance(comparator, ast.Constant):
                    if isinstance(comparator.value, int | float):
                        return True

        return False

    def _has_nested_validation(self, node: ast.If) -> bool:
        """Check if the if statement has nested validation logic."""
        # Look for nested if statements in the body
        for child in node.body:
            if isinstance(child, ast.If):
                # Check if the nested if is also a validation
                if self._is_validation_condition(child.test):
                    return True
            # Check inside other statements
            for descendant in ast.walk(child):
                if isinstance(descendant, ast.If):
                    if self._is_validation_condition(descendant.test):
                        return True
        return False

    def _has_walrus_operator(self, node: ast.If) -> bool:
        """Check if the condition or body uses walrus operator (:=)."""
        for child in ast.walk(node):
            if isinstance(child, ast.NamedExpr):
                return True
        return False

    def _estimate_reduction(self, node: ast.If) -> int:
        """Estimate complexity reduction from applying guard clauses."""
        # Count nesting levels that will be eliminated
        depth = self._get_nesting_depth(node)
        # Each level of nesting contributes to cognitive complexity
        return max(1, depth - 1)

    def _get_nesting_depth(self, node: ast.If, current_depth: int = 0) -> int:
        """Get maximum nesting depth of validation checks."""
        max_depth = current_depth

        for child in node.body:
            if isinstance(child, ast.If) and self._is_validation_condition(child.test):
                child_depth = self._get_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)

        return max_depth

    def _count_validations(self, node: ast.If) -> int:
        """Count the number of validation checks in the chain."""
        count = 1  # Current node

        for child in node.body:
            if isinstance(child, ast.If) and self._is_validation_condition(child.test):
                count += self._count_validations(child)
                break  # Only count the first nested if (the chain)

        return count

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        """Return the estimated complexity reduction for this match."""
        return match.estimated_reduction
