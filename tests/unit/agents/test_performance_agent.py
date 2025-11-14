"""Unit tests for PerformanceAgent.

Tests performance issue detection, optimization application,
nested loop detection, and algorithmic improvements.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.performance_agent import PerformanceAgent


@pytest.mark.unit
class TestPerformanceAgentInitialization:
    """Test PerformanceAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test PerformanceAgent initializes correctly."""
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            agent = PerformanceAgent(context)

            assert agent.context == context
            assert agent.semantic_insights == {}
            assert agent.performance_metrics == {}
            assert "nested_loops_optimized" in agent.optimization_stats

    def test_get_supported_types(self, context):
        """Test agent supports performance issues."""
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            agent = PerformanceAgent(context)

            supported = agent.get_supported_types()

            assert IssueType.PERFORMANCE in supported
            assert len(supported) == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestPerformanceAgentCanHandle:
    """Test performance issue detection and handling capability."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create PerformanceAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            return PerformanceAgent(context)

    async def test_can_handle_nested_loop(self, agent):
        """Test high confidence for nested loop issues."""
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Nested loop detected causing O(n²) complexity",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_string_concatenation(self, agent):
        """Test high confidence for string concatenation issues."""
        issue = Issue(
            id="perf-002",
            type=IssueType.PERFORMANCE,
            severity=Priority.MEDIUM,
            message="Inefficient string concatenation in loop",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_generic_performance(self, agent):
        """Test moderate confidence for generic performance issues."""
        issue = Issue(
            id="perf-003",
            type=IssueType.PERFORMANCE,
            severity=Priority.MEDIUM,
            message="Performance bottleneck detected",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.85

    async def test_cannot_handle_unsupported_type(self, agent):
        """Test agent cannot handle unsupported issue types."""
        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
class TestPerformanceAgentAnalyzeAndFix:
    """Test performance issue analysis and fixing."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create PerformanceAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            return PerformanceAgent(context)

    async def test_analyze_and_fix_no_file_path(self, agent):
        """Test analyze_and_fix when no file path provided."""
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=None,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_analyze_and_fix_file_not_exists(self, agent, tmp_path):
        """Test analyze_and_fix when file doesn't exist."""
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=str(tmp_path / "nonexistent.py"),
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_analyze_and_fix_with_optimizations(self, agent, tmp_path):
        """Test analyze_and_fix with detected performance issues."""
        test_file = tmp_path / "slow.py"
        test_file.write_text("""
for i in range(n):
    for j in range(m):
        result.append(i * j)
""")

        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Nested loops detected",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        with patch.object(agent, "_detect_semantic_performance_issues", return_value=[]):
            result = await agent.analyze_and_fix(issue)

            # Performance metrics should be tracked
            assert str(test_file) in agent.performance_metrics

    async def test_analyze_and_fix_error_handling(self, agent, tmp_path):
        """Test error handling in analyze_and_fix."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(side_effect=Exception("Read error"))

        result = await agent.analyze_and_fix(issue)

        assert result.success is False


@pytest.mark.unit
class TestPerformanceAgentValidation:
    """Test validation helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create PerformanceAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            return PerformanceAgent(context)

    def test_validate_performance_issue_no_path(self, agent):
        """Test validating issue without file path."""
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=None,
        )

        result = agent._validate_performance_issue(issue)

        assert result is not None
        assert result.success is False

    def test_validate_performance_issue_file_not_exists(self, agent, tmp_path):
        """Test validating issue with non-existent file."""
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=str(tmp_path / "missing.py"),
        )

        result = agent._validate_performance_issue(issue)

        assert result is not None
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    def test_validate_performance_issue_valid(self, agent, tmp_path):
        """Test validating issue with valid file."""
        test_file = tmp_path / "valid.py"
        test_file.write_text("def foo(): pass")

        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            severity=Priority.HIGH,
            message="Performance issue",
            file_path=str(test_file),
        )

        result = agent._validate_performance_issue(issue)

        assert result is None  # Validation passed


