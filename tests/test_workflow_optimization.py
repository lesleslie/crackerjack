"""Test suite for WorkflowOptimizationEngine.

Tests the analysis of git workflow patterns, bottleneck identification,
and recommendation generation for workflow improvement.
"""

from datetime import datetime

import pytest

from crackerjack.models.session_metrics import SessionMetrics
from crackerjack.services.workflow_optimization import (
    WorkflowInsights,
    WorkflowOptimizationEngine,
    WorkflowRecommendation,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def metrics_critical_issues():
    """Fixture with critical git metrics (low efficiency, poor merge rate)."""
    return SessionMetrics(
        session_id="critical-issues",
        project_path="/tmp/critical_test",
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        git_commit_velocity=0.5,  # Low velocity
        git_branch_count=15,  # Many branches
        git_merge_success_rate=0.35,  # Very poor merge rate
        conventional_commit_compliance=0.40,  # Poor compliance
        git_workflow_efficiency_score=35.0,  # Critical efficiency
    )


@pytest.fixture
def metrics_high_issues():
    """Fixture with high-priority issues."""
    return SessionMetrics(
        session_id="high-issues",
        project_path="/tmp/high_test",
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        git_commit_velocity=1.5,
        git_branch_count=12,
        git_merge_success_rate=0.60,  # Below 0.7 threshold
        conventional_commit_compliance=0.65,
        git_workflow_efficiency_score=55.0,  # High priority range
    )


@pytest.fixture
def metrics_medium_issues():
    """Fixture with medium-priority issues."""
    return SessionMetrics(
        session_id="medium-issues",
        project_path="/tmp/medium_test",
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        git_commit_velocity=2.5,
        git_branch_count=8,
        git_merge_success_rate=0.75,
        conventional_commit_compliance=0.60,  # Below 0.7
        git_workflow_efficiency_score=70.0,  # Medium range
    )


@pytest.fixture
def metrics_healthy():
    """Fixture with good git metrics."""
    return SessionMetrics(
        session_id="healthy",
        project_path="/tmp/healthy_test",
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        git_commit_velocity=4.5,
        git_branch_count=5,
        git_merge_success_rate=0.92,
        conventional_commit_compliance=0.88,
        git_workflow_efficiency_score=85.0,
    )


@pytest.fixture
def metrics_with_quality_data():
    """Fixture with quality metrics for correlation testing."""
    return SessionMetrics(
        session_id="quality-data",
        project_path="/tmp/quality_test",
        start_time=datetime(2025, 2, 11, 10, 0, 0),
        git_commit_velocity=3.0,
        git_merge_success_rate=0.75,
        conventional_commit_compliance=0.70,
        git_workflow_efficiency_score=72.0,
        test_pass_rate=0.65,  # Poor test pass rate
        tests_run=100,
        tests_passed=65,
        ai_fixes_applied=15,  # High AI fix dependency
    )


@pytest.fixture
def sample_insights():
    """Fixture with WorkflowInsights for testing."""
    return WorkflowInsights(
        velocity_analysis={
            "velocity_trend": 0.25,
            "velocity_stability": 0.72,
            "avg_commit_velocity": 2.5,
            "velocity_score": 50.0,
        },
        bottlenecks=[
            "Low merge success rate (60.0%)",
            "Poor conventional commit compliance (65.0%)",
        ],
        quality_correlations={
            "test_efficiency_correlation": 0.71,
            "ai_fix_dependency": 1.5,
        },
        recommendations=[
            WorkflowRecommendation(
                priority="high",
                action="Improve commit message structure",
                title="Improve commit message structure",
                description="Conventional commit compliance is 65.0%",
                expected_impact="Better release automation",
                effort="low",
            )
        ],
        generated_at=datetime(2025, 2, 11, 10, 0, 0),
    )


# ============================================================================
# Initialization Tests
# ============================================================================


def test_engine_initialization(metrics_healthy):
    """Test that WorkflowOptimizationEngine initializes correctly."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_healthy)
    assert engine.session_metrics == metrics_healthy


# ============================================================================
# Velocity Pattern Analysis Tests
# ============================================================================


def test_analyze_velocity_patterns_normal(metrics_healthy):
    """Test velocity pattern analysis with normal velocity."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_healthy)
    patterns = engine.analyze_velocity_patterns()

    assert "velocity_trend" in patterns
    assert "velocity_stability" in patterns
    assert "avg_commit_velocity" in patterns
    assert "velocity_score" in patterns
    assert patterns["avg_commit_velocity"] == 4.5


def test_analyze_velocity_patterns_no_velocity():
    """Test velocity pattern analysis when velocity is None."""
    metrics = SessionMetrics(
        session_id="no-velocity",
        project_path="/tmp/test",
        start_time=datetime.now(),
    )
    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    patterns = engine.analyze_velocity_patterns()

    assert patterns == {}


def test_calculate_velocity_score():
    """Test velocity score calculation."""
    engine = WorkflowOptimizationEngine(
        session_metrics=SessionMetrics(
            session_id="score-test", project_path="/tmp/test", start_time=datetime.now()
        )
    )

    # Low velocity
    assert engine._calculate_velocity_score(1.0) == 20.0

    # Medium velocity
    assert engine._calculate_velocity_score(2.5) == 50.0

    # High velocity (caps at 100)
    assert engine._calculate_velocity_score(10.0) == 100.0
    assert engine._calculate_velocity_score(20.0) == 100.0


def test_calculate_velocity_stability(metrics_healthy):
    """Test velocity stability calculation."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_healthy)
    stability = engine._calculate_velocity_stability()

    # Stability is efficiency_score / 100
    assert stability == pytest.approx(0.85, rel=1e-3)


def test_calculate_velocity_trend():
    """Test velocity trend calculation."""
    engine = WorkflowOptimizationEngine(
        session_metrics=SessionMetrics(
            session_id="trend-test",
            project_path="/tmp/test",
            start_time=datetime.now(),
            git_commit_velocity=3.0,  # 50% above baseline of 2.0
        )
    )

    trend = engine._calculate_velocity_trend(30)
    assert trend == pytest.approx(0.5, rel=1e-3)


def test_calculate_velocity_trend_caps_at_limits():
    """Test that velocity trend caps at -1.0 and 1.0."""
    engine = WorkflowOptimizationEngine(
        session_metrics=SessionMetrics(
            session_id="trend-caps",
            project_path="/tmp/test",
            start_time=datetime.now(),
            git_commit_velocity=100.0,  # Way above baseline
        )
    )

    trend = engine._calculate_velocity_trend(30)
    assert trend == 1.0

    engine2 = WorkflowOptimizationEngine(
        session_metrics=SessionMetrics(
            session_id="trend-caps-low",
            project_path="/tmp/test",
            start_time=datetime.now(),
            git_commit_velocity=0.0,  # Way below baseline
        )
    )

    trend2 = engine2._calculate_velocity_trend(30)
    assert trend2 == -1.0


# ============================================================================
# Bottleneck Identification Tests
# ============================================================================


def test_identify_bottlenecks_critical(metrics_critical_issues):
    """Test bottleneck detection for CRITICAL issues."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_critical_issues)
    bottlenecks = engine.identify_bottlenecks({})

    assert len(bottlenecks) >= 4
    assert any("merge success rate" in b.lower() for b in bottlenecks)
    assert any("workflow efficiency" in b.lower() for b in bottlenecks)
    assert any("conventional commit compliance" in b.lower() for b in bottlenecks)
    assert any("commit velocity" in b.lower() for b in bottlenecks)


def test_identify_bottlenecks_high(metrics_high_issues):
    """Test bottleneck detection for HIGH issues."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_high_issues)
    bottlenecks = engine.identify_bottlenecks({})

    assert len(bottlenecks) >= 2
    assert any("merge success rate" in b.lower() for b in bottlenecks)
    assert any("workflow efficiency" in b.lower() for b in bottlenecks)


def test_identify_bottlenecks_medium(metrics_medium_issues):
    """Test bottleneck detection for MEDIUM issues."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_medium_issues)
    bottlenecks = engine.identify_bottlenecks({})

    # Should detect poor conventional compliance
    assert any("conventional commit compliance" in b.lower() for b in bottlenecks)


def test_identify_bottlenecks_low(metrics_healthy):
    """Test bottleneck detection returns LOW/empty for good metrics."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_healthy)
    bottlenecks = engine.identify_bottlenecks({})

    # Should have minimal or no bottlenecks
    assert len(bottlenecks) == 0


def test_identify_bottlenecks_with_quality_issues(metrics_with_quality_data):
    """Test bottleneck detection including quality metrics."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_with_quality_data)
    bottlenecks = engine.identify_bottlenecks(
        {"test_pass_rate": 0.65}  # Poor test pass rate
    )

    assert any("test pass rate" in b.lower() for b in bottlenecks)
    assert any("AI fix" in b.lower() or "ai fix" in b.lower() for b in bottlenecks)


def test_identify_bottlenecks_sorted_by_length(metrics_critical_issues):
    """Test that bottlenecks are sorted by length (longest first)."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_critical_issues)
    bottlenecks = engine.identify_bottlenecks({})

    # Check that list is sorted in descending order of length
    for i in range(len(bottlenecks) - 1):
        assert len(bottlenecks[i]) >= len(bottlenecks[i + 1])


# ============================================================================
# Recommendation Generation Tests
# ============================================================================


def test_generate_recommendations_critical_efficiency(metrics_critical_issues):
    """Test recommendation generation for critical efficiency."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_critical_issues)
    insights_data = {"bottlenecks": engine.identify_bottlenecks({})}
    recommendations = engine.generate_recommendations(insights_data)

    # Should have critical recommendation for efficiency
    critical_recs = [r for r in recommendations if r.priority == "critical"]
    assert len(critical_recs) >= 1
    assert any(
        "workflow efficiency" in r.title.lower() for r in critical_recs
    )


def test_generate_recommendations_critical_merge_rate(metrics_critical_issues):
    """Test recommendation generation for critical merge rate."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_critical_issues)
    insights_data = {"bottlenecks": []}
    recommendations = engine.generate_recommendations(insights_data)

    # Should have critical recommendation for merge rate
    critical_recs = [r for r in recommendations if r.priority == "critical"]
    assert any(
        "merge" in r.title.lower() or "merge" in r.description.lower()
        for r in critical_recs
    )


def test_generate_recommendations_high_priority(metrics_high_issues):
    """Test recommendation generation for high-priority issues."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_high_issues)
    insights_data = {"bottlenecks": []}
    recommendations = engine.generate_recommendations(insights_data)

    # Should have high priority recommendations
    high_recs = [r for r in recommendations if r.priority == "high"]
    assert len(high_recs) >= 1


def test_generate_recommendations_medium_priority(metrics_medium_issues):
    """Test recommendation generation for medium-priority issues."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_medium_issues)
    insights_data = {"bottlenecks": []}
    recommendations = engine.generate_recommendations(insights_data)

    # Should have medium priority recommendations
    medium_recs = [r for r in recommendations if r.priority == "medium"]
    assert len(medium_recs) >= 1


def test_generate_recommendations_low_priority(metrics_healthy):
    """Test recommendation generation for healthy metrics."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_healthy)
    insights_data = {"bottlenecks": []}
    recommendations = engine.generate_recommendations(insights_data)

    # Should have low priority or no recommendations
    assert all(isinstance(r, WorkflowRecommendation) for r in recommendations)


def test_recommendation_priority_assignment():
    """Test that recommendations are correctly prioritized."""
    metrics = SessionMetrics(
        session_id="priority-test",
        project_path="/tmp/test",
        start_time=datetime.now(),
        git_commit_velocity=3.0,
        git_workflow_efficiency_score=50.0,  # High
        git_merge_success_rate=0.6,  # High
        conventional_commit_compliance=0.6,  # Medium
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    recommendations = engine.generate_recommendations({"bottlenecks": []})

    # Check sorting: critical should come before high before medium before low
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    for i in range(len(recommendations) - 1):
        current_priority = priority_order[recommendations[i].priority]
        next_priority = priority_order[recommendations[i + 1].priority]
        assert current_priority <= next_priority


def test_recommendation_types():
    """Test that expected recommendation types are generated."""
    metrics = SessionMetrics(
        session_id="types-test",
        project_path="/tmp/test",
        start_time=datetime.now(),
        git_commit_velocity=2.0,
        git_merge_success_rate=0.6,
        conventional_commit_compliance=0.5,
        git_workflow_efficiency_score=45.0,
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    insights_data = {
        "bottlenecks": ["Poor conventional commit compliance (50.0%)"]
    }
    recommendations = engine.generate_recommendations(insights_data)

    # Should include conventional commits recommendation
    assert any(
        "conventional" in r.action.lower() or "commit" in r.action.lower()
        for r in recommendations
    )


# ============================================================================
# Insights Generation Tests
# ============================================================================


def test_generate_insights_comprehensive(metrics_high_issues):
    """Test complete insights generation."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_high_issues)
    insights = engine.generate_insights()

    assert isinstance(insights, WorkflowInsights)
    # velocity_analysis IS a dict, not contains it
    assert isinstance(insights.velocity_analysis, dict)
    assert "velocity_trend" in insights.velocity_analysis
    assert "velocity_stability" in insights.velocity_analysis
    assert "avg_commit_velocity" in insights.velocity_analysis
    assert "velocity_score" in insights.velocity_analysis
    assert isinstance(insights.bottlenecks, list)
    assert isinstance(insights.quality_correlations, dict)
    assert isinstance(insights.recommendations, list)
    assert isinstance(insights.generated_at, datetime)


def test_generate_insights_velocity_analysis(metrics_healthy):
    """Test that insights include velocity analysis."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_healthy)
    insights = engine.generate_insights()

    assert "velocity_trend" in insights.velocity_analysis
    assert "velocity_stability" in insights.velocity_analysis
    assert "avg_commit_velocity" in insights.velocity_analysis
    assert "velocity_score" in insights.velocity_analysis


def test_generate_insights_bottlenecks(metrics_critical_issues):
    """Test that insights include detected bottlenecks."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_critical_issues)
    insights = engine.generate_insights()

    assert len(insights.bottlenecks) > 0
    assert isinstance(insights.bottlenecks, list)


def test_generate_insights_recommendations(metrics_high_issues):
    """Test that insights include recommendations."""
    engine = WorkflowOptimizationEngine(session_metrics=metrics_high_issues)
    insights = engine.generate_insights()

    assert len(insights.recommendations) > 0
    assert all(isinstance(r, WorkflowRecommendation) for r in insights.recommendations)


# ============================================================================
# Quality Correlation Tests
# ============================================================================


def test_calculate_quality_correlations_with_test_data():
    """Test quality correlation calculation with test data."""
    metrics = SessionMetrics(
        session_id="correlation-test",
        project_path="/tmp/test",
        start_time=datetime.now(),
        git_workflow_efficiency_score=70.0,
        test_pass_rate=0.85,
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    correlations = engine._calculate_quality_correlations({"test_pass_rate": 0.85})

    assert "test_efficiency_correlation" in correlations
    # Correlation is calculated as: (pass_rate + (efficiency/100)) / 2
    # Then rounded to 2 decimal places
    # (0.85 + 0.70) / 2 = 0.775 -> round(0.775, 2) = 0.78
    expected = round((0.85 + (70.0 / 100)) / 2, 2)
    assert correlations["test_efficiency_correlation"] == expected


def test_calculate_quality_correlations_with_ai_fixes():
    """Test quality correlation with AI fix dependency."""
    metrics = SessionMetrics(
        session_id="ai-fix-test",
        project_path="/tmp/test",
        start_time=datetime.now(),
        test_pass_rate=0.80,
        ai_fixes_applied=12,  # Above threshold of 5
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    correlations = engine._calculate_quality_correlations({"test_pass_rate": 0.80})

    assert "ai_fix_dependency" in correlations
    assert correlations["ai_fix_dependency"] == 1.2


def test_calculate_quality_correlations_no_ai_fix_threshold():
    """Test that AI fix dependency only calculated above threshold."""
    metrics = SessionMetrics(
        session_id="low-ai-test",
        project_path="/tmp/test",
        start_time=datetime.now(),
        test_pass_rate=0.90,
        ai_fixes_applied=3,  # Below threshold of 5
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    correlations = engine._calculate_quality_correlations({"test_pass_rate": 0.90})

    assert "ai_fix_dependency" not in correlations


def test_calculate_quality_correlations_empty():
    """Test quality correlation with no data."""
    metrics = SessionMetrics(
        session_id="empty-correlation",
        project_path="/tmp/test",
        start_time=datetime.now(),
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    correlations = engine._calculate_quality_correlations({})

    assert correlations == {}


# ============================================================================
# Edge Cases and Graceful Handling
# ============================================================================


def test_missing_metrics_graceful():
    """Test that missing metrics are handled gracefully."""
    metrics = SessionMetrics(
        session_id="missing-metrics",
        project_path="/tmp/test",
        start_time=datetime.now(),
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)

    # Should not raise errors
    velocity = engine.analyze_velocity_patterns()
    bottlenecks = engine.identify_bottlenecks({})
    insights = engine.generate_insights()

    assert velocity == {}
    assert bottlenecks == []
    assert isinstance(insights, WorkflowInsights)


def test_none_velocity_in_analyze():
    """Test analyze_velocity_patterns with None velocity."""
    metrics = SessionMetrics(
        session_id="none-velocity",
        project_path="/tmp/test",
        start_time=datetime.now(),
        git_commit_velocity=None,
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    patterns = engine.analyze_velocity_patterns()

    assert patterns == {}


def test_velocity_stability_with_none_efficiency():
    """Test velocity stability calculation with None efficiency."""
    metrics = SessionMetrics(
        session_id="none-efficiency",
        project_path="/tmp/test",
        start_time=datetime.now(),
        git_commit_velocity=3.0,
        git_workflow_efficiency_score=None,
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    stability = engine._calculate_velocity_stability()

    assert stability == 0.0


def test_velocity_trend_with_none_velocity():
    """Test velocity trend calculation with None velocity."""
    metrics = SessionMetrics(
        session_id="none-velocity-trend",
        project_path="/tmp/test",
        start_time=datetime.now(),
        git_commit_velocity=None,
    )

    engine = WorkflowOptimizationEngine(session_metrics=metrics)
    trend = engine._calculate_velocity_trend(30)

    assert trend == 0.0
