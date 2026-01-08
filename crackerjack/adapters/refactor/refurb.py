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


MODULE_ID = UUID("0f3546f6-4e29-4d9d-98f8-43c6f3c21a4e")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class RefurbSettings(ToolAdapterSettings):
    tool_name: str = "refurb"
    use_json_output: bool = False
    enable_all: bool = False
    disable_checks: list[str] = Field(default_factory=list)
    enable_checks: list[str] = Field(default_factory=list)
    python_version: str | None = None
    explain: bool = False


class RefurbAdapter(BaseToolAdapter):
    settings: RefurbSettings | None = None

    def __init__(self, settings: RefurbSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "RefurbAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            timeout_seconds = self._get_timeout_from_settings()

            self.settings = RefurbSettings(
                timeout_seconds=timeout_seconds,
                max_workers=4,
            )
            logger.info("Using default RefurbSettings")
        await super().init()
        logger.debug(
            "RefurbAdapter initialization complete",
            extra={
                "enable_all": self.settings.enable_all,
                "enable_checks_count": len(self.settings.enable_checks),
                "disable_checks_count": len(self.settings.disable_checks),
                "has_python_version": self.settings.python_version is not None,
                "timeout_seconds": self.settings.timeout_seconds,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Refurb (Refactoring)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "refurb"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        if self.settings.enable_all:
            cmd.append("--enable-all")

        if self.settings.disable_checks:
            for check in self.settings.disable_checks:
                cmd.extend(["--ignore", check])

        if self.settings.enable_checks:
            for check in self.settings.enable_checks:
                cmd.extend(["--enable", check])

        if self.settings.python_version:
            cmd.extend(["--python-version", self.settings.python_version])

        if self.settings.explain:
            cmd.append("--explain")

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Refurb command",
            extra={
                "file_count": len(files),
                "enable_all": self.settings.enable_all,
                "enable_checks_count": len(self.settings.enable_checks),
                "disable_checks_count": len(self.settings.disable_checks),
                "explain": self.settings.explain,
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

        issues = []
        lines = result.raw_output.strip().split("\n")
        logger.debug("Parsing Refurb text output", extra={"line_count": len(lines)})

        for line in lines:
            if "[FURB" not in line:
                continue

            issue = self._parse_refurb_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Refurb output",
            extra={
                "total_issues": len(issues),
                "files_affected": len({str(i.file_path) for i in issues}),
                "unique_codes": len({i.code for i in issues if i.code}),
            },
        )
        return issues

    def _parse_refurb_line(self, line: str) -> ToolIssue | None:
        try:
            if ":" not in line:
                return None

            parts = line.split(":", maxsplit=3)
            if len(parts) < 3:
                return None

            file_path = Path(parts[0].strip())
            line_number = int(parts[1].strip())

            remaining = parts[2].strip()
            column_number = self._extract_column_number(remaining)
            message_part = self._extract_message_part(remaining, column_number)

            code, message = self._extract_code_and_message(message_part)

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                code=code,
                severity="warning",
            )

        except (ValueError, IndexError):
            return None

    def _extract_column_number(self, remaining: str) -> int | None:
        if " " in remaining:
            first_part = remaining.split()[0]
            if first_part.isdigit():
                return int(first_part)
        return None

    def _extract_message_part(self, remaining: str, column_number: int | None) -> str:
        if column_number is not None and " " in remaining:
            first_part = remaining.split()[0]
            return remaining[len(first_part) :].strip()
        return remaining

    def _extract_code_and_message(self, message_part: str) -> tuple[str | None, str]:
        if "[" in message_part and "]" in message_part:
            code_start = message_part.index("[")
            code_end = message_part.index("]")
            code = message_part[code_start + 1 : code_end]
            message = message_part[code_end + 1 :].strip()
            if message.startswith(":"):
                message = message[1:].strip()
            return code, message
        return None, message_part

    def _get_check_type(self) -> QACheckType:
        return QACheckType.REFACTOR

    def _detect_package_directory(self) -> str:
        from contextlib import suppress

        current_dir = Path.cwd()

        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.exists():
            with suppress(Exception):
                import tomllib

                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                if "project" in data and "name" in data["project"]:
                    package_name = str(data["project"]["name"]).replace("-", "_")

                    if (current_dir / package_name).exists():
                        return package_name

        if (current_dir / current_dir.name).exists():
            return current_dir.name

        return "src"

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        package_dir = self._detect_package_directory()

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.REFACTOR,
            enabled=True,
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
            ],
            timeout_seconds=240,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "enable_all": False,
                "disable_checks": [],
                "enable_checks": [],
                "explain": False,
            },
        )
