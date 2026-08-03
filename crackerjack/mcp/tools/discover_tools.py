"""Discover_tools meta-tool for the Crackerjack MCP server.

Mirrors the ``_register_discovery_tool`` pattern from
``akosha/mcp/tools/__init__.py`` (the only other Bodai component with a
``discover_tools`` meta-tool). Crackerjack has no profile gate, so the
Akosha distinction between ``loaded`` and ``not_loaded`` is replaced
with a flat list of every registered tool.

This addresses **Contract 5.5** in
``docs/architecture/MEMORY_ARCHITECTURE.md``: ``discover_tools`` meta-tool
was missing from Crackerjack. Adding it surfaces the orphan tools
discovered by ``bodai/docs/memory/TOOL_ALIAS_INVENTORY.md`` (356 of 371
MCP tools registered ecosystem-wide had no slash-command consumer).

Data source
-----------
``TOOL_REGISTRY`` mirrors ``docs/MCP_TOOLS_SPECIFICATION.md`` Sections
1-9. If you update the spec doc, update ``TOOL_REGISTRY`` here in the
same commit. ``tests/unit/mcp/test_mcp_tool_drift.py`` enforces this
contract by checking ``server_core.py`` calls every function in this
module's ``REGISTERED_BY_THIS_MODULE`` list.
"""

from __future__ import annotations

import logging
import typing as t

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool registry — mirrors docs/MCP_TOOLS_SPECIFICATION.md Sections 1-9
# ---------------------------------------------------------------------------
#
# Shape: tool_name -> {"group": <register_module>, "description": <one-line>}
# Intentionally a flat dict so discover_tools can scan/query without
# walking module imports.

TOOL_REGISTRY: dict[str, dict[str, str]] = {
    # Section 1 — Always-on core tools
    "execute_crackerjack": {
        "group": "execution_tools",
        "description": "Full crackerjack run lifecycle (config → hooks → tests → coverage → commit)",
    },
    "run_crackerjack_stage": {
        "group": "core_tools",
        "description": "Run one stage only (fast|comprehensive|tests|cleaning|init)",
    },
    "init_crackerjack": {
        "group": "execution_tools",
        "description": "First-time setup: writes pyproject.toml, CLAUDE.md, example.mcp.json, settings/local.yaml",
    },
    "smart_error_analysis": {
        "group": "execution_tools",
        "description": "AI-prioritized fix suggestions from accumulated error patterns",
    },
    "analyze_errors": {
        "group": "execution_tools",
        "description": "Extract error patterns from hook output; mark auto-fixable successes (via execution_tools.analyze_errors_with_caching)",
    },
    "clean_crackerjack": {
        "group": "utility_tools",
        "description": "Clean up logs, coverage files, progress dir",
    },
    "config_crackerjack": {
        "group": "utility_tools",
        "description": "Read-only dump of CrackerjackSettings.model_dump()",
    },
    "analyze_crackerjack": {
        "group": "utility_tools",
        "description": "Self-analysis (MOCK: returns status=mock_success per Contract 5.6)",
    },
    "validate_claude_md": {
        "group": "utility_tools",
        "description": "Validate CLAUDE.md; with update=true may rewrite CLAUDE.md",
    },
    "crackerjack_doc_frontmatter_validate": {
        "group": "doc_tools",
        "description": "Validate frontmatter across the package; optional store arg persists results",
    },
    "publish_to_eventbridge": {
        "group": "eventbridge_tools",
        "description": "Publish to Bodai EventBridge when enabled=true in crackerjack.yaml (default false)",
    },
    "get_job_progress": {
        "group": "progress_tools",
        "description": "Read progress_dir/job-<id>.json for a running job",
    },
    "session_management": {
        "group": "progress_tools",
        "description": "start/save_checkpoint/complete/reset session state (writes current_session.json + checkpoints)",
    },
    # Section 2 — Skill / coverage tools
    "list_skills": {
        "group": "skill_tools",
        "description": "List all known skills (agent/mcp/hybrid)",
    },
    "get_skill_info": {
        "group": "skill_tools",
        "description": "Detail for one skill by id",
    },
    "search_skills": {
        "group": "skill_tools",
        "description": "Free-text search across skill name/description/tags",
    },
    "get_skills_for_issue": {
        "group": "skill_tools",
        "description": "Map issue_type -> skill set",
    },
    "get_skill_statistics": {
        "group": "skill_tools",
        "description": "Aggregate counts per registry",
    },
    "execute_skill": {
        "group": "skill_tools",
        "description": "Run a hybrid skill (may delegate to agents and write fix_attempts)",
    },
    "find_best_skill": {
        "group": "skill_tools",
        "description": "Pick the top-skill for an issue_type by can_handle confidence",
    },
    "skill_coverage_report": {
        "group": "skill_coverage",
        "description": "Calls mcp__session-buddy__distilled_skill_health (Contract 5.4)",
    },
    # Section 3 — Semantic / git-semantic tools
    "index_file_semantic": {
        "group": "semantic_tools",
        "description": "Embed a file into the semantic_index.db",
    },
    "remove_file_from_semantic_index": {
        "group": "semantic_tools",
        "description": "Delete rows for a file from semantic_index.db",
    },
    "search_semantic": {
        "group": "semantic_tools",
        "description": "Vector search over semantic_index.db (TF-IDF or sentence-transformers)",
    },
    "get_semantic_stats": {
        "group": "semantic_tools",
        "description": "Semantic index coverage stats",
    },
    "get_embeddings": {
        "group": "semantic_tools",
        "description": "One-off embedding generation (no DB write)",
    },
    "calculate_similarity_semantic": {
        "group": "semantic_tools",
        "description": "Cosine similarity between two embeddings",
    },
    "index_git_history": {
        "group": "git_semantic_tools",
        "description": "Index git events into semantic_index.db",
    },
    "search_git_history": {
        "group": "git_semantic_tools",
        "description": "Semantic search over commit messages + diffs",
    },
    "find_workflow_patterns": {
        "group": "git_semantic_tools",
        "description": "Recurring patterns across commits",
    },
    "recommend_git_practices": {
        "group": "git_semantic_tools",
        "description": "Coaching recommendations grouped by focus_area",
    },
    # Section 4 — Self-improvement / monitoring
    "agent_performance_analysis": {
        "group": "intelligence_tools",
        "description": "Per-agent effectiveness rollup",
    },
    "execute_smart_task": {
        "group": "intelligence_tools",
        "description": "Find the best agent for a task and run it (writes fix_attempts)",
    },
    "get_comprehensive_status": {
        "group": "monitoring_tools",
        "description": "Full status snapshot for dashboards",
    },
    "get_filtered_status": {
        "group": "monitoring_tools",
        "description": "Filtered status (e.g., components='jobs')",
    },
    "get_server_stats": {
        "group": "monitoring_tools",
        "description": "Minimal liveness snapshot",
    },
    "get_stage_status": {
        "group": "monitoring_tools",
        "description": "Fine-grained stage status",
    },
    "get_next_action": {
        "group": "monitoring_tools",
        "description": "State-machine next-step hint",
    },
    "query_local_traces": {
        "group": "otel_tools",
        "description": "Proxy to mcp__akosha__query_local_traces",
    },
    "get_cross_project_git_dashboard": {
        "group": "mahavishnu_tools",
        "description": "Cross-repo velocity summary",
    },
    "get_repository_health": {
        "group": "mahavishnu_tools",
        "description": "Per-repo health score (joins branch + merge metrics)",
    },
    "get_velocity_comparison": {
        "group": "mahavishnu_tools",
        "description": "Period-over-period delta",
    },
    "get_cross_project_patterns": {
        "group": "mahavishnu_tools",
        "description": "Recurring patterns across repos",
    },
    # Section 5 — Code search / IDE
    "search_code": {
        "group": "pycharm_tools",
        "description": "Cross-IDE regex search via PyCharm MCP (returns 'not connected' if PyCharm down)",
    },
    "get_ide_diagnostics": {
        "group": "pycharm_tools",
        "description": "Inline IDE problem pull via PyCharm MCP",
    },
    "get_symbol_info": {
        "group": "pycharm_tools",
        "description": "STUB per Contract 5.9: returns status=not_implemented",
    },
    "find_usages": {
        "group": "pycharm_tools",
        "description": "STUB per Contract 5.9: returns status=not_implemented",
    },
    "pycharm_health": {
        "group": "pycharm_tools",
        "description": "PyCharm MCP connection check (healthy|degraded)",
    },
    # Meta — discover_tools itself
    "discover_tools": {
        "group": "discover_tools",
        "description": "List all Crackerjack MCP tools with descriptions and groups",
    },
}


