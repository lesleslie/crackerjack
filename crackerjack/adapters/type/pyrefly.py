from __future__ import annotations

import json
import logging
import typing as t
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from crackerjack.adapters._tool_adapter_base import (
    BaseToolAdapter,
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


MODULE_ID = UUID("54d80e25-4f7b-4362-8a94-44dc2aae3d0b")
MODULE_STATUS = AdapterStatus.BETA


logger = logging.getLogger(__name__)


class PyreflySettings(ToolAdapterSettings):
    tool_name: str = "pyrefly"
    output_format: str = "json"
    summary: str = "none"
    no_progress_bar: bool = True
    baseline_file: Path | None = None
    update_baseline: bool = False
    suppress_errors: bool = False
    remove_unused_ignores: bool = False


class PyreflyAdapter(BaseToolAdapter):
    settings: PyreflySettings | None = None

    def __init__(self, settings: PyreflySettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "PyreflyAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = PyreflySettings(
                timeout_seconds=180,
                max_workers=4,
            )
            logger.info("Using default PyreflySettings")
        await super().init()
        logger.debug(
            "PyreflyAdapter initialization complete",
            extra={
                "output_format": self.settings.output_format,
                "summary": self.settings.summary,
                "baseline_file": str(self.settings.baseline_file)
                if self.settings.baseline_file
                else None,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Pyrefly (Type Check)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "pyrefly"

    def supports_fix(self) -> bool:
        return False

    def supports_suppress(self) -> bool:
        return True

    def supports_baseline(self) -> bool:
        return True

    def supports_json_output(self) -> bool:
        return True

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        cmd = [
            self.tool_name,
            "check",
            "--output-format",
            self.settings.output_format,
        ]

        if self.settings.summary:
            cmd.extend(["--summary", self.settings.summary])

        if self.settings.no_progress_bar:
            cmd.append("--no-progress-bar")

        if self.settings.baseline_file:
            cmd.extend(["--baseline", str(self.settings.baseline_file)])

        if self.settings.update_baseline:
            cmd.append("--update-baseline")

        if self.settings.suppress_errors:
            cmd.append("--suppress-errors")

        if self.settings.remove_unused_ignores:
            cmd.append("--remove-unused-ignores")

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Pyrefly command",
            extra={
                "file_count": len(files),
                "output_format": self.settings.output_format,
                "summary": self.settings.summary,
                "baseline_file": str(self.settings.baseline_file)
                if self.settings.baseline_file
                else None,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        try:
            data = json.loads(result.raw_output)
            logger.debug(
                "Parsed Pyrefly JSON output",
                extra={"payload_type": type(data).__name__},
            )
        except json.JSONDecodeError as e:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = self._parse_json_output(data)

        logger.info(
            "Parsed Pyrefly output",
            extra={
                "total_issues": len(issues),
                "errors": sum(1 for i in issues if i.severity == "error"),
                "warnings": sum(1 for i in issues if i.severity == "warning"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_json_output(self, data: t.Any) -> list[ToolIssue]:
        issues: list[ToolIssue] = []

        if isinstance(data, dict):
            if isinstance(data.get("errors"), list):
                issues.extend(self._parse_error_items(data["errors"]))
            elif isinstance(data.get("diagnostics"), list):
                issues.extend(self._parse_error_items(data["diagnostics"]))
            elif isinstance(data.get("files"), list):
                for file_data in data["files"]:
                    if not isinstance(file_data, dict):
                        continue
                    file_path = Path(str(file_data.get("path", "")))
                    errors = file_data.get("errors", [])
                    if isinstance(errors, list):
                        issues.extend(
                            self._parse_error_items(errors, default_path=file_path),
                        )
        elif isinstance(data, list):
            issues.extend(self._parse_error_items(data))

        return issues

    def _parse_error_items(
        self,
        items: list[t.Any],
        default_path: Path | None = None,
    ) -> list[ToolIssue]:
        issues: list[ToolIssue] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            file_path = default_path or Path(
                str(item.get("path", item.get("file", "")))
            )
            line_number = self._parse_int(item.get("line"))
            column_number = self._parse_int(item.get("column"))
            message = self._extract_message_from_item(item)
            code = self._extract_code_from_item(item)
            severity = self._normalize_severity(str(item.get("severity", "error")))

            issues.append(
                ToolIssue(
                    file_path=file_path,
                    line_number=line_number,
                    column_number=column_number,
                    message=message,
                    code=code,
                    severity=severity,
                ),
            )

        return issues

    def _parse_int(self, value: t.Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    def _extract_message_from_item(self, item: dict[str, t.Any]) -> str:
        for key in ("concise_description", "description", "message"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _extract_code_from_item(self, item: dict[str, t.Any]) -> str | None:
        for key in ("name", "code"):
            value = item.get(key)
            if value is None:
                continue
            code = str(value).strip()
            if code:
                return code
        return None

    def _normalize_severity(self, severity: str) -> str:
        lowered = severity.lower()
        if lowered == "warning":
            return "warning"
        if lowered in {"info", "information"}:
            return "info"
        return "error"

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            if ":" not in line:
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Pyrefly text output (fallback)",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_text_line(self, line: str) -> ToolIssue | None:
        parts = line.split(":", maxsplit=4)
        if len(parts) < 4:
            return None

        try:
            file_path = Path(parts[0].strip())
            line_number = int(parts[1].strip())
            column_number = (
                int(parts[2].strip()) if parts[2].strip().isdigit() else None
            )

            severity_and_message = parts[3].strip() if len(parts) > 3 else ""
            message = parts[4].strip() if len(parts) > 4 else ""

            severity = self._parse_severity(severity_and_message)
            message = self._extract_message(severity_and_message, message, severity)

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                severity=severity,
            )

        except (ValueError, IndexError):
            return None

    def _parse_severity(self, severity_and_message: str) -> str:
        if severity_and_message.lower().startswith("warning"):
            return "warning"
        return "error"

    def _extract_message(
        self,
        severity_and_message: str,
        message: str,
        severity: str,
    ) -> str:
        if message:
            return message

        if severity_and_message.lower().startswith(severity):
            return severity_and_message[len(severity) :].strip()

        return severity_and_message

    def _get_check_type(self) -> QACheckType:
        return QACheckType.TYPE

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        current_dir = Path.cwd()
        package_dir = "crackerjack"

        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.exists():
            with suppress(Exception):
                import tomllib

                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                if "project" in data and "name" in data["project"]:
                    package_name = str(data["project"]["name"]).replace("-", "_")
                    if (current_dir / package_name).exists():
                        package_dir = package_name

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.TYPE,
            enabled=False,
            file_patterns=[f"{package_dir}/**/*.py"],
            exclude_patterns=[
                "**/test_*.py",
                "**/tests/**",
                "**/.venv/**",
                "**/venv/**",
                "**/build/**",
                "**/dist/**",
                "**/__pycache__/**",
                "**/.git/**",
                "**/node_modules/**",
                "**/.tox/**",
                "**/.pytest_cache/**",
                "**/htmlcov/**",
                "**/.coverage*",
                "**/worktrees/**",
            ],
            timeout_seconds=180,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "output_format": "json",
                "summary": "none",
                "no_progress_bar": True,
                "baseline_file": None,
                "update_baseline": False,
                "suppress_errors": False,
                "remove_unused_ignores": False,
            },
        )
