from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from crackerjack.models.session_metrics import SessionMetrics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowRecommendation:
    priority: Literal["critical", "high", "medium", "low"]
    action: str
    title: str
    description: str
    expected_impact: str
    effort: Literal["low", "medium", "high"]


@dataclass(frozen=True)
class WorkflowInsights:
    velocity_analysis: dict[str, float]
    bottlenecks: list[str]
    quality_correlations: dict[str, float]
    recommendations: list[WorkflowRecommendation]
    generated_at: datetime


class WorkflowOptimizationEngine:
    def __init__(self, session_metrics: SessionMetrics) -> None:
        self.session_metrics = session_metrics

    def analyze_velocity_patterns(self, days_back: int = 30) -> dict[str, float]:
        if self.session_metrics.git_commit_velocity is None:
            logger.warning("Cannot analyze velocity: git_commit_velocity is None")
            return {}

        velocity = self.session_metrics.git_commit_velocity

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
        bottlenecks: list[str] = []

        merge_rate = self.session_metrics.git_merge_success_rate
        if merge_rate is not None and merge_rate < 0.7:
            bottlenecks.append(f"Low merge success rate ({merge_rate:.1%})")

        efficiency = self.session_metrics.git_workflow_efficiency_score
        if efficiency is not None and efficiency < 60:
            bottlenecks.append(f"Poor workflow efficiency score ({efficiency:.0f}/100)")

        compliance = self.session_metrics.conventional_commit_compliance
        if compliance is not None and compliance < 0.7:
            bottlenecks.append(
                f"Poor conventional commit compliance ({compliance:.1%})"
            )

        if self.session_metrics.git_commit_velocity is not None:
            velocity = self.session_metrics.git_commit_velocity
            if velocity < 1.0:
                bottlenecks.append(f"Low commit velocity ({velocity:.1f} commits/hour)")

        if quality_metrics.get("test_pass_rate", 1.0) < 0.8:
            pass_rate = quality_metrics["test_pass_rate"]
            bottlenecks.append(f"Poor test pass rate ({pass_rate:.1%})")

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
        recommendations: list[WorkflowRecommendation] = []

        efficiency = self.session_metrics.git_workflow_efficiency_score
        merge_rate = self.session_metrics.git_merge_success_rate
        compliance = self.session_metrics.conventional_commit_compliance
        velocity = self.session_metrics.git_commit_velocity

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
                        f"Workflow efficiency is {efficiency:.0f}/100. "
                        "Optimizing CI/CD pipelines and reducing feedback loops "
                        "can improve velocity."
                    ),
                    expected_impact="5-10% improvement in workflow speed",
                    effort="medium",
                )
            )

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

        recommendations = self.generate_recommendations(insights_data)  # type: ignore[untyped]

        return WorkflowInsights(
            velocity_analysis=velocity_analysis,
            bottlenecks=bottlenecks,
            quality_correlations=quality_correlations,
            recommendations=recommendations,
            generated_at=datetime.now(),
        )

    def _calculate_velocity_score(self, velocity: float) -> float:

        score = min(velocity / 5.0 * 100, 100)
        return round(score, 2)

    def _calculate_velocity_stability(self) -> float:
        efficiency = self.session_metrics.git_workflow_efficiency_score

        if efficiency is None:
            return 0.0

        return round(efficiency / 100, 2)

    def _calculate_velocity_trend(self, days_back: int) -> float:

        velocity = self.session_metrics.git_commit_velocity

        if velocity is None:
            return 0.0

        baseline = 2.0
        diff = velocity - baseline
        trend = max(min(diff / baseline, 1.0), -1.0)

        return round(trend, 2)

    def _calculate_quality_correlations(
        self,
        quality_metrics: dict[str, float],
    ) -> dict[str, float]:
        correlations: dict[str, float] = {}

        if (
            self.session_metrics.test_pass_rate is not None
            and self.session_metrics.git_workflow_efficiency_score is not None
        ):
            pass_rate = self.session_metrics.test_pass_rate
            efficiency = self.session_metrics.git_workflow_efficiency_score

            correlation = round((pass_rate + (efficiency / 100)) / 2, 2)
            correlations["test_efficiency_correlation"] = correlation

        if (
            self.session_metrics.ai_fixes_applied is not None
            and self.session_metrics.test_pass_rate is not None
        ):
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
