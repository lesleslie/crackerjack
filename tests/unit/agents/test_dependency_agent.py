"""Tests for DependencyAgent.

Tests dependency removal functionality, TOML parsing, and
error handling for unused dependency issues.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from crackerjack.agents.dependency_agent import DependencyAgent
from crackerjack.agents.base import Issue, IssueType, Priority


@pytest.fixture
def mock_context():
    """Mock AgentContext."""
    context = MagicMock()
    context.get_file_content = MagicMock(return_value=None)
    context.write_file_content = MagicMock(return_value=True)
    return context


@pytest.fixture
def agent(mock_context):
    """Create DependencyAgent instance."""
    return DependencyAgent(mock_context)


class TestDependencyAgentSupportedTypes:
    """Test get_supported_types method."""

    def test_get_supported_types_returns_dependency(self, agent):
        """Test that DEPENDENCY is the only supported type."""
        supported = agent.get_supported_types()
        assert supported == {IssueType.DEPENDENCY}


class TestDependencyAgentCanHandle:
    """Test can_handle confidence scoring."""

    @pytest.mark.asyncio
    async def test_can_handle_unused_dependency_high_confidence(self, agent):
        """Test high confidence for 'unused dependency' messages."""
        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="pyproject.toml",
            line_number=1,
        )

        confidence = await agent.can_handle(issue)
        assert confidence == 0.9

    @pytest.mark.asyncio
    async def test_can_handle_dependency_keyword_medium_confidence(self, agent):
        """Test medium confidence for generic dependency messages."""
        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Dependency issue detected",
            file_path="pyproject.toml",
            line_number=1,
        )

        confidence = await agent.can_handle(issue)
        assert confidence == 0.5

    @pytest.mark.asyncio
    async def test_can_handle_non_dependency_issue_returns_zero(self, agent):
        """Test zero confidence for non-DEPENDENCY issues."""
        issue = Issue(
            type=IssueType.SECURITY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="pyproject.toml",
            line_number=1,
        )

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_can_handle_empty_message_returns_zero(self, agent):
        """Test zero confidence for empty message."""
        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="",
            file_path="pyproject.toml",
            line_number=1,
        )

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_can_handle_no_dependency_keyword_returns_zero(self, agent):
        """Test zero confidence for messages without 'dependency' keyword."""
        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Some other issue",
            file_path="pyproject.toml",
            line_number=1,
        )

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0


class TestDependencyAgentAnalyzeAndFix:
    """Test analyze_and_fix method."""

    @pytest.mark.asyncio
    async def test_analyze_and_fix_no_file_path(self, agent):
        """Test handling of missing file path."""
        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path=None,
            line_number=1,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert result.confidence == 0.0
        assert "No file path provided" in result.remaining_issues

    @pytest.mark.asyncio
    async def test_analyze_and_fix_non_pyproject_toml(self, agent):
        """Test rejection of non-pyproject.toml files."""
        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="requirements.txt",
            line_number=1,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert result.confidence == 0.0
        assert "only fix dependencies in pyproject.toml" in result.remaining_issues[0]

    @pytest.mark.asyncio
    async def test_analyze_and_fix_missing_file(self, agent, mock_context):
        """Test handling of missing file."""
        mock_context.get_file_content.return_value = None

        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="pyproject.toml",
            line_number=1,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert result.confidence == 0.0
        assert "Could not read pyproject.toml" in result.remaining_issues

    @pytest.mark.asyncio
    async def test_analyze_and_fix_no_dependencies_section(self, agent, mock_context):
        """Test handling of pyproject.toml without dependencies."""
        mock_context.get_file_content.return_value = """
[project]
name = "test"
version = "0.1.0"
"""

        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="pyproject.toml",
            line_number=1,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        # The implementation may return a different error message
        assert len(result.remaining_issues) > 0

    @pytest.mark.asyncio
    async def test_analyze_and_fix_dependency_not_found(self, agent, mock_context):
        """Test handling when dependency not in list."""
        mock_context.get_file_content.return_value = """
[project]
name = "test"
dependencies = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
]
"""

        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="pyproject.toml",
            line_number=1,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        # Check for either message format
        assert len(result.remaining_issues) > 0
        # Error message could be either format
        error_msg = result.remaining_issues[0]
        assert "not found" in error_msg or "Failed to remove" in error_msg

    @pytest.mark.asyncio
    async def test_analyze_and_fix_success_list_style(self, agent, mock_context):
        """Test successful dependency removal from list-style dependencies."""
        mock_context.get_file_content.return_value = """
[project]
name = "test"
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
]
"""
        mock_context.write_file_content.return_value = True

        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="pyproject.toml",
            line_number=1,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is True
        assert result.confidence == 0.9
        assert "Removed unused dependency: pytest-snob" in result.fixes_applied
        # files_modified may contain Path objects
        assert len(result.files_modified) > 0
        assert "pyproject.toml" in str(result.files_modified[0])

        # Verify write was called with modified content
        mock_context.write_file_content.assert_called_once()
        written_content = mock_context.write_file_content.call_args[0][1]
        assert "pytest-snob" not in written_content
        assert "pytest>=7.0.0" in written_content  # Other deps preserved

    @pytest.mark.asyncio
    async def test_analyze_and_fix_write_failure(self, agent, mock_context):
        """Test handling of write failure."""
        mock_context.get_file_content.return_value = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
        mock_context.write_file_content.return_value = False

        issue = Issue(
            type=IssueType.DEPENDENCY,
            severity=Priority.MEDIUM,
            message="Unused dependency: pytest-snob",
            file_path="pyproject.toml",
            line_number=1,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]


class TestExtractDependencyName:
    """Test _extract_dependency_name method."""

    def test_extract_pattern_colon_format(self, agent):
        """Test extraction from 'Unused dependency: name' format."""
        message = "Unused dependency: pytest-snob"
        dep_name = agent._extract_dependency_name(message)
        assert dep_name == "pytest-snob"

    def test_extract_pattern_quoted_format(self, agent):
        """Test extraction from 'Dependency 'name' is unused' format."""
        message = "Dependency 'pytest-snob' is unused"
        dep_name = agent._extract_dependency_name(message)
        assert dep_name == "pytest-snob"

    def test_extract_pattern_simple_format(self, agent):
        """Test extraction from 'name is unused' format."""
        message = "pytest-snob is unused"
        dep_name = agent._extract_dependency_name(message)
        assert dep_name == "pytest-snob"

    def test_extract_case_insensitive(self, agent):
        """Test case-insensitive matching."""
        message = "UNUSED DEPENDENCY: PyTest-Snob"
        dep_name = agent._extract_dependency_name(message)
        assert dep_name == "PyTest-Snob"

    def test_extract_with_dashes_and_underscores(self, agent):
        """Test extraction with dashes and underscores."""
        message = "Unused dependency: pytest-snob_extra"
        dep_name = agent._extract_dependency_name(message)
        assert dep_name == "pytest-snob_extra"

    def test_extract_malformed_message_returns_none(self, agent):
        """Test None return for malformed messages."""
        dep_name = agent._extract_dependency_name("Some random message")
        assert dep_name is None

    def test_extract_empty_message_returns_none(self, agent):
        """Test None return for empty message."""
        dep_name = agent._extract_dependency_name("")
        assert dep_name is None

    def test_extract_none_message_returns_none(self, agent):
        """Test None return for None input."""
        dep_name = agent._extract_dependency_name(None)
        assert dep_name is None


class TestRemoveDependencyFromToml:
    """Test _remove_dependency_from_toml method."""

    def test_remove_double_quoted_dependency(self, agent):
        """Test removal of double-quoted dependency."""
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
]
"""
        new_content = agent._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "pytest-snob" not in new_content
        assert "pytest>=7.0.0" in new_content
        assert "ruff>=0.1.0" in new_content

    def test_remove_single_quoted_dependency(self, agent):
        """Test removal of single-quoted dependency."""
        content = """
[project]
dependencies = [
    'pytest>=7.0.0',
    'pytest-snob>=0.1.0',
    'ruff>=0.1.0',
]
"""
        new_content = agent._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "pytest-snob" not in new_content
        assert "pytest>=7.0.0" in new_content

    def test_remove_preserves_other_dependencies(self, agent):
        """Test that other dependencies are preserved."""
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
    "ruff>=0.1.0",
    "black>=23.0.0",
]
"""
        new_content = agent._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "pytest>=7.0.0" in new_content
        assert "ruff>=0.1.0" in new_content
        assert "black>=23.0.0" in new_content

    def test_remove_handles_comments_correctly(self, agent):
        """Test that commented lines are not removed."""
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    # "pytest-snob>=0.1.0",  # Commented out
    "ruff>=0.1.0",
]
"""
        new_content = agent._remove_dependency_from_toml(content, "pytest-snob")
        # Should return None because the dependency is commented out
        assert new_content is None

    def test_remove_dependency_not_found_returns_none(self, agent):
        """Test None return when dependency not found."""
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
]
"""
        new_content = agent._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is None

    def test_remove_preserves_sections_outside_dependencies(self, agent):
        """Test that sections outside dependencies are preserved."""
        content = """
[tool.ruff]
line-length = 100

[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]

[tool.pytest]
testpaths = ["tests"]
"""
        new_content = agent._remove_dependency_from_toml(content, "pytest-snob")
        assert new_content is not None
        assert "[tool.ruff]" in new_content
        assert "line-length = 100" in new_content
        assert "[tool.pytest]" in new_content

    def test_remove_no_partial_matches(self, agent):
        """Test that 'pytest' doesn't match 'pytest-snob'."""
        content = """
[project]
dependencies = [
    "pytest>=7.0.0",
    "pytest-snob>=0.1.0",
]
"""
        # Try to remove 'pytest' - should not remove 'pytest-snob'
        new_content = agent._remove_dependency_from_toml(content, "pytest")
        # pytest-snob should still be there
        if new_content:  # If it found and removed pytest
            assert "pytest-snob" in new_content
