from __future__ import annotations

import json
import typing as t
from enum import StrEnum
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
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


MODULE_ID = UUID("c38609f7-f4a4-43ac-a7af-c55ef522c615")
MODULE_STATUS = AdapterStatus.STABLE


class RuffMode(StrEnum):
    CHECK = "check"
    FORMAT = "format"


class RuffSettings(ToolAdapterSettings):
    tool_name: str = "ruff"
    mode: str = "check"
    fix_enabled: bool = False
    unsafe_fixes: bool = False
    select_rules: list[str] = Field(default_factory=list)
    ignore_rules: list[str] = Field(default_factory=list)
    line_length: int | None = None
    use_json_output: bool = True
    respect_gitignore: bool = True
    preview: bool = False


class RuffAdapter(BaseToolAdapter):
    settings: RuffSettings | None = None

    def __init__(self, settings: RuffSettings | None = None) -> None:
        super().__init__(settings=settings)

    async def init(self) -> None:
        if not self.settings:
            self.settings = RuffSettings(
                timeout_seconds=300,
                max_workers=4,
            )
        await super().init()

    @property
    def adapter_name(self) -> str:
        if self.settings:
            mode = self.settings.mode
            return f"Ruff ({mode})"
        return "Ruff"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "ruff"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name, self.settings.mode]

        if self.settings.mode == "check":
            self._add_check_mode_options(cmd)
        elif self.settings.mode == "format":
            self._add_format_mode_options(cmd)

        cmd.extend([str(f) for f in files])

        if self.settings.respect_gitignore:
            cmd.append("--respect-gitignore")

        return cmd

    def _add_check_mode_options(self, cmd: list[str]) -> None:
        if not self.settings:
            return

        if self.settings.fix_enabled:
            cmd.append("--fix")

            if self.settings.unsafe_fixes:
                cmd.append("--unsafe-fixes")

        if self.settings.use_json_output:
            cmd.extend(["--output-format", "json"])

        if self.settings.select_rules:
            cmd.extend(["--select", ", ".join(self.settings.select_rules)])

        if self.settings.ignore_rules:
            cmd.extend(["--ignore", ", ".join(self.settings.ignore_rules)])

        if self.settings.preview:
            cmd.append("--preview")

    def _add_format_mode_options(self, cmd: list[str]) -> None:
        if not self.settings:
            return

        if self.settings.line_length:
            cmd.extend(["--line-length", str(self.settings.line_length)])

        if self.settings.preview:
            cmd.append("--preview")

        if not self.settings.fix_enabled:
            cmd.append("--check")

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        issues: list[ToolIssue] = []

        if self.settings.mode == "check":
            if self.settings.use_json_output and result.raw_output:
                issues = self._parse_check_json(result.raw_output)
            else:
                issues = self._parse_check_text(result.raw_output)

        elif self.settings.mode == "format":
            if result.exit_code != 0:
                issues = self._parse_format_output(
                    result.raw_output,
                    result.files_processed,
                )

        return issues

    def _parse_check_json(self, output: str) -> list[ToolIssue]:
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return []

        issues = []
        for item in data:
            location = item.get("location", {})
            file_path = Path(item.get("filename", ""))

            issue = ToolIssue(
                file_path=file_path,
                line_number=location.get("row"),
                column_number=location.get("column"),
                message=item.get("message", ""),
                code=item.get("code"),
                severity="error" if item.get("code", "").startswith("E") else "warning",
                suggestion=item.get("fix", {}).get("message")
                if item.get("fix")
                else None,
            )
            issues.append(issue)

        return issues

    def _parse_check_text(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            if ":" not in line:
                continue

            issue = self._parse_check_text_line(line)
            if issue:
                issues.append(issue)

        return issues

    def _parse_check_text_line(self, line: str) -> ToolIssue | None:
        parts = line.split(":", maxsplit=3)
        if len(parts) < 4:
            return None

        try:
            file_path = Path(parts[0].strip())
            line_number = int(parts[1].strip())
            column_number = (
                int(parts[2].strip()) if parts[2].strip().isdigit() else None
            )

            message_part = parts[3].strip()
            code, message = self._extract_check_code_and_message(message_part)

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                code=code,
                severity="error" if code and code.startswith("E") else "warning",
            )

        except (ValueError, IndexError):
            return None

    def _extract_check_code_and_message(
        self, message_part: str
    ) -> tuple[str | None, str]:
        if " " not in message_part:
            return None, message_part

        code_candidate = message_part.split()[0]
        if code_candidate.strip():
            code = code_candidate
            message = message_part[len(code) :].strip()
            return code, message

        return None, message_part

    def _parse_format_output(
        self,
        output: str,
        processed_files: list[Path],
    ) -> list[ToolIssue]:
        issues = []

        lines = output.strip().split("\n")

        for line in lines:
            if line.startswith("Would reformat:") or line.strip().endswith(".py"):
                file_str = line.replace("Would reformat:", "").strip()
                if file_str:
                    try:
                        file_path = Path(file_str)
                        issue = ToolIssue(
                            file_path=file_path,
                            message="File would be reformatted",
                            severity="warning",
                        )
                        issues.append(issue)
                    except Exception:
                        continue

        if not issues and processed_files:
            for file_path in processed_files:
                issue = ToolIssue(
                    file_path=file_path,
                    message="File needs formatting",
                    severity="warning",
                )
                issues.append(issue)

        return issues

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        result = await super().check(files=files, config=config)

        if (
            self.settings
            and self.settings.mode == "format"
            and self.settings.fix_enabled
            and result.status in (QAResultStatus.SUCCESS, QAResultStatus.WARNING)
        ):
            result.files_modified = result.files_checked.copy()
            result.issues_fixed = result.issues_found

        return result

    def _get_check_type(self) -> QACheckType:
        if self.settings and self.settings.mode == "format":
            return QACheckType.FORMAT
        return QACheckType.LINT

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        is_format_mode = False
        if self.settings:
            is_format_mode = self.settings.mode == "format"
        else:
            is_format_mode = False

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/.*",
                "**/__pycache__/**",
                "**/build/**",
                "**/dist/**",
            ],
            timeout_seconds=60,
            is_formatter=is_format_mode,
            parallel_safe=True,
            stage="fast",
            settings={
                "mode": "check",
                "fix_enabled": True,
                "select_rules": [],
                "ignore_rules": [],
                "preview": False,
            },
        )
