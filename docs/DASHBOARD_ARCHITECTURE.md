# Dashboard Architecture Guide

This document defines the architectural patterns and design principles for Crackerjack's Web and TUI monitoring dashboards.

## Overview

Crackerjack implements a **Hub-and-Spoke** architecture for unified monitoring across multiple interfaces:

- **Web Dashboard**: Browser-based interface with embedded external tools
- **TUI Monitors**: Rich-based terminal interfaces with tabbed navigation
- **Data Hub**: Centralized WebSocket server and API gateway

## Core Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Unified Monitoring Hub                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Web Dashboard Layer (Port 8676)                       │
│  ├── FastAPI Server                                     │
│  ├── Static Assets (HTML, CSS, JS)                      │
│  ├── Embedded Dashboards (iframes)                      │
│  │   ├── Snifly Claude Code Dashboard                   │
│  │   ├── MkDocs Material Documentation                  │
│  │   ├── Prometheus/Grafana Metrics                     │
│  │   └── Session-mgmt-mcp Interface                     │
│  ├── API Gateway                                        │
│  └── WebSocket Client (connects to 8675)               │
│                                                         │
│  Data Layer (Port 8675)                                │
│  ├── WebSocket Server (existing)                        │
│  ├── Job Progress Tracking                              │
│  ├── Metrics Collection                                 │
│  ├── Event Streaming                                    │
│  └── State Management                                   │
│                                                         │
│  TUI Layer (Rich-based)                                │
│  ├── Unified Monitor (Layout-based tabs)               │
│  │   ├── Progress Monitor                               │
│  │   ├── Enhanced Monitor                               │
│  │   ├── Claude Usage Monitor (absorbed)               │
│  │   └── Session-mgmt Dashboard                         │
│  ├── Shared Rich Components                             │
│  └── WebSocket Client (connects to 8675)               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Single Source of Truth

- **Data Hub** (port 8675) maintains canonical state
- All interfaces consume data from the hub
- No direct data manipulation in UI layers

### 2. Technology Consistency

- **Web**: FastAPI + WebSocket + HTML/CSS/JS
- **TUI**: Pure Rich (no Textual) for simplicity
- **Data**: JSON over WebSocket for real-time updates

### 3. Modular Integration

- Embedded dashboards via iframes
- Plugin architecture for new monitors
- Clean separation between core and extensions

### 4. Performance Optimized

- WebSocket for real-time updates
- Lazy loading for dashboard components
- Efficient Rich rendering for TUI

## Web Dashboard Architecture

### FastAPI Application Structure

```python
# crackerjack/web/app.py
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Crackerjack Dashboard")
templates = Jinja2Templates(directory="web/templates")

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="web/static"), name="static")


# API routes
@app.get("/api/status")
async def get_system_status():
    """Get overall system health and status."""
    return await hub_client.get_status()


@app.get("/api/jobs")
async def list_jobs():
    """List all active and recent jobs."""
    return await hub_client.get_jobs()


@app.get("/api/dashboards")
async def list_dashboards():
    """List available embedded dashboards."""
    return EMBEDDED_DASHBOARDS


# WebSocket proxy to data hub
@app.websocket("/ws")
async def websocket_proxy(websocket: WebSocket):
    """Proxy WebSocket connections to data hub."""
    await websocket.accept()
    async with websockets.connect("ws://localhost:8675") as hub_ws:
        await proxy_messages(websocket, hub_ws)
```

### Embedded Dashboard Configuration

```python
# crackerjack/web/config.py
EMBEDDED_DASHBOARDS = {
    "snifly": {
        "name": "Snifly Claude Code Dashboard",
        "url": "http://localhost:3000",
        "category": "development",
        "description": "Claude Code usage monitoring and analytics",
        "health_check": "/health",
        "iframe_options": {
            "sandbox": "allow-same-origin allow-scripts",
            "loading": "lazy",
        },
    },
    "docs": {
        "name": "Project Documentation",
        "url": "http://localhost:8000",
        "category": "documentation",
        "description": "MkDocs Material documentation site",
        "health_check": "/",
        "iframe_options": {
            "sandbox": "allow-same-origin allow-scripts allow-popups",
            "loading": "lazy",
        },
    },
    "prometheus": {
        "name": "System Metrics",
        "url": "http://localhost:9090",
        "category": "monitoring",
        "description": "Prometheus metrics and Grafana dashboards",
        "health_check": "/api/v1/status/config",
        "iframe_options": {
            "sandbox": "allow-same-origin allow-scripts",
            "loading": "lazy",
        },
    },
    "session-mgmt": {
        "name": "Session Management",
        "url": "http://localhost:8677",  # Future session-mgmt web interface
        "category": "ai",
        "description": "AI conversation memory and context management",
        "health_check": "/health",
        "iframe_options": {
            "sandbox": "allow-same-origin allow-scripts",
            "loading": "lazy",
        },
    },
}
```

