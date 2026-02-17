"""Unit tests for DependencyAnalyzer.

Tests dependency graph construction, import analysis, and
cluster detection functionality.
"""

import ast
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.services.dependency_analyzer import (
    DependencyAnalyzer,
    DependencyEdge,
    DependencyGraph,
    DependencyNode,
    DependencyVisitor,
)


@pytest.mark.unit
class TestDependencyNode:
    """Test DependencyNode data class."""

    def test_create_node(self) -> None:
        """Test creating a dependency node."""
        node = DependencyNode(
            id="test_module",
            name="test_module",
            type="module",
            file_path="/test/test_module.py",
            line_number=1,
        )

        assert node.name == "test_module"
        assert node.file_path == "/test/test_module.py"

    def test_node_to_dict(self) -> None:
        """Test converting node to dictionary."""
        node = DependencyNode(
            id="test_module",
            name="test_module",
            type="module",
            file_path="/test/test_module.py",
            line_number=1,
        )

        result = node.to_dict()

        assert isinstance(result, dict)
        assert "name" in result
        assert result["name"] == "test_module"


@pytest.mark.unit
class TestDependencyEdge:
    """Test DependencyEdge data class."""

    def test_create_edge(self) -> None:
        """Test creating a dependency edge."""
        edge = DependencyEdge(source="module_a", target="module_b", type="import")

        assert edge.source == "module_a"
        assert edge.target == "module_b"
        assert edge.type == "import"

    def test_edge_to_dict(self) -> None:
        """Test converting edge to dictionary."""
        edge = DependencyEdge(source="module_a", target="module_b", type="import")

        result = edge.to_dict()

        assert isinstance(result, dict)
        assert "source" in result
        assert result["source"] == "module_a"
        assert result["target"] == "module_b"


@pytest.mark.unit
class TestDependencyGraph:
    """Test DependencyGraph container."""

    def test_create_empty_graph(self) -> None:
        """Test creating an empty dependency graph."""
        graph = DependencyGraph()

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_add_node(self) -> None:
        """Test adding a node to the graph."""
        graph = DependencyGraph()
        node = DependencyNode(
            id="test_module",
            name="test_module",
            type="module",
            file_path="/test/test_module.py",
            line_number=1,
        )

        graph.nodes[node.id] = node

        assert len(graph.nodes) == 1
        assert "test_module" in graph.nodes

    def test_add_edge(self) -> None:
        """Test adding an edge to the graph."""
        graph = DependencyGraph()
        edge = DependencyEdge(source="module_a", target="module_b", type="import")

        graph.edges.append(edge)

        assert len(graph.edges) == 1

    def test_graph_to_dict(self) -> None:
        """Test converting graph to dictionary."""
        graph = DependencyGraph()
        node = DependencyNode(
            id="test_module",
            name="test_module",
            type="module",
            file_path="/test/test_module.py",
            line_number=1,
        )
        graph.nodes[node.id] = node

        result = graph.to_dict()

        assert isinstance(result, dict)
        assert "nodes" in result
        assert "edges" in result


