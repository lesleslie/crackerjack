from __future__ import annotations

import ast
import logging
import re
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from ..services.refurb_fixer import SafeRefurbFixer
from .base import FixResult, Issue, IssueType, SubAgent

if TYPE_CHECKING:
    from .base import AgentContext
logger = logging.getLogger(__name__)
FURB_TRANSFORMATIONS: dict[str, str] = {
    "FURB102": "_transform_compare_zero",
    "FURB105": "_transform_print_empty_string",
    "FURB107": "_transform_compare_empty",
    "FURB108": "_transform_redundant_none_comparison",
    "FURB109": "_transform_membership_test",
    "FURB110": "_transform_delete_while_iterating",
    "FURB111": "_transform_redundant_continue",
    "FURB113": "_transform_redundant_pass",
    "FURB115": "_transform_open_mode_r",
    "FURB116": "_transform_fstring_numeric_literal",
    "FURB117": "_transform_multiple_with",
    "FURB118": "_transform_enumerate",
    "FURB119": "_transform_redundant_index",
    "FURB122": "_transform_rhs_unpack",
    "FURB123": "_transform_list_copy",
    "FURB125": "_transform_redundantenumerate",
    "FURB126": "_transform_isinstance_type_check",
    "FURB129": "_transform_any_all",
    "FURB131": "_transform_single_item_membership",
    "FURB132": "_transform_check_and_remove",
    "FURB133": "_transform_bad_open_mode",
    "FURB134": "_transform_list_multiply",
    "FURB136": "_transform_bool_return",
    "FURB138": "_transform_list_comprehension",
    "FURB140": "_transform_zip",
    "FURB141": "_transform_redundant_fstring",
    "FURB142": "_transform_unnecessary_listcomp",
    "FURB143": "_transform_no_default_or",
    "FURB145": "_transform_copy",
    "FURB148": "_transform_max_min",
    "FURB152": "_transform_pow_operator",
    "FURB156": "_transform_redundant_lambda",
    "FURB157": "_transform_implicit_print",
    "FURB161": "_transform_int_scientific",
    "FURB163": "_transform_sorted_key_identity",
    "FURB167": "_transform_dict_literal",
    "FURB168": "_transform_isinstance_type_tuple",
    "FURB169": "_transform_type_none_comparison",
    "FURB171": "_transform_single_element_membership",
    "FURB172": "_transform_unnecessary_list_cast",
    "FURB173": "_transform_redundant_not",
    "FURB175": "_transform_abs_sqr",
    "FURB176": "_transform_unnecessary_from_float",
    "FURB177": "_transform_redundant_or",
    "FURB180": "_transform_method_assign",
    "FURB181": "_transform_redundant_expression",
    "FURB183": "_transform_useless_fstring",
    "FURB184": "_transform_bad_version_info_compare",
    "FURB185": "_transform_redundant_substring",
    "FURB186": "_transform_redundant_cast",
    "FURB187": "_transform_chained_assignment",
    "FURB188": "_transform_slice_copy",
    "FURB189": "_transform_fstring_to_print",
    "FURB190": "_transform_subprocess_list",
}


