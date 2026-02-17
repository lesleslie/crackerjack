"""Test ComplexipyAdapter complexity analysis functionality."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

# Module-level import pattern to avoid pytest conflicts
from crackerjack.adapters.complexity import complexipy
from crackerjack.adapters._tool_adapter_base import ToolExecutionResult

ComplexipyAdapter = complexipy.ComplexipyAdapter
ComplexipySettings = complexipy.ComplexipySettings
MODULE_ID = complexipy.MODULE_ID


class TestComplexipySettings:
    """Test ComplexipySettings dataclass."""

    def test_default_field_values(self) -> None:
        """Test that ComplexipySettings has correct default values."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)

        assert settings.tool_name == "complexipy"
        assert settings.use_json_output is True
        assert settings.max_complexity == 15
        assert settings.include_cognitive is True
        assert settings.include_maintainability is True
        assert settings.sort_by == "desc"

    def test_custom_values_override_defaults(self) -> None:
        """Test that custom values override defaults."""
        settings = ComplexipySettings(
            max_complexity=20,
            include_cognitive=False,
            sort_by="asc",
            timeout_seconds=90,
            max_workers=4,
        )

        assert settings.max_complexity == 20
        assert settings.include_cognitive is False
        assert settings.sort_by == "asc"

    def test_inherits_from_tool_adapter_settings(self) -> None:
        """Test that ComplexipySettings inherits from ToolAdapterSettings."""
        settings = ComplexipySettings(timeout_seconds=120, max_workers=8, max_complexity=15)

        assert hasattr(settings, "timeout_seconds")
        assert settings.timeout_seconds == 120
        assert settings.max_workers == 8


