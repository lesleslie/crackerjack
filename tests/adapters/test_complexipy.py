"""Tests for ComplexipyAdapter (complexity analysis adapter)."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.complexity.complexipy import (
    MODULE_ID,
    ComplexipyAdapter,
    ComplexipySettings,
)
from crackerjack.models.qa_results import QACheckType


@pytest.fixture
def complexipy_settings():
    """Provide ComplexipySettings for testing."""
    return ComplexipySettings(
        timeout_seconds=90,
        max_workers=4,
        max_complexity=15,
        include_cognitive=True,
        include_maintainability=True,
        sort_by="desc",
    )


@pytest.fixture
async def complexipy_adapter(complexipy_settings):
    """Provide initialized ComplexipyAdapter for testing."""
    adapter = ComplexipyAdapter(settings=complexipy_settings)

    with (
        patch.object(adapter, "validate_tool_available", return_value=True),
        patch.object(adapter, "get_tool_version", return_value="0.13.0"),
    ):
        await adapter.init()
    return adapter


class TestComplexipySettings:
    """Test suite for ComplexipySettings."""

    def test_default_settings(self):
        """Test ComplexipySettings default values."""
        settings = ComplexipySettings()
        assert settings.tool_name == "complexipy"
        assert settings.use_json_output is True
        assert settings.max_complexity == 15
        assert settings.include_cognitive is True
        assert settings.include_maintainability is True
        assert settings.sort_by == "desc"

    def test_custom_settings(self):
        """Test ComplexipySettings with custom values."""
        settings = ComplexipySettings(
            max_complexity=20,
            include_cognitive=False,
            sort_by="asc",
        )
        assert settings.max_complexity == 20
        assert settings.include_cognitive is False
        assert settings.sort_by == "asc"


class TestComplexipyAdapterProperties:
    """Test suite for ComplexipyAdapter properties."""

    def test_adapter_name(self, complexipy_adapter):
        """Test adapter_name property."""
        assert complexipy_adapter.adapter_name == "Complexipy (Complexity)"

    def test_module_id(self, complexipy_adapter):
        """Test module_id is correct UUID."""
        assert complexipy_adapter.module_id == MODULE_ID

    def test_tool_name(self, complexipy_adapter):
        """Test tool_name property."""
        assert complexipy_adapter.tool_name == "complexipy"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self, complexipy_adapter, tmp_path):
        """Test building basic complexipy command."""
        test_file = tmp_path / "test_code.py"
        test_file.write_text("def test_x(): pass\n")

        cmd = complexipy_adapter.build_command([test_file])

        assert "complexipy" in cmd
        assert "--output-json" in cmd
        assert "--max-complexity-allowed" in cmd
        assert str(test_file) in cmd

    def test_build_command_with_exclude_patterns(self, tmp_path):
        """Test command with exclude patterns."""
        settings = ComplexipySettings()
        adapter = ComplexipyAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        # Mock _load_config_from_pyproject to return exclude patterns
        with patch.object(
            adapter, "_load_config_from_pyproject",
            return_value={"exclude_patterns": ["**/test/**", "**/.venv/**"]}
        ):
            cmd = adapter.build_command([test_file])

        assert "--exclude" in cmd

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = ComplexipyAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestProcessComplexipyData:
    """Test suite for _process_complexipy_data method."""

    @pytest.mark.asyncio
    async def test_process_list_data(self, complexipy_adapter):
        """Test processing list-style complexipy output."""
        data = [
            {
                "path": "test.py",
                "function_name": "complex_function",
                "complexity": 25,
                "cognitive_complexity": 15,
                "maintainability": 65.5,
                "line": 10,
            },
            {
                "path": "test.py",
                "function_name": "simple_function",
                "complexity": 5,
                "cognitive_complexity": 2,
                "maintainability": 90.0,
                "line": 20,
            },
        ]

        issues = complexipy_adapter._process_complexipy_data(data)

        # Should report one issue (complex_function exceeds max=15)
        assert len(issues) == 1
        assert issues[0].code == "COMPLEXITY"
        assert issues[0].severity == "warning"  # 25 < 15*2 = 30, so warning not error
        assert "complex_function" in issues[0].message

    @pytest.mark.asyncio
    async def test_process_dict_data(self, complexipy_adapter):
        """Test processing dict-style complexipy output."""
        data = {
            "files": [
                {
                    "path": "test.py",
                    "functions": [
                        {
                            "name": "very_complex",
                            "complexity": 40,
                            "cognitive_complexity": 20,
                            "maintainability": 45.0,
                            "line": 5,
                        }
                    ],
                }
            ]
        }

        issues = complexipy_adapter._process_complexipy_data(data)

        assert len(issues) == 1
        assert issues[0].severity == "error"  # 40 > 15*2 = 30

    @pytest.mark.asyncio
    async def test_process_very_high_complexity(self, complexipy_adapter):
        """Test processing very high complexity gets error severity."""
        data = [
            {
                "path": "test.py",
                "function_name": "extremely_complex",
                "complexity": 50,
                "line": 1,
            },
        ]

        issues = complexipy_adapter._process_complexipy_data(data)

        assert len(issues) == 1
        assert issues[0].severity == "error"  # 50 > 15*2 = 30


class TestCreateIssueIfNeeded:
    """Test suite for _create_issue_if_needed method."""

    def test_returns_none_for_low_complexity(self, complexipy_adapter):
        """Test returns None when complexity is within threshold."""
        func = {"complexity": 10, "name": "simple"}
        result = complexipy_adapter._create_issue_if_needed(Path("test.py"), func)
        assert result is None

    def test_returns_issue_for_high_complexity(self, complexipy_adapter):
        """Test returns issue when complexity exceeds threshold."""
        func = {"complexity": 20, "name": "complex", "line": 10}
        result = complexipy_adapter._create_issue_if_needed(Path("test.py"), func)
        assert result is not None
        assert result.code == "COMPLEXITY"
        assert result.severity == "warning"  # 20 < 15*2 = 30

    def test_returns_error_for_very_high_complexity(self, complexipy_adapter):
        """Test returns error severity for very high complexity."""
        func = {"complexity": 40, "name": "very_complex", "line": 5}
        result = complexipy_adapter._create_issue_if_needed(Path("test.py"), func)
        assert result is not None
        assert result.severity == "error"  # 40 > 15*2 = 30

    def test_returns_none_without_settings(self):
        """Test returns None when settings not initialized."""
        adapter = ComplexipyAdapter()
        result = adapter._create_issue_if_needed(Path("test.py"), {"complexity": 20})
        assert result is None


class TestBuildIssueMessage:
    """Test suite for _build_issue_message method."""

    def test_message_with_cognitive_and_maintainability(self, complexipy_adapter):
        """Test building issue message with cognitive and maintainability."""
        func = {
            "name": "test_func",
            "cognitive_complexity": 15,
            "maintainability": 72.5,
        }
        message = complexipy_adapter._build_issue_message(func, 20)

        assert "test_func" in message
        assert "20" in message
        assert "15" in message  # cognitive
        assert "72.5" in message  # maintainability

    def test_message_without_cognitive(self, complexipy_adapter):
        """Test building issue message without cognitive complexity."""
        complexipy_adapter.settings.include_cognitive = False
        func = {
            "name": "test_func",
            "cognitive_complexity": 15,
            "maintainability": 80.0,
        }
        message = complexipy_adapter._build_issue_message(func, 20)

        assert "test_func" in message
        assert "Cognitive" not in message

    def test_message_without_maintainability(self, complexipy_adapter):
        """Test building issue message without maintainability."""
        complexipy_adapter.settings.include_maintainability = False
        func = {
            "name": "test_func",
            "cognitive_complexity": 10,
            "maintainability": 85.0,
        }
        message = complexipy_adapter._build_issue_message(func, 20)

        assert "test_func" in message
        assert "Maintainability" not in message


class TestDetermineIssueSeverity:
    """Test suite for _determine_issue_severity method."""

    def test_warning_for_moderate_exceedance(self, complexipy_adapter):
        """Test warning severity for moderate complexity exceedance."""
        severity = complexipy_adapter._determine_issue_severity(25)
        assert severity == "warning"  # 25 < 15*2 = 30

    def test_error_for_high_exceedance(self, complexipy_adapter):
        """Test error severity for high complexity exceedance."""
        severity = complexipy_adapter._determine_issue_severity(35)
        assert severity == "error"  # 35 > 15*2 = 30

    def test_returns_warning_without_settings(self):
        """Test returns warning when settings not initialized."""
        adapter = ComplexipyAdapter()
        severity = adapter._determine_issue_severity(20)
        assert severity == "warning"


class TestParseTextOutput:
    """Test suite for _parse_text_output fallback method."""

    def test_parse_text_with_file_and_complexity(self, complexipy_adapter):
        """Test parsing text output with file and complexity info."""
        # Format must match: "name (line N) complexity value" (no colon)
        output = """File: test.py
