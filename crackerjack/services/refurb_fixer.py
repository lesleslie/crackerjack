
from __future__ import annotations

import ast
import logging
import typing as t
from pathlib import Path

logger = logging.getLogger(__name__)


class SafeRefurbFixer:

    def __init__(self) -> None:
        self.fixes_applied = 0

    def fix_file(self, file_path: Path) -> int:
        if not file_path.exists() or not file_path.is_file():
            return 0

        if file_path.suffix != ".py":
            return 0

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return 0

        new_content, fixes = self._apply_fixes(content)

        if new_content != content:
            try:
                file_path.write_text(new_content, encoding="utf-8")
                self.fixes_applied += fixes
                logger.info(f"Applied {fixes} safe refurb fixes to {file_path}")
                return fixes
            except OSError as e:
                logger.warning(f"Could not write {file_path}: {e}")
                return 0

        return 0

    def fix_package(self, package_dir: Path) -> int:
        if not package_dir.exists() or not package_dir.is_dir():
            logger.warning(f"Package directory not found: {package_dir}")
            return 0

        total_fixes = 0
        for py_file in package_dir.rglob("*.py"):

            if "__pycache__" in str(py_file) or any(
                part.startswith(".") for part in py_file.parts
            ):
                continue

            fixes = self.fix_file(py_file)
            total_fixes += fixes

        logger.info(f"Total safe refurb fixes applied: {total_fixes}")
        return total_fixes

    def _apply_fixes(self, content: str) -> tuple[str, int]:
        total_fixes = 0


        content, fixes_102 = self._fix_furb102(content)
        total_fixes += fixes_102


        content, fixes_109 = self._fix_furb109(content)
        total_fixes += fixes_109

        return content, total_fixes

    def _fix_furb102(self, content: str) -> tuple[str, int]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return content, 0

        transformer = _StartswithTupleTransformer()
        new_tree = transformer.visit(tree)

        if transformer.fixes > 0:
            try:
                new_content = ast.unparse(new_tree)
                return new_content, transformer.fixes
            except Exception as e:
                logger.debug(f"Could not unparse AST: {e}")
                return content, 0

        return content, 0

    def _fix_furb109(self, content: str) -> tuple[str, int]:
        import re

        total_fixes = 0
        new_content = content

        # Handle for loops: for x in (...) -> for x in (...)
        # Pattern: for <var> in (<simple elements>):
        for_pattern = r'for\s+(\w+)\s+in\s+\[([^\]]+)\]:'
        matches = list(re.finditer(for_pattern, new_content))
        for match in reversed(matches):  # Reverse to preserve positions
            var_name = match.group(1)
            list_contents = match.group(2)
            # Check if it's a simple list (no nested structures)
            if '[' not in list_contents and '{' not in list_contents:
                old_text = match.group(0)
                new_text = f'for {var_name} in ({list_contents}):'
                new_content = new_content[:match.start()] + new_text + new_content[match.end():]
                total_fixes += 1

        # Handle membership tests: in (...) -> in (...)
        # Pattern: <not> in (<simple elements>)
        in_pattern = r'\bin\s+\[([^\]]+)\]'
        for match in re.finditer(in_pattern, new_content):
            list_contents = match.group(1)
            if '[' not in list_contents and '{' not in list_contents:
                old_text = match.group(0)
                new_text = f'in ({list_contents})'
                new_content = new_content.replace(old_text, new_text, 1)
                total_fixes += 1

        return new_content, total_fixes


