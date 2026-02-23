
import ast
from collections import Counter

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)


class DecomposeConditionalPattern(BasePattern):


    MIN_OPERANDS = 3


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

        condition = None

        if isinstance(node, ast.If):
            condition = node.test
        elif isinstance(node, ast.While):
            condition = node.test
        elif isinstance(node, ast.BoolOp) and len(node.values) >= self.MIN_OPERANDS:

            condition = node

        if condition is None:
            return None


        suggested_extractions = self._find_extraction_candidates(condition)
        if not suggested_extractions:
            return None


        if self._has_side_effects(condition):
            return None


        reduction = self._estimate_reduction(condition, suggested_extractions)


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
        candidates = []


        if isinstance(condition, ast.BoolOp):

            for operand in condition.values:
                if self._is_extractable_operand(operand):
                    var_name = self._generate_variable_name(operand)
                    candidates.append((var_name, operand))


        for node in ast.walk(condition):
            if isinstance(node, ast.BoolOp) and node is not condition:
                if len(node.values) >= 2:
                    var_name = self._generate_variable_name(node)
                    candidates.append((var_name, node))
                    break


        repeated = self._find_repeated_subexpressions(condition)
        for expr, _ in repeated:
            var_name = self._generate_variable_name(expr)
            candidates.append((var_name, expr))


        if self._is_demorgan_candidate(condition):

            var_name = self._generate_variable_name(condition)
            candidates.append((var_name, condition))


        seen = set()
        unique_candidates = []
        for candidate in candidates:
            expr_str = ast.dump(candidate[1])
            if expr_str not in seen:
                seen.add(expr_str)
                unique_candidates.append(candidate)

        return unique_candidates

    def _is_extractable_operand(self, operand: ast.expr) -> bool:

        if isinstance(operand, ast.Name):
            return False


        if isinstance(operand, ast.Attribute):

            depth = self._get_attribute_depth(operand)
            return depth >= 2


        if isinstance(operand, ast.Compare):
            return self._calculate_complexity_score(operand) >= 2


        if isinstance(operand, ast.BoolOp):
            return True


        if isinstance(operand, ast.UnaryOp):
            return self._calculate_complexity_score(operand.operand) >= 2


        if isinstance(operand, ast.Call):
            return True


        if isinstance(operand, ast.Subscript):
            return True

        return False

    def _get_attribute_depth(self, node: ast.expr) -> int:
        if isinstance(node, ast.Attribute):
            return 1 + self._get_attribute_depth(node.value)
        return 1

    def _generate_variable_name(self, expr: ast.expr) -> str:

        if isinstance(expr, ast.Compare):
            if len(expr.ops) == 1:
                left_name = self._get_expr_name(expr.left)
                op_name = self._get_op_name(expr.ops[0])
                right_name = self._get_expr_name(expr.comparators[0])
                return f"{left_name}_{op_name}_{right_name}"


        if isinstance(expr, ast.Attribute):
            return expr.attr


        if isinstance(expr, ast.BoolOp):
            op_type = "and" if isinstance(expr.op, ast.And) else "or"
            return f"is_{op_type}_condition"


        if isinstance(expr, ast.UnaryOp):
            if isinstance(expr.op, ast.Not):
                inner_name = self._get_expr_name(expr.operand)
                return f"is_not_{inner_name}"


        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Attribute):
                return f"{expr.func.attr}_result"
            if isinstance(expr.func, ast.Name):
                return f"{expr.func.id}_result"


        return "condition"

    def _get_expr_name(self, expr: ast.expr) -> str:
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
        expr_counts: Counter[str] = Counter()
        expr_map: dict[str, ast.expr] = {}

        for node in ast.walk(condition):

            if isinstance(node, ast.Name | ast.Constant):
                continue


            if not isinstance(node, ast.expr):
                continue

            expr_str = ast.dump(node)


            if self._calculate_complexity_score(node) >= 2:
                expr_counts[expr_str] += 1
                expr_map[expr_str] = node


        repeated = []
        for expr_str, count in expr_counts.items():
            if count >= 2:
                repeated.append((expr_map[expr_str], count))

        return repeated

    def _is_demorgan_candidate(self, condition: ast.expr) -> bool:
        if isinstance(condition, ast.UnaryOp) and isinstance(condition.op, ast.Not):
            operand = condition.operand
            if isinstance(operand, ast.BoolOp):

                return len(operand.values) >= 2
        return False

    def _has_side_effects(self, node: ast.expr) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                return True
            if isinstance(child, ast.Yield | ast.YieldFrom | ast.Await):
                return True
        return False

    def _count_operands(self, condition: ast.expr) -> int:
        if isinstance(condition, ast.BoolOp):
            return len(condition.values)
        return 1

    def _calculate_complexity_score(self, node: ast.expr) -> int:
        score = 0.0

        for child in ast.walk(node):

            if isinstance(child, ast.BoolOp):
                score += len(child.values)


            elif isinstance(child, ast.Compare):
                score += len(child.ops)


            elif isinstance(child, ast.UnaryOp):
                score += 1


            elif isinstance(child, ast.Attribute):
                score += 0.5


            elif isinstance(child, ast.Subscript):
                score += 1


            elif isinstance(child, ast.Call):
                score += 2

        return int(score)

    def _estimate_reduction(
        self, condition: ast.expr, extractions: list[tuple[str, ast.expr]]
    ) -> int:
        base_score = self._calculate_complexity_score(condition)


        extraction_savings = len(extractions)


        repeated = self._find_repeated_subexpressions(condition)
        repeated_bonus = len(repeated)


        demorgan_bonus = 1 if self._is_demorgan_candidate(condition) else 0


        reduction = extraction_savings + repeated_bonus + demorgan_bonus


        if base_score >= 6:
            reduction += 1
        if base_score >= 10:
            reduction += 1

        return max(1, reduction)

    def estimate_complexity_reduction(self, match: PatternMatch) -> int:
        return match.estimated_reduction
