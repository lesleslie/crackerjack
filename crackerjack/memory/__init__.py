"""Fix Strategy Memory package for neural pattern learning in AI agent fixes.

This package provides:
- FixStrategyStorage: Persistent SQLite storage with embeddings
- IssueEmbedder: Sentence-transformer based issue encoding
- Strategy recommendation based on historical success rates
"""

from crackerjack.memory.fix_strategy_storage import FixAttempt, FixStrategyStorage
from crackerjack.memory.issue_embedder import IssueEmbedder, get_issue_embedder

__all__ = [
    "FixAttempt",
    "FixStrategyStorage",
    "IssueEmbedder",
    "get_issue_embedder",
]
