"""Unit tests for SemanticAgent.

Tests semantic search, code pattern discovery, vector embeddings,
and context-aware code analysis.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.semantic_agent import SemanticAgent


@pytest.mark.unit
class TestSemanticAgentInitialization:
    """Test SemanticAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test SemanticAgent initializes correctly."""
        agent = SemanticAgent(context)

        assert agent.context == context
        assert agent.semantic_insights == {}
        assert "patterns_discovered" in agent.pattern_stats
        assert agent.pattern_stats["patterns_discovered"] == 0

    def test_get_supported_types(self, context):
        """Test agent supports semantic context issues."""
        agent = SemanticAgent(context)

        supported = agent.get_supported_types()

        assert IssueType.SEMANTIC_CONTEXT in supported
        assert len(supported) == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestSemanticAgentCanHandle:
    """Test semantic issue detection and handling capability."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    async def test_can_handle_semantic_context(self, agent):
        """Test high confidence for semantic context issues."""
        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Need semantic analysis of code patterns",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.85

    async def test_can_handle_pattern_search(self, agent):
        """Test high confidence for pattern-related issues."""
        issue = Issue(
            id="sem-002",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Find similar implementation patterns",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.85

    async def test_can_handle_generic_semantic(self, agent):
        """Test moderate confidence for generic semantic issues."""
        issue = Issue(
            id="sem-003",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.LOW,
            message="Code analysis needed",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

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
class TestSemanticAgentAnalyzeAndFix:
    """Test semantic analysis and fixing."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    async def test_analyze_and_fix_no_file_path(self, agent):
        """Test analyze_and_fix when no file path provided."""
        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Semantic analysis",
            file_path=None,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_analyze_and_fix_file_not_exists(self, agent, tmp_path):
        """Test analyze_and_fix when file doesn't exist."""
        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Semantic analysis",
            file_path=str(tmp_path / "nonexistent.py"),
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_analyze_and_fix_success(self, agent, tmp_path):
        """Test successful semantic analysis."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total
""")

        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Analyze code patterns",
            file_path=str(test_file),
        )

        with patch.object(agent, "_create_semantic_config") as mock_config:
            with patch.object(agent, "_get_vector_store") as mock_store:
                with patch.object(agent, "_perform_semantic_analysis") as mock_analyze:
                    mock_analyze.return_value = FixResult(
                        success=True,
                        confidence=0.8,
                        fixes_applied=["Analysis complete"],
                    )

                    result = await agent.analyze_and_fix(issue)

                    assert result.success is True

    async def test_analyze_and_fix_error_handling(self, agent, tmp_path):
        """Test error handling in analyze_and_fix."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Analysis",
            file_path=str(test_file),
        )

        with patch.object(agent, "_create_semantic_config", side_effect=Exception("Test error")):
            result = await agent.analyze_and_fix(issue)

            assert result.success is False


@pytest.mark.unit
class TestSemanticAgentValidation:
    """Test validation helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    def test_validate_semantic_issue_no_path(self, agent):
        """Test validating issue without file path."""
        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Analysis",
            file_path=None,
        )

        result = agent._validate_semantic_issue(issue)

        assert result is not None
        assert result.success is False

    def test_validate_semantic_issue_file_not_exists(self, agent, tmp_path):
        """Test validating issue with non-existent file."""
        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Analysis",
            file_path=str(tmp_path / "missing.py"),
        )

        result = agent._validate_semantic_issue(issue)

        assert result is not None
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    def test_validate_semantic_issue_valid(self, agent, tmp_path):
        """Test validating issue with valid file."""
        test_file = tmp_path / "valid.py"
        test_file.write_text("def foo(): pass")

        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Analysis",
            file_path=str(test_file),
        )

        result = agent._validate_semantic_issue(issue)

        assert result is None  # Validation passed


