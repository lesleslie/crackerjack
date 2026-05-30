"""Tests for ScaleneAdapter (performance profiling adapter)."""

import json
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.performance.scalene import (
    MODULE_ID,
    ScaleneAdapter,
    ScaleneSettings,
    ProfileHotspot,
)
from crackerjack.models.qa_results import QACheckType


@pytest.fixture
def scalene_settings():
    """Provide ScaleneSettings for testing."""
    return ScaleneSettings(
        timeout_seconds=300,
        max_workers=1,
        cpu_percent_threshold=5.0,
        memory_threshold_mb=10.0,
        copy_threshold_mb=50.0,
        profile_cpu=True,
        profile_memory=True,
        profile_gpu=False,
        detect_leaks=True,
        reduced_profile=True,
        profile_all=False,
    )


@pytest.fixture
async def scalene_adapter(scalene_settings):
    """Provide initialized ScaleneAdapter for testing."""
    adapter = ScaleneAdapter(settings=scalene_settings)

    with (
        patch.object(adapter, "validate_tool_available", return_value=True),
        patch.object(adapter, "get_tool_version", return_value="24.5.0"),
    ):
        await adapter.init()
    return adapter


class TestScaleneSettings:
    """Test suite for ScaleneSettings."""

    def test_default_settings(self):
        """Test ScaleneSettings default values."""
        settings = ScaleneSettings()
        assert settings.tool_name == "scalene"
        assert settings.use_json_output is True
        assert settings.cpu_percent_threshold == 5.0
        assert settings.memory_threshold_mb == 10.0
        assert settings.copy_threshold_mb == 50.0
        assert settings.profile_cpu is True
        assert settings.profile_memory is True
        assert settings.profile_gpu is False
        assert settings.detect_leaks is True
        assert settings.reduced_profile is True
        assert settings.profile_all is False

    def test_custom_settings(self):
        """Test ScaleneSettings with custom values."""
        settings = ScaleneSettings(
            cpu_percent_threshold=10.0,
            memory_threshold_mb=20.0,
            copy_threshold_mb=100.0,
            profile_gpu=True,
        )
        assert settings.cpu_percent_threshold == 10.0
        assert settings.memory_threshold_mb == 20.0
        assert settings.copy_threshold_mb == 100.0
        assert settings.profile_gpu is True


class TestScaleneAdapterProperties:
    """Test suite for ScaleneAdapter properties."""

    def test_adapter_name(self, scalene_adapter):
        """Test adapter_name property."""
        assert scalene_adapter.adapter_name == "scalene"

    def test_module_id(self, scalene_adapter):
        """Test module_id is correct UUID."""
        assert scalene_adapter.module_id == MODULE_ID

    def test_tool_name(self, scalene_adapter):
        """Test tool_name property."""
        assert scalene_adapter.tool_name == "scalene"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self, scalene_adapter, tmp_path):
        """Test building basic scalene command."""
        test_file = tmp_path / "test_perf.py"
        test_file.write_text("def test_x(): pass\n")

        cmd = scalene_adapter.build_command([test_file])

        assert "scalene" in cmd
        assert "--cli" in cmd
        assert "--json" in cmd
        assert "--cpu" in cmd
        assert "--memory" in cmd
        assert "--reduced-profile" in cmd

    def test_build_command_with_cpu_only(self, tmp_path):
        """Test command with CPU profiling only."""
        settings = ScaleneSettings(profile_cpu=True, profile_memory=False)
        adapter = ScaleneAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--cpu" in cmd
        assert "--memory" not in cmd

    def test_build_command_with_gpu(self, tmp_path):
        """Test command with GPU profiling enabled."""
        settings = ScaleneSettings(profile_gpu=True)
        adapter = ScaleneAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--gpu" in cmd

    def test_build_command_for_test_file(self, tmp_path):
        """Test command for test file uses pytest."""
        test_file = tmp_path / "test_perf.py"
        test_file.write_text("def test_x(): pass\n")

        adapter = ScaleneAdapter()
        adapter.settings = ScaleneSettings()
        cmd = adapter.build_command([test_file])

        assert "pytest" in cmd

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = ScaleneAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestDetectTestFile:
    """Test suite for _detect_test_file method."""

    def test_detects_test_prefix(self, scalene_adapter):
        """Test detecting files with test_ prefix."""
        files = [Path("test_foo.py")]
        assert scalene_adapter._detect_test_file(files) is True

    def test_detects_test_suffix(self, scalene_adapter):
        """Test detecting files with _test.py suffix."""
        files = [Path("foo_test.py")]
        assert scalene_adapter._detect_test_file(files) is True

    def test_rejects_regular_file(self, scalene_adapter):
        """Test rejecting regular Python files."""
        files = [Path("foo.py")]
        assert scalene_adapter._detect_test_file(files) is False

    def test_empty_list(self, scalene_adapter):
        """Test empty file list returns False."""
        assert scalene_adapter._detect_test_file([]) is False