# Tools that are NOT registered (intentionally deferred per Contract 5.7).
# Listed in the response so consumers know what exists but is currently
# unreachable.
DEFERRED_TOOLS: dict[str, str] = {
    "create_workspace": "Phase 3 deferred (Contract 5.7)",
    "list_workspaces": "Phase 3 deferred (Contract 5.7)",
    "get_workspace_info": "Phase 3 deferred (Contract 5.7)",
    "remove_workspace": "Phase 3 deferred (Contract 5.7)",
}


def register_discover_tools(mcp_app: t.Any) -> None:
    """Register the ``discover_tools`` meta-tool.

    Always registered (Crackerjack has no profile gate). Returns the
    full tool registry plus the deferred set so consumers can plan
    around what's available now vs. what Phase 3 will unlock.
    """

    @mcp_app.tool()
    async def discover_tools(query: str | None = None) -> dict[str, t.Any]:
        """Search for available Crackerjack tools by name or capability.

        With no ``query`` argument, returns every registered tool with
        its group and one-line description, plus the deferred set so
        callers know what is intentionally absent. With ``query``,
        filters by substring match against name or description
        (case-insensitive).
        """
        # Build response
        all_tools: list[dict[str, str]] = [
            {"name": name, "group": meta["group"], "description": meta["description"]}
            for name, meta in sorted(TOOL_REGISTRY.items())
        ]

        # Query filter
        matched = all_tools
        if query:
            q = query.lower()
            matched = [
                t
                for t in all_tools
                if q in t["name"].lower() or q in t["description"].lower()
            ]

        # Group summary
        group_summary: dict[str, int] = {}
        for meta in TOOL_REGISTRY.values():
            group_summary[meta["group"]] = group_summary.get(meta["group"], 0) + 1

        deferred = [
            {"name": name, "reason": reason}
            for name, reason in sorted(DEFERRED_TOOLS.items())
        ]

        return {
            "status": "success",
            "query": query,
            "matched": matched,
            "matched_count": len(matched),
            "total_count": len(TOOL_REGISTRY),
            "groups": [
                {"name": g, "tool_count": c}
                for g, c in sorted(group_summary.items())
            ],
            "deferred": deferred,
            "deferred_count": len(deferred),
            "hint": "Cross-reference docs/MCP_TOOLS_SPECIFICATION.md for full signatures and contracts.",
        }


__all__ = [
    "DEFERRED_TOOLS",
    "TOOL_REGISTRY",
    "register_discover_tools",
]