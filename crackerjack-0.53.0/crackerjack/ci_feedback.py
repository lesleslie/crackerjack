from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CIFailureAnalysis:
    failure_type: str
    pattern_id: str
    description: str
    similar_failures: list[dict[str, Any]]
    suggestions: list[str]
    confidence: float


class CIFeedbackAnalyzer:
    def __init__(self, patterns_path: str | Path = ".crackerjack/ci_patterns.json"):
        self.patterns_path = Path(patterns_path)
        self.patterns: list[dict[str, Any]] = []

        self.patterns_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.patterns_path.exists():
            self._save_patterns()
        self._load_patterns()

    def _load_patterns(self) -> None:
        if self.patterns_path.exists():
            try:
                data = json.loads(self.patterns_path.read_text())
                self.patterns = data.get("patterns", [])
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load CI patterns: {e}")

    def _save_patterns(self) -> None:
        self.patterns_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"patterns": self.patterns}
        self.patterns_path.write_text(json.dumps(data, indent=2))

    def analyze_ci_failure(
        self,
        build_log: str,
        test_results: dict[str, Any] | None = None,
        coverage_report: dict[str, Any] | None = None,
    ) -> CIFailureAnalysis:
        failure_type = self._identify_failure_type(build_log)

        similar_failures = self._find_similar_failures(failure_type, build_log)

        suggestions = self._generate_suggestions(failure_type, similar_failures)

        confidence = self._calculate_confidence(similar_failures)

        return CIFailureAnalysis(
            failure_type=failure_type,
            pattern_id=self._extract_pattern_id(build_log),
            description=self._describe_failure(failure_type, build_log),
            similar_failures=similar_failures,
            suggestions=suggestions,
            confidence=confidence,
        )

    def _identify_failure_type(self, build_log: str) -> str:
        log_lower = build_log.lower()

        if self._is_test_failure(log_lower):
            return "test_failure"
        if self._is_coverage_failure(log_lower):
            return "coverage_below_threshold"
        if self._is_linting_failure(build_log):
            return "linting_error"
        if self._is_type_check_failure(build_log):
            return "type_error"
        if self._is_import_failure(build_log):
            return "import_error"
        if "permission denied" in log_lower:
            return "permission_error"
        if "timeout" in log_lower:
            return "timeout"
        if "out of memory" in log_lower:
            return "out_of_memory"

        return "unknown_failure"

    def _is_test_failure(self, log_lower: str) -> bool:
        return (
            "pytest" in log_lower
            or "test session starts" in log_lower
            or ("assertionerror" in log_lower and "test_" in log_lower)
            or ("failed" in log_lower and "test_" in log_lower)
            or "test failed" in log_lower
        )

    def _is_coverage_failure(self, log_lower: str) -> bool:
        return "coverage" in log_lower and (
            "below threshold" in log_lower or "coverage check failed" in log_lower
        )

    def _is_linting_failure(self, build_log: str) -> bool:
        log_lower = build_log.lower()
        return "ruff error" in log_lower or "lint" in log_lower

    def _is_type_check_failure(self, build_log: str) -> bool:
        log_lower = build_log.lower()
        return "mypy error" in log_lower or "type checking" in log_lower

    def _is_import_failure(self, build_log: str) -> bool:
        log_lower = build_log.lower()
        return any(
            pattern in log_lower
            for pattern in ("import error", "modulenotfounderror", "importerror")
        )

    def _extract_pattern_id(self, build_log: str) -> str:
        lines = build_log.split("\n")
        for line in lines:
            line = line.strip()
            if line and any(
                marker in line.lower()
                for marker in ("error", "failed", "timeout", "exception")
            ):
                normalized = re.sub(r"\d+", "N", line)
                normalized = re.sub(r"[a-f0-9]{8,}", "HEX", normalized)
                return normalized[:100]

        return "unknown_pattern"

    def _find_similar_failures(
        self,
        failure_type: str,
        build_log: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        similar = []

        for pattern in self.patterns:
            if pattern.get("failure_type") == failure_type:
                similarity = self._calculate_log_similarity(
                    build_log,
                    pattern.get("log_sample", ""),
                )
                if similarity > 0.3:
                    similar.append(pattern | {"similarity": similarity})

        similar.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return similar[:limit]

    def _calculate_log_similarity(self, log1: str, log2: str) -> float:
        words1 = set(re.findall(r"\b\w+\b", log1.lower()))
        words2 = set(re.findall(r"\b\w+\b", log2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0

    def _generate_suggestions(
        self,
        failure_type: str,
        similar_failures: list[dict[str, Any]],
    ) -> list[str]:
        suggestions = []

        generic_suggestions = {
            "test_failure": [
                "✓ Run tests locally before pushing: uv run pytest",
                "✓ Check for flaky tests: uv run pytest --repeat=10",
                "✓ Run specific test: uv run pytest tests/test_module.py::test_function",
                "✓ Enable verbose output: uv run pytest -vv",
            ],
            "coverage_below_threshold": [
                "✓ Check coverage report: uv run pytest --cov",
                "✓ Write tests for uncovered lines",
                "✓ Mark uncovered lines as nocov if not testable: # pragma: no cover",
            ],
            "linting_error": [
                "✓ Run linter locally: uv run ruff check .",
                "✓ Auto-fix issues: uv run ruff check --fix .",
                "✓ Check specific file: uv run ruff check path/to/file.py",
            ],
            "type_error": [
                "✓ Run type checker: uv run mypy .",
                "✓ Add type hints to fix errors",
                "✓ Check specific file: uv run mypy path/to/file.py",
            ],
            "import_error": [
                "✓ Verify dependencies: uv pip list",
                "✓ Add missing dependency to pyproject.toml",
                "✓ Sync lock file: uv sync",
            ],
            "timeout": [
                "✓ Increase timeout in test configuration",
                "✓ Check for infinite loops",
                "✓ Optimize slow operations",
            ],
            "unknown_failure": [
                "✓ Review full build log for error details",
                "✓ Check CI configuration",
                "✓ Run build locally to reproduce",
            ],
        }

        suggestions.extend(generic_suggestions.get(failure_type, []))

        for failure in similar_failures:
            resolution = failure.get("resolution")
            if resolution:
                suggestions.append(f"✓ Historical fix: {resolution}")

        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion not in seen:
                seen.add(suggestion)
                unique_suggestions.append(suggestion)

        return unique_suggestions

    def _describe_failure(self, failure_type: str, build_log: str) -> str:
        descriptions = {
            "test_failure": "One or more tests failed during execution",
            "coverage_below_threshold": "Code coverage dropped below minimum threshold",
            "linting_error": "Code linting found style or quality issues",
            "type_error": "Type checking revealed type inconsistencies",
            "import_error": "Module import failed (missing dependency or path issue)",
            "permission_error": "Insufficient permissions to perform operation",
            "timeout": "Operation timed out (possible infinite loop or slow operation)",
            "out_of_memory": "Process exceeded memory limits",
            "unknown_failure": "Unknown failure type - check build log",
        }

        base_desc = descriptions.get(failure_type, "Unknown failure")

        error_lines = []
        for line in build_log.split("\n"):
            if any(
                marker in line.lower() for marker in ("error", "failed", "exception")
            ):
                error_lines.append(line.strip())
                if len(error_lines) >= 3:
                    break

        if error_lines:
            return f"{base_desc}\n\nError preview:\n" + "\n".join(error_lines[:3])
        return base_desc

    def _calculate_confidence(self, similar_failures: list[dict[str, Any]]) -> float:
        if not similar_failures:
            return 0.5

        best_similarity = similar_failures[0].get("similarity", 0)
        return min(1.0, 0.5 + best_similarity)

    def record_failure_resolution(
        self,
        pattern_id: str,
        resolution: str,
        successful: bool,
    ) -> None:
        pattern = {
            "pattern_id": pattern_id,
            "resolution": resolution,
            "successful": successful,
            "timestamp": datetime.now().isoformat(),
        }

        self.patterns.append(pattern)
        self._save_patterns()


def analyze_ci_failure(
    build_log: str,
    test_results: dict[str, Any] | None = None,
    coverage_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analyzer = CIFeedbackAnalyzer()
    analysis = analyzer.analyze_ci_failure(build_log, test_results, coverage_report)

    return {
        "failure_type": analysis.failure_type,
        "pattern_id": analysis.pattern_id,
        "description": analysis.description,
        "similar_failures_count": len(analysis.similar_failures),
        "similar_failures": analysis.similar_failures[:3],
        "suggestions": analysis.suggestions,
        "confidence": analysis.confidence,
        "recommended_next_steps": _generate_next_steps(analysis),
    }


def _generate_next_steps(analysis: CIFailureAnalysis) -> list[str]:
    steps = []

    if analysis.confidence > 0.7:
        steps.append("High confidence in suggestions - try them in order")
    elif analysis.confidence > 0.5:
        steps.append(
            "Medium confidence - review suggestions and apply what makes sense"
        )
    else:
        steps.append("Low confidence - investigate failure manually first")

    if analysis.similar_failures:
        steps.append(
            f"Found {len(analysis.similar_failures)} similar historical failures - review their resolutions"
        )

    steps.append("After fixing, run: uv run pytest to verify")

    return steps


__all__ = [
    "CIFailureAnalysis",
    "CIFeedbackAnalyzer",
    "analyze_ci_failure",
]
