"""Baseline management for pytest-benchmark performance regression detection."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Single benchmark result from pytest-benchmark."""

    name: str
    min: float  # Minimum time in seconds
    max: float  # Maximum time in seconds
    mean: float  # Mean time
    median: float  # Median time
    stddev: float  # Standard deviation
    rounds: int  # Number of rounds
    iterations: int  # Iterations per round
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def from_pytest_benchmark(cls, data: dict[str, Any]) -> BenchmarkResult:
        """Create BenchmarkResult from pytest-benchmark JSON output."""
        return cls(
            name=data.get("name", "unknown"),
            min=data.get("min", 0.0),
            max=data.get("max", 0.0),
            mean=data.get("mean", 0.0),
            median=data.get("median", 0.0),
            stddev=data.get("stddev", 0.0),
            rounds=data.get("rounds", 0),
            iterations=data.get("iterations", 1),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class RegressionCheck:
    """Result of comparing a benchmark against baseline."""

    name: str
    baseline: BenchmarkResult | None
    current: BenchmarkResult
    change_percent: float
    is_regression: bool
    is_new: bool = False
    is_improvement: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "current": self.current.to_dict(),
            "change_percent": self.change_percent,
            "is_regression": self.is_regression,
            "is_new": self.is_new,
            "is_improvement": self.is_improvement,
        }


class BaselineManager:
    """Manages benchmark baseline storage and comparison.

    The BaselineManager handles:
    - Loading baselines from JSON files
    - Saving current benchmarks as baselines
    - Comparing current results against baselines
    - Detecting performance regressions

    Example:
        manager = BaselineManager(Path(".benchmarks/baseline.json"))
        manager.load()

        # Compare current result
        check = manager.compare("test_query", current_result, threshold=0.15)
        if check.is_regression:
            print(f"Performance regression: {check.change_percent:.1f}%")

        # Update baseline
        manager.update("test_query", current_result)
        manager.save()
    """

    def __init__(self, baseline_path: Path) -> None:
        """Initialize the BaselineManager.

        Args:
            baseline_path: Path to the baseline JSON file
        """
        self._path = baseline_path
        self._baselines: dict[str, BenchmarkResult] = {}

    @property
    def baseline_count(self) -> int:
        """Return the number of stored baselines."""
        return len(self._baselines)

    def load(self) -> None:
        """Load baselines from JSON file."""
        if not self._path.exists():
            logger.debug(
                "Baseline file does not exist, starting fresh",
                extra={"path": str(self._path)},
            )
            return

        try:
            data = json.loads(self._path.read_text())
            self._baselines = {
                k: BenchmarkResult(**v) for k, v in data.get("benchmarks", {}).items()
            }
            logger.info(
                "Loaded baselines from file",
                extra={
                    "path": str(self._path),
                    "count": len(self._baselines),
                },
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                "Failed to parse baseline file, starting fresh",
                extra={"path": str(self._path), "error": str(e)},
            )
            self._baselines = {}

    def save(self) -> None:
        """Save current baselines to JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "benchmarks": {k: v.to_dict() for k, v in self._baselines.items()},
        }

        self._path.write_text(json.dumps(data, indent=2))
        logger.info(
            "Saved baselines to file",
            extra={"path": str(self._path), "count": len(self._baselines)},
        )

    def compare(
        self,
        name: str,
        current: BenchmarkResult,
        threshold: float,
    ) -> RegressionCheck:
        """Compare current result against baseline.

        Args:
            name: Benchmark name
            current: Current benchmark result
            threshold: Regression threshold (0.15 = 15%)

        Returns:
            RegressionCheck with comparison results
        """
        if name not in self._baselines:
            return RegressionCheck(
                name=name,
                baseline=None,
                current=current,
                change_percent=0.0,
                is_regression=False,
                is_new=True,
                is_improvement=False,
            )

        baseline = self._baselines[name]

        # Avoid division by zero
        if baseline.median == 0:
            change = 0.0 if current.median == 0 else float("inf")
        else:
            change = (current.median - baseline.median) / baseline.median

        is_regression = change > threshold
        is_improvement = change < -threshold

        return RegressionCheck(
            name=name,
            baseline=baseline,
            current=current,
            change_percent=change * 100,
            is_regression=is_regression,
            is_new=False,
            is_improvement=is_improvement,
        )

    def update(self, name: str, result: BenchmarkResult) -> None:
        """Update baseline with new result.

        Args:
            name: Benchmark name
            result: Benchmark result to store
        """
        self._baselines[name] = result
        logger.debug(
            "Updated baseline",
            extra={"name": name, "median": result.median},
        )

    def get_baseline(self, name: str) -> BenchmarkResult | None:
        """Get baseline for a specific benchmark.

        Args:
            name: Benchmark name

        Returns:
            BenchmarkResult if exists, None otherwise
        """
        return self._baselines.get(name)

    def clear(self) -> None:
        """Clear all stored baselines."""
        self._baselines.clear()
        logger.debug("Cleared all baselines")

    def get_all_names(self) -> list[str]:
        """Get all benchmark names with baselines."""
        return list(self._baselines.keys())