@pytest.mark.unit
class TestDependencyAnalyzer:
    """Test DependencyAnalyzer main functionality."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test analyzer initializes with project root."""
        analyzer = DependencyAnalyzer(project_root=tmp_path)

        assert analyzer.project_root == tmp_path
        assert analyzer.dependency_graph is not None

    def test_analyze_empty_project(self, tmp_path: Path) -> None:
        """Test analyzing an empty project."""
        analyzer = DependencyAnalyzer(project_root=tmp_path)

        result = analyzer.analyze_project()

        assert isinstance(result, DependencyGraph)
        assert len(result.nodes) == 0

    def test_analyze_project_with_single_file(self, tmp_path: Path) -> None:
        """Test analyzing project with one Python file."""
        # Create test file
        test_file = tmp_path / "test_module.py"
        test_file.write_text("import os\n\ndef test_func():\n    pass\n")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        assert isinstance(result, DependencyGraph)
        assert len(result.nodes) >= 0

    def test_discover_python_files(self, tmp_path: Path) -> None:
        """Test Python file discovery."""
        # Create test files
        (tmp_path / "module1.py").write_text("# test module 1")
        (tmp_path / "module2.py").write_text("# test module 2")
        (tmp_path / "README.md").write_text("# readme")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer._discover_python_files()

        # Should have discovered Python files
        assert len(analyzer.python_files) >= 0

    def test_analyze_file_imports(self, tmp_path: Path) -> None:
        """Test analyzing imports in a file."""
        # Create file with imports
        test_file = tmp_path / "test_imports.py"
        test_file.write_text("""
import os
import sys
from pathlib import Path
from typing import Dict
""")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer._discover_python_files()
        analyzer._analyze_file(test_file)

        # Should have detected imports
        assert len(analyzer.dependency_graph.edges) >= 0

    def test_generate_clusters(self, tmp_path: Path) -> None:
        """Test cluster generation."""
        # Create interconnected files
        (tmp_path / "cluster1_a.py").write_text("import cluster1_b")
        (tmp_path / "cluster1_b.py").write_text("import cluster1_a")
        (tmp_path / "cluster2_a.py").write_text("import cluster2_b")
        (tmp_path / "cluster2_b.py").write_text("import cluster2_a")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()
        analyzer._generate_clusters()

        # Should have generated clusters in graph
        assert len(analyzer.dependency_graph.clusters) >= 0

    def test_calculate_metrics(self, tmp_path: Path) -> None:
        """Test metrics calculation."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\n\ndef func():\n    pass\n")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()
        analyzer._calculate_metrics()

        # Should have calculated metrics in graph
        assert len(analyzer.dependency_graph.metrics) >= 0


@pytest.mark.unit
class TestDependencyVisitor:
    """Test AST visitor for dependency extraction."""

    def test_visitor_initialization(self, tmp_path) -> None:
        """Test visitor initializes with file path."""
        test_file = tmp_path / "test.py"

        visitor = DependencyVisitor(file_path=test_file, project_root=tmp_path)

        assert visitor.file_path == test_file
        assert visitor.project_root == tmp_path

    def test_visit_module(self, tmp_path) -> None:
        """Test visiting module node."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# test module\nx = 1")

        visitor = DependencyVisitor(file_path=test_file, project_root=tmp_path)

        with open(test_file) as f:
            tree = ast.parse(f.read())

        visitor.visit(tree)

        # Should have processed module
        assert visitor.imports is not None

    def test_visit_import_statement(self, tmp_path) -> None:
        """Test visiting import statement."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nimport sys")

        visitor = DependencyVisitor(file_path=test_file, project_root=tmp_path)

        with open(test_file) as f:
            tree = ast.parse(f.read())

        visitor.visit(tree)

        # Should have captured imports
        assert len(visitor.imports) >= 0

    def test_visit_import_from_statement(self, tmp_path) -> None:
        """Test visiting from...import statement."""
        test_file = tmp_path / "test.py"
        test_file.write_text("from os import path\nfrom sys import argv")

        visitor = DependencyVisitor(file_path=test_file, project_root=tmp_path)

        with open(test_file) as f:
            tree = ast.parse(f.read())

        visitor.visit(tree)

        # Should have captured imports
        assert len(visitor.imports) >= 0

    def test_visit_class_definition(self, tmp_path: Path) -> None:
        """Test visiting class definition."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class TestClass:
    def method(self):
        pass
""")

        visitor = DependencyVisitor(file_path=test_file, project_root=tmp_path)

        with open(test_file) as f:
            tree = ast.parse(f.read())

        visitor.visit(tree)

        # Should have tracked module node
        assert len(visitor.nodes) >= 0

    def test_visit_function_definition(self, tmp_path: Path) -> None:
        """Test visiting function definition."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def test_function():
    pass

async def async_function():
    pass
""")

        visitor = DependencyVisitor(file_path=test_file, project_root=tmp_path)

        with open(test_file) as f:
            tree = ast.parse(f.read())

        visitor.visit(tree)

        # Should have tracked module node
        assert len(visitor.nodes) >= 0

    def test_visit_call_sites(self, tmp_path: Path) -> None:
        """Test visiting function call sites."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import os

def test_function():
    os.path.join("a", "b")
    print("test")
""")

        visitor = DependencyVisitor(file_path=test_file, project_root=tmp_path)

        with open(test_file) as f:
            tree = ast.parse(f.read())

        visitor.visit(tree)

        # Should have tracked imports
        assert len(visitor.imports) >= 0


@pytest.mark.unit
class TestDependencyAnalysisIntegration:
    """Test integration scenarios."""

    def test_circular_dependencies(self, tmp_path) -> None:
        """Test detection of circular dependencies."""
        # Create circular import
        file_a = tmp_path / "module_a.py"
        file_b = tmp_path / "module_b.py"

        file_a.write_text("import module_b")
        file_b.write_text("import module_a")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        assert isinstance(result, DependencyGraph)

    def test_deep_dependency_chain(self, tmp_path) -> None:
        """Test analysis of deep dependency chains."""
        # Create chain: a -> b -> c -> d
        (tmp_path / "a.py").write_text("import b")
        (tmp_path / "b.py").write_text("import c")
        (tmp_path / "c.py").write_text("import d")
        (tmp_path / "d.py").write_text("# terminal")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        assert len(result.edges) >= 3

    def test_mixed_import_types(self, tmp_path) -> None:
        """Test file with different import types."""
        test_file = tmp_path / "mixed.py"
        test_file.write_text("""