### Frontend Architecture

```html
<!-- web/templates/dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Crackerjack Dashboard</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/css/dashboard.css') }}">
</head>
<body>
    <nav id="dashboard-nav">
        <!-- Navigation tabs for different views -->
    </nav>

    <main id="dashboard-content">
        <div id="overview-panel">
            <!-- System status, active jobs, quick stats -->
        </div>

        <div id="embedded-dashboards">
            <!-- Dynamic iframe containers -->
        </div>

        <div id="live-logs">
            <!-- WebSocket-powered live log stream -->
        </div>
    </main>

    <script src="{{ url_for('static', path='/js/websocket.js') }}"></script>
    <script src="{{ url_for('static', path='/js/dashboard.js') }}"></script>
</body>
</html>
```

```javascript
// web/static/js/websocket.js
class DashboardWebSocket {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectInterval = 5000;
        this.listeners = new Map();
    }

    connect() {
        this.ws = new WebSocket(this.url);

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.dispatch(data.type, data.payload);
        };

        this.ws.onclose = () => {
            setTimeout(() => this.connect(), this.reconnectInterval);
        };
    }

    subscribe(eventType, callback) {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, []);
        }
        this.listeners.get(eventType).push(callback);
    }

    dispatch(eventType, payload) {
        const callbacks = this.listeners.get(eventType) || [];
        callbacks.forEach(callback => callback(payload));
    }
}
```

## TUI Architecture

### Unified Rich-Based Interface

```python
# crackerjack/monitors/unified_monitor.py
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.console import Console


class UnifiedMonitor:
    """Multi-tab Rich-based monitoring using Layout."""

    def __init__(self):
        self.console = Console()
        self.monitors = {
            "progress": ProgressMonitor(),
            "enhanced": EnhancedMonitor(),
            "claude": ClaudeUsageMonitor(),  # Absorbed from external project
            "session": SessionMgmtMonitor(),
        }
        self.current_tab = "progress"
        self.websocket_client = WebSocketClient("ws://localhost:8675")

    def create_layout(self) -> Layout:
        """Create tabbed interface with Rich Layout."""
        layout = Layout()

        layout.split_column(
            Layout(self.create_header(), size=3, name="header"),
            Layout(self.create_tabs(), size=3, name="tabs"),
            Layout(self.monitors[self.current_tab].render(), name="content"),
            Layout(self.create_footer(), size=3, name="footer"),
        )

        return layout

    def create_header(self) -> Panel:
        """Create header with system status."""
        status_table = Table(show_header=False, box=None)
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="green")

        # Get real-time data from WebSocket
        system_status = self.websocket_client.get_status()
        status_table.add_row("Active Jobs", str(system_status.get("active_jobs", 0)))
        status_table.add_row(
            "System Load", f"{system_status.get('cpu_percent', 0):.1f}%"
        )
        status_table.add_row("Memory", f"{system_status.get('memory_percent', 0):.1f}%")

        return Panel(
            status_table, title="🚀 Crackerjack Monitor", border_style="bright_blue"
        )

    def create_tabs(self) -> Panel:
        """Create tab navigation."""
        tab_content = ""
        for key, monitor in self.monitors.items():
            if key == self.current_tab:
                tab_content += f"[reverse] {monitor.display_name} [/reverse] "
            else:
                tab_content += f" {monitor.display_name} "

        return Panel(
            tab_content, title="Navigation (← → to switch)", border_style="dim"
        )

    def create_footer(self) -> Panel:
        """Create footer with controls."""
        controls = "q: Quit | ←→: Switch Tabs | r: Refresh | h: Help | e: Export"
        return Panel(controls, border_style="dim")

    async def run(self):
        """Run the unified monitor with keyboard controls."""
        with Live(self.create_layout(), refresh_per_second=4, screen=True) as live:
            await self.websocket_client.connect()

            while True:
                try:
                    # Handle keyboard input
                    key = await self.get_key_async()

                    if key == "q":
                        break
                    elif key == "left":
                        self.switch_tab(-1)
                    elif key == "right":
                        self.switch_tab(1)
                    elif key == "r":
                        await self.refresh_data()

                    # Update display
                    live.update(self.create_layout())

                except KeyboardInterrupt:
                    break

            await self.websocket_client.disconnect()
```

### Monitor Plugin Architecture

