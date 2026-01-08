from __future__ import annotations

import logging
import typing as t
from pathlib import Path
from uuid import UUID

from pydantic import Field

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


MODULE_ID = UUID("658dfd25-e475-4e28-9945-23ff31c30b0a")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class PyscnSettings(ToolAdapterSettings):
    tool_name: str = "pyscn"
    use_json_output: bool = False
    severity_threshold: str = "low"
    confidence_threshold: str = "low"
    max_complexity: int = 15
    exclude_rules: list[str] = Field(default_factory=list)
    include_rules: list[str] = Field(default_factory=list)
    recursive: bool = True
    max_depth: int | None = None


class PyscnAdapter(BaseToolAdapter):
    settings: PyscnSettings | None = None

    def __init__(self, settings: PyscnSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "PyscnAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = PyscnSettings(
                timeout_seconds=120,
                max_workers=4,
                max_complexity=15,
            )
            logger.info("Using default PyscnSettings")
        await super().init()
        logger.debug(
            "PyscnAdapter initialization complete",
            extra={
                "severity_threshold": self.settings.severity_threshold,
                "confidence_threshold": self.settings.confidence_threshold,
                "max_complexity": self.settings.max_complexity,
                "recursive": self.settings.recursive,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Pyscn (Security Analysis)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "pyscn"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name, "check"]

        cmd.extend(["--max-complexity", str(self.settings.max_complexity)])

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Pyscn command",
            extra={
                "file_count": len(files),
                "max_complexity": self.settings.max_complexity,
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

        return self._parse_text_output(result.raw_output)

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            if ":" not in line:
                continue

            if "clone of" in line or line.strip().startswith("⚠️"):
                continue

            if "is too complex" not in line:
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Pyscn text output",
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

            severity = self._parse_severity(severity_and_message, message)
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

    def _parse_severity(self, severity_and_message: str, message: str) -> str:
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
        return QACheckType.SAST

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.SAST,
            enabled=False,
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/.venv/**",
                "**/venv/**",
                "**/tests/**",
                "**/build/**",
                "**/dist/**",
            ],
            timeout_seconds=120,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "severity_threshold": "medium",
                "confidence_threshold": "medium",
                "max_complexity": 15,
                "recursive": True,
            },
        )
