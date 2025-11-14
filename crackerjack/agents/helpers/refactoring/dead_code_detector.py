"""Dead code detection and removal logic."""

import ast
import typing as t

from ..base import AgentContext


class DeadCodeDetector:
    """Detects dead code including unused imports and unreachable code."""

    def __init__(self, context: AgentContext) -> None:
        """Initialize detector with agent context.

        Args:
            context: AgentContext for logging
        """
        self.context = context

    def analyze_dead_code(self, tree: ast.AST, content: str) -> dict[str, t.Any]:
        """Analyze code for dead code patterns.

        Args:
            tree: AST tree
            content: File content

        Returns:
            Analysis results
        """
        analysis: dict[str, list[t.Any]] = {
            "unused_imports": [],
            "unused_variables": [],
            "unused_functions": [],
            "unused_classes": [],
            "unreachable_code": [],
            "removable_items": [],
        }

        analyzer_result = self._collect_usage_data(tree)
        self._process_unused_imports(analysis, analyzer_result)
        self._process_unused_functions(analysis, analyzer_result)
        self._process_unused_classes(analysis, analyzer_result)
        self._detect_unreachable_code(analysis, tree, content)
        self._detect_redundant_code(analysis, tree, content)

        return analysis

    def _collect_usage_data(self, tree: ast.AST) -> dict[str, t.Any]:
        """Collect usage data from AST.

        Args:
            tree: AST tree

        Returns:
            Usage data
        """
        collector = UsageDataCollector()
        analyzer = EnhancedUsageAnalyzer(collector)
        analyzer.visit(tree)
        return collector.get_results(analyzer)

    @staticmethod
    def _process_unused_imports(
        analysis: dict[str, t.Any],
        analyzer_result: dict[str, t.Any],
    ) -> None:
        """Process unused imports.

        Args:
            analysis: Analysis dict
            analyzer_result: Analyzer result
        """
        import_lines: list[tuple[int, str, str]] = analyzer_result["import_lines"]
        for line_no, name, import_type in import_lines:
            if name not in analyzer_result["used_names"]:
                analysis["unused_imports"].append(
                    {
                        "name": name,
                        "line": line_no,
                        "type": import_type,
                    },
                )
                analysis["removable_items"].append(f"unused import: {name}")

    @staticmethod
    def _process_unused_functions(
        analysis: dict[str, t.Any],
        analyzer_result: dict[str, t.Any],
    ) -> None:
        """Process unused functions.

        Args:
            analysis: Analysis dict
            analyzer_result: Analyzer result
        """
        all_unused_functions: list[dict[str, t.Any]] = analyzer_result[
            "unused_functions"
        ]
        unused_functions = [
            func
            for func in all_unused_functions
            if func["name"] not in analyzer_result["used_names"]
        ]
        analysis["unused_functions"] = unused_functions
        for func in unused_functions:
            analysis["removable_items"].append(f"unused function: {func['name']}")

    @staticmethod
    def _process_unused_classes(
        analysis: dict[str, t.Any], analyzer_result: dict[str, t.Any]
    ) -> None:
        """Process unused classes.

        Args:
            analysis: Analysis dict
            analyzer_result: Analyzer result
        """
        if "unused_classes" not in analyzer_result:
            return

        unused_classes = [
            cls
            for cls in analyzer_result["unused_classes"]
            if cls["name"] not in analyzer_result["used_names"]
        ]

        analysis["unused_classes"] = unused_classes
        for cls in unused_classes:
            analysis["removable_items"].append(f"unused class: {cls['name']}")

    @staticmethod
    def _detect_unreachable_code(
        analysis: dict[str, t.Any], tree: ast.AST, content: str
    ) -> None:
        """Detect unreachable code.

        Args:
            analysis: Analysis dict
            tree: AST tree
            content: File content
        """

        class UnreachableCodeDetector(ast.NodeVisitor):
            def __init__(self) -> None:
                self.unreachable_blocks: list[dict[str, t.Any]] = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._check_unreachable_in_function(node)
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._check_unreachable_in_function(node)
                self.generic_visit(node)

            def _check_unreachable_in_function(
                self, node: ast.FunctionDef | ast.AsyncFunctionDef
            ) -> None:
                for i, stmt in enumerate(node.body):
                    if isinstance(stmt, ast.Return | ast.Raise):
                        if i + 1 < len(node.body):
                            next_stmt = node.body[i + 1]
                            self.unreachable_blocks.append(
                                {
                                    "type": "unreachable_after_return",
                                    "line": next_stmt.lineno,
                                    "function": node.name,
                                }
                            )

        detector = UnreachableCodeDetector()
        detector.visit(tree)

        analysis["unreachable_code"] = detector.unreachable_blocks
        for block in detector.unreachable_blocks:
            analysis["removable_items"].append(
                f"unreachable code after line {block['line']} in {block['function']}"
            )

    @staticmethod
    def _detect_redundant_code(
        analysis: dict[str, t.Any], tree: ast.AST, content: str
    ) -> None:
        """Detect redundant code patterns.

        Args:
            analysis: Analysis dict
            tree: AST tree
            content: File content
        """
        lines = content.split("\n")

        line_hashes = {}
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith("#"):
                line_hash = hash(line.strip())
                if line_hash in line_hashes:
                    analysis["removable_items"].append(
                        f"potential duplicate code at line {i + 1}"
                    )
                line_hashes[line_hash] = i

        class RedundantPatternDetector(ast.NodeVisitor):
            def __init__(self) -> None:
                self.redundant_items: list[dict[str, t.Any]] = []

            def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    self.redundant_items.append(
                        {"type": "empty_except", "line": node.lineno}
                    )
                self.generic_visit(node)

            def visit_If(self, node: ast.If) -> None:
                if isinstance(node.test, ast.Constant):
                    if node.test.value is True:
                        self.redundant_items.append(
                            {"type": "if_true", "line": node.lineno}
                        )
                    elif node.test.value is False:
                        self.redundant_items.append(
                            {"type": "if_false", "line": node.lineno}
                        )
                self.generic_visit(node)

        detector = RedundantPatternDetector()
        detector.visit(tree)

        for item in detector.redundant_items:
            analysis["removable_items"].append(
                f"redundant {item['type']} at line {item['line']}"
            )

    def find_lines_to_remove(
        self, lines: list[str], analysis: dict[str, t.Any]
    ) -> set[int]:
        """Find lines to remove.

        Args:
            lines: File lines
            analysis: Analysis results

        Returns:
            Set of line indices to remove
        """
        lines_to_remove: set[int] = set()

        for unused_import in analysis["unused_imports"]:
            line_idx = unused_import["line"] - 1
            if 0 <= line_idx < len(lines):
                line = lines[line_idx]
                if self._should_remove_import_line(line, unused_import):
                    lines_to_remove.add(line_idx)

        return lines_to_remove

    @staticmethod
    def _should_remove_import_line(line: str, unused_import: dict[str, str]) -> bool:
        """Check if import line should be removed.

        Args:
            line: Code line
            unused_import: Unused import info

        Returns:
            True if should remove
        """
        if unused_import["type"] == "import":
            return f"import {unused_import['name']}" in line
        elif unused_import["type"] == "from_import":
            return (
                "from " in line
                and unused_import["name"] in line
                and line.strip().endswith(unused_import["name"])
            )
        return False

    @staticmethod
    def _find_unreachable_lines(
        lines: list[str], analysis: dict[str, t.Any]
    ) -> set[int]:
        """Find unreachable code lines.

        Args:
            lines: File lines
            analysis: Analysis results

        Returns:
            Set of line indices
        """
        lines_to_remove: set[int] = set()

        for item in analysis.get("unreachable_code", []):
            if "line" in item:
                line_idx = item["line"] - 1
                if 0 <= line_idx < len(lines):
                    lines_to_remove.add(line_idx)

        return lines_to_remove

    @staticmethod
    def _find_redundant_lines(lines: list[str], analysis: dict[str, t.Any]) -> set[int]:
        """Find redundant code lines.

        Args:
            lines: File lines
            analysis: Analysis results

        Returns:
            Set of line indices
        """
        lines_to_remove: set[int] = set()

        for i in range(len(lines)):
            if DeadCodeDetector._is_empty_except_block(lines, i):
                empty_pass_idx = DeadCodeDetector._find_empty_pass_line(lines, i)
                if empty_pass_idx is not None:
                    lines_to_remove.add(empty_pass_idx)

        return lines_to_remove

    @staticmethod
    def _is_empty_except_block(lines: list[str], line_idx: int) -> bool:
        """Check if except block is empty.

        Args:
            lines: File lines
            line_idx: Line index

        Returns:
            True if empty except block
        """
        stripped = lines[line_idx].strip()
        return stripped == "except: " or stripped.startswith("except ")

    @staticmethod
    def _find_empty_pass_line(lines: list[str], except_idx: int) -> int | None:
        """Find empty pass line in except block.

        Args:
            lines: File lines
            except_idx: Except line index

        Returns:
            Pass line index or None
        """
        for j in range(except_idx + 1, min(except_idx + 5, len(lines))):
            next_line = lines[j].strip()
            if not next_line:
                continue
            if next_line == "pass":
                return j
            break
        return None


