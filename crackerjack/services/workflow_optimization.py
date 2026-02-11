"""Workflow optimization engine for git metrics analysis.

This module provides comprehensive workflow analysis and recommendations based on
git metrics and session data. It identifies bottlenecks, analyzes velocity patterns,
and generates actionable recommendations for improving development workflow efficiency.

Classes:
    WorkflowRecommendation: Actionable improvement recommendation with metadata
    WorkflowInsights: Comprehensive analysis results with recommendations
    WorkflowOptimizationEngine: Analysis engine for git workflow optimization

Example:
    >>> from crackerjack.models.session_metrics import SessionMetrics
    >>> from crackerjack.services.workflow_optimization import WorkflowOptimizationEngine
    >>> engine = WorkflowOptimizationEngine(session_metrics)
    >>> insights = engine.generate_insights()
    >>> for rec in insights.recommendations:
    ...     print(f"[{rec.priority}] {rec.title}: {rec.action}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from crackerjack.models.session_metrics import SessionMetrics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowRecommendation:
    """Actionable workflow improvement recommendation.

    Attributes:
        priority: Urgency level (critical, high, medium, low)
        action: Specific action to take
        title: Brief summary of the recommendation
        description: Detailed explanation of the issue and solution
        expected_impact: What improvement to expect from implementation
        effort: Implementation effort required (low, medium, high)
    """

    priority: Literal["critical", "high", "medium", "low"]
    action: str
    title: str
    description: str
    expected_impact: str
    effort: Literal["low", "medium", "high"]


@dataclass(frozen=True)
class WorkflowInsights:
    """Comprehensive workflow analysis results.

    Attributes:
        velocity_analysis: Velocity trends and metrics
        bottlenecks: List of identified workflow issues
        quality_correlations: Relationships between metrics
        recommendations: Actionable improvement recommendations
        generated_at: Timestamp when insights were generated
    """

    velocity_analysis: dict[str, float]
    bottlenecks: list[str]
    quality_correlations: dict[str, float]
    recommendations: list[WorkflowRecommendation]
    generated_at: datetime


class WorkflowOptimizationEngine:
    """Git workflow optimization and analysis engine.

    Analyzes session metrics to identify workflow bottlenecks, velocity patterns,
    and generate actionable recommendations for improving development efficiency.

    Attributes:
        session_metrics: Session data with git and quality metrics

    Example:
        >>> engine = WorkflowOptimizationEngine(session_metrics)
        >>> velocity = engine.analyze_velocity_patterns(days_back=30)
        >>> bottlenecks = engine.identify_bottlenecks(quality_metrics)
        >>> insights = engine.generate_insights()
    """

    def __init__(self, session_metrics: SessionMetrics) -> None:
        """Initialize the optimization engine with session data.

        Args:
            session_metrics: Session metrics containing git and quality data
        """
        self.session_metrics = session_metrics

    def analyze_velocity_patterns(self, days_back: int = 30) -> dict[str, float]:
        """Analyze git velocity trends over time.

        Calculates velocity metrics including commit rate, stability indicators,
        and trend analysis to identify patterns in development workflow speed.

        Args:
            days_back: Number of days to look back for analysis (default: 30)

        Returns:
            Dictionary with velocity metrics including:
            - velocity_trend: Positive/negative velocity change (-1.0 to 1.0)
            - velocity_stability: Consistency of velocity (0.0 to 1.0)
            - avg_commit_velocity: Average commits per hour
            - velocity_score: Composite velocity score (0-100)

        Note:
            Returns empty dict if required metrics are unavailable.
        """
        if self.session_metrics.git_commit_velocity is None:
            logger.warning("Cannot analyze velocity: git_commit_velocity is None")
            return {}

        velocity = self.session_metrics.git_commit_velocity

        # Calculate velocity metrics
        velocity_score = self._calculate_velocity_score(velocity)
        velocity_stability = self._calculate_velocity_stability()
        velocity_trend = self._calculate_velocity_trend(days_back)

        return {
            "velocity_trend": velocity_trend,
            "velocity_stability": velocity_stability,
            "avg_commit_velocity": velocity,
            "velocity_score": velocity_score,
        }

    def identify_bottlenecks(self, quality_metrics: dict[str, float]) -> list[str]:
        """Detect workflow bottlenecks from git and quality metrics.

        Analyzes metrics to identify specific issues slowing down the workflow,
        such as low merge success rates, declining velocity, or poor compliance.

        Args:
            quality_metrics: Dictionary of quality gate metrics

        Returns:
            Prioritized list of bottleneck descriptions. Empty if no metrics available.

        Example:
            >>> bottlenecks = engine.identify_bottlenecks({"test_pass_rate": 0.75})
            >>> print(bottlenecks)
            ['Low merge success rate (<70%)', 'Poor test pass rate (75%)']
        """
        bottlenecks: list[str] = []

        # Check merge efficiency
        merge_rate = self.session_metrics.git_merge_success_rate
        if merge_rate is not None and merge_rate < 0.7:
            bottlenecks.append(f"Low merge success rate ({merge_rate:.1%})")

        # Check workflow efficiency
        efficiency = self.session_metrics.git_workflow_efficiency_score
        if efficiency is not None and efficiency < 60:
            bottlenecks.append(f"Poor workflow efficiency score ({efficiency:.0f}/100)")

        # Check conventional compliance
        compliance = self.session_metrics.conventional_commit_compliance
        if compliance is not None and compliance < 0.7:
            bottlenecks.append(
                f"Poor conventional commit compliance ({compliance:.1%})"
            )

        # Check velocity trends
        if self.session_metrics.git_commit_velocity is not None:
            velocity = self.session_metrics.git_commit_velocity
            if velocity < 1.0:
                bottlenecks.append(f"Low commit velocity ({velocity:.1f} commits/hour)")

        # Check quality metrics
        if quality_metrics.get("test_pass_rate", 1.0) < 0.8:
            pass_rate = quality_metrics["test_pass_rate"]
            bottlenecks.append(f"Poor test pass rate ({pass_rate:.1%})")

        # Check AI fix dependency
        if self.session_metrics.ai_fixes_applied is not None:
            if self.session_metrics.ai_fixes_applied > 10:
                bottlenecks.append(
                    f"High AI fix dependency ({self.session_metrics.ai_fixes_applied} fixes)"
                )

        return sorted(bottlenecks, key=len, reverse=True)

    def generate_recommendations(
        self,
        insights: dict[str, object],
    ) -> list[WorkflowRecommendation]:
        """Generate actionable recommendations based on analysis insights.

        Creates prioritized recommendations with specific actions, expected impact,
        and effort estimates for improving workflow efficiency.

        Args:
            insights: Dictionary containing velocity_analysis, bottlenecks, and quality_correlations

        Returns:
            List of recommendations sorted by priority (critical -> low)

        Example:
            >>> insights = {"velocity_analysis": {}, "bottlenecks": [], "quality_correlations": {}}
            >>> recs = engine.generate_recommendations(insights)
            >>> for rec in recs:
            ...     print(f"{rec.priority}: {rec.title}")
        """
        recommendations: list[WorkflowRecommendation] = []

        efficiency = self.session_metrics.git_workflow_efficiency_score
        merge_rate = self.session_metrics.git_merge_success_rate
        compliance = self.session_metrics.conventional_commit_compliance
        velocity = self.session_metrics.git_commit_velocity

        # Critical priority recommendations
        if efficiency is not None and efficiency < 40:
            recommendations.append(
                WorkflowRecommendation(
                    priority="critical",
                    action="Review and restructure git workflow processes",
                    title="Critical workflow efficiency issues detected",
                    description=(
                        f"Workflow efficiency score is {efficiency:.0f}/100, "
                        "indicating severe bottlenecks in the development process. "
                        "Immediate intervention required to unblock the team."
                    ),
                    expected_impact="20-30% improvement in overall workflow speed",
                    effort="high",
                )
            )

        if merge_rate is not None and merge_rate < 0.5:
            recommendations.append(
                WorkflowRecommendation(
                    priority="critical",
                    action="Automate merge conflict resolution and improve branch hygiene",
                    title="Critically low merge success rate",
                    description=(
                        f"Merge success rate is {merge_rate:.1%}, meaning more than half "
                        "of merge attempts are failing. This indicates severe integration "
                        "issues or branch management problems."
                    ),
                    expected_impact="30-40% reduction in merge failures",
                    effort="high",
                )
            )

        # High priority recommendations
        if efficiency is not None and 40 <= efficiency < 60:
            recommendations.append(
                WorkflowRecommendation(
                    priority="high",
                    action="Implement branch lifecycle policies and reduce long-lived branches",
                    title="Suboptimal workflow efficiency",
                    description=(
                        f"Workflow efficiency is {efficiency:.0f}/100. Focus on reducing "
                        "branch lifespan and improving integration frequency to boost efficiency."
                    ),
                    expected_impact="10-20% improvement in workflow speed",
                    effort="medium",
                )
            )

        if merge_rate is not None and 0.5 <= merge_rate < 0.7:
            recommendations.append(
                WorkflowRecommendation(
                    priority="high",
                    action="Implement pre-merge validation checks",
                    title="Merge success rate below 70%",
                    description=(
                        f"Merge success rate is {merge_rate:.1%}. Automated pre-merge checks "
                        "can catch issues before merge attempts."
                    ),
                    expected_impact="15-25% improvement in merge success",
                    effort="medium",
                )
            )

        # Medium priority recommendations
        if compliance is not None and compliance < 0.7:
            recommendations.append(
                WorkflowRecommendation(
                    priority="medium",
                    action="Adopt conventional commit format with commitlint",
                    title="Improve commit message structure",
                    description=(
                        f"Conventional commit compliance is {compliance:.1%}. "
                        "Standardized commit messages improve changelog generation "
                        "and semantic versioning."
                    ),
                    expected_impact="Better release automation and documentation",
                    effort="low",
                )
            )

        if efficiency is not None and 60 <= efficiency < 80:
            recommendations.append(
                WorkflowRecommendation(
                    priority="medium",
                    action="Optimize CI/CD pipeline and reduce feedback delay",
                    title="Further workflow optimization opportunities",
                    description=(
                        f"Workflow efficiency is {efficiency:.0f}/100. Optimizing "
                        "CI/CD pipelines and reducing feedback loops can improve velocity."
                    ),
                    expected_impact="5-10% improvement in workflow speed",
                    effort="medium",
                )
            )

        # Low priority recommendations (general improvements)
        if velocity is not None and velocity >= 2.0:
            recommendations.append(
                WorkflowRecommendation(
                    priority="low",
                    action="Review code review process for optimization",
                    title="High velocity with potential review bottlenecks",
                    description=(
                        f"Commit velocity is {velocity:.1f} commits/hour, which is good. "
                        "Ensure code review process can keep up with this pace."
                    ),
                    expected_impact="Sustain high velocity without burnout",
                    effort="low",
                )
            )

        # Add recommendations based on bottlenecks
        bottlenecks = insights.get("bottlenecks", [])
        if isinstance(bottlenecks, list):
            if any("conventional" in b.lower() for b in bottlenecks):
                recommendations.append(
                    WorkflowRecommendation(
                        priority="medium",
                        action="Set up commit message hooks for conventional compliance",
                        title="Enforce conventional commit standards",
                        description=(
                            "Automated enforcement ensures consistency and improves "
                            "changelog generation and semantic versioning."
                        ),
                        expected_impact="90%+ conventional commit compliance",
                        effort="low",
                    )
                )

        return sorted(
            recommendations,
            key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}[r.priority],
        )

    def generate_insights(self) -> WorkflowInsights:
        """Generate comprehensive workflow optimization insights.

        Combines velocity analysis, bottleneck identification, and recommendations
        into a single comprehensive insight report.

        Returns:
            WorkflowInsights with complete analysis and recommendations

        Example:
            >>> insights = engine.generate_insights()
            >>> print(f"Found {len(insights.bottlenecks)} bottlenecks")
            >>> print(f"Generated {len(insights.recommendations)} recommendations")
        """
        velocity_analysis = self.analyze_velocity_patterns()

        quality_metrics: dict[str, float] = {}
        if self.session_metrics.test_pass_rate is not None:
            quality_metrics["test_pass_rate"] = self.session_metrics.test_pass_rate

        bottlenecks = self.identify_bottlenecks(quality_metrics)
        quality_correlations = self._calculate_quality_correlations(quality_metrics)

        insights_data = {
            "velocity_analysis": velocity_analysis,
            "bottlenecks": bottlenecks,
            "quality_correlations": quality_correlations,
        }

        recommendations = self.generate_recommendations(insights_data)

        return WorkflowInsights(
            velocity_analysis=velocity_analysis,
            bottlenecks=bottlenecks,
            quality_correlations=quality_correlations,
            recommendations=recommendations,
            generated_at=datetime.now(),
        )

    def _calculate_velocity_score(self, velocity: float) -> float:
        """Calculate composite velocity score from commit velocity.

        Args:
            velocity: Commits per hour

        Returns:
            Score between 0-100
        """
        # Scale: 0 commits/hour = 0, 5+ commits/hour = 100
        score = min(velocity / 5.0 * 100, 100)
        return round(score, 2)

    def _calculate_velocity_stability(self) -> float:
        """Calculate velocity stability indicator.

        Stability is based on the consistency of workflow efficiency.

        Returns:
            Stability score between 0.0 (unstable) and 1.0 (stable)
        """
        efficiency = self.session_metrics.git_workflow_efficiency_score

        if efficiency is None:
            return 0.0

        # High efficiency correlates with high stability
        return round(efficiency / 100, 2)

    def _calculate_velocity_trend(self, days_back: int) -> float:
        """Calculate velocity trend over time period.

        Args:
            days_back: Days to analyze for trend

        Returns:
            Trend between -1.0 (declining) and 1.0 (growing)
        """
        # Single session analysis: trend based on current velocity vs threshold
        velocity = self.session_metrics.git_commit_velocity

        if velocity is None:
            return 0.0

        # Compare to baseline of 2 commits/hour
        baseline = 2.0
        diff = velocity - baseline
        trend = max(min(diff / baseline, 1.0), -1.0)

        return round(trend, 2)

    def _calculate_quality_correlations(
        self,
        quality_metrics: dict[str, float],
    ) -> dict[str, float]:
        """Calculate correlations between quality and git metrics.

        Args:
            quality_metrics: Dictionary of quality gate results

        Returns:
            Dictionary of correlation coefficients
        """
        correlations: dict[str, float] = {}

        # Test pass rate correlation with workflow efficiency
        if (
            self.session_metrics.test_pass_rate is not None
            and self.session_metrics.git_workflow_efficiency_score is not None
        ):
            pass_rate = self.session_metrics.test_pass_rate
            efficiency = self.session_metrics.git_workflow_efficiency_score

            # Simple correlation: high pass rate should correlate with high efficiency
            correlation = round((pass_rate + (efficiency / 100)) / 2, 2)
            correlations["test_efficiency_correlation"] = correlation

        # AI fix usage correlation
        if (
            self.session_metrics.ai_fixes_applied is not None
            and self.session_metrics.test_pass_rate is not None
        ):
            # High AI fixes with low pass rate indicates chronic issues
            if self.session_metrics.ai_fixes_applied > 5:
                correlations["ai_fix_dependency"] = round(
                    self.session_metrics.ai_fixes_applied / 10.0, 2
                )

        return correlations


__all__ = [
    "WorkflowRecommendation",
    "WorkflowInsights",
    "WorkflowOptimizationEngine",
]
