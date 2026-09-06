"""Tests for ``crackerjack.services.workflow_optimization``.

Covers the ``WorkflowRecommendation`` / ``WorkflowInsights`` dataclasses plus
the ``WorkflowOptimizationEngine`` analysis pipeline that turns session
metrics into actionable recommendations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from crackerjack.models.session_metrics import SessionMetrics
from crackerjack.services.workflow_optimization import (
    WorkflowInsights,
    WorkflowOptimizationEngine,
    WorkflowRecommendation,
)


def _make_metrics(
    *,
    git_commit_velocity: float | None = 5.0,
    git_merge_success_rate: float | None = 0.95,
    conventional_commit_compliance: float | None = 0.85,
    test_pass_rate: float | None = 0.92,
    ai_fixes_applied: int | None = 3,
    quality_gate_passes: int | None = 4,
) -> SessionMetrics:
    return SessionMetrics(
        session_id="test-session",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(UTC),
        git_commit_velocity=git_commit_velocity,
        git_merge_success_rate=git_merge_success_rate,
        conventional_commit_compliance=conventional_commit_compliance,
        test_pass_rate=test_pass_rate,
        ai_fixes_applied=ai_fixes_applied,
        quality_gate_passes=quality_gate_passes,
    )


def test_workflow_recreation_frozen() -> None:
    """WorkflowRecommendation is frozen — assignments should fail."""
    rec = WorkflowRecommendation(
        priority="high",
        action="fix-flaky-tests",
        title="Fix flaky tests",
        description="Test X is flaky",
        expected_impact="Higher merge rate",
        effort="low",
    )
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        rec.priority = "low"  # type: ignore[misc]


def test_workflow_recreation_fields() -> None:
    rec = WorkflowRecommendation(
        priority="medium",
        action="upgrade-deps",
        title="Upgrade dependencies",
        description="Dependencies are out of date",
        expected_impact="Security improvements",
        effort="medium",
    )
    assert rec.priority == "medium"
    assert rec.action == "upgrade-deps"
    assert rec.title == "Upgrade dependencies"
    assert rec.description == "Dependencies are out of date"
    assert rec.expected_impact == "Security improvements"
    assert rec.effort == "medium"


def test_workflow_recreation_with_critical_priority() -> None:
    rec = WorkflowRecommendation(
        priority="critical",
        action="hotfix",
        title="Hotfix",
        description="d",
        expected_impact="e",
        effort="high",
    )
    assert rec.priority == "critical"


def test_workflow_insights_is_dataclass() -> None:
    from dataclasses import is_dataclass

    assert is_dataclass(WorkflowInsights)


def test_workflow_insights_fields() -> None:
    from dataclasses import fields

    field_names = {f.name for f in fields(WorkflowInsights)}
    assert {
        "velocity_analysis",
        "bottlenecks",
        "quality_correlations",
        "recommendations",
        "generated_at",
    } <= field_names


def test_engine_stores_session_metrics() -> None:
    metrics = _make_metrics()
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    assert engine.session_metrics is metrics


def test_engine_analyze_velocity_returns_empty_when_no_data() -> None:
    """When ``git_commit_velocity`` is None, the analysis returns ``{}``."""
    metrics = _make_metrics(git_commit_velocity=None)
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    assert engine.analyze_velocity_patterns() == {}


def test_engine_analyze_velocity_returns_metrics_when_data_present() -> None:
    metrics = _make_metrics(git_commit_velocity=5.0)
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    result = engine.analyze_velocity_patterns()
    assert "velocity_trend" in result
    assert "velocity_stability" in result
    assert "avg_commit_velocity" in result
    assert result["avg_commit_velocity"] == 5.0
    assert "velocity_score" in result


def test_engine_analyze_velocity_respects_days_back() -> None:
    """The ``days_back`` parameter is accepted and doesn't crash."""
    metrics = _make_metrics()
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    result = engine.analyze_velocity_patterns(days_back=90)
    assert isinstance(result, dict)


def test_engine_identify_bottlenecks_with_low_merge_rate() -> None:
    metrics = _make_metrics(git_merge_success_rate=0.5)
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={})
    assert any("merge" in b.lower() for b in bottlenecks)


def test_engine_identify_bottlenecks_with_high_merge_rate() -> None:
    metrics = _make_metrics(git_merge_success_rate=0.95)
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={})
    assert not any("merge" in b.lower() for b in bottlenecks)


def test_engine_identify_bottlenecks_handles_none_merge_rate() -> None:
    """``None`` merge rate should not produce a 'low merge' bottleneck."""
    metrics = _make_metrics(git_merge_success_rate=None)
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={})
    assert not any("merge success" in b.lower() for b in bottlenecks)


def test_engine_identify_bottlenecks_with_low_test_pass_rate() -> None:
    """test_pass_rate comes from quality_metrics, not session_metrics."""
    metrics = _make_metrics()
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={"test_pass_rate": 0.5})
    assert any("test" in b.lower() for b in bottlenecks)


def test_engine_identify_bottlenecks_with_low_conventional_compliance() -> None:
    metrics = _make_metrics(conventional_commit_compliance=0.3)
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={})
    assert any("conventional" in b.lower() for b in bottlenecks)


def test_engine_identify_bottlenecks_returns_list() -> None:
    metrics = _make_metrics()
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={})
    assert isinstance(bottlenecks, list)


