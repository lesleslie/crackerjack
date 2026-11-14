"""Minimal context object for the agent delegator protocol.

The full agent runtime lives outside this checkout. What the type checker
needs is a shape for the ``context`` argument that
``AgentDelegatorProtocol`` passes to every delegator method.

This dataclass was moved here from ``crackerjack/agents/base.py`` when the
``crackerjack/agents`` package was deleted — that package held one file
after the AI-fix runtime was removed in the 2026-08-12 refactor, and the
model layer already owns the types the protocol refers to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["AgentContext"]


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
