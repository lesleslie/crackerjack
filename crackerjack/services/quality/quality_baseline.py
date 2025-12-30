import asyncio
import logging
import subprocess
import typing as t
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

# Repository pattern uses in-memory storage via cache system
# See: crackerjack.services.cache.CrackerjackCache
if TYPE_CHECKING:
    pass  # No external dependencies needed

from crackerjack.models.protocols import QualityBaselineProtocol
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


class QualityBaselineService(QualityBaselineProtocol):
    """Service for tracking and persisting quality baselines across sessions."""

    def __init__(
        self,
        cache: CrackerjackCache | None = None,
        repository: Any = None,  # Repository pattern disabled
    ) -> None:
        self.cache = cache or CrackerjackCache()
        self._logger = logging.getLogger(__name__)
        # Repository pattern uses in-memory cache storage
        self._repository: Any = None  # Not needed - using cache system

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
        """Synchronous wrapper for asynchronous baseline recording."""
        return self._run_async(
            self.arecord_baseline(
                coverage_percent=coverage_percent,
                test_count=test_count,
                test_pass_rate=test_pass_rate,
                hook_failures=hook_failures,
                complexity_violations=complexity_violations,
                security_issues=security_issues,
                type_errors=type_errors,
                linting_issues=linting_issues,
            )
        )

    async def arecord_baseline(
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
        await self._persist_metrics(metrics)
        return metrics

    def get_baseline(self, git_hash: str | None = None) -> QualityMetrics | None:
        """Synchronous wrapper around asynchronous baseline retrieval."""
        return self._run_async(self.aget_baseline(git_hash=git_hash))

    async def aget_baseline(
        self,
        git_hash: str | None = None,
    ) -> QualityMetrics | None:
        """Get quality baseline for specific commit (or current commit)."""
        if not git_hash:
            git_hash = self.get_current_git_hash()

        if not git_hash:
            return None

        if self._repository:
            record = await self._repository.get_by_git_hash(git_hash)
            if record:
                metrics = self._record_to_metrics(record)
                self.cache.set_quality_baseline(git_hash, metrics.to_dict())
                return metrics

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
        """Synchronous wrapper around asynchronous baseline listing."""
        return self._run_async(self.aget_recent_baselines(limit=limit))

    async def aget_recent_baselines(self, limit: int = 10) -> list[QualityMetrics]:
        """Get recent baselines (requires git log parsing since cache is keyed by hash)."""
        if self._repository:
            records = await self._repository.list_recent(limit=limit)
            return [self._record_to_metrics(record) for record in records]

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

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    async def _persist_metrics(self, metrics: QualityMetrics) -> None:
        if not self._repository:
            return

        try:
            await self._repository.upsert(
                {
                    "git_hash": metrics.git_hash,
                    "recorded_at": metrics.timestamp,
                    "coverage_percent": metrics.coverage_percent,
                    "test_count": metrics.test_count,
                    "test_pass_rate": metrics.test_pass_rate,
                    "hook_failures": metrics.hook_failures,
                    "complexity_violations": metrics.complexity_violations,
                    "security_issues": metrics.security_issues,
                    "type_errors": metrics.type_errors,
                    "linting_issues": metrics.linting_issues,
                    "quality_score": metrics.quality_score,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.debug(
                "Failed to persist quality baseline record",
                exc_info=exc,
            )

    def _record_to_metrics(
        self, record: Any
    ) -> QualityMetrics:  # QualityBaselineRecord when enabled
        return QualityMetrics(
            git_hash=record.git_hash,
            timestamp=record.recorded_at,
            coverage_percent=record.coverage_percent,
            test_count=record.test_count,
            test_pass_rate=record.test_pass_rate,
            hook_failures=record.hook_failures,
            complexity_violations=record.complexity_violations,
            security_issues=record.security_issues,
            type_errors=record.type_errors,
            linting_issues=record.linting_issues,
            quality_score=record.quality_score,
        )

    def _run_async(self, coro: t.Awaitable[t.Any]) -> t.Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        msg = (
            "QualityBaselineService synchronous method called while an event loop is "
            "running. Use the corresponding async method instead."
        )
        raise RuntimeError(msg)

    # Protocol methods
    def get_current_baseline(self) -> dict[str, t.Any]:
        """Protocol method for getting baseline metrics."""
        baseline = self.get_baseline()  # Call the existing method
        if baseline:
            return baseline.to_dict()
        return {}

    def update_baseline(self, metrics: dict[str, t.Any]) -> bool:
        """Protocol method for updating baseline metrics."""
        try:
            # Extract required values from metrics dict
            coverage_percent = metrics.get("coverage_percent", 0.0)
            test_count = metrics.get("test_count", 0)
            test_pass_rate = metrics.get("test_pass_rate", 0.0)
            hook_failures = metrics.get("hook_failures", 0)
            complexity_violations = metrics.get("complexity_violations", 0)
            security_issues = metrics.get("security_issues", 0)
            type_errors = metrics.get("type_errors", 0)
            linting_issues = metrics.get("linting_issues", 0)

            result = self.record_baseline(
                coverage_percent=coverage_percent,
                test_count=test_count,
                test_pass_rate=test_pass_rate,
                hook_failures=hook_failures,
                complexity_violations=complexity_violations,
                security_issues=security_issues,
                type_errors=type_errors,
                linting_issues=linting_issues,
            )
            return result is not None
        except Exception:
            return False

    def compare(self, current: dict[str, t.Any]) -> dict[str, t.Any]:
        """Protocol method for comparing current metrics against baseline."""
        return self.compare_with_baseline(current)
