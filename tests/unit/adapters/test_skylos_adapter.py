"""Tests for SkylosAdapter."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from crackerjack.adapters.refactor.skylos import (
    SkylosAdapter,
    SkylosSettings,
)
from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.models.qa_results import QACheckType


@pytest.fixture
def skylos_settings():
    """Provide SkylosSettings for testing."""
    return SkylosSettings(
        timeout_seconds=300,
        max_workers=4,
        use_json_output=True,
        confidence_threshold=86,
        web_dashboard_port=5090,
    )


@pytest.fixture
async def skylos_adapter(skylos_settings):
    """Provide initialized SkylosAdapter for testing."""
    adapter = SkylosAdapter(settings=skylos_settings)
    with patch.object(adapter, 'validate_tool_available', return_value=True), \
         patch.object(adapter, 'get_tool_version', return_value="1.0.0"):
        await adapter.init()
    return adapter


class TestSkylosSettings:
    """Test suite for SkylosSettings."""

    def test_default_settings(self):
        """Test SkylosSettings default values."""
        settings = SkylosSettings()
        assert settings.tool_name == "skylos"
        assert settings.use_json_output is True
        assert settings.confidence_threshold == 86
        assert settings.web_dashboard_port == 5090


class TestSkylosAdapterProperties:
    """Test suite for SkylosAdapter properties."""

    def test_adapter_name(self, skylos_adapter):
        """Test adapter_name property."""
        assert skylos_adapter.adapter_name == "Skylos (Dead Code)"

    def test_module_id(self, skylos_adapter):
        """Test module_id is correct UUID."""
        from crackerjack.adapters.refactor.skylos import MODULE_ID
        assert skylos_adapter.module_id == MODULE_ID

    def test_tool_name(self, skylos_adapter):
        """Test tool_name property."""
        assert skylos_adapter.tool_name == "skylos"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self, skylos_adapter, tmp_path):
        """Test building basic command."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        cmd = skylos_adapter.build_command([test_file])

        assert "uv" in cmd
        assert "run" in cmd
        assert "skylos" in cmd
        assert "--confidence" in cmd
        assert "86" in cmd
        assert "--json" in cmd
        assert "--exclude-folder" in cmd
        assert "tests" in cmd
        assert str(test_file) in cmd

    def test_build_command_with_custom_confidence(self, tmp_path):
        """Test command with custom confidence threshold."""
        settings = SkylosSettings(confidence_threshold=90)
        adapter = SkylosAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        conf_idx = cmd.index("--confidence")
        assert cmd[conf_idx + 1] == "90"

    def test_build_command_with_file_filter(self, tmp_path):
        """Test command with file filter."""
        mock_filter = MagicMock()
        mock_filter.get_files_for_qa_scan.return_value = [tmp_path / "test.py"]

        settings = SkylosSettings()
        adapter = SkylosAdapter(settings=settings, file_filter=mock_filter)
        adapter.settings = settings

        cmd = adapter.build_command(None)

        assert str(tmp_path / "test.py") in cmd

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = SkylosAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_json_output(self, skylos_adapter):
        """Test parsing JSON output."""
        json_output = json.dumps({
            "dead_code": [
                {
                    "file": "test.py",
                    "line": 10,
                    "type": "function",
                    "name": "unused_func",
                    "confidence": "95%",
                }
            ]
        })

        result = ToolExecutionResult(raw_output=json_output)
        issues = await skylos_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10
        assert "Dead function" in issues[0].message
        assert "unused_func" in issues[0].message
        assert issues[0].code == "function"
        assert issues[0].severity == "warning"
        assert "95%" in issues[0].suggestion

    @pytest.mark.asyncio
    async def test_parse_json_multiple_issues(self, skylos_adapter):
        """Test parsing multiple issues from JSON."""
        json_output = json.dumps({
            "dead_code": [
                {
                    "file": "test1.py",
                    "line": 10,
                    "type": "function",
                    "name": "func1",
                    "confidence": "90%",
                },
                {
                    "file": "test2.py",
                    "line": 20,
                    "type": "class",
                    "name": "Class1",
                    "confidence": "85%",
                },
            ]
        })

        result = ToolExecutionResult(raw_output=json_output)
        issues = await skylos_adapter.parse_output(result)

        assert len(issues) == 2
        assert "function" in issues[0].message
        assert "class" in issues[1].message

    @pytest.mark.asyncio
    async def test_parse_json_empty_results(self, skylos_adapter):
        """Test parsing empty JSON."""
        json_output = json.dumps({"dead_code": []})

        result = ToolExecutionResult(raw_output=json_output)
        issues = await skylos_adapter.parse_output(result)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_text_output_fallback(self, skylos_adapter):
        """Test text output parsing when JSON fails."""
        text_output = "test.py:10: Dead function: unused_func (confidence: 95%)\n"

        result = ToolExecutionResult(raw_output=text_output)
        issues = await skylos_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10

    @pytest.mark.asyncio
    async def test_parse_empty_output(self, skylos_adapter):
        """Test parsing empty output."""
        result = ToolExecutionResult(raw_output="")
        issues = await skylos_adapter.parse_output(result)
        assert len(issues) == 0


class TestDetectPackageName:
    """Test suite for package name detection."""

    def test_read_package_from_toml(self, tmp_path):
        """Test reading package name from pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-package"\n')

        package_dir = tmp_path / "test_package"
        package_dir.mkdir()

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            adapter = SkylosAdapter()
            result = adapter._read_package_from_toml(tmp_path)
            assert result == "test_package"
        finally:
            os.chdir(original_cwd)

    def test_find_package_directory(self, tmp_path):
        """Test finding package directory."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            adapter = SkylosAdapter()
            result = adapter._find_package_directory(tmp_path)
            assert result == "mypackage"
        finally:
            os.chdir(original_cwd)


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self, skylos_adapter):
        """Test default configuration."""
        config = skylos_adapter.get_default_config()

        assert config.check_name == "Skylos (Dead Code)"
        assert config.check_type == QACheckType.REFACTOR
        assert config.enabled is True
        assert config.stage == "comprehensive"
        assert "test_" in config.exclude_patterns


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self, skylos_adapter):
        """Test check type is REFACTOR."""
        assert skylos_adapter._get_check_type() == QACheckType.REFACTOR
