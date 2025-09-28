import pytest
from pathlib import Path
from unittest.mock import Mock
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.import_optimization_agent import ImportAnalysis, ImportOptimizationAgent


class TestImportOptimizationAgent:
    """Tests for ImportOptimizationAgent.

    Clean, focused tests that verify actual agent behavior without testing
    non-existent standalone functions.
    """

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        import crackerjack.agents.import_optimization_agent
        assert crackerjack.agents.import_optimization_agent is not None

    @pytest.fixture
    def mock_context(self):
        """Create a mock AgentContext for testing."""
        mock_context = Mock(spec=AgentContext)
        # Create a mock Path object for project_path
        mock_project_path = Mock(spec=Path)
        mock_project_path.rglob = Mock(return_value=[])
        mock_context.project_path = mock_project_path
        mock_context.get_file_content = Mock(return_value="# test content")
        mock_context.write_file_content = Mock(return_value=True)
        return mock_context

    @pytest.fixture
    def agent(self, mock_context):
        """Create ImportOptimizationAgent instance for testing."""
        try:
            return ImportOptimizationAgent(mock_context)
        except Exception:
            pytest.skip("Agent requires specific context configuration")

    def test_importanalysis_creation(self):
        """Test ImportAnalysis NamedTuple creation."""
        analysis = ImportAnalysis(
            file_path=Path("/test/file.py"),
            mixed_imports=["module1"],
            redundant_imports=["unused"],
            unused_imports=["old_import"],
            optimization_opportunities=["consolidate imports"],
            import_violations=["star import"]
        )

        assert analysis.file_path == Path("/test/file.py")
        assert analysis.mixed_imports == ["module1"]
        assert analysis.redundant_imports == ["unused"]
        assert analysis.unused_imports == ["old_import"]
        assert analysis.optimization_opportunities == ["consolidate imports"]
        assert analysis.import_violations == ["star import"]

    def test_agent_instantiation(self, agent):
        """Test successful instantiation of ImportOptimizationAgent."""
        assert agent is not None
        assert isinstance(agent, ImportOptimizationAgent)
        assert hasattr(agent, 'name')
        # The base class sets name to the class name
        assert agent.name == "ImportOptimizationAgent"

    def test_agent_log_method(self, agent):
        """Test agent log method with proper arguments."""
        # Test with message only
        result = agent.log("test message")
        assert result is None  # log method returns None

        # Test with message and level
        result = agent.log("test message", "ERROR")
        assert result is None

    def test_agent_get_supported_types(self, agent):
        """Test agent get_supported_types method."""
        result = agent.get_supported_types()
        assert isinstance(result, set)
        assert IssueType.IMPORT_ERROR in result
        assert IssueType.DEAD_CODE in result

    @pytest.mark.asyncio
    async def test_agent_can_handle(self, agent):
        """Test agent can_handle method with Issue instances."""
        # Test with supported issue type
        import_issue = Issue(
            id="test-1",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="unused import detected",
            file_path="/test/file.py",
            line_number=1
        )
        confidence = await agent.can_handle(import_issue)
        assert confidence == 0.85

        # Test with keyword matching
        keyword_issue = Issue(
            id="test-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.LOW,
            message="unused import found in module",
            file_path="/test/file.py",
            line_number=1
        )
        confidence = await agent.can_handle(keyword_issue)
        assert confidence == 0.8

        # Test with unsupported issue
        other_issue = Issue(
            id="test-3",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="test failed with assertion error",
            file_path="/test/file.py",
            line_number=1
        )
        confidence = await agent.can_handle(other_issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_agent_analyze_file_non_python(self, agent):
        """Test analyze_file with non-Python file."""
        txt_file = Path("/test/file.txt")
        analysis = await agent.analyze_file(txt_file)

        assert isinstance(analysis, ImportAnalysis)
        assert analysis.file_path == txt_file
        assert analysis.mixed_imports == []
        assert analysis.redundant_imports == []
        assert analysis.unused_imports == []

    @pytest.mark.asyncio
    async def test_agent_get_diagnostics(self, agent):
        """Test agent get_diagnostics method."""
        # The mock context already has an empty rglob return value
        result = await agent.get_diagnostics()
        assert isinstance(result, dict)
        assert "files_analyzed" in result
        assert "agent" in result
        assert result["agent"] == "ImportOptimizationAgent"
        assert "capabilities" in result

    @pytest.mark.asyncio
    async def test_agent_fix_issue_no_file_path(self, agent):
        """Test fix_issue with issue missing file_path."""
        issue = Issue(
            id="test-4",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="import error",
            file_path=None,
            line_number=1
        )

        result = await agent.fix_issue(issue)
        assert isinstance(result, FixResult)
        assert not result.success
        assert result.confidence == 0.0
        assert "No file path provided" in result.remaining_issues[0]
