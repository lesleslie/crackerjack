from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CommitResult:
    success: bool
    quality_metrics: dict[str, float]
    problem_context: dict[str, Any]
    applied_fix: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class Pattern:
    pattern_type: str
    category: str
    context: dict[str, Any]
    solution: dict[str, Any] | None
    outcome_score: float
    created_at: datetime = field(default_factory=datetime.now)
    last_applied: datetime | None = None
    application_count: int = 0
    feedback_score: float = 0.0


class ReflectionLoop:
    def __init__(self, storage_path: str | Path = ".crackerjack/patterns.json"):
        self.storage_path = Path(storage_path)
        self.patterns: list[Pattern] = []

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._save_patterns()
        self._load_patterns()

    def _load_patterns(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self.patterns = [
                    Pattern(
                        pattern_type=p["pattern_type"],
                        category=p["category"],
                        context=p["context"],
                        solution=p.get("solution"),
                        outcome_score=p["outcome_score"],
                        created_at=datetime.fromisoformat(p["created_at"]),
                        last_applied=datetime.fromisoformat(p["last_applied"])
                        if p.get("last_applied")
                        else None,
                        application_count=p["application_count"],
                        feedback_score=p["feedback_score"],
                    )
                    for p in data.get("patterns", [])
                ]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load patterns: {e}")

    def _save_patterns(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "patterns": [
                {
                    "pattern_type": p.pattern_type,
                    "category": p.category,
                    "context": p.context,
                    "solution": p.solution,
                    "outcome_score": p.outcome_score,
                    "created_at": p.created_at.isoformat(),
                    "last_applied": p.last_applied.isoformat()
                    if p.last_applied
                    else None,
                    "application_count": p.application_count,
                    "feedback_score": p.feedback_score,
                }
                for p in self.patterns
            ]
        }
        self.storage_path.write_text(json.dumps(data, indent=2))

    def analyze_commit(self, result: CommitResult) -> None:
        if result.success:
            self._capture_success_pattern(result)
        else:
            self._capture_failure_pattern(result)

        self._save_patterns()

    def _capture_success_pattern(self, result: CommitResult) -> None:
        pattern = Pattern(
            pattern_type="solution",
            category=self._infer_category(result),
            context={
                "problem": result.problem_context.get("error_type", "unknown"),
                "files_changed": result.problem_context.get("files_changed", []),
                "quality_metrics": result.quality_metrics,
            },
            solution=result.applied_fix or {},
            outcome_score=self._calculate_outcome_score(result),
        )

        self.patterns.append(pattern)
        print(f"✓ Captured successful pattern: {pattern.category}")

    def _capture_failure_pattern(self, result: CommitResult) -> None:
        pattern = Pattern(
            pattern_type="anti_pattern",
            category=self._infer_category(result),
            context={
                "problem": result.problem_context.get("error_type", "unknown"),
                "error_message": result.error_message,
                "quality_metrics": result.quality_metrics,
            },
            solution=None,
            outcome_score=0.0,
        )

        self.patterns.append(pattern)
        print(f"⚠ Captured failure pattern: {pattern.category}")

    def find_similar_patterns(
        self,
        current_context: dict[str, Any],
        threshold: float = 0.75,
        limit: int = 5,
    ) -> list[Pattern]:
        similar_patterns = []

        for pattern in self.patterns:
            similarity = self._calculate_similarity(current_context, pattern.context)
            if similarity >= threshold:
                similar_patterns.append((similarity, pattern))

        similar_patterns.sort(key=lambda x: (x[0], x[1].outcome_score), reverse=True)

        return [pattern for _, pattern in similar_patterns[:limit]]

    def apply_pattern(
        self, pattern_id: int, outcome: str, feedback: str | None = None
    ) -> None:
        if 0 <= pattern_id < len(self.patterns):
            pattern = self.patterns[pattern_id]
            pattern.last_applied = datetime.now()
            pattern.application_count += 1

            if outcome == "success":
                pattern.feedback_score = min(1.0, pattern.feedback_score + 0.1)
            elif outcome == "failure":
                pattern.feedback_score = max(0.0, pattern.feedback_score - 0.2)

            self._save_patterns()
            print(f"✓ Recorded pattern application: {outcome}")

    def _infer_category(self, result: CommitResult) -> str:
        if result.quality_metrics.get("security_score", 1.0) < 0.8:
            return "security"
        if result.quality_metrics.get("performance_score", 1.0) < 0.8:
            return "performance"
        if result.quality_metrics.get("test_coverage", 1.0) < 0.8:
            return "testing"
        if result.quality_metrics.get("documentation_score", 1.0) < 0.8:
            return "documentation"
        return "general"

    def _calculate_outcome_score(self, result: CommitResult) -> float:
        metrics = [
            result.quality_metrics.get("security_score", 1.0),
            result.quality_metrics.get("performance_score", 1.0),
            result.quality_metrics.get("test_coverage", 1.0),
            result.quality_metrics.get("documentation_score", 1.0),
        ]
        return sum(metrics) / len(metrics) if metrics else 0.5

    def _calculate_similarity(
        self, context1: dict[str, Any], context2: dict[str, Any]
    ) -> float:
        keys1 = set(context1.keys())
        keys2 = set(context2.keys())

        if not keys1 or not keys2:
            return 0.0

        intersection = keys1 & keys2
        union = keys1 | keys2

        return len(intersection) / len(union) if union else 0.0

    def generate_improvements(self, recent_results: list[CommitResult]) -> list[str]:
        suggestions = []

        for result in recent_results:
            if result.success:
                if result.quality_metrics.get("test_coverage", 1.0) > 0.9:
                    suggestions.append(
                        "✓ Excellent test coverage achieved. "
                        "Consider this as a best practice for future changes."
                    )
            else:
                error_type = result.problem_context.get("error_type", "unknown")
                suggestions.append(
                    f"⚠ Common error pattern: {error_type}. "
                    f"Solution: {self._get_suggested_fix(error_type)}"
                )

        return suggestions

    def _get_suggested_fix(self, error_type: str) -> str:
        fixes = {
            "ImportError": "Check dependencies are listed in requirements.txt or pyproject.toml",
            "SyntaxError": "Run linter (ruff) to catch syntax errors before commit",
            "IndentationError": "Run formatter (black) to fix indentation automatically",
            "TypeError": "Add type hints and run mypy for type checking",
            "AttributeError": "Review object structure and use getattr() for optional attributes",
        }
        return fixes.get(error_type, "Review error details and consult documentation")


_reflection_loop: ReflectionLoop | None = None


def get_reflection_loop() -> ReflectionLoop:
    global _reflection_loop
    if _reflection_loop is None:
        _reflection_loop = ReflectionLoop()
    return _reflection_loop


__all__ = [
    "CommitResult",
    "Pattern",
    "ReflectionLoop",
    "get_reflection_loop",
]
