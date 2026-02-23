
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

    name: str
    min: float
    max: float
    mean: float
    median: float
    stddev: float
    rounds: int
    iterations: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def from_pytest_benchmark(cls, data: dict[str, Any]) -> BenchmarkResult:
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
        return asdict(self)


@dataclass
class RegressionCheck:

    name: str
    baseline: BenchmarkResult | None
    current: BenchmarkResult
    change_percent: float
    is_regression: bool
    is_new: bool = False
    is_improvement: bool = False

    def to_dict(self) -> dict[str, Any]:
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

    def __init__(self, baseline_path: Path) -> None:
        self._path = baseline_path
        self._baselines: dict[str, BenchmarkResult] = {}

    @property
    def baseline_count(self) -> int:
        return len(self._baselines)

    def load(self) -> None:
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
        self._baselines[name] = result
        logger.debug(
            "Updated baseline",
            extra={"name": name, "median": result.median},
        )

    def get_baseline(self, name: str) -> BenchmarkResult | None:
        return self._baselines.get(name)

    def clear(self) -> None:
        self._baselines.clear()
        logger.debug("Cleared all baselines")

    def get_all_names(self) -> list[str]:
        return list(self._baselines.keys())
