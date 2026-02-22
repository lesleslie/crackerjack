"""Libcst-based surgeon for AST transformations.

Uses libcst (Concrete Syntax Tree) for type-safe code transformations
that preserve comments and formatting in most cases.
"""

from pathlib import Path

import libcst as cst

from crackerjack.agents.helpers.ast_transform.surgeons.base import (
    BaseSurgeon,
    TransformResult,
)


class EarlyReturnTransformer(cst.CSTTransformer):
    """Libcst transformer for early return pattern.

    Converts:
        if condition:
            # complex body
        else:
            return default

    To:
        if not condition:
            return default
        # complex body (dedented)
    """

    def __init__(self) -> None:
        self.made_changes = False

    def leave_If(
        self,
        original_node: cst.If,
        updated_node: cst.If,
    ) -> cst.If | cst.FlattenSentinel[cst.BaseStatement]:
        """Transform if-else to early return pattern."""
        # Only transform if there's an else clause
        if not updated_node.orelse:
            return updated_node

        # Check if else is a simple return/raise
        else_body = updated_node.orelse
        if not self._is_simple_else(else_body):
            return updated_node

        # Don't transform if-elif chains
        if isinstance(else_body, cst.Else) and len(else_body.body.body) == 1:
            inner_stmt = else_body.body.body[0]
            # Check if it's an if (elif pattern)
            if isinstance(inner_stmt, cst.If):
                return updated_node  # This is an elif, skip
            # Also check inside SimpleStatementLine wrapper
            if isinstance(inner_stmt, cst.SimpleStatementLine) and len(inner_stmt.body) == 1:
                if isinstance(inner_stmt.body[0], cst.If):
                    return updated_node

        # Negate the condition
        negated_test = self._negate_condition(updated_node.test)

        # Get the else body - it's an IndentedBlock inside Else
        if isinstance(else_body, cst.Else):
            # else_body.body is already an IndentedBlock
            else_block = else_body.body
        else:
            else_block = cst.IndentedBlock(body=else_body)

        # Create early return if
        early_return_if = cst.If(
            test=negated_test,
            body=else_block,
            # No else clause - the original body comes after
        )

        # Get the original body statements
        original_body = updated_node.body.body

        # Mark that we made changes
        self.made_changes = True

        # Return: early return check + original body (dedented)
        return cst.FlattenSentinel([early_return_if, *original_body])

    def _is_simple_else(self, orelse: cst.BaseSuite | None) -> bool:
        """Check if else clause is simple enough to convert."""
        if orelse is None:
            return False

        if isinstance(orelse, cst.Else):
            body = orelse.body.body
        else:
            return False

        if len(body) == 0:
            return True

        if len(body) == 1:
            stmt = body[0]
            # Unwrap SimpleStatementLine
            if isinstance(stmt, cst.SimpleStatementLine) and len(stmt.body) == 1:
                inner = stmt.body[0]
                # Return, raise, pass are simple
                if isinstance(inner, cst.Return | cst.Raise | cst.Pass):
                    return True
                # Simple assignment is ok
                if isinstance(inner, cst.AnnAssign | cst.Assign | cst.AugAssign):
                    return True

        return False

    def _negate_condition(self, condition: cst.BaseExpression) -> cst.BaseExpression:
        """Negate a condition, simplifying if possible."""
        # If already a Not, unwrap it
        if isinstance(condition, cst.UnaryOperation) and isinstance(
            condition.operator, cst.Not
        ):
            return condition.expression

        # If a comparison, try to negate the operator
        if isinstance(condition, cst.Comparison):
            return self._negate_comparison(condition)

        # If a boolean operation, apply De Morgan's law
        if isinstance(condition, cst.BooleanOperation):
            return self._apply_de_morgan(condition)

        # Default: wrap in Not()
        return cst.UnaryOperation(
            operator=cst.Not(),
            expression=cst.ensure_type(condition, cst.BaseExpression),
        )

    def _negate_comparison(self, comp: cst.Comparison) -> cst.Comparison:
        """Negate a comparison by inverting operators."""
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
                # is -> is not
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.IsNot(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.IsNot):
                # is not -> is
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.Is(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.In):
                # in -> not in
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.NotIn(),
                        comparator=target.comparator,
                    )
                )
            elif isinstance(target.operator, cst.NotIn):
                # not in -> in
                negated_targets.append(
                    cst.ComparisonTarget(
                        operator=cst.In(),
                        comparator=target.comparator,
                    )
                )
            else:
                # Unknown operator - wrap in Not
                return cst.UnaryOperation(
                    operator=cst.Not(),
                    expression=comp,
                )

        return cst.Comparison(
            left=comp.left,
            comparisons=negated_targets,
        )

    def _apply_de_morgan(self, boolop: cst.BooleanOperation) -> cst.BaseExpression:
        """Apply De Morgan's law to negate boolean operations.

        not (A and B) = (not A) or (not B)
        not (A or B) = (not A) and (not B)
        """
        # Negate left and right
        left = self._negate_condition(boolop.left)
        right = self._negate_condition(boolop.right)

        # Flip and/or
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
    """Libcst transformer for guard clause pattern.

    Converts nested validation checks to flat guard clauses:

        if data is not None:
            if data.valid:
                # do work

    To:

        if data is None:
            return None  # or appropriate default
        if not data.valid:
            return None
        # do work
    """

    def __init__(self) -> None:
        self.made_changes = False

    def leave_If(
        self,
        original_node: cst.If,
        updated_node: cst.If,
    ) -> cst.If | cst.FlattenSentinel[cst.BaseStatement]:
        """Transform nested validation to guard clauses."""
        # Check if this looks like a validation pattern
        if not self._is_validation_pattern(updated_node):
            return updated_node

        # Check if there's a nested if that's also a validation
        body_stmts = list(updated_node.body.body)
        if not body_stmts:
            return updated_node

        first_stmt = body_stmts[0]

        # If the first statement is another if, check if it's also a validation
        if isinstance(first_stmt, cst.If) and self._is_validation_pattern(first_stmt):
            # Convert current if to guard clause
            negated_test = self._negate_condition(updated_node.test)

            # Determine the default return value
            default_return = self._get_default_return(first_stmt)

            # Create guard clause
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

            # The original body becomes the continuation
            # Mark that we made changes
            self.made_changes = True

            return cst.FlattenSentinel([guard_if, *body_stmts])

        # Check if there's no else (pure validation pattern)
        if not updated_node.orelse:
            # This might be a guardable pattern if:
            # - The condition is a validation check
            # - The body ends with a return or has nested validation
            if self._body_ends_with_return(updated_node.body):
                # Already a guard pattern, skip
                return updated_node

        return updated_node

    def _is_validation_pattern(self, node: cst.If) -> bool:
        """Check if this if statement is a validation pattern."""
        # Check for common validation patterns in the condition
        test = node.test

        # x is None / x is not None
        if isinstance(test, cst.Comparison):
            for target in test.comparisons:
                if isinstance(target.operator, cst.Is | cst.IsNot):
                    return True
                if isinstance(target.operator, cst.Equal | cst.NotEqual):
                    if isinstance(target.comparator, cst.Name) and target.comparator.value == "None":
                        return True

        # not x / not x.attr
        if isinstance(test, cst.UnaryOperation) and isinstance(test.operator, cst.Not):
            return True

        # x (truthy check on name)
        if isinstance(test, cst.Name):
            return True

        # x.attr where attr is validation-like
        if isinstance(test, cst.Attribute):
            attr_lower = test.attr.value.lower()
            validation_attrs = ("valid", "enabled", "active", "ready", "ok", "exists")
            return attr_lower in validation_attrs

        return False

    def _negate_condition(self, condition: cst.BaseExpression) -> cst.BaseExpression:
        """Negate a condition, simplifying if possible."""
        # Reuse the logic from EarlyReturnTransformer
        transformer = EarlyReturnTransformer()
        return transformer._negate_condition(condition)

    def _get_default_return(self, node: cst.If) -> cst.Return:
        """Determine the appropriate default return value."""
        # Walk through the node to find return statements
        for child in node.body.body:
            if isinstance(child, cst.SimpleStatementLine):
                for stmt in child.body:
                    if isinstance(stmt, cst.Return):
                        # Use the same return value
                        return cst.Return(value=stmt.value)

        # Default to returning None
        return cst.Return(value=cst.Name(value="None"))

    def _body_ends_with_return(self, body: cst.BaseSuite) -> bool:
        """Check if the body ends with a return statement."""
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
    """Primary surgeon using libcst for type-safe CST manipulation.

    Advantages:
    - Type-safe node replacement
    - Well-maintained by Meta
    - Preserves comments in most cases
    - Good documentation

    Limitations:
    - May change formatting in some cases
    - Complex comment placement can be mishandled
    """

    @property
    def name(self) -> str:
        return "libcst"

    def apply(
        self,
        code: str,
        match_info: dict,
        file_path: Path | None = None,
    ) -> TransformResult:
        """Apply transformation using libcst.

        Args:
            code: Original source code
            match_info: Pattern match information containing:
                - type: Pattern type (e.g., "early_return")
                - Other pattern-specific data
            file_path: Optional file path for error reporting

        Returns:
            TransformResult with transformed code or error
        """
        pattern_type = match_info.get("type", "")

        try:
            # Parse to CST
            module = cst.parse_module(code)

            # Select transformer based on pattern type
            if pattern_type == "early_return":
                transformer = EarlyReturnTransformer()
            elif pattern_type == "guard_clause":
                transformer = GuardClauseTransformer()
            else:
                return TransformResult(
                    success=False,
                    error_message=f"Unknown pattern type: {pattern_type}",
                )

            # Apply transformation
            modified = module.visit(transformer)

            if not transformer.made_changes:
                return TransformResult(
                    success=False,
                    error_message="No changes made by transformer",
                )

            # Generate code
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
        """Check if this surgeon can handle the given match."""
        pattern_type = match_info.get("type", "")
        # Support all currently implemented patterns
        return pattern_type in ("early_return", "guard_clause")
