import ast
import typing as t
from dataclasses import dataclass


@dataclass
class OptimizationResult:
    lines: list[str]
    modified: bool
    optimization_description: str | None = None


class EnhancedNestedLoopAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.loop_stack: list[tuple[str, ast.AST, int]] = []
        self.nested_loops: list[dict[str, t.Any]] = []
        self.complexity_hotspots: list[dict[str, t.Any]] = []

    def visit_For(self, node: ast.For) -> None:
        self._process_loop_node(node, "nested_for_loop")

    def visit_While(self, node: ast.While) -> None:
        self._process_loop_node(node, "nested_while_loop")

    def _process_loop_node(self, node: ast.For | ast.While, loop_type: str) -> None:
        current_depth = len(self.loop_stack) + 1
        self.loop_stack.append((loop_type.split("_")[1], node, current_depth))

        if current_depth > 1:
            loop_info = self._create_loop_info(node, loop_type, current_depth)
            self.nested_loops.append(loop_info)
            self._check_complexity_hotspot(loop_info, current_depth)

        self.generic_visit(node)
        self.loop_stack.pop()

    def _create_loop_info(
        self, node: ast.For | ast.While, loop_type: str, current_depth: int
    ) -> dict[str, t.Any]:
        loop_info: dict[str, t.Any] = {
            "line_number": node.lineno,
            "type": loop_type,
            "depth": current_depth,
            "complexity": f"O(n^{current_depth})",
            "complexity_factor": self._calculate_complexity_factor(current_depth),
            "priority": self._get_optimization_priority(current_depth),
            "node": node,
        }

        if isinstance(node, ast.For):
            loop_info["iterable"] = self._extract_iterable_info(node)

        return loop_info

    def _check_complexity_hotspot(
        self, loop_info: dict[str, t.Any], current_depth: int
    ) -> None:
        if current_depth >= 3:
            self.complexity_hotspots.append(
                loop_info
                | {
                    "severity": "high",
                    "suggestion": "Critical: Consider algorithmic improvements (memoization, caching, different data structures)",
                }
            )

    def _calculate_complexity_factor(self, depth: int) -> int:
        return depth**2

    def _get_optimization_priority(self, depth: int) -> str:
        if depth >= 4:
            return "critical"
        elif depth == 3:
            return "high"
        elif depth == 2:
            return "medium"
        return "low"

    def _extract_iterable_info(self, node: ast.For) -> dict[str, t.Any]:
        iterable_info = {"type": "unknown", "name": None}

        if isinstance(node.iter, ast.Name):
            iterable_info = {"type": "variable", "name": node.iter.id}
        elif isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name):
            iterable_info = {
                "type": "function_call",
                "name": node.iter.func.id,
            }
            if node.iter.func.id == "range":
                iterable_info["optimization_hint"] = (
                    "Consider list[t.Any] comprehension or vectorization"
                )

        return iterable_info


class EnhancedListOpAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.in_loop = False
        self.loop_depth = 0
        self.list_ops: list[dict[str, t.Any]] = []
        self.current_loop_node: ast.For | ast.While | None = None

    def visit_For(self, node: ast.For) -> None:
        self._enter_loop_context(node)
        self.generic_visit(node)
        self._exit_loop_context()

    def visit_While(self, node: ast.While) -> None:
        self._enter_loop_context(node)
        self.generic_visit(node)
        self._exit_loop_context()

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if self._should_analyze_aug_assign(node):
            self._analyze_aug_assign_node(node)
        self.generic_visit(node)

    def _enter_loop_context(self, node: ast.For | ast.While) -> None:
        self._old_state = (self.in_loop, self.loop_depth, self.current_loop_node)
        self.in_loop = True
        self.loop_depth += 1
        self.current_loop_node = node

    def _exit_loop_context(self) -> None:
        self.in_loop, self.loop_depth, self.current_loop_node = self._old_state

    def _should_analyze_aug_assign(self, node: ast.AugAssign) -> bool:
        return self.in_loop and isinstance(node.op, ast.Add)

    def _analyze_aug_assign_node(self, node: ast.AugAssign) -> None:
        impact_factor = self._calculate_performance_impact()

        if isinstance(node.value, ast.List):
            self._handle_list_concat(node, impact_factor)
        elif isinstance(node.value, ast.Name):
            self._handle_variable_concat(node, impact_factor)

    def _handle_list_concat(self, node: ast.AugAssign, impact_factor: int) -> None:
        assert isinstance(node.value, ast.List)
        list_size = len(node.value.elts)

        self.list_ops.append(
            {
                "line_number": node.lineno,
                "type": "list_concat_in_loop",
                "pattern": f"list[t.Any] += [{list_size} items]",
                "loop_depth": self.loop_depth,
                "impact_factor": impact_factor,
                "optimization": "append" if list_size == 1 else "extend",
                "performance_gain": f"{impact_factor * 2}x"
                if list_size > 1
                else "2-3x",
            }
        )

    def _handle_variable_concat(self, node: ast.AugAssign, impact_factor: int) -> None:
        var_name = getattr(node.value, "id", "unknown")
        self.list_ops.append(
            {
                "line_number": node.lineno,
                "type": "list_concat_variable",
                "pattern": f"list[t.Any] += {var_name}",
                "loop_depth": self.loop_depth,
                "impact_factor": impact_factor,
                "optimization": "extend",
                "performance_gain": f"{impact_factor * 3}x",
            }
        )

    def _calculate_performance_impact(self) -> int:
        base_impact = 2

        if self.loop_depth > 1:
            base_impact *= self.loop_depth**2

        if self._is_hot_loop():
            base_impact *= 5

        return min(base_impact, 50)

    def _is_hot_loop(self) -> bool:
        if not (self.current_loop_node and isinstance(self.current_loop_node, ast.For)):
            return False

        return self._has_large_range_iterator()

    def _has_large_range_iterator(self) -> bool:
        if not isinstance(self.current_loop_node, ast.For):
            return False

        iter_node = self.current_loop_node.iter
        if not (
            isinstance(iter_node, ast.Call)
            and isinstance(iter_node.func, ast.Name)
            and iter_node.func.id == "range"
        ):
            return False

        args = iter_node.args
        if not (args and isinstance(args[0], ast.Constant)):
            return False

        value = args[0].value
        return isinstance(value, int | float) and value > 100