class TestConstructor:
    """Test ComplexipyAdapter constructor."""

    @patch("crackerjack.adapters.complexity.complexipy.BaseToolAdapter.__init__")
    def test_initialize_with_settings(self, mock_init: Mock) -> None:
        """Test initialization with settings."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=20)
        adapter = ComplexipyAdapter(settings=settings)

        mock_init.assert_called_once_with(settings=settings)
        assert adapter.settings == settings

    @patch("crackerjack.adapters.complexity.complexipy.BaseToolAdapter.__init__")
    def test_initialize_without_settings(self, mock_init: Mock) -> None:
        """Test initialization without settings."""
        adapter = ComplexipyAdapter(settings=None)

        mock_init.assert_called_once_with(settings=None)
        assert adapter.settings is None

    @patch("crackerjack.adapters.complexity.complexipy.BaseToolAdapter.__init__")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_logs_initialization(self, mock_logger: Mock, mock_init: Mock) -> None:
        """Test that initialization is logged."""
        adapter = ComplexipyAdapter(settings=None)

        mock_logger.debug.assert_called()
        assert "has_settings" in mock_logger.debug.call_args.kwargs["extra"]


class TestInit:
    """Test async init() method."""

    @patch("crackerjack.adapters.complexity.complexipy.BaseToolAdapter.init")
    @patch("tomllib.load")
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_loads_config_from_pyproject_when_no_settings(
        self, mock_logger: Mock, mock_path: Mock, mock_toml_load: Mock, mock_super_init: Mock
    ) -> None:
        """Test that init() loads config from pyproject.toml when settings is None."""
        mock_path.cwd.return_value.exists.return_value = True
        mock_toml_load.return_value = {
            "tool": {"complexipy": {"max_complexity": 20}}
        }

        adapter = ComplexipyAdapter(settings=None)

        import asyncio

        asyncio.run(adapter.init())

        assert adapter.settings is not None
        assert adapter.settings.max_complexity == 20

    @patch("crackerjack.adapters.complexity.complexipy.BaseToolAdapter.init")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_creates_settings_with_default_config(
        self, mock_logger: Mock, mock_super_init: Mock
    ) -> None:
        """Test that init() creates ComplexipySettings with loaded config."""
        adapter = ComplexipyAdapter(settings=None)

        import asyncio

        asyncio.run(adapter.init())

        assert adapter.settings is not None
        assert adapter.settings.max_complexity == 15
        assert adapter.settings.timeout_seconds == 90
        assert adapter.settings.max_workers == 4

    @patch("crackerjack.adapters.complexity.complexipy.BaseToolAdapter.init")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_calls_super_init(self, mock_logger: Mock, mock_super_init: Mock) -> None:
        """Test that init() calls super().init()."""
        adapter = ComplexipyAdapter(settings=None)

        import asyncio

        asyncio.run(adapter.init())

        mock_super_init.assert_called_once()

    @patch("crackerjack.adapters.complexity.complexipy.BaseToolAdapter.init")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_logs_initialization_complete(
        self, mock_logger: Mock, mock_super_init: Mock
    ) -> None:
        """Test that init() logs completion."""
        adapter = ComplexipyAdapter(settings=None)

        import asyncio

        asyncio.run(adapter.init())

        assert any(
            "initialization complete" in str(call).lower()
            for call in mock_logger.debug.call_args_list
        )


class TestProperties:
    """Test adapter properties."""

    def test_adapter_name(self) -> None:
        """Test adapter_name property."""
        adapter = ComplexipyAdapter()
        assert adapter.adapter_name == "Complexipy (Complexity)"

    def test_module_id(self) -> None:
        """Test module_id property."""
        adapter = ComplexipyAdapter()
        assert adapter.module_id == MODULE_ID

    def test_tool_name(self) -> None:
        """Test tool_name property."""
        adapter = ComplexipyAdapter()
        assert adapter.tool_name == "complexipy"


class TestBuildCommand:
    """Test build_command() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_builds_basic_command_with_files(self, mock_logger: Mock) -> None:
        """Test building basic command with files."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)
        files = [Path("test1.py"), Path("test2.py")]

        cmd = adapter.build_command(files)

        assert cmd[0] == "complexipy"
        assert "test1.py" in cmd
        assert "test2.py" in cmd

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_includes_output_json_flag(self, mock_logger: Mock) -> None:
        """Test that --output-json flag is included when use_json_output=True."""
        settings = ComplexipySettings(use_json_output=True)
        adapter = ComplexipyAdapter(settings=settings)
        files = [Path("test.py")]

        cmd = adapter.build_command(files)

        assert "--output-json" in cmd

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_includes_max_complexity_allowed(self, mock_logger: Mock) -> None:
        """Test that --max-complexity-allowed is included."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=20)
        adapter = ComplexipyAdapter(settings=settings)
        files = [Path("test.py")]

        cmd = adapter.build_command(files)

        assert "--max-complexity-allowed" in cmd
        assert "20" in cmd

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_includes_sort_flag(self, mock_logger: Mock) -> None:
        """Test that --sort flag is included."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, sort_by="asc")
        adapter = ComplexipyAdapter(settings=settings)
        files = [Path("test.py")]

        cmd = adapter.build_command(files)

        assert "--sort" in cmd
        assert "asc" in cmd

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_raises_runtime_error_when_settings_not_initialized(
        self, mock_logger: Mock
    ) -> None:
        """Test that RuntimeError is raised when settings is None."""
        adapter = ComplexipyAdapter(settings=None)
        files = [Path("test.py")]

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command(files)

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_converts_file_paths_to_strings(self, mock_logger: Mock) -> None:
        """Test that file paths are converted to strings."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)
        files = [Path("dir/test1.py"), Path("dir/test2.py")]

        cmd = adapter.build_command(files)

        # All file paths should be strings in the command
        for item in cmd[4:]:  # Skip the command and flags
            assert isinstance(item, str)


