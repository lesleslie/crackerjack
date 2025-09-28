import pytest
from pathlib import Path
from unittest.mock import Mock
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.claude_code_bridge import ClaudeCodeBridge


class TestClaudeCodeBridge:
    """Tests for ClaudeCodeBridge class.

    Following crackerjack-test-specialist principles:
    - Test actual class methods, not non-existent standalone functions
    - Use proper mocking for AgentContext
    - Keep tests focused on actual behavior
    - Use synchronous tests to avoid hangs
    """

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        import crackerjack.agents.claude_code_bridge
        assert crackerjack.agents.claude_code_bridge is not None

    @pytest.fixture
    def mock_context(self):
        """Fixture to create a properly mocked AgentContext."""
        mock_context = Mock(spec=AgentContext)
        mock_context.project_path = Path("/test/project")
        mock_context.get_file_content = Mock(return_value="# test content")
        mock_context.write_file_content = Mock(return_value=True)
        return mock_context

    @pytest.fixture
    def claude_bridge(self, mock_context):
        """Fixture to create ClaudeCodeBridge instance for testing."""
        return ClaudeCodeBridge(mock_context)

    @pytest.fixture
    def sample_issue(self):
        """Fixture to create a sample Issue for testing."""
        return Issue(
            id="test-issue-123",
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="Test complexity issue",
            file_path="/test/file.py",
            line_number=10,
            details=["Function complexity too high"]
        )

    @pytest.fixture
    def sample_fix_result(self):
        """Fixture to create a sample FixResult for testing."""
        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["Fixed complexity issue"],
            remaining_issues=[],
            recommendations=["Consider breaking function into smaller parts"],
            files_modified=["/test/file.py"]
        )

    def test_claude_bridge_instantiation(self, claude_bridge):
        """Test successful instantiation of ClaudeCodeBridge."""
        assert claude_bridge is not None
        assert isinstance(claude_bridge, ClaudeCodeBridge)
        assert hasattr(claude_bridge, 'context')
        assert hasattr(claude_bridge, 'logger')
        assert hasattr(claude_bridge, '_agent_path')
        assert hasattr(claude_bridge, '_consultation_cache')

    def test_should_consult_external_agent(self, claude_bridge, sample_issue):
        """Test should_consult_external_agent method with proper arguments."""
        # High confidence should not consult external agent
        result = claude_bridge.should_consult_external_agent(sample_issue, 0.9)
        assert result is False

        # Low confidence should consult for supported issue types
        result = claude_bridge.should_consult_external_agent(sample_issue, 0.5)
        assert result is True

        # Unsupported issue type should not consult
        unsupported_issue = Issue(
            id="unsupported-123",
            type=IssueType.DEAD_CODE,  # Use a type not in mapping
            severity=Priority.LOW,
            message="Dead code issue",
            file_path="/test/file.py",
            line_number=1,
            details=["Unused variable"]
        )
        result = claude_bridge.should_consult_external_agent(unsupported_issue, 0.5)
        assert result is False

    def test_get_recommended_external_agents(self, claude_bridge, sample_issue):
        """Test get_recommended_external_agents method."""
        result = claude_bridge.get_recommended_external_agents(sample_issue)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "refactoring-specialist" in result
        assert "crackerjack-architect" in result

    def test_verify_agent_availability(self, claude_bridge):
        """Test verify_agent_availability method."""
        # Test with non-existent agent
        result = claude_bridge.verify_agent_availability("non-existent-agent")
        assert result is False

        # Test with valid agent name format
        result = claude_bridge.verify_agent_availability("python-pro")
        assert isinstance(result, bool)

    def test_create_enhanced_fix_result(self, claude_bridge, sample_fix_result):
        """Test create_enhanced_fix_result method."""
        consultations = [
            {
                "status": "success",
                "agent": "python-pro",
                "recommendations": ["Use type hints", "Follow PEP 8"],
                "confidence": 0.9
            },
            {
                "status": "success",
                "agent": "refactoring-specialist",
                "recommendations": ["Break down complex functions"],
                "confidence": 0.85
            }
        ]

        result = claude_bridge.create_enhanced_fix_result(sample_fix_result, consultations)

        assert isinstance(result, FixResult)
        assert result.success == sample_fix_result.success
        assert result.confidence >= sample_fix_result.confidence
        assert len(result.recommendations) > len(sample_fix_result.recommendations)
        assert any("[python-pro]" in rec for rec in result.recommendations)
        assert any("[refactoring-specialist]" in rec for rec in result.recommendations)

    @pytest.mark.parametrize("issue_type,expected_agents", [
        (IssueType.COMPLEXITY, ["refactoring-specialist", "crackerjack-architect"]),
        (IssueType.SECURITY, ["security-auditor", "python-pro"]),
        (IssueType.TEST_FAILURE, ["crackerjack-test-specialist", "python-pro"]),
        (IssueType.PERFORMANCE, ["performance-specialist", "python-pro"]),
    ])
    def test_agent_mapping_for_issue_types(self, claude_bridge, issue_type, expected_agents):
        """Test that correct agents are recommended for different issue types."""
        issue = Issue(
            id=f"test-{issue_type.value}",
            type=issue_type,
            severity=Priority.MEDIUM,
            message="Test issue",
            file_path="/test/file.py",
            line_number=1,
            details=["Test details"]
        )

        result = claude_bridge.get_recommended_external_agents(issue)
        assert result == expected_agents

    def test_consultation_threshold_access(self, claude_bridge):
        """Test access to consultation threshold."""
        threshold = claude_bridge._get_consultation_threshold()
        assert isinstance(threshold, float)
        assert 0.0 <= threshold <= 1.0

    def test_agent_mapping_access(self, claude_bridge):
        """Test access to agent mapping."""
        mapping = claude_bridge._get_agent_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) > 0
        assert IssueType.COMPLEXITY in mapping
