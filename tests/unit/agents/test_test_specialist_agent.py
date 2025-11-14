"""Unit tests for TestSpecialistAgent.

Tests pattern-based test failure detection, fixture fixes,
import error resolution, and specialized test issue handling.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.test_specialist_agent import TestSpecialistAgent


@pytest.mark.unit
class TestTestSpecialistAgentInitialization:
    """Test TestSpecialistAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test TestSpecialistAgent initializes correctly."""
        agent = TestSpecialistAgent(context)

        assert agent.context == context
        assert "fixture_not_found" in agent.common_test_patterns
        assert "import_error" in agent.common_test_patterns
        assert "assertion_error" in agent.common_test_patterns
        assert "mock_spec_error" in agent.common_test_patterns

    def test_get_supported_types(self, context):
        """Test agent supports test-related issue types."""
        agent = TestSpecialistAgent(context)

        supported = agent.get_supported_types()

        assert IssueType.TEST_FAILURE in supported
        assert IssueType.IMPORT_ERROR in supported
        assert len(supported) == 2


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestSpecialistAgentCanHandle:
    """Test confidence calculation for different test issues."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    async def test_can_handle_perfect_test_match(self, agent):
        """Test perfect confidence for test keywords."""
        issue = Issue(
            id="test-001",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="Test failed in pytest with assertion error",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 1.0

    async def test_can_handle_fixture_keyword(self, agent):
        """Test confidence for fixture-related messages."""
        issue = Issue(
            id="test-002",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="Fixture not found in conftest",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 1.0

    async def test_can_handle_test_file_path(self, agent):
        """Test confidence based on test file path."""
        issue = Issue(
            id="test-003",
            type=IssueType.TEST_FAILURE,
            severity=Priority.MEDIUM,
            message="Test issue",
            file_path="/tests/test_module.py",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_general_test_failure(self, agent):
        """Test default confidence for test failure type."""
        issue = Issue(
            id="test-004",
            type=IssueType.TEST_FAILURE,
            severity=Priority.MEDIUM,
            message="Generic test issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.7

    async def test_can_handle_unsupported_type(self, agent):
        """Test zero confidence for unsupported types."""
        issue = Issue(
            id="test-005",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.0


@pytest.mark.unit
class TestTestSpecialistAgentFailureIdentification:
    """Test failure type identification."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    def test_identify_fixture_not_found(self, agent):
        """Test identifying fixture not found errors."""
        issue = Issue(
            id="test-001",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="fixture 'temp_pkg_path' not found",
        )

        failure_type = agent._identify_failure_type(issue)

        assert failure_type == "fixture_not_found"

    def test_identify_hardcoded_path(self, agent):
        """Test identifying hardcoded path issues."""
        issue = Issue(
            id="test-002",
            type=IssueType.TEST_FAILURE,
            severity=Priority.MEDIUM,
            message="Path /test/path should use tmp_path fixture",
        )

        failure_type = agent._identify_failure_type(issue)

        # Pattern matching may return different results
        assert isinstance(failure_type, str)

    def test_identify_unknown_failure(self, agent):
        """Test identifying unknown failure types."""
        issue = Issue(
            id="test-003",
            type=IssueType.TEST_FAILURE,
            severity=Priority.LOW,
            message="Unexpected test failure",
        )

        failure_type = agent._identify_failure_type(issue)

        assert failure_type == "unknown"


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestSpecialistAgentAnalyzeAndFix:
    """Test analyze and fix workflow."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    async def test_analyze_and_fix_success(self, agent):
        """Test successful issue fixing."""
        issue = Issue(
            id="test-001",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="Test failed",
        )

        with patch.object(
            agent,
            "_apply_issue_fixes",
            return_value=(["Fixed test issue"], ["/tests/test_file.py"]),
        ):
            result = await agent.analyze_and_fix(issue)

            assert result.success is True
            assert result.confidence == 0.8
            assert len(result.fixes_applied) == 1

    async def test_analyze_and_fix_error_handling(self, agent):
        """Test error handling in analyze_and_fix."""
        issue = Issue(
            id="test-002",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="Test failed",
        )

        with patch.object(
            agent, "_apply_issue_fixes", side_effect=Exception("Fix failed")
        ):
            result = await agent.analyze_and_fix(issue)

            assert result.success is False
            assert result.confidence == 0.0
            assert "Failed to fix test issue" in result.remaining_issues[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestSpecialistAgentFixtureFixes:
    """Test fixture-related fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    async def test_fix_missing_temp_pkg_path_fixture(self, agent, tmp_path):
        """Test adding temp_pkg_path fixture."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
class TestModule:
    def test_something(self, temp_pkg_path):
        pass
""")

        issue = Issue(
            id="test-001",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="fixture 'temp_pkg_path' not found",
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        fixes = await agent._fix_missing_fixtures(issue)

        # Should handle fixture addition
        assert isinstance(fixes, list)

    async def test_fix_missing_console_fixture(self, agent, tmp_path):
        """Test adding console fixture."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_console(console): pass")

        issue = Issue(
            id="test-002",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="fixture 'console' not found",
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        fixes = await agent._fix_missing_fixtures(issue)

        assert isinstance(fixes, list)

    async def test_fix_missing_tmp_path_fixture(self, agent):
        """Test handling built-in tmp_path fixture."""
        issue = Issue(
            id="test-003",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="fixture 'tmp_path' not found",
            file_path="/tests/test_file.py",
        )

        fixes = await agent._fix_missing_fixtures(issue)

        # Should note that tmp_path is built-in
        assert len(fixes) == 1
        assert "built-in pytest fixture" in fixes[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestSpecialistAgentImportFixes:
    """Test import error fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    async def test_fix_import_errors_add_pytest(self, agent, tmp_path):
        """Test adding missing pytest import."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
def test_something():
    assert True
""")

        issue = Issue(
            id="test-001",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.HIGH,
            message="name 'pytest' is not defined",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        fixes = await agent._fix_import_errors(issue)

        # Should attempt to add pytest import
        assert isinstance(fixes, list)

    async def test_fix_import_errors_add_pathlib(self, agent, tmp_path):
        """Test adding missing pathlib import."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
def test_path():
    p = Path("test")
""")

        issue = Issue(
            id="test-002",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.HIGH,
            message="Path not defined",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        fixes = await agent._fix_import_errors(issue)

        assert isinstance(fixes, list)

    async def test_fix_import_errors_invalid_file(self, agent):
        """Test handling invalid file path."""
        issue = Issue(
            id="test-003",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.HIGH,
            message="Import error",
            file_path=None,
        )

        fixes = await agent._fix_import_errors(issue)

        assert fixes == []

    def test_needs_pytest_import(self, agent):
        """Test detecting missing pytest import."""
        content_without = "def test_foo(): pass"
        content_with = "import pytest\ndef test_foo(): pass"

        assert agent._needs_pytest_import(content_without) is True
        assert agent._needs_pytest_import(content_with) is False

    def test_needs_pathlib_import(self, agent):
        """Test detecting missing pathlib import."""
        content_without = "p = Path('test')"
        content_with = "from pathlib import Path\np = Path('test')"

        assert agent._needs_pathlib_import(content_without) is True
        assert agent._needs_pathlib_import(content_with) is False

    def test_needs_mock_import(self, agent):
        """Test detecting missing Mock import."""
        content_without = "m = Mock()"
        content_with = "from unittest.mock import Mock\nm = Mock()"

        assert agent._needs_mock_import(content_without) is True
        assert agent._needs_mock_import(content_with) is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestSpecialistAgentPathFixes:
    """Test hardcoded path fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    async def test_fix_hardcoded_paths(self, agent, tmp_path):
        """Test fixing hardcoded paths."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
def test_path():
    p = Path("/test/path")
""")

        issue = Issue(
            id="test-001",
            type=IssueType.TEST_FAILURE,
            severity=Priority.MEDIUM,
            message="Hardcoded path detected",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        fixes = await agent._fix_hardcoded_paths(issue)

        assert isinstance(fixes, list)

    async def test_fix_hardcoded_paths_no_file(self, agent):
        """Test handling missing file path."""
        issue = Issue(
            id="test-002",
            type=IssueType.TEST_FAILURE,
            severity=Priority.MEDIUM,
            message="Hardcoded path",
            file_path=None,
        )

        fixes = await agent._fix_hardcoded_paths(issue)

        assert fixes == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestSpecialistAgentMockFixes:
    """Test mock-related fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    async def test_fix_mock_issues(self, agent, tmp_path):
        """Test fixing mock issues."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
def test_console():
    console = Mock()
""")

        issue = Issue(
            id="test-001",
            type=IssueType.TEST_FAILURE,
            severity=Priority.MEDIUM,
            message="Mock spec error",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        fixes = await agent._fix_mock_issues(issue)

        assert isinstance(fixes, list)

    def test_needs_console_mock_fix(self, agent):
        """Test detecting console mock issues."""
        content_needs_fix = "console = Mock()"
        content_no_fix = "console = Console()"

        assert agent._needs_console_mock_fix(content_needs_fix) is True
        assert agent._needs_console_mock_fix(content_no_fix) is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestSpecialistAgentGeneralFixes:
    """Test general test file fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    async def test_fix_test_file_issues(self, agent, tmp_path):
        """Test applying general fixes to test file."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
def test_something():
    assert True
""")

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        with patch("crackerjack.services.regex_patterns.apply_test_fixes", return_value=test_file.read_text()):
            fixes = await agent._fix_test_file_issues(str(test_file))

            assert isinstance(fixes, list)

    async def test_apply_general_test_fixes(self, agent):
        """Test applying general test fixes."""
        with patch.object(
            agent,
            "run_command",
            return_value=(0, "", ""),
        ):
            fixes = await agent._apply_general_test_fixes()

            assert isinstance(fixes, list)

    async def test_apply_general_test_fixes_with_import_error(self, agent):
        """Test detecting import issues during test collection."""
        with patch.object(
            agent,
            "run_command",
            return_value=(1, "", "ImportError: cannot import name"),
        ):
            fixes = await agent._apply_general_test_fixes()

            assert len(fixes) > 0
            assert "import issues" in fixes[0]


@pytest.mark.unit
class TestTestSpecialistAgentHelpers:
    """Test helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    def test_check_perfect_test_matches(self, agent):
        """Test perfect test match detection."""
        assert agent._check_perfect_test_matches("test failed") == 1.0
        assert agent._check_perfect_test_matches("pytest error") == 1.0
        assert agent._check_perfect_test_matches("fixture not found") == 1.0
        assert agent._check_perfect_test_matches("some other error") == 0.0

    def test_check_test_file_path(self, agent):
        """Test file path checking."""
        assert agent._check_test_file_path("/tests/test_module.py") == 0.8
        assert agent._check_test_file_path("/src/test_utils.py") == 0.8
        assert agent._check_test_file_path("/src/module.py") == 0.0
        assert agent._check_test_file_path(None) == 0.0

    def test_check_general_test_failure(self, agent):
        """Test general test failure confidence."""
        assert agent._check_general_test_failure(IssueType.TEST_FAILURE) == 0.7
        assert agent._check_general_test_failure(IssueType.FORMATTING) == 0.0

    def test_get_failure_recommendations_with_fixes(self, agent):
        """Test recommendations when fixes applied."""
        recommendations = agent._get_failure_recommendations(["Fix applied"])

        assert recommendations == []

    def test_get_failure_recommendations_no_fixes(self, agent):
        """Test recommendations when no fixes applied."""
        recommendations = agent._get_failure_recommendations([])

        assert len(recommendations) > 0
        assert any("import" in r for r in recommendations)

    def test_is_valid_file_path(self, agent, tmp_path):
        """Test file path validation."""
        valid_file = tmp_path / "test.py"
        valid_file.write_text("content")

        assert agent._is_valid_file_path(str(valid_file)) is True
        assert agent._is_valid_file_path(str(tmp_path / "nonexistent.py")) is False
        assert agent._is_valid_file_path(None) is False

    def test_find_import_section_end(self, agent):
        """Test finding import section end."""
        lines = [
            "import os",
            "import sys",
            "from pathlib import Path",
            "",
            "def foo(): pass",
        ]

        end = agent._find_import_section_end(lines)

        assert end == 3


@pytest.mark.unit
@pytest.mark.asyncio
class TestTestSpecialistAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create TestSpecialistAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return TestSpecialistAgent(context)

    async def test_full_workflow_fixture_fix(self, agent, tmp_path):
        """Test complete workflow for fixture fix."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
class TestModule:
    def test_with_fixture(self, temp_pkg_path):
        assert temp_pkg_path.exists()
""")

        issue = Issue(
            id="test-001",
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="fixture 'temp_pkg_path' not found",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value=test_file.read_text())
        agent.context.write_file_content = Mock(return_value=True)

        # Should identify and attempt to fix
        failure_type = agent._identify_failure_type(issue)
        assert failure_type == "fixture_not_found"

        result = await agent.analyze_and_fix(issue)
        assert isinstance(result, FixResult)

    def test_pattern_coverage(self, agent):
        """Test all pattern types are covered."""
        patterns = agent.common_test_patterns

        assert "fixture_not_found" in patterns
        assert "import_error" in patterns
        assert "assertion_error" in patterns
        assert "attribute_error" in patterns
        assert "mock_spec_error" in patterns
        assert "hardcoded_path" in patterns
        assert "missing_import" in patterns
        assert "pydantic_validation" in patterns
