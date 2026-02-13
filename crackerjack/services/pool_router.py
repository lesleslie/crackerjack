"""Pool Router for intelligent tool-to-worker routing.

This module provides intelligent routing of quality tools to optimal workers
in Mahavishnu pools based on tool characteristics.
"""

from __future__ import annotations

import logging
from typing import Any

from rich.console import Console

logger = logging.getLogger(__name__)


class PoolRouter:
    """Route tools to optimal workers in Mahavishnu pools.

    Different tools have different characteristics:
    - CPU-intensive tools benefit from dedicated heavy-CPU workers
    - Fast tools can share workers
    - Security tools benefit from isolated workers

    This router analyzes tool characteristics and routes to best worker type.
    """

    # Tool-to-worker routing mapping
    TOOL_WORKER_MAP = {
        # Heavy CPU tools → dedicated workers
        "refurb": "heavy-cpu-worker",
        "complexipy": "heavy-cpu-worker",
        "pylint": "heavy-cpu-worker",
        "mypy": "heavy-cpu-worker",
        "bandit": "heavy-cpu-worker",

        # Fast tools (Rust-based, already optimized) → shared workers
        "skylos": "fast-worker",
        "ruff": "fast-worker",
        "vulture": "fast-worker",
        "pylint": "fast-worker",
        "codespell": "fast-worker",
        "check-jsonschema": "fast-worker",

        # Security tools → dedicated workers (isolation)
        "semgrep": "security-worker",
        "gitleaks": "security-worker",
        "bandit": "security-worker",
    }

    def __init__(
        self,
        console: Console | None = None,
    ) -> None:
        """Initialize the pool router.

        Args:
            console: Optional console for output
        """
        self.console = console or Console()

    async def route_to_best_pool(
        self,
        tool_name: str,
        files: list[Any],
    ) -> dict[str, Any]:
        """Route tool to best pool using intelligent routing.

        Args:
            tool_name: Name of tool to execute
            files: Files to process

        Returns:
            Dictionary with routing recommendation and worker type
        """
        worker_type = self.TOOL_WORKER_MAP.get(tool_name, "fast-worker")

        self.console.print(
            f"[cyan]🔀 Routing {tool_name} → {worker_type}[/cyan]"
        )

        routing_info = {
            "tool": tool_name,
            "worker_type": worker_type,
            "reason": self._get_routing_reason(tool_name, worker_type),
            "files_count": len(files),
        }

        return routing_info

    def _get_routing_reason(self, tool_name: str, worker_type: str) -> str:
        """Get human-readable reason for routing decision.

        Args:
            tool_name: Tool being routed
            worker_type: Target worker type

        Returns:
            Reason string
        """
        reasons = {
            ("heavy-cpu-worker", "refurb"): "Refurb requires deep Python analysis",
            ("heavy-cpu-worker", "complexipy"): "Complexipy needs significant CPU for pattern matching",
            ("heavy-cpu-worker", "pylint"): "PyLint performs comprehensive AST analysis",
            ("heavy-cpu-worker", "mypy"): "MyPy needs full type checking",
            ("heavy-cpu-worker", "bandit"): "Bandit requires deep security analysis",
            ("fast-worker", "skylos"): "Skylos is Rust-based, already optimized",
            ("fast-worker", "ruff"): "Ruff is fast enough for shared workers",
            ("fast-worker", "vulture"): "Vulture is quick AST scanner",
            ("fast-worker", "codespell"): "Codespell is fast spell checker",
            ("fast-worker", "check-jsonschema"): "JSON schema validation is lightweight",
            ("security-worker", "semgrep"): "Semgrep needs isolation for security scanning",
            ("security-worker", "gitleaks"): "Gitleaks needs isolation for secret scanning",
            ("security-worker", "bandit"): "Bandit needs isolation for security analysis",
        }

        return reasons.get(
            (worker_type, tool_name),
            f"{tool_name} routed to {worker_type} (default routing)",
        )

    async def get_optimal_pool_config(
        self,
        tools: list[str],
    ) -> dict[str, Any]:
        """Get optimal pool configuration for a set of tools.

        Args:
            tools: List of tools to be executed

        Returns:
            Pool configuration recommendation
        """
        # Analyze tool characteristics
        heavy_cpu_tools = []
        fast_tools = []
        security_tools = []

        for tool in tools:
            worker = self.TOOL_WORKER_MAP.get(tool, "fast-worker")

            if worker == "heavy-cpu-worker":
                heavy_cpu_tools.append(tool)
            elif worker == "fast-worker":
                fast_tools.append(tool)
            elif worker == "security-worker":
                security_tools.append(tool)

        # Generate recommendation
        recommendation = {
            "tools": tools,
            "heavy_cpu_count": len(heavy_cpu_tools),
            "fast_tools_count": len(fast_tools),
            "security_tools_count": len(security_tools),
            "total_tools": len(tools),
            "suggested_min_workers": max(2, len(tools)),
            "suggested_max_workers": max(8, len(tools) * 2),
        }

        self.console.print(
            f"[dim]Tool analysis: {len(heavy_cpu_tools)} heavy-CPU, "
            f"{len(fast_tools)} fast, {len(security_tools)} security[/dim]"
        )

        return recommendation

    def get_routing_summary(self) -> dict[str, Any]:
        """Get summary statistics of routing decisions.

        Returns:
            Dictionary with routing statistics
        """
        total_tools = len(self.TOOL_WORKER_MAP)

        summary = {
            "total_tools_supported": total_tools,
            "heavy_cpu_tools": sum(
                1 for worker in self.TOOL_WORKER_MAP.values()
                if worker == "heavy-cpu-worker"
            ),
            "fast_tools": sum(
                1 for worker in self.TOOL_WORKER_MAP.values()
                if worker == "fast-worker"
            ),
            "security_tools": sum(
                1 for worker in self.TOOL_WORKER_MAP.values()
                if worker == "security-worker"
            ),
        }

        return summary
