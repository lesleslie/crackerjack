# MCP WebSocket

WebSocket server components for real-time MCP communication and job tracking.

## Components

- **`server.py`** - Main WebSocket server with Starlette integration
- **`endpoints.py`** - WebSocket endpoint handlers
- **`monitoring_endpoints.py`** - Health monitoring and status endpoints
- **`event_bridge.py`** - EventBus integration for real-time workflow updates
- **`jobs.py`** - Async job management and progress tracking
- **`websocket_handler.py`** - WebSocket connection lifecycle management
- **`app.py`** - ASGI application setup

## Features

- **Real-time Progress** - Live updates during test execution and workflow runs
- **Job Tracking** - Monitor async job status and completion
- **Event Streaming** - Workflow events broadcast to connected clients
- **Health Monitoring** - `/health` and `/metrics` endpoints for system status

## Usage

The WebSocket server runs on port 8675 when the MCP server starts:

```bash
python -m crackerjack --start-mcp-server
# WebSocket available at ws://localhost:8675/ws
```

See parent `mcp/README.md` for MCP server architecture.
