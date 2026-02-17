"""Test parallel workflow execution in Oneiric workflow builder.

Tests the _build_dag_nodes() function to ensure proper parallel execution
when enable_parallel_phases is True.
"""
from __future__ import annotations

from typing import Any

from crackerjack.runtime.oneiric_workflow import _build_dag_nodes


class MockOptions:
    """Mock options object for testing."""

    def __init__(self, **kwargs: Any) -> None:
        self.no_config_updates: bool = kwargs.get("no_config_updates", False)
        self.strip_code: bool = kwargs.get("strip_code", False)
        self.clean: bool = kwargs.get("clean", False)
        self.comp: bool = kwargs.get("comp", False)
        self.skip_hooks: bool = kwargs.get("skip_hooks", False)
        self.fast: bool = kwargs.get("fast", False)
        self.fast_iteration: bool = kwargs.get("fast_iteration", False)
        self.run_tests: bool = kwargs.get("run_tests", False)
        self.test: bool = kwargs.get("test", False)
        self.xcode_tests: bool = kwargs.get("xcode_tests", False)
        self.enable_parallel_phases: bool = kwargs.get("enable_parallel_phases", False)
        self.cleanup_docs: bool = kwargs.get("cleanup_docs", False)
        self.cleanup_git: bool = kwargs.get("cleanup_git", False)
        self.update_docs: bool = kwargs.get("update_docs", False)


def test_sequential_execution_default():
    """Test default sequential execution (backward compatibility)."""
    options = MockOptions(
        run_tests=True,
    )

    nodes = _build_dag_nodes(options)

    # Should have: config_cleanup, configuration, cleaning, fast_hooks, tests, publishing, commit
    # (comprehensive_hooks not enabled by default)
    assert len(nodes) >= 2

    # Check that tests has a dependency on the previous task
    tests_node = next((n for n in nodes if n["id"] == "tests"), None)
    assert tests_node is not None
    assert "depends_on" in tests_node
    assert len(tests_node["depends_on"]) == 1


def test_parallel_execution_enabled():
    """Test parallel execution when both tests and comprehensive hooks are enabled."""
    options = MockOptions(
        run_tests=True,
        comp=True,
        enable_parallel_phases=True,
    )

    nodes = _build_dag_nodes(options)

    # Find tests and comprehensive_hooks nodes
    tests_node = next((n for n in nodes if n["id"] == "tests"), None)
    comp_node = next((n for n in nodes if n["id"] == "comprehensive_hooks"), None)

    assert tests_node is not None, "tests node should exist"
    assert comp_node is not None, "comprehensive_hooks node should exist"

    # In parallel mode, both should depend on the same predecessor (fast_hooks or configuration)
    # but NOT on each other
    tests_deps = tests_node.get("depends_on", [])
    comp_deps = comp_node.get("depends_on", [])

    # Both tasks should have the same dependency (or both have none)
    assert tests_deps == comp_deps or (not tests_deps and not comp_deps), "Both tasks should depend on the same predecessor"
    assert "tests" not in comp_deps, "comprehensive_hooks should not depend on tests"
    assert "comprehensive_hooks" not in tests_deps, "tests should not depend on comprehensive_hooks"


def test_sequential_execution_when_parallel_disabled():
    """Test sequential execution when enable_parallel_phases is False."""
    options = MockOptions(
        run_tests=True,
        comp=True,
        enable_parallel_phases=False,
    )

    nodes = _build_dag_nodes(options)

    # Find tests and comprehensive_hooks nodes
    tests_node = next((n for n in nodes if n["id"] == "tests"), None)
    comp_node = next((n for n in nodes if n["id"] == "comprehensive_hooks"), None)

    assert tests_node is not None, "tests node should exist"
    assert comp_node is not None, "comprehensive_hooks node should exist"

    # In sequential mode, comprehensive_hooks should depend on tests
    comp_deps = comp_node.get("depends_on", [])
    assert "tests" in comp_deps, "comprehensive_hooks should depend on tests in sequential mode"


def test_parallel_execution_only_tests():
    """Test that tests run alone when comprehensive hooks are disabled."""
    options = MockOptions(
        run_tests=True,
        fast=True,  # Disable comprehensive hooks
        enable_parallel_phases=True,
    )

    nodes = _build_dag_nodes(options)

    tests_node = next((n for n in nodes if n["id"] == "tests"), None)
    comp_node = next((n for n in nodes if n["id"] == "comprehensive_hooks"), None)

    assert tests_node is not None, "tests node should exist"
    assert comp_node is None, "comprehensive_hooks should not exist when fast=True"