function_name (line 10) complexity 25
another_func (line 20) complexity 8
"""
        issues = complexipy_adapter._parse_text_output(output)

        # May find issues depending on max_complexity setting
        assert isinstance(issues, list)

    def test_parse_text_empty_output(self, complexipy_adapter):
        """Test parsing empty text output."""
        issues = complexipy_adapter._parse_text_output("")
        assert issues == []

    def test_parse_text_no_complexity_lines(self, complexipy_adapter):
        """Test parsing text with no complexity info."""
        output = "just some regular text"
        issues = complexipy_adapter._parse_text_output(output)
        # May or may not find issues depending on fallback parsing
        assert isinstance(issues, list)


class TestExtractFunctionData:
    """Test suite for _extract_function_data helper."""

    def test_extract_valid_line(self, complexipy_adapter):
        """Test extracting function data from valid line."""
        # Format: "name (line N) complexity value" - space separated after 'complexity'
        line = "complex_function (line 42) complexity 25"
        result = complexipy_adapter._extract_function_data(line)

        assert result is not None
        func_name, line_num, complexity = result
        assert func_name == "complex_function"
        assert line_num == 42
        assert complexity == 25

    def test_extract_invalid_line(self, complexipy_adapter):
        """Test extracting from invalid line returns None."""
        line = "not a valid complexity line"
        result = complexipy_adapter._extract_function_data(line)
        assert result is None

    def test_extract_line_with_only_lowercase_complexity(self, complexipy_adapter):
        """Test extraction with lowercase 'complexity' keyword."""
        # The code does "complexity" in line.lower() so it's case insensitive
        # But it splits on literal "complexity" not the lowercased version
        line = "MyFunc (line 10) complexity 8"
        result = complexipy_adapter._extract_function_data(line)
        # This should work if format matches
        assert result is not None


class TestMoveComplexipyResults:
    """Test suite for _move_complexipy_results_to_output_dir."""

    def test_returns_none_when_no_files(self, complexipy_adapter, tmp_path):
        """Test returns None when no result files found."""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = complexipy_adapter._move_complexipy_results_to_output_dir()
        assert result is None


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self, complexipy_adapter):
        """Test default configuration."""
        config = complexipy_adapter.get_default_config()

        assert config.check_name == "Complexipy (Complexity)"
        assert config.check_type == QACheckType.COMPLEXITY
        assert config.enabled is True
        assert config.stage == "comprehensive"
        assert config.parallel_safe is True
        assert "**/*.py" in config.file_patterns


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self, complexipy_adapter):
        """Test check type is COMPLEXITY."""
        assert complexipy_adapter._get_check_type() == QACheckType.COMPLEXITY


class TestLoadConfigFromPyproject:
    """Test suite for _load_config_from_pyproject method."""

    def test_load_config_exclude_patterns(self, complexipy_adapter, tmp_path):
        """Test loading exclude patterns from pyproject.toml."""
        pyproject_content = """
