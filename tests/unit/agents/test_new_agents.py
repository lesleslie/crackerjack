"""Tests for newly implemented agents and services.

This module tests:
- RefurbCodeTransformerAgent
- TypeErrorSpecialistAgent enhancements
- DeadCodeRemovalAgent enhancements
- AgentDelegator service
- PlanningAgent delegation
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
)
from crackerjack.agents.dead_code_removal_agent import (
    DeadCodeInfo,
    DeadCodeRemovalAgent,
)
from crackerjack.agents.refurb_agent import RefurbCodeTransformerAgent
from crackerjack.agents.type_error_specialist import TypeErrorSpecialistAgent


# Test Fixtures
@pytest.fixture
def mock_context():
    """Create a mock AgentContext for testing."""
    context = MagicMock(spec=AgentContext)
    context.project_path = Path("/tmp/test_project")
    context.get_file_content = MagicMock(return_value="")
    context.write_file_content = MagicMock(return_value=True)
    return context


@pytest.fixture
def type_error_issue():
    """Create a mock type error issue for testing."""
    return Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.HIGH,
        message="Function is missing return type annotation",
        file_path="/tmp/test_project/test_file.py",
        line_number=10,
    )


@pytest.fixture
def dead_code_issue():
    """Create a mock dead code issue for testing."""
    return Issue(
        type=IssueType.DEAD_CODE,
        severity=Priority.MEDIUM,
        message="Unused function 'old_helper' (line 15, 86% confidence)",
        file_path="/tmp/test_project/test_file.py",
        line_number=15,
    )


@pytest.fixture
def refurb_issue():
    """Create a mock refurb issue for testing."""
    return Issue(
        type=IssueType.REFURB,
        severity=Priority.LOW,
        message="FURB136: Replace if x: return True with return bool(x)",
        file_path="/tmp/test_project/test_file.py",
        line_number=20,
    )


# RefurbCodeTransformerAgent Tests
class TestRefurbCodeTransformerAgent:
    """Tests for RefurbCodeTransformerAgent."""

    def test_agent_initialization(self, mock_context):
        """Test agent initializes correctly."""
        agent = RefurbCodeTransformerAgent(mock_context)
        assert agent.name == "RefurbCodeTransformerAgent"
        assert IssueType.REFURB in agent.get_supported_types()

    @pytest.mark.asyncio
    async def test_can_handle_refurb_issue(self, mock_context, refurb_issue):
        """Test agent can handle refurb issues."""
        agent = RefurbCodeTransformerAgent(mock_context)
        confidence = await agent.can_handle(refurb_issue)
        assert confidence >= 0.7

    @pytest.mark.asyncio
    async def test_cannot_handle_other_issues(self, mock_context, type_error_issue):
        """Test agent rejects non-refurb issues."""
        agent = RefurbCodeTransformerAgent(mock_context)
        confidence = await agent.can_handle(type_error_issue)
        assert confidence == 0.0

    def test_furb_transformations_dict_exists(self, mock_context):
        """Test FURB_TRANSFORMATIONS dictionary is populated."""
        from crackerjack.agents.refurb_agent import FURB_TRANSFORMATIONS

        # FURB_TRANSFORMATIONS is a module-level variable
        assert len(FURB_TRANSFORMATIONS) >= 10
        assert "FURB118" in FURB_TRANSFORMATIONS
        assert "FURB136" in FURB_TRANSFORMATIONS


# TypeErrorSpecialistAgent Tests
class TestTypeErrorSpecialistAgent:
    """Tests for TypeErrorSpecialistAgent enhancements."""

    def test_agent_initialization(self, mock_context):
        """Test agent initializes correctly."""
        agent = TypeErrorSpecialistAgent(mock_context)
        assert agent.name == "TypeErrorSpecialist"
        assert IssueType.TYPE_ERROR in agent.get_supported_types()

    @pytest.mark.asyncio
    async def test_can_handle_type_error(self, mock_context, type_error_issue):
        """Test agent can handle type errors."""
        agent = TypeErrorSpecialistAgent(mock_context)
        confidence = await agent.can_handle(type_error_issue)
        assert confidence >= 0.6

    def test_infer_type_from_constant(self, mock_context):
        """Test type inference from constant expressions."""
        import ast

        agent = TypeErrorSpecialistAgent(mock_context)

        # Test various constant types
        assert agent._infer_type_from_expr(ast.Constant(value=None)) == "None"
        assert agent._infer_type_from_expr(ast.Constant(value=True)) == "bool"
        assert agent._infer_type_from_expr(ast.Constant(value=42)) == "int"
        assert agent._infer_type_from_expr(ast.Constant(value=3.14)) == "float"
        assert agent._infer_type_from_expr(ast.Constant(value="hello")) == "str"

    def test_infer_type_from_list(self, mock_context):
        """Test type inference from list expressions."""
        import ast

        agent = TypeErrorSpecialistAgent(mock_context)

        # Empty list
        empty_list = ast.List(elts=[], ctx=ast.Load())
        assert agent._infer_type_from_expr(empty_list) == "list[Any]"

        # List of ints
        int_list = ast.List(
            elts=[ast.Constant(value=1), ast.Constant(value=2)],
            ctx=ast.Load(),
        )
        result = agent._infer_type_from_expr(int_list)
        assert "list[" in result

    def test_infer_type_from_dict(self, mock_context):
        """Test type inference from dict expressions."""
        import ast

        agent = TypeErrorSpecialistAgent(mock_context)

        # Dict with string keys and int values
        dict_expr = ast.Dict(
            keys=[ast.Constant(value="a"), ast.Constant(value="b")],
            values=[ast.Constant(value=1), ast.Constant(value=2)],
        )
        result = agent._infer_type_from_expr(dict_expr)
        assert "dict[" in result

    def test_infer_type_from_compare(self, mock_context):
        """Test that comparisons return bool."""
        import ast

        agent = TypeErrorSpecialistAgent(mock_context)

        compare = ast.Compare(
            left=ast.Constant(value=1),
            ops=[ast.Eq()],
            comparators=[ast.Constant(value=2)],
        )
        assert agent._infer_type_from_expr(compare) == "bool"

    def test_split_union_types(self, mock_context):
        """Test splitting union type arguments."""
        agent = TypeErrorSpecialistAgent(mock_context)

        # Simple types
        result = agent._split_union_types("int, str, bool")
        assert result == ["int", "str", "bool"]

        # Nested generics
        result = agent._split_union_types("list[int], dict[str, Any]")
        assert len(result) == 2

    def test_modernize_optional_syntax(self, mock_context):
        """Test converting Optional[X] to X | None."""
        agent = TypeErrorSpecialistAgent(mock_context)

        content = """from __future__ import annotations

