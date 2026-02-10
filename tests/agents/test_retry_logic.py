"""Tests for AI agent retry logic with fallback strategies."""

import pytest
from pathlib import Path

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.helpers.retry_logic import (
    AgentRetryManager,
    FixStrategy,
    RetryConfig,
    create_fix_strategy_instructions,
    get_default_strategies_for_issue,
)


class TestRetryLogic:
    """Test retry logic framework."""

    @pytest.mark.asyncio
    async def test_fix_with_strategies_success_on_first_attempt(self, tmp_path):
        """Test that first successful strategy returns immediately."""
        context = AgentContext(project_path=tmp_path)
        manager = AgentRetryManager(context)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test error",
            file_path=str(tmp_path / "test.py"),
        )

        strategies = [FixStrategy.MINIMAL_EDIT, FixStrategy.ADD_ANNOTATION]

        async def mock_fix(issue: Issue, strategy: FixStrategy) -> FixResult:
            return FixResult(success=True, confidence=0.8)

        result = await manager.fix_with_strategies(issue, strategies, mock_fix)

        assert result.success is True
        assert len(manager.attempt_history) == 1
        assert manager.attempt_history[0]["strategy"] == "minimal_edit"
        assert manager.attempt_history[0]["success"] is True

    @pytest.mark.asyncio
    async def test_fix_with_strategies_fallback_to_second_strategy(self, tmp_path):
        """Test fallback to second strategy when first fails."""
        context = AgentContext(project_path=tmp_path)
        manager = AgentRetryManager(context)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test error",
            file_path=str(tmp_path / "test.py"),
        )

        strategies = [FixStrategy.MINIMAL_EDIT, FixStrategy.ADD_ANNOTATION]
        attempt_count = [0]

        async def mock_fix(issue: Issue, strategy: FixStrategy) -> FixResult:
            attempt_count[0] += 1
            # First attempt fails, second succeeds
            if attempt_count[0] == 1:
                return FixResult(success=False, confidence=0.0)
            return FixResult(success=True, confidence=0.8)

        result = await manager.fix_with_strategies(issue, strategies, mock_fix)

        assert result.success is True
        assert len(manager.attempt_history) == 2
        assert manager.attempt_history[0]["success"] is False
        assert manager.attempt_history[1]["success"] is True

    @pytest.mark.asyncio
    async def test_fix_with_strategies_all_fail(self, tmp_path):
        """Test behavior when all strategies fail."""
        context = AgentContext(project_path=tmp_path)
        manager = AgentRetryManager(context)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test error",
            file_path=str(tmp_path / "test.py"),
        )

        strategies = [FixStrategy.MINIMAL_EDIT, FixStrategy.ADD_ANNOTATION]

        async def mock_fix(issue: Issue, strategy: FixStrategy) -> FixResult:
            return FixResult(success=False, confidence=0.0)

        result = await manager.fix_with_strategies(issue, strategies, mock_fix)

        assert result.success is False
        assert len(manager.attempt_history) == 2
        assert manager.attempt_history[0]["success"] is False
        assert manager.attempt_history[1]["success"] is False

    def test_get_default_strategies_for_issue_type_error_with_annotation(self):
        """Test strategy selection for annotation errors."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="has no attribute 'Any' - need annotation",
        )

        strategies = get_default_strategies_for_issue(issue)

        assert strategies == [FixStrategy.ADD_ANNOTATION, FixStrategy.MINIMAL_EDIT]

    def test_get_default_strategies_for_issue_type_error_with_await(self):
        """Test strategy selection for await errors."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Are you missing an await?",
        )

        strategies = get_default_strategies_for_issue(issue)

        assert strategies == [FixStrategy.MINIMAL_EDIT, FixStrategy.FUNCTION_REPLACEMENT]

    def test_get_default_strategies_for_issue_complexity(self):
        """Test strategy selection for complexity issues."""
        issue = Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="Function too complex",
        )

        strategies = get_default_strategies_for_issue(issue)

        assert strategies == [FixStrategy.FUNCTION_REPLACEMENT, FixStrategy.SAFE_MERGE]

    def test_get_attempt_summary(self, tmp_path):
        """Test attempt summary generation."""
        context = AgentContext(project_path=tmp_path)
        manager = AgentRetryManager(context)

        # Simulate some attempts
        manager.attempt_history = [
            {"attempt": 1, "strategy": "minimal_edit", "success": False, "confidence": 0.0},
            {"attempt": 2, "strategy": "add_annotation", "success": True, "confidence": 0.8},
        ]

        summary = manager.get_attempt_summary()

        assert summary["total_attempts"] == 2
        assert summary["strategies_tried"] == ["minimal_edit", "add_annotation"]
        assert summary["success_rate"] == 0.5

    def test_create_fix_strategy_instructions(self):
        """Test strategy instruction generation."""
        instructions = create_fix_strategy_instructions(FixStrategy.MINIMAL_EDIT)

        assert "MINIMAL EDIT STRATEGY" in instructions
        assert "ONLY modify the specific lines" in instructions
        assert "DO NOT regenerate entire functions" in instructions

    def test_retry_config_defaults(self):
        """Test RetryConfig default values."""
        config = RetryConfig()

        assert config.MAX_ATTEMPTS == 3
        assert config.ENABLE_FALLBACKS is True
        assert config.VALIDATE_AFTER_EACH_ATTEMPT is True


class TestFixStrategyEnum:
    """Test FixStrategy enum."""

    def test_strategy_values(self):
        """Test that all strategy values are defined."""
        assert FixStrategy.MINIMAL_EDIT == "minimal_edit"
        assert FixStrategy.FUNCTION_REPLACEMENT == "function_replacement"
        assert FixStrategy.ADD_ANNOTATION == "add_annotation"
        assert FixStrategy.SAFE_MERGE == "safe_merge"
        assert FixStrategy.CONSERVATIVE == "conservative"

    def test_all_strategies_are_strings(self):
        """Test that all strategies are string values."""
        for strategy in FixStrategy:
            assert isinstance(strategy.value, str)
