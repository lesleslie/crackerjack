from __future__ import annotations

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


MODULE_ID = UUID("b42b5648-52e1-4a89-866f-3f9821087b0b")
MODULE_STATUS = AdapterStatus.STABLE


class CodespellSettings(ToolAdapterSettings):
    tool_name: str = "codespell"
    use_json_output: bool = False
    fix_enabled: bool = False
    skip_hidden: bool = True
    ignore_words: list[str] = Field(default_factory=list)
    ignore_words_file: Path | None = None
    check_filenames: bool = False
    quiet_level: int = 2
    timeout_seconds: int = 60
    max_workers: int = 4


class CodespellAdapter(BaseToolAdapter):
    settings: CodespellSettings | None = None

    def __init__(self, settings: CodespellSettings | None = None) -> None:
        super().__init__(settings=settings)

    async def init(self) -> None:
        if not self.settings:
            self.settings = CodespellSettings()
        await super().init()

    @property
    def adapter_name(self) -> str:
        return "Codespell (Spelling)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "codespell"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        if self.settings.fix_enabled:
            cmd.append("--write-changes")

        if self.settings.skip_hidden:
            cmd.append("--skip=.*")

        if self.settings.ignore_words:
            cmd.extend(["--ignore-words-list", ", ".join(self.settings.ignore_words)])

        if self.settings.ignore_words_file and self.settings.ignore_words_file.exists():
            cmd.extend(["--ignore-words", str(self.settings.ignore_words_file)])

        if self.settings.check_filenames:
            cmd.append("--check-filenames")

        cmd.extend(["--quiet-level", str(self.settings.quiet_level)])

        cmd.extend([str(f) for f in files])

        return cmd

    def _parse_codespell_line(
        self, line: str
    ) -> tuple[Path | None, int | None, str, str | None] | None:
        if ":" not in line or "==>" not in line:
            return None

        parts = line.split(":", maxsplit=2)
        if len(parts) < 2:
            return None

        file_path = Path(parts[0].strip())
        line_number = int(parts[1].strip()) if parts[1].strip().isdigit() else None

        error_part = parts[2].strip() if len(parts) > 2 else line
        if "==>" in error_part:
            wrong, correct = error_part.split("==>", maxsplit=1)
            wrong = wrong.strip()
            correct = correct.strip()

            message = f"Spelling: '{wrong}' should be '{correct}'"
            suggestion = f"Replace '{wrong}' with '{correct}'"
        else:
            message = error_part
            suggestion = None

        return file_path, line_number, message, suggestion

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not result.raw_output:
            return []

        issues = []
        lines = result.raw_output.strip().split("\n")

        for line in lines:
            parsed_result = self._parse_codespell_line(line)
            if parsed_result is not None:
                file_path, line_number, message, suggestion = parsed_result

                issue = ToolIssue(
                    file_path=file_path,
                    line_number=line_number,
                    message=message,
                    code="SPELLING",
                    severity="warning",
                    suggestion=suggestion,
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
            file_patterns=["**/*.py", "**/*.md", "**/*.rst", "**/*.txt"],
            exclude_patterns=[
                "**/.git/**",
                "**/.venv/**",
                "**/node_modules/**",
                "**/__pycache__/**",
            ],
            timeout_seconds=60,
            is_formatter=False,
            parallel_safe=True,
            stage="fast",
            settings={
                "fix_enabled": False,
                "skip_hidden": True,
                "ignore_words": ["pydantic", "uuid", "dataclass"],
                "check_filenames": False,
            },
        )
