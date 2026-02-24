from typing import Any

from . import (
    architect_agent,
    dependency_agent,
    documentation_agent,
    dry_agent,
    formatting_agent,
    import_optimization_agent,
    performance_agent,
    refactoring_agent,
    refurb_agent,
    security_agent,
    semantic_agent,
    test_creation_agent,
    test_specialist_agent,
)
from .analysis_coordinator import AnalysisCoordinator
from .base import AgentContext, FixResult, Issue, IssueType, Priority, SubAgent
from .coordinator import AgentCoordinator
from .error_middleware import agent_error_boundary
from .fixer_coordinator import FixerCoordinator
from .tracker import AgentTracker
from .validation_coordinator import ValidationCoordinator

__all__ = [
    "AgentContext",
    "AgentCoordinator",
    "AgentTracker",
    "AnalysisCoordinator",
    "FixResult",
    "FixerCoordinator",
    "Issue",
    "IssueType",
    "Priority",
    "SubAgent",
    "ValidationCoordinator",
    "agent_error_boundary",
    "analysis_coordinator",
    "architect_agent",
    "dependency_agent",
    "documentation_agent",
    "dry_agent",
    "fixer_coordinator",
    "formatting_agent",
    "import_optimization_agent",
    "performance_agent",
    "refactoring_agent",
    "refurb_agent",
    "security_agent",
    "semantic_agent",
    "test_creation_agent",
    "test_specialist_agent",
    "validation_coordinator",
]


def __getattr__(name: str) -> Any:
    agent_modules = {
        "analysis_coordinator",
        "architect_agent",
        "dependency_agent",
        "documentation_agent",
        "dry_agent",
        "fixer_coordinator",
        "formatting_agent",
        "import_optimization_agent",
        "performance_agent",
        "refactoring_agent",
        "refurb_agent",
        "security_agent",
        "semantic_agent",
        "test_creation_agent",
        "test_specialist_agent",
        "validation_coordinator",
    }

    if name in agent_modules:
        import importlib

        module = importlib.import_module(f".{name}", package="crackerjack.agents")
        globals()[name] = module
        return module

    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)
