"""
Workflow orchestration for crackerjack.

This module provides high-level workflows that coordinate multiple
agents and services to accomplish complex tasks like iterative auto-fixing.

It also provides ACB workflow integration for declarative workflow execution
with automatic parallelization and event-driven coordination.
"""

from .actions import ACTION_REGISTRY, register_actions
from .auto_fix import AutoFixWorkflow, FixIteration
from .container_builder import WorkflowContainerBuilder
from .definitions import (
    COMMIT_WORKFLOW,
    COMPREHENSIVE_PARALLEL_WORKFLOW,
    FAST_HOOKS_WORKFLOW,
    PUBLISH_WORKFLOW,
    STANDARD_WORKFLOW,
    TEST_WORKFLOW,
    select_workflow_for_options,
)
from .engine import CrackerjackWorkflowEngine
from .event_bridge import EventBridgeAdapter, StepEventMapping

__all__ = [
    # Legacy auto-fix workflow
    "AutoFixWorkflow",
    "FixIteration",
    # ACB workflow integration
    "CrackerjackWorkflowEngine",
    "EventBridgeAdapter",
    "StepEventMapping",
    "WorkflowContainerBuilder",
    # Workflow definitions
    "FAST_HOOKS_WORKFLOW",
    "STANDARD_WORKFLOW",
    "TEST_WORKFLOW",
    "COMMIT_WORKFLOW",
    "PUBLISH_WORKFLOW",
    "COMPREHENSIVE_PARALLEL_WORKFLOW",
    "select_workflow_for_options",
    # Action handlers
    "ACTION_REGISTRY",
    "register_actions",
]