```python
# crackerjack/monitors/base.py
from abc import ABC, abstractmethod
from rich.console import RenderableType


class BaseMonitor(ABC):
    """Base class for all monitor types."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Display name for tab navigation."""
        pass

    @abstractmethod
    def render(self) -> RenderableType:
        """Render monitor content."""
        pass

    @abstractmethod
    async def update_data(self, websocket_data: dict) -> None:
        """Update with fresh data from WebSocket."""
        pass

    def handle_keypress(self, key: str) -> bool:
        """Handle monitor-specific keypresses. Return True if handled."""
        return False
```

```python
# crackerjack/monitors/claude_usage.py (absorbed functionality)
class ClaudeUsageMonitor(BaseMonitor):
    """Monitor Claude Code usage and token consumption."""

    @property
    def display_name(self) -> str:
        return "📊 Claude Usage"

    def render(self) -> Panel:
        """Render Claude usage statistics."""
        usage_table = Table(title="Claude Code Usage")
        usage_table.add_column("Metric", style="cyan")
        usage_table.add_column("Today", style="green")
        usage_table.add_column("This Week", style="yellow")
        usage_table.add_column("This Month", style="red")

        # Data from absorbed Claude Usage Monitor
        usage_table.add_row("Requests", "127", "856", "3,241")
        usage_table.add_row("Input Tokens", "45.2K", "312.7K", "1.2M")
        usage_table.add_row("Output Tokens", "23.1K", "167.3K", "634.8K")
        usage_table.add_row("Cost ($)", "$2.34", "$18.67", "$87.23")

        return Panel(usage_table, border_style="bright_magenta")

    async def update_data(self, websocket_data: dict) -> None:
        """Update with usage data."""
        if "claude_usage" in websocket_data:
            self.usage_data = websocket_data["claude_usage"]
```

## Data Flow Architecture

### WebSocket Message Protocol

```python
# crackerjack/websocket/protocol.py
from typing import Literal, Union
from pydantic import BaseModel


class WebSocketMessage(BaseModel):
    """Base WebSocket message structure."""

    type: str
    timestamp: float
    payload: dict


class JobUpdateMessage(WebSocketMessage):
    """Job progress update message."""

    type: Literal["job_update"]
    payload: dict  # JobMetrics data


class SystemStatusMessage(WebSocketMessage):
    """System status update message."""

    type: Literal["system_status"]
    payload: dict  # SystemStatus data


class ClaudeUsageMessage(WebSocketMessage):
    """Claude usage statistics message."""

    type: Literal["claude_usage"]
    payload: dict  # Usage metrics


# Message routing
MESSAGE_TYPES = {
    "job_update": JobUpdateMessage,
    "system_status": SystemStatusMessage,
    "claude_usage": ClaudeUsageMessage,
}
```

### Data Hub Integration

```python
# crackerjack/websocket/hub.py
class MonitoringDataHub:
    """Central data hub for all monitoring interfaces."""

    def __init__(self):
        self.websocket_server = WebSocketServer(port=8675)
        self.collectors = {
            "jobs": JobDataCollector(),
            "system": SystemDataCollector(),
            "claude": ClaudeUsageCollector(),
        }
        self.connected_clients = set()

    async def start(self):
        """Start the data hub."""
        # Start all data collectors
        for collector in self.collectors.values():
            await collector.start()

        # Start WebSocket server
        await self.websocket_server.start()

        # Start periodic broadcasts
        self.broadcast_task = asyncio.create_task(self.broadcast_loop())

    async def broadcast_loop(self):
        """Periodically broadcast updates to all clients."""
        while True:
            try:
                # Collect latest data
                data = {}
                for name, collector in self.collectors.items():
                    data[name] = await collector.get_latest()

                # Broadcast to all connected clients
                message = {
                    "type": "batch_update",
                    "timestamp": time.time(),
                    "payload": data,
                }

                await self.broadcast(message)
                await asyncio.sleep(1)  # 1 second updates

            except Exception as e:
                logger.error(f"Broadcast error: {e}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        if not self.connected_clients:
            return

        message_json = json.dumps(message)
        disconnected = set()

        for client in self.connected_clients:
            try:
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)

        # Clean up disconnected clients
        self.connected_clients -= disconnected
```

## CLI Integration

### New Command Flags

```python
# crackerjack/__main__.py additions
@click.option(
    "--unified-monitor",
    is_flag=True,
    help="Start unified TUI monitor with tabbed interface",
)
@click.option("--web-dashboard", is_flag=True, help="Start web dashboard on port 8676")
@click.option("--claude-usage", is_flag=True, help="Show Claude Code usage monitor")
@click.option(
    "--dashboard-port", default=8676, help="Port for web dashboard (default: 8676)"
)
def main(unified_monitor, web_dashboard, claude_usage, dashboard_port, **kwargs):
    """Enhanced main function with dashboard options."""

    if unified_monitor:
        from crackerjack.monitors.unified_monitor import UnifiedMonitor

        monitor = UnifiedMonitor()
        asyncio.run(monitor.run())
        return

    if web_dashboard:
        from crackerjack.web.app import app
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=dashboard_port)
        return

    if claude_usage:
        from crackerjack.monitors.claude_usage import ClaudeUsageMonitor

        monitor = ClaudeUsageMonitor()
        asyncio.run(monitor.run_standalone())
        return

    # Existing functionality continues...
```

