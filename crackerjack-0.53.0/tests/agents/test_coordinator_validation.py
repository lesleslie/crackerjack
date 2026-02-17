"""Test coordinator fallback and validation logic."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.coordinator import AgentCoordinator


@pytest.fixture
def agent_context(tmp_path: Path) -> AgentContext:
    """Create agent context with test directory."""
    return AgentContext(project_path=tmp_path)


@pytest.fixture
def mock_tracker() -> MagicMock:
    """Create mock agent tracker."""
    return MagicMock()


@pytest.fixture
def mock_debugger() -> MagicMock:
    """Create mock debugger."""
    return MagicMock()


@pytest.mark.asyncio
async def test_coordinator_validates_file_writes(
    tmp_path: Path,
    agent_context: AgentContext,
    mock_tracker: MagicMock,
    mock_debugger: MagicMock,
):
    """Test that coordinator validates agents actually wrote files."""
    # Create file with issues
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello( ):\n\tx=1\n")

    # Create issue
    issue = Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="Fix formatting",
        file_path=str(test_file),
        line_number=1,
    )

    # Run coordinator
    coordinator = AgentCoordinator(
        context=agent_context,
        tracker=mock_tracker,
        debugger=mock_debugger,
    )
    result = await coordinator.handle_issues([issue])

    # Verify coordinator detected the fix
    assert result.success, "Coordinator should report success"

    # CRITICAL: File must actually be modified on disk
    new_content = test_file.read_text()
    # FormattingAgent should have fixed the spacing
    assert (
        "def hello():" in new_content or "def hello ( ): " in new_content
    ), "File must be modified after agent reports success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
