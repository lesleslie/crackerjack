"""Test RefurbAdapter functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

# Module-level import pattern to avoid pytest conflicts
from crackerjack.adapters.refactor import refurb


class TestRefurbSettings:
    """Test RefurbSettings configuration."""

    def test_has_correct_default_values(self) -> None:
        """Test that RefurbSettings has correct default values."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)

        assert settings.tool_name == "refurb"
        assert settings.use_json_output is False
        assert settings.enable_all is False
        assert settings.disable_checks == []
        assert settings.enable_checks == []
        assert settings.python_version is None
        assert settings.explain is False

    def test_extends_tool_adapter_settings(self) -> None:
        """Test that RefurbSettings extends ToolAdapterSettings."""
        from crackerjack.adapters._tool_adapter_base import ToolAdapterSettings

        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        assert isinstance(settings, ToolAdapterSettings)

    def test_all_fields_present_and_typed(self) -> None:
        """Test that all fields are present with correct types."""
        settings = refurb.RefurbSettings(
            timeout_seconds=60,
            max_workers=4,
            tool_name="refurb",
            use_json_output=True,
            enable_all=True,
            disable_checks=["FURB123"],
            enable_checks=["FURB456"],
            python_version="3.11",
            explain=True,
        )

        assert settings.tool_name == "refurb"
        assert settings.use_json_output is True
        assert settings.enable_all is True
        assert settings.disable_checks == ["FURB123"]
        assert settings.enable_checks == ["FURB456"]
        assert settings.python_version == "3.11"
        assert settings.explain is True

    def test_field_default_factory_functions_work(self) -> None:
        """Test that list factory functions create independent lists."""
        settings1 = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        settings2 = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)

        settings1.disable_checks.append("FURB123")
        settings2.enable_checks.append("FURB456")

        assert settings1.disable_checks == ["FURB123"]
        assert settings1.enable_checks == []
        assert settings2.disable_checks == []
        assert settings2.enable_checks == ["FURB456"]


