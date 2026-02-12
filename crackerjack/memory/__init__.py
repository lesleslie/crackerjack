from __future__ import annotations

import logging
import sqlite3
import threading
import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from crackerjack.agents.base import FixResult, Issue
from crackerjack.memory.fix_strategy_storage import FixAttempt, FixStrategyStorage
from crackerjack.memory.git_metrics_collector import (
    BranchEvent,
    CommitData,
    GitMetricsCollector,
    MergeEvent,
)

logger = logging.getLogger(__name__)


_thread_local = threading.local()


@dataclass
class GitHistoryEntry:
    path: str
    timestamp: datetime
