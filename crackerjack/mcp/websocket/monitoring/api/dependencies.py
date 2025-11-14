"""REST API endpoints for dependency analysis.

This module provides HTTP endpoints for dependency graph visualization,
metrics, clustering, and analysis triggers.
"""

from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from crackerjack.services.dependency_analyzer import (
    DependencyAnalyzer,
    DependencyGraph,
)

from ..utils import _apply_graph_filters


def register_dependency_api_endpoints(
    app: FastAPI, dependency_analyzer: DependencyAnalyzer
) -> None:
    """Register dependency-related REST API endpoints."""

    @app.get("/api/dependencies/graph")
    async def get_dependency_graph(
        filter_type: str = None,
        max_nodes: int = 1000,
        include_external: bool = False,
    ) -> None:
        """Get dependency graph data."""
        return await _handle_dependency_graph_request(
            dependency_analyzer, filter_type, max_nodes, include_external
        )

    @app.get("/api/dependencies/metrics")
    async def get_dependency_metrics() -> None:
        """Get dependency graph metrics."""
        return await _handle_dependency_metrics_request(dependency_analyzer)

    @app.get("/api/dependencies/clusters")
    async def get_dependency_clusters() -> None:
        """Get dependency graph clusters."""
        return await _handle_dependency_clusters_request(dependency_analyzer)

    @app.post("/api/dependencies/analyze")
    async def trigger_dependency_analysis(request: dict) -> None:
        """Trigger fresh dependency analysis."""
        return await _handle_dependency_analysis_request(dependency_analyzer, request)


async def _handle_dependency_graph_request(
    dependency_analyzer: DependencyAnalyzer,
    filter_type: str | None,
    max_nodes: int,
    include_external: bool,
) -> JSONResponse:
    """Handle dependency graph API request."""
    try:
        graph = dependency_analyzer.analyze_project()

        # Apply filters if requested
        if filter_type or max_nodes < len(graph.nodes):
            filters = {
                "type": filter_type,
                "max_nodes": max_nodes,
                "include_external": include_external,
            }
            graph = await _apply_graph_filters(graph, filters)

        return JSONResponse(
            {
                "status": "success",
                "data": graph.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_dependency_metrics_request(
    dependency_analyzer: DependencyAnalyzer,
) -> JSONResponse:
    """Handle dependency metrics API request."""
    try:
        graph = dependency_analyzer.analyze_project()

        return JSONResponse(
            {
                "status": "success",
                "data": graph.metrics,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_dependency_clusters_request(
    dependency_analyzer: DependencyAnalyzer,
) -> JSONResponse:
    """Handle dependency clusters API request."""
    try:
        graph = dependency_analyzer.analyze_project()

        return JSONResponse(
            {
                "status": "success",
                "data": graph.clusters,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_dependency_analysis_request(
    dependency_analyzer: DependencyAnalyzer, request: dict
) -> JSONResponse:
    """Handle dependency analysis trigger API request."""
    try:
        # Reset analyzer for fresh analysis
        dependency_analyzer.dependency_graph = DependencyGraph()
        graph = dependency_analyzer.analyze_project()

        return JSONResponse(
            {
                "status": "success",
                "message": "Dependency analysis completed",
                "data": {
                    "nodes": len(graph.nodes),
                    "edges": len(graph.edges),
                    "clusters": len(graph.clusters),
                    "metrics": graph.metrics,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
