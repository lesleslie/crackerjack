from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel


class QualityBaselineRecord(SQLModel, table=True):
    __tablename__ = "quality_baselines"

    id: int | None = Field(default=None, primary_key=True)
    git_hash: str = Field(index=True, unique=True)
    recorded_at: datetime = Field(
        default_factory=datetime.utcnow,
        index=True,
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
    )

    def update_from_dict(self, data: dict[str, Any]) -> None:
        for key, value in data.items():
            if not hasattr(self, key):
                continue
            setattr(self, key, value)


class ProjectHealthRecord(SQLModel, table=True):
    __tablename__ = "project_health"

    id: int | None = Field(default=None, primary_key=True)
    project_name: str = Field(index=True, unique=True)
    health_score: int = Field(default=0)
    issue_count: int = Field(default=0)
    warning_count: int = Field(default=0)
    error_count: int = Field(default=0)
    maintenance_score: int = Field(default=0)
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
    )


class DependencyMonitorCacheRecord(SQLModel, table=True):
    __tablename__ = "dependency_monitor_cache"

    id: int | None = Field(default=None, primary_key=True)
    project_root: str = Field(index=True, unique=True)
    cache_data: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
    )
