"""Generic utility check adapter for simple ACB Quality Assurance checks.

This adapter handles simple, configuration-driven checks like whitespace,
EOF newlines, YAML/TOML validation, file size limits, and dependency locks.

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Configuration-driven validators and fixers
- Async execution with semaphore control
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import typing as t
from contextlib import suppress
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid7

import tomli
import yaml
from acb.config import Settings
from acb.depends import depends
from pydantic import Field, validator

from crackerjack.adapters.qa._base import QAAdapterBase, QABaseSettings
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig

# ACB Module Registration (REQUIRED)
MODULE_ID = uuid7()
MODULE_STATUS = "stable"


class UtilityCheckType(str, Enum):
    """Types of utility checks supported by this adapter."""

    TEXT_PATTERN = "text_pattern"
    SYNTAX_VALIDATION = "syntax_validation"
    SIZE_CHECK = "size_check"
    EOF_NEWLINE = "eof_newline"
    DEPENDENCY_LOCK = "dependency_lock"


class UtilityCheckSettings(QABaseSettings):
    """Settings for utility check adapter.

    Configuration-driven checks are defined here or loaded from YAML.
    """

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

    @validator("pattern")
    def validate_pattern(cls, v: str | None, values: dict[str, t.Any]) -> str | None:
        """Validate regex pattern for TEXT_PATTERN checks."""
        if values.get("check_type") == UtilityCheckType.TEXT_PATTERN:
            if not v:
                raise ValueError("pattern is required for TEXT_PATTERN checks")
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v

    @validator("parser_type")
    def validate_parser_type(
        cls, v: str | None, values: dict[str, t.Any]
    ) -> str | None:
        """Validate parser type for SYNTAX_VALIDATION checks."""
        if values.get("check_type") == UtilityCheckType.SYNTAX_VALIDATION:
            if not v:
                raise ValueError("parser_type is required for SYNTAX_VALIDATION checks")
            if v not in ("yaml", "toml", "json"):
                raise ValueError(f"Unsupported parser type: {v}")
        return v


class UtilityCheckAdapter(QAAdapterBase):
    """Generic adapter for configuration-driven utility checks.

    Handles simple checks like:
    - Trailing whitespace detection/fixing
    - EOF newline enforcement
    - YAML/TOML/JSON syntax validation
    - File size limits
    - Dependency lock verification (uv.lock)

    Example:
        ```python
        from uuid import uuid7
        from crackerjack.adapters.qa.utility_check import (
            UtilityCheckAdapter,
            UtilityCheckSettings,
            UtilityCheckType,
        )

        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern=r"\\s+$",
            auto_fix=True,
        )
        adapter = UtilityCheckAdapter(settings=settings)
        await adapter.init()
        result = await adapter.check(files=[Path("src/file.py")])
        ```
    """

    settings: UtilityCheckSettings | None = None

    def __init__(self, settings: UtilityCheckSettings | None = None) -> None:
        """Initialize utility check adapter.

        Args:
            settings: Optional settings override
        """
        super().__init__()
        if settings:
            self.settings = settings

    async def init(self) -> None:
        """Initialize adapter with settings validation."""
        if not self.settings:
            # Default to trailing whitespace check if no settings provided
            self.settings = UtilityCheckSettings(
                check_type=UtilityCheckType.TEXT_PATTERN,
                pattern=r"\s+$",
                auto_fix=True,
            )
        await super().init()

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name."""
        if self.settings:
            return f"UtilityCheck ({self.settings.check_type.value})"
        return "UtilityCheck"

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        """Execute utility check on files.

        Args:
            files: List of files to check (None = check all matching patterns)
            config: Optional configuration override

        Returns:
            QAResult with check execution results
        """
        if not self._initialized:
            await self.init()

        if not self.settings:
            raise RuntimeError("Settings not initialized")

        start_time = asyncio.get_event_loop().time()

        # Determine files to check
        target_files = await self._get_target_files(files, config)

        if not target_files:
            return self._create_skipped_result("No files to check", start_time)

        # Execute appropriate check based on type
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

    async def _get_target_files(
        self,
        files: list[Path] | None,
        config: QACheckConfig | None,
    ) -> list[Path]:
        """Get list of files to check based on patterns.

        Args:
            files: Explicit file list or None for pattern matching
            config: Configuration with file patterns

        Returns:
            List of Path objects to check
        """
        if files:
            return files

        if not self.settings:
            return []

        # Use config patterns if available, otherwise use settings patterns
        patterns = (
            config.file_patterns if config else self.settings.file_patterns
        )
        exclude_patterns = (
            config.exclude_patterns if config else self.settings.exclude_patterns
        )

        # Simple glob-based file discovery
        # In production, this would integrate with git/project structure
        target_files: list[Path] = []
        for pattern in patterns:
            target_files.extend(Path.cwd().glob(pattern))

        # Filter out excluded files
        if exclude_patterns:
            filtered_files = []
            for file_path in target_files:
                excluded = False
                for exclude_pattern in exclude_patterns:
                    if file_path.match(exclude_pattern):
                        excluded = True
                        break
                if not excluded:
                    filtered_files.append(file_path)
            target_files = filtered_files

        return [f for f in target_files if f.is_file()]

    async def _check_text_pattern(
        self,
        files: list[Path],
        start_time: float,
    ) -> QAResult:
        """Check files for text pattern violations.

        Args:
            files: Files to check
            start_time: Check start time

        Returns:
            QAResult with pattern check results
        """
        if not self.settings or not self.settings.pattern:
            raise ValueError("Pattern not configured")

        pattern = re.compile(self.settings.pattern)
        issues_found = 0
        issues_fixed = 0
        files_modified: list[Path] = []

        for file_path in files:
            try:
                content = file_path.read_text()
                lines = content.splitlines(keepends=True)
                has_issues = False
                fixed_lines = []

                for line in lines:
                    if pattern.search(line):
                        has_issues = True
                        issues_found += 1
                        if self.settings.auto_fix:
                            # Remove trailing whitespace
                            fixed_line = pattern.sub("", line)
                            fixed_lines.append(fixed_line)
                            issues_fixed += 1
                        else:
                            fixed_lines.append(line)
                    else:
                        fixed_lines.append(line)

                if has_issues and self.settings.auto_fix:
                    file_path.write_text("".join(fixed_lines))
                    files_modified.append(file_path)

            except Exception as e:
                # Continue checking other files
                continue

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        if issues_found == 0:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
                status=QAResultStatus.SUCCESS,
                message="No pattern violations found",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        elif issues_fixed == issues_found:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
                status=QAResultStatus.SUCCESS,
                message=f"Fixed {issues_fixed} pattern violations",
                files_checked=files,
                files_modified=files_modified,
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                execution_time_ms=elapsed_ms,
            )
        else:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
                status=QAResultStatus.FAILURE,
                message=f"Found {issues_found} pattern violations",
                files_checked=files,
                files_modified=files_modified,
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                execution_time_ms=elapsed_ms,
            )

    async def _check_eof_newline(
        self,
        files: list[Path],
        start_time: float,
    ) -> QAResult:
        """Check files for missing EOF newlines.

        Args:
            files: Files to check
            start_time: Check start time

        Returns:
            QAResult with EOF check results
        """
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
            except Exception:
                continue

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        if issues_found == 0:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
                status=QAResultStatus.SUCCESS,
                message="All files have proper EOF newlines",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        elif issues_fixed == issues_found:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
                status=QAResultStatus.SUCCESS,
                message=f"Fixed {issues_fixed} EOF newline issues",
                files_checked=files,
                files_modified=files_modified,
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                execution_time_ms=elapsed_ms,
            )
        else:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
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
        """Validate file syntax (YAML/TOML/JSON).

        Args:
            files: Files to check
            start_time: Check start time

        Returns:
            QAResult with syntax validation results
        """
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
                error_details.append(f"{file_path}: {str(e)}")

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        if issues_found == 0:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
                status=QAResultStatus.SUCCESS,
                message=f"All {parser_type.upper()} files are valid",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        else:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
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
        """Check files against size limits.

        Args:
            files: Files to check
            start_time: Check start time

        Returns:
            QAResult with size check results
        """
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
            except Exception:
                continue

        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        if issues_found == 0:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
                status=QAResultStatus.SUCCESS,
                message="All files within size limits",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )
        else:
            return QAResult(
                check_id=MODULE_ID,
                check_name=self.adapter_name,
                check_type=QACheckType.UTILITY,
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
        """Check dependency lock file integrity.

        Args:
            files: Files to check (typically uv.lock)
            start_time: Check start time

        Returns:
            QAResult with dependency lock check results
        """
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
                    check_type=QACheckType.UTILITY,
                    status=QAResultStatus.SUCCESS,
                    message="Dependency lock file is up to date",
                    files_checked=files,
                    execution_time_ms=elapsed_ms,
                )
            else:
                return QAResult(
                    check_id=MODULE_ID,
                    check_name=self.adapter_name,
                    check_type=QACheckType.UTILITY,
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
                check_type=QACheckType.UTILITY,
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
                check_type=QACheckType.UTILITY,
                status=QAResultStatus.ERROR,
                message=f"Dependency lock check failed: {str(e)}",
                files_checked=files,
                execution_time_ms=elapsed_ms,
            )

    def _create_skipped_result(self, reason: str, start_time: float) -> QAResult:
        """Create a skipped result.

        Args:
            reason: Reason for skipping
            start_time: Check start time

        Returns:
            QAResult with skipped status
        """
        elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        return QAResult(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.UTILITY,
            status=QAResultStatus.SKIPPED,
            message=reason,
            execution_time_ms=elapsed_ms,
        )

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for utility checks.

        Returns:
            QACheckConfig with sensible defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.UTILITY,
            enabled=True,
            file_patterns=["**/*.py", "**/*.yaml", "**/*.toml", "**/*.json"],
            timeout_seconds=30,
            parallel_safe=True,
            stage="fast",
            settings={
                "check_type": "text_pattern",
                "pattern": r"\s+$",
                "auto_fix": True,
            },
        )


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(UtilityCheckAdapter)