class TestParseOutputJSONFile:
    """Test parse_output() with JSON file."""

    @patch(
        "crackerjack.adapters.complexity.complexipy.AdapterOutputPaths.get_output_dir"
    )
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_loads_json_from_file(
        self, mock_logger: Mock, mock_path: Mock, mock_get_output_dir: Mock
    ) -> None:
        """Test loading JSON from file."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, use_json_output=True, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        # Mock file exists and contains valid JSON
        mock_json_file = Mock()
        mock_json_file.exists.return_value = True
        mock_json_file.open.return_value.__enter__.return_value.read.return_value = (
            '[{"path": "test.py", "function_name": "foo", "complexity": 20}]'
        )

        adapter._move_complexipy_results_to_output_dir = Mock(
            return_value=mock_json_file
        )

        result = ToolExecutionResult(raw_output="", exit_code=0)

        import asyncio

        issues = asyncio.run(adapter.parse_output(result))

        assert len(issues) > 0

    @patch(
        "crackerjack.adapters.complexity.complexipy.AdapterOutputPaths.get_output_dir"
    )
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_empty_list_when_no_json_file(
        self, mock_logger: Mock, mock_path: Mock, mock_get_output_dir: Mock
    ) -> None:
        """Test returning empty list when JSON file doesn't exist."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, use_json_output=True, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        adapter._move_complexipy_results_to_output_dir = Mock(return_value=None)

        result = ToolExecutionResult(raw_output="", exit_code=0)

        import asyncio

        issues = asyncio.run(adapter.parse_output(result))

        assert issues == []

    @patch(
        "crackerjack.adapters.complexity.complexipy.AdapterOutputPaths.get_output_dir"
    )
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_falls_back_to_stdout_parsing_on_json_read_error(
        self, mock_logger: Mock, mock_path: Mock, mock_get_output_dir: Mock
    ) -> None:
        """Test falling back to stdout parsing on JSON read error."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, use_json_output=True, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        # Mock file exists but raises error on read
        mock_json_file = Mock()
        mock_json_file.exists.return_value = True
        mock_json_file.open.side_effect = OSError("File not readable")

        adapter._move_complexipy_results_to_output_dir = Mock(
            return_value=mock_json_file
        )

        adapter._parse_text_output = Mock(return_value=[])

        result = ToolExecutionResult(raw_output="text output", exit_code=0)

        import asyncio

        issues = asyncio.run(adapter.parse_output(result))

        adapter._parse_text_output.assert_called_once_with("text output")


class TestParseOutputJSONStdout:
    """Test parse_output() with JSON from stdout."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_parses_json_from_raw_output(self, mock_logger: Mock) -> None:
        """Test parsing JSON from raw_output."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, use_json_output=False, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        adapter._move_complexipy_results_to_output_dir = Mock(return_value=None)

        json_data = [
            {"path": "test.py", "function_name": "foo", "complexity": 20, "line": 42}
        ]
        result = ToolExecutionResult(
            raw_output=json.dumps(json_data), exit_code=0
        )

        import asyncio

        issues = asyncio.run(adapter.parse_output(result))

        assert len(issues) > 0

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_falls_back_to_text_parsing_on_json_decode_error(
        self, mock_logger: Mock
    ) -> None:
        """Test falling back to text parsing on JSON decode error."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, use_json_output=False, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        adapter._move_complexipy_results_to_output_dir = Mock(return_value=None)
        adapter._parse_text_output = Mock(return_value=[])

        result = ToolExecutionResult(raw_output="invalid json", exit_code=0)

        import asyncio

        issues = asyncio.run(adapter.parse_output(result))

        adapter._parse_text_output.assert_called_once()

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_empty_list_when_no_output(self, mock_logger: Mock) -> None:
        """Test returning empty list when no output."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, use_json_output=False, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        adapter._move_complexipy_results_to_output_dir = Mock(return_value=None)

        result = ToolExecutionResult(raw_output="", exit_code=0)

        import asyncio

        issues = asyncio.run(adapter.parse_output(result))

        assert issues == []


class TestProcessComplexipyDataList:
    """Test _process_complexipy_data() with list format."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_processes_list_of_function_dicts(self, mock_logger: Mock) -> None:
        """Test processing list of function dicts."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        data = [
            {"path": "test.py", "function_name": "foo", "complexity": 20},
            {"path": "test.py", "function_name": "bar", "complexity": 10},
        ]

        issues = adapter._process_complexipy_data(data)

        assert len(issues) == 1  # Only foo exceeds threshold
        assert issues[0].message == "Function 'foo' - Complexity: 20"

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_skips_functions_below_threshold(self, mock_logger: Mock) -> None:
        """Test skipping functions with complexity <= max_complexity."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        data = [
            {"path": "test.py", "function_name": "foo", "complexity": 10},
            {"path": "test.py", "function_name": "bar", "complexity": 15},
        ]

        issues = adapter._process_complexipy_data(data)

        assert len(issues) == 0

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_creates_issue_with_correct_severity(self, mock_logger: Mock) -> None:
        """Test creating issues with correct severity."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        data = [
            {"path": "test.py", "function_name": "high", "complexity": 35},  # > 2x
            {"path": "test.py", "function_name": "medium", "complexity": 20},  # < 2x
        ]

        issues = adapter._process_complexipy_data(data)

        assert len(issues) == 2
        assert issues[0].severity == "error"  # 35 > 15 * 2
        assert issues[1].severity == "warning"  # 20 < 15 * 2

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_empty_list_when_no_settings(self, mock_logger: Mock) -> None:
        """Test returning empty list when settings is None."""
        adapter = ComplexipyAdapter(settings=None)

        data = [{"path": "test.py", "function_name": "foo", "complexity": 20}]

        issues = adapter._process_complexipy_data(data)

        assert issues == []


class TestProcessComplexipyDataDict:
    """Test _process_complexipy_data() with dict format."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_processes_dict_with_files_key(self, mock_logger: Mock) -> None:
        """Test processing dict with 'files' key."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        adapter._process_file_data = Mock(return_value=[])

        data = {
            "files": [
                {"path": "test.py", "functions": [...]},
                {"path": "test2.py", "functions": [...]},
            ]
        }

        issues = adapter._process_complexipy_data(data)

        assert adapter._process_file_data.call_count == 2

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_empty_list_for_empty_dict(self, mock_logger: Mock) -> None:
        """Test returning empty list for empty dict."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        issues = adapter._process_complexipy_data({})

        assert issues == []

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_handles_missing_files_key(self, mock_logger: Mock) -> None:
        """Test handling missing 'files' key."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        issues = adapter._process_complexipy_data({"other_key": "value"})

        assert issues == []


class TestProcessFileData:
    """Test _process_file_data() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_iterates_through_functions(self, mock_logger: Mock) -> None:
        """Test iterating through functions list."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        adapter._create_issue_if_needed = Mock(return_value=None)

        file_path = Path("test.py")
        functions = [
            {"name": "foo", "complexity": 20},
            {"name": "bar", "complexity": 10},
        ]

        issues = adapter._process_file_data(file_path, functions)

        assert adapter._create_issue_if_needed.call_count == 2

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_list_of_issues(self, mock_logger: Mock) -> None:
        """Test returning list of issues."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        mock_issue = Mock()
        adapter._create_issue_if_needed = Mock(side_effect=[mock_issue, None])

        file_path = Path("test.py")
        functions = [{"name": "foo", "complexity": 20}, {"name": "bar", "complexity": 10}]

        issues = adapter._process_file_data(file_path, functions)

        assert len(issues) == 1
        assert issues[0] == mock_issue


