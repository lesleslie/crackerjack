import ast

from crackerjack.agents.helpers.ast_transform.pattern_matcher import (
    BasePattern,
    PatternMatch,
    PatternPriority,
)


class EarlyReturnPattern(BasePattern):
    @property
    def name(self) -> str:
        return "early_return"

    @property
    def priority(self) -> PatternPriority:
        return PatternPriority.EARLY_RETURN

    @property
    def supports_async(self) -> bool:
        return True

    def match(self, node: ast.AST, source_lines: list[str]) -> PatternMatch | None:

        if not isinstance(node, ast.If):
            return None

        if not node.orelse:
            return None

        if not self._is_early_return_candidate(node):
            return None

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

        if len(node.body) < 1:
            return False

        if not self._is_simple_else(node.orelse):
            return False

        if self._has_side_effects(node.test):
            return False

        body_has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))

        else_has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))

        return body_has_return or else_has_return

    def _is_simple_else(self, orelse: list[ast.stmt]) -> bool:
        if len(orelse) == 0:
            return True

        if len(orelse) == 1:
            stmt = orelse[0]

            if isinstance(stmt, ast.Return | ast.Raise):
                return True

            if isinstance(stmt, ast.Pass):
                return True

            if isinstance(stmt, ast.Assign) and not any(
                isinstance(n, ast.Call) for n in ast.walk(stmt.value)
            ):
                return True

            if isinstance(stmt, ast.If):
                return True

        return False

    def _has_side_effects(self, node: ast.expr) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                return True
            if isinstance(child, ast.Yield | ast.YieldFrom | ast.Await):
                return True
        return False

    def _estimate_reduction(self, node: ast.If) -> int:
        reduction = 1

        max_depth = self._get_max_nesting(node.body)
        reduction += max(0, max_depth - 1)

        if isinstance(node.test, ast.BoolOp):
            reduction += 1

        return reduction

    def _get_max_nesting(self, stmts: list[ast.stmt]) -> int:
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
        return match.estimated_reduction
