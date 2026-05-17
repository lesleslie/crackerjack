"""Tests for tool_config module."""

from __future__ import annotations

import pytest

from crackerjack.models.tool_config import (
    OutputFormat,
    ToolConfig,
    TOOL_CONFIGS,
    get_json_flag,
    get_tool_config,
    supports_json,
)


class TestOutputFormat:
    """Tests for OutputFormat StrEnum."""

    def test_enum_values(self) -> None:
        """Verify all OutputFormat values."""
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.TEXT.value == "text"
        assert OutputFormat.CUSTOM.value == "custom"

    def test_enum_members(self) -> None:
        """Verify all OutputFormat members exist."""
        members = {member.value for member in OutputFormat}
        assert members == {"json", "text", "custom"}

    def test_enum_is_str_enum(self) -> None:
        """Verify OutputFormat is a StrEnum."""
        assert isinstance(OutputFormat.JSON, str)
        assert OutputFormat.JSON == "json"
        assert OutputFormat.TEXT == "text"

    def test_enum_iteration(self) -> None:
        """Verify can iterate over all formats."""
        formats = list(OutputFormat)
        assert len(formats) == 3
        assert OutputFormat.JSON in formats
        assert OutputFormat.TEXT in formats
        assert OutputFormat.CUSTOM in formats

    def test_enum_comparison(self) -> None:
        """Verify enum comparison with strings."""
        assert OutputFormat.JSON == "json"
        assert OutputFormat.TEXT != "json"
        assert OutputFormat.CUSTOM == "custom"


class TestToolConfig:
    """Tests for ToolConfig dataclass."""

    def test_minimal_tool_config(self) -> None:
        """Verify minimal ToolConfig creation."""
        config = ToolConfig(
            name="test-tool",
            supports_json=True,
        )
        assert config.name == "test-tool"
        assert config.supports_json is True
        assert config.json_flag is None
        assert config.output_format == OutputFormat.JSON
        assert config.fallback_to_regex is True
        assert config.required_json_fields == frozenset()

    def test_tool_config_full(self) -> None:
        """Verify ToolConfig with all fields."""
        required_fields = frozenset({"file", "line", "message"})
        config = ToolConfig(
            name="mypy",
            supports_json=True,
            json_flag="--output=json",
            output_format=OutputFormat.JSON,
            fallback_to_regex=False,
            required_json_fields=required_fields,
        )
        assert config.name == "mypy"
        assert config.supports_json is True
        assert config.json_flag == "--output=json"
        assert config.output_format == OutputFormat.JSON
        assert config.fallback_to_regex is False
        assert config.required_json_fields == required_fields

    def test_tool_config_no_json_support(self) -> None:
        """Verify ToolConfig for tool without JSON support."""
        config = ToolConfig(
            name="ruff-format",
            supports_json=False,
            output_format=OutputFormat.TEXT,
            fallback_to_regex=True,
        )
        assert config.supports_json is False
        assert config.json_flag is None
        assert config.output_format == OutputFormat.TEXT
        assert config.fallback_to_regex is True

    def test_tool_config_frozen(self) -> None:
        """Verify ToolConfig is frozen (immutable)."""
        config = ToolConfig(
            name="test",
            supports_json=True,
        )
        with pytest.raises(AttributeError):
            config.name = "modified"  # type: ignore

    def test_tool_config_required_json_fields_frozenset(self) -> None:
        """Verify required_json_fields is a frozenset."""
        fields = frozenset({"filename", "location", "code", "message"})
        config = ToolConfig(
            name="ruff",
            supports_json=True,
            required_json_fields=fields,
        )
        assert isinstance(config.required_json_fields, frozenset)
        assert len(config.required_json_fields) == 4
        assert "filename" in config.required_json_fields

    def test_tool_config_required_json_fields_immutable(self) -> None:
        """Verify required_json_fields frozenset is immutable."""
        config = ToolConfig(
            name="test",
            supports_json=True,
            required_json_fields=frozenset({"field1", "field2"}),
        )
        with pytest.raises(AttributeError):
            config.required_json_fields.add("field3")  # type: ignore

    def test_tool_config_all_output_formats(self) -> None:
        """Verify ToolConfig works with all OutputFormat values."""
        for output_format in OutputFormat:
            config = ToolConfig(
                name="test",
                supports_json=True,
                output_format=output_format,
            )
            assert config.output_format == output_format

    def test_tool_config_empty_json_fields(self) -> None:
        """Verify ToolConfig with empty required_json_fields."""
        config = ToolConfig(
            name="test",
            supports_json=False,
            required_json_fields=frozenset(),
        )
        assert config.required_json_fields == frozenset()
        assert len(config.required_json_fields) == 0