class TestCreateIssueIfNeeded:
    """Test _create_issue_if_needed() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_none_when_complexity_below_threshold(
        self, mock_logger: Mock
    ) -> None:
        """Test returning None when complexity <= max_complexity."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        file_path = Path("test.py")
        func = {"name": "foo", "complexity": 10, "line": 42}

        issue = adapter._create_issue_if_needed(file_path, func)

        assert issue is None

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_tool_issue_when_complexity_above_threshold(
        self, mock_logger: Mock
    ) -> None:
        """Test returning ToolIssue when complexity > max_complexity."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        file_path = Path("test.py")
        func = {"name": "foo", "complexity": 20, "line": 42}

        issue = adapter._create_issue_if_needed(file_path, func)

        assert issue is not None
        assert issue.code == "COMPLEXITY"
        assert issue.line_number == 42

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_builds_message_with_build_issue_message(
        self, mock_logger: Mock
    ) -> None:
        """Test that message is built with _build_issue_message()."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        file_path = Path("test.py")
        func = {"name": "foo", "complexity": 20, "line": 42}

        issue = adapter._create_issue_if_needed(file_path, func)

        assert "Complexity" in issue.message
        assert "foo" in issue.message

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_none_when_no_settings(self, mock_logger: Mock) -> None:
        """Test returning None when settings is None."""
        adapter = ComplexipyAdapter(settings=None)

        file_path = Path("test.py")
        func = {"name": "foo", "complexity": 20, "line": 42}

        issue = adapter._create_issue_if_needed(file_path, func)

        assert issue is None


