from __future__ import annotations

import ast
import copy
import re
import textwrap
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
            elif pattern_type in (
                "extract_method",
                "split_sections",
                "lift_nested_helpers",
            ):
                transformed = self._apply_extract_method(code, match_info)
                if transformed is None:
                    return TransformResult(
                        success=False,
                        error_message="No changes made by extract method fallback",
                    )
                transformed = self._simplify_append_loops(transformed)
                return TransformResult(
                    success=True,
                    transformed_code=transformed,
                    pattern_name=pattern_type,
                )
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

        return pattern_type in (
            "early_return",
            "guard_clause",
            "extract_method",
            "split_sections",
            "lift_nested_helpers",
        )

    def _apply_extract_method(
        self,
        code: str,
        match_info: dict,
    ) -> str | None:
        node = match_info.get("node")
        try:
            import ast
            import textwrap

            if not isinstance(node, ast.AST):
                return None

            ast_node = ast.parse(code)
            func_node: ast.FunctionDef | ast.AsyncFunctionDef | None = None
            target_line = int(match_info.get("extraction_start", 0))

            for candidate in ast.walk(ast_node):
                if isinstance(candidate, ast.FunctionDef | ast.AsyncFunctionDef):
                    func_start = candidate.lineno
                    func_end = candidate.end_lineno or func_start
                    if func_start <= target_line <= func_end:
                        func_node = candidate
                        break

            if func_node is None:
                return None

            helper_name = self._ensure_unique_helper_name(
                code,
                func_node,
                match_info.get("suggested_name") or "_helper",
            )
            if match_info.get("type") == "lift_nested_helpers":
                transformed = self._lift_nested_helpers_to_module(
                    code,
                    func_node,
                    helper_name,
                )
            elif match_info.get("registration_wrapper"):
                transformed = self._lift_registration_wrapper_to_module(
                    code,
                    func_node,
                )
            elif match_info.get("type") == "split_sections":
                transformed = self._apply_split_sections(code, func_node, match_info)
            elif match_info.get("lift_to_module"):
                transformed = self._lift_method_to_module(
                    code,
                    func_node,
                    helper_name,
                )
            else:
                lines = code.split("\n")
                block_start = int(match_info.get("extraction_start", 0)) - 1
                block_end = int(match_info.get("extraction_end", 0)) - 1
                if (
                    block_start < 0
                    or block_end >= len(lines)
                    or block_start > block_end
                ):
                    return None

                is_async = isinstance(func_node, ast.AsyncFunctionDef)

                func_indent = len(lines[func_node.lineno - 1]) - len(
                    lines[func_node.lineno - 1].lstrip()
                )
                body_indent = " " * (func_indent + 4)
                helper_indent = body_indent
                helper_body_indent = " " * (func_indent + 8)

                block_lines = lines[block_start : block_end + 1]
                dedented_block = textwrap.dedent("\n".join(block_lines)).strip("\n")
                if not dedented_block:
                    return None

                call_line = f"{body_indent}{helper_name}()"
                helper_header = (
                    f"{helper_indent}{'async ' if is_async else ''}def {helper_name}():"
                )
                helper_body = textwrap.indent(dedented_block, helper_body_indent)

                new_lines = lines[:block_start] + [call_line] + lines[block_end + 1 :]
                insertion_index = func_node.lineno
                transformed_lines = (
                    new_lines[:insertion_index]
                    + [helper_header, helper_body, ""]
                    + new_lines[insertion_index:]
                )

                transformed = "\n".join(transformed_lines)

            ast.parse(transformed)
            return transformed
        except Exception:
            return None

    def _simplify_append_loops(self, code: str) -> str:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            rewritten = self._rewrite_append_loop(code, node)
            if rewritten is not None:
                return rewritten
        return code

    def _rewrite_append_loop(
        self,
        code: str,
        loop_node: ast.For,
    ) -> str | None:
        lines = code.split("\n")
        if not loop_node.body or len(loop_node.body) > 2:
            return None

        append_stmt: ast.Expr | None = None
        assign_stmt: ast.Assign | None = None
        for stmt in loop_node.body:
            if (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and stmt.value.func.attr == "append"
            ):
                append_stmt = stmt
            elif isinstance(stmt, ast.Assign):
                assign_stmt = stmt

        if append_stmt is None:
            return None
        if not isinstance(append_stmt.value.func.value, ast.Name):
            return None
        if len(append_stmt.value.args) != 1:
            return None
        if not isinstance(loop_node.target, (ast.Name, ast.Tuple, ast.List)):
            return None
        if not isinstance(loop_node.iter, ast.AST):
            return None

        list_name = append_stmt.value.func.value.id
        append_arg = append_stmt.value.args[0]
        item_expr = ast.get_source_segment(code, append_arg) or ast.unparse(append_arg)
        if (
            assign_stmt is not None
            and len(assign_stmt.targets) == 1
            and isinstance(assign_stmt.targets[0], ast.Name)
            and isinstance(append_arg, ast.Name)
            and assign_stmt.targets[0].id == append_arg.id
        ):
            item_expr = ast.get_source_segment(code, assign_stmt.value) or ast.unparse(
                assign_stmt.value
            )

        target_source = ast.get_source_segment(code, loop_node.target) or ast.unparse(
            loop_node.target
        )
        iter_source = ast.get_source_segment(code, loop_node.iter) or ast.unparse(
            loop_node.iter
        )

        init_start = self._find_list_initialization_line(code, loop_node, list_name)
        if init_start is None:
            return None

        loop_end = (loop_node.end_lineno or loop_node.lineno) - 1
        indent = lines[init_start][
            : len(lines[init_start]) - len(lines[init_start].lstrip())
        ]
        new_line = (
            f"{indent}{list_name} = [{item_expr} for {target_source} in {iter_source}]"
        )
        return "\n".join(lines[:init_start] + [new_line] + lines[loop_end + 1 :])

    def _find_list_initialization_line(
        self,
        code: str,
        loop_node: ast.For,
        list_name: str,
    ) -> int | None:
        lines = code.split("\n")
        loop_start = loop_node.lineno - 1
        for idx in range(loop_start - 1, -1, -1):
            line = lines[idx]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            loop_indent = len(lines[loop_start]) - len(lines[loop_start].lstrip())
            if indent != loop_indent:
                return None
            if stripped == f"{list_name} = []":
                return idx
            return None
        return None

    def _lift_registration_wrapper_to_module(
        self,
        code: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str | None:
        try:
            from crackerjack.agents.helpers.ast_transform.patterns.extract_method import (
                ExtractMethodPattern,
            )

            pattern = ExtractMethodPattern()
            nested_defs = [
                stmt
                for stmt in func_node.body
                if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef)
            ]
            if not nested_defs:
                return None

            helper_sources: list[str] = []
            registration_calls: dict[str, ast.stmt] = {}
            for nested in nested_defs:
                nested_source = ast.get_source_segment(code, nested)
                if nested_source:
                    nested_source = textwrap.dedent(nested_source).strip("\n")
                    try:
                        nested_tree = ast.parse(nested_source)
                    except SyntaxError:
                        nested_tree = None
                    else:
                        nested_candidate = next(
                            (
                                candidate
                                for candidate in ast.walk(nested_tree)
                                if isinstance(
                                    candidate,
                                    ast.FunctionDef | ast.AsyncFunctionDef,
                                )
                            ),
                            None,
                        )
                        nested_match = (
                            pattern.match(nested_candidate, nested_source.splitlines())
                            if nested_candidate is not None
                            else None
                        )
                        if (
                            nested_candidate is not None
                            and nested_match is not None
                            and nested_match.match_info.get("type") == "split_sections"
                        ):
                            nested_transformed = self._apply_split_sections(
                                nested_source,
                                nested_candidate,
                                nested_match.match_info,
                            )
                            if nested_transformed:
                                helper_sources.append(nested_transformed)
                                registration_calls[nested.name] = ast.Expr(
                                    value=ast.Call(
                                        func=ast.Call(
                                            func=ast.Attribute(
                                                value=ast.Name(
                                                    id="mcp",
                                                    ctx=ast.Load(),
                                                ),
                                                attr="tool",
                                                ctx=ast.Load(),
                                            ),
                                            args=[],
                                            keywords=[],
                                        ),
                                        args=[ast.Name(id=nested.name, ctx=ast.Load())],
                                        keywords=[],
                                    ),
                                )
                                continue

                helper_name = self._ensure_unique_helper_name(
                    code,
                    func_node,
                    f"_{nested.name}_impl",
                )

                helper_node = copy.deepcopy(nested)
                helper_node.name = helper_name
                helper_node.decorator_list = []
                ast.fix_missing_locations(helper_node)
                helper_sources.append(ast.unparse(helper_node))

                registration_calls[nested.name] = ast.Expr(
                    value=ast.Call(
                        func=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="mcp", ctx=ast.Load()),
                                attr="tool",
                                ctx=ast.Load(),
                            ),
                            args=[],
                            keywords=[],
                        ),
                        args=[ast.Name(id=helper_name, ctx=ast.Load())],
                        keywords=[],
                    ),
                )

            outer_node = copy.deepcopy(func_node)
            outer_body: list[ast.stmt] = []
            docstring = ast.get_docstring(func_node)
            if docstring:
                outer_body.append(
                    ast.Expr(
                        value=ast.Constant(value=docstring),
                    )
                )
            for stmt in func_node.body:
                if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
                    call = registration_calls.get(stmt.name)
                    if call is not None:
                        outer_body.append(call)
                    continue
                if (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                    and ast.get_docstring(func_node) == stmt.value.value
                ):
                    continue
                outer_body.append(copy.deepcopy(stmt))
            outer_node.body = outer_body
            ast.fix_missing_locations(outer_node)
            outer_source = ast.unparse(outer_node)

            transformed = "\n\n".join([*helper_sources, outer_source])
            transformed = self._prepend_missing_imports(transformed)
            transformed = self._reflow_overlong_joinedstr_statements(transformed)
            transformed = self._reflow_overlong_dict_assignments(transformed)
            ast.parse(transformed)
            return transformed
        except Exception:
            return None

    class _NestedHelperCallRenamer(ast.NodeTransformer):
        def __init__(self, rename_map: dict[str, str]) -> None:
            self.rename_map = rename_map

        def visit_Name(self, node: ast.Name) -> ast.AST:
            if isinstance(node.ctx, ast.Load) and node.id in self.rename_map:
                return ast.copy_location(
                    ast.Name(id=self.rename_map[node.id], ctx=node.ctx),
                    node,
                )
            return node

    def _lift_nested_helpers_to_module(
        self,
        code: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        helper_name: str,
    ) -> str | None:
        try:
            original_source = ast.get_source_segment(code, func_node)
            if not original_source:
                return None

            nested_defs = [
                stmt
                for stmt in func_node.body
                if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef)
            ]
            if len(nested_defs) < 2:
                return None

            ignore_names = {
                "Any",
                "Exception",
                "OSError",
                "Path",
                "datetime",
                "json",
                "len",
                "list",
                "dict",
                "str",
                "enumerate",
                "re",
            }
            helper_name_map: dict[str, str] = {}
            helper_sources: list[str] = []
            wrapper_sources: dict[str, str] = {}

            for nested in nested_defs:
                nested_source = ast.get_source_segment(code, nested)
                if not nested_source:
                    return None

                nested_inputs, nested_outputs = self._analyze_block_io(
                    list(nested.body)
                )
                nested_arg_names = [
                    *(arg.arg for arg in getattr(nested.args, "posonlyargs", [])),
                    *(arg.arg for arg in nested.args.args),
                    *(arg.arg for arg in getattr(nested.args, "kwonlyargs", [])),
                ]
                captured_inputs = [
                    name
                    for name in list(dict.fromkeys(nested_inputs))
                    if name not in nested_arg_names and name not in ignore_names
                ]

                candidate_name = self._ensure_unique_helper_name(
                    code,
                    func_node,
                    f"_{nested.name}_impl",
                )
                helper_name_map[nested.name] = candidate_name

                helper_node = copy.deepcopy(nested)
                helper_node.name = candidate_name
                existing_kwonly = {
                    arg.arg for arg in getattr(helper_node.args, "kwonlyargs", [])
                }
                helper_node.args.kwonlyargs = [
                    *helper_node.args.kwonlyargs,
                    *[
                        ast.arg(arg=name)
                        for name in captured_inputs
                        if name not in existing_kwonly
                    ],
                ]
                helper_node.args.kw_defaults = [
                    *helper_node.args.kw_defaults,
                    *[ast.Constant(value=None) for _ in captured_inputs],
                ]
                ast.fix_missing_locations(helper_node)
                helper_source = ast.unparse(helper_node)
                helper_sources.append(helper_source)

                if captured_inputs:
                    wrapper_node = ast.Assign(
                        targets=[ast.Name(id=nested.name, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id="partial", ctx=ast.Load()),
                            args=[ast.Name(id=candidate_name, ctx=ast.Load())],
                            keywords=[
                                ast.keyword(
                                    arg=name,
                                    value=ast.Name(id=name, ctx=ast.Load()),
                                )
                                for name in captured_inputs
                            ],
                        ),
                    )
                else:
                    wrapper_node = ast.Assign(
                        targets=[ast.Name(id=nested.name, ctx=ast.Store())],
                        value=ast.Name(id=candidate_name, ctx=ast.Load()),
                    )

                ast.fix_missing_locations(wrapper_node)
                wrapper_source = ast.unparse(wrapper_node)
                wrapper_sources[nested.name] = wrapper_source

            renamed_helper_sources: list[str] = []
            renamer = self._NestedHelperCallRenamer(helper_name_map)
            for helper_source in helper_sources:
                helper_ast = ast.parse(helper_source)
                helper_ast = renamer.visit(helper_ast)  # type: ignore[assignment]
                ast.fix_missing_locations(helper_ast)
                renamed_helper_sources.append(ast.unparse(helper_ast))

            transformed_source = original_source
            for nested in nested_defs:
                nested_source = ast.get_source_segment(code, nested)
                if not nested_source:
                    return None
                transformed_source = transformed_source.replace(
                    nested_source,
                    wrapper_sources[nested.name],
                    1,
                )

            transformed = "\n\n".join([*renamed_helper_sources, transformed_source])
            transformed = self._prepend_missing_imports(transformed)
            transformed = self._reflow_overlong_joinedstr_statements(transformed)
            transformed = self._reflow_overlong_dict_assignments(transformed)
            ast.parse(transformed)
            return transformed
        except Exception:
            return None

    def _build_forward_call(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        helper_name: str,
        captured_inputs: list[str],
    ) -> ast.stmt:
        call = ast.Call(
            func=ast.Name(id=helper_name, ctx=ast.Load()),
            args=[
                ast.Name(id=arg.arg, ctx=ast.Load())
                for arg in getattr(func_node.args, "posonlyargs", [])
            ]
            + [ast.Name(id=arg.arg, ctx=ast.Load()) for arg in func_node.args.args]
            + (
                [
                    ast.Starred(
                        value=ast.Name(id=func_node.args.vararg.arg, ctx=ast.Load()),
                        ctx=ast.Load(),
                    )
                ]
                if func_node.args.vararg
                else []
            ),
            keywords=[
                ast.keyword(
                    arg=arg.arg,
                    value=ast.Name(id=arg.arg, ctx=ast.Load()),
                )
                for arg in func_node.args.kwonlyargs
            ]
            + [
                ast.keyword(arg=name, value=ast.Name(id=name, ctx=ast.Load()))
                for name in captured_inputs
            ]
            + (
                [
                    ast.keyword(
                        arg=None,
                        value=ast.Name(id=func_node.args.kwarg.arg, ctx=ast.Load()),
                    )
                ]
                if func_node.args.kwarg
                else []
            ),
        )

        if isinstance(func_node, ast.AsyncFunctionDef):
            return ast.Return(value=ast.Await(value=call))

        return ast.Return(value=call)

    def _ensure_unique_helper_name(
        self,
        code: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        helper_name: str,
    ) -> str:
        existing_names = {
            node.name
            for node in ast.walk(ast.parse(code))
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        candidate = helper_name
        suffix = 1
        while candidate == func_node.name or candidate in existing_names:
            if candidate.endswith("_impl"):
                candidate = f"{candidate}_{suffix}"
            else:
                candidate = f"{helper_name}_impl"
            suffix += 1
        return candidate

    def _apply_split_sections(
        self,
        code: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        match_info: dict,
    ) -> str | None:
        try:
            lines = code.split("\n")
            section_candidates = list(match_info.get("section_candidates") or [])
            if len(section_candidates) < 3:
                return None

            split_mode = match_info.get("split_mode", "generic")
            if split_mode != "report":
                return self._apply_generic_split_sections(
                    code,
                    func_node,
                    section_candidates,
                )

            func_start = func_node.lineno - 1
            func_end = (func_node.end_lineno or func_node.lineno) - 1
            if func_start < 0 or func_end >= len(lines) or func_start > func_end:
                return None

            available_names = [
                *(arg.arg for arg in getattr(func_node.args, "posonlyargs", [])),
                *(arg.arg for arg in func_node.args.args),
                "storage",
                "lines",
                "effectiveness",
                "phases",
                "session_id",
                "db_path",
            ]
            available_names = list(dict.fromkeys(available_names))

            helper_defs: list[str] = []
            transformed_sections: dict[int, list[str]] = {}
            module_imports: list[str] = []

            if (
                re.search(r"\bPath\.(?:cwd|home)\b", code)
                or re.search(r"\bPath\s*\(", code)
            ) and "from pathlib import Path" not in code:
                module_imports.append("from pathlib import Path")

            if (
                re.search(r"\bdatetime\.\w+\b", code)
                or re.search(r"\bdatetime\s*\(", code)
            ) and "from datetime import datetime" not in code:
                module_imports.append("from datetime import datetime")

            for index, candidate in enumerate(section_candidates, start=1):
                helper_name = self._ensure_unique_helper_name(
                    code,
                    func_node,
                    candidate.get("suggested_name") or f"_section_{index}",
                )
                block_start = int(candidate.get("extraction_start", 0)) - 1
                block_end = int(candidate.get("extraction_end", 0)) - 1
                if (
                    block_start < 0
                    or block_end >= len(lines)
                    or block_start > block_end
                ):
                    return None

                block_lines = lines[block_start : block_end + 1]
                dedented_block = textwrap.dedent("\n".join(block_lines)).strip("\n")
                if not dedented_block:
                    return None

                inputs = set(candidate.get("inputs") or [])
                helper_args = [name for name in available_names if name in inputs]

                helper_lines = [f"def {helper_name}({', '.join(helper_args)}):"]
                if index == 1:
                    helper_lines.append("    phases = {}")
                helper_lines.append(textwrap.indent(dedented_block, "    "))
                if index == 1:
                    helper_lines.append("    return effectiveness, phases")
                helper_defs.extend([*helper_lines, ""])

                if index == 1:
                    transformed_sections[block_start] = [
                        f"    effectiveness, phases = {helper_name}({', '.join(helper_args)})"
                    ]
                else:
                    transformed_sections[block_start] = [
                        f"    {helper_name}({', '.join(helper_args)})"
                    ]

            transformed_lines = module_imports + ([""] if module_imports else [])
            transformed_lines += lines[:func_start] + helper_defs + [""]
            section_cursor = func_start
            for candidate in section_candidates:
                block_start = int(candidate.get("extraction_start", 0)) - 1
                block_end = int(candidate.get("extraction_end", 0)) - 1
                transformed_lines.extend(lines[section_cursor:block_start])
                transformed_lines.extend(transformed_sections.get(block_start, []))
                section_cursor = block_end + 1

            transformed_lines.extend(lines[section_cursor : func_end + 1])
            transformed_lines.extend(lines[func_end + 1 :])
            transformed = "\n".join(transformed_lines)
            transformed = self._prepend_missing_imports(transformed)
            transformed = self._reflow_overlong_joinedstr_statements(transformed)
            transformed = self._reflow_overlong_dict_assignments(transformed)
            ast.parse(transformed)
            return transformed
        except Exception:
            return None

    def _apply_generic_split_sections(
        self,
        code: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        section_candidates: list[dict],
    ) -> str | None:
        try:
            lines = code.split("\n")
            func_start = func_node.lineno - 1
            func_end = (func_node.end_lineno or func_node.lineno) - 1
            if func_start < 0 or func_end >= len(lines) or func_start > func_end:
                return None

            helper_body_indent = " " * 4

            helper_defs: list[str] = []
            call_replacements: dict[int, list[str]] = {}

            for index, candidate in enumerate(section_candidates, start=1):
                helper_name = self._ensure_unique_helper_name(
                    code,
                    func_node,
                    candidate.get("suggested_name") or f"_section_{index}",
                )
                block_start = int(candidate.get("extraction_start", 0)) - 1
                block_end = int(candidate.get("extraction_end", 0)) - 1
                if (
                    block_start < 0
                    or block_end >= len(lines)
                    or block_start > block_end
                ):
                    return None

                block_lines = lines[block_start : block_end + 1]
                dedented_block = textwrap.dedent("\n".join(block_lines)).strip("\n")
                if not dedented_block:
                    return None

                block_indent = " " * (
                    len(lines[block_start]) - len(lines[block_start].lstrip())
                )

                inputs = list(dict.fromkeys(candidate.get("inputs") or []))
                outputs = list(dict.fromkeys(candidate.get("outputs") or []))
                helper_args = [name for name in inputs if name != helper_name]

                helper_lines = [
                    f"{'async ' if isinstance(func_node, ast.AsyncFunctionDef) else ''}def {helper_name}({', '.join(helper_args)}):"
                ]
                helper_lines.append(textwrap.indent(dedented_block, helper_body_indent))
                if outputs:
                    if len(outputs) == 1:
                        helper_lines.append(f"{helper_body_indent}return {outputs[0]}")
                    else:
                        helper_lines.append(
                            f"{helper_body_indent}return ({', '.join(outputs)})"
                        )
                    if len(outputs) == 1:
                        call_replacements[block_start] = [
                            f"{block_indent}{outputs[0]} = {helper_name}({', '.join(helper_args)})"
                        ]
                    else:
                        call_replacements[block_start] = [
                            f"{block_indent}{', '.join(outputs)} = {helper_name}({', '.join(helper_args)})"
                        ]
                else:
                    call_replacements[block_start] = [
                        f"{block_indent}{helper_name}({', '.join(helper_args)})"
                    ]

                helper_defs.extend([*helper_lines, ""])

            transformed_lines = lines[:func_start] + helper_defs + [""]
            section_cursor = func_start
            for candidate in section_candidates:
                block_start = int(candidate.get("extraction_start", 0)) - 1
                block_end = int(candidate.get("extraction_end", 0)) - 1
                transformed_lines.extend(lines[section_cursor:block_start])
                transformed_lines.extend(call_replacements.get(block_start, []))
                section_cursor = block_end + 1

            transformed_lines.extend(lines[section_cursor : func_end + 1])
            transformed_lines.extend(lines[func_end + 1 :])
            transformed = "\n".join(transformed_lines)
            transformed = self._prepend_missing_imports(transformed)
            transformed = self._reflow_overlong_joinedstr_statements(transformed)
            transformed = self._reflow_overlong_dict_assignments(transformed)
            ast.parse(transformed)
            return transformed
        except Exception:
            return None

    def _prepend_missing_imports(self, code: str) -> str:
        module_imports: list[str] = []
        if re.search(r"\bjson\.\w+\b", code) and not self._has_module_import(
            code,
            "json",
        ):
            module_imports.append("import json")

        if re.search(r"\bPath\b", code) and not self._has_module_import(
            code,
            "pathlib",
            "Path",
        ):
            module_imports.append("from pathlib import Path")

        if re.search(r"\bpartial\(", code) and not self._has_module_import(
            code,
            "functools",
            "partial",
        ):
            module_imports.append("from functools import partial")

        if re.search(r"\bAny\b", code) and not self._has_module_import(
            code,
            "typing",
            "Any",
        ):
            module_imports.append("from typing import Any")

        if not module_imports:
            return code

        return "\n".join([*module_imports, "", "", code])

    def _has_module_import(
        self,
        code: str,
        module_name: str,
        imported_name: str | None = None,
    ) -> bool:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        for node in tree.body:
            if isinstance(node, ast.Import):
                if imported_name is None:
                    for alias in node.names:
                        if alias.name == module_name:
                            return True
                continue

            if not isinstance(node, ast.ImportFrom):
                continue

            if node.module != module_name:
                continue

            if imported_name is None:
                return True

            for alias in node.names:
                if alias.name == imported_name:
                    return True

        return False

    def _reflow_overlong_joinedstr_statements(self, code: str) -> str:
        lines = code.splitlines()
        transformed = False
        for index, line in enumerate(lines):
            if len(line) <= 88:
                continue

            replacement = self._reflow_joinedstr_statement(line)
            if replacement is None:
                continue

            lines[index : index + 1] = replacement
            transformed = True

        if not transformed:
            return code

        return "\n".join(lines)

    def _reflow_overlong_dict_assignments(self, code: str) -> str:
        lines = code.splitlines()
        transformed = False
        for index, line in enumerate(lines):
            if len(line) <= 88:
                continue

            replacement = self._reflow_dict_assignment(line)
            if replacement is None:
                continue

            lines[index : index + 1] = replacement
            transformed = True

        if not transformed:
            return code

        return "\n".join(lines)

    def _reflow_dict_assignment(self, line: str) -> list[str] | None:
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        try:
            statement = ast.parse(stripped).body[0]
        except SyntaxError:
            return None

        if not isinstance(statement, ast.Assign):
            return None
        if not isinstance(statement.value, ast.Dict):
            return None
        if len(statement.targets) != 1:
            return None

        lhs = ast.unparse(statement.targets[0])
        rendered_items: list[str] = []
        for key, value in zip(
            statement.value.keys, statement.value.values, strict=False
        ):
            if key is None:
                return None
            rendered_items.append(
                f"{indent}    {ast.unparse(key)}: {ast.unparse(value)},"
            )

        return [
            f"{indent}{lhs} = {{",
            *rendered_items,
            f"{indent}}}",
        ]

    def _reflow_joinedstr_statement(self, line: str) -> list[str] | None:
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        try:
            statement = ast.parse(stripped).body[0]
        except SyntaxError:
            return None

        if isinstance(statement, ast.Assign):
            if not isinstance(statement.value, ast.JoinedStr):
                return None
            lhs = ast.unparse(statement.targets[0])
            return self._render_joined_str_assignment(indent, lhs, statement.value)

        if isinstance(statement, ast.Expr) and isinstance(
            statement.value, ast.JoinedStr
        ):
            return self._render_joined_str_expression(indent, statement.value)

        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            if len(statement.value.args) != 1 or statement.value.keywords:
                return None
            arg = statement.value.args[0]
            if not isinstance(arg, ast.JoinedStr):
                return None
            func = ast.unparse(statement.value.func)
            return self._render_joined_str_call(indent, func, arg)

        return None

    def _render_joined_str_assignment(
        self,
        indent: str,
        lhs: str,
        joined: ast.JoinedStr,
    ) -> list[str]:
        chunk_lines = self._render_joined_str_chunks(joined, indent + "    ")
        return [
            f"{indent}{lhs} = (",
            *chunk_lines,
            f"{indent})",
        ]

    def _render_joined_str_call(
        self,
        indent: str,
        func: str,
        joined: ast.JoinedStr,
    ) -> list[str]:
        chunk_lines = self._render_joined_str_chunks(joined, indent + "    ")
        return [
            f"{indent}{func}(",
            *chunk_lines,
            f"{indent})",
        ]

    def _render_joined_str_expression(
        self,
        indent: str,
        joined: ast.JoinedStr,
    ) -> list[str]:
        return self._render_joined_str_chunks(joined, indent)

    def _render_joined_str_chunks(
        self,
        joined: ast.JoinedStr,
        indent: str,
    ) -> list[str]:
        rendered: list[str] = []
        for value in joined.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                for piece in self._split_string_literal(value.value):
                    rendered.append(f"{indent}{repr(piece)}")
                continue

            chunk = ast.JoinedStr(values=[value])
            rendered.append(f"{indent}{ast.unparse(chunk)}")
        return rendered

    def _split_string_literal(self, value: str, max_width: int = 60) -> list[str]:
        pieces: list[str] = []
        for line in value.splitlines(keepends=True):
            if not line:
                pieces.append(line)
                continue

            if len(line) <= max_width:
                pieces.append(line)
                continue

            segments = re.findall(r"\S+\s*|\s+", line)
            current = ""
            for segment in segments:
                if not segment:
                    continue
                if current and len(current + segment) > max_width:
                    pieces.append(current)
                    current = segment
                else:
                    current += segment
            if current:
                pieces.append(current)

        return pieces or [value]

    def _lift_method_to_module(
        self,
        code: str,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        helper_name: str,
    ) -> str | None:
        try:
            original_source = ast.get_source_segment(code, func_node)
            if not original_source:
                return None

            original_source = textwrap.dedent(original_source).strip("\n")
            helper_source = re.sub(
                rf"(\basync\s+)?def\s+{re.escape(func_node.name)}\b",
                lambda match: f"{match.group(1) or ''}def {helper_name}",
                original_source,
                count=1,
            )

            outer_node = copy.deepcopy(func_node)
            outer_node.body = [self._build_return_call(func_node, helper_name)]
            ast.fix_missing_locations(outer_node)
            outer_source = ast.unparse(outer_node)

            transformed = f"{outer_source}\n\n{helper_source}"
            ast.parse(transformed)
            return transformed
        except Exception:
            return None

    def _build_return_call(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        helper_name: str,
    ) -> ast.stmt:
        call = ast.Call(
            func=ast.Name(id=helper_name, ctx=ast.Load()),
            args=[
                ast.Name(id=arg.arg, ctx=ast.Load())
                for arg in getattr(func_node.args, "posonlyargs", [])
            ]
            + [ast.Name(id=arg.arg, ctx=ast.Load()) for arg in func_node.args.args]
            + (
                [
                    ast.Starred(
                        value=ast.Name(id=func_node.args.vararg.arg, ctx=ast.Load()),
                        ctx=ast.Load(),
                    )
                ]
                if func_node.args.vararg
                else []
            ),
            keywords=[
                ast.keyword(
                    arg=arg.arg,
                    value=ast.Name(id=arg.arg, ctx=ast.Load()),
                )
                for arg in func_node.args.kwonlyargs
            ]
            + (
                [
                    ast.keyword(
                        arg=None,
                        value=ast.Name(id=func_node.args.kwarg.arg, ctx=ast.Load()),
                    )
                ]
                if func_node.args.kwarg
                else []
            ),
        )

        if isinstance(func_node, ast.AsyncFunctionDef):
            return ast.Return(value=ast.Await(value=call))

        return ast.Return(value=call)

    def _analyze_block_io(
        self,
        block: list[ast.stmt],
    ) -> tuple[set[str], set[str]]:
        used_vars: set[str] = set()
        defined_vars: set[str] = set()

        for stmt in block:
            used_vars.update(self._get_used_variables(stmt))
            defined_vars.update(self._get_defined_variables(stmt))

        return used_vars - defined_vars, defined_vars

    def _get_used_variables(self, node: ast.AST) -> set[str]:
        used: set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                used.add(child.id)
            elif isinstance(child, ast.arg):
                used.add(child.arg)

        return used

    def _get_defined_variables(self, node: ast.AST) -> set[str]:
        defined: set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                defined.add(child.id)
            elif isinstance(child, ast.Tuple | ast.List):
                for elt in child.elts:
                    if isinstance(elt, ast.Name) and isinstance(elt.ctx, ast.Store):
                        defined.add(elt.id)
            elif isinstance(child, ast.For):
                defined.update(self._get_target_names(child.target))
            elif isinstance(child, ast.comprehension):
                defined.update(self._get_target_names(child.target))
            elif isinstance(child, ast.ExceptHandler) and child.name:
                if isinstance(child.name, str):
                    defined.add(child.name)

        return defined

    def _get_target_names(self, target: ast.expr) -> set[str]:
        names: set[str] = set()

        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Tuple | ast.List):
            for elt in target.elts:
                names.update(self._get_target_names(elt))

        return names
