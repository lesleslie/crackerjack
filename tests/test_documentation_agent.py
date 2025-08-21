"""Tests for DocumentationAgent."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.documentation_agent import DocumentationAgent


@pytest.fixture
def temp_context():
    """Create a temporary AgentContext for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        context = AgentContext(project_path=Path(temp_dir))
        yield context


@pytest.fixture
def documentation_agent(temp_context):
    """Create a DocumentationAgent instance for testing."""
    return DocumentationAgent(temp_context)


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        # Create basic project structure
        (project_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [0.1.0] - 2025-01-01\n- Initial release\n"
        )
        (project_path / "README.md").write_text(
            "# Test Project\n\nThis project has 8 agents.\n"
        )
        (project_path / "pyproject.toml").write_text(
            '[project]\nname = "test-project"\nversion = "0.1.0"\n'
        )

        yield project_path


class TestDocumentationAgent:
    """Test cases for DocumentationAgent."""

    def test_get_supported_types(self, documentation_agent):
        """Test that DocumentationAgent supports DOCUMENTATION type."""
        supported_types = documentation_agent.get_supported_types()
        assert IssueType.DOCUMENTATION in supported_types
        assert len(supported_types) == 1

    @pytest.mark.asyncio
    async def test_can_handle_documentation_issue(self, documentation_agent):
        """Test that DocumentationAgent can handle documentation issues with correct confidence."""
        issue = Issue(
            id="doc-001",
            type=IssueType.DOCUMENTATION,
            message="Documentation consistency issue",
            file_path="/test/README.md",
            severity=Priority.MEDIUM,
        )

        confidence = await documentation_agent.can_handle(issue)
        assert confidence == 0.8

    @pytest.mark.asyncio
    async def test_cannot_handle_other_issue_types(self, documentation_agent):
        """Test that DocumentationAgent returns 0.0 confidence for non-documentation issues."""
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            message="Performance issue",
            file_path="/test/main.py",
            severity=Priority.HIGH,
        )

        confidence = await documentation_agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_fix_documentation_issue(self, documentation_agent, temp_project_dir):
        """Test fixing a documentation issue."""
        issue = Issue(
            id="doc-002",
            type=IssueType.DOCUMENTATION,
            message="Agent count mismatch in documentation",
            file_path=str(temp_project_dir / "README.md"),
            severity=Priority.MEDIUM,
        )

        with patch.object(
            documentation_agent, "_fix_documentation_consistency"
        ) as mock_fix:
            mock_fix.return_value = True

            result = await documentation_agent.analyze_and_fix(issue)

            assert result.success is True
            mock_fix.assert_called_once()

    @pytest.mark.asyncio
    async def test_fix_documentation_issue_failure(
        self, documentation_agent, temp_project_dir
    ):
        """Test handling of documentation fix failure."""
        issue = Issue(
            id="doc-003",
            type=IssueType.DOCUMENTATION,
            message="Changelog update needed",
            file_path=str(temp_project_dir / "CHANGELOG.md"),
            severity=Priority.LOW,
        )

        # Test when file doesn't exist
        result = await documentation_agent.analyze_and_fix(issue)

        assert result.success is False
        assert len(result.remaining_issues) > 0

    def test_fix_documentation_consistency_agent_count(
        self, documentation_agent, temp_project_dir
    ):
        """Test fixing agent count inconsistencies in documentation."""
        # Create README with incorrect agent count
        readme_path = temp_project_dir / "README.md"
        readme_path.write_text("# Test Project\n\nThis project has 7 agents.\n")

        result = documentation_agent._fix_documentation_consistency(str(readme_path))

        assert result is True
        updated_content = readme_path.read_text()
        assert "9 agents" in updated_content or "9 specialized" in updated_content

    def test_fix_documentation_consistency_no_changes_needed(
        self, documentation_agent, temp_project_dir
    ):
        """Test when documentation is already consistent."""
        readme_path = temp_project_dir / "README.md"
        readme_path.write_text("# Test Project\n\nThis project has 9 agents.\n")

        result = documentation_agent._fix_documentation_consistency(str(readme_path))

        # Should return True even when no changes are needed
        assert result is True

    def test_update_changelog_version_bump(self, documentation_agent, temp_project_dir):
        """Test updating changelog during version bump."""
        changelog_path = temp_project_dir / "CHANGELOG.md"

        with patch.object(documentation_agent, "_get_recent_changes") as mock_changes:
            mock_changes.return_value = [
                "feat: add new feature",
                "fix: resolve bug in parser",
            ]

            result = documentation_agent._update_changelog(str(changelog_path), "0.2.0")

            assert result is True
            updated_content = changelog_path.read_text()
            assert "## [0.2.0]" in updated_content
            assert "add new feature" in updated_content
            assert "resolve bug in parser" in updated_content

    @patch("subprocess.run")
    def test_get_recent_changes(self, mock_run, documentation_agent):
        """Test getting recent git changes."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="feat: add new feature\nfix: resolve bug\ndocs: update README\n",
        )

        changes = documentation_agent._get_recent_changes()

        assert len(changes) == 3
        assert "feat: add new feature" in changes
        assert "fix: resolve bug" in changes
        assert "docs: update README" in changes

    @patch("subprocess.run")
    def test_get_recent_changes_git_error(self, mock_run, documentation_agent):
        """Test handling git command errors."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        changes = documentation_agent._get_recent_changes()

        assert changes == []

    def test_detect_documentation_issues_agent_mismatch(
        self, documentation_agent, temp_project_dir
    ):
        """Test detecting agent count mismatches."""
        readme_path = temp_project_dir / "README.md"
        readme_path.write_text("# Test Project\n\nThis project has 5 agents.\n")

        issues = documentation_agent._detect_documentation_issues(str(readme_path))

        assert len(issues) > 0
        assert any("agent count" in issue.lower() for issue in issues)

    def test_detect_documentation_issues_no_issues(
        self, documentation_agent, temp_project_dir
    ):
        """Test when no documentation issues are found."""
        readme_path = temp_project_dir / "README.md"
        readme_path.write_text(
            "# Test Project\n\nThis project has 9 specialized agents.\n"
        )

        issues = documentation_agent._detect_documentation_issues(str(readme_path))

        # Should return empty list when no issues found
        assert issues == []

    def test_create_changelog_entry_formatting(self, documentation_agent):
        """Test changelog entry formatting."""
        changes = [
            "feat: add new feature",
            "fix: resolve critical bug",
            "docs: update documentation",
        ]

        entry = documentation_agent._create_changelog_entry("1.2.0", changes)

        assert "## [1.2.0]" in entry
        assert "add new feature" in entry
        assert "resolve critical bug" in entry
        assert "update documentation" in entry
        # Should format as bullet points
        assert "- " in entry
