import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .jobs import JobManager


def _build_job_list(job_manager: JobManager, progress_dir: Path) -> list[dict]:
    """Build list of jobs from progress files."""
    jobs = []
    if not progress_dir.exists():
        return jobs
    for progress_file in progress_dir.glob("job-*.json"):
        job_id = job_manager.extract_job_id_from_file(progress_file)
        if job_id and job_manager.validate_job_id(job_id):
            try:
                progress_data = json.loads(progress_file.read_text())
                jobs.append(
                    {
                        "job_id": job_id,
                        "status": progress_data.get("status", "unknown"),
                        "message": progress_data.get("message", ""),
                        "progress": progress_data.get("overall_progress", 0),
                    },
                )
            except (json.JSONDecodeError, OSError):
                continue
    jobs.sort(key=lambda j: j.get("job_id", ""), reverse=True)
    return jobs


def _build_status_response(job_manager: JobManager, jobs: list[dict]) -> dict:
    """Build the status response dictionary."""
    return {
        "status": "running",
        "message": "Crackerjack WebSocket Server",
        "active_connections": len(job_manager.active_connections),
        "jobs": jobs[:10],
        "websocket_url": "ws://localhost:8675/ws/progress/{job_id}",
        "endpoints": {
            "status": "/",
            "latest_job": "/latest",
            "job_monitor": "/monitor/{job_id}",
            "test": "/test",
            "websocket": "/ws/progress/{job_id}",
        },
    }


def _get_test_html() -> str:
    """Generate HTML content for test page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Test Page</title>
        <meta charset="UTF-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }
            .test-section {
                margin: 20px 0;
                padding: 15px;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            button {
                background: #007acc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                margin: 5px;
            }
            button:hover { background: #005999; }
            input[type="text"] {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 3px;
                margin: 5px;
                width: 200px;
            }
            .status {
                margin: 10px 0;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
            .info { background: #d1ecf1; color: #0c5460; }
            #log {
                background: #1e1e1e;
                color: #ffffff;
                padding: 15px;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                max-height: 300px;
                overflow-y: auto;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧪 WebSocket Test Page</h1>
            <p>Test WebSocket connectivity and server functionality</p>

            <div class="test-section">
                <h3>1. Server Status</h3>
                <button onclick="checkServerStatus()">Check Status</button>
                <div id="serverStatus"></div>
            </div>

            <div class="test-section">
                <h3>2. Latest Job</h3>
                <button onclick="checkLatestJob()">Get Latest Job</button>
                <div id="latestJob"></div>
            </div>

            <div class="test-section">
                <h3>3. WebSocket Test</h3>
                <input type="text" id="testJobId" placeholder="Enter job ID (e.g., test-123)" value="test-123">
                <button onclick="testWebSocket()">Test WebSocket</button>
                <button onclick="disconnectWebSocket()">Disconnect</button>
                <div id="wsStatus"></div>
            </div>

            <div id="log">
                <div>Ready to test...</div>
            </div>
        </div>

        <script>
            let testWs = null;
            const log = document.getElementById('log');

            function addLog(message, type = 'info') {
                const timestamp = new Date().toLocaleTimeString();
                const div = document.createElement('div');
                div.textContent = `[${timestamp}] ${message}`;
                if (type === 'error') div.style.color = '#ff6b6b';
                if (type === 'success') div.style.color = '#51cf66';
                log.appendChild(div);
                log.scrollTop = log.scrollHeight;
            }

            function showStatus(elementId, message, type = 'info') {
                const element = document.getElementById(elementId);
                element.innerHTML = `<div class="status ${type}">${message}</div>`;
            }

            async function checkServerStatus() {
                try {
                    addLog('Checking server status...');
                    const response = await fetch('/');
                    const data = await response.json();

                    showStatus('serverStatus',
                        `Status: ${data.status}<br>` +
                        `Active connections: ${data.active_connections}<br>` +
                        `Jobs: ${data.jobs?.length || 0}`, 'success');
                    addLog('Server status retrieved successfully', 'success');
                } catch (error) {
                    showStatus('serverStatus', `Error: ${error.message}`, 'error');
                    addLog(`Server status error: ${error.message}`, 'error');
                }
            }

            async function checkLatestJob() {
                try {
                    addLog('Getting latest job...');
                    const response = await fetch('/latest');
                    const data = await response.json();

                    if (data.job_id) {
                        showStatus('latestJob',
                            `Job ID: ${data.job_id}<br>` +
                            `Status: ${data.progress?.status || 'unknown'}<br>` +
                            `Progress: ${data.progress?.overall_progress || 0}%`, 'success');
                        addLog(`Latest job: ${data.job_id}`, 'success');
                    } else {
                        showStatus('latestJob', data.message, 'info');
                        addLog(data.message);
                    }
                } catch (error) {
                    showStatus('latestJob', `Error: ${error.message}`, 'error');
                    addLog(`Latest job error: ${error.message}`, 'error');
                }
            }

            function testWebSocket() {
                const jobId = document.getElementById('testJobId').value;
                if (!jobId) {
                    showStatus('wsStatus', 'Please enter a job ID', 'error');
                    return;
                }

                disconnectWebSocket();

                addLog(`Connecting to WebSocket for job: ${jobId}`);
                const wsUrl = `ws://localhost:8675/ws/progress/${jobId}`;
                testWs = new WebSocket(wsUrl);

                testWs.onopen = function() {
                    showStatus('wsStatus', `Connected to ${jobId}`, 'success');
                    addLog('WebSocket connected successfully', 'success');
                };

                testWs.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        addLog(`Received: ${data.message || 'Progress update'}`);
                    } catch (e) {
                        addLog(`Raw message: ${event.data}`);
                    }
                };

                testWs.onclose = function() {
                    showStatus('wsStatus', 'WebSocket closed', 'info');
                    addLog('WebSocket connection closed');
                };

                testWs.onerror = function(error) {
                    showStatus('wsStatus', `WebSocket error: ${error.message}`, 'error');
                    addLog(`WebSocket error: ${error.message}`, 'error');
                };
            }

            function disconnectWebSocket() {
                if (testWs) {
                    testWs.close();
                    testWs = null;
                    showStatus('wsStatus', 'Disconnected', 'info');
                    addLog('WebSocket disconnected');
                }
            }

            // Auto-check server status on load
            window.onload = function() {
                checkServerStatus();
            };
        </script>
    </body>
    </html>
    """


