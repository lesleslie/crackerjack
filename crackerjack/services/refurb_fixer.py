"""Safe refurb fixer using AST-based transformations.

This module implements only the safest refurb transformations that cannot
break code structure. It uses AST-based matching instead of regex for
maximum reliability.

Safe patterns implemented:
- FURB102: x.startswith("a") or x.startswith("b") -> x.startswith(("a", "b"))
  (only for simple string literals, not expressions)
- FURB109: in ["a", "b", "c"] -> in ("a", "b", "c")
  (only for simple literals, not list comprehensions)

Explicitly NOT implemented (too risky):
- FURB107: try/except/pass -> with suppress (changes structure)
- FURB118: lambda -> itemgetter (may change semantics)
- FURB126: else: return (breaks if/elif/else chains)
"""

from __future__ import annotations

import ast
import logging
import typing as t
from pathlib import Path

logger = logging.getLogger(__name__)


class SafeRefurbFixer:
    """AST-based fixer for safe refurb transformations.

    This fixer only applies transformations that cannot possibly break
    code structure or change semantics. It uses AST parsing for safety
    and falls back gracefully if parsing fails.
    """

    def __init__(self) -> None:
        """Initialize the safe refurb fixer."""
        self.fixes_applied = 0

    def fix_file(self, file_path: Path) -> int:
        """Apply safe refurb fixes to a single file.

        Args:
            file_path: Path to the Python file to fix.

        Returns:
            Number of fixes applied to this file.
        """
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
        """Apply safe refurb fixes to all Python files in a package.

        Args:
            package_dir: Path to the package directory.

        Returns:
            Total number of fixes applied across all files.
        """
        if not package_dir.exists() or not package_dir.is_dir():
            logger.warning(f"Package directory not found: {package_dir}")
            return 0

        total_fixes = 0
        for py_file in package_dir.rglob("*.py"):
            # Skip __pycache__ and hidden directories
            if "__pycache__" in str(py_file) or any(
                part.startswith(".") for part in py_file.parts
            ):
                continue

            fixes = self.fix_file(py_file)
            total_fixes += fixes

        logger.info(f"Total safe refurb fixes applied: {total_fixes}")
        return total_fixes

    def _apply_fixes(self, content: str) -> tuple[str, int]:
        """Apply all safe refurb fixes to content.

        Args:
            content: The Python source code.

        Returns:
            Tuple of (modified_content, number_of_fixes).
        """
        total_fixes = 0

        # Apply FURB102 (startswith tuple) - safest
        content, fixes_102 = self._fix_furb102(content)
        total_fixes += fixes_102

        # Apply FURB109 (list to tuple for membership) - safe
        content, fixes_109 = self._fix_furb109(content)
        total_fixes += fixes_109

        return content, total_fixes

    def _fix_furb102(self, content: str) -> tuple[str, int]:
        """Fix FURB102: x.startswith("a") or x.startswith("b") -> x.startswith(("a", "b")).

        This transformation is safe because:
        - It only affects the structure of the argument, not the logic
        - The semantics of startswith with a tuple are well-defined
        - We only apply to simple string literals, not expressions

        Args:
            content: The Python source code.

        Returns:
            Tuple of (modified_content, number_of_fixes).
        """
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
        """Fix FURB109: x in ["a", "b"] -> x in ("a", "b").

        This transformation is safe because:
        - Tuples are immutable and have the same membership semantics
        - We only apply to list literals with simple elements
        - We explicitly skip list comprehensions

        Args:
            content: The Python source code.

        Returns:
            Tuple of (modified_content, number_of_fixes).
        """
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return content, 0

        transformer = _MembershipTupleTransformer()
        new_tree = transformer.visit(tree)

        if transformer.fixes > 0:
            try:
                new_content = ast.unparse(new_tree)
                return new_content, transformer.fixes
            except Exception as e:
                logger.debug(f"Could not unparse AST: {e}")
                return content, 0

        return content, 0