def foo(x: Optional[str]) -> None:
    pass
"""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Optional type can be simplified",
            file_path="test.py",
            line_number=3,
        )

        new_content, fixes = agent._fix_optional_union_types(content, issue)
        assert "Optional" not in new_content or len(fixes) > 0


# DeadCodeRemovalAgent Tests
class TestDeadCodeRemovalAgent:
    """Tests for DeadCodeRemovalAgent enhancements."""

    def test_agent_initialization(self, mock_context):
        """Test agent initializes correctly."""
        agent = DeadCodeRemovalAgent(mock_context)
        assert agent.name == "DeadCodeRemovalAgent"
        assert IssueType.DEAD_CODE in agent.get_supported_types()
        assert agent.min_confidence_threshold == 0.70

    @pytest.mark.asyncio
    async def test_can_handle_dead_code(self, mock_context, dead_code_issue):
        """Test agent can handle dead code issues."""
        agent = DeadCodeRemovalAgent(mock_context)
        confidence = await agent.can_handle(dead_code_issue)
        assert confidence >= 0.7

    def test_extract_confidence_from_message(self, mock_context):
        """Test extracting confidence percentage from messages."""
        agent = DeadCodeRemovalAgent(mock_context)

        assert agent._extract_confidence("86% confidence") == 0.86
        assert agent._extract_confidence("definitely unused") == 0.95
        assert agent._extract_confidence("likely unused") == 0.75
        assert agent._extract_confidence("possibly unused") == 0.50
        assert agent._extract_confidence("some unused code") == 0.70

    def test_dead_code_info_dataclass(self):
        """Test DeadCodeInfo dataclass."""
        info = DeadCodeInfo(
            code_type="function",
            name="old_func",
            line_number=10,
            confidence=0.86,
            end_line=20,
            decorators=["@deprecated"],
        )
        assert info.code_type == "function"
        assert info.name == "old_func"
        assert info.line_number == 10
        assert info.confidence == 0.86
        assert info.end_line == 20
        assert info.decorators == ["@deprecated"]

    def test_parse_skylos_format(self, mock_context):
        """Test parsing skylos output format."""
        agent = DeadCodeRemovalAgent(mock_context)

        content = "def unused_func():\n    pass\n"
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused function 'unused_func' (line 1, 92% confidence)",
            file_path="test.py",
            line_number=1,
        )

        result = agent._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "function"
        assert result.name == "unused_func"
        assert result.line_number == 1
        assert result.confidence == 0.92

    def test_parse_vulture_format(self, mock_context):
        """Test parsing vulture output format."""
        agent = DeadCodeRemovalAgent(mock_context)

        content = "class OldClass:\n    pass\n"
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused class 'OldClass' at line 1 (60% confidence)",
            file_path="test.py",
            line_number=1,
        )

        result = agent._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "class"

    def test_find_block_end_by_indent(self, mock_context):
        """Test finding block end using indentation."""
        agent = DeadCodeRemovalAgent(mock_context)

        lines = [
            "def func():",
            "    x = 1",
            "    y = 2",
            "    return x + y",
            "",
            "def other():",
            "    pass",
        ]

        end = agent._find_block_end_by_indent(lines, 1)
        # Returns index of first line at base indent (empty lines skipped)
        assert end == 5  # "def other():" is at base indent

    def test_analyze_usage_dynamic_patterns(self, mock_context):
        """Test detecting dynamic usage patterns."""
        agent = DeadCodeRemovalAgent(mock_context)

        content = """
