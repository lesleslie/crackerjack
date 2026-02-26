from pathlib import Path

import libcst as cst

from crackerjack.agents.helpers.ast_transform.surgeons.base import (
    BaseSurgeon,
    TransformResult,
)


class EarlyReturnTransformer(cst.CSTTransformer):
    def __init__(self) -> None:
        self.made_changes = False

    def leave_If(
        self,
        original_node: cst.If,
        updated_node: cst.If,
    ) -> cst.If | cst.FlattenSentinel[cst.BaseStatement]:

        if not updated_node.orelse:
            return updated_node

        else_body = updated_node.orelse
        if not self._is_simple_else(else_body):  # type: ignore[arg-type]
            return updated_node

        if isinstance(else_body, cst.Else) and len(else_body.body.body) == 1:
            inner_stmt = else_body.body.body[0]

            if isinstance(inner_stmt, cst.If):
                return updated_node

            if (
                isinstance(inner_stmt, cst.SimpleStatementLine)
                and len(inner_stmt.body) == 1
            ):
                if isinstance(inner_stmt.body[0], cst.If):
                    return updated_node

        negated_test = self._negate_condition(updated_node.test)

        if isinstance(else_body, cst.Else):
            else_block = else_body.body
        else:
            else_block = cst.IndentedBlock(body=else_body)  # type: ignore[arg-type]

        early_return_if = cst.If(
            test=negated_test,
            body=else_block,
        )

        original_body = updated_node.body.body

        self.made_changes = True

        return cst.FlattenSentinel([early_return_if, *original_body])  # type: ignore[list-item]

    def _is_simple_else(self, orelse: cst.BaseSuite | None) -> bool:
        if orelse is None:
            return False

        if isinstance(orelse, cst.Else):
            body = orelse.body.body  # type: ignore[union-attr]
        else:
            return False

        if not body:
            return True

        if len(body) == 1:
            stmt = body[0]

            if isinstance(stmt, cst.SimpleStatementLine) and len(stmt.body) == 1:
                inner = stmt.body[0]

                if isinstance(inner, cst.Return | cst.Raise | cst.Pass):
                    return True

                if isinstance(inner, cst.AnnAssign | cst.Assign | cst.AugAssign):
                    return True

        return False

    def _negate_condition(self, condition: cst.BaseExpression) -> cst.BaseExpression:

        if isinstance(condition, cst.UnaryOperation) and isinstance(
            condition.operator, cst.Not
        ):
            return condition.expression

        if isinstance(condition, cst.Comparison):
            return self._negate_comparison(condition)

        if isinstance(condition, cst.BooleanOperation):
            return self._apply_de_morgan(condition)

        return cst.UnaryOperation(
            operator=cst.Not(),
            expression=cst.ensure_type(condition, cst.BaseExpression),
        )

    def _negate_comparison(self, comp: cst.Comparison) -> cst.Comparison:
        negated_targets: list[cst.ComparisonTarget] = []
        for target in comp.comparisons:
            if isinstance(target.operator, cst.Equal):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.NotEqual(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.NotEqual):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.Equal(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.LessThan):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.GreaterThanEqual(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.GreaterThan):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.LessThanEqual(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.LessThanEqual):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.GreaterThan(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.GreaterThanEqual):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.LessThan(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.Is):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.IsNot(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.IsNot):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.Is(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.In):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.NotIn(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.NotIn):
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.In(),
                        comparator=target.comparator,
                    )
                )

            return cst.UnaryOperation(  # type: ignore[return-value]
                operator=cst.Not(),
                expression=comp,
            )

        return cst.Comparison(
            left=comp.left,
            comparisons=negated_targets,
        )

    def _apply_de_morgan(self, boolop: cst.BooleanOperation) -> cst.BaseExpression:

        left = self._negate_condition(boolop.left)
        right = self._negate_condition(boolop.right)

        if isinstance(boolop.operator, cst.And):
            new_op = cst.Or()
        else:
            new_op = cst.And()

        return cst.BooleanOperation(
            left=left,
            operator=new_op,
            right=right,
        )