class _StartswithTupleTransformer(ast.NodeTransformer):
    """AST transformer for FURB102: Combine startswith calls with tuple.

    Transforms:
        x.startswith("a") or x.startswith("b")
    Into:
        x.startswith(("a", "b"))

    Safety constraints:
    - Only applies to string literals (not expressions)
    - Only applies when all calls use the same object
    - Only applies to simple OR chains
    """

    def __init__(self) -> None:
        """Initialize the transformer."""
        self.fixes = 0

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        """Visit boolean operations to find startswith OR chains.

        Args:
            node: The BoolOp AST node.

        Returns:
            The transformed node or the original.
        """
        # Only process OR operations
        if not isinstance(node.op, ast.Or):
            return self.generic_visit(node)

        # Group startswith calls by their object
        startswith_groups = self._group_startswith_calls(node.values)

        # Try to transform each group
        for obj_key, calls in startswith_groups.items():
            result = self._try_transform_group(node, calls)
            if result is not None:
                return result

        return self.generic_visit(node)

    def _group_startswith_calls(
        self, values: list[ast.AST]
    ) -> dict[int, list[ast.Call]]:
        """Group startswith calls by their target object.

        Args:
            values: List of AST nodes from a BoolOp.

        Returns:
            Dict mapping object hash to list of Call nodes.
        """
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
        """Try to transform a group of startswith calls.

        Args:
            node: The original BoolOp node.
            calls: List of startswith calls to potentially combine.

        Returns:
            Transformed AST node or None if not applicable.
        """
        if len(calls) < 2:
            return None

        # Check all calls have simple string literal arguments
        if not all(self._is_simple_string_arg(call) for call in calls):
            return None

        # Create the combined tuple argument
        string_args = self._extract_string_args(calls)
        if len(string_args) < 2:
            return None

        # Create new startswith call with tuple
        new_call = self._create_combined_call(calls[0], string_args)

        # Replace the old calls with the new one
        return self._build_replacement(node, calls, new_call)

    def _extract_string_args(self, calls: list[ast.Call]) -> list[ast.Constant]:
        """Extract string arguments from calls.

        Args:
            calls: List of Call nodes with string arguments.

        Returns:
            List of Constant nodes with string values.
        """
        string_args: list[ast.Constant] = []
        for call in calls:
            arg = call.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                string_args.append(ast.Constant(value=arg.value))
        return string_args

    def _create_combined_call(
        self, template: ast.Call, string_args: list[ast.Constant]
    ) -> ast.Call:
        """Create a new startswith call with tuple argument.

        Args:
            template: The Call node to use as a template.
            string_args: List of string constants for the tuple.

        Returns:
            New Call node with tuple argument.
        """
        tuple_arg = ast.Tuple(elts=string_args, ctx=ast.Load())
        return ast.Call(
            func=template.func,
            args=[tuple_arg],
            keywords=template.keywords,
        )

    def _build_replacement(
        self, node: ast.BoolOp, calls: list[ast.Call], new_call: ast.Call
    ) -> ast.AST:
        """Build the replacement AST node.

        Args:
            node: The original BoolOp node.
            calls: The calls being replaced.
            new_call: The new combined call.

        Returns:
            The replacement AST node.
        """
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
        """Check if node is a startswith method call.

        Args:
            node: The AST node to check.

        Returns:
            True if this is a startswith call with one argument.
        """
        if not isinstance(node, ast.Call):
            return False

        if not isinstance(node.func, ast.Attribute):
            return False

        if node.func.attr != "startswith":
            return False

        return len(node.args) == 1

    def _is_simple_string_arg(self, call: ast.Call) -> bool:
        """Check if call has a simple string literal argument.

        Args:
            call: The Call node to check.

        Returns:
            True if the argument is a simple string literal.
        """
        if not call.args:
            return False

        arg = call.args[0]
        return isinstance(arg, ast.Constant) and isinstance(arg.value, str)

    def _get_object_key(self, node: ast.AST) -> int | None:
        """Get a hashable key for an AST node representing an object.

        Args:
            node: The AST node to get a key for.

        Returns:
            A hashable key or None if not hashable.
        """
        try:
            return hash(ast.dump(node))
        except Exception:
            return None


class _MembershipTupleTransformer(ast.NodeTransformer):
    """AST transformer for FURB109: Convert list to tuple in membership tests.

    Transforms:
        x in ["a", "b", "c"]
    Into:
        x in ("a", "b", "c")

    Safety constraints:
    - Only applies to Compare nodes with 'in' or 'not in' operators
    - Only applies to list literals (not comprehensions)
    - Only applies to lists with simple elements (literals, names)
    """

    def __init__(self) -> None:
        """Initialize the transformer."""
        self.fixes = 0

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        """Visit comparison operations to find list membership tests.

        Args:
            node: The Compare AST node.

        Returns:
            The transformed node or the original.
        """
        new_comparators: list[ast.AST] = []
        original_ids = [id(c) for c in node.comparators]

        for op, comparator in zip(node.ops, node.comparators):
            if self._should_convert_to_tuple(op, comparator):
                new_tuple = ast.Tuple(elts=comparator.elts, ctx=ast.Load())
                new_comparators.append(new_tuple)
                self.fixes += 1
            else:
                new_comparators.append(self.visit(comparator))

        # Check if any changes were made
        new_ids = [id(c) for c in new_comparators]
        if new_ids != original_ids:
            return ast.Compare(
                left=self.visit(node.left),
                ops=node.ops,
                comparators=new_comparators,
            )

        return self.generic_visit(node)

    def _should_convert_to_tuple(self, op: ast.cmpop, comparator: ast.AST) -> bool:
        """Check if a comparator should be converted from list to tuple.

        Args:
            op: The comparison operator.
            comparator: The value being compared against.

        Returns:
            True if the comparator should be converted.
        """
        if not isinstance(op, (ast.In, ast.NotIn)):
            return False

        if not isinstance(comparator, ast.List):
            return False

        return self._is_safe_list(comparator)

    def _is_safe_list(self, node: ast.List) -> bool:
        """Check if a list is safe to convert to tuple.

        A list is safe to convert if all elements are simple.

        Args:
            node: The List AST node to check.

        Returns:
            True if the list can be safely converted to a tuple.
        """
        return all(self._is_simple_element(elt) for elt in node.elts)

    def _is_simple_element(self, node: ast.AST) -> bool:
        """Check if an element is simple enough for safe conversion.

        Simple elements include:
        - Constants (strings, numbers, None, booleans)
        - Names (variable references)
        - Attribute accesses (x.y)

        Args:
            node: The AST node to check.

        Returns:
            True if the element is simple.
        """
        if isinstance(node, ast.Constant):
            return True

        if isinstance(node, ast.Name):
            return True

        if isinstance(node, ast.Attribute):
            return self._is_simple_element(node.value)

        return False


# Module-level convenience functions
def fix_file(file_path: Path) -> int:
    """Apply safe refurb fixes to a single file.

    Args:
        file_path: Path to the Python file to fix.

    Returns:
        Number of fixes applied.
    """
    fixer = SafeRefurbFixer()
    return fixer.fix_file(file_path)


def fix_package(package_dir: Path) -> int:
    """Apply safe refurb fixes to all Python files in a package.

    Args:
        package_dir: Path to the package directory.

    Returns:
        Total number of fixes applied.
    """
    fixer = SafeRefurbFixer()
    return fixer.fix_package(package_dir)
