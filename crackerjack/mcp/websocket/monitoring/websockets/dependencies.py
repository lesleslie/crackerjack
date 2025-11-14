"""WebSocket endpoints for dependency analysis.

This module handles real-time dependency graph visualization
and analysis WebSocket connections.
"""

import asyncio
import json
import typing as t
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from crackerjack.services.dependency_analyzer import (
    DependencyAnalyzer,
    DependencyGraph,
)

from ..utils import _apply_graph_filters
from ..websocket_manager import MonitoringWebSocketManager


def register_dependency_websockets(
    app: FastAPI,
    ws_manager: MonitoringWebSocketManager,
    dependency_analyzer: DependencyAnalyzer,
) -> None:
    """Register dependency-related WebSocket endpoints."""

    @app.websocket("/ws/dependencies/graph")
    async def websocket_dependency_graph(websocket: WebSocket) -> None:
        """WebSocket endpoint for dependency graph data."""
        await _handle_dependency_graph_websocket(
            websocket, ws_manager, dependency_analyzer
        )


async def _handle_dependency_graph_websocket(
    websocket: WebSocket,
    ws_manager: MonitoringWebSocketManager,
    dependency_analyzer: DependencyAnalyzer,
) -> None:
    """Handle dependency graph WebSocket connection."""
    client_id = f"dependencies_{datetime.now().timestamp()}"
    await ws_manager.connect_metrics(websocket, client_id)

    try:
        # Send initial message
        await websocket.send_text(
            json.dumps(
                {
                    "type": "analysis_started",
                    "message": "Starting dependency analysis...",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Generate dependency graph
        graph = dependency_analyzer.analyze_project()

        # Send the complete graph data
        await websocket.send_text(
            json.dumps(
                {
                    "type": "graph_data",
                    "data": graph.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Listen for client requests
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(message)

                await _handle_dependency_request(
                    websocket, dependency_analyzer, graph, data
                )

            except TimeoutError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "keepalive",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


async def _handle_dependency_request(
    websocket: WebSocket,
    dependency_analyzer: DependencyAnalyzer,
    graph: DependencyGraph,
    data: dict[str, t.Any],
) -> None:
    """Handle dependency graph request."""
    if data.get("type") == "filter_request":
        filtered_graph = await _apply_graph_filters(graph, data.get("filters", {}))
        await websocket.send_text(
            json.dumps(
                {
                    "type": "filtered_graph",
                    "data": filtered_graph.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

    elif data.get("type") == "refresh_request":
        fresh_graph = dependency_analyzer.analyze_project()
        await websocket.send_text(
            json.dumps(
                {
                    "type": "graph_data",
                    "data": fresh_graph.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )
