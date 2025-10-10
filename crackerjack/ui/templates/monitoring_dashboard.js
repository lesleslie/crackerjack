
        
        const wsUrl = `ws://${window.location.host}/ws/metrics`;
        let ws = null;
        let reconnectInterval = 5000;
        
        
        function connect() {
            ws = new WebSocket(wsUrl);
            ws.onopen = handleWebSocketOpen;
            ws.onmessage = handleWebSocketMessage;
            ws.onclose = handleWebSocketClose;
            ws.onerror = handleWebSocketError;
        }

        function handleWebSocketOpen() {
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('connection-status').className = 'connection-status connected';
            log('Connected to monitoring server');
        }

        function handleWebSocketMessage(event) {
            const message = JSON.parse(event.data);
            if (message.type === 'metrics_update' || message.type === 'initial_metrics') {
                updateDashboard(message.data);
            }
        }

        function handleWebSocketClose() {
            document.getElementById('connection-status').textContent = 'Disconnected';
            document.getElementById('connection-status').className = 'connection-status disconnected';
            log('Disconnected from monitoring server');
            setTimeout(connect, reconnectInterval);
        }

        function handleWebSocketError(error) {
            log(`WebSocket error: ${error}`);
        }
        
        
        function updateDashboard(data) {
            updateSystemMetrics(data.system);
            updateQualityMetrics(data.quality);
            updateWorkflowMetrics(data.workflow);
            updateAgentMetrics(data.agents);
        }

        function updateSystemMetrics(system) {
            document.getElementById('cpu').textContent = system.cpu_usage.toFixed(1) + '%';
            document.getElementById('memory').textContent = (system.memory_usage_mb / 1024).toFixed(1) + 'GB';
            document.getElementById('uptime').textContent = formatUptime(system.uptime_seconds);
        }

        function updateQualityMetrics(quality) {
            document.getElementById('success-rate').textContent = (quality.success_rate * 100).toFixed(1) + '%';
            document.getElementById('issues-fixed').textContent = quality.issues_fixed;
            document.getElementById('coverage').textContent = (quality.test_coverage * 100).toFixed(1) + '%';
        }

        function updateWorkflowMetrics(workflow) {
            document.getElementById('jobs-completed').textContent = workflow.jobs_completed;
            document.getElementById('avg-duration').textContent = workflow.average_job_duration.toFixed(1) + 's';
            document.getElementById('throughput').textContent = workflow.throughput_per_hour.toFixed(1) + '/h';
        }

        function updateAgentMetrics(agents) {
            document.getElementById('active-agents').textContent = agents.active_agents;
            document.getElementById('total-fixes').textContent = agents.total_fixes_applied;
            document.getElementById('cache-hit-rate').textContent = (agents.cache_hit_rate * 100).toFixed(1) + '%';
        }

        function formatUptime(seconds) {
            if (seconds < 3600) return Math.floor(seconds/60) + 'm';
            if (seconds < 86400) return Math.floor(seconds/3600) + 'h';
            return Math.floor(seconds/86400) + 'd';
        }

        function log(message) {
            const logs = document.getElementById('logs');
            const timestamp = new Date().toLocaleTimeString();
            logs.innerHTML += `<div>[${timestamp}] ${message}</div>`;
            logs.scrollTop = logs.scrollHeight;
        }
        
        
        // Start connection
        connect();

        // Periodic ping to keep connection alive
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'ping'}));
            }
        }, 30000);
        
        