def _get_monitor_html(job_id: str) -> str:
    """Generate HTML content for job monitor page."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Job Monitor - {job_id}</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #007acc;
            }}
            .job-id {{
                font-family: 'Courier New', monospace;
                background: #f0f8ff;
                padding: 5px 10px;
                border-radius: 5px;
                color: #007acc;
            }}
            .status {{
                margin: 20px 0;
                padding: 15px;
                border-radius: 5px;
                font-weight: bold;
            }}
            .status.running {{ background-color: #fff3cd; color: #856404; }}
            .status.completed {{ background-color: #d4edda; color: #155724; }}
            .status.failed {{ background-color: #f8d7da; color: #721c24; }}
            .status.connecting {{ background-color: #cce7ff; color: #004085; }}
            .progress-bar {{
                width: 100%;
                height: 20px;
                background-color: #e9ecef;
                border-radius: 10px;
                overflow: hidden;
                margin: 10px 0;
            }}
            .progress-fill {{
                height: 100%;
                background-color: #007acc;
                width: 0%;
                transition: width 0.3s ease;
            }}
            .details {{
                margin: 20px 0;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 5px;
                border-left: 4px solid #007acc;
            }}
            .log {{
                margin: 20px 0;
                padding: 15px;
                background: #1e1e1e;
                color: #ffffff;
                font-family: 'Courier New', monospace;
                border-radius: 5px;
                max-height: 300px;
                overflow-y: auto;
                font-size: 12px;
                line-height: 1.4;
            }}
            .connection-status {{
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 5px 10px;
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
            }}
            .connected {{ background: #d4edda; color: #155724; }}
            .disconnected {{ background: #f8d7da; color: #721c24; }}
            .reconnecting {{ background: #fff3cd; color: #856404; }}
        </style>
    </head>
    <body>
        <div class="connection-status" id="connectionStatus">Connecting...</div>

        <div class="container">
            <div class="header">
                <h1>🚀 Crackerjack Job Monitor</h1>
                <p>Job ID: <span class="job-id">{job_id}</span></p>
            </div>

            <div class="status connecting" id="status">
                Status: Connecting to job...
            </div>

            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div id="progressText">Progress: 0%</div>

            <div class="details" id="details">
                <strong>Current Stage:</strong> <span id="currentStage">Initializing</span><br>
                <strong>Iteration:</strong> <span id="iteration">0</span> / <span id="maxIterations">10</span><br>
                <strong>Message:</strong> <span id="message">Connecting...</span>
            </div>

            <div class="log" id="log">
                <div>Connecting to WebSocket...</div>
            </div>
        </div>

        <script>
            const jobId = '{job_id}';
            const wsUrl = `ws://localhost:8675/ws/progress/${{jobId}}`;
            let ws = null;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 10;

            const elements = {{
                status: document.getElementById('status'),
                progressFill: document.getElementById('progressFill'),
                progressText: document.getElementById('progressText'),
                currentStage: document.getElementById('currentStage'),
                iteration: document.getElementById('iteration'),
                maxIterations: document.getElementById('maxIterations'),
                message: document.getElementById('message'),
                log: document.getElementById('log'),
                connectionStatus: document.getElementById('connectionStatus')
            }};

            function updateConnectionStatus(status) {{
                elements.connectionStatus.className = 'connection-status ' + status;
                elements.connectionStatus.textContent = {{
                    'connected': '🟢 Connected',
                    'disconnected': '🔴 Disconnected',
                    'reconnecting': '🟡 Reconnecting...'
                }}[status] || '⚪ Unknown';
            }}

            function addLogEntry(message, type = 'info') {{
                const timestamp = new Date().toLocaleTimeString();
                const logEntry = document.createElement('div');
                logEntry.textContent = `[${{timestamp}}] ${{message}}`;
                if (type === 'error') logEntry.style.color = '#ff6b6b';
                if (type === 'success') logEntry.style.color = '#51cf66';
                elements.log.appendChild(logEntry);
                elements.log.scrollTop = elements.log.scrollHeight;
            }}

            function updateProgress(data) {{
                const progress = data.overall_progress || 0;
                const status = data.status || 'unknown';

                elements.progressFill.style.width = progress + '%';
                elements.progressText.textContent = `Progress: ${{progress}}%`;

                elements.status.textContent = `Status: ${{status}}`;
                elements.status.className = 'status ' + status.toLowerCase();

                elements.currentStage.textContent = data.current_stage || 'Unknown';
                elements.iteration.textContent = data.iteration || 0;
                elements.maxIterations.textContent = data.max_iterations || 10;
                elements.message.textContent = data.message || 'No message';

                addLogEntry(`${{data.current_stage || 'Unknown stage'}}: ${{data.message || 'No message'}}`,
                           status === 'failed' ? 'error' : status === 'completed' ? 'success' : 'info');
            }}

            function connect() {{
                if (ws && ws.readyState === WebSocket.OPEN) return;

                updateConnectionStatus('reconnecting');
                addLogEntry('Connecting to WebSocket...');

                ws = new WebSocket(wsUrl);

                ws.onopen = function() {{
                    updateConnectionStatus('connected');
                    addLogEntry('Connected to WebSocket', 'success');
                    reconnectAttempts = 0;
                }};

                ws.onmessage = function(event) {{
                    try {{
                        const data = JSON.parse(event.data);
                        updateProgress(data);
                    }} catch (e) {{
                        addLogEntry('Error parsing message: ' + e.message, 'error');
                    }}
                }};

                ws.onclose = function() {{
                    updateConnectionStatus('disconnected');
                    addLogEntry('WebSocket connection closed');
                    if (reconnectAttempts < maxReconnectAttempts) {{
                        setTimeout(() => {{
                            reconnectAttempts++;
                            addLogEntry(`Attempting to reconnect (${{reconnectAttempts}}/${{maxReconnectAttempts}})...`);
                            connect();
                        }}, 2000);
                    }} else {{
                        addLogEntry('Maximum reconnection attempts reached', 'error');
                    }}
                }};

                ws.onerror = function(error) {{
                    addLogEntry('WebSocket error occurred', 'error');
                    updateConnectionStatus('disconnected');
                }};
            }}

            // Start connection
            connect();

            // Periodically check connection health
            setInterval(() => {{
                if (!ws || ws.readyState !== WebSocket.OPEN) {{
                    if (reconnectAttempts < maxReconnectAttempts) {{
                        connect();
                    }}
                }}
            }}, 5000);
        </script>
    </body>
    </html>
    """