## Security Considerations

### Web Dashboard Security

```python
# crackerjack/web/security.py
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware


def configure_security(app: FastAPI):
    """Configure security middleware."""

    # CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Trusted hosts
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "*.localhost"]
    )


# Iframe sandbox restrictions
IFRAME_SANDBOX_POLICIES = {
    "default": "allow-same-origin allow-scripts",
    "docs": "allow-same-origin allow-scripts allow-popups allow-forms",
    "metrics": "allow-same-origin allow-scripts",
}
```

### WebSocket Authentication

```python
# crackerjack/websocket/auth.py
import hmac
import hashlib
import time


class WebSocketAuth:
    """Simple HMAC-based WebSocket authentication."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()

    def generate_token(self, client_id: str) -> str:
        """Generate authentication token."""
        timestamp = str(int(time.time()))
        message = f"{client_id}:{timestamp}"
        signature = hmac.new(
            self.secret_key, message.encode(), hashlib.sha256
        ).hexdigest()
        return f"{message}:{signature}"

    def verify_token(self, token: str) -> bool:
        """Verify authentication token."""
        try:
            client_id, timestamp, signature = token.split(":")
            message = f"{client_id}:{timestamp}"
            expected = hmac.new(
                self.secret_key, message.encode(), hashlib.sha256
            ).hexdigest()

            # Check signature and timestamp (5 minute window)
            return (
                hmac.compare_digest(signature, expected)
                and int(time.time()) - int(timestamp) < 300
            )
        except (ValueError, TypeError):
            return False
```

## Performance Optimization

### Efficient Data Streaming

```python
# crackerjack/websocket/streaming.py
class EfficientStreamer:
    """Optimized data streaming for monitoring."""

    def __init__(self):
        self.data_cache = {}
        self.dirty_flags = set()
        self.compression_enabled = True

    async def stream_update(self, data_type: str, data: dict):
        """Stream only changed data."""

        # Check if data actually changed
        cache_key = f"{data_type}_hash"
        current_hash = hash(str(data))

        if self.data_cache.get(cache_key) == current_hash:
            return  # No change, skip streaming

        self.data_cache[cache_key] = current_hash

        # Compress large payloads
        payload = data
        if self.compression_enabled and len(str(data)) > 1024:
            payload = await self.compress_data(data)

        message = {
            "type": f"{data_type}_update",
            "timestamp": time.time(),
            "payload": payload,
            "compressed": self.compression_enabled,
        }

        await self.broadcast(message)

    async def compress_data(self, data: dict) -> dict:
        """Compress large data payloads."""
        import gzip
        import base64

        json_str = json.dumps(data)
        compressed = gzip.compress(json_str.encode())
        encoded = base64.b64encode(compressed).decode()

        return {
            "compressed": True,
            "data": encoded,
            "original_size": len(json_str),
            "compressed_size": len(encoded),
        }
```

## Testing Strategy

### Component Testing

```python
# tests/test_dashboard_architecture.py
import pytest
from crackerjack.monitors.unified_monitor import UnifiedMonitor
from crackerjack.web.app import app
from fastapi.testclient import TestClient


class TestUnifiedMonitor:
    """Test unified TUI monitor."""

    def test_tab_switching(self):
        """Test tab navigation."""
        monitor = UnifiedMonitor()

        assert monitor.current_tab == "progress"
        monitor.switch_tab(1)
        assert monitor.current_tab == "enhanced"

    def test_layout_creation(self):
        """Test Rich layout generation."""
        monitor = UnifiedMonitor()
        layout = monitor.create_layout()

        assert layout is not None
        assert "header" in layout._named_children
        assert "content" in layout._named_children


class TestWebDashboard:
    """Test web dashboard API."""

    def test_status_endpoint(self):
        """Test system status API."""
        client = TestClient(app)
        response = client.get("/api/status")

        assert response.status_code == 200
        assert "active_jobs" in response.json()

    def test_dashboard_list(self):
        """Test dashboard configuration."""
        client = TestClient(app)
        response = client.get("/api/dashboards")

        assert response.status_code == 200
        dashboards = response.json()
        assert "snifly" in dashboards
        assert "docs" in dashboards
```

This architecture provides a solid foundation for building comprehensive Web and TUI monitoring dashboards while maintaining simplicity and performance.