class TestBuildIssueMessage:
    """Test _build_issue_message() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_includes_complexity_always(self, mock_logger: Mock) -> None:
        """Test that 'Complexity: N' is always included."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        func = {"name": "foo", "complexity": 20}
        message = adapter._build_issue_message(func, 20)

        assert "Complexity: 20" in message

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_includes_cognitive_when_enabled(self, mock_logger: Mock) -> None:
        """Test including cognitive complexity when enabled."""
        settings = ComplexipySettings(include_cognitive=True)
        adapter = ComplexipyAdapter(settings=settings)

        func = {
            "name": "foo",
            "complexity": 20,
            "cognitive_complexity": 25,
        }
        message = adapter._build_issue_message(func, 20)

        assert "Cognitive: 25" in message

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_includes_maintainability_when_enabled(self, mock_logger: Mock) -> None:
        """Test including maintainability when enabled."""
        settings = ComplexipySettings(include_maintainability=True)
        adapter = ComplexipyAdapter(settings=settings)

        func = {"name": "foo", "complexity": 20, "maintainability": 75.5}
        message = adapter._build_issue_message(func, 20)

        assert "Maintainability: 75.5" in message

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_handles_missing_fields_gracefully(self, mock_logger: Mock) -> None:
        """Test handling missing fields gracefully."""
        settings = ComplexipySettings(
            include_cognitive=True, include_maintainability=True
        )
        adapter = ComplexipyAdapter(settings=settings)

        func = {"name": "foo", "complexity": 20}
        message = adapter._build_issue_message(func, 20)

        # Should not crash, should use .get() defaults
        assert "Complexity: 20" in message


class TestDetermineIssueSeverity:
    """Test _determine_issue_severity() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_error_when_complexity_exceeds_double_threshold(
        self, mock_logger: Mock
    ) -> None:
        """Test returning 'error' when complexity > max_complexity * 2."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        severity = adapter._determine_issue_severity(35)

        assert severity == "error"

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_warning_when_complexity_below_double_threshold(
        self, mock_logger: Mock
    ) -> None:
        """Test returning 'warning' when complexity <= max_complexity * 2."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        severity = adapter._determine_issue_severity(20)

        assert severity == "warning"

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_warning_when_no_settings(self, mock_logger: Mock) -> None:
        """Test returning 'warning' when settings is None."""
        adapter = ComplexipyAdapter(settings=None)

        severity = adapter._determine_issue_severity(35)

        assert severity == "warning"

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_handles_boundary_case_exactly_double(self, mock_logger: Mock) -> None:
        """Test handling boundary case where complexity = 2x threshold."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        severity = adapter._determine_issue_severity(30)  # Exactly 2x

        assert severity == "warning"  # Not > 2x, so warning


class TestParseTextOutput:
    """Test _parse_text_output() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_parses_file_lines(self, mock_logger: Mock) -> None:
        """Test parsing 'File:' lines."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        adapter._parse_complexity_line = Mock(return_value=None)

        output = "File: /path/to/test.py\n"
        adapter._parse_text_output(output)

        # Should update current file
        assert adapter._parse_complexity_line.called

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_empty_list_for_empty_output(self, mock_logger: Mock) -> None:
        """Test returning empty list for empty output."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        issues = adapter._parse_text_output("")

        assert issues == []

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_handles_multiple_files_and_functions(self, mock_logger: Mock) -> None:
        """Test handling multiple files and functions."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        mock_issue = Mock()
        adapter._parse_complexity_line = Mock(return_value=mock_issue)

        output = """File: /path/to/test.py
foo(line 42) complexity 20
bar(line 50) complexity 25
"""

        issues = adapter._parse_text_output(output)

        assert adapter._parse_complexity_line.call_count == 2


