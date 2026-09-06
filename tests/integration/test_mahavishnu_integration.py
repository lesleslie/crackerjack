"""Tests for ``crackerjack.integration.mahavishnu_integration``.

Covers the typed shim of ``MahavishnuConfig`` plus the dataclasses used by the
aggregator pipeline. The real implementation lives in the
``crackerjack-mahavishnu-git-analytics`` FastMCP server; this module exists so
crackerjack code that imports the configuration surface still type-checks.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass

import pytest

from crackerjack.integration.mahavishnu_integration import (
    CrossProjectPattern,
    MahavishnuAggregator,
    MahavishnuConfig,
    PortfolioDashboard,
    RepositoryHealth,
    RepositoryVelocity,
    create_mahavishnu_aggregator,
)


def test_mahavishnu_config_class_annotations() -> None:
    """``MahavishnuConfig`` is a class with annotated defaults."""
    config = MahavishnuConfig()
    assert config.db_path == ".crackerjack/mahavishnu.db"
    assert config.websocket_enabled is False
    assert config.websocket_host == "127.0.0.1"
    assert config.websocket_port == 8686
    assert config.dashboard_refresh_interval == 300


def test_mahavishnu_config_accepts_overrides() -> None:
    config = MahavishnuConfig(
        db_path="/tmp/test.db",
        websocket_enabled=True,
        websocket_port=9999,
        dashboard_refresh_interval=60,
    )
    assert config.db_path == "/tmp/test.db"
    assert config.websocket_enabled is True
    assert config.websocket_port == 9999
    assert config.dashboard_refresh_interval == 60


def test_repository_velocity_defaults() -> None:
    v = RepositoryVelocity()
    assert is_dataclass(v)
    assert v.repository_name == ""
    assert v.repository_path == ""
    assert v.total_commits == 0
    assert v.avg_commits_per_day == 0.0
    assert v.avg_commits_per_week == 0.0
    assert v.conventional_compliance_rate == 0.0
    assert v.breaking_changes == 0
    assert v.merge_conflict_rate == 0.0
    assert v.health_score == 0.0
    assert v.trend_direction == "stable"


def test_repository_velocity_field_count() -> None:
    assert len(fields(RepositoryVelocity)) == 10


def test_repository_health_defaults() -> None:
    h = RepositoryHealth()
    assert is_dataclass(h)
    assert h.repository_name == ""
    assert h.health_score == 0.0
    assert h.risk_level == "low"
    assert h.stale_branches == []
    assert h.unmerged_prs == 0
    assert h.large_files == []
    assert h.last_activity is None
    assert h.recommendations == []


def test_repository_health_list_fields_are_per_instance() -> None:
    h1 = RepositoryHealth()
    h2 = RepositoryHealth()
    h1.stale_branches.append("feature/foo")
    assert h2.stale_branches == []


def test_cross_project_pattern_defaults() -> None:
    p = CrossProjectPattern()
    assert is_dataclass(p)
    assert p.pattern_type == ""
    assert p.severity == "info"
    assert p.description == ""
    assert p.metric_value == 0.0
    assert p.affected_repositories == []
    assert p.recommendation == ""
    assert p.detected_at is not None


def test_portfolio_dashboard_defaults() -> None:
    d = PortfolioDashboard()
    assert is_dataclass(d)
    assert d.total_repositories == 0
    assert d.period_days == 0
    assert d.aggregate_metrics == {}
    assert d.repositories == []
    assert d.top_performers == []
    assert d.needs_attention == []
    assert d.cross_project_patterns == []
    assert d.generated_at is not None


def test_mahavishnu_aggregator_can_be_constructed() -> None:
    """The aggregator exposes a public constructor with default args."""
    agg = MahavishnuAggregator()
    assert agg is not None
    assert agg.config is not None


def test_mahavishnu_aggregator_accepts_config() -> None:
    config = MahavishnuConfig(websocket_port=12345)
    agg = MahavishnuAggregator(config=config)
    assert agg.config is config
    assert agg.config.websocket_port == 12345


def test_create_mahavishnu_aggregator_factory() -> None:
    """The factory builds a usable aggregator instance."""
    agg = create_mahavishnu_aggregator()
    assert isinstance(agg, MahavishnuAggregator)


def test_create_mahavishnu_aggregator_factory_with_config() -> None:
    """The factory passes through the config to the aggregator."""
    config = MahavishnuConfig(websocket_port=11111)
    agg = create_mahavishnu_aggregator(config=config)
    assert agg.config is config


@pytest.mark.asyncio
async def test_mahavishnu_aggregator_initialize_raises_not_implemented() -> None:
    """The shim's runtime bodies raise ``NotImplementedError``."""
    agg = MahavishnuAggregator()
    with pytest.raises(NotImplementedError):
        await agg.initialize()


@pytest.mark.asyncio
async def test_mahavishnu_aggregator_get_cross_project_git_dashboard_raises() -> None:
    agg = MahavishnuAggregator()
    with pytest.raises(NotImplementedError):
        await agg.get_cross_project_git_dashboard(
            project_paths=["/a", "/b"], days_back=7
        )
