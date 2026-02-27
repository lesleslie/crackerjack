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
        cmd = ["uv", "run", "ruff", "format", "."]
        description = "Test command"

        # Mock the internal method
        with patch.object(coordinator, "_run_fix_command", return_value=True):
            result = coordinator.run_fix_command(cmd, description)

        assert result is True

    def test_check_tool_success_patterns_basic(self) -> None:
        """Test basic functionality of check_tool_success_patterns."""
        coordinator = AutofixCoordinator()
        cmd = ["uv", "run", "ruff", "format", "."]
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
        cmd = ["uv", "run", "ruff", "format", "."]

        # The actual validation checks for uv run <allowed_tool>
        result = coordinator.validate_fix_command(cmd)

        # ruff is in the allowed tools list, so this should pass
        assert result is True

    def test_validate_hook_result_basic(self) -> None:
        """Test basic functionality of validate_hook_result."""
        coordinator = AutofixCoordinator()
        result_obj = MagicMock()
        result_obj.name = "test_hook"
        result_obj.status = "passed"

        result = coordinator.validate_hook_result(result_obj)

        assert result is True

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
        """Test basic functionality of running async methods in new loop."""
        coordinator = AutofixCoordinator()

        # Test that async methods can be run in a new event loop
        # This tests the async infrastructure rather than a specific method
        loop = asyncio.new_event_loop()
        try:
            # Test with unknown mode which should return False quickly
            task = loop.create_task(
                coordinator.apply_autofix_for_hooks("unknown_mode", [])
            )
            result = await task
            assert result is False
        finally:
            loop.close()
