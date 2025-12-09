"""Utility functions for monitoring endpoints.

This module contains helper functions for metrics aggregation, health checks,
and data filtering.
"""

import asyncio
import typing as t
from datetime import datetime

from crackerjack.services.dependency_analyzer import DependencyGraph
from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
    SystemHealthStatus,
    TrendDirection,
    UnifiedMetrics,
)


async def get_current_metrics(
    quality_service: EnhancedQualityBaselineService, job_manager: t.Any
) -> UnifiedMetrics:
    """Get current unified metrics."""
    try:
        # Get baseline from quality service
        baseline = await quality_service.aget_baseline()
        if not baseline:
            # Return default metrics if no baseline exists
            return UnifiedMetrics(
                timestamp=datetime.now(),
                quality_score=0,
                test_coverage=0.0,
                hook_duration=0.0,
                active_jobs=len(job_manager.active_connections),
                error_count=0,
                trend_direction=TrendDirection.STABLE,
                predictions={},
            )

        # Create metrics dict from baseline
        current_metrics = {
            "coverage_percent": baseline.coverage_percent,
            "test_count": baseline.test_count,
            "test_pass_rate": baseline.test_pass_rate,
            "hook_failures": baseline.hook_failures,
            "complexity_violations": baseline.complexity_violations,
            "security_issues": baseline.security_issues,
            "type_errors": baseline.type_errors,
            "linting_issues": baseline.linting_issues,
            "hook_duration": 0.0,  # Would need to be tracked separately
        }

        unified = await asyncio.to_thread(
            quality_service.create_unified_metrics,
            current_metrics,
            len(job_manager.active_connections)
            if hasattr(job_manager, "active_connections")
            else 0,
        )
        return unified
    except Exception:
        # Fallback to basic metrics if service fails
        return UnifiedMetrics(
            timestamp=datetime.now(),
            quality_score=0,
            test_coverage=0.0,
            hook_duration=0.0,
            active_jobs=len(job_manager.active_connections)
            if hasattr(job_manager, "active_connections")
            else 0,
            error_count=0,
            trend_direction=TrendDirection.STABLE,
            predictions={},
        )


async def get_system_health_status(
    quality_service: EnhancedQualityBaselineService,
) -> SystemHealthStatus:
    """Get system health status."""
    return await asyncio.to_thread(quality_service.get_system_health)


def _filter_nodes_by_criteria(
    nodes: list[t.Any], filter_type: str | None, include_external: bool
) -> list[t.Any]:
    """Filter nodes by type and external criteria."""
    filtered = nodes

    # Filter by type if specified
    if filter_type:
        filtered = [node for node in filtered if node.type == filter_type]

    # Filter external dependencies if not included
    if not include_external:
        filtered = [
            node
            for node in filtered
            if not node.file_path or "site-packages" not in node.file_path
        ]

    return filtered


def _prioritize_and_limit_nodes(
    nodes: list[t.Any], graph: DependencyGraph, max_nodes: int
) -> list[t.Any]:
    """Prioritize nodes and limit to max count."""
    if len(nodes) <= max_nodes:
        return nodes

    def node_priority(node: t.Any) -> int:
        edge_count = sum(
            1 for edge in graph.edges if node.id in (edge.source, edge.target)
        )
        return int(node.complexity * edge_count)

    nodes.sort(key=node_priority, reverse=True)
    return nodes[:max_nodes]


def _build_filtered_clusters(
    graph: DependencyGraph, node_ids: set[str]
) -> dict[str, list[str]]:
    """Build filtered clusters containing only included nodes."""
    filtered_clusters = {}
    for cluster_name, cluster_nodes in graph.clusters.items():
        filtered_cluster_nodes = [
            node_id for node_id in cluster_nodes if node_id in node_ids
        ]
        if filtered_cluster_nodes:
            filtered_clusters[cluster_name] = filtered_cluster_nodes
    return filtered_clusters


async def _apply_graph_filters(
    graph: DependencyGraph, filters: dict[str, t.Any]
) -> DependencyGraph:
    """Apply filters to dependency graph."""
    filtered_graph = DependencyGraph(
        generated_at=graph.generated_at,
        metrics=graph.metrics.copy(),
        clusters=graph.clusters.copy(),
    )

    # Extract filter parameters
    filter_type = filters.get("type")
    max_nodes = filters.get("max_nodes", 1000)
    include_external = filters.get("include_external", False)

    # Apply filters to nodes
    candidate_nodes = list(graph.nodes.values())
    candidate_nodes = _filter_nodes_by_criteria(
        candidate_nodes, filter_type, include_external
    )
    candidate_nodes = _prioritize_and_limit_nodes(candidate_nodes, graph, max_nodes)

    # Build filtered graph
    node_ids = {node.id for node in candidate_nodes}
    for node in candidate_nodes:
        filtered_graph.nodes[node.id] = node

    # Add edges between filtered nodes
    for edge in graph.edges:
        if edge.source in node_ids and edge.target in node_ids:
            filtered_graph.edges.append(edge)

    # Update clusters
    filtered_graph.clusters = _build_filtered_clusters(graph, node_ids)

    return filtered_graph
