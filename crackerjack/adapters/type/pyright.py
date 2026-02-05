from __future__ import annotations

import json
import logging
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


MODULE_ID = UUID("a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d")
MODULE_STATUS = AdapterStatus.BETA


logger = logging.getLogger(__name__)


class PyrightSettings(ToolAdapterSettings):
    tool_name: str = "pyright"
    use_json_output: bool = True
    strict_mode: bool = False
    ignore_missing_imports: bool = False
    type_checking_mode: str = "basic"
    report_unnecessary_type_ignore_comment: str = "warning"
    report_missing_type_stubs: str = "warning"


class PyrightAdapter(BaseToolAdapter):
    settings: PyrightSettings | None = None

    def __init__(self, settings: PyrightSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "PyrightAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = PyrightSettings(
                timeout_seconds=180,
                max_workers=4,
            )
            logger.info("Using default PyrightSettings")
        await super().init()
        logger.debug(
            "PyrightAdapter initialization complete",
            extra={
                "strict_mode": self.settings.strict_mode,
                "type_checking_mode": self.settings.type_checking_mode,
                "use_json_output": self.settings.use_json_output,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Pyright (Type Check)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "pyright"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,  # noqa: ARG002
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        cmd = [self.tool_name]

        if self.settings.use_json_output:
            cmd.append("--outputjson")

        if self.settings.type_checking_mode == "strict":
            cmd.extend(("--level", "strict"))
        elif self.settings.type_checking_mode == "off":
            cmd.append("--skipunannotated")

        cmd.extend(
            [
                f"--reportUnnecessaryTypeIgnoreComment={self.settings.report_unnecessary_type_ignore_comment}",
                f"--reportMissingTypeStubs={self.settings.report_missing_type_stubs}",
            ]
        )

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Pyright command",
            extra={
                "file_count": len(files),
                "type_checking_mode": self.settings.type_checking_mode,
                "use_json_output": self.settings.use_json_output,
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

        if self.settings and self.settings.use_json_output:
            try:
                parsed_data: dict[str, t.Any] = json.loads(result.raw_output)  # type: ignore[assignment]
                logger.debug(
                    "Parsed Pyright JSON output",
                    extra={
                        "files_count": len(parsed_data.get("generalDiagnostics", []))
                    },
                )
                return self._parse_json_output(parsed_data)
            except json.JSONDecodeError as e:
                logger.warning(
                    "JSON parse failed, falling back to text parsing",
                    extra={"error": str(e), "output_preview": result.raw_output[:200]},
                )
                return self._parse_text_output(result.raw_output)

        return self._parse_text_output(result.raw_output)

    def _parse_json_output(self, data: dict[str, t.Any]) -> list[ToolIssue]:
        issues: list[ToolIssue] = []

        diagnostics: list[dict[str, t.Any]] = data.get("generalDiagnostics", [])  # type: ignore[assignment]

        for diagnostic in diagnostics:
            file_path = Path(diagnostic.get("file", ""))  # type: ignore[arg-type]
            severity: str = diagnostic.get("severity", "error")  # type: ignore[assignment]
            message: str = diagnostic.get("message", "")  # type: ignore[assignment]
            rule: str = diagnostic.get("rule", "")  # type: ignore[assignment]

            range_data: dict[str, t.Any] = diagnostic.get("range", {})  # type: ignore[assignment]
            start_position: dict[str, t.Any] = range_data.get("start", {})  # type: ignore[assignment]
            line_number: int = (
                start_position.get("line", 0) + 1
            )  # Convert 0-indexed to 1-indexed  # type: ignore[assignment]
            column_number: int = start_position.get("character", 0) + 1  # type: ignore[assignment]

            issue = ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                code=rule,
                severity=severity,
            )
            issues.append(issue)

        logger.info(
            "Parsed Pyright JSON output",
            extra={
                "total_issues": len(issues),
                "errors": sum(1 for i in issues if i.severity == "error"),
                "warnings": sum(1 for i in issues if i.severity == "warning"),
                "files_affected": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues: list[ToolIssue] = []
        lines = output.strip().split("\n")

        for line in lines:
            if ":" not in line:
                continue

            if (
                "error" in line
                and "warning" in line
                and (" file" in line or "files" in line)
            ):
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        logger.info(
            "Parsed Pyright text output",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _parse_text_line(self, line: str) -> ToolIssue | None:
        parts = line.split("-", maxsplit=1)
        if len(parts) < 2:
            return None

        location_part = parts[0].strip()
        message_part = parts[1].strip() if len(parts) > 1 else ""

        location_parts = location_part.split(":")
        if len(location_parts) < 3:
            return None

        try:
            file_path = Path(location_parts[0].strip())
            line_number = int(location_parts[1].strip())
            column_number = int(location_parts[2].strip())

            if message_part.lower().startswith("error:"):
                severity = "error"
                message = message_part[6:].strip()
            elif message_part.lower().startswith("warning:"):
                severity = "warning"
                message = message_part[8:].strip()
            else:
                severity = "error"
                message = message_part

            return ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                severity=severity,
            )

        except (ValueError, IndexError):
            return None

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
                "strict_mode": False,
                "type_checking_mode": "basic",
                "use_json_output": True,
                "report_unnecessary_type_ignore_comment": "warning",
                "report_missing_type_stubs": "warning",
            },
        )
