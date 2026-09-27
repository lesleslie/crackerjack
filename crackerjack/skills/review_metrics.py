"""Lightweight metrics primitives for the review-pr skill.

Prometheus client (``prometheus_client``) is intentionally NOT a runtime
dependency of crackerjack (per ``pyproject.toml``); this module provides
the four counters/gauges the plan calls for, implemented as plain
thread-safe accumulators. Operators can wire a real exporter later if
needed — the surface area stays the same.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    le: float
    count: int = 0


@dataclass
class Histogram:
    """Approximate Prometheus histogram with fixed bucket boundaries.

    ``observe(value)`` increments every bucket whose upper bound is
    ``>= value``. ``snapshot()`` returns the per-bucket counts and the
    total observation count. Buckets are immutable; create a fresh
    instance if you need different boundaries.
    """

    name: str
    help: str
    buckets: tuple[float, ...]
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _counts: list[int] = field(default_factory=list, repr=False)
    _total: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        sorted_buckets = tuple(sorted(self.buckets))
        self.buckets = sorted_buckets
        self._counts = [0 for _ in sorted_buckets]

    def observe(self, value: float) -> None:
        with self._lock:
            for index, le in enumerate(self.buckets):
                if value <= le:
                    self._counts[index] += 1
            self._total += 1

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {
                "buckets": dict(zip(self.buckets, self._counts, strict=True)),
                "count": self._total,
            }


@dataclass
class Counter:
    """Labeled counter.

    ``labels(...)`` returns a :class:`LabeledCounter` bound to a
    specific label tuple. ``inc(amount=1)`` on the bound counter
    increments the per-label bucket atomically.
    """

    name: str
    help: str
    labelnames: tuple[str, ...] = ()
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _values: dict[tuple[str, ...], int] = field(
        default_factory=lambda: defaultdict(int),
        repr=False,
    )

    def labels(self, **label_values: str) -> LabeledCounter:
        if set(label_values) != set(self.labelnames):
            missing = set(self.labelnames) - set(label_values)
            raise ValueError(f"missing labels: {sorted(missing)}")
        key = tuple(label_values[name] for name in self.labelnames)
        return LabeledCounter(self, key)

    def snapshot(self) -> dict[tuple[str, ...], int]:
        with self._lock:
            return dict(self._values)


@dataclass
class LabeledCounter:
    counter: Counter
    key: tuple[str, ...]
    _cached_amount: int = 0

    def inc(self, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("Counter only supports non-negative increments")
        with self.counter._lock:
            self.counter._values[self.key] += amount


@dataclass
class Gauge:
    """Single-value gauge.

    No labels; the GitHub quota remaining value is a singleton
    (process-wide) at any moment.
    """

    name: str
    help: str
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _value: float = 0.0

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def snapshot(self) -> float:
        with self._lock:
            return self._value


# Plan § "Observability added" — four metrics, all module-level singletons.
PR_REVIEW_DURATION = Histogram(
    "pr_review_duration_seconds",
    "Time to review one PR (fetch + dispatch + post).",
    buckets=(5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

PR_REVIEW_POST_TOTAL = Counter(
    "pr_review_post_total",
    "PR review posts, labeled by result.",
    labelnames=("result",),  # success | error | 5xx | 429 | auth | timeout
)

GITHUB_API_QUOTA_REMAINING = Gauge(
    "github_api_quota_remaining",
    "GitHub API quota remaining (from response headers).",
)

PR_REVIEW_FORK_PR_TOTAL = Counter(
    "pr_review_fork_pr_total",
    "Fork PR reviews (separate quota tracking).",
    labelnames=("result",),
)


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "LabeledCounter",
    "PR_REVIEW_DURATION",
    "PR_REVIEW_FORK_PR_TOTAL",
    "PR_REVIEW_POST_TOTAL",
    "GITHUB_API_QUOTA_REMAINING",
]