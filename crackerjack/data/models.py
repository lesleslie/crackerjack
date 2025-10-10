"""SQLModel data models for the Crackerjack data layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, String
from sqlmodel import Field, SQLModel


class QualityBaselineRecord(SQLModel, table=True):
    """Persistent representation of quality metrics for a git revision."""

    __tablename__ = "quality_baselines"

    id: int | None = Field(default=None, primary_key=True)
    git_hash: str = Field(sa_column=Column(String(64), unique=True, index=True))
    recorded_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), index=True),
    )
    coverage_percent: float = Field(default=0.0)
    test_count: int = Field(default=0)
    test_pass_rate: float = Field(default=0.0)
    hook_failures: int = Field(default=0)
    complexity_violations: int = Field(default=0)
    security_issues: int = Field(default=0)
    type_errors: int = Field(default=0)
    linting_issues: int = Field(default=0)
    quality_score: int = Field(default=0)
    extra_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """Update this record in-place from a dictionary of values."""
        for key, value in data.items():
            if not hasattr(self, key):
                continue
            setattr(self, key, value)


class ProjectHealthRecord(SQLModel, table=True):
    """Persistent representation of project health metrics."""

    __tablename__ = "project_health"

    id: int | None = Field(default=None, primary_key=True)
    project_root: str = Field(sa_column=Column(String(255), unique=True, index=True))
    lint_error_trend: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    test_coverage_trend: list[float] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    dependency_age: dict[str, int] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    config_completeness: float = Field(default=0.0)
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
    )


class DependencyMonitorCacheRecord(SQLModel, table=True):
    """Cache entry for dependency monitor state."""

    __tablename__ = "dependency_monitor_cache"

    id: int | None = Field(default=None, primary_key=True)
    project_root: str = Field(sa_column=Column(String(255), unique=True, index=True))
    cache_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True)),
    )