class TestToolConfigsRegistry:
    """Tests for TOOL_CONFIGS registry."""

    def test_tool_configs_is_dict(self) -> None:
        """Verify TOOL_CONFIGS is a dictionary."""
        assert isinstance(TOOL_CONFIGS, dict)

    def test_tool_configs_all_entries_valid(self) -> None:
        """Verify all TOOL_CONFIGS entries are ToolConfig instances."""
        for name, config in TOOL_CONFIGS.items():
            assert isinstance(name, str)
            assert isinstance(config, ToolConfig)
            assert config.name == name

    def test_tool_configs_contains_major_tools(self) -> None:
        """Verify TOOL_CONFIGS contains expected tools."""
        expected_tools = {
            "ruff",
            "ruff-check",
            "ruff-format",
            "mypy",
            "bandit",
            "semgrep",
            "pylint",
        }
        for tool in expected_tools:
            assert tool in TOOL_CONFIGS

    def test_tool_configs_total_count(self) -> None:
        """Verify expected number of tool configurations."""
        assert len(TOOL_CONFIGS) == 15

    def test_tool_config_ruff(self) -> None:
        """Verify ruff configuration."""
        config = TOOL_CONFIGS["ruff"]
        assert config.name == "ruff"
        assert config.supports_json is True
        assert config.json_flag == "--output-format=json"
        assert config.output_format == OutputFormat.JSON
        assert config.required_json_fields == frozenset(
            {"filename", "location", "code", "message"}
        )

    def test_tool_config_ruff_check(self) -> None:
        """Verify ruff-check configuration."""
        config = TOOL_CONFIGS["ruff-check"]
        assert config.name == "ruff-check"
        assert config.supports_json is True
        assert config.json_flag == "--output-format=json"

    def test_tool_config_ruff_format(self) -> None:
        """Verify ruff-format configuration."""
        config = TOOL_CONFIGS["ruff-format"]
        assert config.name == "ruff-format"
        assert config.supports_json is False
        assert config.json_flag is None
        assert config.output_format == OutputFormat.TEXT

    def test_tool_config_mypy(self) -> None:
        """Verify mypy configuration."""
        config = TOOL_CONFIGS["mypy"]
        assert config.name == "mypy"
        assert config.supports_json is True
        assert config.json_flag == "--output=json"
        assert config.required_json_fields == frozenset({"file", "line", "message"})

    def test_tool_config_bandit(self) -> None:
        """Verify bandit configuration."""
        config = TOOL_CONFIGS["bandit"]
        assert config.name == "bandit"
        assert config.supports_json is True
        assert config.json_flag == "-f json"
        assert config.required_json_fields == frozenset(
            {"filename", "issue_text", "line_number"}
        )

    def test_tool_config_semgrep(self) -> None:
        """Verify semgrep configuration."""
        config = TOOL_CONFIGS["semgrep"]
        assert config.name == "semgrep"
        assert config.supports_json is True
        assert config.json_flag == "--json"

    def test_tool_config_pylint(self) -> None:
        """Verify pylint configuration."""
        config = TOOL_CONFIGS["pylint"]
        assert config.name == "pylint"
        assert config.supports_json is True
        assert config.json_flag == "--output-format=json"

    def test_tool_config_codespell(self) -> None:
        """Verify codespell configuration."""
        config = TOOL_CONFIGS["codespell"]
        assert config.name == "codespell"
        assert config.supports_json is False
        assert config.output_format == OutputFormat.TEXT

    def test_all_configs_have_required_fields(self) -> None:
        """Verify all configs with supports_json=True have json_flag."""
        for name, config in TOOL_CONFIGS.items():
            if config.supports_json:
                assert config.json_flag is not None, f"{name} supports JSON but has no json_flag"

    def test_all_configs_without_json_have_fallback(self) -> None:
        """Verify configs without JSON support have fallback_to_regex=True."""
        for name, config in TOOL_CONFIGS.items():
            if not config.supports_json:
                assert (
                    config.fallback_to_regex is True
                ), f"{name} doesn't support JSON but fallback_to_regex is False"


