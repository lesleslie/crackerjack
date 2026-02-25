from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .base import FixResult, Issue, IssueType, SubAgent

if TYPE_CHECKING:
    from .base import AgentContext

logger = logging.getLogger(__name__)


class TypeErrorSpecialistAgent(SubAgent):
    """Specialized agent for fixing type annotation issues.

    This agent handles type errors from type checkers like zuban, pyright, and mypy.
    It can infer return types from function body AST analysis, handle complex
    generic types, detect Protocol patterns, and add Self types for methods.

    Capabilities:
    - Infer return types from function body analysis
    - Handle complex generic types (list[int], dict[str, Any])
    - Detect Protocol patterns for duck typing
    - Add Self type for class methods returning instances
    - Modern Python 3.10+ union syntax (X | Y)
    """

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

        if issue.stage in ("zuban", "pyscn"):
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
                success=False,
                confidence=0.0,
                remaining_issues=["No changes applied"],
            )

        try:
            file_path.write_text(new_content)
            return FixResult(
                success=True,
                confidence=0.7,
                fixes_applied=fixes_applied,
                files_modified=[str(file_path)],
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

        fixes = []
        new_content = content

        # Phase 1: Basic type fixes
        new_content, fix1 = self._fix_missing_return_types(new_content, issue)
        if fix1:
            fixes.extend(fix1)

        new_content, fix2 = self._add_future_annotations(new_content)
        if fix2:
            fixes.append("Added 'from __future__ import annotations'")

        new_content, fix3 = self._add_typing_imports(new_content, issue)
        if fix3:
            fixes.extend(fix3)

        # Phase 2: Enhanced type inference
        new_content, fix4 = self._infer_and_add_return_types(new_content, issue)
        if fix4:
            fixes.extend(fix4)

        # Phase 3: Complex generic types
        new_content, fix5 = self._fix_complex_generic_types(new_content, issue)
        if fix5:
            fixes.extend(fix5)

        # Phase 4: Protocol patterns
        new_content, fix6 = self._detect_and_fix_protocol_patterns(new_content, issue)
        if fix6:
            fixes.extend(fix6)

        # Phase 5: Self type for class methods
        new_content, fix7 = self._add_self_type_for_methods(new_content, issue)
        if fix7:
            fixes.extend(fix7)

        # Phase 6: Optional/Union fixes (modern syntax)
        new_content, fix8 = self._fix_optional_union_types(new_content, issue)
        if fix8:
            fixes.extend(fix8)

        return new_content, fixes

    def _fix_missing_return_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:

        fixes = []

        lines = content.split("\n")
        new_lines = []

        for line in lines:
            if re.match(r"^\s*def\s+\w+\s*\([^)]*\)\s*:", line):
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

        return "\n".join(new_lines), fixes

    def _add_future_annotations(self, content: str) -> tuple[str, list[str]]:

        if "from __future__ import annotations" in content:
            return content, []

        lines = content.split("\n")

        insert_index = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if stripped.startswith("import ") or stripped.startswith("from "):
                insert_index = i
                break
            if stripped and not stripped.startswith("#"):
                insert_index = i
                break

        lines.insert(insert_index, "from __future__ import annotations")
        return "\n".join(lines), ["Added __future__ annotations import"]

    def _add_typing_imports(self, content: str, issue: Issue) -> tuple[str, list[str]]:

        fixes = []
        new_imports = []

        message_lower = issue.message.lower()

        if "optional" in message_lower or "None" in message_lower:
            if "from typing import" in content:
                if "Optional" not in content:
                    content = re.sub(
                        r"(from typing import [^\n]+)",
                        r"\1, Optional",
                        content,
                    )
                    fixes.append("Added Optional to typing imports")
            else:
                new_imports.append("from typing import Optional")

        if "union" in message_lower or " | " in issue.message:
            if "from typing import" in content:
                if "Union" not in content:
                    content = re.sub(
                        r"(from typing import [^\n]+)",
                        r"\1, Union",
                        content,
                    )
                    fixes.append("Added Union to typing imports")
            else:
                new_imports.append("from typing import Union")

        if "list[" in message_lower or "dict[" in message_lower:
            if "from typing import" in content:
                if "List" not in content or "Dict" not in content:
                    content = re.sub(
                        r"(from typing import [^\n]+)",
                        r"\1, List, Dict",
                        content,
                    )
                    fixes.append("Added List, Dict to typing imports")
            else:
                new_imports.append("from typing import List, Dict")

        if new_imports:
            lines = content.split("\n")
            insert_index = 0

            for i, line in enumerate(lines):
                if "from __future__ import annotations" in line:
                    insert_index = i + 1
                    break
                elif (
                    line.strip().startswith("import") or line.strip().startswith("from")
                ) and insert_index == 0:
                    insert_index = i

            for new_import in reversed(new_imports):
                lines.insert(insert_index, new_import)
                fixes.append(f"Added import: {new_import}")

            return "\n".join(lines), fixes

        return content, fixes

    def _fix_generic_types(self, content: str, issue: Issue) -> tuple[str, list[str]]:
        """Legacy method - now handled by _fix_complex_generic_types."""
        return content, []

    def _infer_and_add_return_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Infer return types from function body AST analysis.

        This method analyzes function bodies to determine what type they return:
        - If no return statement → None
        - If only returns None → None
        - If returns literals → literal type (str, int, bool, etc.)
        - If returns variables → try to infer from assignments
        - If returns function calls → try to infer from callee
        """
        fixes: list[str] = []

        # Only proceed if issue mentions missing return type
        message_lower = issue.message.lower()
        if not any(
            kw in message_lower for kw in ("missing return", "return type", "->")
        ):
            return content, fixes

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return content, fixes

        lines = content.split("\n")
        modified_lines = list(lines)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip if already has return type annotation
                if node.returns is not None:
                    continue

                # Only fix if it's near the issue line
                if issue.line_number and abs(node.lineno - issue.line_number) > 5:
                    continue

                inferred_type = self._infer_return_type_from_body(node, content)
                if inferred_type:
                    # Modify the function definition line
                    line_idx = node.lineno - 1
                    if 0 <= line_idx < len(modified_lines):
                        old_line = modified_lines[line_idx]
                        # Find the colon and add return type before it
                        colon_pos = old_line.rfind(":")
                        if colon_pos > 0:
                            # Handle multi-line function defs by checking for continuation
                            if old_line.rstrip().endswith(":"):
                                new_line = (
                                    old_line[:colon_pos].rstrip()
                                    + f" -> {inferred_type}:"
                                )
                                if "\n" not in old_line[colon_pos + 1 :]:
                                    modified_lines[line_idx] = new_line
                                    fixes.append(
                                        f"Inferred return type '{inferred_type}' for "
                                        f"{node.name}() at line {node.lineno}"
                                    )

        return "\n".join(modified_lines), fixes

    def _infer_return_type_from_body(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, content: str
    ) -> str | None:
        """Analyze function body to infer return type.

        Returns:
            Inferred type string, or None if cannot infer.
        """
        return_types: set[str] = set()

        for child in ast.walk(node):
            # Check for return statements
            if isinstance(child, ast.Return) and child.value:
                inferred = self._infer_type_from_expr(child.value)
                if inferred:
                    return_types.add(inferred)

            # Check for yield statements (generator)
            if isinstance(child, ast.Yield):
                if child.value:
                    inner_type = self._infer_type_from_expr(child.value)
                    return_types.add(f"Iterator[{inner_type or 'Any'}]")
                else:
                    return_types.add("Iterator[Any]")

            # Check for yield from statements
            if isinstance(child, ast.YieldFrom):
                return_types.add("Iterator[Any]")

        # No return statements → None
        if not return_types:
            return "None"

        # Single return type → that type
        if len(return_types) == 1:
            return return_types.pop()

        # Multiple types → Union
        return f"Union[{', '.join(sorted(return_types))}]"

    def _infer_type_from_expr(self, expr: ast.expr) -> str | None:
        """Infer type from an expression using dispatch pattern."""
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
        handler = handlers.get(type(expr))
        return handler(expr) if handler else None

    def _infer_constant_type(self, expr: ast.Constant) -> str:
        """Infer type from a constant expression."""
        type_map = {
            type(None): "None",
            bool: "bool",
            int: "int",
            float: "float",
            str: "str",
            bytes: "bytes",
        }
        return type_map.get(type(expr.value), type(expr.value).__name__)

    def _infer_list_type(self, expr: ast.List) -> str:
        """Infer type from a list expression."""
        if expr.elts:
            inner_types = {self._infer_type_from_expr(e) or "Any" for e in expr.elts}
            if len(inner_types) == 1:
                return f"list[{inner_types.pop()}]"
        return "list[Any]"

    def _infer_dict_type(self, expr: ast.Dict) -> str:
        """Infer type from a dict expression."""
        if expr.keys and expr.values:
            key_types = {self._infer_type_from_expr(k) or "Any" for k in expr.keys if k}
            val_types = {self._infer_type_from_expr(v) or "Any" for v in expr.values}
            kt = key_types.pop() if len(key_types) == 1 else "Any"
            vt = val_types.pop() if len(val_types) == 1 else "Any"
            return f"dict[{kt}, {vt}]"
        return "dict[Any, Any]"

    def _infer_set_type(self, expr: ast.Set) -> str:
        """Infer type from a set expression."""
        if expr.elts:
            inner_types = {self._infer_type_from_expr(e) or "Any" for e in expr.elts}
            if len(inner_types) == 1:
                return f"set[{inner_types.pop()}]"
        return "set[Any]"

    def _infer_tuple_type(self, expr: ast.Tuple) -> str:
        """Infer type from a tuple expression."""
        if expr.elts:
            inner_types = [self._infer_type_from_expr(e) or "Any" for e in expr.elts]
            return f"tuple[{', '.join(inner_types)}]"
        return "tuple[()]"

    def _infer_call_type(self, expr: ast.Call) -> str | None:
        """Infer type from a function call."""
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
        """Infer type from a binary operation."""
        left_type = self._infer_type_from_expr(expr.left)
        return left_type if left_type in ("str", "int", "float") else None

    def _infer_unaryop_type(self, expr: ast.UnaryOp) -> str | None:
        """Infer type from a unary operation."""
        return (
            "bool"
            if isinstance(expr.op, ast.Not)
            else self._infer_type_from_expr(expr.operand)
        )

    def _fix_complex_generic_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Handle complex generic types like list[int], dict[str, Any].

        Converts old typing module syntax to modern Python 3.9+ syntax when
        from __future__ import annotations is present.
        """
        fixes: list[str] = []
        message_lower = issue.message.lower()

        # Check for generic type issues
        if not any(
            kw in message_lower
            for kw in ("generic", "subscript", "type arguments", "[")
        ):
            return content, fixes

        # Modern syntax is already used or file uses __future__ annotations
        has_future_annotations = "from __future__ import annotations" in content

        lines = content.split("\n")
        modified_lines = list(lines)

        for i, line in enumerate(lines):
            # Convert List[X] -> list[X] when using modern syntax
            if has_future_annotations:
                # Convert typing.List to list
                new_line = re.sub(r"\bList\[", "list[", line)
                new_line = re.sub(r"\bDict\[", "dict[", new_line)
                new_line = re.sub(r"\bSet\[", "set[", new_line)
                new_line = re.sub(r"\bTuple\[", "tuple[", new_line)
                new_line = re.sub(r"\bFrozenSet\[", "frozenset[", new_line)

                if new_line != line:
                    modified_lines[i] = new_line
                    fixes.append(f"Modernized generic syntax on line {i + 1}")

        return "\n".join(modified_lines), fixes

    def _detect_and_fix_protocol_patterns(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Detect Protocol patterns for duck typing.

        When a class has methods that match a common protocol pattern,
        suggest using Protocol instead of concrete type hints.
        """
        fixes: list[str] = []
        message_lower = issue.message.lower()

        # Check for protocol-related issues
        if not any(
            kw in message_lower
            for kw in ("protocol", "compatible", "structural", "duck")
        ):
            return content, fixes

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return content, fixes

        # Find classes that might benefit from Protocol
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class has only method definitions (protocol-like)
                method_count = sum(
                    1
                    for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                attr_count = sum(1 for n in node.body if isinstance(n, ast.AnnAssign))

                # If class looks like a protocol (mostly methods, few attributes)
                if method_count >= 2 and attr_count <= 1:
                    # Check if it already inherits from Protocol
                    inherits_protocol = any(
                        (isinstance(base, ast.Name) and base.id == "Protocol")
                        or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
                        for base in node.bases
                    )

                    if not inherits_protocol and not node.bases:
                        # Suggest adding Protocol as base
                        fixes.append(
                            f"Class '{node.name}' may benefit from Protocol "
                            f"(structural subtyping) - has {method_count} methods"
                        )

        return content, fixes

    def _add_self_type_for_methods(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Add Self type for class methods returning instances."""
        fixes = []
        if not self._is_self_type_issue(issue.message):
            return content, fixes

        has_self_import = "from typing import Self" in content

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return content, fixes

        lines = content.split("\n")
        modified_lines = list(lines)
        needs_self_import = False

        class_names = self._collect_class_names(tree)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                needs_self_import = self._process_class_methods(
                    node, class_names, modified_lines, fixes, needs_self_import
                )

        if needs_self_import and not has_self_import:
            self._add_self_import(modified_lines, fixes)

        return "\n".join(modified_lines), fixes

    def _is_self_type_issue(self, message: str) -> bool:
        """Check if issue is related to Self type."""
        keywords = ("return type", "self", "instance", "same type")
        return any(kw in message.lower() for kw in keywords)

    def _collect_class_names(self, tree: ast.AST) -> set[str]:
        """Collect all class names from AST."""
        return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}

    def _process_class_methods(
        self,
        node: ast.ClassDef,
        class_names: set[str],
        lines: list[str],
        fixes: list[str],
        needs_import: bool,
    ) -> bool:
        """Process methods in a class for Self type conversion."""
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
        """Check if method should be skipped for Self type conversion."""
        if item.name.startswith("_") and not item.name.startswith(
            ("__enter__", "__exit__")
        ):
            return True
        return any(
            isinstance(d, ast.Name) and d.id == "staticmethod"
            for d in item.decorator_list
        )

    def _try_convert_to_self(
        self, item: ast.FunctionDef, class_name: str, lines: list[str]
    ) -> dict | None:
        """Try to convert method return type to Self. Returns info dict or None."""
        if not item.returns:
            return None

        return_type = self._get_return_type_name(item.returns)
        if return_type != class_name:
            return None
        if isinstance(item.returns, ast.Name) and item.returns.id == "Self":
            return None

        line_idx = item.lineno - 1
        if not (0 <= line_idx < len(lines)):
            return None

        old_line = lines[line_idx]
        new_line = re.sub(rf"\b-> {class_name}\b", "-> Self", old_line)
        if new_line == old_line:
            return None

        return {"line_idx": line_idx, "new_line": new_line}

    def _get_return_type_name(self, returns: ast.expr) -> str | None:
        """Get the name of the return type annotation."""
        if isinstance(returns, ast.Name):
            return returns.id
        if isinstance(returns, ast.Constant):
            return str(returns.value)
        return None

    def _add_self_import(self, lines: list[str], fixes: list[str]) -> None:
        """Add Self to typing imports."""
        for i, line in enumerate(lines):
            if "from typing import" in line and "Self" not in line:
                lines[i] = re.sub(r"(from typing import [^\n]+)", r"\1, Self", line)
                fixes.append("Added Self to typing imports")
                break

    def _fix_optional_union_types(
        self, content: str, issue: Issue
    ) -> tuple[str, list[str]]:
        """Fix Optional/Union types with modern syntax.

        When using from __future__ import annotations, converts:
        - Optional[X] -> X | None
        - Union[X, Y] -> X | Y
        """
        fixes: list[str] = []
        message_lower = issue.message.lower()

        if not any(kw in message_lower for kw in ("optional", "union", "none")):
            return content, fixes

        # Only modernize if using __future__ annotations
        has_future_annotations = "from __future__ import annotations" in content
        if not has_future_annotations:
            return content, fixes

        lines = content.split("\n")
        modified_lines = list(lines)

        for i, line in enumerate(lines):
            new_line = line

            # Convert Optional[X] -> X | None
            optional_pattern = r"Optional\[([^\]]+(?:\[[^\]]*\][^\]]*)*)\]"
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

            # Convert Union[X, Y] -> X | Y (for 2-3 types)
            union_pattern = r"Union\[([^\]]+(?:\[[^\]]*\][^\]]*)*)\]"
            while re.search(union_pattern, new_line):
                match = re.search(union_pattern, new_line)
                if match:
                    inner = match.group(1)
                    # Handle nested brackets
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

        return "\n".join(modified_lines), fixes

    def _split_union_types(self, inner: str) -> list[str]:
        """Split Union type arguments respecting nested brackets.

        Args:
            inner: The inner content of Union[...].

        Returns:
            List of type strings.
        """
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


from .base import agent_registry

agent_registry.register(TypeErrorSpecialistAgent)
