from __future__ import annotations

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


MODULE_ID = UUID("d6db665f-1aa2-43d7-954f-3d13a055bdbd")
MODULE_STATUS = AdapterStatus.STABLE


class MdformatSettings(ToolAdapterSettings):
    tool_name: str = "mdformat"
    use_json_output: bool = False
    fix_enabled: bool = True
    line_length: int = 88
    check_only: bool = False
    wrap_mode: str = "keep"
    timeout_seconds: int = 300
    max_workers: int = 4


class MdformatAdapter(BaseToolAdapter):
    settings: MdformatSettings | None = None

    def __init__(self, settings: MdformatSettings | None = None) -> None:
        super().__init__(settings=settings)

    async def init(self) -> None:
        if not self.settings:
            self.settings = MdformatSettings()
        await super().init()

    @property
    def adapter_name(self) -> str:
        return "Mdformat (Markdown)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "mdformat"

    async def _get_target_files(
        self, files: list[Path] | None, config: QACheckConfig | None
    ) -> list[Path]:
        if files:
            return files

        from crackerjack.tools._git_utils import get_git_tracked_files

        md_files = get_git_tracked_files("*.md")
        markdown_files = get_git_tracked_files("*.markdown")
        return md_files + markdown_files

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        if not self.settings.fix_enabled:
            cmd.append("--check")
        else:
            pass

        wrap_mode = getattr(self.settings, "wrap_mode", None)
        if wrap_mode:
            if wrap_mode in {"keep", "no"}:
                cmd.extend(["--wrap", wrap_mode])
            elif isinstance(wrap_mode, str) and wrap_mode.isdigit():
                cmd.extend(["--wrap", wrap_mode])
            else:
                if self.settings.line_length:
                    cmd.extend(["--wrap", str(self.settings.line_length)])
        else:
            if self.settings.line_length:
                cmd.extend(["--wrap", str(self.settings.line_length)])

        cmd.extend([str(f) for f in files])

        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if result.exit_code == 0:
            return []

        issues = self._parse_output_lines(result.raw_output)

        if not issues and result.files_processed:
            issues = self._create_issues_from_processed_files(result.files_processed)

        return issues

    def _parse_output_lines(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            issue = self._create_issue_from_line(line)
            if issue:
                issues.append(issue)

        return issues

    def _create_issue_from_line(self, line: str) -> ToolIssue | None:
        with suppress(Exception):
            file_path = Path(line)
            if file_path.exists() and file_path.suffix in (".md", ".markdown"):
                return ToolIssue(
                    file_path=file_path,
                    message="File needs Markdown formatting",
                    code="MDFORMAT",
                    severity="warning",
                    suggestion="Run mdformat to format this file",
                )

        return None

    def _create_issues_from_processed_files(
        self, processed_files: list[Path]
    ) -> list[ToolIssue]:
        issues = []
        for file_path in processed_files:
            if file_path.suffix in (".md", ".markdown"):
                issue = ToolIssue(
                    file_path=file_path,
                    message="File needs Markdown formatting",
                    code="MDFORMAT",
                    severity="warning",
                )
                issues.append(issue)

        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.FORMAT

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.FORMAT,
            enabled=True,
            file_patterns=["**/*.md", "**/*.markdown"],
            exclude_patterns=[
                "**/.git/**",
                "**/.venv/**",
                "**/node_modules/**",
            ],
            timeout_seconds=300,
            is_formatter=True,
            parallel_safe=True,
            stage="fast",
            settings={
                "fix_enabled": True,
                "line_length": 88,
                "check_only": False,
                "wrap_mode": "keep",
            },
        )