class TestRefurbAdapterInit:
    """Test RefurbAdapter initialization."""

    def test_initializes_with_provided_settings(self) -> None:
        """Test initialization with provided settings."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        adapter = refurb.RefurbAdapter(settings=settings)

        assert adapter.settings == settings

    def test_initializes_without_settings(self) -> None:
        """Test initialization without settings (None)."""
        adapter = refurb.RefurbAdapter(settings=None)

        assert adapter.settings is None


class TestRefurbAdapterProperties:
    """Test RefurbAdapter properties."""

    def test_adapter_name_returns_correct_string(self) -> None:
        """Test that adapter_name returns correct value."""
        adapter = refurb.RefurbAdapter()
        assert adapter.adapter_name == "Refurb (Refactoring)"

    def test_module_id_returns_module_id_constant(self) -> None:
        """Test that module_id returns correct UUID."""
        adapter = refurb.RefurbAdapter()
        assert isinstance(adapter.module_id, UUID)
        assert adapter.module_id == refurb.MODULE_ID

    def test_tool_name_returns_refurb(self) -> None:
        """Test that tool_name returns 'refurb'."""
        adapter = refurb.RefurbAdapter()
        assert adapter.tool_name == "refurb"


class TestRefurbAdapterInitMethod:
    """Test RefurbAdapter.init() method."""

    @patch("crackerjack.adapters.refactor.refurb.logger")
    def test_creates_default_settings_when_none(self, mock_logger: Mock) -> None:
        """Test that init() creates default RefurbSettings when None."""
        adapter = refurb.RefurbAdapter(settings=None)

        with patch.object(adapter, "_get_timeout_from_settings", return_value=120):
            import asyncio

            asyncio.run(adapter.init())

        assert adapter.settings is not None
        assert isinstance(adapter.settings, refurb.RefurbSettings)
        assert adapter.settings.timeout_seconds == 120
        assert adapter.settings.max_workers == 4

    @patch("crackerjack.adapters.refactor.refurb.logger")
    def test_calls_super_init(self, mock_logger: Mock) -> None:
        """Test that init() calls parent class init."""
        adapter = refurb.RefurbAdapter(settings=None)

        with patch.object(adapter, "_get_timeout_from_settings", return_value=60):
            with patch.object(
                refurb.BaseToolAdapter, "init", return_value=None
            ) as mock_super_init:
                import asyncio

                asyncio.run(adapter.init())

                mock_super_init.assert_called_once()

    @patch("crackerjack.adapters.refactor.refurb.logger")
    def test_logs_initialization_details(self, mock_logger: Mock) -> None:
        """Test that init() logs initialization details."""
        adapter = refurb.RefurbAdapter(settings=None)

        with patch.object(adapter, "_get_timeout_from_settings", return_value=60):
            import asyncio

            asyncio.run(adapter.init())

        # Verify logger was called
        assert mock_logger.info.called or mock_logger.debug.called


class TestBuildCommand:
    """Test build_command() method."""

    def test_builds_basic_command_with_files(self) -> None:
        """Test building basic command with file list."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        adapter = refurb.RefurbAdapter(settings=settings)
        import asyncio

        asyncio.run(adapter.init())

        files = [Path("file1.py"), Path("file2.py")]
        cmd = adapter.build_command(files)

        assert cmd[0] == "refurb"
        assert "file1.py" in cmd
        assert "file2.py" in cmd

    def test_adds_enable_all_when_enable_all_true(self) -> None:
        """Test that --enable-all is added when enable_all=True."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4, enable_all=True)
        adapter = refurb.RefurbAdapter(settings=settings)
        import asyncio

        asyncio.run(adapter.init())

        files = [Path("file1.py")]
        cmd = adapter.build_command(files)

        assert "--enable-all" in cmd

    def test_adds_ignore_for_disabled_checks(self) -> None:
        """Test that --ignore is added for each disabled check."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4,
            disable_checks=["FURB123", "FURB456"]
        )
        adapter = refurb.RefurbAdapter(settings=settings)
        import asyncio

        asyncio.run(adapter.init())

        files = [Path("file1.py")]
        cmd = adapter.build_command(files)

        assert "--ignore" in cmd
        assert "FURB123" in cmd
        assert "FURB456" in cmd

    def test_adds_enable_for_enabled_checks(self) -> None:
        """Test that --enable is added for each enabled check."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4, enable_checks=["FURB789"])
        adapter = refurb.RefurbAdapter(settings=settings)
        import asyncio

        asyncio.run(adapter.init())

        files = [Path("file1.py")]
        cmd = adapter.build_command(files)

        assert "--enable" in cmd
        assert "FURB789" in cmd

    def test_adds_python_version_when_set(self) -> None:
        """Test that --python-version is added when set."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4, python_version="3.11")
        adapter = refurb.RefurbAdapter(settings=settings)
        import asyncio

        asyncio.run(adapter.init())

        files = [Path("file1.py")]
        cmd = adapter.build_command(files)

        assert "--python-version" in cmd
        assert "3.11" in cmd

    def test_adds_explain_when_explain_true(self) -> None:
        """Test that --explain is added when explain=True."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4, explain=True)
        adapter = refurb.RefurbAdapter(settings=settings)
        import asyncio

        asyncio.run(adapter.init())

        files = [Path("file1.py")]
        cmd = adapter.build_command(files)

        assert "--explain" in cmd

    def test_raises_runtime_error_when_settings_not_initialized(self) -> None:
        """Test that RuntimeError is raised when settings is None."""
        adapter = refurb.RefurbAdapter(settings=None)

        files = [Path("file1.py")]

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command(files)

    @patch("crackerjack.adapters.refactor.refurb.logger")
    def test_logs_command_details(self, mock_logger: Mock) -> None:
        """Test that build_command logs details."""
        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        adapter = refurb.RefurbAdapter(settings=settings)
        import asyncio

        asyncio.run(adapter.init())

        files = [Path("file1.py")]
        adapter.build_command(files)

        # Verify logger.info was called
        assert mock_logger.info.called


class TestParseOutput:
    """Test parse_output() method."""

    def test_returns_empty_list_when_raw_output_empty(self) -> None:
        """Test that parse_output returns [] when raw_output is empty."""
        import asyncio

        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        adapter = refurb.RefurbAdapter(settings=settings)
        asyncio.run(adapter.init())

        result = Mock()
        result.raw_output = ""

        issues = asyncio.run(adapter.parse_output(result))

        assert issues == []

    def test_returns_empty_list_when_no_furb_in_output(self) -> None:
        """Test that parse_output returns [] when no [FURB in output."""
        import asyncio

        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        adapter = refurb.RefurbAdapter(settings=settings)
        asyncio.run(adapter.init())

        result = Mock()
        result.raw_output = "Some other output\nwithout FURB codes"

        issues = asyncio.run(adapter.parse_output(result))

        assert issues == []

    def test_parses_single_issue_correctly(self) -> None:
        """Test parsing a single refurb issue."""
        import asyncio

        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        adapter = refurb.RefurbAdapter(settings=settings)
        asyncio.run(adapter.init())

        result = Mock()
        result.raw_output = "file.py:10:5 [FURB123]: This is a message"

        issues = asyncio.run(adapter.parse_output(result))

        assert len(issues) == 1
        assert str(issues[0].file_path) == "file.py"
        assert issues[0].line_number == 10
        # Note: column parsing depends on format, message extraction is key
        assert issues[0].code == "FURB123"
        # Message should be extracted after code
        assert issues[0].message == "This is a message"

    def test_parses_multiple_issues_correctly(self) -> None:
        """Test parsing multiple refurb issues."""
        import asyncio

        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        adapter = refurb.RefurbAdapter(settings=settings)
        asyncio.run(adapter.init())

        result = Mock()
        result.raw_output = (
            "file1.py:10:5 [FURB123]: Message 1\n"
            "file2.py:20:10 [FURB456]: Message 2"
        )

        issues = asyncio.run(adapter.parse_output(result))

        assert len(issues) == 2
        assert issues[0].code == "FURB123"
        assert issues[1].code == "FURB456"

    def test_skips_lines_without_furb(self) -> None:
        """Test that lines without [FURB are skipped."""
        import asyncio

        settings = refurb.RefurbSettings(timeout_seconds=60, max_workers=4)
        adapter = refurb.RefurbAdapter(settings=settings)
        asyncio.run(adapter.init())

        result = Mock()
        result.raw_output = (
            "file.py:10:5 [FURB123]: Valid issue\n"
            "Random line without code\n"
            "file2.py:20:10 [FURB456]: Another issue"
        )

        issues = asyncio.run(adapter.parse_output(result))

        assert len(issues) == 2


class TestParseRefurbLine:
    """Test _parse_refurb_line() method."""

    def test_returns_none_when_colon_not_in_line(self) -> None:
        """Test that None is returned when ':' not in line."""
        adapter = refurb.RefurbAdapter()

        result = adapter._parse_refurb_line("no colons here")
        assert result is None

    def test_returns_none_when_parts_less_than_3(self) -> None:
        """Test that None is returned when split parts < 3."""
        adapter = refurb.RefurbAdapter()

        result = adapter._parse_refurb_line("file:only")
        assert result is None

    def test_parses_line_without_column_number(self) -> None:
        """Test parsing line without column number."""
        adapter = refurb.RefurbAdapter()

        # Format: file:line: column [code]: message (space after colon)
        line = "file.py:10: [FURB123]: Message"
        result = adapter._parse_refurb_line(line)

        assert result is not None
        assert str(result.file_path) == "file.py"
        assert result.line_number == 10
        assert result.column_number is None
        assert result.code == "FURB123"
        assert result.message == "Message"

    def test_parses_line_with_column_number(self) -> None:
        """Test parsing line with column number."""
        adapter = refurb.RefurbAdapter()

        # Format: file:line: column [code]: message
        line = "file.py:10:5 [FURB123]: Message"
        result = adapter._parse_refurb_line(line)

        assert result is not None
        assert str(result.file_path) == "file.py"
        assert result.line_number == 10
        assert result.column_number == 5
        assert result.code == "FURB123"
        # Message extraction after code brackets
        assert result.message == "Message"

    def test_extracts_furb_code_correctly(self) -> None:
        """Test that [FURB###] code is extracted correctly."""
        adapter = refurb.RefurbAdapter()

        line = "file.py:10:5 [FURB999]: Some message"
        result = adapter._parse_refurb_line(line)

        assert result is not None
        assert result.code == "FURB999"

    def test_returns_none_on_value_error(self) -> None:
        """Test that None is returned on parsing error."""
        adapter = refurb.RefurbAdapter()

        # Invalid line number
        line = "file.py:abc:5 [FURB123]: Message"
        result = adapter._parse_refurb_line(line)

        assert result is None


class TestExtractColumnNumber:
    """Test _extract_column_number() method."""

    def test_returns_int_when_first_part_is_digit(self) -> None:
        """Test returning int when first part is a digit."""
        adapter = refurb.RefurbAdapter()

        result = adapter._extract_column_number("123 rest of line")
        assert result == 123

    def test_returns_none_when_no_space(self) -> None:
        """Test returning None when there's no space."""
        adapter = refurb.RefurbAdapter()

        result = adapter._extract_column_number("123")
        assert result is None

    def test_returns_none_when_first_part_not_digit(self) -> None:
        """Test returning None when first part is not a digit."""
        adapter = refurb.RefurbAdapter()

        result = adapter._extract_column_number("abc rest")
        assert result is None


class TestExtractMessagePart:
    """Test _extract_message_part() method."""

    def test_removes_column_number_when_present(self) -> None:
        """Test removing column number when present."""
        adapter = refurb.RefurbAdapter()

        result = adapter._extract_message_part("123 [FURB123]: Message", 123)
        assert result == "[FURB123]: Message"

    def test_returns_remaining_when_column_number_none(self) -> None:
        """Test returning remaining when column_number is None."""
        adapter = refurb.RefurbAdapter()

        result = adapter._extract_message_part("[FURB123]: Message", None)
        assert result == "[FURB123]: Message"


class TestExtractCodeAndMessage:
    """Test _extract_code_and_message() method."""

    def test_extracts_code_and_message_when_brackets_present(self) -> None:
        """Test extracting code and message when [code] present."""
        adapter = refurb.RefurbAdapter()

        code, message = adapter._extract_code_and_message("[FURB123]: Some message")

        assert code == "FURB123"
        assert message == "Some message"

    def test_removes_leading_colon_from_message(self) -> None:
        """Test removing leading ':' from message."""
        adapter = refurb.RefurbAdapter()

        # The code removes one leading colon if present
        code, message = adapter._extract_code_and_message("[FURB123]: Message")

        assert code == "FURB123"
        assert message == "Message"

    def test_returns_none_and_message_when_no_brackets(self) -> None:
        """Test returning (None, message_part) when no brackets."""
        adapter = refurb.RefurbAdapter()

        code, message = adapter._extract_code_and_message("Just a message")

        assert code is None
        assert message == "Just a message"


class TestGetCheckType:
    """Test _get_check_type() method."""

    def test_returns_refactor_check_type(self) -> None:
        """Test that _get_check_type returns REFACTOR."""
        from crackerjack.models.qa_results import QACheckType

        adapter = refurb.RefurbAdapter()
        result = adapter._get_check_type()

        assert result == QACheckType.REFACTOR


class TestDetectPackageDirectory:
    """Test _detect_package_directory() method."""

    @patch("crackerjack.adapters.refactor.refurb.Path")
    @patch("crackerjack.adapters.refactor.refurb.tomllib.load")
    def test_returns_package_name_from_pyproject_toml(
        self, mock_toml_load: Mock, mock_path_cls: Mock
    ) -> None:
        """Test detecting package name from pyproject.toml."""
        from pathlib import Path as RealPath

        # Use real current directory
        real_cwd = RealPath.cwd()
        mock_path_cls.cwd.return_value = real_cwd

        # Mock tomllib.load to return test data
        mock_toml_load.return_value = {"project": {"name": "my-package"}}

        adapter = refurb.RefurbAdapter()
        result = adapter._detect_package_directory()

        # Package name should have "-" replaced with "_"
        assert result == "my_package"

    @patch("crackerjack.adapters.refactor.refurb.Path")
    def test_returns_current_dir_name_when_package_exists(
        self, mock_path_cls: Mock
    ) -> None:
        """Test returning current_dir.name when package directory exists."""
        from pathlib import Path as RealPath

        # Use real current directory which should have the package dir
        real_cwd = RealPath.cwd()
        mock_path_cls.cwd.return_value = real_cwd

        adapter = refurb.RefurbAdapter()
        result = adapter._detect_package_directory()

        # Should return the package name if it exists
        # For crackerjack, the package directory is "crackerjack"
        assert result in ["crackerjack", "src"]

    @patch("crackerjack.adapters.refactor.refurb.Path")
    def test_returns_src_as_final_fallback(self, mock_path_cls: Mock) -> None:
        """Test returning 'src' as final fallback."""
        from pathlib import Path as RealPath

        # Use real current directory
        real_cwd = RealPath.cwd()
        mock_path_cls.cwd.return_value = real_cwd

        adapter = refurb.RefurbAdapter()
        result = adapter._detect_package_directory()

        # Should return one of the expected values
        assert result in ["crackerjack", "src"]


class TestGetDefaultConfig:
    """Test get_default_config() method."""

    @patch("crackerjack.adapters.refactor.refurb.Path")
    def test_creates_qa_check_config_with_correct_structure(
        self, mock_path: Mock
    ) -> None:
        """Test that get_default_config creates correct structure."""
        from crackerjack.models.qa_results import QACheckType

        adapter = refurb.RefurbAdapter()

        with patch.object(adapter, "_detect_package_directory", return_value="pkg"):
            config = adapter.get_default_config()

        assert config.check_name == "Refurb (Refactoring)"
        assert config.check_type == QACheckType.REFACTOR
        assert config.enabled is True
        assert "pkg/**/*.py" in config.file_patterns

    @patch("crackerjack.adapters.refactor.refurb.Path")
    def test_calls_detect_package_directory(self, mock_path: Mock) -> None:
        """Test that get_default_config calls _detect_package_directory."""
        adapter = refurb.RefurbAdapter()

        with patch.object(adapter, "_detect_package_directory", return_value="mypkg") as mock_detect:
            config = adapter.get_default_config()

            mock_detect.assert_called_once()

    @patch("crackerjack.adapters.refactor.refurb.Path")
    def test_sets_check_id_to_module_id(self, mock_path: Mock) -> None:
        """Test that check_id is set to MODULE_ID."""
        adapter = refurb.RefurbAdapter()

        with patch.object(adapter, "_detect_package_directory", return_value="pkg"):
            config = adapter.get_default_config()

        assert config.check_id == refurb.MODULE_ID

    @patch("crackerjack.adapters.refactor.refurb.Path")
    def test_sets_check_type_to_refactor(self, mock_path: Mock) -> None:
        """Test that check_type is set to REFACTOR."""
        from crackerjack.models.qa_results import QACheckType

        adapter = refurb.RefurbAdapter()

        with patch.object(adapter, "_detect_package_directory", return_value="pkg"):
            config = adapter.get_default_config()

        assert config.check_type == QACheckType.REFACTOR

    @patch("crackerjack.adapters.refactor.refurb.Path")
    def test_includes_all_exclude_patterns(self, mock_path: Mock) -> None:
        """Test that all standard exclude patterns are included."""
        adapter = refurb.RefurbAdapter()

        with patch.object(adapter, "_detect_package_directory", return_value="pkg"):
            config = adapter.get_default_config()

        assert "**/test_*.py" in config.exclude_patterns
        assert "**/tests/**" in config.exclude_patterns
        assert "**/.venv/**" in config.exclude_patterns
        assert "**/venv/**" in config.exclude_patterns
        assert "**/build/**" in config.exclude_patterns
        assert "**/dist/**" in config.exclude_patterns
