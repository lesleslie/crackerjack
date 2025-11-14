"""Unit tests for FormattingAgent.

Tests formatting issue detection, ruff integration,
whitespace fixes, and import organization.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.formatting_agent import FormattingAgent


@pytest.mark.unit
class TestFormattingAgentInitialization:
    """Test FormattingAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test FormattingAgent initializes correctly."""
        agent = FormattingAgent(context)

        assert agent.context == context

    def test_get_supported_types(self, context):
        """Test agent supports formatting and import error issues."""
        agent = FormattingAgent(context)

        supported = agent.get_supported_types()

        assert IssueType.FORMATTING in supported
        assert IssueType.IMPORT_ERROR in supported


@pytest.mark.unit
@pytest.mark.asyncio
class TestFormattingAgentCanHandle:
    """Test formatting issue detection and handling capability."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create FormattingAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return FormattingAgent(context)

    async def test_can_handle_would_reformat(self, agent):
        """Test perfect confidence for would reformat issues."""
        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="File would reformat with ruff",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 1.0

    async def test_can_handle_trailing_whitespace(self, agent):
        """Test perfect confidence for trailing whitespace."""
        issue = Issue(
            id="fmt-002",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Trailing whitespace found",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 1.0

    async def test_can_handle_ruff_keyword(self, agent):
        """Test perfect confidence for ruff-related issues."""
        issue = Issue(
            id="fmt-003",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Ruff format check failed",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 1.0

    async def test_can_handle_import_sorting(self, agent):
        """Test perfect confidence for import sorting."""
        issue = Issue(
            id="fmt-004",
            type=IssueType.IMPORT_ERROR,
            severity=Priority.LOW,
            message="Import sorting needed",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 1.0

    async def test_can_handle_whitespace_generic(self, agent):
        """Test high confidence for generic whitespace issues."""
        issue = Issue(
            id="fmt-005",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Whitespace issues detected",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_indent_issue(self, agent):
        """Test high confidence for indentation issues."""
        issue = Issue(
            id="fmt-006",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Incorrect indentation",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_line_length(self, agent):
        """Test high confidence for line length issues."""
        issue = Issue(
            id="fmt-007",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Line length exceeds limit",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_generic_formatting(self, agent):
        """Test moderate confidence for generic formatting issues."""
        issue = Issue(
            id="fmt-008",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.6

    async def test_cannot_handle_unsupported_type(self, agent):
        """Test agent cannot handle unsupported issue types."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Security issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
class TestFormattingAgentAnalyzeAndFix:
    """Test formatting issue analysis and fixing."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create FormattingAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return FormattingAgent(context)

    async def test_analyze_and_fix_success(self, agent):
        """Test successful formatting fix application."""
        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issues found",
        )

        with patch.object(agent, "_apply_ruff_fixes", return_value=["Ruff fix"]):
            with patch.object(agent, "_apply_whitespace_fixes", return_value=[]):
                with patch.object(agent, "_apply_import_fixes", return_value=[]):
                    result = await agent.analyze_and_fix(issue)

                    assert result.success is True
                    assert result.confidence == 0.9
                    assert len(result.fixes_applied) > 0

    async def test_analyze_and_fix_no_fixes(self, agent):
        """Test when no fixes can be applied."""
        issue = Issue(
            id="fmt-002",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        with patch.object(agent, "_apply_ruff_fixes", return_value=[]):
            with patch.object(agent, "_apply_whitespace_fixes", return_value=[]):
                with patch.object(agent, "_apply_import_fixes", return_value=[]):
                    result = await agent.analyze_and_fix(issue)

                    assert result.success is False
                    assert result.confidence == 0.3
                    assert len(result.recommendations) > 0

    async def test_analyze_and_fix_with_file_path(self, agent, tmp_path):
        """Test analyze_and_fix with specific file path."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass")

        issue = Issue(
            id="fmt-003",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
            file_path=str(test_file),
        )

        with patch.object(agent, "_apply_ruff_fixes", return_value=[]):
            with patch.object(agent, "_apply_whitespace_fixes", return_value=[]):
                with patch.object(agent, "_apply_import_fixes", return_value=[]):
                    with patch.object(agent, "_fix_specific_file", return_value=["File fix"]):
                        result = await agent.analyze_and_fix(issue)

                        assert result.success is True
                        assert str(test_file) in result.files_modified

    async def test_analyze_and_fix_error_handling(self, agent):
        """Test error handling in analyze_and_fix."""
        issue = Issue(
            id="fmt-004",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        with patch.object(agent, "_apply_ruff_fixes", side_effect=Exception("Test error")):
            result = await agent.analyze_and_fix(issue)

            assert result.success is False
            assert result.confidence == 0.0
            assert "Failed to apply" in result.remaining_issues[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestFormattingAgentRuffFixes:
    """Test ruff-based formatting fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create FormattingAgent instance."""
        context = AgentContext(project_path=tmp_path)
        agent = FormattingAgent(context)
        agent.run_command = AsyncMock()
        return agent

    async def test_apply_ruff_fixes_success(self, agent):
        """Test successful ruff formatting application."""
        agent.run_command.side_effect = [
            (0, "", ""),  # ruff format success
            (0, "", ""),  # ruff check --fix success
        ]

        fixes = await agent._apply_ruff_fixes()

        assert len(fixes) == 2
        assert "ruff code formatting" in fixes[0]
        assert "ruff linting fixes" in fixes[1]

    async def test_apply_ruff_fixes_format_failure(self, agent):
        """Test when ruff format fails."""
        agent.run_command.side_effect = [
            (1, "", "Format error"),  # ruff format failure
            (0, "", ""),  # ruff check --fix success
        ]

        fixes = await agent._apply_ruff_fixes()

        # Should continue and try check --fix
        assert len(fixes) == 1
        assert "linting" in fixes[0]

    async def test_apply_ruff_fixes_check_failure(self, agent):
        """Test when ruff check --fix fails."""
        agent.run_command.side_effect = [
            (0, "", ""),  # ruff format success
            (1, "", "Check error"),  # ruff check --fix failure
        ]

        fixes = await agent._apply_ruff_fixes()

        # Should still report format success
        assert len(fixes) == 1
        assert "formatting" in fixes[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestFormattingAgentWhitespaceFixes:
    """Test whitespace-related fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create FormattingAgent instance."""
        context = AgentContext(project_path=tmp_path)
        agent = FormattingAgent(context)
        agent.run_command = AsyncMock()
        return agent

    async def test_apply_whitespace_fixes_success(self, agent):
        """Test successful whitespace fixes."""
        agent.run_command.side_effect = [
            (0, "", ""),  # trailing whitespace fixer success
            (0, "", ""),  # end-of-file fixer success
        ]

        fixes = await agent._apply_whitespace_fixes()

        assert len(fixes) == 2
        assert "trailing whitespace" in fixes[0]
        assert "end-of-file" in fixes[1]

    async def test_apply_whitespace_fixes_partial_success(self, agent):
        """Test when only some whitespace fixes succeed."""
        agent.run_command.side_effect = [
            (0, "", ""),  # trailing whitespace fixer success
            (1, "", ""),  # end-of-file fixer failure
        ]

        fixes = await agent._apply_whitespace_fixes()

        assert len(fixes) == 1
        assert "trailing whitespace" in fixes[0]

    async def test_apply_whitespace_fixes_all_fail(self, agent):
        """Test when all whitespace fixes fail."""
        agent.run_command.side_effect = [
            (1, "", ""),  # trailing whitespace fixer failure
            (1, "", ""),  # end-of-file fixer failure
        ]

        fixes = await agent._apply_whitespace_fixes()

        assert len(fixes) == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestFormattingAgentImportFixes:
    """Test import organization fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create FormattingAgent instance."""
        context = AgentContext(project_path=tmp_path)
        agent = FormattingAgent(context)
        agent.run_command = AsyncMock()
        return agent

    async def test_apply_import_fixes_success(self, agent):
        """Test successful import fixes."""
        agent.run_command.return_value = (0, "", "")

        fixes = await agent._apply_import_fixes()

        assert len(fixes) == 1
        assert "import" in fixes[0].lower()

    async def test_apply_import_fixes_failure(self, agent):
        """Test when import fixes fail."""
        agent.run_command.return_value = (1, "", "Import error")

        fixes = await agent._apply_import_fixes()

        assert len(fixes) == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestFormattingAgentFileSpecificFixes:
    """Test file-specific formatting fixes."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create FormattingAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return FormattingAgent(context)

    async def test_fix_specific_file_success(self, agent, tmp_path):
        """Test successful file-specific fixes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    pass")

        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format issue",
        )

        agent.context.get_file_content = Mock(return_value="def foo():\n    pass")
        agent.context.write_file_content = Mock(return_value=True)

        with patch.object(agent, "_apply_content_formatting", return_value="def foo():\n    pass\n"):
            fixes = await agent._fix_specific_file(str(test_file), issue)

            assert len(fixes) > 0
            assert str(test_file) in fixes[0]

    async def test_fix_specific_file_no_changes(self, agent, tmp_path):
        """Test when no changes are needed."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    pass\n")

        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format issue",
        )

        content = test_file.read_text()
        agent.context.get_file_content = Mock(return_value=content)

        with patch.object(agent, "_apply_content_formatting", return_value=content):
            fixes = await agent._fix_specific_file(str(test_file), issue)

            assert len(fixes) == 0

    async def test_fix_specific_file_not_exists(self, agent, tmp_path):
        """Test fixing file that doesn't exist."""
        test_file = tmp_path / "missing.py"

        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format issue",
        )

        agent.context.get_file_content = Mock(return_value=None)

        fixes = await agent._fix_specific_file(str(test_file), issue)

        assert len(fixes) == 0

    async def test_fix_specific_file_error_handling(self, agent, tmp_path):
        """Test error handling in file-specific fixes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format issue",
        )

        agent.context.get_file_content = Mock(side_effect=Exception("Read error"))

        # Should not raise exception
        fixes = await agent._fix_specific_file(str(test_file), issue)

        assert len(fixes) == 0


@pytest.mark.unit
class TestFormattingAgentContentFormatting:
    """Test content formatting utilities."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create FormattingAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return FormattingAgent(context)

    def test_apply_content_formatting(self, agent):
        """Test applying content formatting."""
        content = "def foo():\n    pass"

        with patch("crackerjack.agents.formatting_agent.apply_formatting_fixes") as mock_apply:
            mock_apply.return_value = content

            result = agent._apply_content_formatting(content)

            # Should add newline at end
            assert result.endswith("\n")

    def test_apply_content_formatting_already_has_newline(self, agent):
        """Test formatting content that already has trailing newline."""
        content = "def foo():\n    pass\n"

        with patch("crackerjack.agents.formatting_agent.apply_formatting_fixes") as mock_apply:
            mock_apply.return_value = content

            result = agent._apply_content_formatting(content)

            assert result == content

    def test_convert_tabs_to_spaces(self, agent):
        """Test converting tabs to spaces."""
        content = "def foo():\n\treturn True\n"

        result = agent._convert_tabs_to_spaces(content)

        assert "\t" not in result
        assert "    return True" in result

    def test_convert_tabs_to_spaces_no_tabs(self, agent):
        """Test converting when no tabs present."""
        content = "def foo():\n    return True\n"

        result = agent._convert_tabs_to_spaces(content)

        assert result == content

    def test_validate_and_get_file_content_success(self, agent, tmp_path):
        """Test successfully validating and getting file content."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        agent.context.get_file_content = Mock(return_value="content")

        result = agent._validate_and_get_file_content(test_file)

        assert result == "content"

    def test_validate_and_get_file_content_not_exists(self, agent, tmp_path):
        """Test validating non-existent file."""
        test_file = tmp_path / "missing.py"

        result = agent._validate_and_get_file_content(test_file)

        assert result is None

    def test_validate_and_get_file_content_empty(self, agent, tmp_path):
        """Test validating file with empty content."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("")

        agent.context.get_file_content = Mock(return_value="")

        result = agent._validate_and_get_file_content(test_file)

        assert result is None


@pytest.mark.unit
class TestFormattingAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create FormattingAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return FormattingAgent(context)

    def test_multiple_formatting_operations(self, agent):
        """Test applying multiple formatting operations."""
        content = "\tdef foo():\n\t\treturn True  "  # Tab indent + trailing space

        with patch("crackerjack.agents.formatting_agent.apply_formatting_fixes") as mock_apply:
            mock_apply.return_value = content

            result = agent._apply_content_formatting(content)

            # Should convert tabs and add final newline
            assert "\t" not in result
            assert result.endswith("\n")
            # Trailing spaces should be handled by apply_formatting_fixes

    def test_empty_content_handling(self, agent):
        """Test handling empty content."""
        content = ""

        with patch("crackerjack.agents.formatting_agent.apply_formatting_fixes") as mock_apply:
            mock_apply.return_value = content

            result = agent._apply_content_formatting(content)

            # Empty content should still get newline
            assert result == "\n"
