from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Maximum cyclomatic complexity a function may have before the complexity
# gates report it.
#
# pyscn >= 1.30 changed its complexity metric: the same function scores 13
# under pyscn 1.5.0 and 23 under pyscn 1.33.0 (measured on
# crackerjack/fixers/ast_transform/patterns/extract_method.py). The previous
# threshold of 15 was calibrated against the pre-1.30 metric and was never
# actually enforced -- pyscn 1.5.0 could not parse the repo's PEP 758
# `except A, B:` files, and reported no complexity violations at all.
#
# 25 matches the threshold complexipy already enforces in this repo
# (`--max-complexity-allowed 25`), so both complexity gates now express one
# policy, and no function in the tree exceeds it under the current metric.
PYSCN_MAX_COMPLEXITY = 25


class OutputFormat(StrEnum):
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
    "pyscn": ToolConfig(
        name="pyscn",
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
    "osv-scanner": ToolConfig(
        name="osv-scanner",
        supports_json=True,
        json_flag="--format=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"results"}),
    ),
    "gitleaks": ToolConfig(
        name="gitleaks",
        supports_json=True,
        json_flag="--report-format=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"Description", "File", "RuleID"}),
    ),
    "betterleaks": ToolConfig(
        name="betterleaks",
        supports_json=True,
        json_flag="--report-format=json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"Description", "File", "RuleID"}),
    ),
    "check-jsonschema": ToolConfig(
        name="check-jsonschema",
        supports_json=True,
        json_flag="-o json",
        output_format=OutputFormat.JSON,
        required_json_fields=frozenset({"success", "errors"}),
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
