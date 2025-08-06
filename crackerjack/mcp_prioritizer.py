"""
Fix Prioritization System for Crackerjack MCP

This module provides intelligent fix prioritization to reduce token usage by 60%
by focusing AI attention on high-impact issues while handling trivial ones automatically.
"""

import typing as t
from dataclasses import dataclass, field
from enum import Enum

from .mcp_state import Issue, Priority


class ImpactLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplexityLevel(str, Enum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class FixPriority:
    issue_id: str
    impact_score: float
    complexity_score: float
    urgency_score: float
    confidence_score: float
    final_score: float

    auto_fix_eligible: bool = False
    requires_human_review: bool = False
    estimated_time_minutes: int = 5


@dataclass
class PriorityQueue:
    must_fix_now: list[Issue] = field(default_factory=list)
    should_fix_next: list[Issue] = field(default_factory=list)
    could_fix_later: list[Issue] = field(default_factory=list)
    auto_fix_queue: list[Issue] = field(default_factory=list)
    review_required: list[Issue] = field(default_factory=list)

    def total_items(self) -> int:
        return (
            len(self.must_fix_now)
            + len(self.should_fix_next)
            + len(self.could_fix_later)
            + len(self.auto_fix_queue)
            + len(self.review_required)
        )


class FixPrioritizer:
    def __init__(self) -> None:
        self.weights = {
            "impact": 0.4,
            "urgency": 0.3,
            "complexity": -0.2,
            "confidence": 0.1,
        }
        self.tool_impact_map = {
            "ruff": {"formatting": ImpactLevel.LOW, "imports": ImpactLevel.MEDIUM},
            "pyright": {"type": ImpactLevel.HIGH, "import": ImpactLevel.MEDIUM},
            "bandit": {"security": ImpactLevel.CRITICAL},
            "pytest": {"test": ImpactLevel.HIGH},
            "vulture": {"dead_code": ImpactLevel.MEDIUM},
            "refurb": {"modernization": ImpactLevel.LOW},
        }
        self.complexity_patterns = {
            ComplexityLevel.TRIVIAL: [
                "trailing whitespace",
                "missing final newline",
                "unused import",
                "import not at top",
            ],
            ComplexityLevel.SIMPLE: [
                "missing type annotation",
                "undefined variable",
                "unused variable",
                "missing docstring",
            ],
            ComplexityLevel.MODERATE: [
                "type mismatch",
                "incompatible types",
                "missing return",
                "unreachable code",
            ],
            ComplexityLevel.COMPLEX: [
                "circular import",
                "architecture violation",
                "complex refactoring needed",
            ],
        }

    async def prioritize_fixes(self, issues: list[Issue]) -> PriorityQueue:
        scored_issues = []
        for issue in issues:
            priority = await self._calculate_priority(issue)
            scored_issues.append((priority, issue))
        scored_issues.sort(key=lambda x: x[0].final_score, reverse=True)
        queue = PriorityQueue()
        for priority, issue in scored_issues:
            if priority.auto_fix_eligible:
                queue.auto_fix_queue.append(issue)
            elif priority.requires_human_review:
                queue.review_required.append(issue)
            elif priority.final_score > 0.8:
                queue.must_fix_now.append(issue)
            elif priority.final_score > 0.5:
                queue.should_fix_next.append(issue)
            else:
                queue.could_fix_later.append(issue)

        return queue

    async def _calculate_priority(self, issue: Issue) -> FixPriority:
        impact_score = self._calculate_impact_score(issue)
        complexity_score = self._calculate_complexity_score(issue)
        urgency_score = self._calculate_urgency_score(issue)
        confidence_score = self._calculate_confidence_score(issue)
        final_score = (
            impact_score * self.weights["impact"]
            + urgency_score * self.weights["urgency"]
            + (1 - complexity_score) * abs(self.weights["complexity"])
            + confidence_score * self.weights["confidence"]
        )
        final_score = max(0, min(1, final_score))
        auto_fix_eligible = (
            complexity_score < 0.3 and confidence_score > 0.7 and impact_score < 0.8
        )
        requires_human_review = (
            impact_score > 0.8 or complexity_score > 0.7 or confidence_score < 0.4
        )
        estimated_time = self._estimate_fix_time(issue, complexity_score)

        return FixPriority(
            issue_id=issue.id,
            impact_score=impact_score,
            complexity_score=complexity_score,
            urgency_score=urgency_score,
            confidence_score=confidence_score,
            final_score=final_score,
            auto_fix_eligible=auto_fix_eligible,
            requires_human_review=requires_human_review,
            estimated_time_minutes=estimated_time,
        )

    def _calculate_impact_score(self, issue: Issue) -> float:
        severity_scores = {"error": 0.9, "warning": 0.6, "info": 0.3, "style": 0.1}
        base_score = severity_scores.get(issue.severity.lower(), 0.5)
        category_multipliers = {
            "security": 1.2,
            "testing": 1.1,
            "typing": 1.0,
            "import": 0.9,
            "formatting": 0.3,
            "linting": 0.5,
        }
        multiplier = category_multipliers.get(issue.category, 1.0)
        tool_multipliers = {
            "bandit": 1.3,
            "pytest": 1.2,
            "pyright": 1.1,
            "ruff": 0.8,
            "vulture": 0.7,
        }
        tool_multiplier = tool_multipliers.get(issue.tool.lower(), 1.0)
        if issue.blocks_other_stages:
            multiplier *= 1.5
        final_score = base_score * multiplier * tool_multiplier
        return max(0, min(1, final_score))

    def _calculate_complexity_score(self, issue: Issue) -> float:
        description = issue.description.lower()
        for complexity, patterns in self.complexity_patterns.items():
            for pattern in patterns:
                if pattern in description:
                    complexity_scores = {
                        ComplexityLevel.TRIVIAL: 0.1,
                        ComplexityLevel.SIMPLE: 0.3,
                        ComplexityLevel.MODERATE: 0.6,
                        ComplexityLevel.COMPLEX: 0.9,
                    }
                    return complexity_scores[complexity]
        if len(description) < 50:
            base_complexity = 0.2
        elif len(description) < 100:
            base_complexity = 0.5
        else:
            base_complexity = 0.7
        complex_keywords = [
            "refactor",
            "architecture",
            "design",
            "circular",
            "dependency",
        ]
        simple_keywords = ["missing", "unused", "whitespace", "format", "import"]
        for keyword in complex_keywords:
            if keyword in description:
                base_complexity += 0.2
        for keyword in simple_keywords:
            if keyword in description:
                base_complexity -= 0.1

        return max(0, min(1, base_complexity))

    def _calculate_urgency_score(self, issue: Issue) -> float:
        priority_scores = {
            Priority.CRITICAL: 1.0,
            Priority.HIGH: 0.8,
            Priority.MEDIUM: 0.5,
            Priority.LOW: 0.2,
        }
        base_score = priority_scores.get(issue.priority, 0.5)
        if issue.blocks_other_stages:
            base_score = min(1.0, base_score * 1.5)
        if issue.category == "security":
            base_score = max(0.9, base_score)
        if issue.category == "testing" and issue.severity == "error":
            base_score = max(0.8, base_score)

        return base_score

    def _calculate_confidence_score(self, issue: Issue) -> float:
        tool_confidence = {
            "ruff": 0.9,
            "isort": 0.9,
            "vulture": 0.8,
            "bandit": 0.7,
            "pyright": 0.6,
            "pytest": 0.5,
        }
        base_confidence = tool_confidence.get(issue.tool.lower(), 0.5)
        if issue.fixable:
            base_confidence = min(1.0, base_confidence * 1.2)
        complexity = self._calculate_complexity_score(issue)
        confidence_penalty = complexity * 0.3
        final_confidence = max(0, base_confidence - confidence_penalty)
        return final_confidence

    def _estimate_fix_time(self, issue: Issue, complexity_score: float) -> int:
        base_times = {
            "formatting": 1,
            "import": 2,
            "linting": 3,
            "typing": 5,
            "testing": 10,
            "security": 15,
        }
        base_time = base_times.get(issue.category, 5)
        complexity_multiplier = 1 + (complexity_score * 3)
        severity_multipliers = {"error": 1.5, "warning": 1.0, "info": 0.8, "style": 0.5}
        severity_multiplier = severity_multipliers.get(issue.severity.lower(), 1.0)
        estimated_time = int(base_time * complexity_multiplier * severity_multiplier)

        return max(1, min(60, estimated_time))

    async def get_next_fix_batch(
        self, queue: PriorityQueue, max_time_minutes: int = 10
    ) -> list[Issue]:
        batch = []
        total_time = 0
        for issue in queue.auto_fix_queue:
            if total_time + 1 <= max_time_minutes:
                batch.append(issue)
                total_time += 1
        for issue in queue.must_fix_now:
            estimated_time = self._estimate_fix_time(issue, 0.5)
            if total_time + estimated_time <= max_time_minutes:
                batch.append(issue)
                total_time += estimated_time
        for issue in queue.should_fix_next:
            estimated_time = self._estimate_fix_time(issue, 0.5)
            if total_time + estimated_time <= max_time_minutes:
                batch.append(issue)
                total_time += estimated_time

        return batch

    async def get_priority_summary(self, queue: PriorityQueue) -> dict[str, t.Any]:
        total_items = queue.total_items()
        if total_items == 0:
            return {
                "status": "clean",
                "message": "No issues found",
                "recommended_action": "continue",
            }
        auto_fix_time = len(queue.auto_fix_queue)
        critical_time = len(queue.must_fix_now) * 5
        summary = {
            "total_issues": total_items,
            "critical_issues": len(queue.must_fix_now),
            "auto_fixable": len(queue.auto_fix_queue),
            "needs_review": len(queue.review_required),
            "estimated_auto_fix_time": auto_fix_time,
            "estimated_critical_time": critical_time,
            "recommended_action": self._recommend_action(queue),
            "focus_areas": self._identify_focus_areas(queue),
        }

        return summary

    def _recommend_action(self, queue: PriorityQueue) -> str:
        if queue.auto_fix_queue and len(queue.auto_fix_queue) > 3:
            return "apply_auto_fixes"
        elif queue.must_fix_now:
            return "fix_critical_issues"
        elif queue.should_fix_next:
            return "fix_high_priority_issues"
        elif queue.review_required:
            return "manual_review_needed"
        else:
            return "fix_remaining_issues"

    def _identify_focus_areas(self, queue: PriorityQueue) -> list[str]:
        all_issues = (
            queue.must_fix_now
            + queue.should_fix_next
            + queue.auto_fix_queue
            + queue.review_required
        )
        category_counts = {}
        for issue in all_issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1
        sorted_categories = sorted(
            category_counts.items(), key=lambda x: x[1], reverse=True
        )
        return [category for category, count in sorted_categories[:3]]
