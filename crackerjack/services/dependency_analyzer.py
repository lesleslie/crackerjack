"""Dependency analysis service for generating network graph visualizations."""

import ast
import json
import logging
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """Represents a node in the dependency graph."""

    id: str
    name: str
    type: str  # module, function, class, variable
    file_path: str
    line_number: int
    size: int = 1  # For visual sizing
    complexity: int = 0
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "size": self.size,
            "complexity": self.complexity,
            "imports": self.imports,
            "exports": self.exports,
            "metadata": self.metadata,
        }


@dataclass
class DependencyEdge:
    """Represents an edge (relationship) in the dependency graph."""

    source: str
    target: str
    type: str  # import, call, inheritance, composition
    weight: float = 1.0
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "weight": self.weight,
            "metadata": self.metadata,
        }


@dataclass
class DependencyGraph:
    """Complete dependency graph data structure."""

    nodes: dict[str, DependencyNode] = field(default_factory=dict)
    edges: list[DependencyEdge] = field(default_factory=list)
    clusters: dict[str, list[str]] = field(default_factory=dict)
    metrics: dict[str, t.Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "clusters": self.clusters,
            "metrics": self.metrics,
            "generated_at": self.generated_at.isoformat(),
        }


class DependencyAnalyzer:
    """Analyzes code dependencies and generates network graph data."""

    def __init__(self, project_root: Path):
        """Initialize with project root directory."""
        self.project_root = Path(project_root)
        self.python_files: list[Path] = []
        self.dependency_graph = DependencyGraph()

    def analyze_project(self) -> DependencyGraph:
        """Analyze the entire project and build dependency graph."""
        logger.info(f"Starting dependency analysis for {self.project_root}")

        # Discover Python files
        self._discover_python_files()

        # Parse each file for dependencies
        for file_path in self.python_files:
            try:
                self._analyze_file(file_path)
            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {e}")
                continue

        # Generate clusters and metrics
        self._generate_clusters()
        self._calculate_metrics()

        logger.info(
            f"Dependency analysis complete: "
            f"{len(self.dependency_graph.nodes)} nodes, "
            f"{len(self.dependency_graph.edges)} edges"
        )

        return self.dependency_graph

    def _discover_python_files(self) -> None:
        """Discover all Python files in the project."""
        self.python_files = list[t.Any](self.project_root.rglob("*.py"))

        # Filter out common excluded directories
        excluded_patterns = {
            "__pycache__",
            ".git",
            ".pytest_cache",
            "node_modules",
            "venv",
            ".venv",
            "build",
            "dist",
        }

        self.python_files = [
            f
            for f in self.python_files
            if not any(pattern in f.parts for pattern in excluded_patterns)
        ]

        logger.info(f"Discovered {len(self.python_files)} Python files")

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single Python file for dependencies."""
        try:
            content = file_path.read_text(encoding="utf-8")

            tree = ast.parse(content)
            visitor = DependencyVisitor(file_path, self.project_root)
            visitor.visit(tree)

            # Add nodes from this file
            for node in visitor.nodes:
                self.dependency_graph.nodes[node.id] = node

            # Add edges from this file
            self.dependency_graph.edges.extend(visitor.edges)

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")

    def _generate_clusters(self) -> None:
        """Generate clusters based on module hierarchy."""
        clusters: dict[str, list[str]] = {}

        for node_id, node in self.dependency_graph.nodes.items():
            # Create clusters based on directory structure
            relative_path = Path(node.file_path).relative_to(self.project_root)
            parts = relative_path.parts[:-1]  # Exclude filename

            if parts:
                cluster_name = "/".join(parts)
                if cluster_name not in clusters:
                    clusters[cluster_name] = []
                clusters[cluster_name].append(node_id)
            else:
                # Root level files
                if "root" not in clusters:
                    clusters["root"] = []
                clusters["root"].append(node_id)

        self.dependency_graph.clusters = clusters

    def _calculate_metrics(self) -> None:
        """Calculate graph metrics for visualization."""
        nodes = self.dependency_graph.nodes
        edges = self.dependency_graph.edges

        # Basic metrics
        metrics: dict[str, t.Any] = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "total_clusters": len(self.dependency_graph.clusters),
            "density": len(edges) / (len(nodes) * (len(nodes) - 1))
            if len(nodes) > 1
            else 0,
        }

        # Node type distribution
        type_counts: dict[str, int] = {}
        complexity_sum = 0

        for node in nodes.values():
            type_counts[node.type] = type_counts.get(node.type, 0) + 1
            complexity_sum += node.complexity

        metrics["node_types"] = type_counts
        metrics["average_complexity"] = complexity_sum / len(nodes) if nodes else 0

        # Edge type distribution
        edge_type_counts: dict[str, int] = {}
        for edge in edges:
            edge_type_counts[edge.type] = edge_type_counts.get(edge.type, 0) + 1

        metrics["edge_types"] = edge_type_counts

        # Find most connected nodes
        in_degree: dict[str, int] = {}
        out_degree: dict[str, int] = {}

        for edge in edges:
            out_degree[edge.source] = out_degree.get(edge.source, 0) + 1
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        # Top 10 most connected nodes
        from operator import itemgetter

        top_in = sorted(in_degree.items(), key=itemgetter(1), reverse=True)[:10]
        top_out = sorted(out_degree.items(), key=itemgetter(1), reverse=True)[:10]

        metrics["top_imported"] = [
            {"node": node, "count": count} for node, count in top_in
        ]
        metrics["top_exporters"] = [
            {"node": node, "count": count} for node, count in top_out
        ]

        self.dependency_graph.metrics = metrics


class DependencyVisitor(ast.NodeVisitor):
    """AST visitor for extracting dependency information."""

    def __init__(self, file_path: Path, project_root: Path):
        """Initialize visitor with file context."""
        self.file_path = file_path
        self.project_root = project_root
        self.relative_path = file_path.relative_to(project_root)
        self.module_name = str(self.relative_path).replace("/", ".").replace(".py", "")

        self.nodes: list[DependencyNode] = []
        self.edges: list[DependencyEdge] = []
        self.current_class: str | None = None
        self.imports: dict[str, str] = {}  # alias -> full_name

    def visit_Module(self, node: ast.Module) -> None:
        """Visit module and create module node."""
        module_node = DependencyNode(
            id=f"module:{self.module_name}",
            name=self.module_name,
            type="module",
            file_path=str(self.file_path),
            line_number=1,
            size=len(node.body),
            complexity=self._calculate_complexity(node),
            metadata={"docstring": ast.get_docstring(node)},
        )
        self.nodes.append(module_node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Handle import statements."""
        for alias in node.names:
            imported_name = alias.asname or alias.name
            self.imports[imported_name] = alias.name

            # Create import edge
            edge = DependencyEdge(
                source=f"module:{self.module_name}",
                target=f"module:{alias.name}",
                type="import",
                metadata={"line": node.lineno, "alias": alias.asname},
            )
            self.edges.append(edge)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle from...import statements."""
        if node.module:
            for alias in node.names:
                imported_name = alias.asname or alias.name
                full_name = f"{node.module}.{alias.name}"
                self.imports[imported_name] = full_name

                # Create import edge
                edge = DependencyEdge(
                    source=f"module:{self.module_name}",
                    target=f"symbol:{full_name}",
                    type="import_from",
                    metadata={
                        "line": node.lineno,
                        "module": node.module,
                        "symbol": alias.name,
                        "alias": alias.asname,
                    },
                )
                self.edges.append(edge)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Handle class definitions."""
        class_id = f"class:{self.module_name}.{node.name}"
        self.current_class = node.name

        class_node = DependencyNode(
            id=class_id,
            name=node.name,
            type="class",
            file_path=str(self.file_path),
            line_number=node.lineno,
            size=len(node.body),
            complexity=self._calculate_complexity(node),
            metadata={
                "docstring": ast.get_docstring(node),
                "decorators": [
                    self._get_decorator_name(d) for d in node.decorator_list
                ],
            },
        )
        self.nodes.append(class_node)

        # Handle inheritance
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name = self._resolve_name(base.id)
                edge = DependencyEdge(
                    source=class_id,
                    target=f"class:{base_name}",
                    type="inheritance",
                    metadata={"line": node.lineno},
                )
                self.edges.append(edge)

        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Handle function definitions."""
        if self.current_class:
            func_id = f"method:{self.module_name}.{self.current_class}.{node.name}"
            func_type = "method"
        else:
            func_id = f"function:{self.module_name}.{node.name}"
            func_type = "function"

        func_node = DependencyNode(
            id=func_id,
            name=node.name,
            type=func_type,
            file_path=str(self.file_path),
            line_number=node.lineno,
            size=len(node.body),
            complexity=self._calculate_complexity(node),
            metadata={
                "docstring": ast.get_docstring(node),
                "decorators": [
                    self._get_decorator_name(d) for d in node.decorator_list
                ],
                "args": [arg.arg for arg in node.args.args],
            },
        )
        self.nodes.append(func_node)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Handle function/method calls."""
        if isinstance(node.func, ast.Name):
            called_name = self._resolve_name(node.func.id)

            # Create call edge from current context
            source_id = self._get_current_context_id(node.lineno)
            if source_id:
                edge = DependencyEdge(
                    source=source_id,
                    target=f"function:{called_name}",
                    type="call",
                    weight=0.5,
                    metadata={"line": node.lineno},
                )
                self.edges.append(edge)

        elif isinstance(node.func, ast.Attribute):
            # Handle method calls
            if isinstance(node.func.value, ast.Name):
                obj_name = self._resolve_name(node.func.value.id)
                method_name = node.func.attr

                source_id = self._get_current_context_id(node.lineno)
                if source_id:
                    edge = DependencyEdge(
                        source=source_id,
                        target=f"method:{obj_name}.{method_name}",
                        type="call",
                        weight=0.5,
                        metadata={"line": node.lineno},
                    )
                    self.edges.append(edge)

        self.generic_visit(node)

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a node."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if isinstance(child, ast.If | ast.While | ast.For | ast.With | ast.Try):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(
                child, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
            ):
                complexity += 1

        return complexity

    def _get_decorator_name(self, decorator: ast.AST) -> str:
        """Get the name of a decorator."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{decorator.value.id}.{decorator.attr}"  # type: ignore
        return "unknown"

    def _resolve_name(self, name: str) -> str:
        """Resolve a name through imports."""
        return self.imports.get(name, f"{self.module_name}.{name}")

    def _get_current_context_id(self, line_number: int) -> str | None:
        """Get the ID of the current context (function/class/module)."""
        # For simplicity, return module context
        # In a more sophisticated implementation, we'd track the nested context
        return f"module:{self.module_name}"


def analyze_project_dependencies(project_root: str | Path) -> DependencyGraph:
    """Analyze project dependencies and return graph data."""
    analyzer = DependencyAnalyzer(Path(project_root))
    return analyzer.analyze_project()


def export_graph_data(graph: DependencyGraph, output_path: str | Path) -> None:
    """Export dependency graph to JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph.to_dict(), f, indent=2)
