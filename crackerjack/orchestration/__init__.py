"""Hook orchestration layer for ACB integration.

This package provides the orchestration layer for managing hook execution,
dependency resolution, and caching. It bridges the existing pre-commit-based
system with ACB's component architecture.

Key Components:
- HookOrchestratorAdapter: Main orchestration component
- Execution strategies: Parallel and sequential execution
- Cache adapters: Integration with tool_proxy and future cache backends

Architecture:
The orchestrator supports dual execution modes:
1. Legacy mode: Delegates to existing HookExecutor (pre-commit CLI)
2. ACB mode: Direct adapter execution via depends.get()

Migration Path:
- Phase 3-7: Legacy mode (orchestrator + pre-commit)
- Phase 8+: ACB mode (orchestrator + direct adapters)
"""

from __future__ import annotations

__all__ = [
    "HookOrchestratorAdapter",
    "HookOrchestratorSettings",
]


# Lazy imports to avoid circular dependencies
from typing import Any


def __getattr__(name: str) -> Any:
    if name == "HookOrchestratorAdapter":
        from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter

        return HookOrchestratorAdapter
    elif name == "HookOrchestratorSettings":
        from crackerjack.orchestration.hook_orchestrator import HookOrchestratorSettings

        return HookOrchestratorSettings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
