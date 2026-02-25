
from __future__ import annotations

import ast
import logging
import re
import typing as t
from contextlib import suppress
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

        # FURB102: x.startswith(y) or x.startswith(z) -> x.startswith((y, z))
        content, fixes_102 = self._fix_furb102_regex(content)
        total_fixes += fixes_102

        # FURB107: try/except/pass -> with suppress() (only for single except with pass)
        content, fixes_107 = self._fix_furb107(content)
        total_fixes += fixes_107

        # FURB109: in (...) -> in (...)
        content, fixes_109 = self._fix_furb109(content)
        total_fixes += fixes_109

        return content, total_fixes

    def _fix_furb102_regex(self, content: str) -> tuple[str, int]:
        """FURB102: x.startswith(y) or x.startswith(z) -> x.startswith((y, z))."""
        total_fixes = 0
        new_content = content

        # Pattern: x.startswith(a) or x.startswith(b) -> x.startswith((a, b))
        # Only match at start of line (after indentation) to avoid docstrings
        pattern = r'^(\s*)(\w+)\.startswith\(([^)]+)\)\s+or\s+\2\.startswith\(([^)]+)\)'
        for match in re.finditer(pattern, new_content, re.MULTILINE):
            indent, var, arg1, arg2 = match.group(1), match.group(2), match.group(3), match.group(4)
            old_text = match.group(0)
            new_text = f'{indent}{var}.startswith(({arg1}, {arg2}))'
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        # Pattern: not x.startswith(a) and not x.startswith(b)
        pattern = r'^(\s*)not\s+(\w+)\.startswith\(([^)]+)\)\s+and\s+not\s+\2\.startswith\(([^)]+)\)'
        for match in re.finditer(pattern, new_content, re.MULTILINE):
            indent, var, arg1, arg2 = match.group(1), match.group(2), match.group(3), match.group(4)
            old_text = match.group(0)
            new_text = f'{indent}not {var}.startswith(({arg1}, {arg2}))'
            new_content = new_content.replace(old_text, new_text, 1)
            total_fixes += 1

        return new_content, total_fixes

    def _fix_furb107(self, content: str) -> tuple[str, int]:
        """FURB107: try/except/pass -> with suppress().

        Only converts try/except blocks that have:
        - Exactly ONE except handler
        - The handler body is ONLY 'pass'
        - No nested blocks in the try body
        """
        total_fixes = 0
        lines = content.split('\n')
        result_lines = lines.copy()
        i = 0

        while i < len(lines):
            line = lines[i]
            # Look for try: statements
            try_match = re.match(r'^(\s*)try:\s*$', line)
            if not try_match:
                i += 1
                continue

            indent = try_match.group(1)
            body_indent = indent + '    '

            # Scan for ALL except blocks in this try statement
            total_except_count = 0
            pass_only_except = None  # (except_line_idx, pass_line_idx, exception_type)
            j = i + 1

            while j < len(lines):
                curr_line = lines[j]

                # Check if we've exited the try block scope
                if curr_line.strip() and not curr_line.startswith(indent):
                    break

                # Check for any except line (including 'except X as e:' syntax)
                except_match = re.match(
                    rf'^{re.escape(indent)}except\s+(\w+(?:\s*,\s*\w+)*)(?:\s+as\s+\w+)?:',
                    curr_line
                ) or re.match(rf'^{re.escape(indent)}except\s*:', curr_line)

                if except_match:
                    total_except_count += 1
                    exception_type = except_match.group(1) if except_match.lastindex else 'Exception'

                    # Check if this except has only pass
                    # Case 1: inline pass (except X: pass)
                    inline_pass = re.match(
                        rf'^{re.escape(indent)}except\s+\w+(?:\s*,\s*\w+)*(?:\s+as\s+\w+)?:\s*pass\s*$',
                        curr_line
                    ) or re.match(rf'^{re.escape(indent)}except\s*:\s*pass\s*$', curr_line)

                    if inline_pass:
                        if pass_only_except is None:
                            pass_only_except = (j, None, exception_type)
                    else:
                        # Case 2: pass on next line
                        if j + 1 < len(lines):
                            pass_match = re.match(
                                rf'^{re.escape(body_indent)}pass\s*$',
                                lines[j + 1]
                            )
                            if pass_match:
                                if pass_only_except is None:
                                    pass_only_except = (j, j + 1, exception_type)
                                j += 1  # Skip the pass line in scanning
                            else:
                                # This except has actual code, not pass
                                pass_only_except = "INVALID"  # Mark as invalid
                        else:
                            pass_only_except = "INVALID"

                j += 1

            # Only convert if there's exactly ONE except block AND it's pass-only
            if total_except_count != 1 or pass_only_except is None or pass_only_except == "INVALID":
                i += 1
                continue

            except_line_idx, pass_line_idx, exception_type = pass_only_except

            # Check try body for nested blocks
            try_body = lines[i + 1:except_line_idx]
            has_nested = any(
                re.match(rf'^{re.escape(body_indent)}\w+.*:\s*$', line)
                for line in try_body if line.strip()
            )
            if has_nested:
                i += 1
                continue

            # Perform the transformation
            result_lines[i] = f'{indent}with suppress({exception_type}):'
            # Remove the except line and optionally the pass line
            if pass_line_idx is not None:
                del result_lines[pass_line_idx]
                del result_lines[except_line_idx]
                i = pass_line_idx
            else:
                del result_lines[except_line_idx]
                i = except_line_idx
            total_fixes += 1

        return '\n'.join(result_lines), total_fixes

    def _fix_furb109(self, content: str) -> tuple[str, int]:
        """FURB109: in (...) -> in (...)."""
        total_fixes = 0
        new_content = content

        # Handle for loops: for x in (...) -> for x in (...)
        # Only match single-line lists to avoid complex multiline cases
        for_pattern = r'^(\s*)for\s+(.+?)\s+in\s+\[([^\]\n]+)\]:'
        matches = list(re.finditer(for_pattern, new_content, re.MULTILINE))
        for match in reversed(matches):  # Reverse to preserve positions
            indent, var_name, list_contents = match.group(1), match.group(2).strip(), match.group(3)
            # Check if it's a simple list (no nested structures)
            if '[' not in list_contents and '{' not in list_contents:
                old_text = match.group(0)
                new_text = f'{indent}for {var_name} in ({list_contents}):'
                new_content = new_content[:match.start()] + new_text + new_content[match.end():]
                total_fixes += 1

        # Handle membership tests: in (...) -> in (...)
        # Only match single-line lists
        in_pattern = r'\bin\s+\[([^\]\n]+)\]'
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
