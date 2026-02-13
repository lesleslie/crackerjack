"""Tests for ProactiveAgent diff size validation.

Simplified approach - test the method directly without instantiating abstract class.
"""

import pytest

from crackerjack.agents.proactive_agent import ProactiveAgent


class TestProactiveAgentDiffSize:
    """Test suite for diff size validation in ProactiveAgent."""

    def test_max_diff_lines_constant(self) -> None:
        """Test that MAX_DIFF_LINES is defined."""
        assert hasattr(ProactiveAgent, "MAX_DIFF_LINES")
        assert ProactiveAgent.MAX_DIFF_LINES == 50

    def test_validate_diff_size_small_change(self) -> None:
        """Test that small diffs pass validation."""
        old_code = "def foo():\n    pass"
        new_code = "def foo():\n    return 42"

        # Use unbound method with self=None (we're just testing the logic)
        result = ProactiveAgent._validate_diff_size(None, old_code, new_code)

        assert result is True, "Small diff should pass validation"

    def test_validate_diff_size_at_limit(self) -> None:
        """Test that diff at exactly MAX_DIFF_LINES passes."""
        # Create exactly 50 line diff
        old_lines = 10
        new_lines = old_lines + ProactiveAgent.MAX_DIFF_LINES
        old_code = "\n".join(["line"] * old_lines)
        new_code = "\n".join(["line"] * new_lines)

        result = ProactiveAgent._validate_diff_size(None, old_code, new_code)

        assert result is True, "Diff at limit should pass validation"

    def test_validate_diff_size_exceeds_limit(self) -> None:
        """Test that diffs exceeding MAX_DIFF_LINES fail validation."""
        # Create 51 line diff (exceeds limit)
        old_lines = 10
        new_lines = old_lines + ProactiveAgent.MAX_DIFF_LINES + 1
        old_code = "\n".join(["line"] * old_lines)
        new_code = "\n".join(["line"] * new_lines)

        result = ProactiveAgent._validate_diff_size(None, old_code, new_code)

        assert result is False, "Diff exceeding limit should fail validation"

    def test_validate_diff_size_decrease(self) -> None:
        """Test that decreasing code size also validates."""
        old_code = "\n".join(["line"] * 100)
        new_code = "\n".join(["line"] * 60)

        result = ProactiveAgent._validate_diff_size(None, old_code, new_code)

        assert result is True, "Decreasing diff should be validated by size"

    def test_validate_diff_size_empty_to_content(self) -> None:
        """Test validation from empty to content."""
        old_code = ""
        new_code = "\n".join(["line"] * 25)

        result = ProactiveAgent._validate_diff_size(None, old_code, new_code)

        assert result is True, "Empty to small diff should pass"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
