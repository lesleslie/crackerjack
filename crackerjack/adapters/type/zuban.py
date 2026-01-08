from __future__ import annotations

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


MODULE_ID = UUID("e42fd557-ed29-4104-8edd-46607ab807e2")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class ZubanSettings(ToolAdapterSettings):
    tool_name: str = "zuban"
    use_json_output: bool = False
    strict_mode: bool = False
    ignore_missing_imports: bool = False
    follow_imports: str = "normal"
    cache_dir: Path | None = None
    incremental: bool = True
    warn_unused_ignores: bool = False


class ZubanAdapter(BaseToolAdapter):
    settings: ZubanSettings | None = None

    def __init__(self, settings: ZubanSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "ZubanAdapter initialized", extra={"has_settings": settings is not None}
        )

    async def init(self) -> None:
        if not self.settings:
            self.settings = ZubanSettings(
                timeout_seconds=300,
                max_workers=4,
            )
            logger.info("Using default ZubanSettings")
        await super().init()
        logger.debug(
            "ZubanAdapter initialization complete",
            extra={
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
                "has_cache_dir": self.settings.cache_dir is not None,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "Zuban (Type Check)"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "zuban"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            raise RuntimeError("Settings not initialized")

        cmd = [self.tool_name, "mypy", "--config-file", "mypy.ini"]

        if self.settings.strict_mode:
            cmd.append("--strict")

        if self.settings.ignore_missing_imports:
            cmd.append("--ignore-missing-imports")

        if self.settings.follow_imports == "normal":
            pass
        elif self.settings.follow_imports == "skip":
            cmd.append("--follow-untyped-imports")
        elif self.settings.follow_imports == "silent":
            pass

        if self.settings.cache_dir:
            cmd.extend(["--cache-dir", str(self.settings.cache_dir)])

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built Zuban command",
            extra={
                "file_count": len(files),
                "strict_mode": self.settings.strict_mode,
                "incremental": self.settings.incremental,
                "follow_imports": self.settings.follow_imports,
                "has_cache_dir": self.settings.cache_dir is not None,
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
            "Parsing Zuban text output",
            extra={"output_length": len(result.raw_output)},
        )

        return self._parse_text_output(result.raw_output)

    def _check_has_column(self, parts: list[str]) -> tuple[bool, int | None]:
        has_column = parts[2].strip().isdigit()
        column_number = int(parts[2].strip()) if has_column else None
        return has_column, column_number

    def _parse_with_column_format(
        self, file_path_str: str, line_str: str, parts: list[str]
    ) -> tuple[Path, int, int | None, str, str] | None:
        if not line_str.isdigit():
            return None

        line_number = int(line_str)
        column_number = int(line_str)

        severity_and_message = parts[2].strip() if len(parts) > 2 else ""
        message_with_code = parts[3].strip() if len(parts) > 3 else severity_and_message

        message, code = self._extract_message_and_code(message_with_code)

        return (Path(file_path_str), line_number, column_number, message, code)

    def _parse_without_column_format(
        self, file_path_str: str, line_str: str, parts: list[str]
    ) -> tuple[Path, int, int | None, str, str]:
        file_path = Path(file_path_str)
        message_with_code = (
            parts[2].strip() + ":" + parts[3].strip()
            if len(parts) > 3
            else parts[2].strip()
        )
        message, code = self._extract_message_and_code(message_with_code)

        return file_path, int(line_str), None, message, code

    def _parse_standard_format(
        self, file_path_str: str, line_str: str, parts: list[str]
    ) -> tuple[Path, int, int | None, str, str]:
        file_path = Path(file_path_str)
        line_number = int(line_str)

        severity_and_message = parts[2].strip()
        message_with_code = parts[3].strip() if len(parts) > 3 else severity_and_message

        message, code = self._extract_message_and_code(message_with_code)

        return file_path, line_number, None, message, code

    def _extract_parts_from_line(
        self, line: str
    ) -> tuple[Path, int, int | None, str, str] | None:
        if ":" not in line:
            return None

        parts = line.split(":", maxsplit=3)
        if len(parts) < 3:
            return None

        try:
            file_path_str = parts[0].strip()
            line_str = parts[1].strip()

            if not line_str:
                if len(parts) >= 4:
                    line_str = parts[1].strip()
                    int(line_str)

                    result = self._parse_with_column_format(
                        file_path_str, line_str, parts
                    )
                    if result is not None:
                        return result

                    return self._parse_without_column_format(
                        file_path_str, line_str, parts
                    )
                else:
                    return None
            else:
                return self._parse_standard_format(file_path_str, line_str, parts)
        except (ValueError, IndexError):
            return None

    def _extract_message_and_code(self, message_and_code_str: str) -> tuple[str, str]:
        if " error: " in message_and_code_str:
            _, message_part = message_and_code_str.split(" error: ", 1)
        elif " warning: " in message_and_code_str:
            _, message_part = message_and_code_str.split(" warning: ", 1)
        else:
            message_part = message_and_code_str

        code = ""
        if " [" in message_part and "]" in message_part:
            start_bracket = message_part.rfind(" [")
            end_bracket = message_part.rfind("]")
            if (
                start_bracket != -1
                and end_bracket != -1
                and end_bracket > start_bracket
            ):
                code = message_part[start_bracket + 2 : end_bracket]
                message_part = message_part[:start_bracket].strip()

        return message_part.strip(), code

    def _determine_severity_and_message(
        self,
        severity_and_message: str,
        has_column: bool,
        parts: list[str],
        original_message: str,
    ) -> tuple[str, str]:
        severity = "error"
        message = original_message

        if severity_and_message.lower().startswith("warning"):
            severity = "warning"
            message = (
                severity_and_message[len("warning") :].strip()
                if not has_column or len(parts) <= 4
                else original_message
            )
        elif severity_and_message.lower().startswith("error"):
            message = (
                severity_and_message[len("error") :].strip()
                if not has_column or len(parts) <= 4
                else original_message
            )

        return severity, message

    def _parse_text_output(self, output: str) -> list[ToolIssue]:
        issues = []
        lines = output.strip().split("\n")

        for line in lines:
            if ":" not in line or ("error:" not in line and "warning:" not in line):
                continue

            if (
                "Found" in line
                and ("error" in line or "warning" in line)
                and "file" in line
            ):
                continue

            parts_result = self._extract_parts_from_line(line)
            if parts_result is None:
                continue

            (
                file_path,
                line_number,
                column_number,
                message,
                code,
            ) = parts_result

            severity = "error" if "error:" in line else "warning"

            issue = ToolIssue(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                message=message,
                code=code,
                severity=severity,
            )
            issues.append(issue)

        logger.info(
            "Parsed Zuban text output",
            extra={
                "total_issues": len(issues),
                "files_with_issues": len({str(i.file_path) for i in issues}),
            },
        )
        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.TYPE

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
            check_type=QACheckType.TYPE,
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
            timeout_seconds=180,
            parallel_safe=True,
            stage="comprehensive",
            settings={
                "strict_mode": False,
                "incremental": False,
                "follow_imports": "normal",
                "warn_unused_ignores": False,
                "ignore_missing_imports": True,
            },
        )