class UsageDataCollector:
    """Collects usage data from AST traversal."""

    def __init__(self) -> None:
        """Initialize collector."""
        self.imports: dict[str, str] = {}
        self.import_lines: list[tuple[int, str, str]] = []
        self.functions: list[dict[str, t.Any]] = []
        self.classes: list[dict[str, t.Any]] = []
        self.usages: set[str] = set()

    def get_results(self, analyzer: "EnhancedUsageAnalyzer") -> dict[str, t.Any]:
        """Get collection results.

        Args:
            analyzer: Enhanced usage analyzer

        Returns:
            Results dict
        """
        return {
            "import_lines": self.import_lines,
            "used_names": analyzer.used_names,
            "unused_functions": self.functions,
            "unused_classes": self.classes,
        }


class EnhancedUsageAnalyzer(ast.NodeVisitor):
    """Enhanced analyzer for tracking usage."""

    def __init__(self, collector: UsageDataCollector) -> None:
        """Initialize analyzer.

        Args:
            collector: Usage data collector
        """
        self.collector = collector
        self.used_names: set[str] = set()
        self.line_counter = 0

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement."""
        for alias in node.names:
            name = alias.asname or alias.name
            self.collector.import_lines.append((node.lineno, name, "import"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from import statement."""
        for alias in node.names:
            name = alias.asname or alias.name
            self.collector.import_lines.append((node.lineno, name, "from_import"))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self.collector.functions.append({"name": node.name, "line": node.lineno})
        self.used_names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        self.collector.classes.append({"name": node.name, "line": node.lineno})
        self.used_names.add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Visit name reference."""
        self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access."""
        self.used_names.add(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call."""
        if isinstance(node.func, ast.Name):
            self.used_names.add(node.func.id)
        self.generic_visit(node)
