
import ast

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)


class GuardClausePattern(BasePattern):

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

        if not isinstance(node, ast.If):
            return None


        if not self._is_validation_condition(node.test):
            return None


        if not self._has_nested_validation(node):
            return None


        if self._has_walrus_operator(node):
            return None


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

        if isinstance(condition, ast.Compare):
            return self._is_validation_comparison(condition)


        if isinstance(condition, ast.Name):
            return True


        if isinstance(condition, ast.UnaryOp) and isinstance(condition.op, ast.Not):
            return isinstance(condition.operand, ast.Name | ast.Attribute)


        if isinstance(condition, ast.Attribute):
            return condition.attr.lower() in self.VALIDATION_ATTRS


        if isinstance(condition, ast.BoolOp):
            return all(self._is_validation_condition(v) for v in condition.values)

        return False

    def _is_validation_comparison(self, condition: ast.Compare) -> bool:
        for op, comparator in zip(condition.ops, condition.comparators):

            if isinstance(op, ast.Is | ast.IsNot | ast.Eq | ast.NotEq):
                if isinstance(comparator, ast.Constant) and comparator.value is None:
                    return True


            if isinstance(op, ast.In | ast.NotIn):
                return True


            if isinstance(op, ast.Gt | ast.GtE | ast.Lt | ast.LtE):
                if isinstance(comparator, ast.Constant):
                    if isinstance(comparator.value, int | float):
                        return True

        return False

    def _has_nested_validation(self, node: ast.If) -> bool:

        for child in node.body:
            if isinstance(child, ast.If):

                if self._is_validation_condition(child.test):
                    return True

            for descendant in ast.walk(child):
                if isinstance(descendant, ast.If):
                    if self._is_validation_condition(descendant.test):
                        return True
        return False

    def _has_walrus_operator(self, node: ast.If) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.NamedExpr):
                return True
        return False

    def _estimate_reduction(self, node: ast.If) -> int:

        depth = self._get_nesting_depth(node)

        return max(1, depth - 1)

    def _get_nesting_depth(self, node: ast.If, current_depth: int = 0) -> int:
        max_depth = current_depth

        for child in node.body:
            if isinstance(child, ast.If) and self._is_validation_condition(child.test):
                child_depth = self._get_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)

        return max_depth

    def _count_validations(self, node: ast.If) -> int:
        count = 1

        for child in node.body:
            if isinstance(child, ast.If) and self._is_validation_condition(child.test):
                count += self._count_validations(child)
                break

        return count

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        return match.estimated_reduction
