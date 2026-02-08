"""Tests for RefurbAdapter."""

import pytest
from pathlib import Path
from unittest.mock import patch

from crackerjack.adapters.refactor.refurb import (
    RefurbAdapter,
    RefurbSettings,
)
from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.models.qa_results import QACheckType


@pytest.fixture
def refurb_settings():
    """Provide RefurbSettings for testing."""
    return RefurbSettings(
        timeout_seconds=240,
        max_workers=4,
        use_json_output=False,
        enable_all=False,
        disable_checks=[],
        enable_checks=[],
        python_version=None,
        explain=False,
    )


@pytest.fixture
async def refurb_adapter(refurb_settings):
    """Provide initialized RefurbAdapter for testing."""
    adapter = RefurbAdapter(settings=refurb_settings)
    with patch.object(adapter, 'validate_tool_available', return_value=True), \
         patch.object(adapter, 'get_tool_version', return_value="1.0.0"):
        await adapter.init()
    return adapter


class TestRefurbSettings:
    """Test suite for RefurbSettings."""

    def test_default_settings(self):
        """Test RefurbSettings default values."""
        settings = RefurbSettings()
        assert settings.tool_name == "refurb"
        assert settings.use_json_output is False
        assert settings.enable_all is False
        assert settings.disable_checks == []
        assert settings.enable_checks == []
        assert settings.python_version is None
        assert settings.explain is False


class TestRefurbAdapterProperties:
    """Test suite for RefurbAdapter properties."""

    def test_adapter_name(self, refurb_adapter):
        """Test adapter_name property."""
        assert refurb_adapter.adapter_name == "Refurb (Refactoring)"

    def test_module_id(self, refurb_adapter):
        """Test module_id is correct UUID."""
        from crackerjack.adapters.refactor.refurb import MODULE_ID
        assert refurb_adapter.module_id == MODULE_ID

    def test_tool_name(self, refurb_adapter):
        """Test tool_name property."""
        assert refurb_adapter.tool_name == "refurb"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self, refurb_adapter, tmp_path):
        """Test building basic command."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        cmd = refurb_adapter.build_command([test_file])

        assert "refurb" in cmd
        assert str(test_file) in cmd

    def test_build_command_enable_all(self, tmp_path):
        """Test command with enable all."""
        settings = RefurbSettings(enable_all=True)
        adapter = RefurbAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--enable-all" in cmd

    def test_build_command_with_disable_checks(self, tmp_path):
        """Test command with disabled checks."""
        settings = RefurbSettings(disable_checks=["FURB101", "FURB102"])
        adapter = RefurbAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--ignore" in cmd
        assert "FURB101" in cmd

    def test_build_command_with_enable_checks(self, tmp_path):
        """Test command with enabled checks."""
        settings = RefurbSettings(enable_checks=["FURB103"])
        adapter = RefurbAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--enable" in cmd
        assert "FURB103" in cmd

    def test_build_command_with_python_version(self, tmp_path):
        """Test command with Python version."""
        settings = RefurbSettings(python_version="3.12")
        adapter = RefurbAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--python-version" in cmd
        assert "3.12" in cmd

    def test_build_command_with_explain(self, tmp_path):
        """Test command with explain flag."""
        settings = RefurbSettings(explain=True)
        adapter = RefurbAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--explain" in cmd

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = RefurbAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_text_output(self, refurb_adapter):
        """Test parsing text output."""
        text_output = "test.py:10:5: [FURB101] Use isinstance instead of type\n"

        result = ToolExecutionResult(raw_output=text_output)
        issues = await refurb_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10
        assert issues[0].column_number == 5
        assert "isinstance" in issues[0].message
        assert issues[0].code == "FURB101"
        assert issues[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_parse_output_without_column(self, refurb_adapter):
        """Test parsing output without column number."""
        text_output = "test.py:10: [FURB101] Use isinstance\n"

        result = ToolExecutionResult(raw_output=text_output)
        issues = await refurb_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].line_number == 10
        assert issues[0].column_number is None

    @pytest.mark.asyncio
    async def test_parse_empty_output(self, refurb_adapter):
        """Test parsing empty output."""
        result = ToolExecutionResult(raw_output="")
        issues = await refurb_adapter.parse_output(result)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_output_without_furb_code(self, refurb_adapter):
        """Test that lines without [FURB are skipped."""
        text_output = "test.py:10: Some other output\n"

        result = ToolExecutionResult(raw_output=text_output)
        issues = await refurb_adapter.parse_output(result)

        assert len(issues) == 0


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self, refurb_adapter):
        """Test default configuration."""
        config = refurb_adapter.get_default_config()

        assert config.check_name == "Refurb (Refactoring)"
        assert config.check_type == QACheckType.REFACTOR
        assert config.enabled is True
        assert config.stage == "comprehensive"
        assert "test_" in config.exclude_patterns


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self, refurb_adapter):
        """Test check type is REFACTOR."""
        assert refurb_adapter._get_check_type() == QACheckType.REFACTOR
