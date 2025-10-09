"""Configuration models for ACB Quality Assurance framework."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from crackerjack.models.qa_results import QACheckType


class QACheckConfig(BaseModel):
    """Configuration for a single quality assurance check.

    This model defines how a QA check should be executed, including
    file patterns, exclusions, timeouts, and check-specific settings.
    """

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
        default=300,  # 5 minutes default
        gt=0,  # Must be positive
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
        """Check if this is a fast stage check."""
        return self.stage == "fast"

    @property
    def is_comprehensive_stage(self) -> bool:
        """Check if this is a comprehensive stage check."""
        return self.stage == "comprehensive"


class QAOrchestratorConfig(BaseModel):
    """Configuration for the quality assurance orchestrator.

    This model defines global settings for QA execution, including
    parallelization, caching, and execution order.
    """

    project_root: Path = Field(
        ...,
        description="Root directory of the project being checked",
    )
    max_parallel_checks: int = Field(
        default=4,
        gt=0,  # Must be positive
        description="Maximum number of checks to run in parallel",
    )
    enable_caching: bool = Field(
        default=True,
        description="Whether to cache check results",
    )
    cache_directory: Path | None = Field(
        default=None,
        description="Directory for caching results (None = use default)",
    )
    fail_fast: bool = Field(
        default=False,
        description="Stop execution on first failure",
    )
    run_formatters_first: bool = Field(
        default=True,
        description="Run formatter checks before other checks",
    )
    enable_incremental: bool = Field(
        default=True,
        description="Only check modified files when possible",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output",
    )
    checks: list[QACheckConfig] = Field(
        default_factory=list,
        description="List of QA checks to execute",
    )

    @property
    def fast_checks(self) -> list[QACheckConfig]:
        """Get all fast stage checks."""
        return [check for check in self.checks if check.is_fast_stage]

    @property
    def comprehensive_checks(self) -> list[QACheckConfig]:
        """Get all comprehensive stage checks."""
        return [check for check in self.checks if check.is_comprehensive_stage]

    @property
    def formatter_checks(self) -> list[QACheckConfig]:
        """Get all formatter checks."""
        return [check for check in self.checks if check.is_formatter]

    @property
    def enabled_checks(self) -> list[QACheckConfig]:
        """Get all enabled checks."""
        return [check for check in self.checks if check.enabled]