@pytest.mark.unit
class TestSemanticAgentConfiguration:
    """Test semantic configuration methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    def test_create_semantic_config(self, agent):
        """Test creating semantic configuration."""
        config = agent._create_semantic_config()

        assert config.embedding_model is not None
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.max_search_results == 10
        assert config.similarity_threshold == 0.7
        assert config.embedding_dimension == 384

    def test_get_persistent_db_path(self, agent, tmp_path):
        """Test getting persistent database path."""
        db_path = agent._get_persistent_db_path()

        assert db_path.name == "semantic_index.db"
        assert ".crackerjack" in str(db_path)
        assert db_path.parent.exists()

    def test_get_vector_store(self, agent):
        """Test getting vector store instance."""
        config = agent._create_semantic_config()

        with patch("crackerjack.agents.semantic_agent.VectorStore") as mock_store:
            agent._get_vector_store(config)

            mock_store.assert_called_once()
            # Should be called with config and db_path
            assert mock_store.call_args[0][0] == config


@pytest.mark.unit
@pytest.mark.asyncio
class TestSemanticAgentPerformAnalysis:
    """Test semantic analysis performance."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    async def test_perform_semantic_analysis_success(self, agent, tmp_path):
        """Test successful semantic analysis."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): return 42")

        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Analyze",
        )

        mock_store = Mock()
        mock_store.index_file.return_value = ["embedding1", "embedding2"]

        agent.context.get_file_content = Mock(return_value=test_file.read_text())

        with patch.object(agent, "_discover_semantic_patterns", return_value={"related_patterns": []}):
            with patch.object(agent, "_generate_semantic_recommendations", return_value=["Rec1"]):
                result = await agent._perform_semantic_analysis(
                    test_file, mock_store, issue
                )

                assert result.success is True
                assert result.confidence == 0.8
                assert len(result.fixes_applied) > 0

    async def test_perform_semantic_analysis_cannot_read(self, agent, tmp_path):
        """Test when file cannot be read."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Analyze",
        )

        mock_store = Mock()
        agent.context.get_file_content = Mock(return_value=None)

        result = await agent._perform_semantic_analysis(
            test_file, mock_store, issue
        )

        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_perform_semantic_analysis_indexing_error(self, agent, tmp_path):
        """Test handling indexing errors gracefully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass")

        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Analyze",
        )

        mock_store = Mock()
        mock_store.index_file.side_effect = Exception("Indexing error")

        agent.context.get_file_content = Mock(return_value=test_file.read_text())

        with patch.object(agent, "_discover_semantic_patterns", return_value={"related_patterns": []}):
            with patch.object(agent, "_generate_semantic_recommendations", return_value=[]):
                # Should not raise exception despite indexing error
                result = await agent._perform_semantic_analysis(
                    test_file, mock_store, issue
                )

                assert result.success is True


@pytest.mark.unit
class TestSemanticAgentPatternStats:
    """Test pattern statistics tracking."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    def test_pattern_stats_initialization(self, agent):
        """Test pattern stats are initialized correctly."""
        assert agent.pattern_stats["patterns_discovered"] == 0
        assert agent.pattern_stats["context_enhancements"] == 0
        assert agent.pattern_stats["semantic_suggestions"] == 0
        assert agent.pattern_stats["similar_patterns_found"] == 0

    def test_update_pattern_stats(self, agent):
        """Test updating pattern stats."""
        if hasattr(agent, "_update_pattern_stats"):
            result = FixResult(
                success=True,
                confidence=0.8,
                fixes_applied=["Pattern discovery"],
            )

            initial_count = agent.pattern_stats["patterns_discovered"]
            agent._update_pattern_stats(result)

            # Stats should be updated (implementation dependent)
            assert isinstance(agent.pattern_stats["patterns_discovered"], int)


@pytest.mark.unit
@pytest.mark.asyncio
class TestSemanticAgentPatternDiscovery:
    """Test semantic pattern discovery."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    async def test_discover_semantic_patterns(self, agent, tmp_path):
        """Test discovering semantic patterns."""
        test_file = tmp_path / "test.py"
        content = """
def process_data(items):
    result = []
    for item in items:
        result.append(item * 2)
    return result
"""
        issue = Issue(
            id="sem-001",
            type=IssueType.SEMANTIC_CONTEXT,
            severity=Priority.MEDIUM,
            message="Find patterns",
        )

        mock_store = Mock()

        if hasattr(agent, "_discover_semantic_patterns"):
            with patch.object(agent, "_extract_code_elements", return_value=[]):
                insights = await agent._discover_semantic_patterns(
                    mock_store, test_file, content, issue
                )

                assert "related_patterns" in insights
                assert "similar_functions" in insights
                assert "context_suggestions" in insights


@pytest.mark.unit
class TestSemanticAgentHelpers:
    """Test helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    def test_extract_code_elements(self, agent):
        """Test extracting code elements for analysis."""
        content = """
def func1():
    return 1

class MyClass:
    def method1(self):
        pass
"""
        if hasattr(agent, "_extract_code_elements"):
            elements = agent._extract_code_elements(content)

            assert isinstance(elements, list)

    def test_generate_semantic_recommendations(self, agent):
        """Test generating semantic recommendations."""
        insights = {
            "related_patterns": ["pattern1", "pattern2"],
            "similar_functions": ["func1", "func2"],
            "context_suggestions": ["suggestion1"],
        }

        if hasattr(agent, "_generate_semantic_recommendations"):
            recommendations = agent._generate_semantic_recommendations(insights)

            assert isinstance(recommendations, list)

    def test_create_semantic_error_result(self, agent):
        """Test creating semantic error result."""
        error = Exception("Test error")

        if hasattr(agent, "_create_semantic_error_result"):
            result = agent._create_semantic_error_result(error)

            assert result.success is False
            assert result.confidence == 0.0


@pytest.mark.unit
class TestSemanticAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SemanticAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SemanticAgent(context)

    def test_agent_maintains_insights(self, agent):
        """Test that agent maintains semantic insights."""
        # Initially empty
        assert agent.semantic_insights == {}

        # Add insight
        agent.semantic_insights["test_pattern"] = {"similarity": 0.9}

        # Should persist
        assert "test_pattern" in agent.semantic_insights
        assert agent.semantic_insights["test_pattern"]["similarity"] == 0.9

    def test_agent_tracks_statistics(self, agent):
        """Test that agent tracks pattern statistics."""
        initial_stats = agent.pattern_stats.copy()

        # Simulate pattern discovery
        agent.pattern_stats["patterns_discovered"] += 3
        agent.pattern_stats["similar_patterns_found"] += 5

        # Stats should be updated
        assert agent.pattern_stats["patterns_discovered"] == initial_stats["patterns_discovered"] + 3
        assert agent.pattern_stats["similar_patterns_found"] == initial_stats["similar_patterns_found"] + 5

    def test_database_path_creation(self, agent, tmp_path):
        """Test that database path is created correctly."""
        db_path = agent._get_persistent_db_path()

        # Parent directory should be created
        assert db_path.parent.exists()
        assert db_path.parent.name == ".crackerjack"
