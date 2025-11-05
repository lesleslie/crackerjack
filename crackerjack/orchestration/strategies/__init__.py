"""Execution strategies for hook orchestration.

This package provides different execution strategies for running hooks:
- ParallelExecutionStrategy: Concurrent execution with resource limits
- SequentialExecutionStrategy: One-at-a-time execution for dependent hooks

Strategies implement ExecutionStrategyProtocol and handle:
- Timeout management per hook
- Exception isolation
- Resource limiting (semaphores for parallel)
- Early exit on critical failures (sequential)
"""

from __future__ import annotations

__all__ = [
    "ParallelExecutionStrategy",
    "SequentialExecutionStrategy",
]


# Lazy imports
from typing import Any


def __getattr__(name: str) -> Any:
    if name == "ParallelExecutionStrategy":
        from crackerjack.orchestration.strategies.parallel_strategy import (
            ParallelExecutionStrategy,
        )

        return ParallelExecutionStrategy
    elif name == "SequentialExecutionStrategy":
        from crackerjack.orchestration.strategies.sequential_strategy import (
            SequentialExecutionStrategy,
        )

        return SequentialExecutionStrategy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
