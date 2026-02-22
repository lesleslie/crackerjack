"""Tests for ScaleneAdapter and related components."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.performance import (
    ProfileHotspot,
    ScaleneAdapter,
    ScaleneSettings,
)
from crackerjack.adapters.performance.scalene import MODULE_ID
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
        patch.object(adapter, "get_tool_version", return_value="1.5.0"),
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
            profile_all=True,
        )
        assert settings.cpu_percent_threshold == 10.0
        assert settings.memory_threshold_mb == 20.0
        assert settings.copy_threshold_mb == 100.0
        assert settings.profile_gpu is True
        assert settings.profile_all is True


class TestProfileHotspot:
    """Test suite for ProfileHotspot."""

    def test_profile_hotspot_creation(self):
        """Test creating a ProfileHotspot."""
        hotspot = ProfileHotspot(
            file_path=Path("my_module.py"),
            line_number=42,
            rule="SC001",
            message="CPU hotspot",
            severity="warning",
            details={"cpu_percent": 15.0},
        )
        assert hotspot.file_path == Path("my_module.py")
        assert hotspot.line_number == 42
        assert hotspot.rule == "SC001"
        assert hotspot.severity == "warning"

    def test_to_tool_issue(self):
        """Test converting to ToolIssue."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=10,
            rule="SC001",
            message="CPU hotspot",
            severity="warning",
            details={},
        )
        issue = hotspot.to_tool_issue()
        assert issue.file_path == Path("test.py")
        assert issue.line_number == 10
        assert issue.code == "SC001"
        assert issue.severity == "warning"

    def test_get_suggestion_for_cpu_hotspot(self):
        """Test suggestion for CPU hotspot."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=1,
            rule="SC001",
            message="CPU hotspot",
            severity="warning",
            details={},
        )
        suggestion = hotspot._get_suggestion()
        assert "optimizing" in suggestion.lower()

    def test_get_suggestion_for_memory_hotspot(self):
        """Test suggestion for memory hotspot."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=1,
            rule="SC002",
            message="Memory hotspot",
            severity="warning",
            details={},
        )
        suggestion = hotspot._get_suggestion()
        assert "pooling" in suggestion.lower() or "generator" in suggestion.lower()

    def test_get_suggestion_for_memory_leak(self):
        """Test suggestion for memory leak."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=1,
            rule="SC003",
            message="Memory leak",
            severity="error",
            details={},
        )
        suggestion = hotspot._get_suggestion()
        assert "lifecycle" in suggestion.lower()

    def test_get_suggestion_for_copy_volume(self):
        """Test suggestion for copy volume."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=1,
            rule="SC004",
            message="Excessive copying",
            severity="warning",
            details={},
        )
        suggestion = hotspot._get_suggestion()
        assert "view" in suggestion.lower() or "in-place" in suggestion.lower()

    def test_get_suggestion_unknown_rule(self):
        """Test suggestion for unknown rule."""
        hotspot = ProfileHotspot(
            file_path=Path("test.py"),
            line_number=1,
            rule="SC999",
            message="Unknown",
            severity="info",
            details={},
        )
        suggestion = hotspot._get_suggestion()
        assert suggestion is None


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
        """Test building basic command."""
        test_file = tmp_path / "my_module.py"
        test_file.write_text("def main(): pass\n")

        cmd = scalene_adapter.build_command([test_file])

        assert "scalene" in cmd
        assert "--cli" in cmd
        assert "--json" in cmd
        assert "--cpu" in cmd
        assert "--memory" in cmd
        assert "--reduced-profile" in cmd

    def test_build_command_with_test_file(self, scalene_adapter, tmp_path):
        """Test command with test file detection."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_x(): pass\n")

        cmd = scalene_adapter.build_command([test_file])

        assert "pytest" in cmd

    def test_build_command_with_gpu(self, tmp_path):
        """Test command with GPU profiling enabled."""
        settings = ScaleneSettings(profile_gpu=True)
        adapter = ScaleneAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "module.py"

        cmd = adapter.build_command([test_file])

        assert "--gpu" in cmd

    def test_build_command_with_profile_all(self, tmp_path):
        """Test command with profile-all enabled."""
        settings = ScaleneSettings(profile_all=True)
        adapter = ScaleneAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "module.py"

        cmd = adapter.build_command([test_file])

        assert "--profile-all" in cmd

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = ScaleneAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_valid_json_output(self, scalene_adapter):
        """Test parsing valid JSON output."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "my_module.py",
                    "lines": {
                        "10": {
                            "cpu_percent": 2.5,
                            "cpu_python": 1.5,
                            "cpu_c": 1.0,
                            "mem_mb": 5.0,
                            "copy_mb": 1.0,
                            "gpu_percent": 0.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # No issues since all values below threshold
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_cpu_hotspot(self, scalene_adapter):
        """Test detecting CPU hotspot."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "slow_module.py",
                    "lines": {
                        "42": {
                            "cpu_percent": 25.0,
                            "cpu_python": 20.0,
                            "cpu_c": 5.0,
                            "mem_mb": 2.0,
                            "copy_mb": 1.0,
                            "gpu_percent": 0.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should detect CPU hotspot (SC001)
        cpu_issues = [i for i in issues if i.code == "SC001"]
        assert len(cpu_issues) == 1
        assert cpu_issues[0].line_number == 42
        assert "CPU hotspot" in cpu_issues[0].message

    @pytest.mark.asyncio
    async def test_parse_memory_hotspot(self, scalene_adapter):
        """Test detecting memory hotspot."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "memory_hog.py",
                    "lines": {
                        "15": {
                            "cpu_percent": 1.0,
                            "cpu_python": 1.0,
                            "cpu_c": 0.0,
                            "mem_mb": 50.0,
                            "copy_mb": 1.0,
                            "gpu_percent": 0.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should detect memory hotspot (SC002)
        mem_issues = [i for i in issues if i.code == "SC002"]
        assert len(mem_issues) == 1
        assert mem_issues[0].line_number == 15
        assert "Memory hotspot" in mem_issues[0].message

    @pytest.mark.asyncio
    async def test_parse_memory_leak(self, scalene_adapter):
        """Test detecting potential memory leak."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "leaky.py",
                    "lines": {
                        "20": {
                            "cpu_percent": 1.0,
                            "cpu_python": 1.0,
                            "cpu_c": 0.0,
                            "mem_mb": 5.0,
                            "copy_mb": 1.0,
                            "gpu_percent": 0.0,
                            "net_memory": -25.0,  # Net negative = leak indicator
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should detect memory leak (SC003)
        leak_issues = [i for i in issues if i.code == "SC003"]
        assert len(leak_issues) == 1
        assert leak_issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_excessive_copy(self, scalene_adapter):
        """Test detecting excessive copying."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "copycat.py",
                    "lines": {
                        "30": {
                            "cpu_percent": 1.0,
                            "cpu_python": 1.0,
                            "cpu_c": 0.0,
                            "mem_mb": 5.0,
                            "copy_mb": 100.0,  # Exceeds 50 MB threshold
                            "gpu_percent": 0.0,
                        }
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should detect excessive copy (SC004)
        copy_issues = [i for i in issues if i.code == "SC004"]
        assert len(copy_issues) == 1
        assert "Excessive copying" in copy_issues[0].message

    @pytest.mark.asyncio
    async def test_parse_malformed_json(self, scalene_adapter):
        """Test parsing malformed JSON output."""
        # JSON that starts but is invalid
        result = ToolExecutionResult(raw_output='{"files": [invalid}')
        issues = await scalene_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].code == "SC000"
        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_no_json(self, scalene_adapter):
        """Test parsing output with no JSON."""
        result = ToolExecutionResult(raw_output="no json here at all")
        issues = await scalene_adapter.parse_output(result)

        # When no JSON found, returns empty list
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_empty_output(self, scalene_adapter):
        """Test parsing empty output."""
        result = ToolExecutionResult(raw_output="")
        issues = await scalene_adapter.parse_output(result)
        assert len(issues) == 0


class TestDetectTestFile:
    """Test suite for _detect_test_file method."""

    def test_detect_test_file_prefix(self, scalene_adapter, tmp_path):
        """Test detecting test file by prefix."""
        test_file = tmp_path / "test_module.py"
        assert scalene_adapter._detect_test_file([test_file]) is True

    def test_detect_test_file_suffix(self, scalene_adapter, tmp_path):
        """Test detecting test file by suffix."""
        test_file = tmp_path / "module_test.py"
        assert scalene_adapter._detect_test_file([test_file]) is True

    def test_detect_non_test_file(self, scalene_adapter, tmp_path):
        """Test non-test file is not detected."""
        module_file = tmp_path / "my_module.py"
        assert scalene_adapter._detect_test_file([module_file]) is False


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


class TestExtractJson:
    """Test suite for _extract_json method."""

    def test_extract_json_at_start(self, scalene_adapter):
        """Test extracting JSON at start of output."""
        output = '{"files": []}'
        result = scalene_adapter._extract_json(output)
        assert result == '{"files": []}'

    def test_extract_json_with_prefix(self, scalene_adapter):
        """Test extracting JSON with text prefix."""
        output = "Scalene profiling output...\n{\"files\": []}"
        result = scalene_adapter._extract_json(output)
        assert result == '{"files": []}'

    def test_extract_json_no_json(self, scalene_adapter):
        """Test when no JSON present."""
        output = "No JSON here"
        result = scalene_adapter._extract_json(output)
        assert result is None


class TestMultipleHotspots:
    """Test suite for multiple hotspots in one file."""

    @pytest.mark.asyncio
    async def test_multiple_hotspots_same_file(self, scalene_adapter):
        """Test detecting multiple hotspots in same file."""
        profile_output = json.dumps({
            "files": [
                {
                    "filename": "complex.py",
                    "lines": {
                        "10": {
                            "cpu_percent": 15.0,
                            "cpu_python": 12.0,
                            "cpu_c": 3.0,
                            "mem_mb": 2.0,
                            "copy_mb": 1.0,
                        },
                        "20": {
                            "cpu_percent": 2.0,
                            "cpu_python": 2.0,
                            "cpu_c": 0.0,
                            "mem_mb": 25.0,
                            "copy_mb": 1.0,
                        },
                        "30": {
                            "cpu_percent": 8.0,
                            "cpu_python": 8.0,
                            "cpu_c": 0.0,
                            "mem_mb": 5.0,
                            "copy_mb": 75.0,
                        },
                    }
                }
            ]
        })

        result = ToolExecutionResult(raw_output=profile_output)
        issues = await scalene_adapter.parse_output(result)

        # Should detect:
        # - SC001 on line 10 (CPU hotspot)
        # - SC002 on line 20 (Memory hotspot)
        # - SC001 on line 30 (CPU hotspot)
        # - SC004 on line 30 (Excessive copying)
        assert len(issues) >= 3

        cpu_issues = [i for i in issues if i.code == "SC001"]
        mem_issues = [i for i in issues if i.code == "SC002"]
        copy_issues = [i for i in issues if i.code == "SC004"]

        assert len(cpu_issues) >= 1
        assert len(mem_issues) >= 1
        assert len(copy_issues) >= 1