def register_endpoints(
    app: FastAPI,
    job_manager: JobManager,
    progress_dir: Path,
) -> None:
    @app.get("/")
    async def get_status():
        try:
            jobs = _build_job_list(job_manager, progress_dir)
            return _build_status_response(job_manager, jobs)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @app.get("/latest")
    async def get_latest_job():
        try:
            latest_job_id = job_manager.get_latest_job_id()

            if not latest_job_id:
                return {
                    "status": "no_jobs",
                    "message": "No jobs found",
                    "job_id": None,
                    "progress": None,
                }

            progress_data = job_manager.get_job_progress(latest_job_id)

            return {
                "status": "success",
                "message": f"Latest job: {latest_job_id}",
                "job_id": latest_job_id,
                "progress": progress_data,
                "websocket_url": f"ws://localhost:8675/ws/progress/{latest_job_id}",
                "monitor_url": f"http://localhost:8675/monitor/{latest_job_id}",
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get latest job: {e}",
                "job_id": None,
                "progress": None,
            }

    @app.get("/monitor/{job_id}")
    async def get_job_monitor_page(job_id: str):
        if not job_manager.validate_job_id(job_id):
            return HTMLResponse(
                content="<h1>Error</h1><p>Invalid job ID</p>",
                status_code=400,
            )
        return HTMLResponse(content=_get_monitor_html(job_id))

    @app.get("/test")
    async def get_test_page():
        return HTMLResponse(content=_get_test_html())
