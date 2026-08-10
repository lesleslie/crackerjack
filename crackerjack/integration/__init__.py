"""Live integration adapters for crackerjack.

Restored 2026-08-10 after AI-fix subsystem deletion. Imports from deleted
modules (akosha_integration, git_metrics_integration, git_semantic_search,
mahavishnu_integration) removed; only the live learning/MCP adapters
remain.
"""

from __future__ import annotations

from crackerjack.integration.akosha_learning import (
    AkoshaLearningIntegration,
    NoOpQueryOptimizer,
    QueryInteractionRecord,
    QueryOptimizerProtocol,
    QuerySuggestion,
    create_query_optimizer,
)
from crackerjack.integration.dhara_integration import (
    AdapterAttemptRecord,
    AdapterEffectiveness,
    AdapterLearnerProtocol,
    DharaAdapterLearner,
    DharaLearningIntegration,
    NoOpAdapterLearner,
    SQLiteAdapterLearner,
    create_adapter_learner,
)
from crackerjack.integration.mahavishnu_learning import (
    MahavishnuLearningIntegration,
    NoOpWorkflowLearner,
    WorkflowEffectiveness,
    WorkflowExecutionRecord,
    WorkflowLearnerProtocol,
    WorkflowRecommendation,
    create_workflow_learner,
)
from crackerjack.integration.oneiric_learning import (
    DAGExecutionRecord,
    ExecutionStrategy,
    NoOpDAGO_optimizer as NoOpDAGOptimizer,
    OneiricLearningIntegration,
    DAGO_optimizerProtocol as DAGOptimizerProtocol,
    SQLiteDAGO_optimizer as SQLiteDAGOptimizer,
    create_dag_optimizer,
)
from crackerjack.integration.session_buddy_integration import (
    CorrelationInsight,
    CorrelationStorage,
    CorrelationStorageSQLite,
    ExtendedSessionMetrics,
    GitVelocityMetrics,
    NoOpCorrelationStorage,
    NoOpGitMetricsReader,
    NoOpSessionBuddyClient,
    SessionBuddyClient,
    SessionBuddyDirectClient,
    SessionBuddyIntegration,
    create_session_buddy_integration,
)
from crackerjack.integration.skills_tracking import (
    NoOpSkillsTracker,
    SessionBuddyDirectTracker,
    SessionBuddyMCPTracker,
    SkillExecutionContext,
    SkillsTrackerProtocol,
    create_skills_tracker,
)

__all__ = [
    "AdapterAttemptRecord",
    "AdapterEffectiveness",
    "AdapterLearnerProtocol",
    "AkoshaLearningIntegration",
    "CorrelationInsight",
    "CorrelationStorage",
    "CorrelationStorageSQLite",
    "DAGExecutionRecord",
    "DAGOptimizerProtocol",
    "DharaAdapterLearner",
    "DharaLearningIntegration",
    "ExecutionStrategy",
    "ExtendedSessionMetrics",
    "GitVelocityMetrics",
    "MahavishnuLearningIntegration",
    "NoOpAdapterLearner",
    "NoOpCorrelationStorage",
    "NoOpDAGOptimizer",
    "NoOpGitMetricsReader",
    "NoOpQueryOptimizer",
    "NoOpSessionBuddyClient",
    "NoOpSkillsTracker",
    "NoOpWorkflowLearner",
    "OneiricLearningIntegration",
    "QueryInteractionRecord",
    "QueryOptimizerProtocol",
    "QuerySuggestion",
    "SQLiteAdapterLearner",
    "SQLiteDAGOptimizer",
    "SessionBuddyClient",
    "SessionBuddyDirectClient",
    "SessionBuddyDirectTracker",
    "SessionBuddyIntegration",
    "SessionBuddyMCPTracker",
    "SkillExecutionContext",
    "SkillsTrackerProtocol",
    "WorkflowEffectiveness",
    "WorkflowExecutionRecord",
    "WorkflowLearnerProtocol",
    "WorkflowRecommendation",
    "create_adapter_learner",
    "create_dag_optimizer",
    "create_query_optimizer",
    "create_session_buddy_integration",
    "create_skills_tracker",
    "create_workflow_learner",
]