class GuardClauseTransformer(cst.CSTTransformer):
    def __init__(self) -> None:
        self.made_changes = False

    def leave_If(
        self,
        original_node: cst.If,
        updated_node: cst.If,
    ) -> cst.If | cst.FlattenSentinel[cst.BaseStatement]:

        if not self._is_validation_pattern(updated_node):
            return updated_node

        body_stmts = list(updated_node.body.body)
        if not body_stmts:
            return updated_node

        first_stmt = body_stmts[0]

        if isinstance(first_stmt, cst.If) and self._is_validation_pattern(first_stmt):
            negated_test = self._negate_condition(updated_node.test)

            default_return = self._get_default_return(first_stmt)

            guard_if = cst.If(
                test=negated_test,
                body=cst.IndentedBlock(
                    body=[
                        cst.SimpleStatementLine(
                            body=[default_return],
                        ),
                    ],
                ),
            )

            self.made_changes = True

            return cst.FlattenSentinel([guard_if, *body_stmts])  # type: ignore[list-item]

        if not updated_node.orelse:
            if self._body_ends_with_return(updated_node.body):
                return updated_node

        return updated_node

    def _is_validation_pattern(self, node: cst.If) -> bool:

        test = node.test

        if isinstance(test, cst.Comparison):
            for target in test.comparisons:
                if isinstance(target.operator, cst.Is | cst.IsNot):
                    return True
                if isinstance(target.operator, cst.Equal | cst.NotEqual):
                    if (
                        isinstance(target.comparator, cst.Name)
                        and target.comparator.value == "None"
                    ):
                        return True

        if isinstance(test, cst.UnaryOperation) and isinstance(test.operator, cst.Not):
            return True

        if isinstance(test, cst.Name):
            return True

        if isinstance(test, cst.Attribute):
            attr_lower = test.attr.value.lower()
            validation_attrs = ("valid", "enabled", "active", "ready", "ok", "exists")
            return attr_lower in validation_attrs

        return False

    def _negate_condition(self, condition: cst.BaseExpression) -> cst.BaseExpression:

        transformer = EarlyReturnTransformer()
        return transformer._negate_condition(condition)

    def _get_default_return(self, node: cst.If) -> cst.Return:

        for child in node.body.body:
            if isinstance(child, cst.SimpleStatementLine):
                for stmt in child.body:
                    if isinstance(stmt, cst.Return):
                        return cst.Return(value=stmt.value)

        return cst.Return(value=cst.Name(value="None"))

    def _body_ends_with_return(self, body: cst.BaseSuite) -> bool:
        if isinstance(body, cst.IndentedBlock):
            stmts = list(body.body)
            if stmts:
                last = stmts[-1]
                if isinstance(last, cst.SimpleStatementLine):
                    for stmt in last.body:
                        if isinstance(stmt, cst.Return):
                            return True
        return False


class LibcstSurgeon(BaseSurgeon):
    @property
    def name(self) -> str:
        return "libcst"

    def apply(
        self,
        code: str,
        match_info: dict,
        file_path: Path | None = None,
    ) -> TransformResult:
        pattern_type = match_info.get("type", "")

        try:
            module = cst.parse_module(code)

            if pattern_type == "early_return":
                transformer = EarlyReturnTransformer()
            elif pattern_type == "guard_clause":
                transformer = GuardClauseTransformer()
            else:
                return TransformResult(
                    success=False,
                    error_message=f"Unknown pattern type: {pattern_type}",
                )

            modified = module.visit(transformer)

            if not transformer.made_changes:
                return TransformResult(
                    success=False,
                    error_message="No changes made by transformer",
                )

            transformed = modified.code

            return TransformResult(
                success=True,
                transformed_code=transformed,
                pattern_name=pattern_type,
            )

        except cst.ParserSyntaxError as e:
            return TransformResult(
                success=False,
                error_message=f"Libcst parse error: {e}",
            )
        except Exception as e:
            return TransformResult(
                success=False,
                error_message=f"Libcst transform error: {e}",
            )

    def can_handle(self, match_info: dict) -> bool:
        pattern_type = match_info.get("type", "")

        return pattern_type in ("early_return", "guard_clause")
