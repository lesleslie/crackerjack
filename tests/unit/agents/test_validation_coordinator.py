"""Unit tests for validation coordinator behavior."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from crackerjack.agents.syntax_validator import ValidationResult
from crackerjack.agents.validation_coordinator import ValidationCoordinator


@pytest.mark.asyncio
async def test_validate_fix_ruff_only_skips_refurb() -> None:
    """Ruff-only validation should not invoke refurb checks."""
    coordinator = ValidationCoordinator(project_path=Path("/tmp"))

    coordinator.syntax.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.logic.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.behavior.validate = AsyncMock(
        return_value=ValidationResult(True, [])
    )
    coordinator.quality._check_ruff = AsyncMock(return_value=[])
    coordinator.quality._check_refurb = AsyncMock(return_value=["refurb: should not run"])

    is_valid, feedback = await coordinator.validate_fix(
        code="def hello() -> None:\n    print('hello')\n",
        file_path="/tmp/test.py",
        quality_checks=("ruff",),
    )

    assert is_valid is True
    assert feedback == "Fix validated"
    coordinator.quality._check_ruff.assert_awaited_once()
    coordinator.quality._check_refurb.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_fix_strict_ruff_validation_fails_on_existing_issue() -> None:
    """Strict Ruff validation should fail if the issue is still present."""
    coordinator = ValidationCoordinator(project_path=Path("/tmp"))

    coordinator.syntax.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.logic.validate = AsyncMock(return_value=ValidationResult(True, []))
    coordinator.behavior.validate = AsyncMock(
        return_value=ValidationResult(True, [])
    )
    coordinator.quality._check_ruff = AsyncMock(
        return_value=["ruff C901 (line 1): still too complex"]
    )
    coordinator.quality._check_refurb = AsyncMock(return_value=[])

    is_valid, feedback = await coordinator.validate_fix(
        code="def hello():\n    return 1\n",
        file_path="/tmp/test.py",
        original_code="def hello():\n    return 1\n",
        quality_checks=("ruff",),
        compare_to_original=False,
    )

    assert is_valid is False
    assert "Quality validation failed" in feedback
    coordinator.quality._check_ruff.assert_awaited_once()
    coordinator.quality._check_refurb.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_with_retry_forwards_strict_validation_mode() -> None:
    """Retry validation should preserve strict Ruff behavior."""
    coordinator = ValidationCoordinator(project_path=Path("/tmp"))
    coordinator.validate_fix = AsyncMock(return_value=(True, "Fix validated"))

    result = await coordinator.validate_with_retry(
        code="def hello():\n    return 1\n",
        file_path="/tmp/test.py",
        original_code="def hello():\n    return 1\n",
        quality_checks=("ruff",),
        compare_to_original=False,
    )

    assert result == (True, "Fix validated", 1)
    coordinator.validate_fix.assert_awaited_once_with(
        code="def hello():\n    return 1\n",
        file_path="/tmp/test.py",
        test_path=None,
        run_tests=False,
        original_code="def hello():\n    return 1\n",
        quality_checks=("ruff",),
        compare_to_original=False,
    )
