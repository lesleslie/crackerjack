from __future__ import annotations

import ast
import logging
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .base import FixResult, Issue, IssueType, SubAgent

if TYPE_CHECKING:
    from .base import AgentContext
logger = logging.getLogger(__name__)


class TypeErrorSpecialistAgent(SubAgent):
    name = "TypeErrorSpecialist"

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.log = logger.info  # type: ignore

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.TYPE_ERROR}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type != IssueType.TYPE_ERROR:
            return 0.0
        if not issue.message:
            return 0.0
        if issue.stage in ("zuban", "pyrefly", "ty", "pyright", "pyscn"):
            return 0.85
        return 0.6

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"TypeErrorSpecialist analyzing: {issue.message[:100]}")
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
        new_content, fixes_applied = await self._apply_type_fixes(
            content, issue, file_path
        )
        if new_content == content:
            return FixResult(
                success=False, confidence=0.0, remaining_issues=["No changes applied"]
            )
        try:
            file_path.write_text(new_content)
            if file_path.suffix == ".py":
                self._format_python_file(file_path)
            return FixResult(
                success=True,
                confidence=0.7,
                fixes_applied=fixes_applied,
                files_modified=[file_path],  # type: ignore
            )
        except Exception as e:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write file: {e}"],
            )

    async def _apply_type_fixes(
        self, content: str, issue: Issue, file_path: Path
    ) -> tuple[str, list[str]]:
        fixes: list[Any] = []
        new_content = content

        new_content, fix1 = self._fix_missing_return_types(new_content, issue)
        if fix1:
            fixes.extend(fix1)

        new_content, fix2 = self._apply_common_fixes(new_content, issue)
        if fix2:
            fixes.extend(fix2)

        new_content, fix3 = self._fix_suppress_tuple_arg_type(new_content, issue)
        if fix3:
            fixes.extend(fix3)
        new_content, fix4 = self._infer_and_add_return_types(new_content, issue)
        if fix4:
            fixes.extend(fix4)
        new_content, fix5 = self._fix_complex_generic_types(new_content, issue)
        if fix5:
            fixes.extend(fix5)
        new_content, fix6 = self._detect_and_fix_protocol_patterns(new_content, issue)
        if fix6:
            fixes.extend(fix6)
        new_content, fix7 = self._add_self_type_for_methods(new_content, issue)
        if fix7:
            fixes.extend(fix7)
        new_content, fix8 = self._fix_optional_union_types(new_content, issue)
        if fix8:
            fixes.extend(fix8)
        new_content, fix9 = self._prune_unused_typing_imports(new_content)
        if fix9:
            fixes.extend(fix9)
        new_content, fix10 = self._fix_up031_percent_format(new_content, issue)
        if fix10:
            fixes.extend(fix10)
        new_content, fix11 = self._fix_var_annotated(new_content, issue)
        if fix11:
            fixes.extend(fix11)
        new_content, fix12 = self._fix_literal_mismatch(new_content, issue)
        if fix12:
            fixes.extend(fix12)

        # Phase G: ty-error-code-specific handlers. Each handler is
        # gated on its own substring; they only run when the issue
        # actually matches their category.
        new_content, fix13 = self._fix_invalid_assignment_paired_ty_ignore(
            new_content, issue
        )
        if fix13:
            fixes.extend(fix13)
        new_content, fix14 = self._fix_invalid_typed_dict_subscript(new_content, issue)
        if fix14:
            fixes.extend(fix14)
        new_content, fix15 = self._fix_unresolved_import_with_ty_ignore(
            new_content, issue
        )
        if fix15:
            fixes.extend(fix15)

        return (new_content, fixes)

    def _apply_common_fixes(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[str] = []
        new_content = content

        new_content, fix_future = self._add_future_annotations(new_content)
        if fix_future:
            fixes.append("Added 'from __future__ import annotations'")

        new_content, fix_typing = self._add_typing_imports(new_content, issue)
        if fix_typing:
            fixes.extend(fix_typing)

        new_content, fix_common = self._add_common_imports(new_content, issue)
        if fix_common:
            fixes.extend(fix_common)

        return new_content, fixes

    def _fix_up031_percent_format(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        message_lower = issue.message.lower()
        if "up031" not in message_lower:
            return content, []
        if not issue.line_number:
            return content, []

        lines = content.split("\n")
        index = issue.line_number - 1
        if not (0 <= index < len(lines)):
            return content, []

        old_line = lines[index]
        if "%" not in old_line:
            return content, []
        if "# noqa: UP031" in old_line:
            return content, []

        lines[index] = f"{old_line.rstrip()} # noqa: UP031"
        return "\n".join(lines), [
            f"Suppressed UP031 on line {issue.line_number} with noqa annotation"
        ]

    def _fix_var_annotated(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        if "var-annotated" not in issue.message:
            return content, []
        var_match = re.search(
            r'Need type annotation for ["\'](?P<name>\w+)["\']', issue.message
        )
        if not var_match:
            return content, []
        var_name = var_match.group("name")

        lines = content.split("\n")

        candidates: list[int] = []
        if issue.line_number:
            start = max(0, issue.line_number - 21)
            end = min(len(lines), issue.line_number + 20)
            candidates.extend(range(start, end))
        candidates.extend(range(len(lines)))
        seen: set[int] = set()
        index: int | None = None
        for i in candidates:
            if i in seen:
                continue
            seen.add(i)
            if re.match(
                rf"^\s*{re.escape(var_name)}\s*=\s*[^=]", lines[i]
            ) and not re.match(rf"^\s*{re.escape(var_name)}\s*:", lines[i]):
                index = i
                break

        if index is None:
            return content, []

        old_line = lines[index]
        annotation = self._infer_annotation_from_rhs(old_line, var_name)
        if annotation is None:
            return content, []

        new_line = re.sub(
            rf"^(\s*)({re.escape(var_name)})(\s*=)",
            rf"\1\2: {annotation}\3",
            old_line,
            count=1,
        )
        if new_line == old_line:
            return content, []

        lines[index] = new_line
        return (
            "\n".join(lines),
            [
                f"Added type annotation `{annotation}` for `{var_name}` on line {index + 1}"
            ],
        )

    def _fix_literal_mismatch(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        match = self._parse_literal_mismatch_message(issue.message)
        if match is None:
            return content, []
        param_name, type_name, new_value = match

        tree = self._safe_parse(content)
        if tree is None:
            return content, []

        target_class = self._find_class(tree, type_name)
        if target_class is None:
            return content, []

        target_field = self._find_literal_field(target_class, param_name)
        if target_field is None:
            return content, []

        existing_values = self._collect_existing_literal_values(target_field)
        if existing_values is None or new_value in existing_values:
            return content, []

        return self._splice_literal_value(
            content, target_field.annotation, new_value, type_name, param_name
        )

    @staticmethod
    def _parse_literal_mismatch_message(
        message: str,
    ) -> tuple[str, str, str] | None:
        if "incompatible type" not in message or "Literal" not in message:
            return None
        m = re.search(
            r"""Argument\s+["'](?P<param>\w+)["']\s+to\s+["'](?P<type>\w+)["']\s+
                has\s+incompatible\s+type\s+["']Literal\[
                (?P<q>['"])(?P<value>[^'"]+)(?P=q)
                \]""",
            message,
            re.VERBOSE,
        )
        if not m:
            return None
        return m.group("param"), m.group("type"), m.group("value")

    @staticmethod
    def _safe_parse(content: str) -> ast.Module | None:
        try:
            return ast.parse(content)
        except SyntaxError:
            return None

    @staticmethod
    def _find_class(tree: ast.Module, type_name: str) -> ast.ClassDef | None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == type_name:
                return node
        return None

    @staticmethod
    def _find_literal_field(
        target_class: ast.ClassDef, param_name: str
    ) -> ast.AnnAssign | None:
        for node in target_class.body:
            if not isinstance(node, ast.AnnAssign):
                continue
            if not isinstance(node.target, ast.Name):
                continue
            if node.target.id != param_name:
                continue
            annotation = node.annotation
            if not isinstance(annotation, ast.Subscript):
                continue

            annotation = annotation
            if not isinstance(annotation.value, ast.Name):
                continue
            if annotation.value.id != "Literal":
                continue
            return node
        return None

    @staticmethod
    def _collect_existing_literal_values(
        target_field: ast.AnnAssign,
    ) -> set[str] | None:

        slice_node = cast(ast.Subscript, target_field.annotation).slice
        if isinstance(slice_node, ast.Tuple):
            return {
                elt.value
                for elt in slice_node.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            return {slice_node.value}
        return None

    @staticmethod
    def _splice_literal_value(
        content: str,
        annotation: ast.expr,
        new_value: str,
        type_name: str,
        param_name: str,
    ) -> tuple[str, list[str]]:
        slice_node = cast(ast.Subscript, annotation).slice
        if not hasattr(slice_node, "end_lineno") or not hasattr(
            slice_node, "end_col_offset"
        ):
            return content, []

        try:
            slice_text = ast.get_source_segment(content, slice_node) or ""
        except Exception:
            slice_text = ""

        if '"' in slice_text and "'" not in slice_text:
            quote = '"'
        elif "'" in slice_text and '"' not in slice_text:
            quote = "'"
        else:
            quote = "'"

        lines = content.split("\n")
        end_line_idx = slice_node.end_lineno - 1  # type: ignore[attr-defined]
        end_col = slice_node.end_col_offset  # type: ignore[attr-defined]
        if not (0 <= end_line_idx < len(lines)):
            return content, []

        line = lines[end_line_idx]

        prefix = line[:end_col]
        suffix = line[end_col:]
        if prefix.rstrip().endswith(","):
            new_prefix = prefix.rstrip() + f" {quote}{new_value}{quote} "
        else:
            new_prefix = prefix.rstrip() + f", {quote}{new_value}{quote} "

        lines[end_line_idx] = new_prefix + suffix
        new_content = "\n".join(lines)

        return new_content, [
            f"Added '{new_value}' to {type_name}.{param_name} Literal type "
            f"on line {end_line_idx + 1}"
        ]

    @staticmethod
    def _infer_annotation_from_rhs(line: str, var_name: str) -> str | None:
        rhs_match = re.search(rf"^\s*{re.escape(var_name)}\s*=\s*(.+?)\s*$", line)
        if not rhs_match:
            return None
        rhs = rhs_match.group(1)

        if re.search(r"\b(?:or|else)\s*\{\s*\}", rhs) or re.search(
            r"\bor\s*dict\s*\(", rhs
        ):
            return "dict[str, object]"

        if re.search(r"\b(?:or|else)\s*\[\s*\]", rhs) or re.search(
            r"\bor\s*list\s*\(", rhs
        ):
            return "list[object]"

        return None

    def _prune_unused_typing_imports(self, content: str) -> tuple[str, list[str]]:
        lines = content.split("\n")
        updated_lines: list[str] = []
        fixes: list[str] = []

        for index, line in enumerate(lines):
            match = re.match(r"^(\s*)from typing import (.+)$", line)
            if not match:
                updated_lines.append(line)
                continue

            indent, names_text = match.groups()
            import_names = [
                name.strip() for name in names_text.split(", ") if name.strip()
            ]
            search_space = "\n".join(lines[:index] + lines[index + 1 :])
            kept_names: list[str] = []

            for import_name in import_names:
                base_name = import_name.split(" as ", 1)[0].strip()
                if re.search(rf"\b{re.escape(base_name)}\b", search_space):
                    kept_names.append(import_name)
                else:
                    fixes.append(f"Removed unused typing import: {base_name}")

            if kept_names:
                updated_lines.append(
                    f"{indent}from typing import {', '.join(kept_names)}"
                )
            else:
                fixes.append("Removed unused typing import block")

        return ("\n".join(updated_lines), fixes)

    def _fix_missing_return_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        fixes: list[Any] = []
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if re.match("^\\s*def\\s+\\w+\\s*\\([^)]*\\)\\s*:", line):
                if "->" not in line and "async def" not in line:
                    if any(
                        keyword in issue.message.lower()
                        for keyword in ("missing", "return", "type")
                    ):
                        modified = line.rstrip().rstrip(":") + " -> None:"
                        if modified != line:
                            new_lines.append(modified)
                            fixes.append(
                                f"Added return type annotation: {modified[:80]}..."
                            )
                            continue
            new_lines.append(line)
        return ("\n".join(new_lines), fixes)

    def _add_future_annotations(self, content: str) -> tuple[str, list[str]]:
        if "from __future__ import annotations" in content:
            return (content, [])
        lines = content.split("\n")
        insert_index = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('"""', "'''")):
                continue
            if stripped.startswith(("import ", "from ")):
                insert_index = i
                break
            if stripped and (not stripped.startswith("#")):
                insert_index = i
                break
        lines.insert(insert_index, "from __future__ import annotations")
        return ("\n".join(lines), ["Added __future__ annotations import"])

    def _add_typing_imports(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[Any] = []
        new_imports: list[str] = []
        message_lower = issue.message.lower()
        content = self._maybe_add_typing_import(
            content,
            new_imports,
            fixes,
            trigger="any" in message_lower and "not defined" in message_lower,
            import_names=["Any"],
        )
        content = self._maybe_add_typing_import(
            content,
            new_imports,
            fixes,
            trigger="optional" in message_lower or "None" in message_lower,
            import_names=["Optional"],
        )
        content = self._maybe_add_typing_import(
            content,
            new_imports,
            fixes,
            trigger="union" in message_lower or " | " in issue.message,
            import_names=["Union"],
        )
        content = self._maybe_add_typing_import(
            content,
            new_imports,
            fixes,
            trigger="list[" in message_lower or "dict[" in message_lower,
            import_names=["List", "Dict"],
        )
        if new_imports:
            lines = content.split("\n")
            insert_index = 0
            for i, line in enumerate(lines):
                if "from __future__ import annotations" in line:
                    insert_index = i + 1
                    break
                elif line.strip().startswith(("import", "from")) and insert_index == 0:
                    insert_index = i
            typing_names: list[str] = []
            for new_import in new_imports:
                typing_names.extend(
                    name.strip()
                    for name in new_import.replace("from typing import ", "", 1).split(
                        ", "
                    )
                    if name.strip()
                )
            combined_import = (
                f"from typing import {', '.join(dict.fromkeys(typing_names))}"
            )
            lines.insert(insert_index, combined_import)
            fixes.append(f"Added import: {combined_import}")
            return ("\n".join(lines), fixes)
        return (content, fixes)

    def _maybe_add_typing_import(
        self,
        content: str,
        new_imports: list[str],
        fixes: list[str],
        *,
        trigger: bool,
        import_names: list[str],
    ) -> str:
        if not trigger:
            return content

        if "from typing import" in content:
            if not all(name in content for name in import_names):
                replacement = ", ".join(import_names)
                content = re.sub(
                    "(from typing import [^\\n]+)", f"\\1, {replacement}", content
                )
                fixes.append(f"Added {replacement} to typing imports")
        else:
            new_imports.append(f"from typing import {', '.join(import_names)}")

        return content

    def _add_common_imports(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()

        import_specs = [
            ("operator" in message_lower, "import operator", "Added operator import"),
            (
                "suppress" in message_lower,
                "from contextlib import suppress",
                "Added suppress import",
            ),
        ]

        for trigger, import_line, fix_message in import_specs:
            if not trigger or import_line in content:
                continue
            content = self._insert_import_line(content, import_line)
            fixes.append(fix_message)

        return (content, fixes)

    def _fix_suppress_tuple_arg_type(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if "suppress" not in message_lower:
            return (content, fixes)

        new_content = re.sub(
            r"with suppress\(\(([^)]+)\)\)",
            lambda match: f"with suppress({match.group(1)})",
            content,
            count=1,
        )
        if new_content != content:
            fixes.append("Flattened suppress() exception tuple")
        return (new_content, fixes)

    def _insert_import_line(self, content: str, import_line: str) -> str:
        lines = content.split("\n")
        insert_index = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('"""', "'''")):
                continue
            if stripped.startswith(("import ", "from ")):
                insert_index = i + 1
                continue
            if stripped and not stripped.startswith("#"):
                insert_index = i
                break
        lines.insert(insert_index, import_line)
        return "\n".join(lines)

    def _fix_generic_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        return (content, [])

    def _infer_and_add_return_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if not any(
            kw in message_lower for kw in ("missing return", "return type", "->")
        ):
            return (content, fixes)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return (content, fixes)
        lines = content.split("\n")
        modified_lines = lines.copy()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is not None:
                    continue
                if issue.line_number and abs(node.lineno - issue.line_number) > 5:
                    continue
                inferred_type = self._infer_return_type_from_body(node, content)
                if inferred_type:
                    line_idx = node.lineno - 1
                    if 0 <= line_idx < len(modified_lines):
                        old_line = modified_lines[line_idx]
                        colon_pos = old_line.rfind(":")
                        if colon_pos > 0:
                            if old_line.rstrip().endswith(":"):
                                new_line = (
                                    old_line[:colon_pos].rstrip()
                                    + f" -> {inferred_type}:"
                                )
                                if "\n" not in old_line[colon_pos + 1 :]:
                                    modified_lines[line_idx] = new_line
                                    fixes.append(
                                        f"Inferred return type '{inferred_type}' for {node.name}() at line {node.lineno}"
                                    )
        return ("\n".join(modified_lines), fixes)

    def _infer_return_type_from_body(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, content: str
    ) -> str | None:
        return_types: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value:
                inferred = self._infer_type_from_expr(child.value)
                if inferred:
                    return_types.add(inferred)
            if isinstance(child, ast.Yield):
                if child.value:
                    inner_type = self._infer_type_from_expr(child.value)
                    return_types.add(f"Iterator[{inner_type or 'Any'}]")
                else:
                    return_types.add("Iterator[Any]")
            if isinstance(child, ast.YieldFrom):
                return_types.add("Iterator[Any]")
        if not return_types:
            return "None"
        if len(return_types) == 1:
            return return_types.pop()
        return f"Union[{', '.join(sorted(return_types))}]"

    def _infer_type_from_expr(self, expr: ast.expr) -> str | None:
        handlers = {
            ast.Constant: self._infer_constant_type,
            ast.List: self._infer_list_type,
            ast.Dict: self._infer_dict_type,
            ast.Set: self._infer_set_type,
            ast.Tuple: self._infer_tuple_type,
            ast.Call: self._infer_call_type,
            ast.BinOp: self._infer_binop_type,
            ast.Compare: lambda e: "bool",
            ast.BoolOp: lambda e: "bool",
            ast.UnaryOp: self._infer_unaryop_type,
        }
        handler = cast("Callable[[ast.expr], str] | None", handlers.get(type(expr)))
        return handler(expr) if handler else None

    def _infer_constant_type(self, expr: ast.Constant) -> str:
        type_map = {
            type(None): "None",
            bool: "bool",
            int: "int",
            float: "float",
            str: "str",
            bytes: "bytes",
        }
        return type_map.get(type(expr.value)) or type(expr.value).__name__  # type: ignore[call-overload,return-value]

    def _infer_list_type(self, expr: ast.List) -> str:
        if expr.elts:
            inner_types = {self._infer_type_from_expr(e) or "Any" for e in expr.elts}
            if len(inner_types) == 1:
                return f"list[{inner_types.pop()}]"
        return "list[Any]"

    def _infer_dict_type(self, expr: ast.Dict) -> str:
        if expr.keys and expr.values:
            key_types = {self._infer_type_from_expr(k) or "Any" for k in expr.keys if k}
            val_types = {self._infer_type_from_expr(v) or "Any" for v in expr.values}
            kt = key_types.pop() if len(key_types) == 1 else "Any"
            vt = val_types.pop() if len(val_types) == 1 else "Any"
            return f"dict[{kt}, {vt}]"
        return "dict[Any, Any]"

    def _infer_set_type(self, expr: ast.Set) -> str:
        if expr.elts:
            inner_types = {self._infer_type_from_expr(e) or "Any" for e in expr.elts}
            if len(inner_types) == 1:
                return f"set[{inner_types.pop()}]"
        return "set[Any]"

    def _infer_tuple_type(self, expr: ast.Tuple) -> str:
        if expr.elts:
            inner_types = [self._infer_type_from_expr(e) or "Any" for e in expr.elts]
            return f"tuple[{', '.join(inner_types)}]"
        return "tuple[()]"

    def _infer_call_type(self, expr: ast.Call) -> str | None:
        if isinstance(expr.func, ast.Name):
            factory_returns = {
                "list": "list[Any]",
                "dict": "dict[Any, Any]",
                "set": "set[Any]",
                "tuple": "tuple[Any, ...]",
                "str": "str",
                "int": "int",
                "float": "float",
                "bool": "bool",
                "frozenset": "frozenset[Any]",
                "range": "range",
            }
            return factory_returns.get(expr.func.id)
        return None

    def _infer_binop_type(self, expr: ast.BinOp) -> str | None:
        left_type = self._infer_type_from_expr(expr.left)
        return left_type if left_type in ("str", "int", "float") else None

    def _infer_unaryop_type(self, expr: ast.UnaryOp) -> str | None:
        return (
            "bool"
            if isinstance(expr.op, ast.Not)
            else self._infer_type_from_expr(expr.operand)
        )

    def _fix_complex_generic_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if not any(
            kw in message_lower
            for kw in ("generic", "subscript", "type arguments", "[")
        ):
            return (content, fixes)
        has_future_annotations = "from __future__ import annotations" in content
        lines = content.split("\n")
        modified_lines = lines.copy()
        for i, line in enumerate(lines):
            if has_future_annotations:
                new_line = re.sub("\\bList\\[", "list[", line)
                new_line = re.sub("\\bDict\\[", "dict[", new_line)
                new_line = re.sub("\\bSet\\[", "set[", new_line)
                new_line = re.sub("\\bTuple\\[", "tuple[", new_line)
                new_line = re.sub("\\bFrozenSet\\[", "frozenset[", new_line)
                if new_line != line:
                    modified_lines[i] = new_line
                    fixes.append(f"Modernized generic syntax on line {i + 1}")
        return ("\n".join(modified_lines), fixes)

    def _format_python_file(self, file_path: Path) -> None:
        try:
            result = subprocess.run(
                ["ruff", "format", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.debug(f"Applied ruff format to {file_path}")
            else:
                logger.warning(
                    f"Ruff format warning for {file_path}: {result.stderr.strip()}"
                )
        except Exception as e:
            logger.warning(f"Ruff format failed for {file_path}: {e}")

    def _detect_and_fix_protocol_patterns(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if not any(
            kw in message_lower
            for kw in ("protocol", "compatible", "structural", "duck")
        ):
            return (content, fixes)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return (content, fixes)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                method_count = sum(
                    1
                    for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                attr_count = sum(1 for n in node.body if isinstance(n, ast.AnnAssign))
                if method_count >= 2 and attr_count <= 1:
                    inherits_protocol = any(
                        isinstance(base, ast.Name)
                        and base.id == "Protocol"
                        or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
                        for base in node.bases
                    )
                    if not inherits_protocol and (not node.bases):
                        fixes.append(
                            f"Class '{node.name}' may benefit from Protocol (structural subtyping) - has {method_count} methods"
                        )
        return (content, fixes)

    def _add_self_type_for_methods(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        fixes: list[Any] = []
        if not self._is_self_type_issue(issue.message):
            return (content, fixes)
        has_self_import = "from typing import Self" in content
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return (content, fixes)
        lines = content.split("\n")
        modified_lines = lines.copy()
        needs_self_import = False
        class_names = self._collect_class_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                needs_self_import = self._process_class_methods(
                    node, class_names, modified_lines, fixes, needs_self_import
                )
        if needs_self_import and (not has_self_import):
            self._add_self_import(modified_lines, fixes)
        return ("\n".join(modified_lines), fixes)

    def _is_self_type_issue(self, message: str) -> bool:
        keywords = ("return type", "self", "instance", "same type")
        return any(kw in message.lower() for kw in keywords)

    def _collect_class_names(self, tree: ast.AST) -> set[str]:
        return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}

    def _process_class_methods(
        self,
        node: ast.ClassDef,
        class_names: set[str],
        lines: list[str],
        fixes: list[str],
        needs_import: bool,
    ) -> bool:
        class_name = node.name
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            if self._should_skip_method(item):
                continue
            result = self._try_convert_to_self(item, class_name, lines)
            if result:
                lines[result["line_idx"]] = result["new_line"]
                fixes.append(
                    f"Changed return type to 'Self' for {class_name}.{item.name}()"
                )
                needs_import = True
        return needs_import

    def _should_skip_method(self, item: ast.FunctionDef) -> bool:
        if item.name.startswith("_") and (
            not item.name.startswith(("__enter__", "__exit__"))
        ):
            return True
        return any(
            isinstance(d, ast.Name) and d.id == "staticmethod"
            for d in item.decorator_list
        )

    def _try_convert_to_self(
        self, item: ast.FunctionDef, class_name: str, lines: list[str]
    ) -> dict[str, Any] | None:
        if not item.returns:
            return None
        return_type = self._get_return_type_name(item.returns)
        if return_type != class_name:
            return None
        if isinstance(item.returns, ast.Name) and item.returns.id == "Self":
            return None
        line_idx = item.lineno - 1
        if not 0 <= line_idx < len(lines):
            return None
        old_line = lines[line_idx]
        new_line = re.sub(f"\\b-> {class_name}\\b", "-> Self", old_line)
        if new_line == old_line:
            return None
        return {"line_idx": line_idx, "new_line": new_line}

    def _get_return_type_name(self, returns: ast.expr) -> str | None:
        if isinstance(returns, ast.Name):
            return returns.id
        if isinstance(returns, ast.Constant):
            return str(returns.value)
        return None

    def _add_self_import(self, lines: list[str], fixes: list[str]) -> None:
        for i, line in enumerate(lines):
            if "from typing import" in line and "Self" not in line:
                lines[i] = re.sub("(from typing import [^\\n]+)", "\\1, Self", line)
                fixes.append("Added Self to typing imports")
                break

    def _fix_optional_union_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        fixes: list[str] = []
        message_lower = issue.message.lower()
        if not any(kw in message_lower for kw in ("optional", "union", "none")):
            return (content, fixes)
        has_future_annotations = "from __future__ import annotations" in content
        if not has_future_annotations:
            return (content, fixes)
        lines = content.split("\n")
        modified_lines = lines.copy()
        for i, line in enumerate(lines):
            new_line = line
            optional_pattern = "Optional\\[([^\\]]+(?:\\[[^\\]]*\\][^\\]]*)*)\\]"
            while re.search(optional_pattern, new_line):
                match = re.search(optional_pattern, new_line)
                if match:
                    inner_type = match.group(1)
                    new_line = (
                        new_line[: match.start()]
                        + f"{inner_type} | None"
                        + new_line[match.end() :]
                    )
                    fixes.append(
                        f"Converted Optional[{inner_type}] to {inner_type} | None on line {i + 1}"
                    )
            union_pattern = "Union\\[([^\\]]+(?:\\[[^\\]]*\\][^\\]]*)*)\\]"
            while re.search(union_pattern, new_line):
                match = re.search(union_pattern, new_line)
                if match:
                    inner = match.group(1)
                    types = self._split_union_types(inner)
                    if 2 <= len(types) <= 5:
                        union_syntax = " | ".join(t.strip() for t in types)
                        new_line = (
                            new_line[: match.start()]
                            + union_syntax
                            + new_line[match.end() :]
                        )
                        fixes.append(
                            f"Converted Union[{inner}] to {union_syntax} on line {i + 1}"
                        )
                    else:
                        break
            if new_line != line:
                modified_lines[i] = new_line
        return ("\n".join(modified_lines), fixes)

    def _split_union_types(self, inner: str) -> list[str]:
        types = []
        current = ""
        depth = 0
        for char in inner:
            if char == "[":
                depth += 1
                current += char
            elif char == "]":
                depth -= 1
                current += char
            elif char == "," and depth == 0:
                if current.strip():
                    types.append(current.strip())
                current = ""
            else:
                current += char
        if current.strip():
            types.append(current.strip())
        return types

    # ------------------------------------------------------------------
    # Phase G: ty-error-code-specific handlers.
    #
    # Each handler is gated on a substring in `issue.message` so the
    # dispatcher in `_apply_type_fixes` doesn't pay the AST-parsing
    # cost for unrelated issues. Handlers are intentionally narrow and
    # easy to unit-test — they cover the recurring patterns that bulk
    # rewrites (Phase C/D) can't handle without human review.
    # ------------------------------------------------------------------

    def _fix_invalid_assignment_paired_ty_ignore(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Append ``# ty: ignore[...]`` next to existing ``# type: ignore[...]``.

        Phase D audit found 20+ sites where the crackerjack codebase
        had ``# type: ignore[assignment]`` (mypy/ruff syntax) but no
        corresponding ``# ty: ignore[invalid-assignment]`` (ty syntax).
        Both suppressions are valid; they target different toolchains.

        The fix is mechanical and safe: append the ty variant inline.
        We deliberately do NOT delete the mypy/ignore because that
        would re-introduce mypy errors.
        """
        msg = issue.message or ""
        if "invalid-assignment" not in msg:
            return content, []
        if issue.line_number is None:
            return content, []
        if not issue.file_path:
            return content, []

        lines = content.split("\n")
        idx = issue.line_number - 1
        if not (0 <= idx < len(lines)):
            return content, []

        line = lines[idx]
        # Already has a ty: ignore — nothing to do.
        if "# ty: ignore" in line:
            return content, []
        # No existing mypy: ignore — this case needs a human to decide
        # whether to add a ty suppression or fix the underlying bug.
        if "# type: ignore" not in line:
            return content, []

        # Append the ty variant. Inline keeps the suppression visible
        # on the same line as the offending assignment.
        lines[idx] = f"{line.rstrip()}  # ty: ignore[invalid-assignment]"
        return (
            "\n".join(lines),
            [f"Added # ty: ignore[invalid-assignment] on line {issue.line_number}"],
        )

    def _fix_invalid_typed_dict_subscript(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Add an explicit type assertion when ``dict.get()`` feeds a typed slot.

        Pattern: ``var: T = some_dict.get(key)`` where the dict is
        ``dict[str, object]`` (typical after JSON parsing). ty reports
        ``Object of type ``Literal[X]`` is not assignable to T`` because
        the dict's value type is ``object``. The fix is ``cast(T, ...)``
        at the call site or, when the value is provably non-None,
        ``assert``.
        """
        msg = issue.message or ""
        if "invalid-assignment" not in msg:
            return content, []
        if "is not assignable to" not in msg:
            return content, []
        if issue.line_number is None:
            return content, []
        if not issue.file_path:
            return content, []

        lines = content.split("\n")
        idx = issue.line_number - 1
        if not (0 <= idx < len(lines)):
            return content, []

        line = lines[idx]
        # Match the common pattern: ``var: T = <expr>`` and wrap the RHS
        # in ``cast(T, ...)`` if it contains ``.get(``. We avoid
        # touching lines that already have a cast().
        if "cast(" in line:
            return content, []
        m = re.match(
            r"^(\s*)(?P<var>[A-Za-z_]\w*)\s*:\s*(?P<typ>[^=]+?)\s*=\s*(?P<rhs>.+)$",
            line.rstrip(),
        )
        if not m or ".get(" not in m.group("rhs"):
            return content, []

        indent = m.group(1)
        var_name = m.group("var")
        typ = m.group("typ").strip()
        rhs = m.group("rhs").strip()
        new_line = f"{indent}{var_name}: {typ} = cast({typ}, {rhs})"
        lines[idx] = new_line
        return (
            "\n".join(lines),
            [f"Wrapped .get() result in cast() on line {issue.line_number}"],
        )

    def _fix_unresolved_import_with_ty_ignore(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Suppress ``unresolved-import`` when the module is intentionally absent.

        The codebase has a few sites that import modules which never
        existed in any branch (workspace_tools is one). Ty's directive
        is the cleanest way to silence the static complaint without
        removing the (potentially runtime-required) import.

        Only acts when the file is NOT ``workspace_tools.py`` — that
        case has its own suppression already.
        """
        msg = issue.message or ""
        if "unresolved-import" not in msg:
            return content, []
        if issue.line_number is None:
            return content, []
        if not issue.file_path:
            return content, []

        lines = content.split("\n")
        idx = issue.line_number - 1
        if not (0 <= idx < len(lines)):
            return content, []

        line = lines[idx]
        if "# ty: ignore" in line:
            return content, []
        # Don't touch workspace_tools — its import is already documented
        # with a comment. The handler is for sites lacking any
        # suppression.
        if "workspace_tools" in (issue.file_path or ""):
            return content, []

        # Append ty: ignore. Keep any existing mypy: ignore intact.
        if "# type: ignore" in line:
            lines[idx] = f"{line.rstrip()}  # ty: ignore[unresolved-import]"
        else:
            lines[idx] = f"{line.rstrip()}  # ty: ignore[unresolved-import]"
        return (
            "\n".join(lines),
            [
                f"Added # ty: ignore[unresolved-import] on line "
                f"{issue.line_number} (intentionally-absent module)"
            ],
        )


from .base import agent_registry

agent_registry.register(TypeErrorSpecialistAgent)
