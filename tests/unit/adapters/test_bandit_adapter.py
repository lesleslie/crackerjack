"""Tests for BanditAdapter."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from crackerjack.adapters.sast.bandit import (
    BanditAdapter,
    BanditSettings,
)
from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.models.qa_results import QACheckType


@pytest.fixture
def bandit_settings():
    """Provide BanditSettings for testing."""
    return BanditSettings(
        timeout_seconds=1200,
        max_workers=4,
        use_json_output=True,
        severity_level="low",
        confidence_level="low",
        exclude_tests=True,
        skip_rules=[],
        tests_to_run=[],
        recursive=True,
    )


@pytest.fixture
async def bandit_adapter(bandit_settings):
    """Provide initialized BanditAdapter for testing."""
    adapter = BanditAdapter(settings=bandit_settings)
    with patch.object(adapter, 'validate_tool_available', return_value=True), \
         patch.object(adapter, 'get_tool_version', return_value="1.7.0"):
        await adapter.init()
    return adapter


@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file for testing."""
    test_file = tmp_path / "test.py"
    test_file.write_text("import os\nexec(input())\n")
    return test_file


class TestBanditSettings:
    """Test suite for BanditSettings."""

    def test_default_settings(self):
        """Test BanditSettings default values."""
        settings = BanditSettings()
        assert settings.tool_name == "bandit"
        assert settings.use_json_output is True
        assert settings.severity_level == "low"
        assert settings.confidence_level == "low"
        assert settings.exclude_tests is True
        assert settings.recursive is True
        assert settings.timeout_seconds == 1200


class TestBanditAdapterProperties:
    """Test suite for BanditAdapter properties."""

    def test_adapter_name(self, bandit_adapter):
        """Test adapter_name property."""
        assert bandit_adapter.adapter_name == "Bandit (Security)"

    def test_module_id(self, bandit_adapter):
        """Test module_id is correct UUID."""
        from crackerjack.adapters.sast.bandit import MODULE_ID
        assert bandit_adapter.module_id == MODULE_ID

    def test_tool_name(self, bandit_adapter):
        """Test tool_name property."""
        assert bandit_adapter.tool_name == "bandit"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self, bandit_adapter, sample_python_file):
        """Test building basic command."""
        cmd = bandit_adapter.build_command([sample_python_file])

        assert "bandit" in cmd
        assert "-r" in cmd
        assert "-f" in cmd
        assert "json" in cmd
        assert str(sample_python_file) in cmd

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = BanditAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_json_output(self, bandit_adapter):
        """Test parsing JSON output."""
        json_output = json.dumps({
            "results": [
                {
                    "filename": "test.py",
                    "line_number": 10,
                    "issue_text": "Use of exec detected",
                    "test_id": "B102",
                    "issue_severity": "HIGH",
                    "issue_confidence": "MEDIUM",
                    "more_info": "https://bandit.readthedocs.io/",
                }
            ]
        })

        result = ToolExecutionResult(raw_output=json_output)
        issues = await bandit_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10
        assert issues[0].code == "B102"
        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_json_empty_results(self, bandit_adapter):
        """Test parsing JSON with no results."""
        json_output = json.dumps({"results": []})

        result = ToolExecutionResult(raw_output=json_output)
        issues = await bandit_adapter.parse_output(result)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_empty_output(self, bandit_adapter):
        """Test parsing empty output."""
        result = ToolExecutionResult(raw_output="")
        issues = await bandit_adapter.parse_output(result)
        assert len(issues) == 0


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self, bandit_adapter):
        """Test default configuration."""
        config = bandit_adapter.get_default_config()

        assert config.check_name == "Bandit (Security)"
        assert config.check_type == QACheckType.SAST
        assert config.enabled is True
        assert config.stage == "comprehensive"


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self, bandit_adapter):
        """Test check type is SAST."""
        assert bandit_adapter._get_check_type() == QACheckType.SAST
