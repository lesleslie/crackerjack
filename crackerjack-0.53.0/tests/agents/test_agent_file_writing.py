"""Test that agents actually write files when they claim to fix issues.

This test prevents the "ArchitectAgent bug" where agents report success
but never actually modify files.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.formatting_agent import FormattingAgent


@pytest.fixture
def temp_file(tmp_path: Path) -> Path:
    """Create a temporary file with bad formatting."""
    test_file = tmp_path / "test_bad_formatting.py"
    test_file.write_text(
        "def hello( ):\n"  # Bad: spaces before paren
        "\tx=1\n"  # Bad: tabs instead of spaces
        "return x\n\n"  # Good: trailing newline
    )
    return test_file


@pytest.fixture
def agent_context(tmp_path: Path) -> AgentContext:
    """Create agent context with test directory."""
    return AgentContext(project_path=tmp_path)


@pytest.mark.asyncio
async def test_formatting_agent_writes_files(temp_file: Path, agent_context: AgentContext):
    """Test that FormattingAgent actually writes files to disk."""
    # Create issue
    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="Fix formatting issues",
        file_path=str(temp_file),
        line_number=1,
    )

    # Store original content
    original_content = temp_file.read_text()
    assert "def hello( ):" in original_content, "Test setup failed"

    # Run agent
    agent = FormattingAgent(agent_context)
    result = await agent.analyze_and_fix(issue)

    # Verify agent reports success
    assert result.success, "Agent should report success"
    assert len(result.files_modified) > 0, "Agent should claim files modified"

    # CRITICAL: Verify file actually changed on disk
    new_content = temp_file.read_text()
    assert new_content != original_content, "File content must change after fix"

    # Verify actual fixes applied
    assert "def hello():" in new_content or "def hello ( ): " in new_content


@pytest.mark.asyncio
async def test_agent_lie_detector(temp_file: Path, agent_context: AgentContext):
    """Test that agents don't claim to fix files without actually writing them.

    This prevents the ArchitectAgent bug where:
    - Agent returns FixResult(success=True, files_modified=[...])
    - But file on disk is unchanged
    """
    # Create issue
    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="Fix formatting",
        file_path=str(temp_file),
        line_number=1,
    )

    # Store original content and modification time
    original_content = temp_file.read_text()
    original_mtime = temp_file.stat().st_mtime

    # Run agent
    agent = FormattingAgent(agent_context)
    result = await agent.analyze_and_fix(issue)

    # If agent claims files were modified, they must actually be modified
    if result.success and len(result.files_modified) > 0:
        new_content = temp_file.read_text()
        new_mtime = temp_file.stat().st_mtime

        # File content must change
        assert (
            new_content != original_content
        ), "Agent claimed to modify file but content is unchanged"

        # Modification time should be newer (or at least not older)
        assert (
            new_mtime >= original_mtime
        ), "Agent claimed to modify file but mtime is older"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
