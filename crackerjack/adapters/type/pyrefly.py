from __future__ import annotations

import json
import logging
import typing as t
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


MODULE_ID = UUID("25e1e5cf-d1f8-485e-85ab-01c8b540734a")
MODULE_STATUS = AdapterStatus.BETA


logger = logging.getLogger(__name__)


class PyreflySettings(ToolAdapterSettings):
    tool_name: str = "pyrefly"
    use_json_output: bool = True
    strict_mode: bool = False
    ignore_missing_imports: bool = False
    follow_imports: str = "normal"
    incremental: bool = True
    warn_unused_ignores: bool = True


class PyreflyAdapter(BaseToolAdapter):
    settings: PyreflySettings | None = None

    def __init__(self, settings: PyreflySettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "PyreflyAdapter initialized", extra={"has_settings": settings is not None}
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
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
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

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        if self.settings.use_json_output:
            cmd.extend(["--format", "json"])

        if self.settings.strict_mode:
            cmd.append("--strict")

        if self.settings.ignore_missing_imports:
            cmd.append("--ignore-missing-imports")

        cmd.extend(["--follow-imports", self.settings.follow_imports])

        if self.settings.incremental:
            cmd.append("--incremental")

        # Warn about unused type: ignore comments
        if self.settings.warn_unused_ignores:
            cmd.append("--warn-unused-ignores")

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Pyrefly command",
            extra={
                "file_count": len(files),
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
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
                extra={"files_count": len(data.get("files", []))},
            )
        except json.JSONDecodeError as e:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = []

        for file_data in data.get("files", []):
            file_path = Path(file_data.get("path", ""))

            for error in file_data.get("errors", []):
                issue = ToolIssue(
                    file_path=file_path,
                    line_number=error.get("line"),
                    column_number=error.get("column"),
                    message=error.get("message", ""),
                    code=error.get("code"),
                    severity=error.get("severity", "error"),
                )
                issues.append(issue)

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
        self, severity_and_message: str, message: str, severity: str
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

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.TYPE,
            enabled=False,
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/.venv/**",
                "**/venv/**",
                "**/build/**",
                "**/dist/**",
            ],
            timeout_seconds=180,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "strict_mode": False,
                "incremental": True,
                "follow_imports": "normal",
                "warn_unused_ignores": True,
            },
        )
