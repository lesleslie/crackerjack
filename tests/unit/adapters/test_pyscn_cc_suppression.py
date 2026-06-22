"""Tests for PyscnAdapter cyclomatic complexity suppression (Task 8)."""

from __future__ import annotations

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult


@pytest.mark.unit
class TestPyscnCCSuppression:
    @pytest.fixture
    async def adapter_with_skip_cc(self):
        from unittest.mock import patch

        from crackerjack.adapters.sast.pyscn import PyscnAdapter, PyscnSettings

        settings = PyscnSettings(
            timeout_seconds=120,
            max_workers=4,
            skip_cyclomatic=True,
        )
        adapter = PyscnAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="2.0.0"),
        ):
            await adapter.init()
        return adapter

    @pytest.fixture
    async def adapter_with_cc_enabled(self):
        from unittest.mock import patch

        from crackerjack.adapters.sast.pyscn import PyscnAdapter, PyscnSettings

        settings = PyscnSettings(
            timeout_seconds=120,
            max_workers=4,
            skip_cyclomatic=False,
        )
        adapter = PyscnAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="2.0.0"),
        ):
            await adapter.init()
        return adapter

    async def test_pyscn_cyclomatic_issues_suppressed(
        self, adapter_with_skip_cc
    ) -> None:
        """When skip_cyclomatic=True, 'is too complex' lines are NOT returned."""
        raw_output = (
            "crackerjack/core/phase_coordinator.py:507:1:"
            " error: function _run_all is too complex (20 > 15)\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter_with_skip_cc.parse_output(result)

        cc_issues = [i for i in issues if "too complex" in i.message.lower()]
        assert len(cc_issues) == 0, (
            "CC issues must be suppressed when skip_cyclomatic=True "
            "(ruff C901 already covers this in the fast stage)"
        )

    async def test_pyscn_cyclomatic_default_is_true(self) -> None:
        """skip_cyclomatic must default to True."""
        from crackerjack.adapters.sast.pyscn import PyscnSettings

        settings = PyscnSettings(timeout_seconds=120, max_workers=4)
        assert settings.skip_cyclomatic is True

    async def test_pyscn_cc_returned_when_not_skipped(
        self, adapter_with_cc_enabled
    ) -> None:
        """When skip_cyclomatic=False, CC issues DO appear."""
        raw_output = (
            "crackerjack/core/phase_coordinator.py:507:1:"
            " error: function _run_all is too complex (20 > 15)\n"
        )
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=raw_output,
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter_with_cc_enabled.parse_output(result)

        cc_issues = [i for i in issues if "too complex" in i.message.lower()]
        assert len(cc_issues) >= 1, (
            "CC issues must appear when skip_cyclomatic=False"
        )
