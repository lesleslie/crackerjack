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
import logging
import subprocess
import typing as t
from contextlib import suppress
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4

import tomli
import yaml
from acb.depends import depends
from pydantic import Field, validator

from crackerjack.adapters._qa_adapter_base import QAAdapterBase, QABaseSettings
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus
from crackerjack.services.regex_patterns import CompiledPatternCache

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig

# ACB Module Registration (REQUIRED)
MODULE_ID = uuid4()
MODULE_STATUS = "stable"

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


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
        """Validate regex pattern using safe compilation.

        Uses CompiledPatternCache for security and performance.
        Pattern validation only occurs if pattern is provided.
        Runtime check() will enforce required patterns.

        Args:
            v: Pattern string to validate
            values: Other field values (unused)

        Returns:
            Validated pattern string or None

        Raises:
            ValueError: If pattern compilation fails
        """
        if v is not None:
            try:
                # Use cached, safe pattern compilation
                CompiledPatternCache.get_compiled_pattern(v)
            except ValueError as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v

    @validator("parser_type")
    def validate_parser_type(
        cls, v: str | None, values: dict[str, t.Any]
    ) -> str | None:
        """Validate parser type for SYNTAX_VALIDATION checks.

        Parser type validation only occurs if parser_type is provided.
        Runtime check() will enforce required parser_type.
        """
        if v is not None and v not in ("yaml", "toml", "json"):
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

    def _is_file_excluded(
        self,
        file_path: Path,
        exclude_patterns: list[str],
    ) -> bool:
        """Check if file matches any exclude pattern.

        Args:
            file_path: File to check
            exclude_patterns: List of glob patterns to exclude

        Returns:
            True if file should be excluded
        """
        for exclude_pattern in exclude_patterns:
            if file_path.match(exclude_pattern):
                return True
        return False

    def _apply_exclude_filters(
        self,
        files: list[Path],
        exclude_patterns: list[str],
    ) -> list[Path]:
        """Filter files by exclude patterns.

        Args:
            files: Files to filter
            exclude_patterns: List of glob patterns to exclude

        Returns:
            Filtered file list
        """
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
        patterns = config.file_patterns if config else self.settings.file_patterns
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
            target_files = self._apply_exclude_filters(target_files, exclude_patterns)

        return [f for f in target_files if f.is_file()]

    def _process_file_lines(
        self,
        lines: list[str],
        pattern: t.Pattern[str],
    ) -> tuple[list[str], int]:
        """Process file lines for pattern violations.

        Args:
            lines: File lines to process
            pattern: Compiled regex pattern

        Returns:
            Tuple of (fixed_lines, issues_count)
        """
        fixed_lines = []
        issues_count = 0

        for line in lines:
            if pattern.search(line):
                issues_count += 1
                if self.settings and self.settings.auto_fix:
                    # Remove pattern matches (e.g., trailing whitespace)
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
        """Create QAResult for pattern check.

        Args:
            files: Files checked
            issues_found: Number of issues found
            issues_fixed: Number of issues fixed
            files_modified: List of modified files
            elapsed_ms: Execution time in milliseconds

        Returns:
            QAResult with appropriate status
        """
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
        """Check files for text pattern violations.

        Args:
            files: Files to check
            start_time: Check start time

        Returns:
            QAResult with pattern check results
        """
        if not self.settings or not self.settings.pattern:
            raise ValueError("Pattern not configured")

        # Use safe cached pattern compilation
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
                # Add structured logging for failures
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
            except Exception as e:
                # Add structured logging for failures
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
                error_details.append(f"{file_path}: {e}")
                # Add structured logging for failures
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
            except Exception as e:
                # Add structured logging for failures
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
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.SKIPPED,
            message=reason,
            execution_time_ms=elapsed_ms,
        )

    def _get_check_type(self) -> QACheckType:
        """Determine QA check type based on utility check type.

        Utility checks map to FORMAT type since they can format/fix files.

        Returns:
            QACheckType.FORMAT for all utility checks
        """
        return QACheckType.FORMAT

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration for utility checks.

        Configuration varies based on the check_type setting:
        - TEXT_PATTERN: fast stage, common text files
        - EOF_NEWLINE: fast stage, all files, is_formatter=True
        - SYNTAX_VALIDATION: comprehensive stage, parser-specific patterns
        - SIZE_CHECK: fast stage, all files
        - DEPENDENCY_LOCK: fast stage, lock files only

        Returns:
            QACheckConfig with check-type-specific defaults
        """
        from crackerjack.models.qa_config import QACheckConfig

        # Determine settings based on configured check type
        if self.settings and self.settings.check_type:
            check_type = self.settings.check_type

            # Configure file patterns based on check type
            if check_type == UtilityCheckType.TEXT_PATTERN:
                file_patterns = [
                    "**/*.py",
                    "**/*.yaml",
                    "**/*.toml",
                    "**/*.json",
                    "**/*.md",
                ]
                stage = "fast"
                is_formatter = self.settings.auto_fix
            elif check_type == UtilityCheckType.EOF_NEWLINE:
                file_patterns = ["**/*"]  # All files
                stage = "fast"
                is_formatter = True  # Can modify files
            elif check_type == UtilityCheckType.SYNTAX_VALIDATION:
                # Parser-specific patterns
                if self.settings.parser_type == "yaml":
                    file_patterns = ["**/*.yaml", "**/*.yml"]
                elif self.settings.parser_type == "toml":
                    file_patterns = ["**/*.toml"]
                elif self.settings.parser_type == "json":
                    file_patterns = ["**/*.json"]
                else:
                    file_patterns = ["**/*.yaml", "**/*.toml", "**/*.json"]
                stage = "comprehensive"
                is_formatter = False
            elif check_type == UtilityCheckType.SIZE_CHECK:
                file_patterns = ["**/*"]  # All files
                stage = "fast"
                is_formatter = False
            elif check_type == UtilityCheckType.DEPENDENCY_LOCK:
                file_patterns = ["uv.lock", "requirements.lock"]
                stage = "fast"
                is_formatter = False
            else:
                # Fallback defaults
                file_patterns = ["**/*.py"]
                stage = "fast"
                is_formatter = False
        else:
            # No settings, use generic defaults
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
            timeout_seconds=60,  # Utility checks should be fast
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


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(UtilityCheckAdapter)
