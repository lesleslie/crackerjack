"""WebSocket endpoints for error heatmap visualization.

This module handles real-time error heatmap streaming for
file-based, temporal, and function-based error analysis.
"""

import asyncio
import json
import typing as t
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from crackerjack.services.monitoring.error_pattern_analyzer import (
    ErrorPatternAnalyzer,
)


def register_heatmap_websockets(
    app: FastAPI, error_analyzer: ErrorPatternAnalyzer
) -> None:
    """Register heatmap-related WebSocket endpoints."""

    @app.websocket("/ws/heatmap/errors")
    async def websocket_error_heatmap(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time error heat map streaming."""
        await _handle_error_heatmap_websocket(websocket, error_analyzer)


async def _handle_error_heatmap_websocket(
    websocket: WebSocket, error_analyzer: ErrorPatternAnalyzer
) -> None:
    """Handle error heatmap WebSocket connection."""
    await websocket.accept()

    try:
        # Analyze error patterns and send initial data
        error_patterns = error_analyzer.analyze_error_patterns(days=30)
        await _send_initial_heatmap_data(websocket, error_analyzer, error_patterns)

        # Handle client messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(message)

                await _handle_heatmap_request(websocket, error_analyzer, data)

            except TimeoutError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )


async def _send_initial_heatmap_data(
    websocket: WebSocket,
    error_analyzer: ErrorPatternAnalyzer,
    error_patterns: list[t.Any],
) -> None:
    """Send initial heatmap data to client."""
    # Send file-based heat map
    file_heatmap = error_analyzer.generate_file_error_heatmap()
    await websocket.send_text(
        json.dumps(
            {
                "type": "file_heatmap",
                "data": file_heatmap.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )

    # Send temporal heat map
    temporal_heatmap = error_analyzer.generate_temporal_heatmap()
    await websocket.send_text(
        json.dumps(
            {
                "type": "temporal_heatmap",
                "data": temporal_heatmap.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )

    # Send function-based heat map
    function_heatmap = error_analyzer.generate_function_error_heatmap()
    await websocket.send_text(
        json.dumps(
            {
                "type": "function_heatmap",
                "data": function_heatmap.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )

    # Send error patterns summary
    patterns_data = [pattern.to_dict() for pattern in error_patterns]
    await websocket.send_text(
        json.dumps(
            {
                "type": "error_patterns",
                "data": patterns_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


async def _handle_heatmap_request(
    websocket: WebSocket,
    error_analyzer: ErrorPatternAnalyzer,
    data: dict[str, t.Any],
) -> None:
    """Handle heatmap request from client."""
    if data.get("type") == "refresh_heatmap":
        await _handle_heatmap_refresh(websocket, error_analyzer, data)
    elif data.get("type") == "keepalive":
        await websocket.send_text(
            json.dumps(
                {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )


async def _handle_heatmap_refresh(
    websocket: WebSocket,
    error_analyzer: ErrorPatternAnalyzer,
    data: dict[str, t.Any],
) -> None:
    """Handle heatmap refresh request."""
    error_analyzer.analyze_error_patterns(days=data.get("days", 30))

    heatmap_type = data.get("heatmap_type", "file")

    if heatmap_type == "file":
        heatmap = error_analyzer.generate_file_error_heatmap()
    elif heatmap_type == "temporal":
        heatmap = error_analyzer.generate_temporal_heatmap(
            time_buckets=data.get("time_buckets", 24)
        )
    elif heatmap_type == "function":
        heatmap = error_analyzer.generate_function_error_heatmap()
    else:
        return

    await websocket.send_text(
        json.dumps(
            {
                "type": f"{heatmap_type}_heatmap_refresh",
                "data": heatmap.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )
