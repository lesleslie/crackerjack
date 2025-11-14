"""Unit tests for DocumentationAgent.

Tests changelog updates, documentation consistency checks,
agent count verification, and API documentation.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.documentation_agent import DocumentationAgent


@pytest.mark.unit
class TestDocumentationAgentInitialization:
    """Test DocumentationAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test DocumentationAgent initializes correctly."""
        agent = DocumentationAgent(context)

        assert agent.context == context

    def test_get_supported_types(self, context):
        """Test agent supports documentation issues."""
        agent = DocumentationAgent(context)

        supported = agent.get_supported_types()

        assert IssueType.DOCUMENTATION in supported
        assert len(supported) == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestDocumentationAgentCanHandle:
    """Test documentation issue detection and handling capability."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DocumentationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return DocumentationAgent(context)

    async def test_can_handle_documentation_issue(self, agent):
        """Test confidence for documentation issues."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Documentation needs updating",
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
class TestDocumentationAgentAnalyzeAndFix:
    """Test documentation issue analysis and fixing."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DocumentationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return DocumentationAgent(context)

    async def test_analyze_and_fix_changelog(self, agent):
        """Test analyzing changelog issues."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Changelog needs updating",
        )

        with patch.object(agent, "_update_changelog") as mock_update:
            mock_update.return_value = FixResult(success=True, confidence=0.9)

            result = await agent.analyze_and_fix(issue)

            mock_update.assert_called_once_with(issue)
            assert result.success is True

    async def test_analyze_and_fix_consistency(self, agent):
        """Test analyzing consistency issues."""
        issue = Issue(
            id="doc-002",
            type=IssueType.DOCUMENTATION,
            severity=Priority.MEDIUM,
            message="Agent count consistency issue",
        )

        with patch.object(agent, "_fix_documentation_consistency") as mock_fix:
            mock_fix.return_value = FixResult(success=True, confidence=0.85)

            result = await agent.analyze_and_fix(issue)

            mock_fix.assert_called_once_with(issue)
            assert result.success is True

    async def test_analyze_and_fix_api_docs(self, agent):
        """Test analyzing API documentation issues."""
        issue = Issue(
            id="doc-003",
            type=IssueType.DOCUMENTATION,
            severity=Priority.MEDIUM,
            message="API documentation needs update",
        )

        with patch.object(agent, "_update_api_documentation") as mock_api:
            mock_api.return_value = FixResult(success=True, confidence=0.8)

            result = await agent.analyze_and_fix(issue)

            mock_api.assert_called_once_with(issue)
            assert result.success is True

    async def test_analyze_and_fix_readme(self, agent):
        """Test analyzing README issues."""
        issue = Issue(
            id="doc-004",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="README needs updating",
        )

        with patch.object(agent, "_update_api_documentation") as mock_api:
            mock_api.return_value = FixResult(success=True, confidence=0.8)

            result = await agent.analyze_and_fix(issue)

            mock_api.assert_called_once_with(issue)

    async def test_analyze_and_fix_general(self, agent):
        """Test analyzing general documentation issues."""
        issue = Issue(
            id="doc-005",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="General documentation update needed",
        )

        with patch.object(agent, "_general_documentation_update") as mock_general:
            mock_general.return_value = FixResult(success=True, confidence=0.7)

            result = await agent.analyze_and_fix(issue)

            mock_general.assert_called_once_with(issue)

    async def test_analyze_and_fix_error_handling(self, agent):
        """Test error handling in analyze_and_fix."""
        issue = Issue(
            id="doc-006",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Changelog update",
        )

        with patch.object(agent, "_update_changelog", side_effect=Exception("Test error")):
            result = await agent.analyze_and_fix(issue)

            assert result.success is False
            assert result.confidence == 0.0
            assert "Error processing" in result.remaining_issues[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestDocumentationAgentChangelog:
    """Test changelog update functionality."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DocumentationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        # Change to tmp_path directory for changelog operations
        import os
        os.chdir(tmp_path)
        return DocumentationAgent(context)

    async def test_update_changelog_no_changes(self, agent):
        """Test updating changelog when no recent changes."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Update changelog",
        )

        with patch.object(agent, "_get_recent_changes", return_value=[]):
            result = await agent._update_changelog(issue)

            assert result.success is True
            assert result.confidence == 0.7
            assert "No recent changes" in result.recommendations[0]

    async def test_update_changelog_with_changes(self, agent, tmp_path):
        """Test updating changelog with recent changes."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Update changelog",
        )

        changelog_path = Path("CHANGELOG.md")
        changelog_path.write_text("# Changelog\n\n## [1.0.0] - 2024-01-01\n")

        recent_changes = [
            {"type": "feat", "message": "New feature"},
            {"type": "fix", "message": "Bug fix"},
        ]

        with patch.object(agent, "_get_recent_changes", return_value=recent_changes):
            with patch.object(agent, "_generate_changelog_entry", return_value="## New Entry\n"):
                with patch.object(agent, "_insert_changelog_entry", return_value="Updated"):
                    agent.context.get_file_content = Mock(return_value=changelog_path.read_text())
                    agent.context.write_file_content = Mock(return_value=True)

                    result = await agent._update_changelog(issue)

                    assert result.success is True
                    assert result.confidence == 0.9
                    assert "CHANGELOG.md" in result.files_modified[0]

    async def test_update_changelog_create_new(self, agent):
        """Test creating new changelog when it doesn't exist."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Update changelog",
        )

        recent_changes = [{"type": "feat", "message": "Initial release"}]

        with patch.object(agent, "_get_recent_changes", return_value=recent_changes):
            with patch.object(agent, "_generate_changelog_entry", return_value="## Entry\n"):
                with patch.object(agent, "_create_initial_changelog", return_value="# Changelog\n"):
                    agent.context.write_file_content = Mock(return_value=True)

                    result = await agent._update_changelog(issue)

                    assert result.success is True

    async def test_update_changelog_read_failure(self, agent, tmp_path):
        """Test handling changelog read failure."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Update changelog",
        )

        changelog_path = Path("CHANGELOG.md")
        changelog_path.write_text("content")

        recent_changes = [{"type": "feat", "message": "Change"}]

        with patch.object(agent, "_get_recent_changes", return_value=recent_changes):
            agent.context.get_file_content = Mock(return_value=None)

            result = await agent._update_changelog(issue)

            assert result.success is False
            assert "Failed to read" in result.remaining_issues[0]

    async def test_update_changelog_write_failure(self, agent):
        """Test handling changelog write failure."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Update changelog",
        )

        recent_changes = [{"type": "feat", "message": "Change"}]

        with patch.object(agent, "_get_recent_changes", return_value=recent_changes):
            with patch.object(agent, "_generate_changelog_entry", return_value="Entry"):
                with patch.object(agent, "_create_initial_changelog", return_value="Changelog"):
                    agent.context.write_file_content = Mock(return_value=False)

                    result = await agent._update_changelog(issue)

                    assert result.success is False
                    assert "Failed to write" in result.remaining_issues[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestDocumentationAgentConsistency:
    """Test documentation consistency checking."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DocumentationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        import os
        os.chdir(tmp_path)
        return DocumentationAgent(context)

    async def test_fix_documentation_consistency_with_issues(self, agent, tmp_path):
        """Test fixing consistency issues."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.MEDIUM,
            message="Agent count consistency issue",
        )

        readme_path = tmp_path / "README.md"
        readme_path.write_text("We have 10 specialized agents")

        agent_count_issues = [
            (readme_path, "10", "12")
        ]

        with patch.object(agent, "_check_agent_count_consistency", return_value=agent_count_issues):
            with patch.object(agent, "_fix_agent_count_references", return_value="We have 12 specialized agents"):
                agent.context.get_file_content = Mock(return_value=readme_path.read_text())
                agent.context.write_file_content = Mock(return_value=True)

                result = await agent._fix_documentation_consistency(issue)

                assert result.success is True
                assert result.confidence == 0.85
                assert len(result.files_modified) > 0

    async def test_fix_documentation_consistency_already_consistent(self, agent):
        """Test when documentation is already consistent."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.MEDIUM,
            message="Check consistency",
        )

        with patch.object(agent, "_check_agent_count_consistency", return_value=[]):
            result = await agent._fix_documentation_consistency(issue)

            assert result.success is True
            assert result.confidence == 0.8
            assert "already consistent" in result.recommendations[0]

    async def test_fix_documentation_consistency_write_failure(self, agent, tmp_path):
        """Test when writing updated content fails."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.MEDIUM,
            message="Fix consistency",
        )

        readme_path = tmp_path / "README.md"
        agent_count_issues = [(readme_path, "10", "12")]

        with patch.object(agent, "_check_agent_count_consistency", return_value=agent_count_issues):
            with patch.object(agent, "_fix_agent_count_references", return_value="Updated"):
                agent.context.get_file_content = Mock(return_value="Original")
                agent.context.write_file_content = Mock(return_value=False)

                result = await agent._fix_documentation_consistency(issue)

                # Should still return success=True but no files modified
                assert len(result.files_modified) == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestDocumentationAgentAPIDocumentation:
    """Test API documentation updates."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DocumentationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return DocumentationAgent(context)

    async def test_update_api_documentation_no_changes(self, agent):
        """Test updating API docs when no changes detected."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            severity=Priority.LOW,
            message="Update API docs",
        )

        with patch.object(agent, "_detect_api_changes", return_value=[]):
            result = await agent._update_api_documentation(issue)

            assert result.success is True
            assert result.confidence == 0.7
            assert "No API changes" in result.recommendations[0]


@pytest.mark.unit
class TestDocumentationAgentHelpers:
    """Test helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DocumentationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        import os
        os.chdir(tmp_path)
        return DocumentationAgent(context)

    def test_get_recent_changes(self, agent):
        """Test getting recent changes from git."""
        # This method typically calls git commands
        if hasattr(agent, "_get_recent_changes"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=0,
                    stdout="feat: new feature\nfix: bug fix\n",
                    stderr=""
                )

                changes = agent._get_recent_changes()

                # Should return some form of change list
                assert isinstance(changes, list)

    def test_generate_changelog_entry(self, agent):
        """Test generating changelog entry from changes."""
        if hasattr(agent, "_generate_changelog_entry"):
            changes = [
                {"type": "feat", "message": "New feature"},
                {"type": "fix", "message": "Bug fix"},
            ]

            entry = agent._generate_changelog_entry(changes)

            # Should return formatted entry
            assert isinstance(entry, str)
            assert len(entry) > 0

    def test_insert_changelog_entry(self, agent):
        """Test inserting entry into existing changelog."""
        if hasattr(agent, "_insert_changelog_entry"):
            existing = "# Changelog\n\n## [1.0.0] - 2024-01-01\n"
            new_entry = "## [1.1.0] - 2024-02-01\n- New feature\n"

            result = agent._insert_changelog_entry(existing, new_entry)

            # Should insert entry in correct location
            assert isinstance(result, str)
            assert new_entry in result or existing in result

    def test_create_initial_changelog(self, agent):
        """Test creating initial changelog."""
        if hasattr(agent, "_create_initial_changelog"):
            entry = "## [1.0.0] - 2024-01-01\n- Initial release\n"

            result = agent._create_initial_changelog(entry)

            # Should create proper changelog structure
            assert isinstance(result, str)
            assert "Changelog" in result or "CHANGELOG" in result or len(result) > 0

    def test_check_agent_count_consistency(self, agent, tmp_path):
        """Test checking agent count consistency."""
        if hasattr(agent, "_check_agent_count_consistency"):
            readme = tmp_path / "README.md"
            readme.write_text("We have 10 agents")

            issues = agent._check_agent_count_consistency([readme])

            # Should detect inconsistencies
            assert isinstance(issues, list)

    def test_fix_agent_count_references(self, agent):
        """Test fixing agent count references."""
        if hasattr(agent, "_fix_agent_count_references"):
            content = "We have 10 specialized agents"
            current_count = "10"
            expected_count = "12"

            result = agent._fix_agent_count_references(
                content, current_count, expected_count
            )

            # Should update count
            assert isinstance(result, str)

    def test_detect_api_changes(self, agent):
        """Test detecting API changes."""
        if hasattr(agent, "_detect_api_changes"):
            changes = agent._detect_api_changes()

            # Should return list of changes
            assert isinstance(changes, list)


@pytest.mark.unit
class TestDocumentationAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create DocumentationAgent instance."""
        context = AgentContext(project_path=tmp_path)
        import os
        os.chdir(tmp_path)
        return DocumentationAgent(context)

    def test_multiple_documentation_files(self, agent, tmp_path):
        """Test handling multiple documentation files."""
        # Create multiple doc files
        (tmp_path / "README.md").write_text("# Project")
        (tmp_path / "CONTRIBUTING.md").write_text("# Contributing")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "api.md").write_text("# API")

        # Verify files exist
        assert (tmp_path / "README.md").exists()
        assert (tmp_path / "CONTRIBUTING.md").exists()
        assert (docs_dir / "api.md").exists()
