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


MODULE_ID = UUID("c4c0c9fc-43d8-4b17-afb5-4febacec2e90")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class CreosoteSettings(ToolAdapterSettings):
    tool_name: str = "creosote"
    use_json_output: bool = False
    config_file: Path | None = None
    exclude_deps: list[str] = Field(default_factory=list)
    paths: list[Path] = Field(default_factory=list)


class CreosoteAdapter(BaseToolAdapter):
    settings: CreosoteSettings | None = None

    def __init__(self, settings: CreosoteSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "CreosoteAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = CreosoteSettings(
                timeout_seconds=60,
                max_workers=4,
            )
            logger.info("Using default CreosoteSettings")
        await super().init()
        logger.debug(
            "CreosoteAdapter initialization complete",
            extra={
                "has_config_file": self.settings.config_file is not None,
                "exclude_deps_count": len(self.settings.exclude_deps),
                "scan_paths_count": len(self.settings.paths),
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Creosote (Dependencies)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "creosote"

    async def _get_target_files(
        self, files: list[Path] | None, config: QACheckConfig | None
    ) -> list[Path]:
        if files:
            return files

        pyproject = Path.cwd() / "pyproject.toml"
        return [pyproject] if pyproject.exists() else []

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name]

        if self.settings.config_file and self.settings.config_file.exists():
            cmd.extend(["--deps-file", str(self.settings.config_file)])

        if self.settings.exclude_deps:
            for dep in self.settings.exclude_deps:
                cmd.extend(["--exclude", dep])

        if self.settings.paths:
            for path in self.settings.paths:
                cmd.extend(["--paths", str(path)])

        logger.info(
            "Built Creosote command",
            extra={
                "has_config_file": self.settings.config_file is not None,
                "exclude_deps_count": len(self.settings.exclude_deps),
                "scan_paths_count": len(self.settings.paths),
            },
        )
        return cmd

    def _is_unused_deps_section_start(self, line: str) -> bool:
        return "unused" in line.lower() and "dependenc" in line.lower()

    def _process_dependency_line(self, line: str) -> str | None:
        dep_name = line.lstrip("- ").strip()

        if dep_name:
            return dep_name
        return None

    def _create_issue_for_dependency(
        self, dep_name: str, config_file: Path
    ) -> ToolIssue:
        return ToolIssue(
            file_path=config_file,
            message=f"Unused dependency: {dep_name}",
            code="UNUSED_DEP",
            severity="warning",
            suggestion=f"Consider removing '{dep_name}' from dependencies if not needed",
        )

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not result.raw_output:
            logger.debug("No output to parse")
            return []

        issues = []
        lines = result.raw_output.strip().split("\n")
        logger.debug("Parsing Creosote text output", extra={"line_count": len(lines)})

        parsing_unused = False
        config_file = (
            self.settings.config_file if self.settings else Path("pyproject.toml")
        )

        for line in lines:
            line = line.strip()

            if self._is_unused_deps_section_start(line):
                parsing_unused = True
                continue

            if not line:
                parsing_unused = False
                continue

            if parsing_unused and line:
                dep_name = self._process_dependency_line(line)
                if dep_name:
                    issue = self._create_issue_for_dependency(dep_name, config_file)
                    issues.append(issue)

        logger.info(
            "Parsed Creosote output",
            extra={
                "total_unused": len(issues),
                "config_file": str(config_file),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.REFACTOR

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.REFACTOR,
            enabled=True,
            file_patterns=["pyproject.toml", "requirements*.txt"],
            timeout_seconds=60,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "config_file": "pyproject.toml",
                "exclude_deps": [
                    "pytest",
                    "black",
                    "ruff",
                    "mypy",
                    "sphinx",
                    "tox",
                ],
                "paths": ["src", "tests"],
            },
        )
