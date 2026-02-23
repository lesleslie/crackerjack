"""Tests for ProactiveAgent diff size validation.

Tests the diff size validation logic without requiring full agent instantiation.
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

        # The _validate_diff_size method calls self.log() when diff is too large,
        # but for small diffs it just returns True without logging.
        # Since we pass None as self, this tests the logic without needing a full agent.
        # We need to verify the method works - it should return True for small diffs
        # without calling self.log() since the diff is within limits.
        try:
            result = ProactiveAgent._validate_diff_size(None, old_code, new_code)
            assert result is True, "Small diff should pass validation"
        except AttributeError:
            # If self.log is called, this will fail - but it shouldn't be for small diffs
            pytest.fail("_validate_diff_size should not call self.log for small diffs")

    def test_validate_diff_size_at_limit(self) -> None:
        """Test that diff at exactly MAX_DIFF_LINES passes."""
        # Create exactly 50 line diff
        old_lines = 10
        new_lines = old_lines + ProactiveAgent.MAX_DIFF_LINES
        old_code = "\n".join(["line"] * old_lines)
        new_code = "\n".join(["line"] * new_lines)

        # At limit, should return True without logging
        try:
            result = ProactiveAgent._validate_diff_size(None, old_code, new_code)
            assert result is True, "Diff at limit should pass validation"
        except AttributeError:
            pytest.fail("_validate_diff_size should not call self.log for diffs at limit")

    def test_validate_diff_size_exceeds_limit(self) -> None:
        """Test that diffs exceeding MAX_DIFF_LINES fail validation."""
        # Create 51 line diff (exceeds limit)
        old_lines = 10
        new_lines = old_lines + ProactiveAgent.MAX_DIFF_LINES + 1
        old_code = "\n".join(["line"] * old_lines)
        new_code = "\n".join(["line"] * new_lines)

        # Create a minimal mock object with a log method
        class MockAgent:
            def log(self, msg: str) -> None:
                pass

        mock_self = MockAgent()
        result = ProactiveAgent._validate_diff_size(mock_self, old_code, new_code)

        assert result is False, "Diff exceeding limit should fail validation"

    def test_validate_diff_size_decrease(self) -> None:
        """Test that decreasing code size also validates."""
        old_code = "\n".join(["line"] * 100)
        new_code = "\n".join(["line"] * 60)

        # The diff is 40 lines (decrease), which is under the limit
        try:
            result = ProactiveAgent._validate_diff_size(None, old_code, new_code)
            assert result is True, "Decreasing diff should be validated by size"
        except AttributeError:
            pytest.fail("_validate_diff_size should not call self.log for small diffs")

    def test_validate_diff_size_empty_to_content(self) -> None:
        """Test validation from empty to content."""
        old_code = ""
        new_code = "\n".join(["line"] * 25)

        # 25 lines is under the limit
        try:
            result = ProactiveAgent._validate_diff_size(None, old_code, new_code)
            assert result is True, "Empty to small diff should pass"
        except AttributeError:
            pytest.fail("_validate_diff_size should not call self.log for small diffs")

    def test_validate_diff_size_large_increase_logs_warning(self) -> None:
        """Test that large diff increase calls log method and returns False."""
        old_code = "\n".join(["line"] * 10)
        new_code = "\n".join(["line"] * 70)  # 60 line increase exceeds limit

        log_messages = []

        class MockAgent:
            def log(self, msg: str) -> None:
                log_messages.append(msg)

        mock_self = MockAgent()
        result = ProactiveAgent._validate_diff_size(mock_self, old_code, new_code)

        assert result is False, "Large diff should fail validation"
        assert len(log_messages) == 1, "Should log one warning message"
        assert "Diff too large" in log_messages[0], "Warning should mention diff size"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
