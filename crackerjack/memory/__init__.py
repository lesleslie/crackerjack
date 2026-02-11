"""Fix Strategy Memory package for neural pattern learning in AI agent fixes.

This package provides:
- FixStrategyStorage: Persistent SQLite storage with embeddings
- IssueEmbedder: Sentence-transformer based issue encoding
- Strategy recommendation based on historical success rates
- GitMetricsCollector: Development velocity and pattern tracking
"""

from crackerjack.memory.fix_strategy_storage import FixAttempt, FixStrategyStorage
from crackerjack.memory.git_metrics_collector import (
    BranchEvent,
    BranchMetrics,
    CommitData,
    CommitMetrics,
    MergeEvent,
    MergeMetrics,
    VelocityDashboard,
    _ConventionalCommitParser,
    _GitRepository,
)

# IssueEmbedder will be available after uv sync: sentence-transformers
# from crackerjack.memory.issue_embedder import IssueEmbedder, get_issue_embedder

__all__ = [
    "FixAttempt",
    "FixStrategyStorage",
    # "IssueEmbedder",  # Uncomment after uv sync
    # "get_issue_embedder",  # Uncomment after uv sync
    # Git Metrics
    "GitMetricsCollector",
    "CommitData",
    "CommitMetrics",
    "BranchMetrics",
    "MergeMetrics",
    "BranchEvent",
    "MergeEvent",
    "VelocityDashboard",
    "_ConventionalCommitParser",
    "_GitRepository",
]
