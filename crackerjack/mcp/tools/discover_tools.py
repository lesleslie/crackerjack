from __future__ import annotations

import logging
import typing as t

logger = logging.getLogger(__name__)


TOOL_REGISTRY: dict[str, dict[str, str]] = {
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
    "skill_coverage_report": {
        "group": "skill_coverage",
        "description": "Calls mcp__session-buddy__distilled_skill_health (Contract 5.4)",
    },
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
    "discover_tools": {
        "group": "discover_tools",
        "description": "List all Crackerjack MCP tools with descriptions and groups",
    },
}


DEFERRED_TOOLS: dict[str, str] = {
    "create_workspace": "Phase 3 deferred (Contract 5.7)",
    "list_workspaces": "Phase 3 deferred (Contract 5.7)",
    "get_workspace_info": "Phase 3 deferred (Contract 5.7)",
    "remove_workspace": "Phase 3 deferred (Contract 5.7)",
}


def register_discover_tools(mcp_app: t.Any) -> None:

    @mcp_app.tool()
    async def discover_tools(query: str | None = None) -> dict[str, t.Any]:

        all_tools: list[dict[str, str]] = [
            {"name": name, "group": meta["group"], "description": meta["description"]}
            for name, meta in sorted(TOOL_REGISTRY.items())
        ]

        matched = all_tools
        if query:
            q = query.lower()
            matched = [
                t
                for t in all_tools
                if q in t["name"].lower() or q in t["description"].lower()
            ]

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
                {"name": g, "tool_count": c} for g, c in sorted(group_summary.items())
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