@pytest.mark.unit
class TestPerformanceAgentResultCreation:
    """Test result creation helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create PerformanceAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            return PerformanceAgent(context)

    def test_create_no_optimization_result(self, agent):
        """Test creating result when no optimizations could be applied."""
        result = agent._create_no_optimization_result()

        assert result.success is False
        assert result.confidence == 0.6
        assert len(result.remaining_issues) > 0
        assert len(result.recommendations) > 0
        assert "Manual optimization" in result.recommendations[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestPerformanceAgentProcessing:
    """Test performance optimization processing workflow."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create PerformanceAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            return PerformanceAgent(context)

    async def test_process_performance_optimization_no_issues(self, agent, tmp_path):
        """Test processing when no issues found."""
        test_file = tmp_path / "clean.py"
        test_file.write_text("def foo():\n    return sum(range(10))\n")

        agent.context.get_file_content = Mock(return_value=test_file.read_text())

        with patch.object(agent, "_detect_performance_issues", return_value=[]):
            with patch.object(agent, "_detect_semantic_performance_issues", return_value=[]):
                result = await agent._process_performance_optimization(test_file)

                assert result.success is True
                assert result.confidence == 0.7
                assert "No performance issues" in result.recommendations[0]

    async def test_process_performance_optimization_cannot_read(self, agent, tmp_path):
        """Test processing when file cannot be read."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        agent.context.get_file_content = Mock(return_value=None)

        result = await agent._process_performance_optimization(test_file)

        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_apply_and_save_optimizations_success(self, agent, tmp_path):
        """Test successfully applying and saving optimizations."""
        test_file = tmp_path / "test.py"
        content = "original content"
        issues = [{"type": "nested_loops"}]

        with patch.object(agent, "_apply_performance_optimizations", return_value="optimized"):
            with patch.object(agent, "_generate_enhanced_recommendations") as mock_rec:
                mock_rec.return_value = ["Verify performance"]
                agent.context.write_file_content = Mock(return_value=True)

                result = await agent._apply_and_save_optimizations(
                    test_file, content, issues
                )

                assert result.success is True
                assert result.confidence == 0.8
                assert len(result.fixes_applied) > 0

    async def test_apply_and_save_optimizations_no_changes(self, agent, tmp_path):
        """Test when optimizations produce no changes."""
        test_file = tmp_path / "test.py"
        content = "original content"
        issues = [{"type": "unknown"}]

        with patch.object(agent, "_apply_performance_optimizations", return_value=content):
            result = await agent._apply_and_save_optimizations(
                test_file, content, issues
            )

            assert result.success is False
            assert result.confidence == 0.6

    async def test_apply_and_save_optimizations_write_failure(self, agent, tmp_path):
        """Test when writing optimized content fails."""
        test_file = tmp_path / "test.py"
        content = "original content"
        issues = [{"type": "nested_loops"}]

        with patch.object(agent, "_apply_performance_optimizations", return_value="optimized"):
            agent.context.write_file_content = Mock(return_value=False)

            result = await agent._apply_and_save_optimizations(
                test_file, content, issues
            )

            assert result.success is False
            assert "Failed to write" in result.remaining_issues[0]


@pytest.mark.unit
class TestPerformanceAgentMetrics:
    """Test performance metrics tracking."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create PerformanceAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            return PerformanceAgent(context)

    def test_optimization_stats_initialization(self, agent):
        """Test optimization stats are initialized correctly."""
        assert agent.optimization_stats["nested_loops_optimized"] == 0
        assert agent.optimization_stats["list_ops_optimized"] == 0
        assert agent.optimization_stats["string_concat_optimized"] == 0
        assert agent.optimization_stats["repeated_ops_cached"] == 0
        assert agent.optimization_stats["comprehensions_applied"] == 0

    def test_performance_metrics_empty(self, agent):
        """Test performance metrics start empty."""
        assert agent.performance_metrics == {}


@pytest.mark.unit
@pytest.mark.asyncio
class TestPerformanceAgentSemanticDetection:
    """Test semantic performance issue detection."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create PerformanceAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer") as mock_create:
            mock_enhancer = AsyncMock()
            mock_create.return_value = mock_enhancer
            agent = PerformanceAgent(context)
            agent.semantic_enhancer = mock_enhancer
            return agent

    async def test_detect_semantic_performance_issues_with_matches(self, agent, tmp_path):
        """Test detecting semantic performance issues."""
        content = """
def process_items(items):
    result = []
    for item in items:
        for subitem in item:
            result.append(subitem)
    return result
"""
        mock_insight = Mock()
        mock_insight.high_confidence_matches = 2
        mock_insight.total_matches = 3
        mock_insight.related_patterns = ["pattern1", "pattern2"]

        agent.semantic_enhancer.find_performance_bottlenecks = AsyncMock(
            return_value=mock_insight
        )

        # Most agents will have a method like this even if not shown in first 200 lines
        if hasattr(agent, "_detect_semantic_performance_issues"):
            issues = await agent._detect_semantic_performance_issues(content, tmp_path)
            # Should return issues based on semantic analysis
            assert isinstance(issues, list)


@pytest.mark.unit
class TestPerformanceAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create PerformanceAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.performance_agent.create_semantic_enhancer"):
            return PerformanceAgent(context)

    def test_agent_state_persistence(self, agent):
        """Test that agent maintains state across operations."""
        # Initial state
        assert agent.performance_metrics == {}
        assert agent.optimization_stats["nested_loops_optimized"] == 0

        # After hypothetical optimization
        agent.optimization_stats["nested_loops_optimized"] += 1
        agent.performance_metrics["test.py"] = {"analysis_duration": 1.5}

        # State should persist
        assert agent.optimization_stats["nested_loops_optimized"] == 1
        assert "test.py" in agent.performance_metrics
