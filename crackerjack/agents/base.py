"""Lightweight type stubs for the agents package.

The agent runtime lives outside this checkout, but a handful of protocol
signatures still reference ``AgentContext`` and ``FixResult``. This module
provides just enough surface for type checkers to resolve those references
without re-introducing the full agent system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crackerjack.models.issues import FixResult

__all__ = ["AgentContext", "FixResult"]


@dataclass
class AgentContext:
    """Minimal context object referenced by ``AgentDelegatorProtocol``.

    Callers that need richer behavior should construct the full context
    provided by the agent runtime; this stub only carries the fields the
    type checker requires to validate the protocols module.
    """

    project_path: Path | None = None
    max_cache_size: int = 64
    extra: dict[str, Any] = field(default_factory=dict)