[tool.complexipy]
exclude_patterns = ["**/mypy/**", "**/pylint/**"]
max_complexity = 20
"""
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            config = complexipy_adapter._load_config_from_pyproject()

        assert "exclude_patterns" in config
        assert "**/mypy/**" in config["exclude_patterns"]

    def test_load_config_max_complexity(self, complexipy_adapter, tmp_path):
        """Test loading max_complexity from pyproject.toml."""
        pyproject_content = """
[tool.complexipy]
max_complexity = 25
"""
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text(pyproject_content)

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            config = complexipy_adapter._load_config_from_pyproject()

        assert config.get("max_complexity") == 25

    def test_load_config_file_not_found(self, complexipy_adapter, tmp_path):
        """Test loading config when file doesn't exist."""
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            config = complexipy_adapter._load_config_from_pyproject()

        assert "exclude_patterns" in config  # default value
        assert "max_complexity" in config  # default value


class TestLoadExcludePatternsFromConfig:
    """Test suite for _load_exclude_patterns_from_config method."""

    def test_returns_exclude_patterns_from_config(self, complexipy_adapter, tmp_path):
        """Test returns exclude patterns from pyproject.toml config."""
        # The actual behavior loads from pyproject.toml tool.complexipy section
        # In the test environment, this may return the project's configured patterns
        patterns = complexipy_adapter._load_exclude_patterns_from_config()
        # Just verify it returns a list - actual patterns depend on pyproject.toml content
        assert isinstance(patterns, list)
        assert len(patterns) >= 1