class TestGetToolConfig:
    """Tests for get_tool_config function."""

    def test_get_tool_config_exists(self) -> None:
        """Verify get_tool_config returns config for known tool."""
        config = get_tool_config("ruff")
        assert config is not None
        assert config.name == "ruff"
        assert config.supports_json is True

    def test_get_tool_config_mypy(self) -> None:
        """Verify get_tool_config for mypy."""
        config = get_tool_config("mypy")
        assert config is not None
        assert config.json_flag == "--output=json"

    def test_get_tool_config_not_found(self) -> None:
        """Verify get_tool_config returns None for unknown tool."""
        config = get_tool_config("nonexistent-tool")
        assert config is None

    def test_get_tool_config_case_sensitive(self) -> None:
        """Verify get_tool_config is case-sensitive."""
        config = get_tool_config("RUFF")
        assert config is None

    def test_get_tool_config_all_known_tools(self) -> None:
        """Verify get_tool_config works for all registered tools."""
        for tool_name in TOOL_CONFIGS.keys():
            config = get_tool_config(tool_name)
            assert config is not None
            assert config.name == tool_name

    def test_get_tool_config_empty_string(self) -> None:
        """Verify get_tool_config with empty string."""
        config = get_tool_config("")
        assert config is None

    def test_get_tool_config_returns_same_instance(self) -> None:
        """Verify get_tool_config returns the actual registry instance."""
        config1 = get_tool_config("ruff")
        config2 = get_tool_config("ruff")
        assert config1 is config2


class TestSupportsJson:
    """Tests for supports_json function."""

    def test_supports_json_true(self) -> None:
        """Verify supports_json returns True for JSON-supporting tools."""
        assert supports_json("ruff") is True
        assert supports_json("mypy") is True
        assert supports_json("bandit") is True

    def test_supports_json_false(self) -> None:
        """Verify supports_json returns False for non-JSON tools."""
        assert supports_json("ruff-format") is False
        assert supports_json("codespell") is False
        assert supports_json("refurb") is False

    def test_supports_json_unknown_tool(self) -> None:
        """Verify supports_json returns False for unknown tool."""
        assert supports_json("unknown-tool") is False
        assert supports_json("") is False

    def test_supports_json_case_sensitive(self) -> None:
        """Verify supports_json is case-sensitive."""
        assert supports_json("RUFF") is False
        assert supports_json("Mypy") is False

    def test_supports_json_all_json_tools(self) -> None:
        """Verify all JSON-supporting tools return True."""
        for name, config in TOOL_CONFIGS.items():
            if config.supports_json:
                assert supports_json(name) is True

    def test_supports_json_all_text_tools(self) -> None:
        """Verify all non-JSON tools return False."""
        for name, config in TOOL_CONFIGS.items():
            if not config.supports_json:
                assert supports_json(name) is False


class TestGetJsonFlag:
    """Tests for get_json_flag function."""

    def test_get_json_flag_exists(self) -> None:
        """Verify get_json_flag returns flag for JSON-supporting tools."""
        assert get_json_flag("ruff") == "--output-format=json"
        assert get_json_flag("mypy") == "--output=json"
        assert get_json_flag("bandit") == "-f json"

    def test_get_json_flag_no_support(self) -> None:
        """Verify get_json_flag returns None for non-JSON tools."""
        assert get_json_flag("ruff-format") is None
        assert get_json_flag("codespell") is None
        assert get_json_flag("refurb") is None

    def test_get_json_flag_unknown_tool(self) -> None:
        """Verify get_json_flag returns None for unknown tool."""
        assert get_json_flag("nonexistent-tool") is None
        assert get_json_flag("") is None

    def test_get_json_flag_case_sensitive(self) -> None:
        """Verify get_json_flag is case-sensitive."""
        assert get_json_flag("RUFF") is None
        assert get_json_flag("Mypy") is None

    def test_get_json_flag_all_json_tools(self) -> None:
        """Verify all JSON-supporting tools have json_flag."""
        for name, config in TOOL_CONFIGS.items():
            if config.supports_json:
                flag = get_json_flag(name)
                assert flag is not None
                assert flag == config.json_flag

    def test_get_json_flag_various_formats(self) -> None:
        """Verify different JSON flag formats."""
        flags = {
            "ruff": "--output-format=json",
            "mypy": "--output=json",
            "bandit": "-f json",
            "complexipy": "--output-json",
            "semgrep": "--json",
            "pip-audit": "--format=json",
            "gitleaks": "--report-format=json",
            "pylint": "--output-format=json",
        }
        for tool, expected_flag in flags.items():
            assert get_json_flag(tool) == expected_flag
