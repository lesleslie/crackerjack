import ast
import typing as t


class ComplexityCalculator(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 0
        self.nesting_level = 0
        self.binary_sequences = 0

    def visit_If(self, node: ast.If) -> None:
        self._process_conditional_node(node)

    def visit_For(self, node: ast.For) -> None:
        self._process_loop_node(node)

    def visit_While(self, node: ast.While) -> None:
        self._process_loop_node(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._process_try_node(node)

    def visit_With(self, node: ast.With) -> None:
        self._process_context_node(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self._process_boolean_operation(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._process_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._process_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._process_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._process_comprehension(node)

    def _process_conditional_node(self, node: ast.If) -> None:
        self.complexity += 1 + self.nesting_level

        if self._has_complex_condition(node.test):
            self.complexity += 1

        self._visit_with_nesting(node)

    def _process_loop_node(self, node: ast.For | ast.While) -> None:
        self.complexity += 1 + self.nesting_level
        self._visit_with_nesting(node)

    def _process_try_node(self, node: ast.Try) -> None:
        self.complexity += 1 + self.nesting_level + len(node.handlers)
        self._visit_with_nesting(node)

    def _process_context_node(self, node: ast.With) -> None:
        self.complexity += 1 + self.nesting_level
        self._visit_with_nesting(node)

    def _process_boolean_operation(self, node: ast.BoolOp) -> None:
        penalty = len(node.values) - 1
        if penalty > 2:
            penalty += 1
        self.complexity += penalty
        self.generic_visit(node)

    def _process_comprehension(
        self, node: ast.ListComp | ast.DictComp | ast.SetComp | ast.GeneratorExp
    ) -> None:
        self.complexity += 1

        for generator in node.generators:
            if hasattr(generator, "ifs") and generator.ifs:
                self.complexity += len(generator.ifs)
        self.generic_visit(node)

    def _visit_with_nesting(self, node: ast.AST) -> None:
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def _has_complex_condition(self, node: ast.expr) -> bool:
        return (isinstance(node, ast.BoolOp) and len(node.values) > 2) or isinstance(
            node, ast.Compare | ast.Call
        )


class UsageDataCollector:
    def __init__(self) -> None:
        self.defined_names: set[str] = set()
        self.used_names: set[str] = set()
        self.import_lines: list[tuple[int, str, str]] = []
        self.unused_functions: list[dict[str, t.Any]] = []
        self.unused_classes: list[dict[str, t.Any]] = []
        self.unused_variables: list[dict[str, t.Any]] = []

    def get_results(self, analyzer: "EnhancedUsageAnalyzer") -> dict[str, t.Any]:
        return {
            "defined_names": self.defined_names,
            "used_names": self.used_names,
            "import_lines": self.import_lines,
            "unused_functions": self.unused_functions,
            "unused_classes": self.unused_classes,
            "unused_variables": self.unused_variables,
            "function_calls": analyzer.function_calls,
        }


class EnhancedUsageAnalyzer(ast.NodeVisitor):
    def __init__(self, collector: UsageDataCollector) -> None:
        self.scope_stack: list[set[str]] = [set()]
        self.class_methods: dict[str, list[str]] = {}
        self.function_calls: set[str] = set()
        self.collector = collector

    def visit_Import(self, node: ast.Import) -> None:
        self._process_import_node(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._process_import_from_node(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function_definition(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_async_function_definition(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._process_class_definition(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._process_assignment(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._process_annotated_assignment(node)

    def visit_Name(self, node: ast.Name) -> None:
        self._process_name_usage(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._process_function_call(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._process_attribute_access(node)

    def _process_import_node(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self.collector.defined_names.add(name)
            self.collector.import_lines.append((node.lineno, name, "import"))

    def _process_import_from_node(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self.collector.defined_names.add(name)
            self.collector.import_lines.append((node.lineno, name, "from_import"))

    def _process_function_definition(self, node: ast.FunctionDef) -> None:
        self.collector.defined_names.add(node.name)
        if self._should_track_function(node.name):
            function_info = self._create_function_info(node)
            self.collector.unused_functions.append(function_info)
        self._visit_with_scope(node)

    def _process_async_function_definition(self, node: ast.AsyncFunctionDef) -> None:
        self.collector.defined_names.add(node.name)
        if not node.name.startswith("_"):
            function_info = self._create_function_info(node)
            self.collector.unused_functions.append(function_info)
        self._visit_with_scope(node)

    def _process_class_definition(self, node: ast.ClassDef) -> None:
        self.collector.defined_names.add(node.name)
        self.collector.unused_classes.append(
            {
                "name": node.name,
                "line": node.lineno,
                "methods": [],
            }
        )
        self._visit_with_scope(node)

    def _process_assignment(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.collector.defined_names.add(target.id)
                if self._is_in_function_or_class_scope():
                    var_info = self._create_variable_info(target, node)
                    self.collector.unused_variables.append(var_info)
        self.generic_visit(node)

    def _process_annotated_assignment(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.collector.defined_names.add(node.target.id)
        self.generic_visit(node)

    def _process_name_usage(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.collector.used_names.add(node.id)
            if self.scope_stack:
                self.scope_stack[-1].add(node.id)

    def _process_function_call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self.function_calls.add(node.func.id)
            self.collector.used_names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                self.collector.used_names.add(node.func.value.id)
            self.function_calls.add(node.func.attr)
        self.generic_visit(node)

    def _process_attribute_access(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            self.collector.used_names.add(node.value.id)
        self.generic_visit(node)

    def _should_track_function(self, name: str) -> bool:
        return not name.startswith("_") and name != "__init__"

    def _create_function_info(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> dict[str, t.Any]:
        return {
            "name": node.name,
            "line": node.lineno,
            "is_method": len(self.scope_stack) > 1,
            "args": [arg.arg for arg in node.args.args],
        }

    def _create_variable_info(
        self, target: ast.Name, node: ast.Assign
    ) -> dict[str, t.Any]:
        return {
            "name": target.id,
            "line": node.lineno,
            "scope_level": len(self.scope_stack),
        }

    def _is_in_function_or_class_scope(self) -> bool:
        return len(self.scope_stack) > 1

    def _visit_with_scope(self, node: ast.AST) -> None:
        self.scope_stack.append(set())
        self.generic_visit(node)
        self.scope_stack.pop()
