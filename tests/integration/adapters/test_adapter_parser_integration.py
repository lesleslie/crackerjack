"""Integration tests for adapter-parser workflow."""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from crackerjack.adapters.factory import DefaultAdapterFactory
from crackerjack.adapters._tool_adapter_base import ToolExecutionResult


class TestAdapterFactoryIntegration:
    """Test factory integration with adapters."""

    def test_factory_creates_all_adapters(self):
        """Test that factory can create all registered adapters."""
        factory = DefaultAdapterFactory()

        for tool_name, adapter_name in factory.TOOL_TO_ADAPTER_NAME.items():
            assert factory.tool_has_adapter(tool_name)
            adapter = factory.create_adapter(adapter_name)
            assert adapter is not None
            assert hasattr(adapter, 'adapter_name')

    def test_factory_adapter_settings_flow(self):
        """Test factory passes settings through to adapters."""
        from crackerjack.adapters.format.ruff import RuffSettings

        factory = DefaultAdapterFactory()
        settings = RuffSettings(fix_enabled=True)

        adapter = factory.create_adapter("Ruff", settings=settings)

        assert adapter.settings.fix_enabled is True

    def test_factory_with_ai_agent_environment(self):
        """Test factory respects AI_AGENT environment variable."""
        import os
        from crackerjack.adapters.format.ruff import RuffSettings

        with patch.dict(os.environ, {"AI_AGENT": "1"}):
            factory = DefaultAdapterFactory()
            settings = RuffSettings(fix_enabled=False)

            settings = factory._enable_tool_native_fixes("Ruff", settings)

            assert settings.fix_enabled is True


class TestRuffAdapterIntegration:
    """Integration tests for RuffAdapter."""

    @pytest.mark.asyncio
    async def test_ruff_full_check_workflow(self, tmp_path):
        """Test complete Ruff check workflow."""
        from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings

        # Create test file with issues
        test_file = tmp_path / "test.py"
        test_file.write_text("x=1\ny  =  2\n")  # Has style issues

        settings = RuffSettings(
            mode="check",
            fix_enabled=False,
            use_json_output=True,
        )
        adapter = RuffAdapter(settings=settings)

        # Mock tool availability
        with patch.object(adapter, 'validate_tool_available', return_value=True), \
             patch.object(adapter, 'get_tool_version', return_value="1.0.0"), \
             patch.object(adapter, '_execute_tool') as mock_exec:

            # Mock ruff output
            import json
            mock_output = json.dumps([
                {
                    "filename": str(test_file),
                    "location": {"row": 1, "column": 2},
                    "message": "Missing spaces around operator",
                    "code": "E225",
                }
            ])

            mock_result = ToolExecutionResult(
                raw_output=mock_output,
                exit_code=1,
                success=True,
            )
            mock_exec.return_value = mock_result

            # Run check
            result = await adapter.check([test_file])

            # Verify result
            assert result.check_name == "Ruff (check)"
            assert result.issues_found == 1
            assert len(result.files_checked) == 1


class TestAdapterErrorHandling:
    """Integration tests for adapter error handling."""

    @pytest.mark.asyncio
    async def test_adapter_handles_timeout(self, tmp_path):
        """Test adapter handles tool timeout gracefully."""
        from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings
        import asyncio

        settings = RuffSettings(timeout_seconds=1)
        adapter = RuffAdapter(settings=settings)

        with patch.object(adapter, 'validate_tool_available', return_value=True), \
             patch.object(adapter, 'get_tool_version', return_value="1.0.0"), \
             patch.object(adapter, '_execute_tool', side_effect=asyncio.TimeoutError()):

            result = await adapter.check([tmp_path / "test.py"])

            # Should handle timeout gracefully
            assert result.status.value in ("error", "ERROR")

    @pytest.mark.asyncio
    async def test_adapter_handles_missing_tool(self, tmp_path):
        """Test adapter handles missing tool gracefully."""
        from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings

        settings = RuffSettings()
        adapter = RuffAdapter(settings=settings)

        with patch.object(adapter, 'validate_tool_available', return_value=False):
            with pytest.raises(RuntimeError, match="not found"):
                await adapter.init()


class TestAdapterOutputParsingIntegration:
    """Integration tests for adapter output parsing."""

    @pytest.mark.asyncio
    async def test_ruff_json_to_qa_result(self, tmp_path):
        """Test Ruff JSON output conversion to QA result."""
        from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings
        import json

        test_file = tmp_path / "test.py"
        test_file.write_text("x=1\n")

        settings = RuffSettings(mode="check", use_json_output=True)
        adapter = RuffAdapter(settings=settings)

        # Mock output
        json_output = json.dumps([
            {
                "filename": str(test_file),
                "location": {"row": 1, "column": 1},
                "message": "E225: Missing whitespace around operator",
                "code": "E225",
            }
        ])

        result = ToolExecutionResult(raw_output=json_output)
        issues = await adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].code == "E225"
        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_bandit_json_to_qa_result(self):
        """Test Bandit JSON output conversion to QA result."""
        from crackerjack.adapters.sast.bandit import BanditAdapter, BanditSettings
        import json

        settings = BanditSettings(use_json_output=True)
        adapter = BanditAdapter(settings=settings)
        await adapter.init()

        json_output = json.dumps({
            "results": [
                {
                    "filename": "test.py",
                    "line_number": 10,
                    "issue_text": "Use of exec detected",
                    "test_id": "B102",
                    "issue_severity": "HIGH",
                    "issue_confidence": "MEDIUM",
                }
            ]
        })

        result = ToolExecutionResult(raw_output=json_output)
        issues = await adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].code == "B102"
        assert issues[0].severity == "error"


class TestMultiAdapterWorkflow:
    """Integration tests for multi-adapter workflows."""

    @pytest.mark.asyncio
    async def test_sequential_adapter_execution(self, tmp_path):
        """Test running multiple adapters sequentially."""
        from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings
        from crackerjack.adapters.sast.bandit import BanditAdapter, BanditSettings

        test_file = tmp_path / "test.py"
        test_file.write_text("x=1\n")

        # Ruff check
        ruff_settings = RuffSettings(mode="check")
        ruff = RuffAdapter(settings=ruff_settings)

        with patch.object(ruff, 'validate_tool_available', return_value=True), \
             patch.object(ruff, 'get_tool_version', return_value="1.0.0"), \
             patch.object(ruff, '_execute_tool') as mock_exec:
            mock_exec.return_value = ToolExecutionResult(raw_output="[]")
            ruff_result = await ruff.check([test_file])

        # Bandit check
        bandit_settings = BanditSettings()
        bandit = BanditAdapter(settings=bandit_settings)

        with patch.object(bandit, 'validate_tool_available', return_value=True), \
             patch.object(bandit, 'get_tool_version', return_value="1.7.0"), \
             patch.object(bandit, '_execute_tool') as mock_exec:
            mock_exec.return_value = ToolExecutionResult(
                raw_output='{"results": []}',
            )
            bandit_result = await bandit.check([test_file])

        # Both should complete
        assert ruff_result.check_name == "Ruff (check)"
        assert bandit_result.check_name == "Bandit (Security)"