def old_func():
    pass

# Dynamic usage
result = getattr(obj, 'old_func')
"""
        dead_code = DeadCodeInfo(
            code_type="function",
            name="old_func",
            line_number=2,
            confidence=0.80,
        )

        usage = agent._analyze_usage(content, dead_code)
        assert usage["has_dynamic_usage"] is True

    def test_analyze_usage_string_references(self, mock_context):
        """Test detecting string references."""
        agent = DeadCodeRemovalAgent(mock_context)

        # Content with multiple string references to the function
        content = '''
def old_func():
    pass

# String references
name = "old_func"
alias = "old_func"
'''
        dead_code = DeadCodeInfo(
            code_type="function",
            name="old_func",
            line_number=2,
            confidence=0.80,
        )

        usage = agent._analyze_usage(content, dead_code)
        # Should detect at least 1 string reference (subtracts 1 for definition)
        # With 2 explicit string references, we get 2 - 1 = 1
        assert usage["string_references"] >= 1

    def test_protected_decorator_detection(self, mock_context):
        """Test that protected decorators are detected."""
        agent = DeadCodeRemovalAgent(mock_context)

        content = """
@pytest.fixture
def my_fixture():
    return {}
"""
        dead_code = DeadCodeInfo(
            code_type="function",
            name="my_fixture",
            line_number=3,
            confidence=0.90,
            decorators=["@pytest.fixture"],
        )

        result = agent._perform_safety_checks_enhanced(content, dead_code)
        assert result["safe_to_remove"] is False
        assert any("protected decorator" in r for r in result["reasons"])

    def test_is_test_file_detection(self, mock_context):
        """Test test file detection."""
        agent = DeadCodeRemovalAgent(mock_context)

        assert agent._is_test_file(Path("/project/tests/test_foo.py")) is True
        assert agent._is_test_file(Path("/project/test_foo.py")) is True
        assert agent._is_test_file(Path("/project/conftest.py")) is True
        assert agent._is_test_file(Path("/project/foo_test.py")) is True
        assert agent._is_test_file(Path("/project/src/module.py")) is False


# AgentDelegator Tests
class TestAgentDelegator:
    """Tests for AgentDelegator service."""

    def test_delegator_initialization(self, mock_context):
        """Test delegator initializes correctly."""
        from crackerjack.services.agent_delegator import AgentDelegator

        mock_coordinator = MagicMock()
        mock_coordinator.agents = []

        delegator = AgentDelegator(mock_coordinator)
        assert delegator.coordinator == mock_coordinator

    def test_delegation_stats(self, mock_context):
        """Test DelegationStats dataclass."""
        from crackerjack.services.agent_delegator import DelegationStats

        stats = DelegationStats()
        assert stats.total_delegations == 0
        assert stats.successful_delegations == 0

        stats.total_delegations = 10
        stats.successful_delegations = 8
        stats.total_latency_ms = 500.0

        assert stats.average_latency_ms == 50.0

    def test_create_cache_key(self, mock_context):
        """Test cache key creation."""
        from crackerjack.services.agent_delegator import AgentDelegator

        mock_coordinator = MagicMock()
        delegator = AgentDelegator(mock_coordinator)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test error",
            file_path="test.py",
            line_number=10,
        )

        key1 = delegator._create_cache_key("TestAgent", issue, None)
        key2 = delegator._create_cache_key("TestAgent", issue, None)
        key3 = delegator._create_cache_key("OtherAgent", issue, None)

        assert key1 == key2  # Same inputs = same key
        assert key1 != key3  # Different agent = different key

    def test_get_delegation_metrics(self, mock_context):
        """Test getting delegation metrics."""
        from crackerjack.services.agent_delegator import AgentDelegator

        mock_coordinator = MagicMock()
        delegator = AgentDelegator(mock_coordinator)

        # Record some delegations
        delegator._record_delegation("TestAgent", success=True, latency_ms=100.0)
        delegator._record_delegation("TestAgent", success=False, latency_ms=50.0)

        metrics = delegator.get_delegation_metrics()
        assert metrics["total_delegations"] == 2
        assert metrics["successful_delegations"] == 1
        assert metrics["failed_delegations"] == 1
        assert "TestAgent" in metrics["agents_used"]


# PlanningAgent Delegation Tests
class TestPlanningAgentDelegation:
    """Tests for PlanningAgent delegation support."""

    def test_planning_agent_accepts_delegator(self):
        """Test PlanningAgent accepts optional delegator."""
        from crackerjack.agents.planning_agent import PlanningAgent

        # Without delegator
        agent1 = PlanningAgent("/tmp/test")
        assert agent1.delegator is None

        # With delegator
        mock_delegator = MagicMock()
        agent2 = PlanningAgent("/tmp/test", delegator=mock_delegator)
        assert agent2.delegator == mock_delegator

    def test_try_delegator_fix_without_delegator(self):
        """Test _try_delegator_fix returns None without delegator."""
        from crackerjack.agents.planning_agent import PlanningAgent

        agent = PlanningAgent("/tmp/test")
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test",
            file_path="test.py",
            line_number=1,
        )

        result = agent._try_delegator_fix(issue, {})
        assert result is None


# Integration Tests
class TestAgentIntegration:
    """Integration tests for agent interactions."""

    @pytest.mark.asyncio
    async def test_refurb_agent_analyze_and_fix(self, mock_context, refurb_issue):
        """Test RefurbCodeTransformerAgent analyze_and_fix method."""
        mock_context.get_file_content.return_value = """
