from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from crackerjack.models.qa_results import QACheckType


class QACheckConfig(BaseModel):
    check_id: UUID = Field(
        ...,
        description="Unique identifier for this check",
    )
    check_name: str = Field(
        ...,
        description="Human-readable name (e.g., 'ruff-format', 'pyright')",
    )
    check_type: QACheckType = Field(
        ...,
        description="Category of the check (lint, format, type_check, etc.)",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this check is enabled",
    )
    file_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for files to check",
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for files to exclude",
    )
    timeout_seconds: int = Field(
        default=300,
        gt=0,
        description="Maximum execution time in seconds",
    )
    retry_on_failure: bool = Field(
        default=False,
        description="Whether to retry if the check fails",
    )
    is_formatter: bool = Field(
        default=False,
        description="Whether this check modifies files",
    )
    parallel_safe: bool = Field(
        default=True,
        description="Whether this check can run in parallel with others",
    )
    stage: str = Field(
        default="fast",
        description="Execution stage: 'fast' or 'comprehensive'",
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Check-specific configuration settings",
    )

    @property
    def is_fast_stage(self) -> bool:
        return self.stage == "fast"

    @property
    def is_comprehensive_stage(self) -> bool:
        return self.stage == "comprehensive"

    @property
    def name(self) -> str:
        return self.check_name