class TestUpdateCurrentFile:
    """Test _update_current_file() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_extracts_file_path_from_file_line(self, mock_logger: Mock) -> None:
        """Test extracting file path from 'File:' line."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        new_file = adapter._update_current_file("File: /path/to/test.py", None)

        assert str(new_file) == "/path/to/test.py"

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_current_file_for_non_file_line(
        self, mock_logger: Mock
    ) -> None:
        """Test returning current_file for non-'File:' line."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        current_file = Path("/path/to/test.py")
        result = adapter._update_current_file("foo(line 42) complexity 20", current_file)

        assert result == current_file


class TestParseComplexityLine:
    """Test _parse_complexity_line() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_parses_valid_complexity_line(self, mock_logger: Mock) -> None:
        """Test parsing valid complexity line."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        current_file = Path("/path/to/test.py")
        line = "foo(line 42) complexity 20"

        issue = adapter._parse_complexity_line(line, current_file)

        assert issue is not None
        assert issue.file_path == current_file
        assert issue.line_number == 42
        assert issue.severity == "warning"

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_none_when_complexity_below_threshold(
        self, mock_logger: Mock
    ) -> None:
        """Test returning None when complexity <= max_complexity."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        current_file = Path("/path/to/test.py")
        line = "foo(line 42) complexity 10"

        issue = adapter._parse_complexity_line(line, current_file)

        assert issue is None

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_none_on_parse_errors(self, mock_logger: Mock) -> None:
        """Test returning None on parse errors."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        current_file = Path("/path/to/test.py")
        line = "invalid line format"

        issue = adapter._parse_complexity_line(line, current_file)

        assert issue is None


class TestExtractFunctionData:
    """Test _extract_function_data() method."""

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_extracts_function_data_from_valid_line(
        self, mock_logger: Mock
    ) -> None:
        """Test extracting function data from valid line."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        line = "foo(line 42) complexity 20"
        data = adapter._extract_function_data(line)

        assert data is not None
        func_name, line_number, complexity = data
        assert func_name == "foo"
        assert line_number == 42
        assert complexity == 20

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_none_for_invalid_format(self, mock_logger: Mock) -> None:
        """Test returning None for invalid line format."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        line = "invalid line"
        data = adapter._extract_function_data(line)

        assert data is None

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_handles_missing_parenthesis(self, mock_logger: Mock) -> None:
        """Test handling missing parenthesis."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        line = "foo line 42 complexity 20"
        data = adapter._extract_function_data(line)

        assert data is None

    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_handles_missing_complexity_keyword(self, mock_logger: Mock) -> None:
        """Test handling missing 'complexity' keyword."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        line = "foo(line 42) something 20"
        data = adapter._extract_function_data(line)

        assert data is None


class TestGetDefaultConfig:
    """Test get_default_config() method."""

    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_qa_check_config_with_correct_fields(
        self, mock_logger: Mock, mock_path: Mock
    ) -> None:
        """Test returning QACheckConfig with correct fields."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        mock_path.cwd.return_value.exists.return_value = False

        config = adapter.get_default_config()

        assert config.check_id == MODULE_ID
        assert config.check_name == "Complexipy (Complexity)"
        assert config.check_type.value == "complexity"
        assert config.enabled is True
        assert "**/*.py" in config.file_patterns

    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_loads_exclude_patterns_from_pyproject(
        self, mock_logger: Mock, mock_path: Mock
    ) -> None:
        """Test loading exclude_patterns from pyproject.toml."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        mock_path.cwd.return_value.exists.return_value = True
        adapter._load_config_from_pyproject = Mock(
            return_value={
                "exclude_patterns": ["**/tests/**", "**/venv/**"],
                "max_complexity": 20,
            }
        )

        config = adapter.get_default_config()

        assert "**/tests/**" in config.exclude_patterns
        assert "**/venv/**" in config.exclude_patterns

    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_uses_defaults_when_pyproject_missing(
        self, mock_logger: Mock, mock_path: Mock
    ) -> None:
        """Test using defaults when pyproject.toml missing."""
        settings = ComplexipySettings(timeout_seconds=90, max_workers=4, max_complexity=15)
        adapter = ComplexipyAdapter(settings=settings)

        mock_path.cwd.return_value.exists.return_value = False
        adapter._load_config_from_pyproject = Mock(
            return_value={
                "exclude_patterns": ["**/.venv/**", "**/venv/**", "**/tests/**"],
                "max_complexity": 15,
            }
        )

        config = adapter.get_default_config()

        assert config.settings["max_complexity"] == 15


class TestLoadConfigFromPyproject:
    """Test _load_config_from_pyproject() method."""

    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_default_config_when_pyproject_missing(
        self, mock_logger: Mock, mock_path: Mock
    ) -> None:
        """Test returning default config when pyproject.toml missing."""
        adapter = ComplexipyAdapter()

        mock_path.cwd.return_value.exists.return_value = False

        config = adapter._load_config_from_pyproject()

        assert config["exclude_patterns"] == ["**/.venv/**", "**/venv/**", "**/tests/**"]
        assert config["max_complexity"] == 15

    @patch("tomllib.load")
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_loads_exclude_patterns_from_tool_section(
        self, mock_logger: Mock, mock_path: Mock, mock_toml_load: Mock
    ) -> None:
        """Test loading exclude_patterns from [tool.complexipy] section."""
        adapter = ComplexipyAdapter()

        mock_path.cwd.return_value.exists.return_value = True
        mock_toml_load.return_value = {
            "tool": {"complexipy": {"exclude_patterns": ["**/tests/**"]}}
        }

        config = adapter._load_config_from_pyproject()

        assert config["exclude_patterns"] == ["**/tests/**"]

    @patch("tomllib.load")
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_loads_max_complexity_from_tool_section(
        self, mock_logger: Mock, mock_path: Mock, mock_toml_load: Mock
    ) -> None:
        """Test loading max_complexity from [tool.complexipy] section."""
        adapter = ComplexipyAdapter()

        mock_path.cwd.return_value.exists.return_value = True
        mock_toml_load.return_value = {
            "tool": {"complexipy": {"max_complexity": 20}}
        }

        config = adapter._load_config_from_pyproject()

        assert config["max_complexity"] == 20

    @patch("tomllib.load")
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_handles_toml_decode_errors(self, mock_logger: Mock, mock_path: Mock, _) -> None:
        """Test handling TOML decode errors."""
        adapter = ComplexipyAdapter()

        mock_path.cwd.return_value.exists.return_value = True
        mock_path.cwd.return_value.open.side_effect = OSError("File error")

        config = adapter._load_config_from_pyproject()

        # Should return defaults on error
        assert config["max_complexity"] == 15


class TestMoveComplexipyResultsToOutputDir:
    """Test _move_complexipy_results_to_output_dir() method."""

    @patch(
        "crackerjack.adapters.complexity.complexipy.AdapterOutputPaths.cleanup_old_outputs"
    )
    @patch(
        "crackerjack.adapters.complexity.complexipy.AdapterOutputPaths.get_output_dir"
    )
    @patch("crackerjack.adapters.complexity.complexipy.shutil.move")
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_moves_newest_result_file(
        self,
        mock_logger: Mock,
        mock_path: Mock,
        mock_move: Mock,
        mock_get_output_dir: Mock,
        mock_cleanup: Mock,
    ) -> None:
        """Test moving newest result file to output dir."""
        adapter = ComplexipyAdapter()

        mock_source = Mock()
        mock_source.name = "complexipy_results_123.json"
        mock_path.cwd.return_value.glob.return_value = [mock_source]
        mock_get_output_dir.return_value = Path("/output/dir")

        result = adapter._move_complexipy_results_to_output_dir()

        mock_move.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch(
        "crackerjack.adapters.complexity.complexipy.AdapterOutputPaths.get_output_dir"
    )
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_none_when_no_result_files(
        self, mock_logger: Mock, mock_path: Mock, mock_get_output_dir: Mock
    ) -> None:
        """Test returning None when no result files found."""
        adapter = ComplexipyAdapter()

        mock_path.cwd.return_value.glob.return_value = []

        result = adapter._move_complexipy_results_to_output_dir()

        assert result is None

    @patch(
        "crackerjack.adapters.complexity.complexipy.AdapterOutputPaths.get_output_dir"
    )
    @patch("crackerjack.adapters.complexity.complexipy.shutil.move")
    @patch("crackerjack.adapters.complexity.complexipy.Path")
    @patch("crackerjack.adapters.complexity.complexipy.logger")
    def test_returns_original_file_path_on_move_error(
        self, mock_logger: Mock, mock_path: Mock, mock_move: Mock, mock_get_output_dir: Mock
    ) -> None:
        """Test returning original file path on move error."""
        adapter = ComplexipyAdapter()

        mock_source = Mock()
        mock_source.name = "complexipy_results_123.json"
        mock_path.cwd.return_value.glob.return_value = [mock_source]
        mock_move.side_effect = OSError("Move failed")
        mock_get_output_dir.return_value = Path("/output/dir")

        result = adapter._move_complexipy_results_to_output_dir()

        # Should return original file path on error
        assert result is not None
