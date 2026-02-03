from dataclasses import dataclass
from enum import Enum


class OutputFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ToolConfig:
    name: str
    supports_json: bool
    json_flag: str | None = None
    output_format: OutputFormat = OutputFormat.JSON
    fallback_to_regex: bool = True
    required_json_fields: frozenset[str] = frozenset()


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
    return TOOL_CONFIGS.get(tool_name)


def supports_json(tool_name: str) -> bool:
    config = get_tool_config(tool_name)
    return config.supports_json if config else False


def get_json_flag(tool_name: str) -> str | None:
    config = get_tool_config(tool_name)
    return config.json_flag if config else None
