"""Test PatternAgent actually applies pattern-based fixes."""

from pathlib import Path

import pytest

from crackerjack.agents.pattern_agent import PatternAgent
from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority


@pytest.mark.asyncio
async def test_pattern_agent_fixes_try_except_pass(tmp_path: Path):
    """Test PatternAgent fixes try/except/pass pattern."""
    test_file = tmp_path / "test_suppress.py"
    original_content = """def example():
    try:
        do_something()
    except Exception:
        pass
"""
    test_file.write_text(original_content)

    issue = Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.MEDIUM,
        message="FURB107 Replace try/except/pass with contextlib.suppress",
        file_path=str(test_file),
        line_number=2,
    )

    context = AgentContext(project_path=tmp_path)
    agent = PatternAgent(context)
    result = await agent.analyze_and_fix(issue)

    # Agent should report success
    assert result.success, "PatternAgent should successfully fix the pattern"

    # File MUST be modified
    new_content = test_file.read_text()
    assert (
        new_content != original_content
    ), "File content must change after pattern fix"

    # Verify pattern was applied (at least suppress was added)
    assert "suppress" in new_content, "Should have added contextlib.suppress"


@pytest.mark.asyncio
async def test_pattern_agent_fixes_len_check(tmp_path: Path):
    """Test PatternAgent fixes len(collection) > 0 pattern."""
    test_file = tmp_path / "test_len.py"
    original_content = """def example(items):
    if len(items) > 0:
        return items[0]
    return None
"""
    test_file.write_text(original_content)

    issue = Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.MEDIUM,
        message="FURB115 Replace len(items) > 0 with items",
        file_path=str(test_file),
        line_number=2,
    )

    context = AgentContext(project_path=tmp_path)
    agent = PatternAgent(context)
    result = await agent.analyze_and_fix(issue)

    # Should succeed
    assert result.success or result.remaining_issues, "Should handle or explain"

    # If successful, file should be modified
    if result.success:
        new_content = test_file.read_text()
        assert new_content != original_content, "File should change"


@pytest.mark.asyncio
async def test_pattern_agent_priority(tmp_path: Path):
    """Test PatternAgent has appropriate priority for pattern issues."""
    test_file = tmp_path / "test.py"
    test_file.write_text("try:\n    pass\nexcept Exception:\n    pass\n")

    issue = Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.MEDIUM,
        message="FURB107 Replace try/except/pass with suppress",
        file_path=str(test_file),
        line_number=1,
    )

    context = AgentContext(project_path=tmp_path)
    agent = PatternAgent(context)

    # Should have high confidence for pattern issues
    confidence = await agent.can_handle(issue)
    assert confidence >= 0.9, "Should have high confidence for pattern issues"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
