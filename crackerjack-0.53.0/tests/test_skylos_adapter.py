"""Tests for SkylosAdapter - dead code detection."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, mock_open, patch
from uuid import UUID

import pytest

from crackerjack.adapters._tool_adapter_base import BaseToolAdapter
from crackerjack.adapters.refactor.skylos import SkylosAdapter, SkylosSettings
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QACheckType


class TestSkylosAdapter:
    """Tests for SkylosAdapter."""

    def test_skylos_adapter_initialization(self) -> None:
        """Test SkylosAdapter initialization with settings."""
        settings = SkylosSettings(confidence_threshold=90, web_dashboard_port=5091)
        adapter = SkylosAdapter(settings=settings)

        assert adapter.settings.confidence_threshold == 90
        assert adapter.settings.web_dashboard_port == 5091
        assert isinstance(adapter.adapter_name, str)
        assert isinstance(adapter.module_id, UUID)

    def test_skylos_adapter_default_settings(self) -> None:
        """Test SkylosAdapter with default settings."""
        adapter = SkylosAdapter()
        assert adapter.settings is None

    def test_skylos_adapter_extends_base_tool(self) -> None:
        """Test SkylosAdapter extends BaseToolAdapter."""
        adapter = SkylosAdapter()
        assert isinstance(adapter, BaseToolAdapter)

    def test_skylos_adapter_name(self) -> None:
        """Test SkylosAdapter adapter_name property."""
        adapter = SkylosAdapter()
        assert adapter.adapter_name == "Skylos (Dead Code)"

    def test_skylos_adapter_module_id(self) -> None:
        """Test SkylosAdapter module_id property."""
        adapter = SkylosAdapter()
        expected_id = UUID("445401b8-b273-47f1-9015-22e721757d46")
        assert adapter.module_id == expected_id

    def test_skylos_adapter_tool_name(self) -> None:
        """Test SkylosAdapter tool_name property."""
        adapter = SkylosAdapter()
        assert adapter.tool_name == "skylos"

    @pytest.mark.asyncio
    async def test_skylos_adapter_init(self) -> None:
        """Test SkylosAdapter init method."""
        adapter = SkylosAdapter()

        # Mock the parent init and timeout method
        with patch.object(adapter, "_get_timeout_from_settings", return_value=300):
            await adapter.init()

        assert adapter.settings is not None
        assert adapter.settings.confidence_threshold == 86  # Default value
        assert adapter.settings.timeout_seconds == 300

    def test_skylos_adapter_build_command(self) -> None:
        """Test SkylosAdapter build_command method."""
        settings = SkylosSettings(confidence_threshold=85, use_json_output=True)
        adapter = SkylosAdapter(settings=settings)

        files = [Path("test.py"), Path("main.py")]
        command = adapter.build_command(files)

        assert "uv" in command
        assert "run" in command
        assert "skylos" in command
        assert "--confidence" in command
        assert "85" in command
        assert "--json" in command
        assert "test.py" in command
        assert "main.py" in command

    def test_skylos_adapter_build_command_no_files(self) -> None:
        """Test SkylosAdapter build_command with no files."""
        settings = SkylosSettings()
        adapter = SkylosAdapter(settings=settings)

        # Mock the package detection methods
        with patch.object(adapter, "_detect_package_name", return_value="test_package"):
            command = adapter.build_command([])

        assert "./test_package" in command

    def test_skylos_adapter_detect_package_name(self) -> None:
        """Test SkylosAdapter package name detection."""
        adapter = SkylosAdapter()

        # Test with pyproject.toml
        mock_file_data = b'{"project": {"name": "test-package"}}'
        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.read = Mock(return_value=mock_file_data)

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.open", return_value=mock_file), \
             patch("tomllib.load") as mock_toml:

            mock_toml.return_value = {"project": {"name": "test-package"}}
            result = adapter._read_package_from_toml(Path("/test"))
            assert result == "test_package"

        # Test fallback to directory search
        with patch("pathlib.Path.iterdir") as mock_iterdir:
            from unittest.mock import MagicMock
            mock_dir = MagicMock(spec=Path)
            mock_dir.name = "test_package"
            mock_dir.is_dir.return_value = True
            mock_init = MagicMock()
            mock_init.exists.return_value = True
            type(mock_dir).__truediv__ = Mock(return_value=mock_init)
            mock_iterdir.return_value = [mock_dir]

            result = adapter._find_package_directory(Path("/test"))
            assert result == "test_package"

    def test_skylos_adapter_get_default_config(self) -> None:
        """Test SkylosAdapter get_default_config method."""
        adapter = SkylosAdapter()

        # Mock package detection
        with patch.object(adapter, "_detect_package_directory", return_value="test_package"):
            config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.REFACTOR
        assert config.enabled is True
        assert any("test_package" in pattern for pattern in config.file_patterns)
        assert config.stage == "comprehensive"
        assert config.timeout_seconds == 300

    @pytest.mark.asyncio
    async def test_skylos_adapter_parse_json_output(self) -> None:
        """Test SkylosAdapter JSON output parsing."""
        adapter = SkylosAdapter()

        # Mock execution result
        mock_result = Mock()
        mock_result.raw_output = '{"dead_code": [{"file": "test.py", "line": 10, "type": "function", "name": "unused_func", "confidence": 95}]}'

        issues = await adapter.parse_output(mock_result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10
        assert "Dead function: unused_func" in issues[0].message
        assert issues[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_skylos_adapter_parse_text_output(self) -> None:
        """Test SkylosAdapter text output parsing."""
        adapter = SkylosAdapter()

        # Mock execution result with text output
        mock_result = Mock()
        mock_result.raw_output = "test.py:15: Unused variable: old_var (confidence: 88%)"

        issues = await adapter.parse_output(mock_result)

        assert len(issues) == 1
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 15
        assert "Unused variable: old_var" in issues[0].message

    @pytest.mark.asyncio
    async def test_skylos_adapter_parse_empty_output(self) -> None:
        """Test SkylosAdapter with empty output."""
        adapter = SkylosAdapter()

        mock_result = Mock()
        mock_result.raw_output = ""

        issues = await adapter.parse_output(mock_result)
        assert len(issues) == 0

    def test_skylos_adapter_check_type(self) -> None:
        """Test SkylosAdapter check type."""
        adapter = SkylosAdapter()
        check_type = adapter._get_check_type()
        assert check_type == QACheckType.REFACTOR

    def test_skylos_adapter_settings_validation(self) -> None:
        """Test SkylosAdapter settings validation."""
        # Test valid settings
        settings = SkylosSettings(confidence_threshold=80)
        assert settings.confidence_threshold == 80
        assert settings.use_json_output is True
        assert settings.web_dashboard_port == 5090

        # Test custom settings
        custom_settings = SkylosSettings(
            confidence_threshold=95,
            use_json_output=False,
            web_dashboard_port=8080,
        )
        assert custom_settings.confidence_threshold == 95
        assert custom_settings.use_json_output is False
        assert custom_settings.web_dashboard_port == 8080


def mock_open(read_data=None):
    """Mock open function for testing."""
    mock_file = Mock()
    mock_file.__enter__ = Mock(return_value=Mock(read=Mock(return_value=read_data)))
    mock_file.__exit__ = Mock(return_value=False)
    return mock_file
