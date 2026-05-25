from __future__ import annotations

import logging
import re
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


MODULE_ID = UUID("25e1e5cf-d1f8-485e-85ab-01c8b540734a")
MODULE_STATUS = AdapterStatus.BETA


logger = logging.getLogger(__name__)

_TY_DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<column>\d+):\s*"
    r"(?:(?P<severity>[A-Za-z]+)(?:\[(?P<code>[^\]]+)\])?\s*)?"
    r"(?P<message>.*)$",
)


class TySettings(ToolAdapterSettings):
    tool_name: str = "ty"
    output_format: str = "concise"
    fix_enabled: bool = False
    add_ignore_enabled: bool = False
    no_progress: bool = True


class TyAdapter(BaseToolAdapter):
    settings: TySettings | None = None

    def __init__(self, settings: TySettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "TyAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = TySettings(
                timeout_seconds=180,
                max_workers=4,
            )
            logger.info("Using default TySettings")

        await super().init()
        logger.debug(
            "TyAdapter initialization complete",
            extra={
                "output_format": self.settings.output_format,
                "fix_enabled": self.settings.fix_enabled,
                "add_ignore_enabled": self.settings.add_ignore_enabled,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Ty (Type Check)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "ty"

    def supports_fix(self) -> bool:
        return True

    def supports_suppress(self) -> bool:
        return True

    def supports_baseline(self) -> bool:
        return False

    def supports_json_output(self) -> bool:
        return False

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None, # noqa: ARG002
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

        if self.settings.no_progress:
            cmd.append("--no-progress")

        if self.settings.fix_enabled:
            cmd.append("--fix")

        if self.settings.add_ignore_enabled:
            cmd.append("--add-ignore")

        cmd.extend(str(f) for f in files)

        logger.info(
            "Built Ty command",
            extra={
                "file_count": len(files),
                "output_format": self.settings.output_format,
                "fix_enabled": self.settings.fix_enabled,
                "add_ignore_enabled": self.settings.add_ignore_enabled,
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

        logger.debug(
            "Parsing Ty output",
            extra={"output_length": len(result.raw_output)},
        )
        return self._parse_text_output(result.raw_output)

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues: list[ToolIssue] = []

        for line in output.splitlines():
            issue = self._parse_text_line(line.strip())
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Ty output",
            extra={
                "total_issues": len(issues),
                "errors": sum(1 for issue in issues if issue.severity == "error"),
                "warnings": sum(1 for issue in issues if issue.severity == "warning"),
                "files_affected": len({str(issue.file_path) for issue in issues}),
            },
        )
        return issues

    def _parse_text_line(self, line: str) -> ToolIssue | None:
        if not line or line.startswith("Found "):
            return None

        match = _TY_DIAGNOSTIC_RE.match(line)
        if not match:
            return None

        try:
            file_path = Path(match.group("path"))
            line_number = int(match.group("line"))
            column_number = int(match.group("column"))
            severity = self._normalize_severity(match.group("severity"))
            code = match.group("code")
            message = match.group("message").strip()

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                code=code,
                severity=severity,
            )
        except (TypeError, ValueError):
            return None

    def _normalize_severity(self, severity: str | None) -> str:
        if not severity:
            return "error"

        lowered = severity.lower()
        if lowered == "warning":
            return "warning"
        if lowered in {"info", "information"}:
            return "info"
        return "error"

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
                "output_format": "concise",
                "fix_enabled": False,
                "add_ignore_enabled": False,
                "no_progress": True,
            },
        )