def test_parallel_execution_only_comprehensive_hooks():
    """Test that comprehensive hooks run alone when tests are disabled."""
    options = MockOptions(
        comp=True,
        enable_parallel_phases=True,
    )

    nodes = _build_dag_nodes(options)

    tests_node = next((n for n in nodes if n["id"] == "tests"), None)
    comp_node = next((n for n in nodes if n["id"] == "comprehensive_hooks"), None)

    assert tests_node is None, "tests should not exist"
    assert comp_node is not None, "comprehensive_hooks node should exist"


def test_parallel_execution_dependencies_chain():
    """Test that parallel tasks have correct dependencies in the chain."""
    options = MockOptions(
        run_tests=True,
        comp=True,
        enable_parallel_phases=True,
    )

    nodes = _build_dag_nodes(options)

    # Build a map of node dependencies
    deps_map = {node["id"]: node.get("depends_on", []) for node in nodes}

    # Verify the dependency chain
    # fast_hooks should come before both tests and comprehensive_hooks
    if "fast_hooks" in deps_map and "tests" in deps_map and "comprehensive_hooks" in deps_map:
        # tests and comprehensive_hooks should both depend on fast_hooks
        assert "fast_hooks" in deps_map["tests"] or deps_map["tests"] == []
        assert "fast_hooks" in deps_map["comprehensive_hooks"] or deps_map["comprehensive_hooks"] == []

        # publishing should come after both
        if "publishing" in deps_map:
            # publishing should depend on the last task
            assert len(deps_map["publishing"]) == 1


def test_parallel_execution_with_all_phases():
    """Test parallel execution with all phases enabled."""
    options = MockOptions(
        cleanup_docs=True,
        cleanup_git=True,
        update_docs=True,
        run_tests=True,
        comp=True,
        enable_parallel_phases=True,
    )

    nodes = _build_dag_nodes(options)

    # Should have all phases
    node_ids = [node["id"] for node in nodes]
    assert "tests" in node_ids
    assert "comprehensive_hooks" in node_ids
    assert "documentation_cleanup" in node_ids
    assert "git_cleanup" in node_ids
    assert "doc_updates" in node_ids
    assert "publishing" in node_ids
    assert "commit" in node_ids

    # Tests and comprehensive_hooks should not depend on each other
    tests_node = next(n for n in nodes if n["id"] == "tests")
    comp_node = next(n for n in nodes if n["id"] == "comprehensive_hooks")

    assert "comprehensive_hooks" not in tests_node.get("depends_on", [])
    assert "tests" not in comp_node.get("depends_on", [])


def test_backward_compatibility():
    """Test that default behavior is sequential for backward compatibility."""
    options = MockOptions(
        run_tests=True,
        comp=True,
        # enable_parallel_phases defaults to False
    )

    nodes = _build_dag_nodes(options)

    tests_node = next((n for n in nodes if n["id"] == "tests"), None)
    comp_node = next((n for n in nodes if n["id"] == "comprehensive_hooks"), None)

    if tests_node and comp_node:
        # In sequential mode (default), comprehensive_hooks should depend on tests
        comp_deps = comp_node.get("depends_on", [])
        assert "tests" in comp_deps, "Default should be sequential for backward compatibility"


def test_parallel_preserves_all_nodes():
    """Test that parallel execution doesn't drop any workflow nodes."""
    options = MockOptions(
        run_tests=True,
        comp=True,
        enable_parallel_phases=True,
    )

    parallel_nodes = _build_dag_nodes(options)

    options_sequential = MockOptions(
        run_tests=True,
        comp=True,
        enable_parallel_phases=False,
    )

    sequential_nodes = _build_dag_nodes(options_sequential)

    # Should have the same number of nodes
    assert len(parallel_nodes) == len(sequential_nodes), "Parallel execution should not drop nodes"

    # Should have the same node IDs
    parallel_ids = {node["id"] for node in parallel_nodes}
    sequential_ids = {node["id"] for node in sequential_nodes}
    assert parallel_ids == sequential_ids, "Parallel execution should have same nodes"
