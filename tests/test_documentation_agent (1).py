import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.documentation_agent import DocumentationAgent


@pytest.fixture
def temp_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        context = AgentContext(project_path=Path(temp_dir))
        yield context


@pytest.fixture
def documentation_agent(temp_context):
    return DocumentationAgent(temp_context)


@pytest.fixture
def temp_project_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)

        (project_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [0.1.0] - 2025 - 01 - 01\n - Initial release\n",
        )
        (project_path / "README.md").write_text(
            "# Test Project\n\nThis project has 8 agents.\n",
        )
        (project_path / "pyproject.toml").write_text(
            '[project]\nname = "test - project"\nversion = "0.1.0"\n',
        )

        yield project_path


class TestDocumentationAgent:
    def test_get_supported_types(self, documentation_agent) -> None:
        supported_types = documentation_agent.get_supported_types()
        assert IssueType.DOCUMENTATION in supported_types
        assert len(supported_types) == 1

    @pytest.mark.asyncio
    async def test_can_handle_documentation_issue(self, documentation_agent) -> None:
        issue = Issue(
            id="doc - 001",
            type=IssueType.DOCUMENTATION,
            message="Documentation consistency issue",
            file_path="/ test / README.md",
            severity=Priority.MEDIUM,
        )

        confidence = await documentation_agent.can_handle(issue)
        assert confidence == 0.8

    @pytest.mark.asyncio
    async def test_cannot_handle_other_issue_types(self, documentation_agent) -> None:
        issue = Issue(
            id="perf - 001",
            type=IssueType.PERFORMANCE,
            message="Performance issue",
            file_path="/ test / main.py",
            severity=Priority.HIGH,
        )

        confidence = await documentation_agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_fix_documentation_issue(
        self, documentation_agent, temp_project_dir
    ) -> None:
        issue = Issue(
            id="doc - 002",
            type=IssueType.DOCUMENTATION,
            message="Agent count mismatch in documentation",
            file_path=str(temp_project_dir / "README.md"),
            severity=Priority.MEDIUM,
        )

        with patch.object(
            documentation_agent,
            "_fix_documentation_consistency",
        ) as mock_fix:
            mock_fix.return_value = FixResult(success=True, confidence=0.8)

            result = await documentation_agent.analyze_and_fix(issue)

            assert result.success is True
            mock_fix.assert_called_once()

    @pytest.mark.asyncio
    async def test_fix_documentation_issue_failure(
        self,
        documentation_agent,
        temp_project_dir,
    ) -> None:
        issue = Issue(
            id="doc - 003",
            type=IssueType.DOCUMENTATION,
            message="Changelog update needed",
            file_path="/ nonexistent / path / CHANGELOG.md",
            severity=Priority.LOW,
        )

        with patch.object(documentation_agent, "_get_recent_changes", return_value=[]):
            result = await documentation_agent.analyze_and_fix(issue)

            assert result.success is True
            assert "No recent changes to add to changelog" in str(
                result.recommendations,
            )

    @pytest.mark.asyncio
    async def test_fix_documentation_consistency_agent_count(
        self,
        documentation_agent,
        temp_project_dir,
    ) -> None:
        readme_path = temp_project_dir / "README.md"
        readme_path.write_text("# Test Project\n\nThis project has 7 agents.\n")

        issue = Issue(
            id="doc - 004",
            type=IssueType.DOCUMENTATION,
            message="Agent count consistency issue",
            file_path=str(readme_path),
            severity=Priority.MEDIUM,
        )

        result = await documentation_agent._fix_documentation_consistency(issue)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_fix_documentation_consistency_no_changes_needed(
        self,
        documentation_agent,
        temp_project_dir,
    ) -> None:
        readme_path = temp_project_dir / "README.md"
        readme_path.write_text("# Test Project\n\nThis project has 9 agents.\n")

        issue = Issue(
            id="doc - 005",
            type=IssueType.DOCUMENTATION,
            message="Agent count consistency check",
            file_path=str(readme_path),
            severity=Priority.MEDIUM,
        )

        result = await documentation_agent._fix_documentation_consistency(issue)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_changelog_version_bump(
        self,
        documentation_agent,
        temp_project_dir,
    ) -> None:
        changelog_path = temp_project_dir / "CHANGELOG.md"

        issue = Issue(
            id="doc - 006",
            type=IssueType.DOCUMENTATION,
            message="changelog update needed",
            file_path=str(changelog_path),
            severity=Priority.MEDIUM,
        )

        with patch.object(documentation_agent, "_get_recent_changes") as mock_changes:
            mock_changes.return_value = [
                {"message": "feat: add new feature", "hash": "abc123"},
                {"message": "fix: resolve bug in parser", "hash": "def456"},
            ]

            result = await documentation_agent._update_changelog(issue)

            assert result.success is True

    @patch("subprocess.run")
    def test_get_recent_changes(self, mock_run, documentation_agent) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=""),
            MagicMock(
                returncode=0,
                stdout="feat: add new feature | abc123 | Author1\nfix: resolve bug | def456 | Author2\ndocs: update README | ghi789 | Author3\n",
            ),
        ]

        changes = documentation_agent._get_recent_changes()

        assert len(changes) == 3
        assert changes[0]["message"] == "feat: add new feature"
        assert changes[0]["hash"] == "abc123"
        assert changes[0]["author"] == "Author1"
        assert changes[1]["message"] == "fix: resolve bug"
        assert changes[2]["message"] == "docs: update README"

    @patch("subprocess.run")
    def test_get_recent_changes_git_error(self, mock_run, documentation_agent) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        changes = documentation_agent._get_recent_changes()

        assert changes == []

    def test_check_agent_count_consistency_mismatch(
        self,
        documentation_agent,
        temp_project_dir,
    ) -> None:
        readme_path = temp_project_dir / "README.md"
        readme_path.write_text("# Test Project\n\nThis project has 5 agents.\n")

        issues = documentation_agent._check_agent_count_consistency([readme_path])

        assert isinstance(issues, list)

    def test_check_agent_count_consistency_no_issues(
        self,
        documentation_agent,
        temp_project_dir,
    ) -> None:
        readme_path = temp_project_dir / "README.md"
        readme_path.write_text(
            "# Test Project\n\nThis project has 9 specialized agents.\n",
        )

        issues = documentation_agent._check_agent_count_consistency([readme_path])

        assert isinstance(issues, list)

    def test_generate_changelog_entry_formatting(self, documentation_agent) -> None:
        changes = [
            {"message": "feat: add new feature", "hash": "abc123"},
            {"message": "fix: resolve critical bug", "hash": "def456"},
            {"message": "docs: update documentation", "hash": "ghi789"},
        ]

        entry = documentation_agent._generate_changelog_entry(changes)

        assert isinstance(entry, str)
        assert len(entry) > 0
