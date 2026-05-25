"""Tests for Semgrep SAST adapter."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult, ToolIssue
from crackerjack.adapters.sast.semgrep import SemgrepAdapter, SemgrepSettings
from crackerjack.models.qa_results import QACheckType


class TestSemgrepAdapter:
    """Test cases for SemgrepAdapter."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """Test basic initialization of SemgrepAdapter."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            adapter = SemgrepAdapter()
            assert adapter.settings is None

            await adapter.init()
            assert adapter.settings is not None
            assert isinstance(adapter.settings, SemgrepSettings)
            assert adapter.tool_name == "semgrep"
            assert adapter.adapter_name == "Semgrep (Security)"

    @pytest.mark.asyncio
    async def test_initialization_with_custom_settings(self) -> None:
        """Test initialization with custom settings."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            settings = SemgrepSettings(
                config="p/security",
                exclude_tests=False,
            )
            adapter = SemgrepAdapter(settings=settings)
            await adapter.init()

            assert adapter.settings.config == "p/security"
            assert adapter.settings.exclude_tests is False

    @pytest.mark.asyncio
    async def test_build_command_basic(self) -> None:
        """Test building a basic semgrep command."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            settings = SemgrepSettings()
            adapter = SemgrepAdapter(settings=settings)
            await adapter.init()

            files = [Path("file1.py"), Path("file2.py")]
            command = adapter.build_command(files)

            assert "semgrep" in command
            assert "scan" in command
            assert "--json" in command
            assert "--config" in command
            assert "p/python" in command
            assert "file1.py" in command
            assert "file2.py" in command

    @pytest.mark.asyncio
    async def test_build_command_custom_config(self) -> None:
        """Test building a semgrep command with custom config."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            settings = SemgrepSettings(config="p/security")
            adapter = SemgrepAdapter(settings=settings)
            await adapter.init()

            files = [Path("file.py")]
            command = adapter.build_command(files)

            assert "--config" in command
            assert "p/security" in command

    @pytest.mark.asyncio
    async def test_build_command_no_json_output(self) -> None:
        """Test building a semgrep command without JSON output."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            settings = SemgrepSettings(use_json_output=False)
            adapter = SemgrepAdapter(settings=settings)
            await adapter.init()

            files = [Path("file.py")]
            command = adapter.build_command(files)

            assert "--json" not in command

    @pytest.mark.asyncio
    async def test_build_command_raises_without_settings(self) -> None:
        """Test build_command raises RuntimeError without settings."""
        adapter = SemgrepAdapter()
        # No init called, settings is None
        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([Path("file.py")])

    @pytest.mark.asyncio
    async def test_parse_json_output(self) -> None:
        """Test parsing valid JSON output from semgrep."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            adapter = SemgrepAdapter()
            await adapter.init()

        json_output = json.dumps({
            "results": [
                {
                    "check_id": "python.lang.security.audit.insecure-hash.insecure-hash",
                    "path": "test.py",
                    "start": {"line": 10, "col": 5},
                    "extra": {
                        "message": "Detected use of insecure hash function MD5",
                        "severity": "WARNING",
                    },
                },
                {
                    "check_id": "python.lang.correctness.useless-eqeq.useless-eqeq",
                    "path": "example.py",
                    "start": {"line": 25, "col": 10},
                    "extra": {
                        "message": "Detected comparison to True using '=='",
                        "severity": "ERROR",
                    },
                },
            ],
            "errors": [],
            "stats": {"warnings": 1, "errors": 1},
        })

        result = ToolExecutionResult(
            success=True,
            raw_output=json_output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) == 2
        assert issues[0].file_path == Path("test.py")
        assert issues[0].line_number == 10
        assert issues[0].code == "python.lang.security.audit.insecure-hash.insecure-hash"
        assert issues[0].severity == "warning"
        assert "insecure hash" in issues[0].message.lower()

        assert issues[1].file_path == Path("example.py")
        assert issues[1].line_number == 25
        assert issues[1].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_json_output_empty(self) -> None:
        """Test parsing empty JSON output."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            adapter = SemgrepAdapter()
            await adapter.init()

        json_output = json.dumps({
            "results": [],
            "errors": [],
        })

        result = ToolExecutionResult(
            success=True,
            raw_output=json_output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )
        issues = await adapter.parse_output(result)

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_json_output_invalid(self) -> None:
        """Test parsing invalid JSON returns empty list."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            adapter = SemgrepAdapter()
            await adapter.init()

        result = ToolExecutionResult(
            success=False,
            raw_output="not valid json",
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=1,
        )
        issues = await adapter.parse_output(result)

        assert issues == []

    @pytest.mark.asyncio
    async def test_parse_json_output_missing_fields(self) -> None:
        """Test parsing JSON with missing optional fields."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            adapter = SemgrepAdapter()
            await adapter.init()

        json_output = json.dumps({
            "results": [
                {
                    "check_id": "test.rule",
                    # Missing path, start, extra
                },
            ],
            "errors": [],
        })

        result = ToolExecutionResult(
            success=True,
            raw_output=json_output,
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )
        issues = await adapter.parse_output(result)

        # Should handle missing fields gracefully
        assert len(issues) == 1
        assert issues[0].file_path == Path("")

    @pytest.mark.asyncio
    async def test_parse_empty_output(self) -> None:
        """Test parsing empty output."""
        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            adapter = SemgrepAdapter()
            await adapter.init()

        result = ToolExecutionResult(
            success=True,
            raw_output="",
            raw_stderr="",
            execution_time_ms=0.0,
            exit_code=0,
        )
        issues = await adapter.parse_output(result)

        assert issues == []

    def test_get_check_type(self) -> None:
        """Test _get_check_type returns SAST."""
        adapter = SemgrepAdapter()
        assert adapter._get_check_type() == QACheckType.SAST

    def test_get_default_config(self) -> None:
        """Test getting default configuration."""
        adapter = SemgrepAdapter()
        config = adapter.get_default_config()

        assert config.check_name == "Semgrep (Security)"
        assert config.check_type == QACheckType.SAST
        assert config.enabled is True
        assert config.file_patterns is not None
        assert config.file_patterns[0].endswith("/**/*.py")
        assert "**/test_*.py" in config.exclude_patterns
        assert config.stage == "comprehensive"
        assert config.timeout_seconds == 1200

    def test_module_id_matches_constant(self) -> None:
        """Test module_id is correct UUID."""
        from crackerjack.adapters.sast.semgrep import MODULE_ID

        adapter = SemgrepAdapter()
        assert adapter.module_id == MODULE_ID

    def test_detect_package_directory(self) -> None:
        """Test _detect_package_directory method."""
        adapter = SemgrepAdapter()
        # Just verify it returns a string
        result = adapter._detect_package_directory()
        assert isinstance(result, str)
        assert len(result) > 0