class _StartswithTupleTransformer(ast.NodeTransformer):

    def __init__(self) -> None:
        self.fixes = 0

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:

        if not isinstance(node.op, ast.Or):
            return self.generic_visit(node)


        startswith_groups = self._group_startswith_calls(node.values)


        for obj_key, calls in startswith_groups.items():
            result = self._try_transform_group(node, calls)
            if result is not None:
                return result

        return self.generic_visit(node)

    def _group_startswith_calls(
        self, values: list[ast.AST]
    ) -> dict[int, list[ast.Call]]:
        groups: dict[int, list[ast.Call]] = {}

        for value in values:
            if not self._is_startswith_call(value):
                continue

            call = t.cast(ast.Call, value)
            if not isinstance(call.func, ast.Attribute):
                continue

            obj_key = self._get_object_key(call.func.value)
            if obj_key is not None:
                groups.setdefault(obj_key, []).append(call)

        return groups

    def _try_transform_group(
        self, node: ast.BoolOp, calls: list[ast.Call]
    ) -> ast.AST | None:
        if len(calls) < 2:
            return None


        if not all(self._is_simple_string_arg(call) for call in calls):
            return None


        string_args = self._extract_string_args(calls)
        if len(string_args) < 2:
            return None


        new_call = self._create_combined_call(calls[0], string_args)


        return self._build_replacement(node, calls, new_call)

    def _extract_string_args(self, calls: list[ast.Call]) -> list[ast.Constant]:
        string_args: list[ast.Constant] = []
        for call in calls:
            arg = call.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                string_args.append(ast.Constant(value=arg.value))
        return string_args

    def _create_combined_call(
        self, template: ast.Call, string_args: list[ast.Constant]
    ) -> ast.Call:
        tuple_arg = ast.Tuple(elts=string_args, ctx=ast.Load())
        return ast.Call(
            func=template.func,
            args=[tuple_arg],
            keywords=template.keywords,
        )

    def _build_replacement(
        self, node: ast.BoolOp, calls: list[ast.Call], new_call: ast.Call
    ) -> ast.AST:
        new_values: list[ast.AST] = []
        replaced_ids = {id(c) for c in calls}

        for value in node.values:
            if id(value) not in replaced_ids:
                new_values.append(self.visit(value))

        new_values.append(new_call)
        self.fixes += 1

        if len(new_values) == 1:
            return new_values[0]
        return ast.BoolOp(op=ast.Or(), values=new_values)

    def _is_startswith_call(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False

        if not isinstance(node.func, ast.Attribute):
            return False

        if node.func.attr != "startswith":
            return False

        return len(node.args) == 1

    def _is_simple_string_arg(self, call: ast.Call) -> bool:
        if not call.args:
            return False

        arg = call.args[0]
        return isinstance(arg, ast.Constant) and isinstance(arg.value, str)

    def _get_object_key(self, node: ast.AST) -> int | None:
        try:
            return hash(ast.dump(node))
        except Exception:
            return None


class _MembershipTupleTransformer(ast.NodeTransformer):

    def __init__(self) -> None:
        self.fixes = 0

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        new_comparators: list[ast.AST] = []
        original_ids = [id(c) for c in node.comparators]

        for op, comparator in zip(node.ops, node.comparators):
            if self._should_convert_to_tuple(op, comparator):
                new_tuple = ast.Tuple(elts=comparator.elts, ctx=ast.Load())
                new_comparators.append(new_tuple)
                self.fixes += 1
            else:
                new_comparators.append(self.visit(comparator))


        new_ids = [id(c) for c in new_comparators]
        if new_ids != original_ids:
            return ast.Compare(
                left=self.visit(node.left),
                ops=node.ops,
                comparators=new_comparators,
            )

        return self.generic_visit(node)

    def _should_convert_to_tuple(self, op: ast.cmpop, comparator: ast.AST) -> bool:
        if not isinstance(op, (ast.In, ast.NotIn)):
            return False

        if not isinstance(comparator, ast.List):
            return False

        return self._is_safe_list(comparator)

    def _is_safe_list(self, node: ast.List) -> bool:
        return all(self._is_simple_element(elt) for elt in node.elts)

    def _is_simple_element(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return True

        if isinstance(node, ast.Name):
            return True

        if isinstance(node, ast.Attribute):
            return self._is_simple_element(node.value)

        return False


class _ForLoopTupleTransformer(ast.NodeTransformer):
    """Transform for x in (...) to for x in (...)."""

    def __init__(self) -> None:
        self.fixes = 0

    def visit_For(self, node: ast.For) -> ast.AST:
        # Check if iter is a list literal
        if isinstance(node.iter, ast.List):
            if self._is_safe_list(node.iter):
                # Convert list to tuple
                node.iter = ast.Tuple(elts=node.iter.elts, ctx=ast.Load())
                self.fixes += 1
        return self.generic_visit(node)

    def _is_safe_list(self, node: ast.List) -> bool:
        return all(self._is_simple_element(elt) for elt in node.elts)

    def _is_simple_element(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.Name):
            return True
        if isinstance(node, ast.Attribute):
            return self._is_simple_element(node.value)
        return False


def fix_file(file_path: Path) -> int:
    fixer = SafeRefurbFixer()
    return fixer.fix_file(file_path)


def fix_package(package_dir: Path) -> int:
    fixer = SafeRefurbFixer()
    return fixer.fix_package(package_dir)
