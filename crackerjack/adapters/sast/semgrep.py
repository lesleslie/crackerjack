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


MODULE_ID = UUID("bff2e3e9-9b3c-49b7-a8c0-526fe56b0c37")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class SemgrepSettings(ToolAdapterSettings):
    tool_name: str = "semgrep"
    use_json_output: bool = True
    config: str = "p/python"
    exclude_tests: bool = True
    timeout_seconds: int = 1200


class SemgrepAdapter(BaseToolAdapter):
    settings: SemgrepSettings | None = None

    def __init__(self, settings: SemgrepSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "SemgrepAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = SemgrepSettings(
                timeout_seconds=1200,
                max_workers=4,
            )
            logger.info("Using default SemgrepSettings")
        await super().init()
        logger.debug(
            "SemgrepAdapter initialization complete",
            extra={
                "config": self.settings.config,
                "exclude_tests": self.settings.exclude_tests,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Semgrep (Security)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "semgrep"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name, "scan"]

        if self.settings.use_json_output:
            cmd.append("--json")

        cmd.extend(["--config", self.settings.config])

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Semgrep command",
            extra={
                "file_count": len(files),
                "config": self.settings.config,
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
                "Parsed Semgrep JSON output",
                extra={"results_count": len(data.get("results", []))},
            )
        except json.JSONDecodeError as e:
            logger.debug(
                "JSON parse failed, falling back to text parsing",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return []

        issues = []
        for item in data.get("results", []):
            file_path = Path(item.get("path", ""))
            start_line = item.get("start", {}).get("line")
            message = item.get("extra", {}).get("message", "")
            code = item.get("check_id")
            severity = item.get("extra", {}).get("severity", "WARNING").lower()

            issue = ToolIssue(
                file_path=file_path,
                line_number=start_line,
                message=message,
                code=code,
                severity=severity,
            )
            issues.append(issue)

        logger.info(
            "Parsed Semgrep output",
            extra={
                "total_issues": len(issues),
                "files_affected": len({str(i.file_path) for i in issues}),
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
            ],
            timeout_seconds=1200,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "config": "p/python",
                "exclude_tests": True,
            },
        )
