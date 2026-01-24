from typing import Any

from . import (
    architect_agent,
    documentation_agent,
    dry_agent,
    formatting_agent,
    import_optimization_agent,
    performance_agent,
    refactoring_agent,
    security_agent,
    semantic_agent,
    test_creation_agent,
    test_specialist_agent,
)
from .base import AgentContext, FixResult, Issue, IssueType, Priority, SubAgent
from .coordinator import AgentCoordinator
from .error_middleware import agent_error_boundary
from .tracker import AgentTracker, get_agent_tracker, reset_agent_tracker

__all__ = [
    "AgentContext",
    "AgentCoordinator",
    "AgentTracker",
    "FixResult",
    "Issue",
    "IssueType",
    "Priority",
    "SubAgent",
    "agent_error_boundary",
    "architect_agent",
    "documentation_agent",
    "dry_agent",
    "formatting_agent",
    "get_agent_tracker",
    "import_optimization_agent",
    "performance_agent",
    "refactoring_agent",
    "reset_agent_tracker",
    "security_agent",
    "semantic_agent",
    "test_creation_agent",
    "test_specialist_agent",
]


def __getattr__(name: str) -> Any:
    agent_modules = {
        "architect_agent",
        "documentation_agent",
        "dry_agent",
        "formatting_agent",
        "import_optimization_agent",
        "performance_agent",
        "refactoring_agent",
        "security_agent",
        "semantic_agent",
        "test_creation_agent",
        "test_specialist_agent",
    }

    if name in agent_modules:
        import importlib

        module = importlib.import_module(f".{name}", package="crackerjack.agents")
        globals()[name] = module
        return module

    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)