def test_engine_quality_correlation_returns_dict() -> None:
    metrics = _make_metrics()
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    result = engine._calculate_quality_correlations(  # noqa: SLF001
        quality_metrics={}
    )
    assert isinstance(result, dict)


def test_engine_generate_insights_returns_workflow_insights() -> None:
    metrics = _make_metrics()
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    insights = engine.generate_insights()
    assert isinstance(insights, WorkflowInsights)
    assert isinstance(insights.recommendations, list)
    assert isinstance(insights.bottlenecks, list)
    assert isinstance(insights.velocity_analysis, dict)
    assert isinstance(insights.quality_correlations, dict)


def test_engine_generate_recommendations_returns_list() -> None:
    metrics = _make_metrics()
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    recs = engine.generate_recommendations(insights={"recommendations": []})
    assert isinstance(recs, list)


def test_engine_recommendations_have_required_fields() -> None:
    metrics = _make_metrics(
        git_merge_success_rate=0.5,
        test_pass_rate=0.5,
        conventional_commit_compliance=0.5,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    insights = engine.generate_insights()
    for rec in insights.recommendations:
        assert rec.priority in {"critical", "high", "medium", "low"}
        assert rec.action
        assert rec.title
        assert rec.description
        assert rec.effort in {"low", "medium", "high"}


def test_engine_velocity_score_calculation() -> None:
    """The private ``_calculate_velocity_score`` is exercised through analysis."""
    metrics = _make_metrics(git_commit_velocity=5.0)
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    score = engine._calculate_velocity_score(5.0)  # noqa: SLF001
    assert isinstance(score, float)


def test_engine_velocity_score_zero_when_no_data(tmp_path: Path) -> None:
    """When ``velocity`` is None, the score is 0.0."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_commit_velocity=None,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    score = engine._calculate_velocity_score(0.0)  # noqa: SLF001
    assert score == 0.0


def test_engine_velocity_trend_zero_when_no_data(tmp_path: Path) -> None:
    """When velocity is None, trend is 0.0."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_commit_velocity=None,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    trend = engine._calculate_velocity_trend(days_back=30)  # noqa: SLF001
    assert trend == 0.0


def test_engine_velocity_stability_zero_when_no_data(tmp_path: Path) -> None:
    """When ``git_workflow_efficiency_score`` is None, stability is 0.0."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_workflow_efficiency_score=None,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    stability = engine._calculate_velocity_stability()  # noqa: SLF001
    assert stability == 0.0


def test_engine_velocity_stability_calculation() -> None:
    """``_calculate_velocity_stability`` returns efficiency / 100 when present."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_workflow_efficiency_score=75.0,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    stability = engine._calculate_velocity_stability()  # noqa: SLF001
    assert stability == 0.75


def test_engine_velocity_trend_calculation() -> None:
    metrics = _make_metrics(git_commit_velocity=5.0)
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    trend = engine._calculate_velocity_trend(days_back=30)  # noqa: SLF001
    assert isinstance(trend, float)


def test_engine_identify_bottlenecks_low_efficiency(tmp_path: Path) -> None:
    """Low efficiency_score produces a workflow-efficiency bottleneck."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_workflow_efficiency_score=40.0,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={})
    assert any("efficiency" in b.lower() for b in bottlenecks)


def test_engine_identify_bottlenecks_low_velocity(tmp_path: Path) -> None:
    """Low commit velocity produces a velocity bottleneck."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_commit_velocity=0.5,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={})
    assert any("velocity" in b.lower() for b in bottlenecks)


def test_engine_identify_bottlenecks_high_ai_fixes(tmp_path: Path) -> None:
    """More than 10 AI fixes produces an AI-dependency bottleneck."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        ai_fixes_applied=15,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    bottlenecks = engine.identify_bottlenecks(quality_metrics={})
    assert any("ai" in b.lower() for b in bottlenecks)


def test_engine_recommendations_for_low_efficiency(tmp_path: Path) -> None:
    """Low efficiency produces at least one recommendation."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_workflow_efficiency_score=30.0,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    insights = engine.generate_insights()
    assert any(
        rec.priority == "critical" for rec in insights.recommendations
    )


def test_engine_recommendations_for_very_low_merge_rate(tmp_path: Path) -> None:
    """Merge rate below 0.5 produces a critical recommendation."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_merge_success_rate=0.4,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    insights = engine.generate_insights()
    assert any(
        rec.priority == "critical" for rec in insights.recommendations
    )


def test_engine_recommendations_for_moderate_efficiency(tmp_path: Path) -> None:
    """Moderate efficiency (40-60) produces a high-priority recommendation."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_workflow_efficiency_score=50.0,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    insights = engine.generate_insights()
    assert any(
        rec.priority == "high" for rec in insights.recommendations
    )


def test_engine_recommendations_for_good_efficiency(tmp_path: Path) -> None:
    """Good efficiency (60-80) produces a medium-priority recommendation."""
    from crackerjack.models.session_metrics import SessionMetrics

    metrics = SessionMetrics(
        session_id="s",
        project_path=Path("/tmp/x"),
        start_time=datetime.now(UTC),
        git_workflow_efficiency_score=70.0,
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    insights = engine.generate_insights()
    assert any(
        rec.priority == "medium" for rec in insights.recommendations
    )
