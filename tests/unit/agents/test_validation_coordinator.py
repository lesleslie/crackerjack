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

