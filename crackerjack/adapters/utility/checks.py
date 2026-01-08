from __future__ import annotations

import asyncio
import logging
import subprocess
import typing as t
from enum import Enum
from pathlib import Path
from uuid import UUID

import tomli
import yaml
from pydantic import Field, field_validator

from crackerjack.adapters._qa_adapter_base import QAAdapterBase, QABaseSettings
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus
from crackerjack.services.regex_patterns import CompiledPatternCache

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


MODULE_ID = UUID("ed516d6d-b273-458a-a2fc-c656046897cd")
MODULE_STATUS = AdapterStatus.STABLE


logger = logging.getLogger(__name__)


class UtilityCheckType(str, Enum):
    TEXT_PATTERN = "text_pattern"
    SYNTAX_VALIDATION = "syntax_validation"
    SIZE_CHECK = "size_check"
    EOF_NEWLINE = "eof_newline"
    DEPENDENCY_LOCK = "dependency_lock"


class UtilityCheckSettings(QABaseSettings):
    check_type: UtilityCheckType = Field(
        ...,
        description="Type of utility check to perform",
    )
    pattern: str | None = Field(
        None,
        description="Regex pattern for TEXT_PATTERN checks",
    )
    parser_type: str | None = Field(
        None,
        description="Parser type for SYNTAX_VALIDATION (yaml, toml, json)",
    )
    max_size_bytes: int | None = Field(
        None,
        ge=0,
        description="Maximum file size in bytes for SIZE_CHECK",
    )
    auto_fix: bool = Field(
        False,
        description="Whether to automatically fix issues when possible",
    )
    lock_command: list[str] | None = Field(
        None,
        description="Command to run for DEPENDENCY_LOCK checks",
    )

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                CompiledPatternCache.get_compiled_pattern(v)
            except ValueError as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v

    @field_validator("parser_type")
    @classmethod
    def validate_parser_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("yaml", "toml", "json"):
            raise ValueError(f"Unsupported parser type: {v}")
        return v