class RefurbCodeTransformerAgent(SubAgent):
    name = "RefurbCodeTransformerAgent"
    confidence = 0.85

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.log = logger.info  # type: ignore

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.REFURB}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.REFURB:
            return 0.0
        furb_code = self._extract_furb_code(issue)
        if furb_code is None:
            return 0.0
        if furb_code in FURB_TRANSFORMATIONS:
            return self.confidence
        return 0.0

    def _extract_furb_code(self, issue: Issue) -> str | None:
        for detail in issue.details:
            match = re.search(r"refurb_code:\s*(FURB\d+)", detail)
            if match:
                return match.group(1)
            match = re.search(r"\[?(FURB\d+)\]?", detail)
            if match:
                return match.group(1)
        if issue.message:
            match = re.search(r"\[?(FURB\d+)\]?", issue.message)
            if match:
                return match.group(1)
        if hasattr(issue, "reason") and issue.reason:
            reason_value = str(issue.reason)
            match = re.search(r"REFURB_TRANSFORM:(FURB\d+):", reason_value)
            if match:
                return match.group(1)
        return None

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"RefurbCodeTransformerAgent analyzing: {issue.message[:100]}")
        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided"],
            )
        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["Could not read file content"],
            )

        furb_code = self._extract_furb_code(issue)
        canonical_fix: FixResult | None = None
        if furb_code is not None:
            handler_name = FURB_TRANSFORMATIONS.get(furb_code)
            handler = getattr(self, handler_name, None) if handler_name else None
            if handler is not None:
                new_content, fix_description = self._try_ast_transform(
                    content, issue, furb_code, handler
                )
                if new_content == content:
                    new_content, fix_description = handler(content, issue)
                if new_content != content:
                    if self.context.write_file_content(file_path, new_content):
                        verified_content = self.context.get_file_content(file_path)
                        if verified_content is None or verified_content == content:
                            canonical_fix = FixResult(
                                success=False,
                                confidence=0.0,
                                remaining_issues=[
                                    f"write_file_content returned success but file content unchanged for {furb_code}"  # noqa: E501
                                ],
                            )
                        else:
                            return FixResult(
                                success=True,
                                confidence=self.confidence,
                                fixes_applied=[fix_description],
                                files_modified=[file_path],  # type: ignore
                            )
                    else:
                        canonical_fix = FixResult(
                            success=False,
                            confidence=0.0,
                            remaining_issues=[
                                f"Failed to write transformed content to {file_path}"
                            ],
                        )

        safe_fixer = SafeRefurbFixer()
        safe_content, safe_fixes = safe_fixer._apply_fixes(content)
        if safe_fixes > 0 and safe_content != content:
            if self.context.write_file_content(file_path, safe_content):
                verified_content = self.context.get_file_content(file_path)
                if verified_content is None or verified_content == content:
                    return FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[
                            "write_file_content returned success but file content unchanged for SafeRefurbFixer"  # noqa: E501
                        ],
                    )
                return FixResult(
                    success=True,
                    confidence=self.confidence,
                    fixes_applied=[
                        f"Applied SafeRefurbFixer with {safe_fixes} fix(es)"
                    ],
                    files_modified=[file_path],  # type: ignore
                )

        if canonical_fix is not None:
            return canonical_fix
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                f"No transformation produced a fix for {furb_code or 'unknown FURB code'}"  # noqa: E501
            ],
        )

    def _try_ast_transform(
        self, content: str, issue: Issue, furb_code: str, handler: object
    ) -> tuple[str, str]:
        try:
            tree = ast.parse(content)
            line_number = issue.line_number or 0
            ast_handlers = {
                "FURB107": self._ast_transform_suppress,
                "FURB102": self._ast_transform_startswith_tuple,
                "FURB109": self._ast_transform_membership_tuple,
                "FURB118": self._ast_transform_itemgetter,
                "FURB126": self._ast_transform_remove_else_return,
                "FURB110": self._ast_transform_or_operator,
                "FURB115": self._ast_transform_len_comparison,
                "FURB113": self._ast_transform_append_to_extend,
                "FURB123": self._ast_transform_list_copy,
                "FURB142": self._ast_transform_set_update,
            }
            ast_handler = ast_handlers.get(furb_code)
            if ast_handler:
                new_tree, fix_desc = ast_handler(tree, line_number, content)
                if new_tree:
                    new_content = self._unparse_tree(new_tree, content)
                    if new_content and new_content != content:
                        return (new_content, fix_desc)
        except SyntaxError as e:
            logger.debug(f"AST parse failed for {furb_code}: {e}")
        except Exception as e:
            logger.debug(f"AST transform failed for {furb_code}: {e}")
        return (content, "No AST transformation applied")

    def _unparse_tree(self, tree: ast.AST, original_content: str) -> str | None:
        with suppress(Exception):
            if hasattr(ast, "unparse"):
                return ast.unparse(tree)
        return None

    def _ast_transform_suppress(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        lines = content.split("\n")
        if not 1 <= line_number <= len(lines):
            return (None, "Line out of range")

        class _SuppressTransformer(ast.NodeTransformer):
            def __init__(self) -> None:
                self.replaced = False
                self.exc_desc = ""

            def visit_Try(self, node: ast.Try) -> ast.AST:  # type: ignore[override]
                if self.replaced or node.lineno != line_number:
                    return self.generic_visit(node)
                if not (
                    len(node.handlers) == 1
                    and len(node.handlers[0].body) == 1
                    and isinstance(node.handlers[0].body[0], ast.Pass)
                    and not node.finalbody
                    and not node.orelse
                ):
                    return self.generic_visit(node)
                handler = node.handlers[0]

                if isinstance(handler.type, ast.Tuple):
                    self.exc_desc = ast.unparse(handler.type)
                    suppress_args = handler.type.elts.copy()
                else:
                    self.exc_desc = ast.unparse(handler.type)
                    suppress_args = [handler.type]
                new_node = ast.With(
                    items=[
                        ast.withitem(
                            context_expr=ast.Call(
                                func=ast.Name(id="suppress", ctx=ast.Load()),
                                args=suppress_args,
                                keywords=[],
                            ),
                            optional_vars=None,
                        ),
                    ],
                    body=node.body,
                )
                ast.copy_location(new_node, node)
                ast.fix_missing_locations(new_node)
                self.replaced = True
                return new_node

        transformer = _SuppressTransformer()
        new_tree = transformer.visit(tree)
        if not transformer.replaced:
            return (None, "No suppress pattern found")
        ast.fix_missing_locations(new_tree)
        new_content = ast.unparse(new_tree)
        new_content = self._ensure_import_after_others(
            new_content, "from contextlib import suppress"
        )
        if new_content == content:
            return (None, "suppress rewrite was a no-op")
        return (
            new_tree,
            f"FURB107: replaced try/except {transformer.exc_desc}: pass with suppress()",  # noqa: E501
        )

    def _ast_transform_startswith_tuple(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        if not line_number:
            return (None, "FURB102 requires a line number")
        new_content, pattern_label = self._ast_line_rewrite(
            content,
            line_number,
            [
                (
                    r"(\w+)\.endswith\(([^)]+)\)\s+or\s+\1\.endswith\(([^)]+)\)",
                    r"\1.endswith((\2, \3))",
                    "endswith",
                ),
                (
                    r"(\w+)\.startswith\(([^)]+)\)\s+or\s+\1\.startswith\(([^)]+)\)",
                    r"\1.startswith((\2, \3))",
                    "startswith",
                ),
                (
                    r"not\s+(\w+)\.endswith\(([^)]+)\)\s+and\s+not\s+\1\.endswith\(([^)]+)\)",
                    r"not \1.endswith((\2, \3))",
                    "not endswith",
                ),
                (
                    r"not\s+(\w+)\.startswith\(([^)]+)\)\s+and\s+not\s+\1\.startswith\(([^)]+)\)",
                    r"not \1.startswith((\2, \3))",
                    "not startswith",
                ),
            ],
        )
        if new_content is None:
            return (None, f"FURB102 {pattern_label or 'no'} pattern matched")
        try:
            return (
                ast.parse(new_content),
                f"FURB102: combined {pattern_label} calls into tuple form",
            )
        except SyntaxError:
            return (None, "FURB102 rewrite produced invalid syntax")

    def _ast_transform_membership_tuple(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        if not line_number:
            return (None, "FURB109 requires a line number")
        new_content, _ = self._ast_line_rewrite(
            content,
            line_number,
            [(r"\bin\s*\[([^\]]+)\]", r"in (\1)", "membership")],
        )
        if new_content is None:
            return (None, "FURB109 no membership pattern")
        try:
            return (
                ast.parse(new_content),
                "FURB109: converted list membership to tuple membership",
            )
        except SyntaxError:
            return (None, "FURB109 rewrite produced invalid syntax")

    def _ast_transform_itemgetter(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        if not line_number:
            return (None, "FURB118 requires a line number")
        new_content, _ = self._ast_line_rewrite(
            content,
            line_number,
            [
                (
                    r"lambda\s+(\w+)\s*:\s*\1\s*\[\s*(\d+)\s*\]",
                    r"operator.itemgetter(\2)",
                    "indexed",
                ),
                (
                    r"""lambda\s+(\w+)\s*:\s*\1\s*\[\s*["']([^"']+)["']\s*\]""",
                    r"""operator.itemgetter("\2")""",
                    "keyed",
                ),
            ],
        )
        if new_content is None:
            return (None, "FURB118 no itemgetter pattern")

        new_content = self._ensure_import_after_others(new_content, "import operator")
        try:
            return (
                ast.parse(new_content),
                "FURB118: replaced lambda x: x[k] with operator.itemgetter(k)",
            )
        except SyntaxError:
            return (None, "FURB118 rewrite produced invalid syntax")

    def _ast_transform_remove_else_return(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        if not line_number:
            return (None, "FURB126 requires a line number")
        lines = content.split("\n")
        if not 1 <= line_number <= len(lines) - 1:
            return (None, "FURB126 needs an else line with a successor")
        else_line = lines[line_number - 1]
        next_line = lines[line_number]
        m = re.match(r"^(\s*)else:\s*$", else_line)
        n = re.match(r"^(\s+)return\b(.*)$", next_line)
        if not (m and n):
            return (None, "FURB126 no else-return pattern")
        else_indent = m.group(1)
        body_indent = n.group(1)
        if (
            not body_indent.startswith(else_indent + " ")
            and body_indent != else_indent + " " * 4
        ):
            return (None, "FURB126 else body not properly indented")
        new_lines = (
            lines[: line_number - 1]
            + [f"{else_indent}return{n.group(2)}"]
            + lines[line_number + 1 :]
        )
        new_content = "\n".join(new_lines)
        try:
            return (
                ast.parse(new_content),
                "FURB126: removed redundant else: return",
            )
        except SyntaxError:
            return (None, "FURB126 rewrite produced invalid syntax")

    def _ast_transform_or_operator(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        if not line_number:
            return (None, "FURB110 requires a line number")
        new_content, _ = self._ast_line_rewrite(
            content,
            line_number,
            [
                (
                    r"(\b\w[\w.]*)\s+if\s+\1\s+else\s+(\b\w[\w.]*\b)",
                    r"\1 or \2",
                    "ternary",
                ),
            ],
        )
        if new_content is None:
            return (None, "FURB110 no ternary pattern")
        try:
            return (
                ast.parse(new_content),
                "FURB110: collapsed x or y to x or y",
            )
        except SyntaxError:
            return (None, "FURB110 rewrite produced invalid syntax")

    def _ast_transform_len_comparison(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        if not line_number:
            return (None, "FURB115 requires a line number")
        new_content, label = self._ast_line_rewrite(
            content,
            line_number,
            [
                (r"len\s*\(([^)]+)\)\s*==\s*0\b", r"not \1", "len-eq-zero"),
                (r"len\s*\(([^)]+)\)\s*>=\s*1\b", r"\1", "len-gte-one"),
                (
                    r"open\s*\(\s*(\w+)\s*,\s*['\"]r['\"]\s*\)",
                    r"\1.open()",
                    "open-r",
                ),
                (
                    r"open\s*\(\s*([^, ]+),\s*['\"]r['\"]\s*\)",
                    r"open(\1)",
                    "open-r-mode",
                ),
            ],
        )
        if new_content is None:
            return (None, "FURB115 no matching pattern")
        try:
            return (
                ast.parse(new_content),
                f"FURB115: applied {label} transformation",
            )
        except SyntaxError:
            return (None, "FURB115 rewrite produced invalid syntax")

    def _ast_transform_append_to_extend(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        lines = content.split("\n")
        if not line_number or line_number > len(lines) - 1:
            return (None, "FURB113 requires a line number with a successor")

        first_line = lines[line_number - 1]
        second_line = lines[line_number]

        first_match = re.match(r"^(\s*)(\w+)\.append\(([^(),\n]+)\)\s*$", first_line)
        second_match = re.match(r"^(\s*)(\w+)\.append\(([^(),\n]+)\)\s*$", second_line)
        if not (first_match and second_match):
            return (None, "FURB113 no consecutive .append() pattern")

        first_indent, first_var, first_arg = first_match.groups()
        second_indent, second_var, second_arg = second_match.groups()
        if first_indent != second_indent or first_var != second_var:
            return (None, "FURB113 append lines target different lists/indents")

        replacement = f"{first_indent}{first_var}.extend(({first_arg.strip()}, {second_arg.strip()}))"  # noqa: E501
        new_lines = (
            lines[: line_number - 1] + [replacement, ""] + lines[line_number + 1 :]
        )
        new_content = "\n".join(new_lines)
        try:
            return (
                ast.parse(new_content),
                "FURB113: converted consecutive append() calls to extend()",
            )
        except SyntaxError:
            return (None, "FURB113 rewrite produced invalid syntax")

    def _ast_transform_list_copy(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        if not line_number:
            return (None, "FURB123 requires a line number")
        new_content, _ = self._ast_line_rewrite(
            content,
            line_number,
            [(r"\blist\(([a-z_][a-z0-9_]*)\)", r"\1.copy()", "list-copy")],
        )
        if new_content is None:
            return (None, "FURB123 no x.copy() pattern")
        try:
            return (
                ast.parse(new_content),
                "FURB123: replaced x.copy() with x.copy()",
            )
        except SyntaxError:
            return (None, "FURB123 rewrite produced invalid syntax")

    def _ast_transform_set_update(
        self, tree: ast.AST, line_number: int, content: str
    ) -> tuple[ast.AST | None, str]:
        if not line_number:
            return (None, "FURB142 requires a line number")
        lines = content.split("\n")
        if not 1 <= line_number <= len(lines) - 1:
            return (None, "FURB142 needs a for-line with a successor")
        for_line = lines[line_number - 1]
        next_line = lines[line_number]
        for_match = re.match(r"^(\s*)for\s+(\w+)\s+in\s+(.+?):\s*$", for_line)
        discard_match = (
            re.match(r"^(\s+)([a-z_]\w*)\.discard\(\2\)\s*$", next_line)
            if for_match
            else None
        )

        if for_match:
            loop_var = for_match.group(2)
            discard_match = re.match(
                rf"^(\s+)([a-z_]\w*)\.discard\({re.escape(loop_var)}\)\s*$",
                next_line,
            )
        if not (for_match and discard_match):
            return (None, "FURB142 no discard-loop pattern")
        for_indent, _var, iterable = for_match.groups()
        _body_indent, set_name = discard_match.groups()
        new_lines = (
            lines[: line_number - 1]
            + [f"{for_indent}{set_name}.difference_update({iterable})"]
            + lines[line_number + 1 :]
        )
        new_content = "\n".join(new_lines)
        try:
            return (
                ast.parse(new_content),
                "FURB142: replaced for-loop with set.difference_update()",
            )
        except SyntaxError:
            return (None, "FURB142 rewrite produced invalid syntax")

    def _ast_line_rewrite(
        self,
        content: str,
        line_number: int,
        patterns: list[tuple[str, str, str]],
    ) -> tuple[str | None, str]:
        lines = content.split("\n")
        if not 1 <= line_number <= len(lines):
            return (None, "")
        target_line = lines[line_number - 1]
        for pattern, replacement, label in patterns:
            if re.search(pattern, target_line):
                new_line = re.sub(pattern, replacement, target_line)
                new_content = "\n".join(
                    lines[: line_number - 1] + [new_line] + lines[line_number:]
                )
                return (new_content, label)
        return (None, "")

    def _ensure_import_after_others(self, content: str, import_line: str) -> str:
        if import_line in content:
            return content
        lines = content.split("\n")
        insert_idx = 0
        in_docstring = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped.startswith(("import ", "from ")):
                insert_idx = i + 1
        lines.insert(insert_idx, import_line)
        return "\n".join(lines)

    def _transform_enumerate(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        new_content = content
        lambda_index_pattern = "lambda\\s+(\\w+)\\s*:\\s*\\1\\s*\\[\\s*(\\d+)\\s*\\]"
        for match in re.finditer(lambda_index_pattern, content):
            match.group(1)
            index = match.group(2)
            old_lambda = match.group(0)
            new_itemgetter = f"operator.itemgetter({index})"
            new_content = new_content.replace(old_lambda, new_itemgetter)
            if (
                "import operator" not in new_content
                and "from operator import" not in new_content
            ):
                lines = new_content.split("\n")
                insert_pos = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith(("import ", "from ")):
                        insert_pos = i + 1
                    elif line.strip() and (not line.strip().startswith("#")):
                        break
                lines.insert(insert_pos, "import operator")
                new_content = "\n".join(lines)
        if new_content != content:
            fixes.append("Replaced lambda x: x[n] with operator.itemgetter(n)")
            content = new_content
        lambda_key_pattern = (
            "lambda\\s+(\\w+)\\s*:\\s*\\1\\s*\\[\\s*[\"\\']([^\"\\']+)[\"\\']\\s*\\]"
        )
        for match in re.finditer(lambda_key_pattern, content):
            match.group(1)
            key = match.group(2)
            old_lambda = match.group(0)
            new_itemgetter = f'operator.itemgetter("{key}")'
            new_content = new_content.replace(old_lambda, new_itemgetter)
        if new_content != content and "itemgetter" not in "; ".join(fixes):
            fixes.append(
                'Replaced operator.itemgetter("key") with operator.itemgetter("key")'
            )
        pattern = "(\\s*)(\\w+)\\s*=\\s*0\\n\\1for\\s+(\\w+)\\s+in\\s+([^:]+):\\n((?:.*\\n)*?)\\1\\2\\s*\\+=\\s*1"  # noqa: E501
        replacement = "\\1for \\2, \\3 in enumerate(\\4):\\n\\5"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Replaced manual index tracking with enumerate()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No enumerate transformation applied",
        )

    def _transform_any_all(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []

        pattern = r"(\b\w+(?:\.\w+)*)\.readlines\(\)"
        new_content = re.sub(pattern, r"\1", content)
        if new_content != content:
            count = len(re.findall(pattern, content))
            fixes.append(f"Removed {count} redundant .readlines() call(s)")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No simplify-readlines transformation",
        )

    def _transform_bool_return(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []

        max_pattern = (
            r"(\b\w[\w.]*\s*=\s*)([\w.]+)\s+if\s+\2\s*>\s*([\w.]+)\s+else\s+\3\b"
        )
        min_pattern = (
            r"(\b\w[\w.]*\s*=\s*)([\w.]+)\s+if\s+\2\s*<\s*([\w.]+)\s+else\s+\3\b"
        )

        new_content = re.sub(max_pattern, r"\1max(\2, \3)", content)
        if new_content != content:
            fixes.append("Rewrote ternary as max()")
        new_content = re.sub(min_pattern, r"\1min(\2, \3)", new_content)
        if new_content != content and "min(" in new_content:
            fixes.append("Rewrote ternary as min()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-min-max transformation",
        )

    def _transform_zip(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = "(\\s*)for\\s+(\\w+)\\s+in\\s+range\\(len\\(([^)]+)\\)\\):"
        new_content = re.sub(
            pattern,
            "\\1for _, _ in zip(\\3, _): # TODO: Apply zip transformation manually",
            content,
        )
        if new_content != content:
            fixes.append(
                "Identified zip() transformation opportunity (may need manual review)"
            )
        return (
            new_content,
            "; ".join(fixes) if fixes else "No zip transformation applied",
        )

    def _transform_unnecessary_listcomp(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []

        pattern = re.compile(
            r"^(\s*)for\s+(\w+)\s+in\s+(.+?):\s*\n"
            r"\s*([a-z_]\w*)\.discard\(\2\)\s*$",
            re.MULTILINE,
        )

        def _repl(match: re.Match[str]) -> str:
            indent, _var, iterable, set_name = (
                match.group(1),
                match.group(2),
                match.group(3),
                match.group(4),
            )
            return f"{indent}{set_name}.difference_update({iterable})"

        new_content = pattern.sub(_repl, content)
        if new_content != content:
            fixes.append("Replaced for-loop with set.difference_update()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No set-for-loop transformation",
        )

    def _transform_copy(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = "(\\w+)\\[\\s*:\\s*\\](?!\\s*, )"
        replacement = "\\1.copy()"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Replaced [:] slice with .copy() for clarity")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No copy transformation applied",
        )

    def _transform_max_min(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []

        index_pattern = re.compile(
            r"^(\s*)for\s+(\w+)\s*,\s*_\s+in\s+enumerate\(([^)]+)\)\s*:\s*$",
            re.MULTILINE,
        )
        new_content = index_pattern.sub(
            lambda m: f"{m.group(1)}for {m.group(2)} in range(len({m.group(3)})):",
            content,
        )
        if new_content != content:
            fixes.append("Rewrote for i, _ in enumerate(...) as range(len(...))")

        value_pattern = re.compile(
            r"^(\s*)for\s+_\s*,\s*(\w+)\s+in\s+enumerate\(([^)]+)\)\s*:\s*$",
            re.MULTILINE,
        )
        new_content = value_pattern.sub(
            lambda m: f"{m.group(1)}for {m.group(2)} in {m.group(3)}:",
            new_content,
        )
        if (
            new_content != content and "enumerated-as-direct" not in fixes[-1:]
            if fixes
            else True
        ):
            pass

        before_value = value_pattern.sub(
            lambda m: f"{m.group(1)}for {m.group(2)} in {m.group(3)}:",
            content,
        )
        if before_value != content:
            fixes.append("Rewrote for _, v in enumerate(...) as direct iteration")

        return (
            new_content,
            "; ".join(fixes) if fixes else "No no-ignored-enumerate transformation",
        )

    def _transform_pow_operator(self, content: str, issue: Issue) -> tuple[str, str]:  # noqa: C901
        fixes: list[str] = []

        replacements: list[tuple[str, str]] = [
            (r"\b3\.14159265\b", "math.pi"),
            (r"\b3\.14159\b", "math.pi"),
            (r"\b3\.1415\b", "math.pi"),
            (r"\b3\.141\b", "math.pi"),
            (r"\b3\.14\b", "math.pi"),
            (r"\b2\.71828\b", "math.e"),
            (r"\b2\.7182\b", "math.e"),
            (r"\b2\.718\b", "math.e"),
            (r"\b6\.28318\b", "math.tau"),
            (r"\b6\.2831\b", "math.tau"),
            (r"\b6\.283\b", "math.tau"),
        ]
        new_content = content
        for pattern_str, replacement in replacements:
            new_content2, count = re.subn(pattern_str, replacement, new_content)
            if count > 0:
                new_content = new_content2
                fixes.append(
                    f"Replaced {count} hardcoded constant(s) with {replacement}"
                )
        return (
            new_content,
            "; ".join(fixes) if fixes else "No math-constant transformation",
        )

    def _transform_int_scientific(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []

        pattern = re.compile(
            r"\b(bin|oct|hex)\s*\(([^)]+)\)\.count\(\s*['\"]1['\"]\s*\)"
        )
        new_content = pattern.sub(
            lambda m: f"({m.group(2)}).bit_count()",
            content,
        )
        if new_content != content:
            fixes.append("Replaced bin/oct/hex(...).count('1') with .bit_count()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-bit-count transformation",
        )

    def _transform_sorted_key_identity(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []

        log10_pattern = re.compile(r"\bmath\.log\s*\(\s*([^,)]+)\s*,\s*10\s*\)")
        new_content = log10_pattern.sub(
            lambda m: f"math.log10({m.group(1)})",
            content,
        )
        if new_content != content:
            fixes.append("Replaced math.log(x, 10) with math.log10(x)")

        log2_pattern = re.compile(r"\bmath\.log\s*\(\s*([^,)]+)\s*,\s*2\s*\)")
        new_content = log2_pattern.sub(
            lambda m: f"math.log2({m.group(1)})",
            new_content,
        )
        if new_content != content and "log2" in new_content:
            fixes.append("Replaced math.log(x, 2) with math.log2(x)")

        log_e_pattern = re.compile(r"\bmath\.log\s*\(\s*([^,)]+)\s*,\s*math\.e\s*\)")
        new_content = log_e_pattern.sub(
            lambda m: f"math.log({m.group(1)})",
            new_content,
        )
        if new_content != content:
            fixes.append("Replaced math.log(x, math.e) with math.log(x)")

        return (
            new_content,
            "; ".join(fixes) if fixes else "No simplify-math-log transformation",
        )

    def _transform_compare_zero(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        startswith_pattern = "(\\w+)\\.startswith\\s*\\(\\s*([^)]+)\\s*\\)\\s+or\\s+\\1\\.startswith\\s*\\(\\s*([^)]+)\\s*\\)"  # noqa: E501
        new_content = re.sub(startswith_pattern, "\\1.startswith((\\2, \\3))", content)
        if new_content != content:
            fixes.append("Combined startswith calls into tuple form")
            content = new_content
        not_startswith_pattern = "not\\s+(\\w+)\\.startswith\\s*\\(\\s*([^)]+)\\s*\\)\\s+and\\s+not\\s+\\1\\.startswith\\s*\\(\\s*([^)]+)\\s*\\)"  # noqa: E501
        new_content = re.sub(
            not_startswith_pattern, "not \\1.startswith((\\2, \\3))", content
        )
        if new_content != content:
            fixes.append("Combined not startswith calls into tuple form")
            content = new_content

        endswith_pattern = "(\\w+)\\.endswith\\s*\\(\\s*([^)]+)\\s*\\)\\s+or\\s+\\1\\.endswith\\s*\\(\\s*([^)]+)\\s*\\)"  # noqa: E501
        new_content = re.sub(endswith_pattern, "\\1.endswith((\\2, \\3))", content)
        if new_content != content:
            fixes.append("Combined endswith calls into tuple form")
            content = new_content
        not_endswith_pattern = "not\\s+(\\w+)\\.endswith\\s*\\(\\s*([^)]+)\\s*\\)\\s+and\\s+not\\s+\\1\\.endswith\\s*\\(\\s*([^)]+)\\s*\\)"  # noqa: E501
        new_content = re.sub(
            not_endswith_pattern, "not \\1.endswith((\\2, \\3))", content
        )
        if new_content != content:
            fixes.append("Combined not endswith calls into tuple form")
            content = new_content
        new_content = re.sub("len\\s*\\(([^)]+)\\)\\s*==\\s*0", "not \\1", content)
        if new_content != content:
            fixes.append("Simplified not x to not x")
            content = new_content
        new_content = re.sub("(\\w+)\\s*==\\s*0\\b", "not \\1", content)
        if new_content != content and "Simplified x == 0" not in "; ".join(fixes):
            fixes.append("Simplified x == 0 to not x")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No zero comparison transformation",
        )

    def _transform_compare_empty(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []

        exc_spec = r"(?:\w+(?:\.\w+)*|\([^)]*\))"
        suppress_pattern = (
            r"(\s*)try:\s*\n"
            r"((?:\1\s+.*\n)+)"
            r"\1except\s+(" + exc_spec + r")"
            r"(?:\s+as\s+\w+)?"
            r"\s*:\s*\n"
            r"\1\s+pass"
        )
        new_content = content
        for match in re.finditer(suppress_pattern, content):
            indent = match.group(1)
            body = match.group(2)
            exc_type = match.group(3)

            if exc_type.startswith("(") and exc_type.endswith(")"):
                exc_type = exc_type[1:-1]
            has_contextlib = (
                "from contextlib import" in content or "import contextlib" in content
            )
            suppress_import = (
                "from contextlib import suppress" if not has_contextlib else ""
            )
            replacement = f"{indent}with suppress({exc_type}):\n{body}"
            new_content = new_content.replace(match.group(0), replacement)
            if suppress_import and suppress_import not in new_content:
                lines = new_content.split("\n")
                insert_pos = 0
                in_docstring = False
                for i, line in enumerate(lines):
                    if '"""' in line or "'''" in line:
                        in_docstring = not in_docstring
                    if (
                        not in_docstring
                        and line.strip()
                        and (not line.strip().startswith("#"))
                    ):
                        insert_pos = i
                        break
                lines.insert(insert_pos, suppress_import)
                new_content = "\n".join(lines)
        if new_content != content:
            fixes.append("Replaced try/except: pass with suppress()")
            content = new_content
        new_content = re.sub("(\\w+)\\s*==\\s*\\[\\s*\\]", "not \\1", content)
        if new_content != content:
            fixes.append("Simplified x == [] to not x")
            content = new_content
        new_content = re.sub("(\\w+)\\s*==\\s*\\{\\s*\\}", "not \\1", content)
        if new_content != content:
            fixes.append("Simplified x == {} to not x")
            content = new_content
        new_content = re.sub('(\\w+)\\s*==\\s*""', "not \\1", content)
        if new_content != content:
            fixes.append('Simplified x == "" to not x')
        return (
            new_content,
            "; ".join(fixes) if fixes else "No empty comparison transformation",
        )

    def _transform_redundant_none_comparison(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        _val = r"""(?:'[^']*'|"[^"]*"|\w+)"""
        pattern = re.compile(
            r"\b([\w.]+)\s*==\s*(" + _val + r")\s+or\s+\1\s*==\s*(" + _val + r")"
        )
        new_content = pattern.sub(r"\1 in (\2, \3)", content)
        if new_content != content:
            fixes.append("Replaced chained == or with in operator")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-in-oper transformation",
        )

    def _transform_membership_test(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = "\\bin\\s*\\[([^\\]]+)\\]"
        replacement = "in (\\1)"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Converted list membership to tuple membership")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No membership test transformation",
        )

    def _transform_isinstance_type_check(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        new_content = content

        pattern = "type\\s*\\(([^)]+)\\)\\s*==\\s*(\\w+)"
        new_content = re.sub(pattern, "isinstance(\\1, \\2)", new_content)
        if new_content != content:
            fixes.append("Converted type(x) == T to isinstance(x, T)")

        type_rewrite = new_content
        lines = type_rewrite.split("\n")
        rewritten_lines: list[str] = []
        i = 0
        edits = 0
        while i < len(lines):
            line = lines[i]
            else_match = re.match(r"^(\s*)else:\s*$", line)
            if not else_match:
                rewritten_lines.append(line)
                i += 1
                continue
            indent = else_match.group(1)
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            return_match = re.match(r"^(\s+)return\b(.*)$", next_line)
            if not return_match:
                rewritten_lines.append(line)
                i += 1
                continue
            body_indent = return_match.group(1)

            has_more_code = False
            for j in range(i + 2, len(lines)):
                following = lines[j]
                if not following.strip():
                    continue
                if following.startswith(body_indent):
                    has_more_code = True
                    break
                if following.startswith(indent) or not following.startswith(" "):
                    break
            if has_more_code:
                rewritten_lines.append(line)
                i += 1
                continue

            rewritten_lines.append(f"{indent}return{return_match.group(2)}")
            edits += 1
            i += 2

        if edits:
            new_content = "\n".join(rewritten_lines)
            if "Removed redundant else: return" not in fixes:
                fixes.append("Removed redundant else: return")

        return (
            new_content,
            "; ".join(fixes) if fixes else "No isinstance transformation",
        )

    def _transform_write_whole_file(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes = []
        pattern = "open\\s*\\(\\s*([^, ]+), \\s*['\\\"]w['\\\"]\\s*\\)\\.write\\s*\\(([^)]+)\\)"  # noqa: E501
        replacement = "Path(\\1).write_text(\\2)"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Converted open().write() to Path.write_text()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No write file transformation",
        )

    def _transform_multiple_with(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = "with\\s+([^:]+):\\s*\\n\\s*with\\s+([^:]+):"
        replacement = "with \\1, \\2:"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Combined nested with statements")
        return (new_content, "; ".join(fixes) if fixes else "No with transformation")

    def _transform_redundant_not(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []

        pattern = r"\{([^{}]*?)\*\*([a-z_]\w*(?:\.[a-z_]\w*)*)\s*\}"
        new_content = re.sub(pattern, r"{\1} | \2", content)
        if new_content != content:
            fixes.append("Replaced **spread in dict literal with | union")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No dict-union transformation",
        )

    def _transform_substring(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        pattern = "(\\w+)\\.find\\s*\\(([^)]+)\\)\\s*!=\\s*-1"
        replacement = "\\2 in \\1"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Converted x.find(y) != -1 to y in x")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No substring transformation",
        )

    def _transform_useless_fstring(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []

        pattern = r"""f(["'])\{(\s*\S[^!}:]*|)\}\1"""

        matches = list(re.finditer(pattern, content))
        new_content = re.sub(pattern, r"str(\2)", content)
        if new_content != content and matches:
            count = len(matches)
            verb = "Replaced" if count == 1 else f"Replaced {count} of"
            fixes.append(f"{verb} useless f-string(s) with str()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No useless f-string transformation",
        )

    def _transform_print_empty_string(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes = []
        new_content = content
        print_empty = 'print\\s*\\(\\s*""\\s*\\)'
        new_content = re.sub(print_empty, "print()", new_content)
        if new_content != content:
            fixes.append('Converted print("") to print()')
            content = new_content
        or_pattern = "\\b(\\w+)\\s+if\\s+\\1\\s+else\\s+(\\w+)"
        new_content = re.sub(or_pattern, "\\1 or \\2", new_content)
        if new_content != content and "or" not in "; ".join(fixes):
            fixes.append("Converted x or y to x or y")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No print empty string transformation",
        )

    def _transform_delete_while_iterating(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:

        pattern = re.compile(
            r"(\b\w[\w.]*\s*=\s*)([\w.]+)\s+if\s+\2\s+else\s+([\w.]+)\b"
        )
        new_content = pattern.sub(r"\1\2 or \3", content)
        if new_content != content:
            fixes = "Rewrote ternary (x or y) as (x or y)"
        else:
            fixes = "No use-or-oper transformation"
        return (new_content, fixes)

    def _transform_redundant_continue(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes = []
        pattern = "\\n(\\s*)continue\\s*\\n(\\s*)\\n"
        replacement = "\\n\\2\\n"
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            fixes.append("Removed redundant continue")
        return (new_content, "; ".join(fixes) if fixes else "No redundant continue")

    def _transform_list_copy(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = r"\blist\(([a-z_][a-z0-9_]*)\)"
        new_content = content
        for match in re.finditer(pattern, content):
            var_name = match.group(1)
            old_text = match.group(0)
            new_text = f"{var_name}.copy()"
            new_content = new_content.replace(old_text, new_text, 1)
            fixes.append(f"Replaced list({var_name}) with {var_name}.copy()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No list copy transformation",
        )

    def _transform_redundant_pass(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        lines = content.split("\n")
        result_lines = lines.copy()

        i = 0
        while i < len(lines) - 1:
            first_line = lines[i]
            first_match = re.match(
                r"^(\s*)(\w+)\.append\(([^(), \n]+)\)\s*$",
                first_line,
            )
            if not first_match:
                i += 1
                continue

            indent, var_name, arg1 = (
                first_match.group(1),
                first_match.group(2),
                first_match.group(3).strip(),
            )

            second_line = lines[i + 1]
            second_match = re.match(
                rf"^{re.escape(indent)}{re.escape(var_name)}\.append\(([^(), \n]+)\)\s*$",  # noqa: E501
                second_line,
            )
            if not second_match:
                i += 1
                continue

            arg2 = second_match.group(1).strip()
            result_lines[i] = f"{indent}{var_name}.extend(({arg1}, {arg2}))"
            result_lines[i + 1] = ""
            fixes.append("Converted consecutive append() calls to extend()")
            i += 2

        new_content = "\n".join(result_lines)
        return (
            new_content,
            "; ".join(fixes) if fixes else "No append to extend transformation",
        )

    def _transform_open_mode_r(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes = []
        new_content = content
        len_eq_zero = "len\\s*\\(([^)]+)\\)\\s*==\\s*0\\b"
        new_content = re.sub(len_eq_zero, "not \\1", new_content)
        if new_content != content:
            fixes.append("Converted not x to not x")
            content = new_content
        len_gte_one = "len\\s*\\(([^)]+)\\)\\s*>=\\s*1\\b"
        new_content = re.sub(len_gte_one, "\\1", new_content)
        if new_content != content:
            fixes.append("Converted x to x")
        open_path_r = "open\\s*\\(\\s*(\\w+)\\s*, \\s*[\"\\']r[\"\\']\\s*\\)"
        new_content = re.sub(open_path_r, "\\1.open()", new_content)
        if new_content != content and "open()" not in "; ".join(fixes):
            fixes.append("Converted open(path, 'r') to path.open()")
        open_path_w = "open\\s*\\(\\s*(\\w+)\\s*, \\s*[\"\\']w[\"\\']\\s*\\)"
        new_content = re.sub(open_path_w, "\\1.open('w')", new_content)
        if new_content != content and "open(" not in "; ".join(fixes):
            fixes.append("Converted open(path, 'w') to path.open('w')")
        pattern = "open\\s*\\(\\s*([^, ]+), \\s*['\\\"]r['\\\"]\\s*\\)"
        replacement = "open(\\1)"
        new_content = re.sub(pattern, replacement, new_content)
        if new_content != content and "open()" not in "; ".join(fixes):
            fixes.append("Removed redundant 'r' mode from open()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No open mode transformation",
        )

    def _transform_fstring_numeric_literal(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        import ast as _ast

        try:
            tree = _ast.parse(content)
        except SyntaxError:
            return content, "use-fstring-number-format requires manual review"

        fixes: list[str] = []
        new_content = content

        for node in _ast.walk(tree):
            if not isinstance(node, _ast.Subscript):
                continue
            call = node.value
            if not (
                isinstance(call, _ast.Call)
                and isinstance(call.func, _ast.Name)
                and call.func.id in ("bin", "oct", "hex")
                and len(call.args) == 1
                and isinstance(node.slice, _ast.Slice)
                and isinstance(node.slice.lower, _ast.Constant)
                and node.slice.lower.value == 2
                and node.slice.upper is None
            ):
                continue
            try:
                inner = _ast.unparse(call.args[0])
            except Exception:
                continue
            fmt = {"bin": "b", "oct": "o", "hex": "x"}[call.func.id]
            replacement = f'f"{{{inner}:{fmt}}}"'

            lines = new_content.split("\n")
            start = node.lineno - 1
            end = (node.end_lineno or node.lineno) - 1
            if 0 <= start < len(lines) and 0 <= end < len(lines):
                indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
                lines[start : end + 1] = [indent + replacement]
                new_content = "\n".join(lines)
                fixes.append(f"Replaced {call.func.id}({inner})[2:] with f-string")

        return (
            new_content,
            "; ".join(fixes)
            if fixes
            else "No use-fstring-number-format transformation",
        )

    def _transform_redundant_index(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        _var = r"([\w.]+)"
        transforms = [
            (
                re.compile(r"\{bin\(" + _var + r"\)\}"),
                r"{\1:b}",
                "Replaced {bin(n)} with {n: b}",
            ),
            (
                re.compile(r"\{oct\(" + _var + r"\)\}"),
                r"{\1:o}",
                "Replaced {oct(n)} with {n: o}",
            ),
            (
                re.compile(r"\{hex\(" + _var + r"\)\}"),
                r"{\1:x}",
                "Replaced {hex(n)} with {n: x}",
            ),
            (
                re.compile(r"\{str\(" + _var + r"\)\}"),
                r"{\1}",
                "Replaced {str(x)} with {x}",
            ),
        ]
        new_content = content
        for pattern, repl, msg in transforms:
            result = pattern.sub(repl, new_content)
            if result != new_content:
                fixes.append(msg)
                new_content = result
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-fstring-format transformation",
        )

    def _transform_rhs_unpack(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(
            r"^(\s*)for\s+(\w+)\s+in\s+(\w+)\s*:\s*\n"
            r"\s*(\w+)\.write\(\2\)\s*$",
            re.MULTILINE,
        )
        new_content = pattern.sub(r"\1\4.writelines(\3)", content)
        if new_content != content:
            fixes.append("Replaced for-loop with writelines()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-writelines transformation",
        )

    def _transform_redundantenumerate(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        import ast as _ast

        try:
            tree = _ast.parse(content)
        except SyntaxError:
            return content, "no-redundant-return requires manual review"

        fixes: list[str] = []
        lines = content.split("\n")

        for node in _ast.walk(tree):
            if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                continue
            if not node.body:
                continue
            last = node.body[-1]
            if isinstance(last, _ast.Return) and last.value is None:
                start = last.lineno - 1
                end = (last.end_lineno or last.lineno) - 1
                if 0 <= start < len(lines) and 0 <= end < len(lines):
                    del lines[start : end + 1]
                    fixes.append(f"Removed redundant return at end of {node.name}()")
        return (
            "\n".join(lines),
            "; ".join(fixes) if fixes else "No no-redundant-return transformation",
        )

    def _transform_single_item_membership(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        new_content = content

        del_pattern = r"\bdel\s+([a-z_]\w*)\s*\[\s*:\s*\]"
        new_content = re.sub(del_pattern, r"\1.clear()", new_content)
        if new_content != content:
            fixes.append("Replaced del x[:] with x.clear()")
            content = new_content

        slice_assign_pattern = r"\b([a-z_]\w*)\s*\[\s*:\s*\]\s*=\s*\[\s*\]"
        new_content = re.sub(slice_assign_pattern, r"\1.clear()", content)
        if new_content != content:
            if fixes:
                fixes.append("Also replaced x[:] = [] with x.clear()")
            else:
                fixes.append("Replaced x[:] = [] with x.clear()")

        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-clear transformation",
        )

    def _transform_check_and_remove(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(
            r"^(\s*)if\s+([\w.]+)\s+in\s+(\w+)\s*:\s*\n"
            r"\s*\3\.remove\(\2\)\s*$",
            re.MULTILINE,
        )
        new_content = pattern.sub(r"\1\3.discard(\2)", content)
        if new_content != content:
            fixes.append("Replaced if-in-remove with set.discard()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-set-discard transformation",
        )

    def _transform_bad_open_mode(self, content: str, issue: Issue) -> tuple[str, str]:
        import ast as _ast

        try:
            tree = _ast.parse(content)
        except SyntaxError:
            return content, "no-redundant-continue requires manual review"

        fixes: list[str] = []
        lines = content.split("\n")

        for node in _ast.walk(tree):
            if not isinstance(node, (_ast.For, _ast.While, _ast.AsyncFor)):
                continue
            if not node.body:
                continue
            last = node.body[-1]
            if isinstance(last, _ast.Continue):
                start = last.lineno - 1
                end = (last.end_lineno or last.lineno) - 1
                if 0 <= start < len(lines) and 0 <= end < len(lines):
                    del lines[start : end + 1]
                    fixes.append("Removed redundant continue at end of loop")
        return (
            "\n".join(lines),
            "; ".join(fixes) if fixes else "No no-redundant-continue transformation",
        )

    def _transform_list_multiply(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(r"@lru_cache\s*\(\s*maxsize\s*=\s*None\s*\)")
        new_content = pattern.sub("@cache", content)
        if new_content != content:
            fixes.append("Replaced @lru_cache(maxsize=None) with @cache")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-cache transformation",
        )

    def _transform_print_literal(self, content: str, issue: Issue) -> tuple[str, str]:
        return self._transform_list_comprehension(content, issue)

    def _transform_list_comprehension(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        if issue.line_number is None:
            return (content, "FURB138 list comprehension requires a line number")

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return (content, "FURB138 list comprehension requires valid Python")

        target_for = self._find_list_comprehension_loop(tree, issue.line_number)
        if target_for is None:
            return (content, "No list comprehension loop found")

        extract_result = self._build_list_comprehension_rewrite(content, target_for)
        if extract_result is None:
            return (content, "List comprehension pattern requires a simple loop body")
        return extract_result

    def _find_list_comprehension_loop(
        self, tree: ast.AST, line_number: int
    ) -> ast.For | None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            node_end = node.end_lineno or node.lineno
            if node.lineno <= line_number <= node_end:
                return node
        return None

    def _build_list_comprehension_rewrite(
        self, content: str, target_for: ast.For
    ) -> tuple[str, str] | None:
        if not target_for.body or len(target_for.body) > 2:
            return None

        append_stmt, assign_stmt = self._extract_append_loop_parts(target_for)
        if append_stmt is None:
            return None

        list_name = self._get_append_target_name(append_stmt)
        if list_name is None:
            return None

        item_expr = self._get_list_comprehension_item_expr(
            content,
            append_stmt,
            assign_stmt,
        )
        if item_expr is None:
            return None

        loop_signature = self._get_list_comprehension_loop_signature(
            content,
            target_for,
            list_name,
            item_expr,
        )
        if loop_signature is None:
            return None

        new_content = self._rewrite_loop_as_list_comprehension(
            content,
            target_for,
            list_name,
            item_expr,
            loop_signature,
        )
        if new_content == content:
            return None

        return (
            new_content,
            f"Converted append loop to list comprehension for {list_name}",
        )

    def _extract_append_loop_parts(
        self, target_for: ast.For
    ) -> tuple[ast.Expr | None, ast.Assign | None]:
        append_stmt: ast.Expr | None = None
        assign_stmt: ast.Assign | None = None
        for stmt in target_for.body:
            if (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and stmt.value.func.attr == "append"
            ):
                append_stmt = stmt
            elif isinstance(stmt, ast.Assign):
                assign_stmt = stmt
        return append_stmt, assign_stmt

    def _get_append_target_name(self, append_stmt: ast.Expr) -> str | None:

        if not isinstance(append_stmt.value, ast.Call):
            return None
        call_value: ast.Call = append_stmt.value  # type: ignore[assignment]
        if not isinstance(call_value.func, ast.Attribute):
            return None
        if not isinstance(call_value.func.value, ast.Name):  # type: ignore[union-attr]
            return None
        if len(call_value.args) != 1:  # type: ignore[union-attr]
            return None
        return call_value.func.value.id  # type: ignore[union-attr]

    def _get_list_comprehension_item_expr(
        self,
        content: str,
        append_stmt: ast.Expr,
        assign_stmt: ast.Assign | None,
    ) -> str | None:
        assert isinstance(append_stmt.value, ast.Call), "expected .append(...) call"
        append_arg = append_stmt.value.args[0]
        item_expr = ast.get_source_segment(content, append_arg) or ast.unparse(
            append_arg
        )

        if (
            assign_stmt is not None
            and len(assign_stmt.targets) == 1
            and isinstance(assign_stmt.targets[0], ast.Name)
            and isinstance(append_arg, ast.Name)
            and assign_stmt.targets[0].id == append_arg.id
        ):
            item_expr = ast.get_source_segment(
                content, assign_stmt.value
            ) or ast.unparse(assign_stmt.value)

        return item_expr

    def _get_list_comprehension_loop_signature(
        self,
        content: str,
        target_for: ast.For,
        list_name: str,
        item_expr: str,
    ) -> tuple[str, str, int, int] | None:
        if not isinstance(target_for.target, (ast.Name, ast.Tuple, ast.List)):
            return None

        target_source = ast.get_source_segment(
            content, target_for.target
        ) or ast.unparse(target_for.target)
        iter_source = ast.get_source_segment(content, target_for.iter) or ast.unparse(
            target_for.iter
        )
        init_start = self._find_list_initialization_line(content, target_for, list_name)
        if init_start is None:
            return None

        return (
            target_source,
            iter_source,
            init_start,
            (target_for.end_lineno or target_for.lineno) - 1,
        )

    def _find_list_initialization_line(
        self, content: str, target_for: ast.For, list_name: str
    ) -> int | None:
        lines = content.split("\n")
        for_start = target_for.lineno - 1
        for idx in range(for_start - 1, -1, -1):
            line = lines[idx]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            for_indent = len(lines[for_start]) - len(lines[for_start].lstrip())
            if indent != for_indent:
                return None
            if stripped == f"{list_name} = []":
                return idx
            return None
        return None

    def _rewrite_loop_as_list_comprehension(
        self,
        content: str,
        target_for: ast.For,
        list_name: str,
        item_expr: str,
        loop_signature: tuple[str, str, int, int],
    ) -> str:
        lines = content.split("\n")
        target_source, iter_source, init_start, loop_end = loop_signature
        indent = lines[init_start][
            : len(lines[init_start]) - len(lines[init_start].lstrip())
        ]
        new_line = (
            f"{indent}{list_name} = [{item_expr} for {target_source} in {iter_source}]"
        )
        return "\n".join(lines[:init_start] + [new_line] + lines[loop_end + 1 :])

    def _transform_redundant_fstring(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []

        func_to_method: dict[str, str] = {
            "exists": "exists",
            "isdir": "is_dir",
            "isfile": "is_file",
            "islink": "is_symlink",
        }

        new_content = content
        for func_name, method_name in func_to_method.items():
            pattern = re.compile(
                r"os\.path\." + re.escape(func_name) + r"\s*\(([^)]*)\)"
            )
            new_content2 = pattern.sub(
                lambda m: f"Path({m.group(1)}).{method_name}()",
                new_content,
            )
            if new_content2 != new_content:
                count = len(pattern.findall(new_content))
                fixes.append(
                    f"Replaced {count} os.path.{func_name}(...) call(s) with Path(...).{method_name}()"  # noqa: E501
                )
                new_content = new_content2

        if fixes and "from pathlib import Path" not in new_content:
            if (
                "import pathlib" not in new_content
                and "from pathlib import" not in new_content
            ):
                lines = new_content.split("\n")
                insert_pos = 0
                in_docstring = False
                for i, line in enumerate(lines):
                    if '"""' in line or "'''" in line:
                        in_docstring = not in_docstring
                    if (
                        not in_docstring
                        and line.strip()
                        and (not line.strip().startswith("#"))
                    ):
                        insert_pos = i
                        break
                lines.insert(insert_pos, "from pathlib import Path")
                new_content = "\n".join(lines)

        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-pathlib-exists transformation",
        )

    def _transform_no_default_or(self, content: str, issue: Issue) -> tuple[str, str]:

        pattern = re.compile(
            r"""
            (?P<lhs>[A-Za-z_][A-Za-z0-9_\.]*)
            \s*=\s*
            (?P<expr>.+?)
            \s+or\s+
            (?P<falsey>""|''|0|None)
            (?P<trail>\s*)$
            """,
            re.MULTILINE | re.VERBOSE,
        )

        new_content = content
        fixes: list[str] = []
        for match in pattern.finditer(content):
            old = match.group(0)
            new = f"{match.group('lhs')} = {match.group('expr')}{match.group('trail')}"
            new_content = new_content.replace(old, new, 1)
            fixes.append(
                f"Removed redundant `or {match.group('falsey')}` from "
                f"assignment to `{match.group('lhs')}`"
            )
        return (
            new_content,
            "; ".join(fixes) if fixes else "No no-default-or transformation",
        )

    def _transform_redundant_lambda(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []

        charset_map: list[tuple[str, str]] = [
            (r'"0123456789"', "string.digits"),
            (r"'0123456789'", "string.digits"),
            (r'"0123456789abcdefABCDEF"', "string.hexdigits"),
            (r"'0123456789abcdefABCDEF'", "string.hexdigits"),
            (r'"abcdefghijklmnopqrstuvwxyz"', "string.ascii_lowercase"),
            (r"'abcdefghijklmnopqrstuvwxyz'", "string.ascii_lowercase"),
            (r'"ABCDEFGHIJKLMNOPQRSTUVWXYZ"', "string.ascii_uppercase"),
            (r"'ABCDEFGHIJKLMNOPQRSTUVWXYZ'", "string.ascii_uppercase"),
        ]
        new_content = content
        for pattern, replacement in charset_map:
            new_content2, count = re.subn(pattern, replacement, new_content)
            if count > 0:
                new_content = new_content2
                fixes.append(f"Replaced {count} inline alphabet(s) with {replacement}")

        if fixes and "import string" not in new_content:
            lines = new_content.split("\n")
            insert_pos = 0
            in_docstring = False
            for i, line in enumerate(lines):
                if '"""' in line or "'''" in line:
                    in_docstring = not in_docstring
                if (
                    not in_docstring
                    and line.strip()
                    and (not line.strip().startswith("#"))
                ):
                    insert_pos = i
                    break
            lines.insert(insert_pos, "import string")
            new_content = "\n".join(lines)

        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-string-charsets transformation",
        )

    def _transform_implicit_print(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(r"""\bDecimal\s*\(\s*(['"])(-?\d+)\1\s*\)""")
        new_content = pattern.sub(lambda m: f"Decimal({m.group(2)})", content)
        if new_content != content:
            fixes.append("Simplified Decimal(integer-string) to Decimal(int)")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No simplify-decimal-ctor transformation",
        )

    def _transform_dict_literal(self, content: str, issue: Issue) -> tuple[str, str]:
        _flag_map = {
            "I": "IGNORECASE",
            "M": "MULTILINE",
            "S": "DOTALL",
            "X": "VERBOSE",
            "A": "ASCII",
            "L": "LOCALE",
            "U": "UNICODE",
        }
        fixes: list[str] = []
        new_content = content
        for short, long in _flag_map.items():
            pat = re.compile(r"\bre\." + short + r"\b")
            result = pat.sub(f"re.{long}", new_content)
            if result != new_content:
                fixes.append(f"Replaced re.{short} with re.{long}")
                new_content = result
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-long-regex-flag transformation",
        )

    def _transform_isinstance_type_tuple(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        not_pattern = re.compile(
            r"\bnot\s+isinstance\s*\(\s*([\w.]+)\s*,\s*type\s*\(\s*None\s*\)\s*\)"
        )
        new_content = not_pattern.sub(r"\1 is not None", content)
        if new_content != content:
            fixes.append("Replaced not isinstance(x, type(None)) with x is not None")
        is_pattern = re.compile(
            r"\bisinstance\s*\(\s*([\w.]+)\s*,\s*type\s*\(\s*None\s*\)\s*\)"
        )
        new_content = is_pattern.sub(r"\1 is None", new_content)
        if new_content != content and "is None" in new_content:
            fixes.append("Replaced isinstance(x, type(None)) with x is None")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No no-isinstance-type-none transformation",
        )

    def _transform_type_none_comparison(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []

        is_type_none = re.compile(
            r"\btype\s*\(\s*([\w.]+)\s*\)\s+is\s+type\s*\(\s*None\s*\)"
        )
        new_content = is_type_none.sub(
            lambda m: f"{m.group(1)} is None",
            content,
        )
        if new_content != content:
            fixes.append("Rewrote type(x) is type(None) as x is None")
            content = new_content

        is_not_type_none = re.compile(
            r"\btype\s*\(\s*([\w.]+)\s*\)\s+is\s+not\s+type\s*\(\s*None\s*\)"
        )
        new_content = is_not_type_none.sub(
            lambda m: f"{m.group(1)} is not None",
            new_content,
        )
        if new_content != content:
            fixes.append("Rewrote type(x) is not type(None) as x is not None")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No no-is-type-none transformation",
        )

    def _transform_single_element_membership(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:

        pattern = re.compile(r"\b([\w.]+)\s+in\s+\(([^,)]+),\s*\)")
        new_content = pattern.sub(
            lambda m: f"{m.group(1)} == {m.group(2)}",
            content,
        )
        if new_content != content:
            fixes = "Converted x in (y,) to x == y"
        else:
            fixes = "No single-item-in transformation"
        return (new_content, fixes)

    def _transform_unnecessary_list_cast(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(
            r"\b([\w.]+)\.name\.endswith\s*\(\s*(['\"][^'\"]+['\"])\s*\)"
        )
        new_content = pattern.sub(r"\1.suffix == \2", content)
        if new_content != content:
            fixes.append("Replaced .name.endswith(...) with .suffix ==")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-suffix transformation",
        )

    def _transform_abs_sqr(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        _val = r"""(?:None|\.\.\.|"[^"]*"|'[^']*'|-?\d+(?:\.\d+)?)"""
        pattern = re.compile(
            r"\b(Query|Path|Body|Header|Cookie|Form|File)\s*\(\s*default\s*=\s*("
            + _val
            + r")\s*([,)])"
        )
        new_content = pattern.sub(r"\1(\2\3", content)
        if new_content != content:
            fixes.append("Replaced FastAPI param(default=X) with param(X)")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No simplify-fastapi-query transformation",
        )

    def _transform_unnecessary_from_float(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        utcnow_pat = re.compile(r"\bdatetime\.utcnow\s*\(\s*\)")
        new_content = utcnow_pat.sub("datetime.now(timezone.utc)", content)
        if new_content != content:
            fixes.append("Replaced datetime.utcnow() with datetime.now(timezone.utc)")
        utcfromts_pat = re.compile(r"\bdatetime\.utcfromtimestamp\s*\(\s*([\w.]+)\s*\)")
        result = utcfromts_pat.sub(
            r"datetime.fromtimestamp(\1, timezone.utc)", new_content
        )
        if result != new_content:
            fixes.append(
                "Replaced datetime.utcfromtimestamp() with datetime.fromtimestamp(..., timezone.utc)"  # noqa: E501
            )
            new_content = result
        return (
            new_content,
            "; ".join(fixes) if fixes else "No unreliable-utc-usage transformation",
        )

    def _transform_redundant_or(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(r"\bPath\s*\(\s*\)\s*\.\s*resolve\s*\(\s*\)")
        new_content = pattern.sub("Path.cwd()", content)
        if new_content != content:
            fixes.append("Replaced Path().resolve() with Path.cwd()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No no-implicit-cwd transformation",
        )

    def _transform_method_assign(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(r"\bclass\s+(\w+)\s*\(\s*metaclass\s*=\s*ABCMeta\s*\)\s*:")
        new_content = pattern.sub(r"class \1(ABC):", content)
        if new_content != content:
            fixes.append("Replaced metaclass=ABCMeta with ABC base class")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-abc-shorthand transformation",
        )

    def _transform_redundant_expression(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(r"\.digest\s*\(\s*\)\s*\.\s*hex\s*\(\s*\)")
        new_content = pattern.sub(".hexdigest()", content)
        if new_content != content:
            fixes.append("Replaced .digest().hex() with .hexdigest()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-hexdigest transformation",
        )

    def _transform_bad_version_info_compare(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(
            r"^(\s*)(\w+)\s*=\s*\2\.(\w+\([^)\n]*\))\s*\n"
            r"\s*\2\s*=\s*\2\.(\w+\([^)\n]*\))\s*$",
            re.MULTILINE,
        )
        new_content = pattern.sub(r"\1\2 = \2.\3.\4", content)
        if new_content != content:
            fixes.append("Chained consecutive method reassignments")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-fluid-interface transformation",
        )

    def _transform_redundant_substring(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(
            r"^(\s*)(\w+)\s*=\s*([\w.]+)\.copy\(\)\s*\n"
            r"\s*\2\.update\s*\(\s*([\w.]+)\s*\)\s*$",
            re.MULTILINE,
        )
        new_content = pattern.sub(r"\1\2 = \3 | \4", content)
        if new_content != content:
            fixes.append("Replaced .copy().update() with merge operator |")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No no-copy-with-merge transformation",
        )

    def _transform_redundant_cast(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        pattern = re.compile(
            r"^(\s*)(\w+)\s*=\s*sorted\s*\(\s*\2\s*\)\s*$",
            re.MULTILINE,
        )
        new_content = pattern.sub(r"\1\2.sort()", content)
        if new_content != content:
            fixes.append("Replaced VAR = sorted(VAR) with VAR.sort()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-sort transformation",
        )

    def _transform_chained_assignment(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        fixes: list[str] = []
        slice_pattern = re.compile(
            r"^(\s*)(\w+)\s*=\s*\2\s*\[\s*::\s*-1\s*\]\s*$",
            re.MULTILINE,
        )
        after_slice = slice_pattern.sub(r"\1\2.reverse()", content)
        if after_slice != content:
            fixes.append("Replaced VAR[::-1] with VAR.reverse()")
        reversed_pattern = re.compile(
            r"^(\s*)(\w+)\s*=\s*list\s*\(\s*reversed\s*\(\s*\2\s*\)\s*\)\s*$",
            re.MULTILINE,
        )
        new_content = reversed_pattern.sub(r"\1\2.reverse()", after_slice)
        if new_content != after_slice:
            fixes.append("Replaced list(reversed(VAR)) with VAR.reverse()")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-reverse transformation",
        )

    def _transform_slice_copy(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []

        suffix_pattern = re.compile(
            r"([a-z_]\w*(?:\.[a-z_]\w*)*)\[:-?len\((['\"])([^'\"]+)\2\)\]\s+if\s+\1\.endswith\(\2\3\2\)\s+else\s+\1\b"
        )
        new_content = content

        for m in list(suffix_pattern.finditer(content)):
            target = m.group(1)
            quote = m.group(2)
            lit = m.group(3)
            replacement = f"{target}.removesuffix({quote}{lit}{quote})"
            new_content = new_content.replace(m.group(0), replacement, 1)
            fixes.append(f"Rewrote endswith+slice as removesuffix({quote}{lit}{quote})")

        prefix_pattern = re.compile(
            r"([a-z_]\w*(?:\.[a-z_]\w*)*)\[len\((['\"])([^'\"]+)\2\):\]\s+if\s+\1\.startswith\(\2\3\2\)\s+else\s+\1\b"
        )
        for m in list(prefix_pattern.finditer(content)):
            target = m.group(1)
            quote = m.group(2)
            lit = m.group(3)
            replacement = f"{target}.removeprefix({quote}{lit}{quote})"
            new_content = new_content.replace(m.group(0), replacement, 1)
            fixes.append(
                f"Rewrote startswith+slice as removeprefix({quote}{lit}{quote})"
            )

        return (
            new_content,
            "; ".join(fixes) if fixes else "No remove-prefix-or-suffix transformation",
        )

    def _transform_fstring_to_print(
        self, content: str, issue: Issue
    ) -> tuple[str, str]:
        _builtin_map = {"list": "UserList", "dict": "UserDict", "str": "UserString"}
        fixes: list[str] = []
        new_content = content
        for builtin, user_cls in _builtin_map.items():
            pat = re.compile(r"\bclass\s+(\w+)\s*\(\s*" + builtin + r"\s*\)\s*:")
            result = pat.sub(rf"class \1({user_cls}):", new_content)
            if result != new_content:
                fixes.append(f"Replaced subclass of {builtin} with {user_cls}")
                new_content = result
        return (
            new_content,
            "; ".join(fixes) if fixes else "No no-subclass-builtin transformation",
        )

    def _transform_subprocess_list(self, content: str, issue: Issue) -> tuple[str, str]:
        fixes: list[str] = []
        str_methods = (
            "upper|lower|strip|lstrip|rstrip|title|capitalize|swapcase"
            "|isdigit|isalpha|isalnum|isspace|islower|isupper"
        )
        pattern = re.compile(
            r"\blambda\s+(\w+)\s*:\s*\1\s*\.\s*(" + str_methods + r")\s*\(\s*\)"
        )
        new_content = pattern.sub(r"str.\2", content)
        if new_content != content:
            fixes.append("Replaced lambda x: x.method() with str.method")
        return (
            new_content,
            "; ".join(fixes) if fixes else "No use-str-method transformation",
        )


from .base import agent_registry

agent_registry.register(RefurbCodeTransformerAgent)
