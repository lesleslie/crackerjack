"""Typed stub for the Mahavishnu integration module.

This module exists so the type checker can resolve
``crackerjack.integration.mahavishnu_integration`` and so the call
sites in ``crackerjack/mahavishnu/mcp/tools/git_analytics.py`` and
``crackerjack/mcp/tools/mahavishnu_tools.py`` have the surface they
need at static-analysis time.

Production entry points:

- **Worker spawn**: vishnu workers spawn via the **tmux durable-worker
  contract** (Spec §9.4) — i.e., the existing
  ``mahavishnu.workers.contract.manager.DurableWorkerManager.spawn(...)``
  path wired through ``mahavishnu/terminal/adapters/tmux.py``. This is
  the runtime surface, NOT this stub class.
- **Cross-component analytics**: cross-project Git velocity / health /
  pattern data flows through the FastMCP tools registered at
  ``crackerjack/mcp/tools/mahavishnu_tools.py`` (and the
  ``crackerjack/mahavishnu/mcp/tools/git_analytics.py`` aggregators
  that back them). Vishnu consumes those tools via the MCP wire
  protocol; Crackerjack remains the canonical source.

The runtime bodies of this stub raise ``NotImplementedError``; the
class is a **type-checker shim** only and is not on the production
path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "CrossProjectPattern",
    "MahavishnuAggregator",
    "MahavishnuConfig",
    "RepositoryHealth",
    "RepositoryVelocity",
    "create_mahavishnu_aggregator",
]


@dataclass
class MahavishnuConfig:
    db_path: Path | str = ".crackerjack/mahavishnu.db"
    websocket_enabled: bool = False
    websocket_host: str = "127.0.0.1"
    websocket_port: int = 8686
    dashboard_refresh_interval: int = 300


@dataclass
class RepositoryVelocity:
    repository_name: str = ""
    repository_path: str = ""
    total_commits: int = 0
    avg_commits_per_day: float = 0.0
    avg_commits_per_week: float = 0.0
    conventional_compliance_rate: float = 0.0
    breaking_changes: int = 0
    merge_conflict_rate: float = 0.0
    health_score: float = 0.0
    trend_direction: str = "stable"


@dataclass
class RepositoryHealth:
    repository_name: str = ""
    health_score: float = 0.0
    risk_level: str = "low"
    stale_branches: list[str] = field(default_factory=list)
    unmerged_prs: int = 0
    large_files: list[str] = field(default_factory=list)
    last_activity: datetime | None = None
    recommendations: list[str] = field(default_factory=list)


@dataclass
class CrossProjectPattern:
    pattern_type: str = ""
    severity: str = "info"
    description: str = ""
    metric_value: float = 0.0
    affected_repositories: list[str] = field(default_factory=list)
    recommendation: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PortfolioDashboard:
    total_repositories: int = 0
    period_days: int = 0
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    aggregate_metrics: dict[str, Any] = field(default_factory=dict)
    repositories: list[RepositoryVelocity] = field(default_factory=list)
    top_performers: list[str] = field(default_factory=list)
    needs_attention: list[str] = field(default_factory=list)
    cross_project_patterns: list[CrossProjectPattern] = field(default_factory=list)


class MahavishnuAggregator:
    """Type-checker shim for the Mahavishnu aggregator.

    This class is **not** the production entry point for spawning
    workers. Production worker spawn happens through the **tmux
    durable-worker contract** (Spec §9.4) via
    ``mahavishnu.workers.contract.manager.DurableWorkerManager.spawn(...)``.

    For cross-component analytics, the production surface is the
    FastMCP tools registered at
    ``crackerjack/mcp/tools/mahavishnu_tools.py`` and the aggregator
    implementations at ``crackerjack/mahavishnu/mcp/tools/git_analytics.py``.
    Methods on this shim exist only so the ty gate can resolve the
    cross-module call sites; their runtime bodies raise
    ``NotImplementedError``.
    """

    def __init__(self, config: MahavishnuConfig | None = None) -> None:
        self.config = config or MahavishnuConfig()

    async def initialize(self) -> None:
        raise NotImplementedError(
            "Mahavishnu integration is provided by the Mahavishnu project."
        )

    async def get_cross_project_git_dashboard(
        self,
        project_paths: list[str],
        days_back: int,
    ) -> PortfolioDashboard:
        raise NotImplementedError

    async def get_repository_health(self, repo_path: Path) -> RepositoryHealth:
        raise NotImplementedError

    async def get_cross_project_patterns(
        self,
        project_paths: list[str],
        days_back: int,
    ) -> list[CrossProjectPattern]:
        raise NotImplementedError

    async def _collect_repository_velocity(
        self,
        repo_path: str | Path,
        period_start: datetime,
        period_end: datetime,
    ) -> RepositoryVelocity:
        raise NotImplementedError


def create_mahavishnu_aggregator(
    config: MahavishnuConfig | None = None,
) -> MahavishnuAggregator:
    return MahavishnuAggregator(config=config)