class UtilityCheckAdapter(QAAdapterBase):
    settings: UtilityCheckSettings | None = None

    def __init__(self, settings: UtilityCheckSettings | None = None) -> None:
        super().__init__()
        if settings:
            self.settings = settings

    async def init(self) -> None:
        if not self.settings:
            self.settings = UtilityCheckSettings(
                check_type=UtilityCheckType.TEXT_PATTERN,
                pattern=r"\s+$",
                parser_type=None,
                max_size_bytes=None,
                auto_fix=True,
                lock_command=None,
                timeout_seconds=300,
                max_workers=4,
            )
        await super().init()

    @property
    def adapter_name(self) -> str:
        if self.settings:
            return f"UtilityCheck ({self.settings.check_type.value})"
        return "UtilityCheck"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        if not self._initialized:
            await self.init()

        if not self.settings:
            raise RuntimeError("Settings not initialized")

        start_time = asyncio.get_event_loop().time()

        target_files = await self._get_target_files(files, config)

        if not target_files:
            return self._create_skipped_result("No files to check", start_time)

        check_type = self.settings.check_type

        if check_type == UtilityCheckType.TEXT_PATTERN:
            result = await self._check_text_pattern(target_files, start_time)
        elif check_type == UtilityCheckType.EOF_NEWLINE:
            result = await self._check_eof_newline(target_files, start_time)
        elif check_type == UtilityCheckType.SYNTAX_VALIDATION:
            result = await self._check_syntax_validation(target_files, start_time)
        elif check_type == UtilityCheckType.SIZE_CHECK:
            result = await self._check_size_limit(target_files, start_time)
        elif check_type == UtilityCheckType.DEPENDENCY_LOCK:
            result = await self._check_dependency_lock(target_files, start_time)
        else:
            raise ValueError(f"Unsupported check type: {check_type}")

        return result

    @staticmethod
    def _is_file_excluded(
        file_path: Path,
        exclude_patterns: list[str],
    ) -> bool:
        for exclude_pattern in exclude_patterns:
            if file_path.match(exclude_pattern):
                return True
        return False

    def _apply_exclude_filters(
        self,
        files: list[Path],
        exclude_patterns: list[str],
    ) -> list[Path]:
        return [
            file_path
            for file_path in files
            if not self._is_file_excluded(file_path, exclude_patterns)
        ]

    async def _get_target_files(
        self,
        files: list[Path] | None,
        config: QACheckConfig | None,
    ) -> list[Path]:
        if files:
            return files

        if not self.settings:
            return []

        patterns = config.file_patterns if config else self.settings.file_patterns
        exclude_patterns = (
            config.exclude_patterns if config else self.settings.exclude_patterns
        )

        target_files: list[Path] = []
        for pattern in patterns:
            target_files.extend(Path.cwd().glob(pattern))

        if exclude_patterns:
            target_files = self._apply_exclude_filters(target_files, exclude_patterns)

        return [f for f in target_files if f.is_file()]

    def _process_file_lines(
        self,
        lines: list[str],
        pattern: t.Pattern[str],
    ) -> tuple[list[str], int]:
        fixed_lines = []
        issues_count = 0

        for line in lines:
            if pattern.search(line):
                issues_count += 1
                if self.settings and self.settings.auto_fix:
                    fixed_lines.append(pattern.sub("", line))
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)

        return fixed_lines, issues_count

    def _create_pattern_result(
        self,
        files: list[Path],
        issues_found: int,
        issues_fixed: int,
        files_modified: list[Path],
        elapsed_ms: float,
    ) -> QAResult:
        if issues_found == 0:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.SUCCESS,
                message="No pattern violations found",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        elif issues_fixed == issues_found:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.SUCCESS,
                message=f"Fixed {issues_fixed} pattern violations",
                files_checked=files,
                files_modified=files_modified,
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                execution_time_ms=elapsed_ms,
            )
        return QAResult(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.FAILURE,
            message=f"Found {issues_found} pattern violations",
            files_checked=files,
            files_modified=files_modified,
            issues_found=issues_found,
            issues_fixed=issues_fixed,
            execution_time_ms=elapsed_ms,
        )

    async def _check_text_pattern(
        self,
        files: list[Path],
        start_time: float,
    ) -> QAResult:
        if not self.settings or not self.settings.pattern:
            raise ValueError("Pattern not configured")

        pattern = CompiledPatternCache.get_compiled_pattern(self.settings.pattern)
        issues_found = 0
        issues_fixed = 0
        files_modified: list[Path] = []

        for file_path in files:
            try:
                content = file_path.read_text()
                lines = content.splitlines(keepends=True)

                fixed_lines, file_issues = self._process_file_lines(lines, pattern)
                issues_found += file_issues

                if file_issues > 0 and self.settings.auto_fix:
                    file_path.write_text("".join(fixed_lines))
                    files_modified.append(file_path)
                    issues_fixed += file_issues

            except Exception as e:
                logger.warning(
                    "Failed to check file for pattern violations",
                    extra={
                        "file_path": str(file_path),
                        "check_type": self.settings.check_type.value,
                        "pattern": self.settings.pattern,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                continue

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        return self._create_pattern_result(
            files, issues_found, issues_fixed, files_modified, elapsed_ms
        )

    async def _check_eof_newline(
        self,
        files: list[Path],
        start_time: float,
    ) -> QAResult:
        issues_found = 0
        issues_fixed = 0
        files_modified: list[Path] = []

        for file_path in files:
            try:
                content = file_path.read_text()
                if content and not content.endswith("\n"):
                    issues_found += 1
                    if self.settings and self.settings.auto_fix:
                        file_path.write_text(content + "\n")
                        issues_fixed += 1
                        files_modified.append(file_path)
            except Exception as e:
                logger.warning(
                    "Failed to check file for EOF newline",
                    extra={
                        "file_path": str(file_path),
                        "check_type": self.settings.check_type.value
                        if self.settings
                        else "unknown",
                        "auto_fix": self.settings.auto_fix if self.settings else False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                continue

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        if issues_found == 0:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.SUCCESS,
                message="All files have proper EOF newlines",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        elif issues_fixed == issues_found:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.SUCCESS,
                message=f"Fixed {issues_fixed} EOF newline issues",
                files_checked=files,
                files_modified=files_modified,
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                execution_time_ms=elapsed_ms,
            )
        return QAResult(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.FAILURE,
            message=f"Found {issues_found} files missing EOF newlines",
            files_checked=files,
            issues_found=issues_found,
            execution_time_ms=elapsed_ms,
        )

    async def _check_syntax_validation(
        self,
        files: list[Path],
        start_time: float,
    ) -> QAResult:
        if not self.settings or not self.settings.parser_type:
            raise ValueError("Parser type not configured")

        parser_type = self.settings.parser_type
        issues_found = 0
        error_details: list[str] = []

        for file_path in files:
            try:
                content = file_path.read_text()

                if parser_type == "yaml":
                    yaml.safe_load(content)
                elif parser_type == "toml":
                    tomli.loads(content)
                elif parser_type == "json":
                    import json

                    json.loads(content)

            except Exception as e:
                issues_found += 1
                error_details.append(f"{file_path}: {e}")

                logger.warning(
                    "Failed to validate file syntax",
                    extra={
                        "file_path": str(file_path),
                        "check_type": self.settings.check_type.value
                        if self.settings
                        else "unknown",
                        "parser_type": parser_type,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        if issues_found == 0:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.SUCCESS,
                message=f"All {parser_type.upper()} files are valid",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        return QAResult(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.FAILURE,
            message=f"Found {issues_found} {parser_type.upper()} syntax errors",
            details="\n".join(error_details),
            files_checked=files,
            issues_found=issues_found,
            execution_time_ms=elapsed_ms,
        )

    async def _check_size_limit(
        self,
        files: list[Path],
        start_time: float,
    ) -> QAResult:
        if not self.settings or self.settings.max_size_bytes is None:
            raise ValueError("Max size not configured")

        max_size = self.settings.max_size_bytes
        issues_found = 0
        large_files: list[str] = []

        for file_path in files:
            try:
                file_size = file_path.stat().st_size
                if file_size > max_size:
                    issues_found += 1
                    size_mb = file_size / (1024 * 1024)
                    max_mb = max_size / (1024 * 1024)
                    large_files.append(
                        f"{file_path} ({size_mb:.2f} MB > {max_mb:.2f} MB)"
                    )
            except Exception as e:
                logger.warning(
                    "Failed to check file size",
                    extra={
                        "file_path": str(file_path),
                        "check_type": self.settings.check_type.value
                        if self.settings
                        else "unknown",
                        "max_size_bytes": max_size,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                continue

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        if issues_found == 0:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.SUCCESS,
                message="All files within size limits",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        return QAResult(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.FAILURE,
            message=f"Found {issues_found} files exceeding size limit",
            details="\n".join(large_files),
            files_checked=files,
            issues_found=issues_found,
            execution_time_ms=elapsed_ms,
        )

    async def _check_dependency_lock(
        self,
        files: list[Path],
        start_time: float,
    ) -> QAResult:
        if not self.settings or not self.settings.lock_command:
            raise ValueError("Lock command not configured")

        try:
            result = subprocess.run(
                self.settings.lock_command,
                capture_output=True,
                text=True,
                timeout=self.settings.timeout_seconds,
                check=False,
            )

            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            if result.returncode == 0:
                return QAResult(
                    check_id=MODULE_ID,
                    check_name=self.adapter_name,
                    check_type=QACheckType.FORMAT,
                    status=QAResultStatus.SUCCESS,
                    message="Dependency lock file is up to date",
                    files_checked=files,
                    execution_time_ms=elapsed_ms,
                )
            else:
                return QAResult(
                    check_id=MODULE_ID,
                    check_name=self.adapter_name,
                    check_type=QACheckType.FORMAT,
                    status=QAResultStatus.FAILURE,
                    message="Dependency lock file is out of sync",
                    details=result.stderr or result.stdout,
                    files_checked=files,
                    issues_found=1,
                    execution_time_ms=elapsed_ms,
                )

        except subprocess.TimeoutExpired:
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.ERROR,
                message="Dependency lock check timed out",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.ERROR,
                message=f"Dependency lock check failed: {e}",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )

    def _create_skipped_result(self, reason: str, start_time: float) -> QAResult:
        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        return QAResult(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.SKIPPED,
            message=reason,
            execution_time_ms=elapsed_ms,
        )

    @staticmethod
    def _get_check_type() -> QACheckType:
        return QACheckType.FORMAT

    def _get_syntax_validation_patterns(self) -> list[str]:
        if not self.settings:
            return ["**/*.yaml", "**/*.toml", "**/*.json"]

        parser_patterns = {
            "yaml": ["**/*.yaml", "**/*.yml"],
            "toml": ["**/*.toml"],
            "json": ["**/*.json"],
        }
        return parser_patterns.get(
            self.settings.parser_type,
            ["**/*.yaml", "**/*.toml", "**/*.json"],
        )

    def _get_config_for_check_type(
        self, check_type: UtilityCheckType
    ) -> tuple[list[str], str, bool]:
        if check_type == UtilityCheckType.TEXT_PATTERN:
            return (
                ["**/*.py", "**/*.yaml", "**/*.toml", "**/*.json", "**/*.md"],
                "fast",
                self.settings.auto_fix if self.settings else False,
            )
        if check_type == UtilityCheckType.EOF_NEWLINE:
            return (["**/*"], "fast", True)
        if check_type == UtilityCheckType.SYNTAX_VALIDATION:
            return (self._get_syntax_validation_patterns(), "comprehensive", False)
        if check_type == UtilityCheckType.SIZE_CHECK:
            return (["**/*"], "fast", False)
        if check_type == UtilityCheckType.DEPENDENCY_LOCK:
            return (["uv.lock", "requirements.lock"], "fast", False)

        return (["**/*.py"], "fast", False)

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        if self.settings and self.settings.check_type:
            file_patterns, stage, is_formatter = self._get_config_for_check_type(
                self.settings.check_type
            )
        else:
            file_patterns = ["**/*.py", "**/*.yaml", "**/*.toml", "**/*.json"]
            stage = "fast"
            is_formatter = False

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=self._get_check_type(),
            enabled=True,
            file_patterns=file_patterns,
            exclude_patterns=[
                "**/.*",
                "**/.git/**",
                "**/.venv/**",
                "**/node_modules/**",
                "**/__pycache__/**",
            ],
            timeout_seconds=60,
            parallel_safe=True,
            is_formatter=is_formatter,
            stage=stage,
            settings={
                "check_type": self.settings.check_type.value
                if self.settings
                else "text_pattern",
                "auto_fix": self.settings.auto_fix if self.settings else False,
            },
        )
