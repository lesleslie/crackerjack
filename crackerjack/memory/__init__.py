from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

_thread_local = threading.local()


@dataclass
class GitHistoryEntry:
    path: str
    timestamp: datetime