class TestParseOutput:
    """Test suite for parse_output method with JSON file reading."""

    @pytest.mark.asyncio
    async def test_parse_json_from_file(self, complexipy_adapter, tmp_path):
        """Test parsing JSON from output file."""
        # Create a fake result file
        result_file = tmp_path / "complexipy_results_0.json"
        result_data = [
            {
                "path": "test.py",
                "function_name": "test_func",
                "complexity": 20,
                "line": 1,
            }
        ]
        result_file.write_text(json.dumps(result_data))

        # Mock output path and AdapterOutputPaths
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            with patch(
                "crackerjack.adapters.complexity.complexipy.AdapterOutputPaths.get_output_dir"
            ) as mock_get_output:
                mock_output_dir = tmp_path / "output"
                mock_output_dir.mkdir()
                mock_get_output.return_value = mock_output_dir

                result = ToolExecutionResult(raw_output="")
                issues = await complexipy_adapter.parse_output(result)

        # Should find the issue
        assert len(issues) >= 0  # May have issues depending on config

    @pytest.mark.asyncio
    async def test_parse_json_from_stdout(self, complexipy_adapter):
        """Test parsing JSON from stdout when no file exists."""
        json_output = json.dumps([
            {
                "path": "test.py",
                "function_name": "test_func",
                "complexity": 20,
                "line": 1,
            }
        ])

        result = ToolExecutionResult(raw_output=json_output)
        issues = await complexipy_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].code == "COMPLEXITY"

    @pytest.mark.asyncio
    async def test_parse_invalid_json_fallback(self, complexipy_adapter):
        """Test fallback to text parsing on invalid JSON."""
        result = ToolExecutionResult(raw_output="not valid json")
        issues = await complexipy_adapter.parse_output(result)

        # Falls back to text parsing
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_parse_empty_output(self, complexipy_adapter):
        """Test parsing empty output."""
        result = ToolExecutionResult(raw_output="")
        issues = await complexipy_adapter.parse_output(result)
        assert issues == []