class TestSemgrepSettings:
    """Test suite for SemgrepSettings."""

    def test_default_settings(self) -> None:
        """Test SemgrepSettings default values."""
        settings = SemgrepSettings()
        assert settings.tool_name == "semgrep"
        assert settings.use_json_output is True
        assert settings.config == "p/python"
        assert settings.exclude_tests is True
        assert settings.timeout_seconds == 1200

    def test_custom_settings(self) -> None:
        """Test SemgrepSettings with custom values."""
        settings = SemgrepSettings(
            config="p/security",
            exclude_tests=False,
            use_json_output=False,
            timeout_seconds=600,
        )
        assert settings.config == "p/security"
        assert settings.exclude_tests is False
        assert settings.use_json_output is False
        assert settings.timeout_seconds == 600

    def test_config_custom(self) -> None:
        """Test config can be set to various rulesets."""
        settings = SemgrepSettings(config="auto")
        assert settings.config == "auto"

        settings2 = SemgrepSettings(config="r/typescript.react.security")
        assert settings2.config == "r/typescript.react.security"


class TestSemgrepAdapterProtocol:
    """Test SASTAdapter protocol compliance."""

    @pytest.mark.asyncio
    async def test_adapter_implements_protocol(self) -> None:
        """Test that SemgrepAdapter implements SASTAdapterProtocol."""
        from crackerjack.adapters.sast._base import SASTAdapterProtocol

        with patch.object(SemgrepAdapter, "validate_tool_available", return_value=True):
            adapter = SemgrepAdapter()
            await adapter.init()

        # Protocol checks
        assert hasattr(adapter, "adapter_name")
        assert hasattr(adapter, "module_id")
        assert hasattr(adapter, "tool_name")
        assert hasattr(adapter, "init")
        assert hasattr(adapter, "build_command")
        assert hasattr(adapter, "check")
        assert hasattr(adapter, "parse_output")
        assert hasattr(adapter, "_get_check_type")
        assert hasattr(adapter, "get_default_config")

    def test_adapter_is_runtime_checkable(self) -> None:
        """Test SASTAdapterProtocol is runtime_checkable."""
        from crackerjack.adapters.sast._base import SASTAdapterProtocol

        assert hasattr(SASTAdapterProtocol, "__protocol_attrs__")


class TestSemgrepSeverityParsing:
    """Test suite for severity parsing."""

    def test_parse_severity_warning(self) -> None:
        """Test severity mapping for WARNING."""
        adapter = SemgrepAdapter()

        json_output = json.dumps({
            "results": [
                {
                    "check_id": "test.rule",
                    "path": "test.py",
                    "start": {"line": 1},
                    "extra": {
                        "message": "Test message",
                        "severity": "WARNING",
                    },
                },
            ],
        })

        result = ToolExecutionResult(raw_output=json_output)

        import asyncio
        issues = asyncio.get_event_loop().run_until_complete(adapter.parse_output(result))

        assert issues[0].severity == "warning"

    def test_parse_severity_error(self) -> None:
        """Test severity mapping for ERROR."""
        adapter = SemgrepAdapter()

        json_output = json.dumps({
            "results": [
                {
                    "check_id": "test.rule",
                    "path": "test.py",
                    "start": {"line": 1},
                    "extra": {
                        "message": "Test message",
                        "severity": "ERROR",
                    },
                },
            ],
        })

        result = ToolExecutionResult(raw_output=json_output)

        import asyncio
        issues = asyncio.get_event_loop().run_until_complete(adapter.parse_output(result))

        assert issues[0].severity == "error"

    def test_parse_severity_unknown(self) -> None:
        """Test severity mapping for unknown severity."""
        adapter = SemgrepAdapter()

        json_output = json.dumps({
            "results": [
                {
                    "check_id": "test.rule",
                    "path": "test.py",
                    "start": {"line": 1},
                    "extra": {
                        "message": "Test message",
                        "severity": "UNKNOWN",
                    },
                },
            ],
        })

        result = ToolExecutionResult(raw_output=json_output)

        import asyncio
        issues = asyncio.get_event_loop().run_until_complete(adapter.parse_output(result))

        # Unknown severity is passed through as-is (lowercased)
        assert issues[0].severity == "unknown"