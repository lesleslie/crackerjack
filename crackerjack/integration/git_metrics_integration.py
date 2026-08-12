"""Typed stub for the session-level git-metrics integration.

The full ``GitMetricsSessionCollector`` previously lived alongside other
memory / AI-fix subsystems that were removed when the AI-fix stage was
deleted (see ``crackerjack/core/autofix_coordinator.py`` for the
dead-code note). This module exists so the type checker can resolve
``crackerjack.integration.git_metrics_integration`` and so the call
site at ``crackerjack/core/session_coordinator.py:21`` (TYPE_CHECKING)
plus the runtime call at ``session_coordinator.py:316`` have the surface
they need.

The runtime body raises ``NotImplementedError``; the production path is
the ``get_repository_health_dashboard`` MCP tool exposed via the
``crackerjack-mahavishnu-git-analytics`` FastMCP server in
``crackerjack/mahavishnu/mcp/tools/git_analytics.py``. The single
runtime caller in ``session_coordinator.py:316`` is already None-guarded
by ``if self.git_metrics_collector is None: return None``, so this stub
never executes in practice.

TODO(mcpretentious-removed): restore full module once vishnu MCP wire-up is verified
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from crackerjack.models.session_metrics import SessionMetrics

if TYPE_CHECKING:
    from crackerjack.models.protocols import SecureSubprocessExecutorProtocol

__all__ = ["GitMetricsSessionCollector"]


class GitMetricsSessionCollector:
    def __init__(self, pkg_path: Path | None = None) -> None:
        self.pkg_path = pkg_path

    async def collect_session_metrics(
        self,
        executor: SecureSubprocessExecutorProtocol | None = None,
    ) -> SessionMetrics:
        """Collect session-level git metrics via ``executor``.

        Stub: production callers should invoke the
        ``get_repository_health_dashboard`` MCP tool on the
        ``crackerjack-mahavishnu-git-analytics`` FastMCP server instead.
        """
        raise NotImplementedError(
            "GitMetricsSessionCollector.collect_session_metrics is a stub. "
            "Use the get_repository_health_dashboard MCP tool instead.",
        )
