import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.documentation_agent import DocumentationAgent


@pytest.fixture
def temp_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        context = AgentContext(project_path=Path(temp_dir))
        yield context


@pytest.fixture
def documentation_agent(temp_context):
    return DocumentationAgent(temp_context)


class TestDocumentationAgentSimple:
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
    async def test_analyze_and_fix_with_nonexistent_file(
        self, documentation_agent
    ) -> None:
        issue = Issue(
            id="doc - 002",
            type=IssueType.DOCUMENTATION,
            message="Agent count mismatch in documentation",
            file_path="/ nonexistent / file.md",
            severity=Priority.MEDIUM,
        )

        result = await documentation_agent.analyze_and_fix(issue)

        assert result is not None
        assert isinstance(result.success, bool)

    @pytest.mark.asyncio
    async def test_analyze_and_fix_general_update(self, documentation_agent) -> None:
        issue = Issue(
            id="doc - 003",
            type=IssueType.DOCUMENTATION,
            message="General documentation update needed",
            file_path="/ test / file.md",
            severity=Priority.LOW,
        )

        result = await documentation_agent.analyze_and_fix(issue)

        assert result is not None
        assert isinstance(result.success, bool)
        assert isinstance(result.confidence, float)
