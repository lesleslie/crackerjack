import subprocess
import typing as t
from dataclasses import asdict, dataclass
from datetime import datetime

from crackerjack.services.cache import CrackerjackCache


@dataclass
class QualityMetrics:
    """Quality metrics for a specific commit/session."""

    git_hash: str
    timestamp: datetime
    coverage_percent: float
    test_count: int
    test_pass_rate: float
    hook_failures: int
    complexity_violations: int
    security_issues: int
    type_errors: int
    linting_issues: int
    quality_score: int  # Overall score 0-100

    def to_dict(self) -> dict[str, t.Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "QualityMetrics":
        data = data.copy()
        if isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class QualityBaselineService:
    """Service for tracking and persisting quality baselines across sessions."""

    def __init__(self, cache: CrackerjackCache | None = None) -> None:
        self.cache = cache or CrackerjackCache()

    def get_current_git_hash(self) -> str | None:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def calculate_quality_score(
        self,
        coverage_percent: float,
        test_pass_rate: float,
        hook_failures: int,
        complexity_violations: int,
        security_issues: int,
        type_errors: int,
        linting_issues: int,
    ) -> int:
        """Calculate overall quality score (0-100)."""
        # Base score from coverage and tests
        base_score = (coverage_percent * 0.4) + (test_pass_rate * 0.3)

        # Penalty for issues (each issue type has different weight)
        penalties = (
            hook_failures * 2.0  # Hook failures are serious
            + complexity_violations * 1.5  # Complexity is important
            + security_issues * 3.0  # Security is critical
            + type_errors * 2.0  # Type errors are serious
            + linting_issues * 0.5  # Linting is less critical
        )

        # Apply penalties with diminishing returns
        penalty_score = max(0, 30 - (penalties * 0.8))

        return max(0, min(100, int(base_score + penalty_score)))

    def record_baseline(
        self,
        coverage_percent: float,
        test_count: int,
        test_pass_rate: float,
        hook_failures: int = 0,
        complexity_violations: int = 0,
        security_issues: int = 0,
        type_errors: int = 0,
        linting_issues: int = 0,
    ) -> QualityMetrics | None:
        """Record quality baseline for current commit."""
        git_hash = self.get_current_git_hash()
        if not git_hash:
            return None

        quality_score = self.calculate_quality_score(
            coverage_percent=coverage_percent,
            test_pass_rate=test_pass_rate,
            hook_failures=hook_failures,
            complexity_violations=complexity_violations,
            security_issues=security_issues,
            type_errors=type_errors,
            linting_issues=linting_issues,
        )

        metrics = QualityMetrics(
            git_hash=git_hash,
            timestamp=datetime.now(),
            coverage_percent=coverage_percent,
            test_count=test_count,
            test_pass_rate=test_pass_rate,
            hook_failures=hook_failures,
            complexity_violations=complexity_violations,
            security_issues=security_issues,
            type_errors=type_errors,
            linting_issues=linting_issues,
            quality_score=quality_score,
        )

        # Store in cache for persistence across sessions
        self.cache.set_quality_baseline(git_hash, metrics.to_dict())
        return metrics

    def get_baseline(self, git_hash: str | None = None) -> QualityMetrics | None:
        """Get quality baseline for specific commit (or current commit)."""
        if not git_hash:
            git_hash = self.get_current_git_hash()

        if not git_hash:
            return None

        baseline_data = self.cache.get_quality_baseline(git_hash)
        if baseline_data:
            return QualityMetrics.from_dict(baseline_data)

        return None

    def compare_with_baseline(
        self,
        current_metrics: dict[str, t.Any],
        baseline_git_hash: str | None = None,
    ) -> dict[str, t.Any]:
        """Compare current metrics with baseline."""
        baseline = self.get_baseline(baseline_git_hash)
        if not baseline:
            return {
                "comparison_available": False,
                "message": "No baseline found for comparison",
            }

        current_score = self.calculate_quality_score(**current_metrics)

        return {
            "comparison_available": True,
            "baseline_score": baseline.quality_score,
            "current_score": current_score,
            "score_change": current_score - baseline.quality_score,
            "baseline_timestamp": baseline.timestamp.isoformat(),
            "improvements": self._identify_improvements(baseline, current_metrics),
            "regressions": self._identify_regressions(baseline, current_metrics),
        }

    def _identify_improvements(
        self, baseline: QualityMetrics, current: dict[str, t.Any]
    ) -> list[str]:
        """Identify areas that improved since baseline."""
        improvements = []

        if current["coverage_percent"] > baseline.coverage_percent:
            improvements.append(
                f"Coverage increased by {current['coverage_percent'] - baseline.coverage_percent:.1f}%"
            )

        if current["test_pass_rate"] > baseline.test_pass_rate:
            improvements.append(
                f"Test pass rate improved by {current['test_pass_rate'] - baseline.test_pass_rate:.1f}%"
            )

        if current.get("hook_failures", 0) < baseline.hook_failures:
            improvements.append(
                f"Hook failures reduced by {baseline.hook_failures - current.get('hook_failures', 0)}"
            )

        return improvements

    def _identify_regressions(
        self, baseline: QualityMetrics, current: dict[str, t.Any]
    ) -> list[str]:
        """Identify areas that regressed since baseline."""
        regressions = []

        if current["coverage_percent"] < baseline.coverage_percent:
            regressions.append(
                f"Coverage decreased by {baseline.coverage_percent - current['coverage_percent']:.1f}%"
            )

        if current["test_pass_rate"] < baseline.test_pass_rate:
            regressions.append(
                f"Test pass rate decreased by {baseline.test_pass_rate - current['test_pass_rate']:.1f}%"
            )

        if current.get("security_issues", 0) > baseline.security_issues:
            regressions.append(
                f"Security issues increased by {current.get('security_issues', 0) - baseline.security_issues}"
            )

        return regressions

    def get_recent_baselines(self, limit: int = 10) -> list[QualityMetrics]:
        """Get recent baselines (requires git log parsing since cache is keyed by hash)."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-n", str(limit), "--format=%H"],
                capture_output=True,
                text=True,
                check=True,
            )
            git_hashes = result.stdout.strip().split("\n")

            baselines = []
            for git_hash in git_hashes:
                baseline = self.get_baseline(git_hash.strip())
                if baseline:
                    baselines.append(baseline)

            return sorted(baselines, key=lambda b: b.timestamp, reverse=True)

        except (subprocess.CalledProcessError, FileNotFoundError):
            return []
