"""Tests for autofix coordinator public methods."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.autofix_coordinator import AutofixCoordinator


class TestAutofixCoordinatorPublicMethods:
    """Test AutofixCoordinator public methods."""

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_basic(self) -> None:
        """Test basic functionality of apply_autofix_for_hooks."""
        coordinator = AutofixCoordinator()

        # Test with unknown mode - should return False
        result = await coordinator.apply_autofix_for_hooks("unknown_mode", [])
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_fast_stage_fixes_basic(self) -> None:
        """Test basic functionality of apply_fast_stage_fixes."""
        coordinator = AutofixCoordinator()
        hook_results: list[MagicMock] = []

        # Mock the internal async method
        with patch.object(
            coordinator,
            "_apply_fast_stage_fixes",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await coordinator.apply_fast_stage_fixes(hook_results)

        assert result is True

    @pytest.mark.asyncio
    async def test_apply_comprehensive_stage_fixes_basic(self) -> None:
        """Test basic functionality of apply_comprehensive_stage_fixes."""
        coordinator = AutofixCoordinator()
        hook_results: list[MagicMock] = []

        # Mock the internal async method
        with patch.object(
            coordinator,
            "_apply_comprehensive_stage_fixes",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await coordinator.apply_comprehensive_stage_fixes(hook_results)

        assert result is True

    def test_run_fix_command_basic(self) -> None:
        """Test basic functionality of run_fix_command."""
        coordinator = AutofixCoordinator()
        # Use bandit which is in the allowed tools list
        cmd = ["uv", "run", "bandit", "-r", "."]
        description = "Test command"

        # Mock the internal method
        with patch.object(coordinator, "_run_fix_command", return_value=True):
            result = coordinator.run_fix_command(cmd, description)

        assert result is True

    def test_check_tool_success_patterns_basic(self) -> None:
        """Test basic functionality of check_tool_success_patterns."""
        coordinator = AutofixCoordinator()
        # Use bandit which is in the allowed tools list
        cmd = ["uv", "run", "bandit", "-r", "."]
        result_obj = MagicMock()

        # Mock the internal method
        with patch.object(
            coordinator, "_check_tool_success_patterns", return_value=True
        ):
            result = coordinator.check_tool_success_patterns(cmd, result_obj)

        assert result is True

    def test_validate_fix_command_basic(self) -> None:
        """Test basic functionality of validate_fix_command."""
        coordinator = AutofixCoordinator()
        # Use bandit which is in the allowed tools list
        cmd = ["uv", "run", "bandit", "-r", "."]

        # The actual validation checks for uv run <allowed_tool>
        result = coordinator.validate_fix_command(cmd)

        # bandit is in the allowed tools list, so this should pass
        assert result is True

    def test_validate_fix_command_invalid_tool(self) -> None:
        """Test validate_fix_command with a non-allowed tool."""
        coordinator = AutofixCoordinator()
        # ruff is NOT in the allowed tools list
        cmd = ["uv", "run", "ruff", "format", "."]

        result = coordinator.validate_fix_command(cmd)

        # ruff is not in the allowed tools list, so this should fail
        assert result is False

    def test_validate_fix_command_invalid_format(self) -> None:
        """Test validate_fix_command with invalid command format."""
        coordinator = AutofixCoordinator()
        # Invalid command format (missing tool)
        cmd = ["uv", "run"]

        result = coordinator.validate_fix_command(cmd)

        assert result is False

    def test_validate_hook_result_basic(self) -> None:
        """Test basic functionality of validate_hook_result."""
        coordinator = AutofixCoordinator()
        result_obj = MagicMock()
        result_obj.name = "test_hook"
        result_obj.status = "passed"

        result = coordinator.validate_hook_result(result_obj)

        assert result is True

    def test_validate_hook_result_invalid_status(self) -> None:
        """Test validate_hook_result with invalid status."""
        coordinator = AutofixCoordinator()
        result_obj = MagicMock()
        result_obj.name = "test_hook"
        result_obj.status = "invalid_status"

        result = coordinator.validate_hook_result(result_obj)

        assert result is False

    def test_should_skip_autofix_basic(self) -> None:
        """Test basic functionality of should_skip_autofix."""
        coordinator = AutofixCoordinator()
        hook_results: list[MagicMock] = []

        # Mock the internal method
        with patch.object(coordinator, "_should_skip_autofix", return_value=False):
            result = coordinator.should_skip_autofix(hook_results)

        assert result is False

    @pytest.mark.asyncio
    async def test_run_in_new_loop_basic(self) -> None:
        """Test basic functionality of running async methods."""
        coordinator = AutofixCoordinator()

        # Test with unknown mode which should return False quickly
        # Use pytest's async support instead of creating our own loop
        result = await coordinator.apply_autofix_for_hooks("unknown_mode", [])
        assert result is False
