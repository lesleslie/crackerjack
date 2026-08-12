"""Tests for SyrupyAdapter — snapshot testing via pytest-syrupy plugin."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult


@pytest.mark.unit
class TestSyrupyHooksRegistration:
    """Syrupy is deliberately NOT registered as an auto-run hook.

    Decision: 35c7ccb3 (2026-06-28) removed the syrupy HookDefinition from
    COMPREHENSIVE_HOOKS. Syrupy is a pytest plugin — validating snapshots means
    running tests, which belongs in the test suite, not in a lint-stage quality
    gate. SyrupyAdapter stays available for explicit opt-in use.

    These assertions are inverted ON PURPOSE. An earlier version of this class
    asserted *presence*; when the hook was removed the stale assertion started
    failing, and d85c4ba8 (2026-08-03) resolved it by re-registering the hook
    rather than updating the test — silently reverting the decision under an
    unrelated commit message. Do not re-register syrupy to make a test pass;
    revisit the decision above first.
    """

    def test_syrupy_not_in_comprehensive_hooks(self) -> None:
        from crackerjack.config.hooks import COMPREHENSIVE_HOOKS

        names = [h.name for h in COMPREHENSIVE_HOOKS]
        assert "syrupy" not in names, (
            "syrupy re-registered in COMPREHENSIVE_HOOKS — see 35c7ccb3; "
            "snapshot tests belong in the test suite, not a lint-stage hook"
        )

    def test_syrupy_not_in_fast_hooks(self) -> None:
        from crackerjack.config.hooks import FAST_HOOKS

        names = [h.name for h in FAST_HOOKS]
        assert "syrupy" not in names, (
            "syrupy re-registered in FAST_HOOKS — see 35c7ccb3; snapshot "
            "validation runs pytest and is far too slow for the fast tier"
        )

    def test_syrupy_not_dispatchable_as_native_tool(self) -> None:
        """No dispatch entry should survive the hook removal.

        Guards the second regression layer: ef49d8fe (2026-08-11) added a
        ``syrupy`` tool_commands entry plus a wrapper module on top of the
        already-reverted hook.
        """
        from crackerjack.config.tool_commands import list_available_tools

        assert "syrupy" not in list_available_tools(), (
            "syrupy dispatch entry re-added to tool_commands — see 35c7ccb3"
        )


@pytest.mark.unit
class TestSyrupySettings:
    def test_syrupy_default_update_is_false(self) -> None:
        from crackerjack.adapters.test.syrupy import SyrupySettings

        settings = SyrupySettings(timeout_seconds=300, max_workers=4)
        assert settings.update_snapshots is False

    def test_syrupy_default_extension_is_json(self) -> None:
        from crackerjack.adapters.test.syrupy import SyrupySettings

        settings = SyrupySettings(timeout_seconds=300, max_workers=4)
        assert "json" in settings.extension.lower()


@pytest.mark.unit
class TestSyrupyBuildCommand:
    @pytest.fixture
    async def adapter(self):
        from crackerjack.adapters.test.syrupy import SyrupyAdapter, SyrupySettings

        settings = SyrupySettings(timeout_seconds=300, max_workers=4)
        adapter = SyrupyAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="5.3.2"),
        ):
            await adapter.init()
        return adapter

    async def test_syrupy_build_command_no_update_by_default(self, adapter) -> None:
        """--snapshot-update must NOT appear when update_snapshots is False."""
        cmd = adapter.build_command(files=[])
        assert "--snapshot-update" not in cmd

    async def test_syrupy_build_command_with_update_flag(self, adapter) -> None:
        """--snapshot-update appears when update_snapshots=True."""
        from crackerjack.adapters.test.syrupy import SyrupySettings

        adapter.settings = SyrupySettings(
            timeout_seconds=300, max_workers=4, update_snapshots=True
        )
        cmd = adapter.build_command(files=[])
        assert "--snapshot-update" in cmd

    async def test_syrupy_build_command_uses_pytest(self, adapter) -> None:
        """Command must invoke pytest (syrupy is a plugin)."""
        cmd = adapter.build_command(files=[])
        assert "pytest" in cmd[0] or cmd[0] == "pytest"


@pytest.mark.unit
class TestSyrupyParseOutput:
    @pytest.fixture
    async def adapter(self):
        from crackerjack.adapters.test.syrupy import SyrupyAdapter, SyrupySettings

        settings = SyrupySettings(timeout_seconds=300, max_workers=4)
        adapter = SyrupyAdapter(settings=settings)
        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="5.3.2"),
        ):
            await adapter.init()
        return adapter

    async def test_syrupy_parse_snapshot_failure(self, adapter) -> None:
        """exit_code=1 + snapshot failure text → severity 'error'."""
        result = ToolExecutionResult(
            exit_code=1,
            raw_output=(
                "FAILED tests/test_api.py::test_response_format - "
                "snapshot does not match\n"
                "1 snapshot failed"
            ),
            error_output="",
            execution_time_ms=3.5,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) >= 1
        assert any(i.severity == "error" for i in issues)

    async def test_syrupy_parse_all_pass(self, adapter) -> None:
        """exit_code=0 → empty issues list."""
        result = ToolExecutionResult(
            exit_code=0,
            raw_output="5 passed, 5 snapshots passed in 0.45s",
            error_output="",
            execution_time_ms=0.5,
        )
        issues = await adapter.parse_output(result)
        assert issues == []

    async def test_syrupy_parse_snapshots_written(self, adapter) -> None:
        """Snapshot write/update (exit_code=0) → empty issues (informational only)."""
        result = ToolExecutionResult(
            exit_code=0,
            raw_output="3 snapshots generated",
            error_output="",
            execution_time_ms=1.0,
        )
        issues = await adapter.parse_output(result)
        assert issues == []