def foo(x):
    if x:
        return True
    return False
"""
        agent = RefurbCodeTransformerAgent(mock_context)
        result = await agent.analyze_and_fix(refurb_issue)

        assert isinstance(result, FixResult)
        assert result.confidence >= 0.0

    @pytest.mark.asyncio
    async def test_type_error_agent_analyze_and_fix(
        self, mock_context, type_error_issue
    ):
        """Test TypeErrorSpecialistAgent analyze_and_fix method."""
        mock_context.get_file_content.return_value = """
def foo(x):
    return x + 1
"""
        agent = TypeErrorSpecialistAgent(mock_context)
        result = await agent.analyze_and_fix(type_error_issue)

        assert isinstance(result, FixResult)

    @pytest.mark.asyncio
    async def test_dead_code_agent_rejects_test_files(
        self, mock_context, dead_code_issue
    ):
        """Test DeadCodeRemovalAgent rejects test files."""
        dead_code_issue.file_path = "/tmp/test_project/tests/test_foo.py"
        agent = DeadCodeRemovalAgent(mock_context)
        result = await agent.analyze_and_fix(dead_code_issue)

        assert result.success is False
        assert any("test file" in r.lower() for r in result.remaining_issues)


# Edge Case Tests
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_file_handling(self, mock_context):
        """Test agents handle empty files gracefully."""
        mock_context.get_file_content.return_value = ""

        agent = TypeErrorSpecialistAgent(mock_context)
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Error",
            file_path="empty.py",
            line_number=1,
        )

        # Should not crash
        new_content, fixes = agent._fix_missing_return_types("", issue)
        assert isinstance(new_content, str)

    def test_malformed_issue_handling(self, mock_context):
        """Test agents handle malformed issues gracefully."""
        agent = DeadCodeRemovalAgent(mock_context)

        # Issue with no file path
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused code",
            file_path=None,
            line_number=None,
        )

        result = asyncio.run(agent.analyze_and_fix(issue))
        assert result.success is False

    def test_syntax_error_in_file(self, mock_context):
        """Test agents handle files with syntax errors."""
        agent = TypeErrorSpecialistAgent(mock_context)

        # Invalid Python code
        bad_code = "def foo(:\n    pass"

        # Should not crash when trying to parse
        try:
            tree = compile(bad_code, "test.py", "exec")
        except SyntaxError:
            pass  # Expected

        # Agent should handle gracefully
        new_content, fixes = agent._infer_and_add_return_types(
            bad_code,
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="Error",
                file_path="test.py",
                line_number=1,
            ),
        )
        assert isinstance(new_content, str)


# PyCharmMCPAdapter Tests
class TestPyCharmMCPAdapter:
    """Tests for PyCharmMCPAdapter service."""

    def test_adapter_initialization(self):
        """Test adapter initializes correctly."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()
        assert adapter._timeout == 30.0
        assert adapter._max_results == 100

    def test_adapter_with_custom_settings(self):
        """Test adapter with custom settings."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(timeout=60.0, max_results=50)
        assert adapter._timeout == 60.0
        assert adapter._max_results == 50

    def test_circuit_breaker_state(self):
        """Test CircuitBreakerState dataclass."""
        from crackerjack.services.pycharm_mcp_integration import (
            CircuitBreakerState,
        )

        cb = CircuitBreakerState()
        assert cb.failure_count == 0
        assert cb.is_open is False
        assert cb.can_execute() is True

        # Record failures to open circuit
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_execute() is False  # Circuit is open

        # Record success to close circuit
        cb.record_success()
        assert cb.is_open is False
        assert cb.failure_count == 0

    def test_sanitize_regex_valid(self):
        """Test sanitizing valid regex patterns."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Valid patterns
        assert adapter._sanitize_regex(r"# type: ignore") == r"# type: ignore"
        assert adapter._sanitize_regex(r"def\s+\w+") == r"def\s+\w+"
        assert adapter._sanitize_regex(r"TODO|FIXME") == r"TODO|FIXME"

    def test_sanitize_regex_invalid(self):
        """Test sanitizing invalid regex patterns."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Invalid patterns
        assert adapter._sanitize_regex("[invalid") == ""  # Unclosed bracket
        assert adapter._sanitize_regex("") == ""  # Empty is valid but returns empty
        assert adapter._sanitize_regex("x" * 600) == ""  # Too long

    def test_sanitize_regex_dangerous(self):
        """Test sanitizing dangerous ReDoS patterns."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Dangerous ReDoS patterns
        assert adapter._sanitize_regex(r"(.*)+") == ""
        assert adapter._sanitize_regex(r"(.+)+") == ""
        assert adapter._sanitize_regex(r"(.*)*") == ""

    def test_is_safe_path(self):
        """Test path safety validation."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Safe paths
        assert adapter._is_safe_path("src/module.py") is True
        assert adapter._is_safe_path("test_file.py") is True
        assert adapter._is_safe_path("/tmp/test.py") is True

        # Unsafe paths
        assert adapter._is_safe_path("../../../etc/passwd") is False  # Path traversal
        assert adapter._is_safe_path("") is False  # Empty
        assert adapter._is_safe_path("/etc/passwd") is False  # Outside project
        assert adapter._is_safe_path("file\x00.py") is False  # Null byte

    def test_search_result_dataclass(self):
        """Test SearchResult dataclass."""
        from crackerjack.services.pycharm_mcp_integration import SearchResult

        result = SearchResult(
            file_path="test.py",
            line_number=10,
            column=5,
            match_text="# type: ignore",
            context_before="def foo():",
            context_after="    pass",
        )
        assert result.file_path == "test.py"
        assert result.line_number == 10
        assert result.match_text == "# type: ignore"

    @pytest.mark.asyncio
    async def test_search_regex_no_mcp(self):
        """Test search when MCP is not available (uses fallback)."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(mcp_client=None)

        # Should use fallback grep search
        results = await adapter.search_regex(r"def\s+\w+", file_pattern="*.py")
        # Results depend on current directory content
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_replace_text_unsafe_path(self):
        """Test replace rejects unsafe paths."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(mcp_client=None)

        # Should reject path traversal
        result = await adapter.replace_text_in_file(
            "../../../etc/passwd",
            "old",
            "new",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_get_file_problems_unsafe_path(self):
        """Test get_file_problems rejects unsafe paths."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(mcp_client=None)

        # Should reject path traversal
        problems = await adapter.get_file_problems("../../../etc/passwd")
        assert problems == []

    def test_cache_operations(self):
        """Test caching functionality."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Set and get cached
        adapter._set_cached("test_key", {"data": "value"}, ttl=60.0)
        result = adapter._get_cached("test_key")
        assert result == {"data": "value"}

        # Clear cache
        adapter.clear_cache()
        assert adapter._get_cached("test_key") is None

    def test_cache_expiry(self):
        """Test cache expiry."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter
        import time

        adapter = PyCharmMCPAdapter()

        # Set with very short TTL
        adapter._set_cached("test_key", "value", ttl=0.01)
        time.sleep(0.02)

        # Should be expired
        result = adapter._get_cached("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check functionality."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(mcp_client=None)
        health = await adapter.health_check()

        assert "mcp_available" in health
        assert "circuit_breaker_open" in health
        assert "failure_count" in health
        assert "cache_size" in health
        assert health["mcp_available"] is False


# Export Tests Summary
TEST_SUMMARY = """
Test Coverage Summary:
- RefurbCodeTransformerAgent: 4 tests
- TypeErrorSpecialistAgent: 8 tests
- DeadCodeRemovalAgent: 11 tests
- AgentDelegator: 4 tests
- PlanningAgent Delegation: 2 tests
- Integration Tests: 3 tests
- Edge Cases: 3 tests
- PyCharmMCPAdapter: 12 tests

Total: 47 tests covering all new features
"""
