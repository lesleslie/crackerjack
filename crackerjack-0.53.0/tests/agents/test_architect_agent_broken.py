"""Test that ArchitectAgent delegates to specialists and actually fixes files.

After fixing ArchitectAgent to delegate instead of returning fake results,
files should actually be modified on disk.
"""

from pathlib import Path

import pytest

from crackerjack.agents.architect_agent import ArchitectAgent
from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority


@pytest.mark.asyncio
async def test_architect_agent_delegates_and_writes_files(tmp_path: Path):
    """Verify ArchitectAgent delegates to specialists and files are modified."""
    # Create file with formatting issues
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello( ):\n\tx=1\n")

    # Create formatting issue
    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="Fix formatting",
        file_path=str(test_file),
        line_number=1,
    )

    # Store original content
    original_content = test_file.read_text()

    # Run agent (should delegate to FormattingAgent)
    context = AgentContext(project_path=tmp_path)
    agent = ArchitectAgent(context)
    result = await agent.analyze_and_fix(issue)

    # Agent should report success
    assert result.success, "Agent should report success"

    # CRITICAL: File MUST be modified on disk (the real test)
    new_content = test_file.read_text()
    assert (
        new_content != original_content
    ), "File MUST be modified after agent reports success"

    # Verify actual formatting fixes applied
    assert "def hello()" in new_content or "def hello ( ): " in new_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
