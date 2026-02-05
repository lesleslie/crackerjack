from __future__ import annotations

import logging
import re
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


MODULE_ID = UUID("b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e")
MODULE_STATUS = AdapterStatus.BETA


logger = logging.getLogger(__name__)


class VultureSettings(ToolAdapterSettings):
    tool_name: str = "vulture"
    min_confidence: int = 60
    exclude_patterns: list[str] = []
    ignore_decorators: list[str] = []
    ignore_names: list[str] = []
    sort_by_size: bool = False
    make_whitelist: bool = False


class VultureAdapter(BaseToolAdapter):
    settings: VultureSettings | None = None

    def __init__(self, settings: VultureSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "VultureAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        if not self.settings:
            timeout_seconds = self._get_timeout_from_settings()

            self.settings = VultureSettings(
                timeout_seconds=timeout_seconds,
                max_workers=4,
                min_confidence=60,
                exclude_patterns=[],
                ignore_decorators=[],
                ignore_names=[],
            )
            logger.info("Using default VultureSettings")
        await super().init()
        logger.debug(
            "VultureAdapter initialization complete",
            extra={
                "min_confidence": self.settings.min_confidence,
                "timeout_seconds": self.settings.timeout_seconds,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Vulture (Dead Code)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "vulture"

    def build_command(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,  # noqa: ARG002
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        cmd = [self.tool_name]

        cmd.extend(["--min-confidence", str(self.settings.min_confidence)])

        if self.settings.exclude_patterns:
            exclude_str = ",".join(self.settings.exclude_patterns)
            cmd.extend(["--exclude", exclude_str])

        if self.settings.ignore_decorators:
            decorators_str = ",".join(self.settings.ignore_decorators)
            cmd.extend(["--ignore-decorators", decorators_str])

        if self.settings.ignore_names:
            names_str = ",".join(self.settings.ignore_names)
            cmd.extend(["--ignore-names", names_str])

        if self.settings.sort_by_size:
            cmd.append("--sort-by-size")

        if self.settings.make_whitelist:
            cmd.append("--make-whitelist")

        if files:
            cmd.extend([str(f) for f in files])
        else:
            package_dir = self._detect_package_directory()
            cmd.append(package_dir)

        logger.info(
            "Built Vulture command",
            extra={
                "file_count": len(files) if files else 1,
                "min_confidence": self.settings.min_confidence,
                "has_exclude_patterns": self.settings.exclude_patterns is not None,
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
            "Parsing Vulture output",
            extra={"output_length": len(result.raw_output)},
        )

        return self._parse_text_output(result.raw_output)

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues: list[ToolIssue] = []
        lines = output.strip().split("\n")

        for line in lines:
            if (
                not line.strip()
                or "unused" in line
                and "attribute" in line
                or "confidence" not in line.lower()
            ):
                continue

            issue = self._parse_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Vulture output",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_line(self, line: str) -> ToolIssue | None:

        pattern = r"^(.+?):(\d+):\s+(\S+)\s+-\s+(.+?)\s+\((\d+)%\s+confidence\)"

        match = re.match(pattern, line.strip())
        if not match:
            return None

        try:
            file_path = Path(match.group(1))
            line_number = int(match.group(2))
            name = match.group(3)
            code_type = match.group(4).strip()
            confidence = int(match.group(5))

            message = f"Unused {code_type}: '{name}' ({confidence}% confidence)"

            severity = "error" if confidence >= 80 else "warning"

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=None,
                message=message,
                code=f"vulture_{code_type.lower().replace(' ', '_')}",
                severity=severity,
            )

        except (ValueError, IndexError):
            return None

    def _get_check_type(self) -> QACheckType:
        return QACheckType.COMPLEXITY

    def _detect_package_directory(self) -> str:
        cwd = Path.cwd()

        pyproject_path = cwd / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib

                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                if "project" in data and "name" in data["project"]:
                    package_name = str(data["project"]["name"]).replace("-", "_")
                    if (cwd / package_name).exists():
                        return package_name
            except Exception:
                pass

        for name in ["crackerjack", "src", "app"]:
            if (cwd / name).exists():
                return name

        return "."

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        package_dir = self._detect_package_directory()

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.COMPLEXITY,
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
                "**/worktrees/**",
                "**/conftest.py",
                "**/*_test.py",
            ],
            timeout_seconds=30,
            parallel_safe=True,
            stage="fast",
            settings={
                "min_confidence": 60,
                "exclude_patterns": [],
                "ignore_decorators": [
                    "@app.route",
                    "@pytest.fixture",
                    "@property",
                    "@setter",
                    "@deleter",
                    "@staticmethod",
                    "@lru_cache",
                ],
                "ignore_names": None,
                "sort_by_size": False,
                "make_whitelist": False,
            },
        )
