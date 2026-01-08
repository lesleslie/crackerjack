from __future__ import annotations

import json
import logging
import typing as t
from contextlib import suppress
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


MODULE_ID = UUID("1a6108e1-275a-4539-9536-aa66abfe7cd6")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class BanditSettings(ToolAdapterSettings):
    tool_name: str = "bandit"
    use_json_output: bool = True
    severity_level: str = "low"
    confidence_level: str = "low"
    exclude_tests: bool = True
    skip_rules: list[str] = Field(default_factory=list)
    tests_to_run: list[str] = Field(default_factory=list)
    recursive: bool = True
    timeout_seconds: int = 1200


class BanditAdapter(BaseToolAdapter):
    settings: BanditSettings | None = None

    def __init__(self, settings: BanditSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "BanditAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = BanditSettings(
                timeout_seconds=1200,
                max_workers=4,
            )
            logger.info("Using default BanditSettings")
        await super().init()
        logger.debug(
            "BanditAdapter initialization complete",
            extra={
                "severity": self.settings.severity_level,
                "confidence": self.settings.confidence_level,
                "exclude_tests": self.settings.exclude_tests,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Bandit (Security)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "bandit"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        if self.settings.recursive:
            cmd.append("-r")

        cmd.extend(["-lll"])
        cmd.extend(["-iii"])

        skip_rules = ["B101", "B110", "B112", "B311", "B404", "B603", "B607"]
        cmd.extend(["-s", ", ".join(skip_rules)])

        if self.settings.use_json_output:
            cmd.extend(["-f", "json"])

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Bandit command with aggressive skip rules",
            extra={
                "file_count": len(files),
                "severity": "high",
                "confidence": "high",
                "recursive": self.settings.recursive,
                "skip_rules": skip_rules,
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
                "Parsed Bandit JSON output",
                extra={"results_count": len(data.get("results", []))},
            )
        except json.JSONDecodeError as e:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return self._parse_text_output(result.raw_output)

        issues = []

        for item in data.get("results", []):
            file_path = Path(item.get("filename", ""))

            severity_mapping = {
                "HIGH": "error",
                "MEDIUM": "warning",
                "LOW": "warning",
            }
            bandit_severity = item.get("issue_severity", "MEDIUM")
            severity = severity_mapping.get(bandit_severity.upper(), "warning")

            issue = ToolIssue(
                file_path=file_path,
                line_number=item.get("line_number"),
                message=item.get("issue_text", ""),
                code=item.get("test_id"),
                severity=severity,
                suggestion=f"Confidence: {item.get('issue_confidence', 'UNKNOWN')}, "
                f"See: {item.get('more_info', '')}",
            )
            issues.append(issue)

        logger.info(
            "Parsed Bandit output",
            extra={
                "total_issues": len(issues),
                "high_severity": sum(1 for i in issues if i.severity == "error"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")

        current_file: Path | None = None
        current_line: int | None = None

        for line in lines:
            line = line.strip()

            if line.startswith(">>"):
                try:
                    file_str = line.split(">>")[1].strip()
                    current_file = Path(file_str)
                except (IndexError, ValueError):
                    continue

            elif line.startswith("Issue:") and current_file:
                message = line.replace("Issue:", "").strip()
                issue = ToolIssue(
                    file_path=current_file,
                    line_number=current_line,
                    message=message,
                    severity="warning",
                )
                issues.append(issue)

            elif "Line:" in line:
                with suppress(IndexError, ValueError):
                    line_num_str = line.split("Line:")[1].strip()
                    current_line = int(line_num_str)

        logger.info(
            "Parsed Bandit text output (fallback)",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len(
                    {str(i.file_path) for i in issues if i.file_path}
                ),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.SAST

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
            check_type=QACheckType.SAST,
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
            timeout_seconds=1200,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "severity_level": "low",
                "confidence_level": "low",
                "exclude_tests": True,
                "skip_rules": [],
            },
        )
