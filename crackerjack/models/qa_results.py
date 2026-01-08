from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QAResultStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


class QACheckType(str, Enum):
    LINT = "lint"
    FORMAT = "format"
    TYPE = "type"
    SECURITY = "security"
    SAST = "sast"
    COMPLEXITY = "complexity"
    REFACTOR = "refactor"
    TEST = "test"


class QAResult(BaseModel):
    check_id: UUID = Field(
        ...,
        description="Unique identifier for the check that produced this result",
    )
    check_name: str = Field(
        ...,
        description="Human-readable name of the check (e.g., 'ruff-format', 'pyright')",
    )
    check_type: QACheckType = Field(
        ...,
        description="Category of the check (lint, format, type_check, etc.)",
    )
    status: QAResultStatus = Field(
        ...,
        description="Outcome status of the check",
    )
    message: str = Field(
        default="",
        description="Summary message describing the result",
    )
    details: str = Field(
        default="",
        description="Detailed output from the check (stdout/stderr)",
    )
    files_checked: list[Path] = Field(
        default_factory=list,
        description="List of files that were checked",
    )
    files_modified: list[Path] = Field(
        default_factory=list,
        description="List of files modified by the check (for formatters)",
    )
    issues_found: int = Field(
        default=0,
        description="Number of issues found (errors, warnings, style violations)",
    )
    issues_fixed: int = Field(
        default=0,
        description="Number of issues automatically fixed",
    )
    execution_time_ms: float = Field(
        default=0.0,
        description="Execution time in milliseconds",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the check was executed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional check-specific metadata",
    )

    @property
    def is_success(self) -> bool:
        return self.status in (QAResultStatus.SUCCESS, QAResultStatus.WARNING)

    @property
    def is_failure(self) -> bool:
        return self.status == QAResultStatus.FAILURE

    @property
    def is_warning(self) -> bool:
        return self.status == QAResultStatus.WARNING

    @property
    def has_issues(self) -> bool:
        return self.issues_found > 0

    def to_summary(self) -> str:
        summary_parts = [f"{self.check_name}: {self.status.value}"]

        if self.issues_found > 0:
            summary_parts.append(f"{self.issues_found} issues found")

        if self.issues_fixed > 0:
            summary_parts.append(f"{self.issues_fixed} fixed")

        if self.execution_time_ms > 0:
            summary_parts.append(f"({self.execution_time_ms:.0f}ms)")

        return " | ".join(summary_parts)
