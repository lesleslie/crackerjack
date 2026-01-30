"""Tool configuration for output parsing.

This module defines the configuration for each quality tool, including whether
they support JSON output and what command-line flags are needed.
"""

from dataclasses import dataclass
from enum import Enum


class OutputFormat(str, Enum):
    """Output format type for a tool."""

    JSON = "json"
    TEXT = "text"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ToolConfig:
    """Configuration for a quality tool's output parsing.

    Attributes:
        name: Tool name (e.g., "ruff", "mypy")
        supports_json: Whether the tool supports JSON output format
        json_flag: Command-line flag to enable JSON output (e.g., "--output-format=json")
        output_format: Preferred output format for this tool
        fallback_to_regex: Whether to use regex parser if JSON fails
        required_json_fields: Set of required fields for JSON validation
    """

    name: str
    supports_json: bool
    json_flag: str | None = None
    output_format: OutputFormat = OutputFormat.JSON
    fallback_to_regex: bool = True
    required_json_fields: frozenset[str] = frozenset()


# Tool configuration registry
#
# This registry defines which tools support JSON output and how to invoke them.
# When adding new tools, check their documentation for JSON output support.
#
# Common JSON output flags:
# - ruff: --output-format=json
# - mypy: --output=json
# - bandit: -f json
# - pylint: --output-format=json
# - codespell: (no JSON support)
# - refurb: (no JSON support)
TOOL_CONFIGS: dict[str, ToolConfig] = {
    "ruff": ToolConfig(
        name="ruff",
        supports_json=True,
        json_flag="--output-format=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"filename", "location", "code", "message"}),
    ),
    "ruff-check": ToolConfig(
        name="ruff-check",
        supports_json=True,
        json_flag="--output-format=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"filename", "location", "code", "message"}),
    ),
    "ruff-format": ToolConfig(
        name="ruff-format",
        supports_json=False,
        output_format=OutputFormat.TEXT,
        fallback_to_regex=True,
    ),
    "mypy": ToolConfig(
        name="mypy",
        supports_json=True,
        json_flag="--output=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"file", "line", "message"}),
    ),
    "zuban": ToolConfig(
        name="zuban",
        supports_json=True,
        json_flag="--output=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"file", "line", "message"}),
    ),
    "bandit": ToolConfig(
        name="bandit",
        supports_json=True,
        json_flag="-f json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"filename", "issue_text", "line_number"}),
    ),
    "codespell": ToolConfig(
        name="codespell",
        supports_json=False,
        output_format=OutputFormat.TEXT,
        fallback_to_regex=True,
    ),
    "refurb": ToolConfig(
        name="refurb",
        supports_json=False,
        output_format=OutputFormat.TEXT,
        fallback_to_regex=True,
    ),
    "complexity": ToolConfig(
        name="complexity",
        supports_json=False,
        output_format=OutputFormat.TEXT,
        fallback_to_regex=True,
    ),
    "complexipy": ToolConfig(
        name="complexipy",
        supports_json=True,
        json_flag="--output-json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset(
            {"complexity", "file_name", "function_name", "path"}
        ),
    ),
    "semgrep": ToolConfig(
        name="semgrep",
        supports_json=True,
        json_flag="--json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"check_id", "path", "start"}),
    ),
    "pip-audit": ToolConfig(
        name="pip-audit",
        supports_json=True,
        json_flag="--format=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"dependencies"}),
    ),
    "gitleaks": ToolConfig(
        name="gitleaks",
        supports_json=True,
        json_flag="--report-format=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"Description", "File", "RuleID"}),
    ),
    "pylint": ToolConfig(
        name="pylint",
        supports_json=True,
        json_flag="--output-format=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"path", "message", "type"}),
    ),
}


def get_tool_config(tool_name: str) -> ToolConfig | None:
    """Get configuration for a tool.

    Args:
        tool_name: Name of the tool (e.g., "ruff", "mypy")

    Returns:
        ToolConfig if found, None otherwise
    """
    return TOOL_CONFIGS.get(tool_name)


def supports_json(tool_name: str) -> bool:
    """Check if a tool supports JSON output.

    Args:
        tool_name: Name of the tool

    Returns:
        True if tool supports JSON output, False otherwise
    """
    config = get_tool_config(tool_name)
    return config.supports_json if config else False


def get_json_flag(tool_name: str) -> str | None:
    """Get the JSON output flag for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        JSON flag string (e.g., "--output-format=json") or None if not supported
    """
    config = get_tool_config(tool_name)
    return config.json_flag if config else None
