"""Tests for SemgrepAdapter."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from crackerjack.adapters.sast.semgrep import (
    SemgrepAdapter,
    SemgrepSettings,
)
from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.models.qa_results import QACheckType


@pytest.fixture
def semgrep_settings():
    """Provide SemgrepSettings for testing."""
    return SemgrepSettings(
        timeout_seconds=1200,
        max_workers=4,
        use_json_output=True,
        config="p/python",
        exclude_tests=True,
    )


@pytest.fixture
async def semgrep_adapter(semgrep_settings):
    """Provide initialized SemgrepAdapter for testing."""
    adapter = SemgrepAdapter(settings=semgrep_settings)
    with patch.object(adapter, 'validate_tool_available', return_value=True), \
         patch.object(adapter, 'get_tool_version', return_value="1.0.0"):
        await adapter.init()
    return adapter


class TestSemgrepSettings:
    """Test suite for SemgrepSettings."""

    def test_default_settings(self):
        """Test SemgrepSettings default values."""
        settings = SemgrepSettings()
        assert settings.tool_name == "semgrep"
        assert settings.use_json_output is True
        assert settings.config == "p/python"
        assert settings.exclude_tests is True
        assert settings.timeout_seconds == 1200


class TestSemgrepAdapterProperties:
    """Test suite for SemgrepAdapter properties."""

    def test_adapter_name(self, semgrep_adapter):
        """Test adapter_name property."""
        assert semgrep_adapter.adapter_name == "Semgrep (Security)"

    def test_module_id(self, semgrep_adapter):
        """Test module_id is correct UUID."""
        from crackerjack.adapters.sast.semgrep import MODULE_ID
        assert semgrep_adapter.module_id == MODULE_ID

    def test_tool_name(self, semgrep_adapter):
        """Test tool_name property."""
        assert semgrep_adapter.tool_name == "semgrep"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self, semgrep_adapter, tmp_path):
        """Test building basic command."""
        test_file = tmp_path / "test.py"
        test_file.write_text("pass\n")

        cmd = semgrep_adapter.build_command([test_file])

        assert "semgrep" in cmd
        assert "scan" in cmd
        assert "--json" in cmd
        assert "--config" in cmd
        assert "p/python" in cmd
        assert str(test_file) in cmd

    def test_build_command_with_custom_config(self, tmp_path):
        """Test command with custom config."""
        settings = SemgrepSettings(config="auto")
        adapter = SemgrepAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        config_idx = cmd.index("--config")
        assert cmd[config_idx + 1] == "auto"

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = SemgrepAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_json_output(self, semgrep_adapter):
        """Test parsing JSON output."""
        json_output = json.dumps({
            "results": [
                {
                    "path": "test.py",
                    "start": {"line": 10},
                    "extra": {
                        "message": "Dangerous function",
                        "severity": "ERROR",
                    },
                    "check_id": "python.dangerous.function",
                }
            ]
        })

        result = ToolExecutionResult(raw_output=json_output)
        issues = await semgrep_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10
        assert issues[0].message == "Dangerous function"
        assert issues[0].code == "python.dangerous.function"
        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_json_multiple_issues(self, semgrep_adapter):
        """Test parsing multiple issues."""
        json_output = json.dumps({
            "results": [
                {
                    "path": "test1.py",
                    "start": {"line": 10},
                    "extra": {"message": "Issue 1", "severity": "ERROR"},
                    "check_id": "check1",
                },
                {
                    "path": "test2.py",
                    "start": {"line": 20},
                    "extra": {"message": "Issue 2", "severity": "WARNING"},
                    "check_id": "check2",
                },
            ]
        })

        result = ToolExecutionResult(raw_output=json_output)
        issues = await semgrep_adapter.parse_output(result)

        assert len(issues) == 2

    @pytest.mark.asyncio
    async def test_parse_json_empty_results(self, semgrep_adapter):
        """Test parsing empty JSON."""
        json_output = json.dumps({"results": []})

        result = ToolExecutionResult(raw_output=json_output)
        issues = await semgrep_adapter.parse_output(result)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_invalid_json_returns_empty(self, semgrep_adapter):
        """Test that invalid JSON returns empty list."""
        result = ToolExecutionResult(raw_output="invalid json")
        issues = await semgrep_adapter.parse_output(result)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_empty_output(self, semgrep_adapter):
        """Test parsing empty output."""
        result = ToolExecutionResult(raw_output="")
        issues = await semgrep_adapter.parse_output(result)
        assert len(issues) == 0


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self, semgrep_adapter):
        """Test default configuration."""
        config = semgrep_adapter.get_default_config()

        assert config.check_name == "Semgrep (Security)"
        assert config.check_type == QACheckType.SAST
        assert config.enabled is True
        assert config.stage == "comprehensive"
        assert "test_" in config.exclude_patterns


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self, semgrep_adapter):
        """Test check type is SAST."""
        assert semgrep_adapter._get_check_type() == QACheckType.SAST