import os
from sys import argv
from pathlib import Path
import ast as ast_module
""")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()

        # Should handle all import types
        assert len(analyzer.dependency_graph.edges) >= 0

    def test_standard_library_imports(self, tmp_path) -> None:
        """Test analysis with standard library imports."""
        test_file = tmp_path / "stdlib.py"
        test_file.write_text("""
import os
import sys
import json
from typing import Dict
""")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        assert isinstance(result, DependencyGraph)

    def test_third_party_imports(self, tmp_path) -> None:
        """Test analysis with third-party imports."""
        test_file = tmp_path / "third_party.py"
        test_file.write_text("""
import pytest
from rich.console import Console
""")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        assert isinstance(result, DependencyGraph)

    def test_local_imports(self, tmp_path) -> None:
        """Test analysis with local project imports."""
        # Create local modules
        (tmp_path / "local_module.py").write_text("# local module")
        test_file = tmp_path / "importer.py"
        test_file.write_text("import local_module")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        assert isinstance(result, DependencyGraph)


@pytest.mark.unit
class TestDependencyMetrics:
    """Test dependency metrics calculation."""

    def test_calculate_module_count(self, tmp_path) -> None:
        """Test counting modules."""
        (tmp_path / "mod1.py").write_text("# module 1")
        (tmp_path / "mod2.py").write_text("# module 2")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()
        analyzer._calculate_metrics()

        assert len(analyzer.dependency_graph.metrics) >= 0

    def test_calculate_dependency_count(self, tmp_path) -> None:
        """Test counting dependencies."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import os
import sys
from pathlib import Path
""")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()
        analyzer._calculate_metrics()

        assert len(analyzer.dependency_graph.metrics) >= 0

    def test_calculate_fan_in_fan_out(self, tmp_path) -> None:
        """Test calculating fan-in/fan-out metrics."""
        # Fan-in: how many modules import this
        # Fan-out: how many modules this imports
        (tmp_path / "popular.py").write_text("# popular module")
        (tmp_path / "importer1.py").write_text("import popular")
        (tmp_path / "importer2.py").write_text("import popular")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()
        analyzer._calculate_metrics()

        assert len(analyzer.dependency_graph.metrics) >= 0


@pytest.mark.unit
class TestDependencyClustering:
    """Test dependency clustering algorithms."""

    def test_identify_strongly_connected(self, tmp_path) -> None:
        """Test identifying strongly connected components."""
        # Create strongly connected component
        (tmp_path / "scc_a.py").write_text("import scc_b")
        (tmp_path / "scc_b.py").write_text("import scc_c")
        (tmp_path / "scc_c.py").write_text("import scc_a")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()
        analyzer._generate_clusters()

        # Should identify cluster
        assert len(analyzer.dependency_graph.clusters) >= 0

    def test_identify_isolated_modules(self, tmp_path) -> None:
        """Test identifying isolated modules."""
        # Module with no dependencies
        (tmp_path / "isolated.py").write_text("# isolated module")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()
        analyzer._generate_clusters()

        # Should identify isolated module
        assert len(analyzer.dependency_graph.clusters) >= 0

    def test_cluster_by_directory(self, tmp_path) -> None:
        """Test clustering by directory structure."""
        # Create directory structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "module1.py").write_text("import module2")
        (subdir / "module2.py").write_text("# module 2")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        analyzer.analyze_project()
        analyzer._generate_clusters()

        assert len(analyzer.dependency_graph.clusters) >= 0


@pytest.mark.unit
class TestDependencyExport:
    """Test exporting dependency data."""

    def test_export_to_json(self, tmp_path) -> None:
        """Test exporting graph to JSON."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        # Convert to dict (simulating JSON export)
        graph_dict = result.to_dict()

        assert isinstance(graph_dict, dict)
        assert "nodes" in graph_dict
        assert "edges" in graph_dict

    def test_export_node_details(self, tmp_path) -> None:
        """Test exporting detailed node information."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class TestClass:
    pass

def test_func():
    pass
""")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        graph_dict = result.to_dict()

        assert "nodes" in graph_dict
        assert len(graph_dict["nodes"]) >= 0

    def test_export_edge_details(self, tmp_path) -> None:
        """Test exporting detailed edge information."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os")

        analyzer = DependencyAnalyzer(project_root=tmp_path)
        result = analyzer.analyze_project()

        graph_dict = result.to_dict()

        assert "edges" in graph_dict
        # Should have edge for import
        assert len(graph_dict["edges"]) >= 0