class TestExtractJson:
    """Test suite for _extract_json method."""

    def test_extracts_json_from_mixed_output(self, scalene_adapter):
        """Test extracting JSON from mixed output."""
        output = """some text output
{"files": [], "summary": "test"}
more text
"""
        result = scalene_adapter._extract_json(output)
        assert result is not None
        assert '"files"' in result
        assert "summary" in result

    def test_returns_none_for_plain_text(self, scalene_adapter):
        """Test returns None when no JSON found."""
        output = "just plain text output"
        result = scalene_adapter._extract_json(output)
        assert result is None

    def test_returns_none_for_empty_output(self, scalene_adapter):
        """Test returns None for empty output."""
        result = scalene_adapter._extract_json("")
        assert result is None


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_valid_json_output(self, scalene_adapter):
        """Test parsing valid JSON output."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "test.py",
                    "lines": {
                        "10": {
                            "cpu_percent": 25.0,
                            "cpu_python": 20.0,
                            "cpu_c": 5.0,
                            "mem_mb": 5.0,
                            "copy_mb": 0.0,
                            "net_memory": 0.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should find CPU hotspot
        cpu_issues = [i for i in issues if i.code == "SC001"]
        assert len(cpu_issues) == 1
        assert "25.0%" in cpu_issues[0].message

    @pytest.mark.asyncio
    async def test_parse_memory_hotspot(self, scalene_adapter):
        """Test detecting memory hotspot."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "test.py",
                    "lines": {
                        "15": {
                            "cpu_percent": 1.0,
                            "cpu_python": 1.0,
                            "cpu_c": 0.0,
                            "mem_mb": 50.0,
                            "copy_mb": 0.0,
                            "net_memory": 0.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should find memory hotspot
        mem_issues = [i for i in issues if i.code == "SC002"]
        assert len(mem_issues) == 1
        assert "50.0 MB" in mem_issues[0].message

    @pytest.mark.asyncio
    async def test_parse_memory_leak(self, scalene_adapter):
        """Test detecting potential memory leak."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "test.py",
                    "lines": {
                        "20": {
                            "cpu_percent": 10.0,
                            "cpu_python": 10.0,
                            "cpu_c": 0.0,
                            "mem_mb": 100.0,
                            "copy_mb": 0.0,
                            "net_memory": -50.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should find memory leak issue
        leak_issues = [i for i in issues if i.code == "SC003"]
        assert len(leak_issues) == 1

    @pytest.mark.asyncio
    async def test_parse_copy_threshold(self, scalene_adapter):
        """Test detecting excessive copying."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "test.py",
                    "lines": {
                        "25": {
                            "cpu_percent": 1.0,
                            "cpu_python": 1.0,
                            "cpu_c": 0.0,
                            "mem_mb": 1.0,
                            "copy_mb": 100.0,
                            "net_memory": 0.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should find copy issue
        copy_issues = [i for i in issues if i.code == "SC004"]
        assert len(copy_issues) == 1
        assert "100.0 MB" in copy_issues[0].message

    @pytest.mark.asyncio
    async def test_parse_gpu_underutilization(self, tmp_path):
        """Test detecting GPU underutilization."""
        settings = ScaleneSettings(profile_gpu=True)
        adapter = ScaleneAdapter(settings=settings)
        adapter.settings = settings

        profile_output = json.dumps({
            "files": [
                {
                    "filename": "test.py",
                    "lines": {
                        "30": {
                            "cpu_percent": 50.0,
                            "cpu_python": 30.0,
                            "cpu_c": 20.0,
                            "mem_mb": 5.0,
                            "copy_mb": 0.0,
                            "net_memory": 0.0,
                            "gpu_percent": 5.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await adapter.parse_output(result)

        # Should find GPU underutilization
        gpu_issues = [i for i in issues if i.code == "SC005"]
        assert len(gpu_issues) == 1

    @pytest.mark.asyncio
    async def test_parse_empty_output(self, scalene_adapter):
        """Test parsing empty output."""
        result = ToolExecutionResult(raw_output="")
        issues = await scalene_adapter.parse_output(result)
        assert issues == []

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, scalene_adapter):
        """Test parsing invalid JSON output with JSON-like content that fails to parse."""
        # The adapter looks for JSON starting with { and extracts it
        # Then tries to parse it. If JSON is found but invalid, creates SC000 issue
        result = ToolExecutionResult(raw_output='{"files": [], "summary": "test"\nnot valid json')
        issues = await scalene_adapter.parse_output(result)

        # Should get error issue when JSON content is found but malformed
        assert len(issues) == 1
        assert issues[0].code == "SC000"
        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_no_json_found(self, scalene_adapter):
        """Test parsing output with no JSON content."""
        result = ToolExecutionResult(raw_output="just some text output")
        issues = await scalene_adapter.parse_output(result)

        assert len(issues) == 0


class TestProfileHotspot:
    """Test suite for ProfileHotspot dataclass."""

    def test_profile_hotspot_to_tool_issue(self):
        """Test converting ProfileHotspot to ToolIssue."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=42,
            rule="SC001",
            message="CPU hotspot: 25% of CPU time",
            severity="warning",
            details={"cpu_percent": 25.0},
        )

        issue = hotspot.to_tool_issue()

        assert issue.file_path == Path("test.py")
        assert issue.line_number == 42
        assert issue.message == "CPU hotspot: 25% of CPU time"
        assert issue.code == "SC001"
        assert issue.severity == "warning"

    def test_get_suggestion_for_cpu(self):
        """Test suggestion for CPU hotspot."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=10,
            rule="SC001",
            message="CPU hotspot",
            severity="warning",
            details={},
        )
        suggestion = hotspot._get_suggestion()
        assert "optimizing" in suggestion.lower() or "algorithm" in suggestion.lower()

    def test_get_suggestion_for_memory_leak(self):
        """Test suggestion for memory leak."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=10,
            rule="SC003",
            message="Memory leak",
            severity="error",
            details={},
        )
        suggestion = hotspot._get_suggestion()
        assert "lifecycle" in suggestion.lower() or "release" in suggestion.lower()


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self, scalene_adapter):
        """Test default configuration."""
        config = scalene_adapter.get_default_config()

        assert config.check_name == "scalene"
        assert config.check_type == QACheckType.PROFILE
        assert config.enabled is True
        assert config.stage == "comprehensive"
        assert config.parallel_safe is False
        assert "**/*.py" in config.file_patterns


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self, scalene_adapter):
        """Test check type is PROFILE."""
        assert scalene_adapter._get_check_type() == QACheckType.PROFILE


class TestValidateToolAvailable:
    """Test suite for validate_tool_available method."""

    @pytest.mark.asyncio
    async def test_validate_tool_found(self):
        """Test validate_tool_available when scalene is found."""
        adapter = ScaleneAdapter()

        with patch("shutil.which", return_value="/usr/bin/scalene"):
            with patch(
                "asyncio.create_subprocess_exec",
                new_callable=AsyncMock,
                return_value=AsyncMock(
                    communicate=AsyncMock(
                        return_value=(b"scalene 24.5.0", b"")
                    )
                ),
            ):
                result = await adapter.validate_tool_available()
                assert result is True
                assert adapter._tool_available is True

    @pytest.mark.asyncio
    async def test_validate_tool_not_found(self):
        """Test validate_tool_available when scalene is not found."""
        adapter = ScaleneAdapter()

        with patch("shutil.which", return_value=None):
            result = await adapter.validate_tool_available()
            assert result is False
            assert adapter._tool_available is False

    @pytest.mark.asyncio
    async def test_validate_tool_uses_cache(self):
        """Test validate_tool_available uses cached result."""
        adapter = ScaleneAdapter()
        adapter._tool_available = True

        result = await adapter.validate_tool_available()
        assert result is True
